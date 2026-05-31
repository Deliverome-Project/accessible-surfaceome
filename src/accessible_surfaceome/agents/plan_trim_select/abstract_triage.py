"""Abstract triage — Haiku per-paper 3-way routing.

Sits between discovery (gene2pubmed / topic_search / recent_corpus +
evidence_retrieval in discover-only mode all return paper metadata)
and trim/select. For each discovered paper, makes a single Haiku call
against the abstract to decide:

  discard         → drop from pool
  keep_abstract   → add the abstract as preview clip(s) to the pool
  worth_fetching  → fetch the body (PMC native → PMID→PMCID eLink →
                    Unpaywall), let it flow through normal body-clip
                    extraction; fall back to abstract clip(s) if the
                    body can't be retrieved

This is the cheap routing step; the selector (Sonnet) no longer has
to decide what to fetch — by the time it sees the menu, abstracts
that warrant a fetch have already been fetched and abstracts that
warrant inclusion are already preview clips.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from anthropic import Anthropic
from anthropic.types import TextBlock
from pydantic import ValidationError

from accessible_surfaceome.agents._support.pricing import (
    UsageRecord,
    record_from_response,
)
from accessible_surfaceome.agents.plan_trim_select.schemas import (
    AbstractTriageResponse,
)
from accessible_surfaceome.tools._shared.europepmc import fetch_fulltext
from accessible_surfaceome.tools._shared.http import CachedHTTP
from accessible_surfaceome.tools._shared.models import (
    EvidenceClaimDraft,
    IdentifierBundle,
    Paper,
)
from accessible_surfaceome.tools._shared.retraction_watch import RetractionIndex
from accessible_surfaceome.tools.evidence_retrieval import (
    _split_sentences,
    extract_paper_drafts,
)

# runner._add_to_pool is passed in to the action layer as ``add_to_pool_fn``
# rather than imported, so abstract_triage never imports runner (runner
# imports abstract_triage — keeping the dependency one-directional).

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent / "prompts"
ABSTRACT_TRIAGE_PROMPT_PATH = PROMPTS_DIR / "abstract_triage_system.md"

HAIKU_MODEL = "claude-haiku-4-5-20251001"
HAIKU_PRICING_KEY = "claude-haiku-4-5"
MAX_TOKENS_TRIAGE = 512
TRIAGE_CONCURRENCY = 10

_FENCED_JSON_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def _extract_json(text: str) -> dict[str, Any] | None:
    match = _FENCED_JSON_RE.search(text)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None


@dataclass
class TriageOutcome:
    paper_id: str
    response: AbstractTriageResponse | None
    usage: UsageRecord | None
    elapsed_s: float
    error: str | None = None


def triage_one_abstract(
    client: Anthropic,
    *,
    paper: Paper,
    gene: str,
    bundle: IdentifierBundle | None = None,
    prompt_template: str | None = None,
) -> TriageOutcome:
    """Single Haiku call to triage one paper's abstract.

    ``bundle`` carries the gene's synonyms (HGNC aliases + previous
    symbols + approved name). Without it, the agent has only the HGNC
    symbol to identify the gene, which leads it to treat the common
    name as a different protein (e.g. CD20 vs MS4A1). Passing the
    bundle is strongly recommended.
    """

    if not paper.abstract or not paper.abstract.strip():
        return TriageOutcome(
            paper_id=_paper_source_id(paper),
            response=None,
            usage=None,
            elapsed_s=0.0,
            error="no abstract",
        )

    template = prompt_template or ABSTRACT_TRIAGE_PROMPT_PATH.read_text()
    paper_id = _paper_source_id(paper)
    schema_str = json.dumps(AbstractTriageResponse.model_json_schema(), indent=2)
    prompt = template.format(
        gene=gene,
        synonyms=_format_synonyms(bundle),
        paper_id=paper_id,
        title=paper.title or "(no title)",
        year=str(paper.year) if paper.year else "(unknown)",
        abstract=paper.abstract.strip(),
        schema=schema_str,
    )

    t0 = time.perf_counter()
    try:
        resp = client.messages.create(
            model=HAIKU_MODEL,
            max_tokens=MAX_TOKENS_TRIAGE,
            messages=cast("Any", [{"role": "user", "content": prompt}]),
        )
    except Exception as exc:  # noqa: BLE001
        return TriageOutcome(
            paper_id=paper_id,
            response=None,
            usage=None,
            elapsed_s=round(time.perf_counter() - t0, 3),
            error=f"{type(exc).__name__}: {exc}",
        )

    elapsed = round(time.perf_counter() - t0, 3)
    usage = record_from_response(resp.usage, HAIKU_PRICING_KEY)
    text = "\n".join(
        b.text for b in resp.content if isinstance(b, TextBlock)
    ).strip()
    raw = _extract_json(text)
    if raw is None:
        return TriageOutcome(
            paper_id=paper_id,
            response=None,
            usage=usage,
            elapsed_s=elapsed,
            error="no fenced JSON block in model output",
        )

    try:
        parsed = AbstractTriageResponse.model_validate(raw)
        parsed = parsed.model_copy(update={"paper_id": paper_id})
        return TriageOutcome(
            paper_id=paper_id, response=parsed, usage=usage, elapsed_s=elapsed
        )
    except ValidationError as exc:
        return TriageOutcome(
            paper_id=paper_id,
            response=None,
            usage=usage,
            elapsed_s=elapsed,
            error=f"schema validation: {exc}",
        )


def triage_abstracts(
    client: Anthropic,
    *,
    papers: list[Paper],
    gene: str,
    bundle: IdentifierBundle | None = None,
    concurrency: int = TRIAGE_CONCURRENCY,
) -> list[TriageOutcome]:
    """Fan out per-paper triage across ``concurrency`` threads."""

    if not papers:
        return []
    template = ABSTRACT_TRIAGE_PROMPT_PATH.read_text()
    out: list[TriageOutcome] = []
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [
            pool.submit(
                triage_one_abstract,
                client,
                paper=p,
                gene=gene,
                bundle=bundle,
                prompt_template=template,
            )
            for p in papers
        ]
        for f in as_completed(futures):
            out.append(f.result())
    return out


def _format_synonyms(bundle: IdentifierBundle | None) -> str:
    """Build the human-readable synonyms string for the prompt.

    Returns something like "CD20, B-lymphocyte antigen CD20, Bp35, Leu-16"
    when the bundle carries aliases + previous_symbols + approved_name,
    or "(no known synonyms)" if the bundle is absent or empty.
    """

    if bundle is None:
        return "(no known synonyms)"
    parts: list[str] = []
    seen: set[str] = {bundle.hgnc_symbol.upper()}
    if bundle.approved_name:
        parts.append(bundle.approved_name)
        seen.add(bundle.approved_name.upper())
    for s in (*bundle.aliases, *bundle.previous_symbols):
        if not s:
            continue
        key = s.upper()
        if key in seen:
            continue
        seen.add(key)
        parts.append(s)
    if not parts:
        return "(no known synonyms)"
    return ", ".join(parts)


def paper_source_id(paper: Paper) -> str:
    """Canonical pool/source key for a paper: ``PMC:<id>`` > ``PMID:<id>``.

    This is the key both the clip pool's ``source_id`` and the triage
    outcome's ``paper_id`` agree on, so the runner can join triage
    outcomes back to discovered papers and to the body pool.
    """
    if paper.pmc_id:
        return f"PMC:{paper.pmc_id}"
    if paper.pmid:
        return f"PMID:{paper.pmid}"
    return "UNKNOWN"


# Internal alias retained for the existing call sites in this module.
_paper_source_id = paper_source_id


# ---------------------------------------------------------------------------
# Acting on triage outcomes — drop / keep-abstract / fetch
# ---------------------------------------------------------------------------


@dataclass
class TriageAction:
    """Result of applying one triage decision to the pool.

    Carries audit detail for the case where ``worth_fetching`` couldn't
    actually retrieve a body and fell back to ``keep_abstract``.
    """

    paper_id: str
    decision: str  # discard | keep_abstract | worth_fetching | error
    drafts_added: int = 0
    fetched_body: bool = False
    fetch_error: str | None = None
    fell_back_to_abstract: bool = False
    elapsed_s: float = 0.0


_ABSTRACT_QUOTE_CAP = 600  # matches EvidenceClaimDraft.quote max_length


def _chunk_abstract(text: str, cap: int) -> list[str]:
    """Greedy sentence-pack ``text`` into chunks of at most ``cap`` chars.

    Packs whole sentences until the next would overflow ``cap``, then
    starts a new chunk. A single sentence longer than ``cap`` (rare in
    abstracts) is hard-split on a word boundary. Preserves local context
    within each chunk so anaphora resolves — "such cells" stays adjacent
    to the sentence it refers to, unlike a sentence-level split.
    """

    sentences = _split_sentences(text.strip())
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        if len(sentence) > cap:
            # Flush what we have, then hard-split the long sentence.
            if current:
                chunks.append(current)
                current = ""
            start = 0
            while start < len(sentence):
                window = sentence[start : start + cap]
                if start + cap < len(sentence):
                    cut = window.rfind(" ")
                    if cut > cap * 2 // 3:
                        window = window[:cut]
                chunks.append(window.strip())
                start += len(window)
            continue
        candidate = f"{current} {sentence}".strip() if current else sentence
        if len(candidate) > cap:
            if current:
                chunks.append(current)
            current = sentence
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def _abstract_clips(paper: Paper) -> list[EvidenceClaimDraft]:
    """Build preview clip(s) from a paper's abstract for keep_abstract.

    Greedy sentence-packs the abstract into <=600-char chunks (the
    ``EvidenceClaimDraft.quote`` cap), one draft per chunk. Most abstracts
    yield 2-3 chunks. Earlier chunks score higher so the trim/select
    layers see the lead (where the load-bearing finding usually sits)
    first. All chunks tagged ``hallmark_phrase='abstract_preview'`` so
    downstream can distinguish abstract-derived from body-derived clips.
    """
    if not paper.abstract or not paper.abstract.strip():
        return []
    source_id = _paper_source_id(paper)
    if source_id == "UNKNOWN":
        return []
    bare = source_id.split(":", 1)[-1]
    chunks = _chunk_abstract(paper.abstract, _ABSTRACT_QUOTE_CAP)
    drafts: list[EvidenceClaimDraft] = []
    n = len(chunks)
    for i, chunk in enumerate(chunks):
        if not chunk:
            continue
        # Score 2.0 → 1.0 across chunks so the lead ranks above the tail
        # but all abstract previews sit below typical body clips.
        score = 1.0 + (n - i) / n if n else 1.0
        drafts.append(
            EvidenceClaimDraft(
                suggested_evidence_id=f"draft_{bare}_abstract_{i + 1:02d}",
                quote=chunk,
                source_id=source_id,
                section="abstract",
                figure_or_table_id=None,
                context_excerpt=None,
                hallmark_phrase="abstract_preview",
                score=score,
            )
        )
    return drafts


_NCBI_ELINK = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/elink.fcgi"
_UNPAYWALL_API = "https://api.unpaywall.org/v2"


@dataclass
class UnpaywallLocation:
    """One OA location reported by Unpaywall."""

    url: str
    url_for_pdf: str | None
    url_for_landing_page: str | None
    host_type: str | None  # "publisher" or "repository"
    version: str | None  # "publishedVersion" | "acceptedVersion" | "submittedVersion"
    license: str | None
    has_pdf: bool


def _lookup_oa_via_unpaywall(
    doi: str, *, http: CachedHTTP, email: str
) -> list[UnpaywallLocation]:
    """Resolve DOI → OA locations via Unpaywall.

    Returns an empty list if the DOI isn't in Unpaywall or the paper
    has no OA copies. Each ``UnpaywallLocation`` describes one OA host
    (publisher landing page, repository PDF, etc.). The caller decides
    which one to attempt fetching first — typically publisher
    publishedVersion > repository acceptedVersion > submittedVersion.

    Cached for 90 days; Unpaywall data is stable for old DOIs and
    only changes when new OA copies are deposited.
    """

    if not doi:
        return []
    try:
        payload = http.get_json(
            f"{_UNPAYWALL_API}/{doi.lstrip('/')}",
            source="unpaywall",
            ttl_days=90,
            params={"email": email},
        )
    except Exception:  # noqa: BLE001
        return []

    if not payload.get("is_oa"):
        return []

    locations: list[UnpaywallLocation] = []
    for loc in payload.get("oa_locations") or []:
        locations.append(
            UnpaywallLocation(
                url=loc.get("url") or "",
                url_for_pdf=loc.get("url_for_pdf"),
                url_for_landing_page=loc.get("url_for_landing_page"),
                host_type=loc.get("host_type"),
                version=loc.get("version"),
                license=loc.get("license"),
                has_pdf=bool(loc.get("url_for_pdf")),
            )
        )
    return locations


def _lookup_pmcid_for_pmid(pmid: int, *, http: CachedHTTP) -> str | None:
    """Resolve PMID → PMCID via NCBI eLink ``pubmed_pmc`` linkname.

    The gene2pubmed metadata path goes through EuropePMC's bulk search
    with ``SRC:MED``, which surfaces MEDLINE records and doesn't always
    carry the PMCID even when the paper is also in PMC. NCBI's eLink
    is the canonical authoritative PMID↔PMCID cross-reference.

    Returns ``"PMC{N}"`` if the PMID is linked to a PMC record, else
    ``None``. Cached aggressively — the link is stable once published.
    """

    params: dict[str, Any] = {
        "dbfrom": "pubmed",
        "db": "pmc",
        "id": str(pmid),
        "linkname": "pubmed_pmc",
        "retmode": "json",
    }
    api_key = os.environ.get("NCBI_API_KEY")
    if api_key:
        params["api_key"] = api_key
    try:
        payload = http.get_json(
            _NCBI_ELINK,
            source="ncbi",
            ttl_days=90,
            params=params,
        )
    except Exception:  # noqa: BLE001
        return None

    linksets = payload.get("linksets") or []
    for ls in linksets:
        for ldb in ls.get("linksetdbs") or []:
            if ldb.get("dbto") != "pmc":
                continue
            links = ldb.get("links") or []
            if links:
                return f"PMC{links[0]}"
    return None


def _fetch_body_drafts(
    paper: Paper,
    *,
    http: CachedHTTP,
    retraction_index: RetractionIndex,
) -> list[EvidenceClaimDraft]:
    """Pull the full body for ``paper`` and convert to drafts.

    Resolution chain:

    1. If ``paper.pmc_id`` is set, fetch directly.
    2. Otherwise, look up PMID → PMCID via NCBI eLink — many older
       papers are in PMC but the gene2pubmed metadata pipeline didn't
       carry the link.
    3. If no PMCID resolves, raise (caller falls back to keep_abstract).

    Uses the same no-filter extractor as ``gene_literature(mode=fetch_fulltext)``
    so body clips from triage-driven fetches are indistinguishable from
    body clips from selector-driven fetches downstream.
    """

    pmcid = paper.pmc_id
    if not pmcid and paper.pmid:
        pmcid = _lookup_pmcid_for_pmid(paper.pmid, http=http)
    if not pmcid:
        raise ValueError(
            f"no PMCID for PMID:{paper.pmid} "
            f"(NCBI eLink reports paper not in PMC)"
        )

    body_paper = fetch_fulltext(
        http=http,
        pmcid=pmcid,
        retraction_index=retraction_index,
    )
    if not body_paper.sections:
        raise RuntimeError(
            f"PMC:{pmcid} body not available (NCBI + EuropePMC both empty)"
        )
    source_id = f"PMC:{pmcid}"
    return extract_paper_drafts(
        source_id=source_id,
        abstract=body_paper.abstract,
        sections=body_paper.sections,
    )


def apply_triage_outcomes(
    outcomes: list[TriageOutcome],
    papers_by_id: dict[str, Paper],
    *,
    pool: dict[str, EvidenceClaimDraft],
    by_source: dict[str, list[EvidenceClaimDraft]],
    http: CachedHTTP,
    retraction_index: RetractionIndex,
    add_to_pool_fn: Any,
    fetch_concurrency: int = 5,
) -> list[TriageAction]:
    """Apply all triage outcomes.

    Discards and keep_abstract actions run on the main thread (no I/O).
    worth_fetching actions are dispatched in parallel up to
    ``fetch_concurrency`` since each is an HTTP call. Results are
    applied to the pool on the main thread to avoid concurrent mutation.
    """

    actions: list[TriageAction] = []

    # Phase 1: parallel fetch for worth_fetching outcomes.
    to_fetch: list[tuple[TriageOutcome, Paper]] = []
    for o in outcomes:
        if o.response is None or o.response.decision != "worth_fetching":
            continue
        paper = papers_by_id.get(o.paper_id)
        if paper is None:
            continue
        to_fetch.append((o, paper))

    fetched: dict[str, list[EvidenceClaimDraft] | Exception] = {}
    if to_fetch:
        with ThreadPoolExecutor(max_workers=fetch_concurrency) as ex:
            futures = {
                ex.submit(
                    _fetch_body_drafts,
                    p,
                    http=http,
                    retraction_index=retraction_index,
                ): o.paper_id
                for o, p in to_fetch
            }
            for f in as_completed(futures):
                pid = futures[f]
                try:
                    fetched[pid] = f.result()
                except Exception as exc:  # noqa: BLE001
                    fetched[pid] = exc

    # Phase 2: apply all actions on main thread.
    for o in outcomes:
        paper = papers_by_id.get(o.paper_id)
        if paper is None:
            actions.append(
                TriageAction(
                    paper_id=o.paper_id,
                    decision="error",
                    fetch_error="paper not in inventory",
                )
            )
            continue
        if o.response is None:
            actions.append(
                TriageAction(
                    paper_id=o.paper_id,
                    decision="error",
                    fetch_error=o.error,
                )
            )
            continue

        decision = o.response.decision
        if decision == "discard":
            actions.append(TriageAction(paper_id=o.paper_id, decision="discard"))
        elif decision == "keep_abstract":
            clips = _abstract_clips(paper)
            for clip in clips:
                add_to_pool_fn(clip, pool, by_source)
            actions.append(
                TriageAction(
                    paper_id=o.paper_id,
                    decision="keep_abstract",
                    drafts_added=len(clips),
                    fetch_error=None if clips else "no abstract text to clip",
                )
            )
        elif decision == "worth_fetching":
            result = fetched.get(o.paper_id)
            if isinstance(result, list):
                for d in result:
                    add_to_pool_fn(d, pool, by_source)
                actions.append(
                    TriageAction(
                        paper_id=o.paper_id,
                        decision="worth_fetching",
                        drafts_added=len(result),
                        fetched_body=True,
                    )
                )
            else:
                # Fetch failed — fall back to abstract preview clip(s).
                clips = _abstract_clips(paper)
                for clip in clips:
                    add_to_pool_fn(clip, pool, by_source)
                actions.append(
                    TriageAction(
                        paper_id=o.paper_id,
                        decision="worth_fetching",
                        drafts_added=len(clips),
                        fetched_body=False,
                        fetch_error=(
                            f"{type(result).__name__}: {result}"
                            if isinstance(result, Exception)
                            else "unknown fetch result"
                        ),
                        fell_back_to_abstract=len(clips) > 0,
                    )
                )

    return actions


__all__ = [
    "TriageOutcome",
    "TriageAction",
    "triage_one_abstract",
    "triage_abstracts",
    "apply_triage_outcomes",
    "paper_source_id",
    "ABSTRACT_TRIAGE_PROMPT_PATH",
]
