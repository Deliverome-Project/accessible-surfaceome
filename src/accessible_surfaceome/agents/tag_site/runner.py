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
from accessible_surfaceome.agents.surfaceome_v2.builders._common import SONNET_MODEL, call_builder
from accessible_surfaceome.tools._shared.http import CachedHTTP, open_default_client
from accessible_surfaceome.tools._shared.models import Evidence, Paper, paper_source_id
from accessible_surfaceome.tools._shared.retraction_watch import empty as _empty_retraction
from accessible_surfaceome.tools._shared.retraction_watch import from_http as _retraction_from_http

from .geometry import apply_geometry_pass
from .literature_discovery import (
    DISCOVERY_CACHE_DIR,
    SOURCE_TIERS,
    best_supporting_quote,
    boost_residue_clips,
    discover_tag_site_papers,
    load_discovery_cache,
    quote_is_probative,
    ledger_clip_within,
    quote_supported,
    residue_mentions,
    save_discovery_cache,
)
from .normalize import signal_peptide_end
from .prompt import (
    SYSTEM_PROMPT,
    TAG_SITE_PROMPT_VERSION,
    build_user_prompt,
    keep_validated_sites,
    prompt_sha,
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
    input_sha as triage_input_sha,
)
from .triage_cache import (
    triage_prompt_sha,
)
from .schema import (
    VALIDATION_LEVELS,
    VALIDATION_RANK,
    RejectedSite,
    TagSiteProposal,
    TagSiteResult,
)

# web_search discovery is delegated to the shared ``web_literature`` module
# (agents/_support), so the tag-site and internalization tracks share ONE
# implementation. This is the tag-site topic phrase passed to it.
_TAG_SITE_INTENT = (
    "epitope / peptide tag insertion for surface display — ecto-tagging and "
    "knock-in constructs that place a tag (HA, FLAG, Myc, ALFA, HiBiT, SpyTag, "
    "bungarotoxin-binding site, snorkel) in an extracellular loop or terminus, "
    "and their surface-display / functional validation"
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


def tag_site_relevance(sequence: str) -> Callable[[str], float]:
    """A per-sentence relevance term for draft extraction, scoring what a
    tag-site clip has to contain to be worth anything.

    Draft extraction otherwise ranks sentences by POSITION and keeps the first
    few per section, so for a paper of any length the agent receives the section
    preamble and none of its findings. On the preprint behind five of the curated
    controls that cost the one sentence naming the insertion residue; the agent
    cited the general-method line it did receive and invented a position 64
    residues away.

    Two signals, deliberately additive rather than either/or:

    * the sentence describes an insertion at all (:func:`quote_is_probative`);
    * it names a residue the canonical sequence CONFIRMS
      (:func:`residue_mentions`), which is what separates a real label from a
      cell line or a histone mark.

    A sentence with both outranks one with either, and both outrank the 1..2
    band positional scoring occupies — so a finding can displace preamble, which
    is the whole point."""
    def score(text: str) -> float:
        value = 0.0
        if quote_is_probative(text):
            value += 3.0
        if residue_mentions(text, sequence=sequence):
            value += 3.0
        return value

    return score


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
        "its QUOTE into supporting_quote exactly — that is what identifies the "
        "source, so the citation is filled in for you. Do NOT invent sites or "
        "quotes beyond this ledger):"
    ]
    for e in evidence:
        span = e.spans[0] if e.spans else None
        source_id = span.source.source_id if span and span.source else "?"
        pmid = source_id.split("PMID:", 1)[1] if source_id.startswith("PMID:") else None
        label = f"PMID {pmid}" if pmid else source_id
        quote = span.quote if span else ""
        lines.append(f"- [{label}] {e.claim}\n  QUOTE: {quote}")
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


def enforce_position_claims(result: TagSiteResult, *, sequence: str) -> TagSiteResult:
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
    cell line or a stray integer cannot launder a position claim."""
    if not sequence:
        return result
    for s in result.sites:
        if s.position_evidence != "validated":
            continue
        n = s.insert_after_residue
        if n is None:
            # A region-level site claims no junction, so there is no position
            # for a quote to name; it is already labelled 'inferred' by the
            # prompt and must not be re-judged against a residue it never gave.
            continue
        named = residue_mentions(s.supporting_quote, sequence=sequence)
        if not named & {n - 1, n, n + 1}:
            s.position_evidence = "inferred"
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
        paper = papers_by_id.get(source_id) if source_id else None
        pmid = getattr(paper, "pmid", None)
        if pmid:
            try:
                site.supporting_pmid = int(str(pmid).strip())
            except ValueError:  # a non-numeric id is not a PMID; leave it null
                pass
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
    sp_end: int | None = None,
    usage_sink: list[Any] | None = None,
    intermediates: dict[str, Any] | None = None,
) -> TagSiteResult:
    """Discover papers (+ preprints, retraction-filtered), triage, pool + span-verify
    tag-insertion clips (shared clip pipeline), then synthesize a validated, ranked
    :class:`TagSiteResult` grounded in that evidence ledger. ``aliases`` should
    include the protein name(s).

    ``sp_end`` is the AUTHORITATIVE signal-peptide end (UniProt's ``Signal``
    feature). Pass it whenever you have it: it beats the DeepTMHMM run encoded in
    ``topology``, which disagrees with UniProt for a real fraction of genes, and
    it is what both the prompt landmarks and the geometry gate key off."""
    client = client or get_client()
    http = http or open_default_client()
    usage_sink = usage_sink if usage_sink is not None else []

    try:
        ri = _retraction_from_http(http)  # best-effort Retraction Watch index
    except Exception:  # noqa: BLE001 - never block on the retraction fetch
        ri = _empty_retraction()

    def _empty() -> TagSiteResult:
        """An empty result is still a result, and carries its provenance.

        There are three early returns through here — no papers, no evidence, a
        synthesis that came back None — and each bypassed the stamping at the
        end of the function. A gene that ran and legitimately found nothing was
        therefore indistinguishable from one that never ran: ITGB5 came out of a
        24-gene sweep with no prompt_sha while every other gene carried one,
        including VANGL1, which also found nothing but reached the normal path.

        "Ran under prompt X and found nothing" is exactly the fact the
        provenance rule exists to preserve — a zero that cannot be dated has to
        be re-run to be trusted."""
        return TagSiteResult(
            gene_symbol=gene_symbol,
            uniprot_accession=uniprot_accession,
            sequence_length=len(sequence or ""),
            prompt_sha=prompt_sha(),
            prompt_version=TAG_SITE_PROMPT_VERSION,
            model=SONNET_MODEL,
            generated_at=datetime.now(UTC).isoformat(),
        )

    # 1. Discovery: repo lit-search + shared web_search complement, hydrated to real
    # Papers keyed by paper_source_id (deterministic pool wins on collision).
    # Seed with everything previous runs found for this gene, so a paper that is
    # only reachable through web search cannot vanish between runs.
    papers = discover_tag_site_papers(
        http=http,
        gene_symbol=gene_symbol,
        aliases=aliases,
        retraction_index=ri,
        cached=load_discovery_cache(gene_symbol, cache_dir=DISCOVERY_CACHE_DIR),
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
    save_discovery_cache(gene_symbol, papers_by_id, cache_dir=DISCOVERY_CACHE_DIR)
    if not papers_by_id:
        return _empty()

    # 2. Abstract triage -> 3. body pool + real source store (shared).
    # Resume: reuse verdicts this gene already has under the SAME triage prompt.
    # Triage is ~90% of a run's model calls (one per discovered paper), and it
    # was recomputed from scratch every time — so re-running a gene after a
    # SYNTHESIS prompt edit paid the whole triage bill again for identical
    # verdicts. A changed triage prompt_sha invalidates the lot automatically.
    _tsha = triage_prompt_sha()
    _cached = load_triage_cache(gene_symbol)
    _todo, _reused = split_triage(papers_by_id, _cached, prompt_sha=_tsha)
    if _reused:
        log.info("  %s: reusing %d cached triage verdict(s); %d to run",
                 gene_symbol, len(_reused), len(_todo))
    outcomes = _reused + (
        triage_abstracts(client, papers=_todo, gene=gene_symbol) if _todo else []
    )
    save_triage_cache(
        gene_symbol, outcomes, prompt_sha=_tsha,
        inputs={sid: triage_input_sha(p) for sid, p in papers_by_id.items()},
    )
    if usage_sink is not None:
        # `TriageOutcome.usage` is a populated UsageRecord (Haiku-priced) that
        # nothing collected, so abstract triage — the biggest fan-out, one call
        # per paper — contributed nothing to any cost total.
        usage_sink.extend(o.usage for o in outcomes if getattr(o, "usage", None))
    pool, actions = build_pool(
        outcomes, papers_by_id, http=http, retraction_index=ri,
        relevance=tag_site_relevance(sequence) if sequence else None,
    )
    fetched_by_id = {a.paper_id: bool(getattr(a, "fetched_body", False)) for a in actions}
    papers_by_source_id = {
        pid: (paper, fetched_by_id.get(pid, False)) for pid, paper in papers_by_id.items()
    }
    store = build_source_store(
        pool, papers_by_source_id=papers_by_source_id, http=http, retraction_index=ri
    )

    # 4. Clip select (tag-site prompt) -> 5. span-verified promotion. Keep only
    # clips whose quote has a real char offset into the fetched body.
    #
    # First lift clips that NAME an extracellular residue. The selector keeps only
    # the top clips by score, which on a well-studied gene drops most of the pool
    # (TFRC: 746 -> 100), so a clip pinning a real insertion can be cut before the
    # model ever sees it.
    boosted: dict[str, set[int]] = {}
    if sequence and topology:
        boosted = boost_residue_clips(pool, sequence=sequence, topology=topology)
        if boosted:
            log.info("  %s: boosted %d/%d clips naming an extracellular residue",
                     gene_symbol, len(boosted), len(pool))
            # Name them. A bare count cannot answer "was the right clip lifted?"
            # once the run is over, because the pool is not persisted.
            for key, positions in list(boosted.items())[:12]:
                clip = pool[key]
                log.info("      %s @%s: %s",
                         getattr(clip, "source_id", key), sorted(positions),
                         (getattr(clip, "quote", "") or "")[:110])
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
        gene_symbol, protein_name, mode=mode, sequence=sequence, topology=topology,
        sp_end=sp_end,
    )
    user_prompt = f"{user_prompt}\n\n{format_evidence_ledger(evidence)}"

    # n_repair_attempts + validation_error, as every v2 builder records. Without
    # it a repair cascade is only visible by reading raw logs, which is how the
    # KCNH2 13-error cascade went unnoticed.
    synth_meta: dict[str, Any] = {}
    result = call_builder(
        client,
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        schema=TagSiteResult,
        usage_sink=usage_sink,
        label=f"tag_site:{gene_symbol}",
        max_tokens=32_000,  # 16k default truncated multi-site outputs (e.g. SLC6A4)
        tools=CODE_EXECUTION_TOOL,
        meta_sink=synth_meta,
    )
    if result is None:
        return _empty()
    assert isinstance(result, TagSiteResult)  # expect_array=False -> single instance
    # Anything the model put here is its own editorial judgement, not a gate
    # record; `notes` is where that belongs.
    result.rejected = []

    # Identity is ours, not the model's: we passed the symbol and accession in and
    # computed the sequence. Stamping them here keeps the record's provenance
    # honest and lets the prompt stop asking for three fields it cannot know
    # better than we do.
    result.gene_symbol = gene_symbol
    result.uniprot_accession = uniprot_accession
    result.sequence_length = len(sequence or "")

    # 7. Post-process. Three gates, each removing a class of site that was
    # previously shipped unchecked:
    #   a) entailment — a quote that is not in the ledger is not evidence, so the
    #      site is DROPPED, not merely down-ranked.
    #   b) geometry — the junction is re-derived from the computed sequence and
    #      topology, repaired where that is deterministic, rejected otherwise.
    #   c) validation + ranking, as before.
    # Repair before the gate — but ONLY a repair that proves the citation, which
    # is the narrow case `apply_geometry_pass`'s "repair FIRST, then gate" rule
    # actually licenses. `recover_overcomplete_quotes` fires only when the
    # model's text CONTAINS a real ledger clip, and stores that clip, so it
    # cannot invent support; this is what rescues KCNH2 T436, deleted for
    # quoting its source more completely than the clip stored.
    #
    # `upgrade_quotes` stays AFTER the drop. It rescues a weak quote by swapping
    # in another ledger line, and falls back to any probative quote when none
    # names the residue — ahead of the gate that would let a wholly invented
    # quote survive wearing a real but unrelated citation, which is worse than
    # dropping the site.
    verify_entailment(result, evidence=evidence)
    recover_overcomplete_quotes(result, evidence=evidence)
    verify_entailment(result, evidence=evidence)

    for _s in result.sites:
        if not _s.entailment_verified:
            log.info("  %s: dropped %s — quote not found in the ledger: %.120r",
                     gene_symbol, _s.residue_label, _s.supporting_quote or "")
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
    #   b2) a site may claim a VALIDATED position only if its quote names it;
    #       otherwise the position came from topology, not from the citation.
    enforce_position_claims(result, sequence=sequence)
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
                gate="geometry", reason=reason,
            ))
        result.sites = kept
    if intermediates is not None:
        # The clip pool and the ledger were never persisted — the code says so
        # twice — so after a run finished there was no way to ask which clips
        # were available, what the model was shown, or why a site was not
        # proposed. Every such question today cost a fresh run to answer.
        intermediates.update({
            "gene_symbol": gene_symbol,
            "n_papers": len(papers_by_id),
            "n_clips": len(pool),
            "n_boosted": len(boosted),
            "boosted": {k: sorted(v) for k, v in boosted.items()},
            "ledger": [
                {
                    "source_id": (sp.source.source_id if sp.source else None),
                    "claim": e.claim,
                    "quote": sp.quote,
                }
                for e in evidence
                for sp in (e.spans or [])
            ],
            "synthesis_meta": synth_meta,
            "notes": result.notes,
            "rejected": [x.model_dump() for x in result.rejected],
        })

    result.prompt_sha = prompt_sha()
    result.prompt_version = TAG_SITE_PROMPT_VERSION
    result.model = SONNET_MODEL
    result.generated_at = datetime.now(UTC).isoformat()
    return rank_sites(result)


def to_viewer_sites(result: TagSiteResult, *, uniprot_acc: str) -> list[dict[str, Any]]:
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
            # Preprint / DOI-only citation with a quote but no PMID.
            sources.append({"citation": "preprint", "claim": s.supporting_quote})

        site_id = f"{result.gene_symbol}-{s.site_type}-{s.insert_after_residue}-lit"
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
            "provenance": "literature_retrieved",
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
            "rationale": (
                f"{s.rationale} "
                # evidence_detail is where the prompt sends the assay, the result
                # and any confound, and cited_tag_residue is what makes an
                # "inferred" position honest by naming where the real tag sits.
                # Both were collected every run and read by nothing.
                + (f"{s.evidence_detail} " if s.evidence_detail else "")
                + f"[validation: {s.validation_level}; "
                f"position: {s.position_evidence}; source: {s.source_tier}; "
                + (f"cited_tag_residue: {s.cited_tag_residue}; "
                   if s.position_evidence == "inferred" and s.cited_tag_residue is not None
                   else "")
                + f"entailment_verified: {s.entailment_verified}"
                # Only stated when true, so an untouched record reads exactly
                # as it did before this gate existed.
                + ("; position_repaired: true" if s.position_repaired else "")
                + ("" if s.quote_probative else "; quote_describes_no_insertion: true")
                + "]"
            ),
            "sources": sources,
            "plddt": None,
            "conservation_rank": None,
            "median_conservation": None,
        }
        by_id[site_id] = record
        out.append(record)
    return out
