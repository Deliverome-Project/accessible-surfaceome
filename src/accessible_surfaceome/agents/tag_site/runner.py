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

import logging
from datetime import UTC, datetime
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from typing import Any, Literal

from anthropic import Anthropic

from accessible_surfaceome.agents._support.client import get_client
from accessible_surfaceome.agents._support.literature_clips import (
    build_pool,
    build_source_store,
    promote,
    select_clips,
)
from accessible_surfaceome.agents._support.web_literature import web_discover_papers
from accessible_surfaceome.agents.internalization.intermediates import (
    force_worth_fetching_outcomes,
    hydrate_paper_ids,
)
from accessible_surfaceome.agents.surfaceome_v2.builders._common import call_builder
from accessible_surfaceome.tools._shared.http import CachedHTTP, open_default_client
from accessible_surfaceome.tools._shared.models import Evidence, Paper, paper_source_id
from accessible_surfaceome.tools._shared.retraction_watch import empty as _empty_retraction
from accessible_surfaceome.tools._shared.retraction_watch import from_http as _retraction_from_http

from .enrichment import (
    EnrichmentScope,
    count_new,
    covered_clip_ids,
    new_clip_ids,
)
from .frames import Frame, resolve
from .geometry import apply_geometry_pass
from .literature_discovery import (
    DISCOVERY_CACHE_DIR,
    SOURCE_TIERS,
    best_supporting_quote,
    boost_residue_clips,
    discover_tag_site_papers,
    is_cytoplasmic_terminal_fusion,
    is_internal_loop_mention,
    ledger_clip_within,
    load_discovery_cache,
    load_web_search_cache,
    quote_is_probative,
    quote_supported,
    residue_mentions,
    save_discovery_cache,
    save_web_search_cache,
)
from .literature_triage import (
    HAIKU_MODEL as DEFAULT_TAG_SITE_TRIAGE_MODEL,
)
from .literature_triage import (
    triage_tag_site_abstracts as triage_abstracts,
)
from .member_frames import run_at
from .normalize import signal_peptide_end
from .position_verify import verify_position_blind
from .prior_ledger import PriorClip, seed_pool
from .prompt import (
    SYSTEM_PROMPT,
    TAG_SITE_PROMPT_VERSION,
    build_user_prompt,
    keep_validated_sites,
    prompt_sha,
)
from .reference_followup import find_construct_followup_paper_ids
from .schema import (
    VALIDATION_LEVELS,
    VALIDATION_RANK,
    RejectedSite,
    TagSiteProposal,
    TagSiteResult,
)
from .triage_cache import (
    input_sha as triage_input_sha,
)
from .triage_cache import (
    load as load_triage_cache,
)
from .triage_cache import (
    save as save_triage_cache,
)
from .triage_cache import (
    split as split_triage,
)
from .triage_cache import (
    triage_prompt_sha,
)

DEFAULT_TAG_SITE_MODEL = "claude-sonnet-5-5"
DEFAULT_TAG_SITE_WEB_SCOUT_MODEL = "claude-haiku-5-5"
SONNET_MODEL = DEFAULT_TAG_SITE_MODEL  # back-compat alias
WebSearchMode = Literal["always", "adaptive", "off"]

_WEB_SEARCH_MAX_USES = 6
_MAX_WORTH_FETCHING = 25
_MAX_POOL_PER_PAPER = 8
_MAX_SYNTHESIS_EVIDENCE = 50
_MAX_SYNTHESIS_PER_PAPER = 5
_ADAPTIVE_MIN_FETCHED = 2
_ADAPTIVE_MIN_BOOSTED_PAPERS = 2

# web_search discovery is delegated to the shared ``web_literature`` module
# (agents/_support), so the tag-site and internalization tracks share ONE
# implementation. These are the tag-site topic phrases passed to it.
_TAG_SITE_INTENT = (
    "epitope / peptide tag insertion for surface display — ecto-tagging and "
    "knock-in constructs that place a tag (HA, FLAG, Myc, ALFA, HiBiT, SpyTag, "
    "BLAP, bungarotoxin-binding site / BBS, snorkel) in an extracellular loop "
    "or terminus, and their surface-display / functional validation"
)
_TAG_SITE_INTERNAL_INTENT = (
    "extracellular loop epitope / peptide tag insertion into this multipass "
    "membrane protein (ECL1-ECL4, EC1-EC2, EL1-EL4, S1-S2, S3-S4, loop C, "
    "HA, FLAG, Myc, ALFA, HiBiT, BLAP, bungarotoxin-binding site / BBS, "
    "pHluorin, SpyTag, DogTag, transposon or domain-insertion screen, or "
    "snorkel tag) — EXCLUDING N-terminal or C-terminal cytoplasmic fusions"
)
#: Compartment -> DeepTMHMM char for the viewer shape. "unknown" maps to None,
#: never to "O": an underived compartment that renders as extracellular is the
#: failure this table used to have via a `.get(..., "O")` default.
_TOPO_CHAR: dict[str, str | None] = {
    "extracellular": "O", "intracellular": "I",
    "membrane": "M", "signal": "S", "unknown": None,
}

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

# Server-side Python REPL for the synthesis stage. Declared in ``tools`` and
# resolved inside the same ``create`` call -- no client-side tool loop -- which is
# the shape ``call_builder`` already supports for ``web_search``.
#
# The model is given the canonical sequence but cannot compute over it reliably:
# from a bare topology string it read a 26-residue signal-peptide run as 18 and
# shifted every boundary it derived. Deterministic code now covers the checks we
# knew to write; the REPL is for the one we cannot pre-write -- a paper stating a
# position in a DIFFERENT numbering frame (mature protein, an isoform, an
# ortholog), where recovering the offset is a search over the sequence.
#
# ``call_builder`` degrades to a plain call if code execution is not enabled on
# the account, the same way it does for web_search.
CODE_EXECUTION_TOOL: list[dict[str, Any]] = [
    {"type": "code_execution_20260120", "name": "code_execution"}
]

log = logging.getLogger(__name__)


def tag_site_relevance(
    sequence: str, *, internal_only: bool = False
) -> Callable[[str], float]:
    """A per-sentence relevance term for draft extraction, scoring what a
    tag-site clip has to contain to be worth anything.

    Signals (additive):
    * describes an insertion/tag (:func:`quote_is_probative`): +3.0
    * names a residue confirmed by ``sequence`` (:func:`residue_mentions`): +3.0
    * when ``internal_only=True``:
        - names an extracellular loop or internal insertion: +2.0
        - describes an explicit N-/C-terminal fusion without mentioning a loop:
          -3.5 (pushes cytoplasmic terminal GFP/FLAG noise below real loop hits)
    """
    def score(text: str) -> float:
        value = 0.0
        has_loop = is_internal_loop_mention(text)
        if quote_is_probative(text):
            value += 3.0
        if sequence and residue_mentions(text, sequence=sequence):
            value += 3.0
        if internal_only:
            if has_loop:
                value += 2.0
            elif is_cytoplasmic_terminal_fusion(text):
                value -= 3.5
        return value

    return score


def _cap_worth_fetching(
    outcomes: list[Any],
    papers_by_id: Mapping[str, Any],
    *,
    sequence: str,
    internal_only: bool = False,
    max_fetch: int = _MAX_WORTH_FETCHING,
    pinned_ids: set[str] | None = None,
    citation_counts: Mapping[str, int] | None = None,
) -> list[Any]:
    """Keep at most ``max_fetch`` highest-value ``worth_fetching`` outcomes,
    downgrading excess ones to ``keep_abstract`` so their abstracts stay in the
    pool without stalling on 80+ redundant full-text downloads."""
    pinned = pinned_ids or set()
    cites = citation_counts or {}
    wf_indices = [
        i
        for i, o in enumerate(outcomes)
        if getattr(getattr(o, "response", None), "decision", None) == "worth_fetching"
    ]
    if len(wf_indices) <= max_fetch:
        return outcomes
    scorer = tag_site_relevance(sequence, internal_only=internal_only)

    def _priority(idx: int) -> tuple[int, float, int, int]:
        o = outcomes[idx]
        p = papers_by_id.get(o.paper_id)
        is_pinned = 1 if o.paper_id in pinned else 0
        title = (getattr(p, "title", "") or "") if p is not None else ""
        abstract = (getattr(p, "abstract", "") or "") if p is not None else ""
        cited = int(cites.get(o.paper_id, 0) or 0)
        has_pmc = 1 if (p is not None and getattr(p, "pmc_id", None)) else 0
        return (is_pinned, scorer(f"{title}. {abstract}"), cited, has_pmc)

    ranked = sorted(wf_indices, key=_priority, reverse=True)
    keep_set = set(ranked[: max(max_fetch, len(pinned))])
    out = list(outcomes)
    downgraded = 0
    for idx in wf_indices:
        if idx not in keep_set:
            o = out[idx]
            resp = o.response
            out[idx] = type(o)(
                paper_id=o.paper_id,
                response=resp.model_copy(update={"decision": "keep_abstract"}),
                usage=o.usage,
                elapsed_s=o.elapsed_s,
                error=o.error,
            )
            downgraded += 1
    if downgraded:
        log.info(
            "  capped worth_fetching at %d (downgraded %d excess to keep_abstract)",
            max_fetch,
            downgraded,
        )
    return out


def _cap_pool_per_paper(
    pool: dict[str, Any],
    *,
    max_per_paper: int = _MAX_POOL_PER_PAPER,
    keep_ids: set[str] | None = None,
) -> dict[str, Any]:
    """Limit each paper to at most ``max_per_paper`` clips in the selector menu
    so one verbose GFP/localization paper cannot swallow 30+ menu slots.
    Always preserves ``keep_ids`` (carried clips and residue-boosted clips)."""
    if not pool or max_per_paper <= 0:
        return pool
    must_keep = keep_ids or set()
    ordered = sorted(
        pool.items(),
        key=lambda kv: (1 if kv[0] in must_keep else 0, getattr(kv[1], "score", 0.0) or 0.0),
        reverse=True,
    )
    out: dict[str, Any] = {}
    counts: dict[str, int] = {}
    for cid, draft in ordered:
        sid = getattr(draft, "source_id", None) or cid
        if cid in must_keep or counts.get(sid, 0) < max_per_paper:
            out[cid] = draft
            counts[sid] = counts.get(sid, 0) + 1
    return out


def _select_evidence_for_synthesis(
    evidence: list[Any],
    *,
    sequence: str,
    internal_only: bool = False,
    max_clips: int = _MAX_SYNTHESIS_EVIDENCE,
    max_per_paper: int = _MAX_SYNTHESIS_PER_PAPER,
) -> list[Any]:
    """Bound and diversify the span-verified evidence ledger before synthesis
    so one multi-clip paper cannot crowd out independent papers or trigger
    output truncation."""
    if len(evidence) <= max_clips:
        return evidence
    scorer = tag_site_relevance(sequence, internal_only=internal_only)
    conf_rank = {"strong": 2, "moderate": 1, "weak": 0}

    def _rank_key(e: Any) -> tuple[float, int, int]:
        span = e.spans[0] if getattr(e, "spans", None) else None
        quote = (span.quote if span else "") or ""
        claim = getattr(e, "claim", "") or ""
        is_primary = 1 if getattr(e, "evidence_tier", "") == "primary" else 0
        c_rank = conf_rank.get(str(getattr(e, "confidence", "")), 0)
        return (scorer(f"{quote} {claim}"), is_primary, c_rank)

    ranked = sorted(evidence, key=_rank_key, reverse=True)
    chosen: list[Any] = []
    per_source: dict[str, int] = {}
    overflow: list[Any] = []
    for e in ranked:
        span = e.spans[0] if getattr(e, "spans", None) else None
        sid = span.source.source_id if span and span.source else e.evidence_id
        if per_source.get(sid, 0) < max_per_paper:
            chosen.append(e)
            per_source[sid] = per_source.get(sid, 0) + 1
            if len(chosen) >= max_clips:
                break
        else:
            overflow.append(e)
    if len(chosen) < max_clips and overflow:
        chosen.extend(overflow[: max_clips - len(chosen)])
    log.info(
        "  capped synthesis evidence ledger %d -> %d clips across %d distinct sources",
        len(evidence),
        len(chosen),
        len(per_source),
    )
    return chosen


def _needs_adaptive_web_search(
    *,
    pool: Mapping[str, Any],
    actions: list[Any],
    boosted: Mapping[str, set[int]],
) -> tuple[bool, str]:
    n_fetched = sum(1 for a in actions if bool(getattr(a, "fetched_body", False)))
    boosted_sources = {
        getattr(pool[cid], "source_id", cid) for cid in boosted if cid in pool
    }
    if n_fetched < _ADAPTIVE_MIN_FETCHED:
        return True, f"fetched={n_fetched}<{_ADAPTIVE_MIN_FETCHED}"
    if len(boosted_sources) < _ADAPTIVE_MIN_BOOSTED_PAPERS:
        return (
            True,
            f"boosted_papers={len(boosted_sources)}<{_ADAPTIVE_MIN_BOOSTED_PAPERS}",
        )
    return (
        False,
        f"sufficient (fetched={n_fetched}, boosted_papers={len(boosted_sources)}, clips={len(pool)})",
    )


def load_tag_select_prompt() -> str:
    """The tag-site clip-select system prompt (scopes IN a tag engineered into the
    full-length surface protein; scopes OUT soluble-ectodomain / Fc-decoy /
    epitope-mapping / vendor-plasmid / intracellular-tag clips)."""
    return _TAG_SELECT_PROMPT_PATH.read_text()


def format_evidence_ledger(evidence: Iterable[Any]) -> str:
    """Render span-verified ``Evidence`` as the synthesis prompt's ledger block.

    Each line carries an ``[Ln]`` id. The model cites that id and never retypes
    the quote, which is how the clip-SELECT stage has always worked ("you only
    pick and classify by clip_id, you never retype the quote") and makes a
    fabricated quote structurally impossible rather than something the
    entailment gate has to catch afterwards. It also stops paying output rates
    to echo our own input: the quotes ran ~240 characters each.

    Each line is ``[<label>] <claim>`` + a verbatim ``QUOTE`` already located in
    the cited source upstream, so the synthesis stage can only ground a site in a
    real clip. ``<label>`` surfaces the numeric PMID (``PMID 123``) when the
    source_id is a ``PMID:`` key, else the raw source_id (``PMC:...`` / ``DOI:...``)
    so a preprint clip is cited by DOI/PMC with ``supporting_pmid``=null."""
    evidence = list(evidence)  # an iterator would always test truthy
    if not evidence:
        return (
            "EVIDENCE LEDGER: empty — no span-verified tag-insertion clips were "
            "found for this protein. Return an EMPTY sites list with a rationale."
        )
    lines = [
        "EVIDENCE LEDGER (span-verified clips, each already located VERBATIM in "
        "its source). Ground EVERY site in ONE line and name it by its [Ln] id "
        "in supporting_clip_id. The quote and the citation are filled in from "
        "that id — you never retype them. Do NOT invent sites beyond this ledger):"
    ]
    for i, e in enumerate(evidence, start=1):
        span = e.spans[0] if e.spans else None
        source_id = span.source.source_id if span and span.source else "?"
        pmid = source_id.split("PMID:", 1)[1] if source_id.startswith("PMID:") else None
        label = f"PMID {pmid}" if pmid else source_id
        quote = span.quote if span else ""
        lines.append(f"- [L{i}] [{label}] {e.claim}\n  QUOTE: {quote}")
    return "\n".join(lines)


def _sort_key(s: TagSiteProposal) -> tuple[int, int, int, int, int]:
    """Validation strength first (surface+function best), then source tier
    (paper > patent > vendor), then source-verified citations ahead of unverified,
    then citations that actually describe an insertion ahead of bare ones, then
    the model's own rank."""
    return (
        VALIDATION_RANK.get(s.validation_level, len(VALIDATION_LEVELS)),
        SOURCE_TIERS.index(s.source_tier) if s.source_tier in SOURCE_TIERS else len(SOURCE_TIERS),
        0 if s.entailment_verified else 1,
        0 if s.quote_probative else 1,
        s.rank,
    )


def rank_sites(result: TagSiteResult) -> TagSiteResult:
    """Drop non-validated sites, sort by validation+tier+entailment, renumber ``rank``."""
    keep_validated_sites(result)
    result.sites.sort(key=_sort_key)
    for i, s in enumerate(result.sites, start=1):
        s.rank = i
    return result


def upgrade_quotes(result: TagSiteResult, *, evidence: list[Evidence]) -> TagSiteResult:
    """Set ``quote_probative`` on every site, swapping in a better LEDGER quote
    when the model cited a sentence that describes no insertion.

    The site is never dropped for a weak quote: the observed failure had the
    right residue and the right paper and only quoted the abstract's opening
    line. Any replacement comes from the same span-verified ledger, so it is
    entailed by construction."""
    for s in result.sites:
        if quote_is_probative(s.supporting_quote):
            s.quote_probative = True
            continue
        better = best_supporting_quote(residue=s.insert_after_residue, evidence=evidence)
        if better:
            s.supporting_quote = better
            s.quote_probative = True
    return result


def enforce_position_claims(
    result: TagSiteResult,
    *,
    sequence: str,
    client: Any | None = None,
    frames: list[Frame] | None = None,
    reference_label: str = "member",
    verifier_model: str = DEFAULT_TAG_SITE_TRIAGE_MODEL,
    usage_sink: list[Any] | None = None,
) -> TagSiteResult:
    """Downgrade ``position_evidence`` to ``inferred`` on any site whose quote
    does not NAME its position.

    The schema already separates "a tag was published AT this residue" from "the
    loop has precedent and I chose this residue", but nothing enforced it, and
    every site produced on the held-out control genes claimed ``validated`` from
    a quote that named no position at all -- one cited an internalization-rate
    experiment, another a plasmid-localization sentence. Those positions were
    derived from topology (they are the canonical cleavage sites) and may well
    be right; what they are not is validated by the citation attached to them.

    The site is kept either way. A correct site with a weak citation is still
    worth reporting -- it just must not claim more than its evidence does.

    Both ``n`` and its neighbours count, because a paper may name the residue
    before or after the junction, and the quote is read with the sequence so a
    cell line or a stray integer cannot launder a position claim.

    ``client`` enables a BLIND second opinion for the long tail the literal
    matcher misses. It is consulted only when the matcher found nothing, it is
    shown the sentence and nothing else, and it can only UPGRADE — a verifier
    that could also downgrade would be a second way to lose a correct site, and
    the deterministic path already decides that."""
    if not sequence:
        return result
    for s in result.sites:
        if s.position_evidence != "validated":
            continue  # 'inferred' and 'topology_derived' already claim no exact citation
        n = s.insert_after_residue
        if n is None:
            # A region-level site claims no junction, so there is no position
            # for a quote to name; it is already labelled 'inferred' by the
            # prompt and must not be re-judged against a residue it never gave.
            continue
        named = residue_mentions(s.supporting_quote, sequence=sequence)
        if named & {n - 1, n, n + 1}:
            continue
        # Nothing in THIS construct's numbering. Before anything else, ask
        # whether the citation is numbering in another proteoform — a library
        # member's ordered form is often an isoform or a designed ORF, and a
        # paper will essentially never use the designed ORF's coordinates, so
        # "the reference frame does not confirm it" is the expected state rather
        # than a problem. This route is deterministic and auditable, so it goes
        # ahead of the model-based verifier below.
        if frames:
            res = resolve(
                s.supporting_quote,
                frames=frames,
                reference_label=reference_label,
                target=n,
            )
            hit = res.validating_hit
            if hit is not None and hit.frame_label != reference_label:
                log.info(
                    "  %s: %s position upheld in the %s frame (frame pos %d)",
                    result.gene_symbol or "?", s.residue_label,
                    hit.frame_label, hit.frame_position,
                )
                s.position_frame = hit.frame_label
                continue
        # Still nothing. Before downgrading, ask the blind verifier
        # — it handles the spellings no pattern list covers, and returns NONE
        # for the numbers that are durations, figures and catalogue ids.
        stated = verify_position_blind(
            s.supporting_quote,
            client=client,
            max_residue=len(sequence),
            model=verifier_model,
            usage_sink=usage_sink,
        )
        if stated is not None and stated in {n - 1, n, n + 1}:
            # Say so. Without this the verifier is invisible: two sites were
            # upgraded in one run and both turned out to be the deterministic
            # span/list patterns, which is only knowable by re-deriving the
            # match by hand. A fallback nobody can see firing cannot be
            # evaluated, and will get credited for work it did not do.
            log.info("  %s: %s position upheld by blind verify (quote states %d)",
                     result.gene_symbol or "?", s.residue_label, stated)
            s.position_repaired = True
            continue
        s.position_evidence = "inferred"
    return result


def enforce_evidence_type_coupling(result: TagSiteResult) -> TagSiteResult:
    """An unvalidated position may not carry an exact-site ``evidence_type``.

    The prompt couples them — `evidence_type` may be "published tag insertion at
    this exact site" ONLY when the position is validated — but nothing enforced
    it. `enforce_position_claims` downgrades `position_evidence` when the quote
    does not name the residue and leaves `evidence_type` untouched, so a record
    could say "I inferred this position" and "a tag was published at this exact
    site" in the same breath. TFRC's C-terminal site shipped exactly that pair,
    which made it read stronger than the sentence behind it.

    The site is KEPT. Only the claim is corrected — a terminal position derived
    from topology is a real finding, it just is not an exact-site citation."""
    for site in result.sites:
        if (
            site.position_evidence != "validated"
            and site.evidence_type == "published tag insertion at this exact site"
        ):
            site.evidence_type = "published tag insertion in the same loop or domain"
    return result


def verify_entailment(result: TagSiteResult, *, evidence: Iterable[Any]) -> TagSiteResult:
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


def recover_overcomplete_quotes(result: TagSiteResult, *, evidence: Iterable[Any]) -> TagSiteResult:
    """Rescue a site whose quote CONTAINS a ledger clip instead of being inside one.

    Clips are truncated at extraction, so a model that reads the source and
    reproduces the whole sentence yields a string no clip contains. That is a
    more faithful citation, and the entailment check was deleting it. The site
    keeps the ledger's own text, never the longer string we did not verify."""
    for site in result.sites:
        if site.entailment_verified:
            continue
        clip = ledger_clip_within(site.supporting_quote, evidence)
        if clip:
            site.supporting_quote = clip
    return result


def fill_quotes_from_ledger(
    result: TagSiteResult, *, evidence: Iterable[Any]
) -> TagSiteResult:
    """Fill ``supporting_quote`` from the ``[Ln]`` id the site cited.

    The quote is OURS, not the model's: it comes back out of the same ledger it
    went in as, so it cannot be mistyped, truncated or embellished. Every quote
    failure today was a transcription artifact — a curly apostrophe against a
    straight one, a sentence reproduced more completely than the clip stored —
    and none of them can occur when the text is never retyped.

    A site that cites no id keeps whatever quote it wrote, so the entailment
    gate still has something to judge; that is the backward-compatible path."""
    lines = list(evidence)
    for site in result.sites:
        cid = (getattr(site, "supporting_clip_id", "") or "").strip().upper()
        if not cid.startswith("L"):
            continue
        try:
            idx = int(cid[1:]) - 1
        except ValueError:
            continue
        if not 0 <= idx < len(lines):
            continue
        span = next(iter(getattr(lines[idx], "spans", None) or []), None)
        if span is not None and getattr(span, "quote", None):
            site.supporting_quote = span.quote
    return result


def attach_source_pmids(
    result: TagSiteResult,
    *,
    evidence: Iterable[Any],
    papers_by_id: Mapping[str, Any],
) -> TagSiteResult:
    """Fill ``supporting_pmid`` from the ledger line the site actually cited.

    The model was being asked to transcribe an identifier the pipeline already
    holds, and it could not: ``paper_source_id`` keys a paper ``PMC:<id>`` in
    preference to ``PMID:<id>`` (right for a pool key — PMC is the full-text
    key), and the ledger inherited that label and instructed null. So every
    PMC-sourced citation lost its PMID — 99 of 125 papers in one pool — and
    ``to_viewer_sites`` then stamped the record ``citation: "preprint"`` on
    peer-reviewed papers, which also left the records with no PMID for the
    viewer's citation rule to link.

    The quote identifies the ledger line, the line identifies the source, and
    the source carries the PMID. A genuine DOI-only preprint has no pmid and
    stays null, which is the only case that label was ever meant for."""
    spans = [
        (sp.quote, sp.source.source_id)
        for e in evidence
        for sp in (e.spans or [])
        if sp.quote and sp.source
    ]
    for site in result.sites:
        if not site.supporting_quote:
            continue
        source_id = next(
            (sid for quote, sid in spans if quote_supported(site.supporting_quote, quote)),
            None,
        )
        if source_id:
            # Keep the accession even when there is no PMID. Without it a
            # DOI-only preprint published as the bare word "preprint", naming
            # nothing a reader could look up — and the repo's citation rule is
            # that a cited paper must be one click from its source.
            site.supporting_source_id = source_id
        paper = papers_by_id.get(source_id) if source_id else None
        pmid = getattr(paper, "pmid", None)
        if pmid:
            try:
                site.supporting_pmid = int(str(pmid).strip())
            except ValueError:  # a non-numeric id is not a PMID; leave it null
                pass
    return result


#: Quote prefix kept per clip in the run artifact. Enough to recognise a clip;
#: not the draft's `context_excerpt`, which runs to 1500 chars and would make
#: one well-studied gene's pool (2,175 clips) megabytes on its own.
_POOL_QUOTE_CHARS = 180


def _pool_index(
    pool: dict[str, Any],
    *,
    boosted: dict[str, set[int]],
    selected: set[str],
) -> list[dict[str, Any]]:
    """A bounded, per-clip record of the pool the selector was offered.

    The artifact exists so that "why was this clip not proposed" costs a read
    rather than a fresh run, and it could not answer that: `pool` was empty in
    all 26 artifacts of a live sweep while `n_clips` recorded 60-214. Size was
    persisted; contents were not.

    Each entry carries the clip id, its source and section, whether the
    residue-boost lifted it above the menu cap, whether the selector took it,
    and a quote prefix. The boost flag is the load-bearing one: it separates
    "the model saw this clip and passed on it" from "the cap meant the model
    never saw it", which is the whole menu-starvation question.
    """
    out: list[dict[str, Any]] = []
    for clip_id, draft in pool.items():
        quote = str(getattr(draft, "quote", "") or "")
        out.append(
            {
                "clip_id": clip_id,
                "source_id": getattr(draft, "source_id", None),
                "section": getattr(draft, "section", None),
                "quote_chars": len(quote),
                "quote_head": quote[:_POOL_QUOTE_CHARS],
                "boosted_residues": sorted(boosted.get(clip_id, ()) or ()),
                "selected": clip_id in selected,
            }
        )
    return out


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
    sp_end: int | None = None,
    usage_sink: list[Any] | None = None,
    intermediates: dict[str, Any] | None = None,
    loop_inventory: str | None = None,
    prior_clips: list[PriorClip] | None = None,
    seen_keys: set[str] | None = None,
    covered_junctions: set[int] | None = None,
    numbered_against: str | None = None,
    alternate_frames: list[Frame] | None = None,
    frame_label: str = "member",
    select_max_batches: int = 1,
    faceted_discovery: bool = False,
    web_search_mode: WebSearchMode = "adaptive",
    model: str = DEFAULT_TAG_SITE_MODEL,
    triage_model: str = DEFAULT_TAG_SITE_TRIAGE_MODEL,
    web_scout_model: str = DEFAULT_TAG_SITE_WEB_SCOUT_MODEL,
    triage_concurrency: int | None = None,
    use_caches: bool = True,
    extra_paper_ids: list[str] | None = None,
    skip_discovery: bool = False,
    seed_papers: dict[str, Paper] | None = None,
    seed_triage_cache: dict[str, dict[str, Any]] | None = None,
    follow_construct_refs: bool | None = None,
    max_worth_fetching: int = _MAX_WORTH_FETCHING,
    max_pool_per_paper: int = _MAX_POOL_PER_PAPER,
) -> TagSiteResult:
    """Discover papers (+ preprints, retraction-filtered), triage with the
    dedicated tag-site Haiku prompt, cap & fetch full-text bodies with loop-
    aware relevance, run adaptive web search + optional 1-hop construct-citation
    follow-up, boost & select clips, then synthesize a validated, ranked
    :class:`TagSiteResult` grounded in the span-verified evidence ledger."""
    client = client or get_client()
    http = http or open_default_client()
    usage_sink = usage_sink if usage_sink is not None else []
    caches_active = use_caches and isinstance(http, CachedHTTP)
    internal_only = bool(loop_inventory)
    do_ref_followup = (
        internal_only if follow_construct_refs is None else bool(follow_construct_refs)
    )
    web_intent = _TAG_SITE_INTERNAL_INTENT if internal_only else _TAG_SITE_INTENT

    try:
        ri = _retraction_from_http(http)  # best-effort Retraction Watch index
    except Exception:  # noqa: BLE001 - never block on the retraction fetch
        ri = _empty_retraction()

    _progress: dict[str, Any] = {
        "gene_symbol": gene_symbol,
        "model": model,
        "triage_model": triage_model,
        "web_scout_model": web_scout_model,
        "web_search_mode": web_search_mode,
        "web_search_used": False,
        "web_search_reason": None,
        "web_search_paper_ids": [],
        "followup_ref_ids": [],
        "extra_paper_ids": list(extra_paper_ids or ()),
        "n_papers": 0,
        "n_papers_fetched": 0,
        "n_clips": 0,
        "n_boosted": 0,
        "boosted": {},
        "ledger": [],
        "synthesis_meta": {},
        "notes": "",
        "n_sites": 0,
        "rejected": [],
        "other_positions": [],
        "n_new_clips": 0,
        "n_carried": 0,
        "n_dropped_covered": 0,
        "n_refusals": 0,
        "cache_read_tokens": 0,
        "cache_write_tokens": 0,
        "numbered_against": numbered_against,
        "outcome": "incomplete",
        "sites": [],
    }

    def _stamp(**final: Any) -> None:
        """Write the run's account into the caller's dict. Every return goes
        through here, so a new early return cannot silently skip it."""
        n_ref = sum(
            1 for u in usage_sink if getattr(u, "api_stop_reason", None) == "refusal"
        )
        cr = sum(int(getattr(u, "cache_read_input_tokens", 0) or 0) for u in usage_sink)
        cw = sum(int(getattr(u, "cache_creation_input_tokens", 0) or 0) for u in usage_sink)
        _progress["n_refusals"] = n_ref
        _progress["cache_read_tokens"] = cr
        _progress["cache_write_tokens"] = cw
        if intermediates is not None:
            intermediates.update({**_progress, **final})

    def _empty() -> TagSiteResult:
        _stamp()
        return TagSiteResult(
            gene_symbol=gene_symbol,
            uniprot_accession=uniprot_accession,
            sequence_length=len(sequence or ""),
            prompt_sha=prompt_sha(),
            prompt_version=TAG_SITE_PROMPT_VERSION,
            model=model,
            generated_at=datetime.now(UTC).isoformat(),
        )

    all_names = [n for n in dict.fromkeys([gene_symbol, protein_name, *aliases]) if n]
    triage_syns = [
        s for s in all_names if s.strip().upper() != gene_symbol.strip().upper()
    ]
    _tsha = triage_prompt_sha(internal_only=internal_only)

    def _triage_papers(target_papers: dict[str, Paper]) -> list[Any]:
        if not target_papers:
            return []
        cached_map: dict[str, dict[str, Any]] = dict(seed_triage_cache or {})
        if caches_active:
            cached_map.update(load_triage_cache(gene_symbol))
        todo, reused = split_triage(
            target_papers, cached_map, prompt_sha=_tsha, model=triage_model
        )
        if reused:
            log.info(
                "  %s: reusing %d cached triage verdict(s) [%s]; %d to run",
                gene_symbol,
                len(reused),
                triage_model,
                len(todo),
            )
        triage_kw: dict[str, Any] = {
            "papers": todo,
            "gene": gene_symbol,
            "synonyms": triage_syns,
            "internal_only": internal_only,
            "model": triage_model,
        }
        if triage_concurrency is not None:
            triage_kw["concurrency"] = triage_concurrency
        fresh = triage_abstracts(client, **triage_kw) if todo else []
        usage_sink.extend(o.usage for o in fresh if getattr(o, "usage", None))
        if fresh and caches_active:
            save_triage_cache(
                gene_symbol,
                fresh,
                prompt_sha=_tsha,
                inputs={sid: triage_input_sha(p) for sid, p in target_papers.items()},
                model=triage_model,
            )
        return reused + fresh

    def _run_web_scout(known: dict[str, Paper] | None = None) -> list[Paper]:
        _progress["web_search_used"] = True
        if caches_active:
            cached_ws_ids = load_web_search_cache(
                gene_symbol,
                model=web_scout_model,
                max_uses=_WEB_SEARCH_MAX_USES,
                intent=web_intent,
                cache_dir=DISCOVERY_CACHE_DIR,
            )
            if cached_ws_ids is not None:
                _progress["web_search_paper_ids"] = list(cached_ws_ids)
                log.info(
                    "  %s: reusing cached web_search result (%d hit(s), model=%s)",
                    gene_symbol,
                    len(cached_ws_ids),
                    web_scout_model,
                )
                reused_hits: list[Paper] = []
                missing_ids: list[str] = []
                for cid in cached_ws_ids:
                    if known and cid in known:
                        reused_hits.append(known[cid])
                    else:
                        missing_ids.append(cid)
                if missing_ids and isinstance(http, CachedHTTP):
                    hydrated = hydrate_paper_ids(
                        missing_ids, http=http, retraction_index=ri
                    )
                    reused_hits.extend(hydrated.values())
                return reused_hits
        hits = web_discover_papers(
            client,
            intent=web_intent,
            gene_names=all_names,
            http=http,
            retraction_index=ri,
            usage_sink=usage_sink,
            max_uses=_WEB_SEARCH_MAX_USES,
            model=web_scout_model,
        )
        hit_ids = [paper_source_id(p) for p in hits]
        _progress["web_search_paper_ids"] = hit_ids
        if caches_active:
            save_web_search_cache(
                gene_symbol,
                hit_ids,
                model=web_scout_model,
                max_uses=_WEB_SEARCH_MAX_USES,
                intent=web_intent,
                cache_dir=DISCOVERY_CACHE_DIR,
            )
        return hits

    # 1. Discovery: deterministic EuropePMC (TITLE_ABS + SRC:PPR) + PubTator,
    # seeded from R2/local discovery cache + optional user-supplied extra papers.
    cached_papers: dict[str, Paper] = dict(seed_papers or {})
    if use_caches:
        cached_papers.update(
            load_discovery_cache(gene_symbol, cache_dir=DISCOVERY_CACHE_DIR)
        )
    citation_counts: dict[str, int] = {}
    if skip_discovery and cached_papers:
        papers: dict[str, Paper] = dict(cached_papers)
        log.info("  %s: skip_discovery=True — using %d seeded paper(s)", gene_symbol, len(papers))
    else:
        papers = discover_tag_site_papers(
            http=http,
            gene_symbol=gene_symbol,
            aliases=aliases,
            retraction_index=ri,
            cached=cached_papers or None,
            faceted=faceted_discovery,
            internal_only=internal_only,
            include_preprint_pass=True,
            citation_counts_out=citation_counts,
        )

    pinned_extra_papers: dict[str, Paper] = {}
    if extra_paper_ids and isinstance(http, CachedHTTP):
        pinned_extra_papers = hydrate_paper_ids(
            extra_paper_ids, http=http, retraction_index=ri
        )
        for sid, paper in pinned_extra_papers.items():
            papers[sid] = paper

    if web_search_mode == "always":
        _progress["web_search_reason"] = "mode=always"
        for wp in _run_web_scout(papers):
            sid = paper_source_id(wp)
            papers.setdefault(sid, wp)
            pinned_extra_papers.setdefault(sid, wp)
    elif web_search_mode == "adaptive" and not papers:
        _progress["web_search_reason"] = "deterministic_empty"
        for wp in _run_web_scout(papers):
            sid = paper_source_id(wp)
            papers.setdefault(sid, wp)
            pinned_extra_papers.setdefault(sid, wp)

    papers_by_id: dict[str, Paper] = {paper_source_id(p): p for p in papers.values()}
    if use_caches and papers_by_id:
        save_discovery_cache(gene_symbol, papers_by_id, cache_dir=DISCOVERY_CACHE_DIR)
    _progress["n_papers"] = len(papers_by_id)
    if not papers_by_id:
        _progress["outcome"] = "no_papers_discovered"
        return _empty()

    # 2. Dedicated tag-site abstract triage -> 3. capped body fetch -> clip pool.
    pinned_ids = set(pinned_extra_papers)
    papers_to_triage = {
        sid: p for sid, p in papers_by_id.items() if sid not in pinned_ids
    }
    outcomes = _triage_papers(papers_to_triage)
    if pinned_extra_papers:
        outcomes.extend(force_worth_fetching_outcomes(pinned_extra_papers))
    outcomes = _cap_worth_fetching(
        outcomes,
        papers_by_id,
        sequence=sequence,
        internal_only=internal_only,
        max_fetch=max_worth_fetching,
        pinned_ids=pinned_ids,
        citation_counts=citation_counts,
    )
    rel_fn = tag_site_relevance(sequence, internal_only=internal_only) if sequence else None
    pool, actions = build_pool(
        outcomes, papers_by_id, http=http, retraction_index=ri, relevance=rel_fn
    )

    # Initial boost pass so adaptive web search knows whether deterministic
    # discovery already delivered residue-pinned extracellular clips.
    boosted: dict[str, set[int]] = {}
    if sequence and topology:
        boosted = boost_residue_clips(
            pool,
            sequence=sequence,
            topology=topology,
            alternate_frames=alternate_frames,
            internal_only=internal_only,
        )

    def _merge_extra_papers(
        new_papers: dict[str, Paper],
        *,
        force_fetch: bool,
        reason: str = "1-hop construct citation follow-up",
    ) -> None:
        if not new_papers:
            return
        for sid, p in new_papers.items():
            papers_by_id[sid] = p
        if use_caches:
            save_discovery_cache(gene_symbol, papers_by_id, cache_dir=DISCOVERY_CACHE_DIR)
        _progress["n_papers"] = len(papers_by_id)
        if force_fetch:
            sub_outcomes = force_worth_fetching_outcomes(new_papers, reason=reason)
        else:
            sub_outcomes = _triage_papers(new_papers)
        outcomes.extend(sub_outcomes)
        sub_pool, sub_actions = build_pool(
            sub_outcomes, new_papers, http=http, retraction_index=ri, relevance=rel_fn
        )
        for cid, draft in sub_pool.items():
            key = cid
            k = 2
            while key in pool:
                key = f"{cid}_{k}"
                k += 1
            pool[key] = draft.model_copy(update={"suggested_evidence_id": key})
        actions.extend(sub_actions)

    # Adaptive web_search: only pay for the Haiku 5.5 web scout when
    # deterministic discovery left thin full-text or residue-pinned coverage.
    # Force-fetch the 1-6 targeted web_search hits directly (even if already
    # in papers_by_id and discarded by abstract-only triage) because web_search
    # searched full text for Methods-hidden extracellular loop tags.
    if web_search_mode == "adaptive" and not _progress["web_search_used"]:
        need_ws, ws_reason = _needs_adaptive_web_search(
            pool=pool, actions=actions, boosted=boosted
        )
        _progress["web_search_reason"] = ws_reason
        log.info("  %s: adaptive web_search=%s (%s)", gene_symbol, need_ws, ws_reason)
        if need_ws:
            already_fetched = set(pinned_ids) | {
                o.paper_id
                for o in outcomes
                if o.response is not None and o.response.decision == "worth_fetching"
            }
            web_to_fetch: dict[str, Paper] = {}
            for wp in _run_web_scout(papers_by_id):
                sid = paper_source_id(wp)
                if sid not in already_fetched:
                    web_to_fetch[sid] = papers_by_id.get(sid, wp)
            _merge_extra_papers(
                web_to_fetch, force_fetch=True, reason="adaptive web_search hit"
            )

    # Optional 1-hop construct-citation follow-up (e.g. "BLAP-KCNN3 as
    # previously described [18]") when we still have <2 residue-boosted papers.
    if do_ref_followup and isinstance(http, CachedHTTP):
        boosted_sources = {
            getattr(pool[cid], "source_id", cid) for cid in boosted if cid in pool
        }
        if len(boosted_sources) < 2 and pool:
            ref_ids = find_construct_followup_paper_ids(
                pool.values(), papers_by_id=papers_by_id, http=http, max_refs=3
            )
            if ref_ids:
                _progress["followup_ref_ids"] = list(ref_ids)
                log.info(
                    "  %s: 1-hop construct citation follow-up -> %s",
                    gene_symbol,
                    ref_ids,
                )
                hydrated_refs = hydrate_paper_ids(
                    ref_ids, http=http, retraction_index=ri
                )
                new_refs = {
                    sid: p for sid, p in hydrated_refs.items() if sid not in papers_by_id
                }
                _merge_extra_papers(new_refs, force_fetch=True)

    # Re-run boosting if adaptive web search or 1-hop ref follow-up grew the pool.
    if sequence and topology and (
        _progress["web_search_paper_ids"] or _progress["followup_ref_ids"]
    ):
        boosted = boost_residue_clips(
            pool,
            sequence=sequence,
            topology=topology,
            alternate_frames=alternate_frames,
            internal_only=internal_only,
        )

    if boosted:
        log.info(
            "  %s: boosted %d/%d clips naming an extracellular residue",
            gene_symbol,
            len(boosted),
            len(pool),
        )
        for key, positions in list(boosted.items())[:12]:
            clip = pool[key]
            log.info(
                "      %s @%s: %s",
                getattr(clip, "source_id", key),
                sorted(positions),
                (getattr(clip, "quote", "") or "")[:110],
            )

    fetched_by_id = {a.paper_id: bool(getattr(a, "fetched_body", False)) for a in actions}
    _progress["n_papers_fetched"] = sum(1 for v in fetched_by_id.values() if v)
    _progress["fetch_actions"] = [
        {
            "paper_id": getattr(a, "paper_id", None),
            "decision": getattr(a, "decision", None),
            "fetched_body": bool(getattr(a, "fetched_body", False)),
            "body_source": getattr(a, "fetch_source", None) or getattr(a, "body_source", None),
            "n_drafts": getattr(a, "drafts_added", None),
            "error": getattr(a, "fetch_error", None) or getattr(a, "error", None),
        }
        for a in actions
    ]
    _progress["triage_verdicts"] = {
        getattr(o, "paper_id", ""): {
            "decision": getattr(getattr(o, "response", None), "decision", None),
            "reason": getattr(getattr(o, "response", None), "reason", None),
            "prompt_sha": _tsha,
            "input_sha": (
                triage_input_sha(papers_by_id[o.paper_id])
                if getattr(o, "paper_id", None) in papers_by_id
                else None
            ),
            "model": triage_model,
            "error": getattr(o, "error", None),
        }
        for o in outcomes
        if getattr(o, "paper_id", None)
    }
    _progress["discovered_papers"] = {
        sid: (p.model_dump(mode="json") if hasattr(p, "model_dump") else dict(vars(p)))
        for sid, p in papers_by_id.items()
    }

    papers_by_source_id = {
        pid: (paper, fetched_by_id.get(pid, False)) for pid, paper in papers_by_id.items()
    }
    store = build_source_store(
        pool, papers_by_source_id=papers_by_source_id, http=http, retraction_index=ri
    )

    # Carry forward what an earlier run cited.
    carried = seed_pool(pool, prior_clips, store=store) if prior_clips else set()
    if carried:
        log.info("  %s: carried %d previously-cited clip(s) forward", gene_symbol, len(carried))

    # Drop clips that only restate a junction we already publish.
    dropped_covered = (
        covered_clip_ids(pool, sequence=sequence, covered_junctions=covered_junctions)
        if covered_junctions
        else set()
    )
    for cid in dropped_covered:
        pool.pop(cid, None)
    if dropped_covered:
        log.info(
            "  %s: dropped %d clip(s) restating an already-published junction",
            gene_symbol,
            len(dropped_covered),
        )

    # Cap per-paper clips in the menu (always preserving carried & residue-boosted clips).
    pool = _cap_pool_per_paper(
        pool, max_per_paper=max_pool_per_paper, keep_ids=carried | set(boosted)
    )

    enriching = bool(seen_keys or carried or dropped_covered)
    if enriching:
        scope = EnrichmentScope(
            carried=carried, seen_keys=set(seen_keys or ()), dropped_covered=set()
        )
        n_new = count_new(pool, scope)
        fresh_ids = sorted(new_clip_ids(pool, scope))
    else:
        n_new, fresh_ids = len(pool), []
    _progress.update({
        "n_clips": len(pool),
        "n_boosted": len(boosted),
        "boosted": {k: sorted(v) for k, v in boosted.items()},
        "n_new_clips": n_new,
        "n_carried": len(carried),
        "n_dropped_covered": len(dropped_covered),
        "new_clip_ids": fresh_ids,
    })

    if enriching and n_new == 0:
        log.info(
            "  %s: no new evidence in %d clip(s) — stopping before synthesis",
            gene_symbol,
            len(pool),
        )
        _progress["outcome"] = "no_new_evidence"
        return _empty()

    selection = select_clips(
        client,
        pool=pool,
        gene=gene_symbol,
        synonyms=aliases,
        system_prompt=load_tag_select_prompt(),
        model=model,
        menu_instruction=_TAG_SELECT_MENU_INSTRUCTION,
        usage_sink=usage_sink,
        max_batches=select_max_batches,
    )
    _progress["pool"] = _pool_index(
        pool,
        boosted=boosted,
        selected={
            s.clip_id
            for s in getattr(selection, "selections", []) or []
            if getattr(s, "clip_id", None)
        },
    )

    evidence_all = [
        e
        for e in promote(
            selection, pool=pool, store=store, evidence_id_prefix=_TAG_EVIDENCE_ID_PREFIX
        )
        if e.entailment_verified
    ]
    if not evidence_all:
        _progress["outcome"] = "no_span_verified_evidence"
        return _empty()

    evidence = _select_evidence_for_synthesis(
        evidence_all, sequence=sequence, internal_only=internal_only
    )

    # 6. Synthesis: the geometry/validation/snorkel rules read the span-verified ledger.
    user_prompt = build_user_prompt(
        gene_symbol, protein_name, mode=mode, sequence=sequence, topology=topology,
        sp_end=sp_end,
    )
    if loop_inventory:
        user_prompt = f"{user_prompt}\n\nCONSTRUCT GEOMETRY: {loop_inventory}"
    user_prompt = f"{user_prompt}\n\n{format_evidence_ledger(evidence)}"

    synth_meta: dict[str, Any] = {}
    result = call_builder(
        client,
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        schema=TagSiteResult,
        usage_sink=usage_sink,
        label=f"tag_site:{gene_symbol}",
        max_tokens=32_000,
        tools=CODE_EXECUTION_TOOL,
        meta_sink=synth_meta,
        model=model,
    )
    if result is None:
        _progress["outcome"] = "synthesis_returned_nothing"
        return _empty()
    assert isinstance(result, TagSiteResult)
    result.rejected = []

    result.gene_symbol = gene_symbol
    result.uniprot_accession = uniprot_accession
    result.sequence_length = len(sequence or "")

    fill_quotes_from_ledger(result, evidence=evidence)
    verify_entailment(result, evidence=evidence)
    recover_overcomplete_quotes(result, evidence=evidence)
    verify_entailment(result, evidence=evidence)

    for _s in result.sites:
        if not _s.entailment_verified:
            log.info(
                "  %s: dropped %s — quote not found in the ledger: %.120r",
                gene_symbol,
                _s.residue_label,
                _s.supporting_quote or "",
            )
            result.rejected.append(RejectedSite(
                residue_label=_s.residue_label,
                insert_after_residue=_s.insert_after_residue,
                gate="entailment",
                reason="supporting_quote is not in the span-verified ledger",
                supporting_quote=_s.supporting_quote,
            ))
    result.sites = [s for s in result.sites if s.entailment_verified]
    attach_source_pmids(result, evidence=evidence, papers_by_id=papers_by_id)
    upgrade_quotes(result, evidence=evidence)
    enforce_position_claims(
        result,
        sequence=sequence,
        client=client,
        frames=alternate_frames,
        reference_label=frame_label,
        verifier_model=triage_model,
        usage_sink=usage_sink,
    )
    enforce_evidence_type_coupling(result)
    if sequence and topology:
        kept, rejected = apply_geometry_pass(
            result.sites,
            sequence=sequence,
            topology=topology,
            sp_end=signal_peptide_end(topology) if sp_end is None else sp_end,
        )
        for site, reason in rejected:
            log.info("  %s: dropped %s — %s", gene_symbol, site.residue_label, reason)
            result.rejected.append(RejectedSite(
                residue_label=site.residue_label,
                insert_after_residue=site.insert_after_residue,
                gate="geometry",
                reason=reason,
            ))
        result.sites = kept

    _stamp(
        ledger=[
            {
                "source_id": (sp.source.source_id if sp.source else None),
                "claim": e.claim,
                "quote": sp.quote,
            }
            for e in evidence
            for sp in (e.spans or [])
        ],
        synthesis_meta=synth_meta,
        notes=result.notes,
        n_sites=len(result.sites),
        rejected=[x.model_dump() for x in result.rejected],
        other_positions=[x.model_dump() for x in result.other_positions],
        sites=[x.model_dump() for x in result.sites],
        outcome="synthesized",
    )

    result.prompt_sha = prompt_sha()
    result.prompt_version = TAG_SITE_PROMPT_VERSION
    result.model = model
    result.generated_at = datetime.now(UTC).isoformat()
    return rank_sites(result)


def _run_position(topology: str, junction: int | None) -> str | None:
    """Where the junction's extracellular run sits: ``inter_tm`` means a loop.

    Derived rather than taken from ``site_kind``, which cannot tell a loop from
    an N-terminal tail — the five published literature sites at positions 4-5 are
    topologically identical and are labelled ``internal`` twice and
    ``terminal_n`` three times, with both paralogue pairs disagreeing with their
    own partner."""
    if junction is None:
        return None
    run = run_at(topology, junction)
    return run.position if run else None


def _citation_label(source_id: str) -> str:
    """A human citation from an accession: "DOI 10.1101/x", "PMC PMC123".

    Falls back to "preprint" only when there is genuinely no identifier, which
    is the one case that word was ever meant for."""
    if not source_id:
        return "preprint"
    prefix, _, rest = source_id.partition(":")
    return f"{prefix} {rest}" if rest else source_id


def to_viewer_sites(
    result: TagSiteResult,
    *,
    uniprot_acc: str,
    provenance: str = "literature_retrieved",
    candidate_id: str | None = None,
    library: str | None = None,
    numbered_against: str | None = None,
    topology: str | None = None,
) -> list[dict[str, Any]]:
    """Convert to the viewer's ``literature_retrieved`` TaggedSite shape
    (viewer/lib/tag-sites-types.ts). Agent-only fields (validation_level,
    position_evidence, source_tier, entailment) fold into ``rationale``/``sources``
    so the viewer contract is unchanged.

    Proposals sharing a junction are MERGED into one site carrying every
    citation. Two papers independently placing a tag at the same residue is
    corroboration, not two sites — emitting both produced records with a
    duplicated ``site_id``. ``result.sites`` arrives best-first, so the
    better-validated proposal supplies the body and the rest contribute sources."""
    out: list[dict[str, Any]] = []
    by_id: dict[str, dict[str, Any]] = {}
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
            # No PMID — a preprint, or a record NCBI does not index. Cite the
            # accession the pipeline resolved; "preprint" on its own identifies
            # nothing, and 25 published refs across 24 genes said exactly that.
            acc = s.supporting_source_id or ""
            sources.append({
                "source_id": acc or None,
                "citation": _citation_label(acc),
                "claim": s.supporting_quote,
            })

        if provenance == "literature_enriched":
            member = candidate_id or "nomember"
            site_id = (
                f"{result.gene_symbol}-{member}-{s.site_type}-"
                f"{s.insert_after_residue}-enr"
            )
        else:
            site_id = (
                f"{result.gene_symbol}-{s.site_type}-{s.insert_after_residue}-lit"
            )
        if site_id in by_id:
            kept = by_id[site_id]["sources"]
            seen = {(src.get("pmid"), src.get("claim")) for src in kept}
            kept.extend(
                src for src in sources if (src.get("pmid"), src.get("claim")) not in seen
            )
            continue

        record: dict[str, Any] = {
            "site_id": site_id,
            "gene_symbol": result.gene_symbol,
            "uniprot_acc": uniprot_acc,
            "provenance": provenance,
            "det_path": None,
            "site_kind": s.site_type,
            "insert_after_residue": s.insert_after_residue,
            "residue_before": s.residue_before,
            "residue_after": s.residue_after,
            "residue_label": s.residue_label,
            "topology_state": _TOPO_CHAR[s.topology_state],
            "extracellular": s.topology_state == "extracellular",
            "compartment": s.topology_state,
            "tag_type": s.tag_type,
            "tag_length_aa": None,
            "linker": None,
            "evidence_type": s.evidence_type,
            "functional_impact_measured": s.functional_or_expression_impact_measured,
            "confidence": s.confidence,
            # Prose only. These used to be concatenated into the rationale as
            # "[validation: ...; position: ...; entailment_verified: True]",
            # which put raw field names and Python True in front of a reader and
            # left the viewer unable to render any of it as structure. They are
            # fields now; the rationale is the argument, and nothing else.
            "rationale": (
                f"{s.rationale} "
                # evidence_detail is where the prompt sends the assay, the
                # result and any confound.
                + (f"{s.evidence_detail}" if s.evidence_detail else "")
            ).strip(),
            "validation_level": s.validation_level,
            "position_evidence": s.position_evidence,
            "source_tier": s.source_tier,
            # What makes an "inferred" position honest: where the real tag sits.
            "cited_tag_residue": (
                s.cited_tag_residue if s.position_evidence == "inferred" else None
            ),
            "entailment_verified": bool(s.entailment_verified),
            "position_repaired": bool(s.position_repaired),
            "quote_probative": bool(s.quote_probative),
            "sources": sources,
            "plddt": None,
            "conservation_rank": None,
            "median_conservation": None,
            # Which construct, and the sequence the position is expressed in.
            "candidate_id": candidate_id,
            "library": library,
            "numbered_against": numbered_against,
            # Loop-ness from topology, never from the site_kind label.
            "loop_run_position": (
                _run_position(topology, s.insert_after_residue) if topology else None
            ),
            # Set by the frame resolver when the citation numbered in another
            # proteoform; None means the paper used this construct's own frame.
            "position_frame": getattr(s, "position_frame", None),
        }
        by_id[site_id] = record
        out.append(record)
    return out
