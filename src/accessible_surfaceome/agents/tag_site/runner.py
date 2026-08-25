"""End-to-end runner for the literature tag-site agent.

Multi-stage clip pipeline, shared with the internalization track
(``agents/_support/literature_clips``):
  1. discovery — repo lit-search (``literature_discovery``: EuropePMC alias +
     methods vocabulary, default + citation-sorted passes, PubTator; retraction
     filtered; INCLUDING bioRxiv/medRxiv preprints) PLUS a shared ``web_search``
     discovery pass, all hydrated to real Papers keyed by ``paper_source_id``;
  2. abstract triage (shared ``triage_abstracts``) — mark each paper worth
     fetching or not;
  3. body pool + real source store (shared ``build_pool`` / ``build_source_store``)
     — fetch full text for the worth-fetching papers and cut it into clips;
  4. clip select (shared ``select_clips`` with the tag-site select prompt) — the
     model picks tag-insertion clips by ``clip_id`` and never authors a quote;
  5. span-verified promotion (shared ``promote``) — each pick becomes an
     ``Evidence`` with a real char offset into the fetched body;
  6. synthesis — Sonnet with the tag-site prompt + the span-verified EVIDENCE
     LEDGER (via ``call_builder``) proposes ranked sites, each grounded in one
     ledger clip;
  7. post-process — re-check each site's supporting_quote against the ledger
     (entailment backstop), drop non-validated sites, rank by validation strength
     then source tier then entailment.

Every quote a shipped site cites is thus span-verified BY CONSTRUCTION (it came
from the ledger), the same guarantee the internalization track gives — the two
agents now share ONE clip pipeline. Synthesis mirrors
``agents/surfaceome_v2/builders/_common.call_builder`` — same repair loop and
usage sink the other agents use.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from anthropic import Anthropic

from accessible_surfaceome.agents._support.client import get_client
from accessible_surfaceome.agents._support.literature_clips import (
    build_pool,
    build_source_store,
    promote,
    select_clips,
)
from accessible_surfaceome.agents._support.web_literature import web_discover_papers
from accessible_surfaceome.agents.plan_trim_select.abstract_triage import triage_abstracts
from accessible_surfaceome.agents.surfaceome_v2.builders._common import call_builder
from accessible_surfaceome.tools._shared.http import CachedHTTP, open_default_client
from accessible_surfaceome.tools._shared.models import Evidence, Paper, paper_source_id
from accessible_surfaceome.tools._shared.retraction_watch import empty as _empty_retraction
from accessible_surfaceome.tools._shared.retraction_watch import from_http as _retraction_from_http

from .literature_discovery import SOURCE_TIERS, discover_tag_site_papers, quote_supported
from .prompt import SYSTEM_PROMPT, build_user_prompt, keep_validated_sites
from .schema import VALIDATION_LEVELS, VALIDATION_RANK, TagSiteProposal, TagSiteResult

# web_search discovery is delegated to the shared ``web_literature`` module
# (agents/_support), so the tag-site and internalization tracks share ONE
# implementation. This is the tag-site topic phrase passed to it.
_TAG_SITE_INTENT = (
    "epitope / peptide tag insertion for surface display — ecto-tagging and "
    "knock-in constructs that place a tag (HA, FLAG, Myc, ALFA, HiBiT, SpyTag, "
    "bungarotoxin-binding site, snorkel) in an extracellular loop or terminus, "
    "and their surface-display / functional validation"
)
_TOPO_CHAR = {"extracellular": "O", "intracellular": "I", "membrane": "M", "signal": "S"}

# Tag-site clip-select stage: the shared selector is fed this prompt + menu
# instruction, and its picks are promoted under the ``tag_evi_`` evidence-id
# namespace (internalization uses ``int_evi_``).
_TAG_SELECT_PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "literature_select_system.md"
_TAG_SELECT_MENU_INSTRUCTION = (
    "pick the tag-insertion clips by clip_id (a tag / FP / insertion engineered "
    "INTO the full-length, surface-displayed protein at a named site); do NOT "
    "paraphrase — the quote is auto-filled from the clip"
)
_TAG_EVIDENCE_ID_PREFIX = "tag_evi_"


def load_tag_select_prompt() -> str:
    """The tag-site clip-select system prompt (scopes IN a tag engineered into the
    full-length surface protein; scopes OUT soluble-ectodomain / Fc-decoy /
    epitope-mapping / vendor-plasmid / intracellular-tag clips)."""
    return _TAG_SELECT_PROMPT_PATH.read_text()


def format_evidence_ledger(evidence: list[Evidence]) -> str:
    """Render span-verified ``Evidence`` as the synthesis prompt's ledger block.

    Each line is ``[<label>] <claim>`` + a verbatim ``QUOTE`` already located in
    the cited source upstream, so the synthesis stage can only ground a site in a
    real clip. ``<label>`` surfaces the numeric PMID (``PMID 123``) when the
    source_id is a ``PMID:`` key, else the raw source_id (``PMC:...`` / ``DOI:...``)
    so a preprint clip is cited by DOI/PMC with ``supporting_pmid``=null."""
    if not evidence:
        return (
            "EVIDENCE LEDGER: empty — no span-verified tag-insertion clips were "
            "found for this protein. Return an EMPTY sites list with a rationale."
        )
    lines = [
        "EVIDENCE LEDGER (span-verified clips — each QUOTE is VERBATIM and already "
        "located in the cited source. Ground EVERY site in ONE ledger line: copy "
        "its QUOTE into supporting_quote exactly. For a [PMID n] line set "
        "supporting_pmid=n; for a [PMC ...]/[DOI ...] line set supporting_pmid=null "
        "and cite it in the rationale. Do NOT invent sites or quotes beyond this "
        "ledger):"
    ]
    for e in evidence:
        span = e.spans[0] if e.spans else None
        source_id = span.source.source_id if span and span.source else "?"
        pmid = source_id.split("PMID:", 1)[1] if source_id.startswith("PMID:") else None
        label = f"PMID {pmid}" if pmid else source_id
        quote = span.quote if span else ""
        lines.append(f"- [{label}] {e.claim}\n  QUOTE: {quote}")
    return "\n".join(lines)


def _sort_key(s: TagSiteProposal) -> tuple[int, int, int, int]:
    """Validation strength first (surface+function best), then source tier
    (paper > patent > vendor), then source-verified citations ahead of unverified,
    then the model's own rank."""
    return (
        VALIDATION_RANK.get(s.validation_level, len(VALIDATION_LEVELS)),
        SOURCE_TIERS.index(s.source_tier) if s.source_tier in SOURCE_TIERS else len(SOURCE_TIERS),
        0 if s.entailment_verified else 1,
        s.rank,
    )


def rank_sites(result: TagSiteResult) -> TagSiteResult:
    """Drop non-validated sites, sort by validation+tier+entailment, renumber ``rank``."""
    keep_validated_sites(result)
    result.sites.sort(key=_sort_key)
    for i, s in enumerate(result.sites, start=1):
        s.rank = i
    return result


def verify_entailment(result: TagSiteResult, *, evidence: list[Evidence]) -> TagSiteResult:
    """Entailment backstop: set ``entailment_verified`` on each site True iff its
    supporting_quote is found in the span-verified evidence ledger. The ledger is
    the ONLY citation source the synthesis stage saw and every clip in it is
    already span-located in a real body, so a site whose quote is drawn from the
    ledger passes and a hallucinated quote (nowhere in the ledger) is flagged and
    down-ranked."""
    ledger = "\n".join(sp.quote for e in evidence for sp in (e.spans or []) if sp.quote)
    for s in result.sites:
        s.entailment_verified = quote_supported(s.supporting_quote, ledger)
    return result


def run_tag_site_agent(
    *,
    gene_symbol: str,
    protein_name: str,
    uniprot_accession: str,
    aliases: list[str],
    sequence: str,
    topology: str,
    client: Anthropic | None = None,
    http: CachedHTTP | None = None,
    mode: str = "production",
    usage_sink: list[Any] | None = None,
) -> TagSiteResult:
    """Discover papers (+ preprints, retraction-filtered), triage, pool + span-verify
    tag-insertion clips (shared clip pipeline), then synthesize a validated, ranked
    :class:`TagSiteResult` grounded in that evidence ledger. ``aliases`` should
    include the protein name(s)."""
    client = client or get_client()
    http = http or open_default_client()
    usage_sink = usage_sink if usage_sink is not None else []

    try:
        ri = _retraction_from_http(http)  # best-effort Retraction Watch index
    except Exception:  # noqa: BLE001 - never block on the retraction fetch
        ri = _empty_retraction()

    def _empty() -> TagSiteResult:
        return TagSiteResult(
            gene_symbol=gene_symbol,
            uniprot_accession=uniprot_accession,
            sequence_length=len(sequence or ""),
        )

    # 1. Discovery: repo lit-search + shared web_search complement, hydrated to real
    # Papers keyed by paper_source_id (deterministic pool wins on collision).
    papers = discover_tag_site_papers(
        http=http, gene_symbol=gene_symbol, aliases=aliases, retraction_index=ri
    )
    for wp in web_discover_papers(
        client,
        intent=_TAG_SITE_INTENT,
        gene_names=[protein_name, *aliases],
        http=http,
        retraction_index=ri,
        usage_sink=usage_sink,
    ):
        papers.setdefault(paper_source_id(wp), wp)
    papers_by_id: dict[str, Paper] = {paper_source_id(p): p for p in papers.values()}
    if not papers_by_id:
        return _empty()

    # 2. Abstract triage -> 3. body pool + real source store (shared).
    outcomes = triage_abstracts(client, papers=list(papers_by_id.values()), gene=gene_symbol)
    pool, actions = build_pool(outcomes, papers_by_id, http=http, retraction_index=ri)
    fetched_by_id = {a.paper_id: bool(getattr(a, "fetched_body", False)) for a in actions}
    papers_by_source_id = {
        pid: (paper, fetched_by_id.get(pid, False)) for pid, paper in papers_by_id.items()
    }
    store = build_source_store(
        pool, papers_by_source_id=papers_by_source_id, http=http, retraction_index=ri
    )

    # 4. Clip select (tag-site prompt) -> 5. span-verified promotion. Keep only
    # clips whose quote has a real char offset into the fetched body.
    selection = select_clips(
        client,
        pool=pool,
        gene=gene_symbol,
        synonyms=aliases,
        system_prompt=load_tag_select_prompt(),
        menu_instruction=_TAG_SELECT_MENU_INSTRUCTION,
        usage_sink=usage_sink,
    )
    evidence = [
        e
        for e in promote(
            selection, pool=pool, store=store, evidence_id_prefix=_TAG_EVIDENCE_ID_PREFIX
        )
        if e.entailment_verified
    ]
    if not evidence:
        # No span-verified tag-insertion clip -> the correct answer is ZERO sites
        # (never a structural-inference guess); skip the synthesis call entirely.
        return _empty()

    # 6. Synthesis: the geometry/validation/snorkel rules read the span-verified ledger.
    user_prompt = build_user_prompt(
        gene_symbol, protein_name, mode=mode, sequence=sequence, topology=topology
    )
    user_prompt = f"{user_prompt}\n\n{format_evidence_ledger(evidence)}"

    result = call_builder(
        client,
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        schema=TagSiteResult,
        usage_sink=usage_sink,
        label=f"tag_site:{gene_symbol}",
        max_tokens=32_000,  # 16k default truncated multi-site outputs (e.g. SLC6A4)
    )
    if result is None:
        return _empty()
    assert isinstance(result, TagSiteResult)  # expect_array=False -> single instance

    # 7. Post-process: entailment backstop against the ledger, drop non-validated, rank.
    verify_entailment(result, evidence=evidence)
    return rank_sites(result)


def to_viewer_sites(result: TagSiteResult, *, uniprot_acc: str) -> list[dict[str, Any]]:
    """Convert to the viewer's ``literature_retrieved`` TaggedSite shape
    (viewer/lib/tag-sites-types.ts). Agent-only fields (validation_level,
    position_evidence, source_tier, entailment) fold into ``rationale``/``sources``
    so the viewer contract is unchanged."""
    out: list[dict[str, Any]] = []
    for s in result.sites:
        sources: list[dict[str, Any]] = []
        if s.supporting_pmid:
            # ``claim`` carries the verbatim supporting_quote (entailment-checked)
            # so the viewer's expandable drawer can show the exact sentence.
            sources.append(
                {
                    "pmid": s.supporting_pmid,
                    "citation": f"PMID {s.supporting_pmid}",
                    "claim": s.supporting_quote or None,
                }
            )
        elif s.supporting_quote:
            # Preprint / DOI-only citation with a quote but no PMID.
            sources.append({"citation": "preprint", "claim": s.supporting_quote})
        out.append(
            {
                "site_id": f"{result.gene_symbol}-{s.site_type}-{s.insert_after_residue}-lit",
                "gene_symbol": result.gene_symbol,
                "uniprot_acc": uniprot_acc,
                "provenance": "literature_retrieved",
                "det_path": None,
                "site_kind": s.site_type,
                "insert_after_residue": s.insert_after_residue,
                "residue_before": s.residue_before,
                "residue_after": s.residue_after,
                "residue_label": s.residue_label,
                "topology_state": _TOPO_CHAR.get(s.topology_state, "O"),
                "extracellular": s.topology_state == "extracellular",
                "compartment": s.topology_state,
                "tag_type": s.tag_type,
                "tag_length_aa": None,
                "linker": None,
                "evidence_type": s.evidence_type,
                "functional_impact_measured": s.functional_or_expression_impact_measured,
                "confidence": s.confidence,
                "rationale": (
                    f"{s.rationale} [validation: {s.validation_level}; "
                    f"position: {s.position_evidence}; source: {s.source_tier}; "
                    f"entailment_verified: {s.entailment_verified}]"
                ),
                "sources": sources,
                "plddt": None,
                "conservation_rank": None,
                "median_conservation": None,
            }
        )
    return out
