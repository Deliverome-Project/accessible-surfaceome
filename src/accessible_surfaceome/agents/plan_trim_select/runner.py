"""Runner for the plan → trim → select loop.

End-to-end driver:

1. Resolve the gene (gene_lookup) so we have a UniProt acc + HPA snapshot
   to hand to the planner as context.
2. Call Sonnet planner with the context → ``SearchPlan``.
3. Dispatch each ``SearchRequest`` via the existing tool entry points
   (``evidence_retrieval``, ``gene_literature``); collect every emitted
   ``EvidenceClaimDraft`` into a pool keyed by global clip_id.
4. Group clips by source paper; per-paper, ask Haiku to ``keep`` the
   load-bearing ones (one call per paper).
5. Build the trimmed menu, ask Sonnet selector to pick clip_ids with
   classifications (no ``quote`` field).
6. Look up each picked clip in the pool, construct ``EvidenceClaim``
   records with ``quote`` = ``Clip.quote`` (verbatim by construction).
7. Return the claim list + audit traces + usage summary.

Single-shot for the MVP — no ``needs_more_searches`` iteration yet; the
selector's ``additional_searches`` field is captured for inspection but
not re-dispatched. Add iteration once the single-shot quality holds.
"""

from __future__ import annotations

import json
import logging
import re
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

from anthropic import Anthropic
from anthropic.types import TextBlock
from pydantic import BaseModel, ValidationError

from accessible_surfaceome.agents._support.client import get_client
from accessible_surfaceome.agents._support.pricing import (
    UsageRecord,
    UsageSummary,
    record_from_response,
    summarize_usage,
)
from accessible_surfaceome.agents.plan_trim_select.schemas import (
    SearchPlan,
    SelectionResponse,
    TrimResponse,
)
from accessible_surfaceome.tools._shared.http import CachedHTTP, open_default_client
from accessible_surfaceome.tools._shared.models import (
    EvidenceClaim,
    EvidenceClaimDraft,
    IdentifierBundle,
    LiteraturePack,
    Paper,
)
from accessible_surfaceome.tools._shared.normalize import (
    find_quote_in_normalized,
    normalize_for_quote_matching,
)
from accessible_surfaceome.tools._shared.retraction_watch import (
    RetractionIndex,
    empty as _empty_retraction_index,
)
from accessible_surfaceome.tools.evidence_retrieval import evidence_retrieval
from accessible_surfaceome.tools.gene_literature import gene_literature
from accessible_surfaceome.tools.gene_lookup import (
    db_panel,
    resolve,
    uniprot_summary,
)


logger = logging.getLogger(__name__)


PROMPTS_DIR = Path(__file__).parent / "prompts"
PLAN_PROMPT_PATH = PROMPTS_DIR / "plan_system.md"
SELECT_PROMPT_PATH = PROMPTS_DIR / "select_system.md"

SONNET_MODEL = "claude-sonnet-4-6"
HAIKU_MODEL = "claude-haiku-4-5-20251001"
HAIKU_PRICING_KEY = "claude-haiku-4-5"

MAX_TOKENS_PLAN = 4_000
MAX_TOKENS_TRIM = 4_000
MAX_TOKENS_SELECT = 16_000
MAX_REPAIRS = 2
TRIM_PREVIEW_CHARS = 700

# Cap per-paper clip pool size sent to Haiku trim. Above this, sort by score
# (evidence_retrieval drafts carry a score; paper_level drafts default to ~1).
MAX_CLIPS_PER_TRIM_CALL = 60

# How many plan iterations the loop runs in total: 1 initial plan + up to
# (MAX_PLAN_ITERATIONS - 1) follow-ups requested via needs_more_searches.
# Capped so the loop terminates even if the selector keeps asking.
MAX_PLAN_ITERATIONS = 3

_FENCED_JSON_RE = re.compile(r"```(?:json)?\s*(\{.*\})\s*```", re.DOTALL)


# ---------------------------------------------------------------------------
# Result + log records
# ---------------------------------------------------------------------------


@dataclass
class SearchLogEntry:
    """One executed search with its outcome (for audit + cost attribution)."""

    tool: str
    params: dict[str, Any]
    intent: str
    n_drafts: int
    n_papers: int
    elapsed_s: float
    error: str | None = None


@dataclass
class IterationLogEntry:
    """One plan→execute→trim→select cycle's headline stats. ``new_searches``
    counts only the searches executed in this iteration (so iteration 0 has
    the initial plan, iteration N has the selector's additional_searches)."""

    iteration: int
    new_searches: int
    new_drafts: int
    n_papers_after: int
    n_drafts_after: int
    n_kept_after_trim: int
    n_selections: int
    needs_more_searches: bool


@dataclass
class PlanTrimSelectResult:
    """Output of one end-to-end run."""

    gene: str
    bundle: IdentifierBundle | None
    plan: SearchPlan | None
    selection_response: SelectionResponse | None
    claims: list[EvidenceClaim] = field(default_factory=list)
    search_log: list[SearchLogEntry] = field(default_factory=list)
    iteration_log: list[IterationLogEntry] = field(default_factory=list)
    # Anchored-rate audit. Should be 100% by construction since we never
    # paraphrase, but verify so any regressions surface.
    n_claims: int = 0
    n_anchored: int = 0
    # Cost + token accounting per stage.
    plan_usage: UsageSummary = field(
        default_factory=lambda: UsageSummary(model=SONNET_MODEL)
    )
    trim_usage: UsageSummary = field(
        default_factory=lambda: UsageSummary(model=HAIKU_PRICING_KEY)
    )
    select_usage: UsageSummary = field(
        default_factory=lambda: UsageSummary(model=SONNET_MODEL)
    )
    # Pool stats (final, after all iterations).
    n_drafts_total: int = 0
    n_papers_total: int = 0
    n_kept_after_trim: int = 0
    n_iterations_run: int = 0
    # Free-text errors that didn't abort the run.
    warnings: list[str] = field(default_factory=list)
    elapsed_s: float = 0.0

    @property
    def total_cost_usd(self) -> float:
        return (
            self.plan_usage.cost_usd
            + self.trim_usage.cost_usd
            + self.select_usage.cost_usd
        )

    @property
    def pct_anchored(self) -> float | None:
        if not self.n_claims:
            return None
        return 100.0 * self.n_anchored / self.n_claims


# ---------------------------------------------------------------------------
# Step 0 — gene context
# ---------------------------------------------------------------------------


@dataclass
class GeneContext:
    """Bundled gene context the planner + selector both read.

    HPA evidence is rolled into ``db_panel_json`` (the DBVotePanel carries
    HPA's main location + reliability flag alongside the SURFY/CSPA votes).
    """

    gene: str
    bundle: IdentifierBundle
    uniprot_summary_json: str
    db_panel_json: str


def _build_gene_context(
    gene: str, *, http: CachedHTTP, retraction_index: RetractionIndex
) -> GeneContext:
    """Resolve gene + pull UniProt + DB-vote context for the planner."""

    bundle = resolve(symbol_or_acc=gene, http=http)
    if not bundle.uniprot_acc:
        raise LookupError(f"could not resolve {gene} to a UniProt accession")

    uniprot = uniprot_summary(uniprot_acc=bundle.uniprot_acc, http=http)
    db = db_panel(uniprot_acc=bundle.uniprot_acc, http=http)

    return GeneContext(
        gene=gene,
        bundle=bundle,
        uniprot_summary_json=uniprot.model_dump_json(indent=2),
        db_panel_json=db.model_dump_json(indent=2),
    )


# ---------------------------------------------------------------------------
# Step 1 — planner
# ---------------------------------------------------------------------------


def _extract_json(text: str) -> dict[str, Any] | None:
    matches = _FENCED_JSON_RE.findall(text)
    if not matches:
        return None
    try:
        return json.loads(matches[-1])
    except json.JSONDecodeError:
        return None


def _call_with_repair(
    client: Anthropic,
    *,
    model: str,
    system_prompt: str,
    user_prompt: str,
    schema: type[BaseModel],
    max_tokens: int,
    usage_sink: list[UsageRecord],
    label: str,
) -> tuple[BaseModel | None, dict[str, Any] | None, str]:
    """Repair-looped messages.create until the emitted JSON validates
    against ``schema``, capped at ``MAX_REPAIRS`` retries. Returns the
    parsed model (or None), the raw JSON (or None), and the final text.
    """

    messages: list[dict[str, Any]] = [{"role": "user", "content": user_prompt}]
    validation_error: str | None = None
    parsed: BaseModel | None = None
    raw_json: dict[str, Any] | None = None
    final_text = ""

    for attempt in range(MAX_REPAIRS + 1):
        resp = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=cast("Any", messages),
        )
        usage_sink.append(record_from_response(resp.usage, model))
        final_text = "\n".join(
            b.text for b in resp.content if isinstance(b, TextBlock)
        ).strip()
        raw_json = _extract_json(final_text)
        if raw_json is None:
            validation_error = "no fenced JSON block in model output"
        else:
            try:
                parsed = schema.model_validate(raw_json)
                return parsed, raw_json, final_text
            except ValidationError as exc:
                validation_error = str(exc)
        logger.info(
            "%s repair %d/%d — %s", label, attempt + 1, MAX_REPAIRS, validation_error[:200]
        )
        messages.append({"role": "assistant", "content": final_text})
        messages.append(
            {
                "role": "user",
                "content": (
                    f"Your JSON failed schema validation:\n\n{validation_error[:1500]}\n\n"
                    "Emit a corrected JSON object as one fenced ```json block. "
                    "Respect the schema exactly — no extra fields."
                ),
            }
        )
    logger.warning("%s validation failed after %d repairs", label, MAX_REPAIRS)
    return None, raw_json, final_text


def _run_planner(
    client: Anthropic, *, context: GeneContext, usage_sink: list[UsageRecord]
) -> SearchPlan | None:
    system_prompt = PLAN_PROMPT_PATH.read_text()
    plan_schema = json.dumps(SearchPlan.model_json_schema(), indent=2)
    user_prompt = (
        f"# Gene: {context.gene}\n\n"
        f"UniProt summary:\n```json\n{context.uniprot_summary_json}\n```\n\n"
        f"DB vote panel (includes HPA main_location + reliability):\n"
        f"```json\n{context.db_panel_json}\n```\n\n"
        "Emit one fenced ```json block matching this SearchPlan schema:\n\n"
        f"```json\n{plan_schema}\n```\n"
    )
    parsed, _, _ = _call_with_repair(
        client,
        model=SONNET_MODEL,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        schema=SearchPlan,
        max_tokens=MAX_TOKENS_PLAN,
        usage_sink=usage_sink,
        label="planner",
    )
    return parsed if isinstance(parsed, SearchPlan) else None


# ---------------------------------------------------------------------------
# Step 2 — execute the search plan
# ---------------------------------------------------------------------------


def _execute_plan(
    plan: SearchPlan,
    *,
    context: GeneContext,
    http: CachedHTTP,
    retraction_index: RetractionIndex,
) -> tuple[
    dict[str, EvidenceClaimDraft],
    list[SearchLogEntry],
    dict[str, list[EvidenceClaimDraft]],
    dict[int, Paper],
]:
    """Dispatch each search; collect drafts into a global pool keyed by
    ``clip_id``. Returns (pool, search_log, clips_by_source, discovered_papers).

    ``discovered_papers`` is a {pmid: Paper} dict populated from
    ``gene2pubmed`` and ``topic_search`` results — papers the planner
    surfaced but didn't fetch the body of. The selector reads this list
    to decide whether to iterate with ``fetch_abstract`` /
    ``fetch_fulltext`` calls for the most promising PMIDs.
    """

    pool: dict[str, EvidenceClaimDraft] = {}
    clips_by_source: dict[str, list[EvidenceClaimDraft]] = defaultdict(list)
    discovered_papers: dict[int, Paper] = {}
    search_log: list[SearchLogEntry] = []
    bundle = context.bundle
    acc = bundle.uniprot_acc

    for req in plan.searches:
        t0 = time.time()
        n_drafts = 0
        n_papers = 0
        err: str | None = None
        params: dict[str, Any] = {}
        try:
            if req.tool == "evidence_retrieval":
                params = {"category": req.category, "uniprot_acc": acc}
                if req.category is None:
                    raise ValueError("evidence_retrieval requires category")
                pack = evidence_retrieval(
                    uniprot_acc=acc,
                    category=req.category,
                    http=http,
                    retraction_index=retraction_index,
                )
                for draft in pack.evidence_claim_drafts:
                    _add_to_pool(draft, pool, clips_by_source)
                    n_drafts += 1
                n_papers = len(pack.papers)
            elif req.tool == "gene_literature":
                params = {"mode": req.mode}
                if req.mode == "gene2pubmed":
                    res = gene_literature(
                        mode="gene2pubmed",
                        uniprot_acc=acc,
                        hgnc_symbol=bundle.hgnc_symbol,
                        ncbi_gene_id=bundle.ncbi_gene_id,
                        aliases=bundle.aliases,
                        http=http,
                        retraction_index=retraction_index,
                    )
                    # gene2pubmed returns LiteraturePack (no drafts; just paper list).
                    # Each Paper carries title + abstract pre-populated from the
                    # EuropePMC search hits — surface them as discovered_papers
                    # so the selector can request fetch_abstract on iteration.
                    assert isinstance(res, LiteraturePack)
                    for paper in res.papers:
                        discovered_papers.setdefault(paper.pmid, paper)
                    n_papers = len(res.papers)
                elif req.mode == "topic_search":
                    if not req.anchors:
                        raise ValueError("topic_search requires anchors")
                    params["anchors"] = list(req.anchors)
                    res = gene_literature(
                        mode="topic_search",
                        uniprot_acc=acc,
                        hgnc_symbol=bundle.hgnc_symbol,
                        ncbi_gene_id=bundle.ncbi_gene_id,
                        aliases=bundle.aliases,
                        topic_anchors=list(req.anchors),
                        http=http,
                        retraction_index=retraction_index,
                    )
                    assert isinstance(res, LiteraturePack)
                    for paper in res.papers:
                        discovered_papers.setdefault(paper.pmid, paper)
                    n_papers = len(res.papers)
                elif req.mode == "fetch_abstract":
                    if not req.pmid:
                        raise ValueError("fetch_abstract requires pmid")
                    params["pmid"] = req.pmid
                    paper = gene_literature(
                        mode="fetch_abstract",
                        pmid=req.pmid,
                        http=http,
                        retraction_index=retraction_index,
                    )
                    assert isinstance(paper, Paper)
                    for draft in paper.evidence_claim_drafts:
                        _add_to_pool(draft, pool, clips_by_source)
                        n_drafts += 1
                    n_papers = 1
                elif req.mode == "fetch_fulltext":
                    if not req.pmcid:
                        raise ValueError("fetch_fulltext requires pmcid")
                    params["pmcid"] = req.pmcid
                    paper = gene_literature(
                        mode="fetch_fulltext",
                        pmcid=req.pmcid,
                        http=http,
                        retraction_index=retraction_index,
                    )
                    assert isinstance(paper, Paper)
                    for draft in paper.evidence_claim_drafts:
                        _add_to_pool(draft, pool, clips_by_source)
                        n_drafts += 1
                    n_papers = 1
                else:
                    raise ValueError(f"unknown gene_literature mode: {req.mode!r}")
            else:
                raise ValueError(f"unknown tool: {req.tool!r}")
        except Exception as exc:  # noqa: BLE001 — search-level robustness
            err = f"{type(exc).__name__}: {exc}"
            logger.warning("search failed: %s %s → %s", req.tool, params, err)
        elapsed = time.time() - t0
        search_log.append(
            SearchLogEntry(
                tool=req.tool,
                params=params,
                intent=req.intent,
                n_drafts=n_drafts,
                n_papers=n_papers,
                elapsed_s=round(elapsed, 2),
                error=err,
            )
        )

    return pool, search_log, dict(clips_by_source), discovered_papers


def _add_to_pool(
    draft: EvidenceClaimDraft,
    pool: dict[str, EvidenceClaimDraft],
    by_source: dict[str, list[EvidenceClaimDraft]],
) -> None:
    """Insert draft into the pool with a globally-unique clip_id.

    Draft.suggested_evidence_id already encodes (source_id, section, seq) and
    is unique within one tool call; conflicts across calls (same paper hit by
    multiple categories) get a `_k` suffix.
    """

    clip_id = draft.suggested_evidence_id
    if clip_id in pool:
        # Already have this exact (source, section, seq) — likely same snippet
        # re-emitted by another category. Skip duplicate quote.
        if pool[clip_id].quote == draft.quote:
            return
        # Same id but different content — suffix and keep both.
        k = 2
        while f"{clip_id}_{k}" in pool:
            k += 1
        clip_id = f"{clip_id}_{k}"
    # Re-stamp the draft with its global clip_id.
    redrafted = draft.model_copy(update={"suggested_evidence_id": clip_id})
    pool[clip_id] = redrafted
    by_source[redrafted.source_id].append(redrafted)


# ---------------------------------------------------------------------------
# Step 3 — Haiku trim per paper
# ---------------------------------------------------------------------------


TRIM_PROMPT = """You are reviewing pre-extracted verbatim clips from a scientific \
paper to assemble an evidence corpus for a deep-dive surface-accessibility annotation \
of the protein **{gene}**.

For each clip below, decide whether it is load-bearing for one of these evidence \
categories:

* Surface expression / localization (cell-surface flow cytometry, surface \
biotinylation, mass-spec surfaceome, non-permeabilized IF, IHC with membrane staining)
* Topology (single-pass, multi-pass, 7-TM, GPI-anchored, ECD/ICD)
* Subcellular localization including ciliary, junctional, basolateral, apical, \
dual-localization
* Tissue / cell-type expression for {gene}
* State-dependent surface presence (internalization, recycling, ligand-driven)
* Shed / secreted form
* Epitope masking (glycan, partner protein, conformational)
* Therapeutic engagement of the ECD (clinical-stage antibodies, ADCs)
* Genetic / loss-of-function evidence connecting the protein to phenotype

Drop clips that are:
* Generic background / introduction not specifically about {gene}'s surface
* Pure intracellular signaling unrelated to surface presentation
* Acknowledgments, funding, conflicts of interest
* Pure methods recipes with no result tied to {gene}
* Figure schematics ("Schematic of...", "Workflow for...") without underlying data
* Paper-aim statements ("We aimed to...", "Here we report...")

Paper id: {paper_id}
Clips ({n_clips}):

{numbered_clips}

Respond ONLY with one fenced ```json block matching this TrimResponse schema:

```json
{schema}
```

List ONLY the clip_ids to keep. Anything not listed is dropped. Reason ≤140 chars."""


def _format_clips_for_trim(clips: list[EvidenceClaimDraft]) -> str:
    lines: list[str] = []
    for c in clips:
        preview = c.quote if len(c.quote) <= TRIM_PREVIEW_CHARS else c.quote[:TRIM_PREVIEW_CHARS] + " […]"
        meta = f"section={c.section}, score={c.score:.1f}, hallmark={c.hallmark_phrase}"
        lines.append(f"--- {c.suggested_evidence_id} ({meta}) ---\n{preview}")
    return "\n\n".join(lines)


def _run_trim(
    client: Anthropic,
    *,
    clips_by_source: dict[str, list[EvidenceClaimDraft]],
    gene: str,
    usage_sink: list[UsageRecord],
) -> dict[str, TrimResponse]:
    """One Haiku call per paper. Returns {source_id: TrimResponse}."""

    schema_str = json.dumps(TrimResponse.model_json_schema(), indent=2)
    results: dict[str, TrimResponse] = {}

    for source_id, clips in clips_by_source.items():
        if not clips:
            continue
        bounded = sorted(clips, key=lambda c: c.score, reverse=True)[:MAX_CLIPS_PER_TRIM_CALL]
        prompt = TRIM_PROMPT.format(
            gene=gene,
            paper_id=source_id,
            n_clips=len(bounded),
            numbered_clips=_format_clips_for_trim(bounded),
            schema=schema_str,
        )
        try:
            resp = client.messages.create(
                model=HAIKU_MODEL,
                max_tokens=MAX_TOKENS_TRIM,
                messages=cast("Any", [{"role": "user", "content": prompt}]),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("trim call failed for %s: %s", source_id, exc)
            continue
        usage_sink.append(record_from_response(resp.usage, HAIKU_PRICING_KEY))
        text = "\n".join(
            b.text for b in resp.content if isinstance(b, TextBlock)
        ).strip()
        raw = _extract_json(text)
        if raw is None:
            logger.warning("trim for %s emitted no JSON; treating as no keeps", source_id)
            results[source_id] = TrimResponse(paper_id=source_id, kept=[])
            continue
        try:
            tr = TrimResponse.model_validate(raw)
            # The model sometimes echoes the paper_id; normalize it.
            tr = tr.model_copy(update={"paper_id": source_id})
            # Filter out kept ids that aren't in our submitted clip set —
            # the model occasionally hallucinates ids.
            known_ids = {c.suggested_evidence_id for c in bounded}
            tr = tr.model_copy(
                update={"kept": [k for k in tr.kept if k.clip_id in known_ids]}
            )
            results[source_id] = tr
        except ValidationError as exc:
            logger.warning("trim validation failed for %s: %s", source_id, exc)
            results[source_id] = TrimResponse(paper_id=source_id, kept=[])

    return results


# ---------------------------------------------------------------------------
# Step 4 — Sonnet selector
# ---------------------------------------------------------------------------


def _format_menu_for_selector(
    pool: dict[str, EvidenceClaimDraft], trim_results: dict[str, TrimResponse]
) -> str:
    """Render kept clips as a single markdown menu the selector reads."""

    blocks: list[str] = []
    for source_id, tr in sorted(trim_results.items()):
        if not tr.kept:
            continue
        blocks.append(f"## {source_id}\n")
        for kept in tr.kept:
            draft = pool.get(kept.clip_id)
            if draft is None:
                continue
            reason = f"  _Haiku reason:_ {kept.reason}" if kept.reason else ""
            blocks.append(
                f"### clip_id: `{kept.clip_id}`\n"
                f"_section:_ {draft.section} · _hallmark:_ {draft.hallmark_phrase}\n"
                f"{reason}\n\n"
                f"> {draft.quote}\n"
            )
    return "\n".join(blocks)


def _pmids_already_fetched(pool: dict[str, EvidenceClaimDraft]) -> set[int]:
    """Return PMIDs for papers that ALREADY have drafts in the pool.

    Used to mark gene2pubmed / topic_search results as fetched vs not,
    so the selector knows which still need a fetch_abstract / fetch_fulltext
    follow-up to contribute clips.

    Pool source_ids look like ``PMC:PMC12345`` or ``PMID:67890`` or
    ``HPA:GENE``. We extract numeric PMIDs from any PMID-prefixed source;
    PMC-only sources don't tell us the PMID directly, but the selector
    can match by PMCID via the discovered_papers list.
    """

    pmids: set[int] = set()
    for draft in pool.values():
        sid = draft.source_id
        if sid.startswith("PMID:"):
            try:
                pmids.add(int(sid.split(":", 1)[1]))
            except ValueError:
                pass
    return pmids


def _format_unfetched_inventory(
    discovered: dict[int, Paper], fetched_pmids: set[int], cap: int = 30
) -> str:
    """Render a markdown list of papers discovered via gene2pubmed / topic_search
    that haven't been deep-dived yet. Each entry has title + a short abstract
    preview + the PMID so the selector can request fetch_abstract."""

    rows: list[str] = []
    # Prioritize: non-retracted, non-review, has abstract, recent year.
    candidates = [
        p for p in discovered.values() if p.pmid not in fetched_pmids
    ]
    candidates.sort(
        key=lambda p: (
            p.is_retracted,  # False first
            p.year is None,  # known year first
            -(p.year or 0),  # newest first
            p.is_review,     # primary first
        )
    )
    for paper in candidates[:cap]:
        flags = []
        if paper.is_review:
            flags.append("review")
        if paper.is_retracted:
            flags.append("RETRACTED")
        if paper.is_pmc_oa and paper.pmc_id:
            flags.append(f"PMC OA: {paper.pmc_id}")
        flag_str = f" [{', '.join(flags)}]" if flags else ""
        abstract_preview = (
            (paper.abstract or "(no abstract)")[:300]
            + ("…" if paper.abstract and len(paper.abstract) > 300 else "")
        )
        rows.append(
            f"- **PMID:{paper.pmid}** ({paper.year or '?'}){flag_str} — _{paper.title}_\n"
            f"  > {abstract_preview}"
        )
    if not rows:
        return "_(no unfetched discovered papers — gene2pubmed/topic_search returned only papers already in the pool, or were not in the plan)_"
    n_total = len(candidates)
    overflow = (
        f"\n\n_…showing {cap} of {n_total} unfetched papers; iterate to surface more._"
        if n_total > cap
        else ""
    )
    return "\n\n".join(rows) + overflow


def _run_selector(
    client: Anthropic,
    *,
    context: GeneContext,
    menu_markdown: str,
    unfetched_inventory: str,
    n_kept: int,
    n_unfetched: int,
    iteration: int,
    max_iterations: int,
    usage_sink: list[UsageRecord],
) -> SelectionResponse | None:
    system_prompt = SELECT_PROMPT_PATH.read_text()
    schema_str = json.dumps(SelectionResponse.model_json_schema(), indent=2)
    iters_left = max_iterations - iteration - 1
    iteration_banner = (
        f"## Iteration {iteration + 1} of up to {max_iterations} "
        f"({iters_left} follow-up{'s' if iters_left != 1 else ''} available)\n\n"
        "If you finalize selections this turn (`needs_more_searches: false`), "
        "the orchestrator promotes them and the loop ends.\n"
        "If you set `needs_more_searches: true` with up to 3 "
        "`additional_searches`, those run, the menu is augmented, and you "
        "see the menu again next turn. "
        + (
            "This is the last iteration — `additional_searches` will be ignored."
            if iters_left == 0
            else f"You can iterate at most {iters_left} more time(s)."
        )
        + "\n\n"
    )
    user_prompt = (
        f"# Gene: {context.gene}\n\n"
        f"{iteration_banner}"
        f"UniProt summary (for context):\n```json\n{context.uniprot_summary_json}\n```\n\n"
        f"DB vote panel (HPA + SURFY/CSPA, for context):\n"
        f"```json\n{context.db_panel_json}\n```\n\n"
        f"## Trimmed clip menu ({n_kept} clips across multiple sources)\n\n"
        f"{menu_markdown}\n\n"
        f"## Discovered papers not yet deep-dived ({n_unfetched} papers)\n\n"
        "These came from gene2pubmed / topic_search calls but their bodies "
        "haven't been fetched, so they contributed zero clips to the menu "
        "above. If any look load-bearing, set `needs_more_searches: true` "
        "and request `fetch_abstract` (cheap) or `fetch_fulltext` (more "
        "clips, OA papers only) in `additional_searches`.\n\n"
        f"{unfetched_inventory}\n\n"
        "Pick the clips that should become evidence rows. Use the clip_id as it "
        "appears above. Emit one fenced ```json block matching this "
        "SelectionResponse schema:\n\n"
        f"```json\n{schema_str}\n```\n"
    )
    parsed, _, _ = _call_with_repair(
        client,
        model=SONNET_MODEL,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        schema=SelectionResponse,
        max_tokens=MAX_TOKENS_SELECT,
        usage_sink=usage_sink,
        label="selector",
    )
    return parsed if isinstance(parsed, SelectionResponse) else None


# ---------------------------------------------------------------------------
# Step 5 — promote selections → EvidenceClaim records
# ---------------------------------------------------------------------------


def _promote_selections(
    selection_response: SelectionResponse,
    *,
    pool: dict[str, EvidenceClaimDraft],
) -> tuple[list[EvidenceClaim], list[str]]:
    """Build EvidenceClaim records from selections. Quote auto-filled from
    the pool's verbatim text — agent never typed it. Returns (claims, warnings).
    """

    claims: list[EvidenceClaim] = []
    warnings: list[str] = []
    seq = 1
    for sel in selection_response.selections:
        draft = pool.get(sel.clip_id)
        if draft is None:
            warnings.append(
                f"selector picked unknown clip_id={sel.clip_id!r}; skipping"
            )
            continue
        claim = EvidenceClaim(
            evidence_id=f"pts_evi_{seq:02d}",
            claim=sel.claim,
            claim_type=sel.claim_type,
            direction=sel.direction,
            evidence_type=sel.evidence_type,
            evidence_tier=sel.evidence_tier,
            confidence=sel.confidence,
            assay_context=sel.assay_context,
            source_id=draft.source_id,
            quote=draft.quote,  # verbatim, copied from the pool
            section=draft.section,
            figure_or_table_id=draft.figure_or_table_id,
        )
        claims.append(claim)
        seq += 1
    return claims, warnings


# ---------------------------------------------------------------------------
# End-to-end driver
# ---------------------------------------------------------------------------


def run_plan_trim_select(
    gene: str,
    *,
    client: Anthropic | None = None,
    http: CachedHTTP | None = None,
    retraction_index: RetractionIndex | None = None,
) -> PlanTrimSelectResult:
    """Run plan → trim → select for one gene. Returns the full audit result."""

    t0 = time.time()
    client = client or get_client()
    own_http = http is None
    http = http or open_default_client()
    retraction = retraction_index or _empty_retraction_index()

    plan_usage: list[UsageRecord] = []
    trim_usage: list[UsageRecord] = []
    select_usage: list[UsageRecord] = []

    result = PlanTrimSelectResult(
        gene=gene, bundle=None, plan=None, selection_response=None
    )

    # Cumulative state across plan iterations.
    pool: dict[str, EvidenceClaimDraft] = {}
    clips_by_source: dict[str, list[EvidenceClaimDraft]] = defaultdict(list)
    cumulative_search_log: list[SearchLogEntry] = []
    cumulative_discovered: dict[int, Paper] = {}
    sel_resp: SelectionResponse | None = None

    try:
        # Step 0 — gene context (once per run)
        context = _build_gene_context(gene, http=http, retraction_index=retraction)
        result.bundle = context.bundle
        logger.info("gene context built: %s → %s", gene, context.bundle.uniprot_acc)

        # Step 1 — initial planner call
        initial_plan = _run_planner(client, context=context, usage_sink=plan_usage)
        if initial_plan is None:
            result.warnings.append("planner returned no valid SearchPlan; aborting")
            return result
        result.plan = initial_plan
        logger.info("planner emitted %d searches", len(initial_plan.searches))

        # Plan→execute→trim→select loop. Iteration 0 uses initial_plan;
        # subsequent iterations use the selector's additional_searches.
        current_plan: SearchPlan | None = initial_plan
        for iteration in range(MAX_PLAN_ITERATIONS):
            if current_plan is None or not current_plan.searches:
                break

            # Step 2 — execute this iteration's searches, merge into the
            # cumulative pool. _execute_plan returns its own fresh pool; we
            # merge the new drafts via _add_to_pool so dedup works across
            # iterations.
            iter_pool, iter_log, iter_by_source, iter_discovered = _execute_plan(
                current_plan,
                context=context,
                http=http,
                retraction_index=retraction,
            )
            n_new_drafts = 0
            for draft in iter_pool.values():
                if draft.suggested_evidence_id in pool:
                    continue
                pool[draft.suggested_evidence_id] = draft
                clips_by_source[draft.source_id].append(draft)
                n_new_drafts += 1
            cumulative_search_log.extend(iter_log)
            for pmid, paper in iter_discovered.items():
                cumulative_discovered.setdefault(pmid, paper)
            logger.info(
                "iteration %d: executed %d searches → %d new drafts (pool now %d across %d papers)",
                iteration,
                len(current_plan.searches),
                n_new_drafts,
                len(pool),
                len(clips_by_source),
            )

            if not pool:
                result.warnings.append(
                    f"iteration {iteration} returned no drafts; nothing to trim or select"
                )
                break

            # Step 3 — re-trim ALL papers in the cumulative pool. Re-trim
            # rather than caching per-paper because new clips for an existing
            # paper would otherwise stay invisible; Haiku is cheap enough
            # ($~0.01/paper) that re-trim per iteration is fine.
            trim_results = _run_trim(
                client,
                clips_by_source=dict(clips_by_source),
                gene=gene,
                usage_sink=trim_usage,
            )
            n_kept = sum(len(t.kept) for t in trim_results.values())
            logger.info(
                "iteration %d: trim kept %d/%d clips across %d papers",
                iteration, n_kept, len(pool), len(trim_results),
            )

            if n_kept == 0:
                result.warnings.append(
                    f"iteration {iteration}: trim kept zero clips; selector skipped"
                )
                break

            # Step 4 — selector sees the full cumulative menu + a list of
            # papers that were discovered (via gene2pubmed / topic_search)
            # but haven't had their bodies fetched yet. The selector can
            # use this to plan additional_searches.
            menu = _format_menu_for_selector(pool, trim_results)
            fetched_pmids = _pmids_already_fetched(pool)
            unfetched_inventory = _format_unfetched_inventory(
                cumulative_discovered, fetched_pmids
            )
            sel_resp = _run_selector(
                client,
                context=context,
                menu_markdown=menu,
                unfetched_inventory=unfetched_inventory,
                n_kept=n_kept,
                n_unfetched=sum(
                    1 for p in cumulative_discovered.values()
                    if p.pmid not in fetched_pmids
                ),
                iteration=iteration,
                max_iterations=MAX_PLAN_ITERATIONS,
                usage_sink=select_usage,
            )
            if sel_resp is None:
                result.warnings.append(
                    f"iteration {iteration}: selector returned no valid SelectionResponse"
                )
                break

            result.iteration_log.append(
                IterationLogEntry(
                    iteration=iteration,
                    new_searches=len(current_plan.searches),
                    new_drafts=n_new_drafts,
                    n_papers_after=len(clips_by_source),
                    n_drafts_after=len(pool),
                    n_kept_after_trim=n_kept,
                    n_selections=len(sel_resp.selections),
                    needs_more_searches=sel_resp.needs_more_searches,
                )
            )

            # Decide whether to iterate.
            if not sel_resp.needs_more_searches or not sel_resp.additional_searches:
                logger.info(
                    "iteration %d: selector finalized %d selections (no more searches)",
                    iteration, len(sel_resp.selections),
                )
                break
            if iteration + 1 >= MAX_PLAN_ITERATIONS:
                result.warnings.append(
                    f"reached MAX_PLAN_ITERATIONS={MAX_PLAN_ITERATIONS}; "
                    f"selector requested more searches but the loop is capped"
                )
                logger.info(
                    "iteration %d: selector requested more searches but cap reached",
                    iteration,
                )
                break

            logger.info(
                "iteration %d: selector requested %d more searches; iterating",
                iteration, len(sel_resp.additional_searches),
            )
            current_plan = SearchPlan(
                searches=sel_resp.additional_searches,
                rationale=f"(iteration {iteration + 1} follow-up requested by selector)",
            )

        # End of plan iteration loop. Wrap up.
        result.search_log = cumulative_search_log
        result.n_drafts_total = len(pool)
        result.n_papers_total = len(clips_by_source)
        if result.iteration_log:
            result.n_kept_after_trim = result.iteration_log[-1].n_kept_after_trim
        result.n_iterations_run = len(result.iteration_log)
        result.selection_response = sel_resp

        if sel_resp is None:
            return result

        # Step 5 — promote final selections
        claims, promote_warnings = _promote_selections(sel_resp, pool=pool)
        result.claims = claims
        result.warnings.extend(promote_warnings)
        result.n_claims = len(claims)
        result.n_anchored = sum(1 for c in claims if _is_anchored(c, pool))

        logger.info(
            "FINAL: %d iterations → %d claims (%d anchored, %.1f%%)",
            result.n_iterations_run,
            result.n_claims,
            result.n_anchored,
            100.0 * result.n_anchored / max(1, result.n_claims),
        )

    finally:
        result.plan_usage = summarize_usage(plan_usage, SONNET_MODEL)
        result.trim_usage = summarize_usage(trim_usage, HAIKU_PRICING_KEY)
        result.select_usage = summarize_usage(select_usage, SONNET_MODEL)
        result.elapsed_s = round(time.time() - t0, 1)
        if own_http:
            http.close()

    return result


def _is_anchored(claim: EvidenceClaim, pool: dict[str, EvidenceClaimDraft]) -> bool:
    """Confirm the claim's quote is a verbatim substring of its source body.

    Since the quote is copied from a pool draft (which was extracted as a
    substring of the source body in the first place), this should always
    pass — but verify explicitly so any drift surfaces.
    """

    # The pool's draft.quote is verbatim from the source body by construction
    # in evidence_retrieval._extract_snippets and gene_literature's
    # extract_paper_drafts. The promote step copies that quote into the
    # claim. So substring identity is the right local check.
    for draft in pool.values():
        if draft.source_id == claim.source_id and draft.quote == claim.quote:
            return True
    # Fall back to a normalized substring check against any pool draft
    # from the same source (in case the model rewrote the quote field
    # we didn't expect — defensive only).
    nq = normalize_for_quote_matching(claim.quote)
    for draft in pool.values():
        if draft.source_id != claim.source_id:
            continue
        nb = normalize_for_quote_matching(draft.quote)
        if find_quote_in_normalized(nq, nb) is not None:
            return True
    return False
