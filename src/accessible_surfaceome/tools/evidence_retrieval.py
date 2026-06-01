"""``evidence_retrieval`` — per-category, retrieval-grounded surface evidence.

The deep-dive agent's job is to anchor every load-bearing surface call to a
verbatim quote from a paper or database it actually fetched. ``gene_literature``
gives the agent bibliographic access; this tool drives the agent to specific
*assay-category* evidence with pre-extracted candidate quotes.

One call → one (uniprot_acc, category) pair → a small set of papers + the
≤600-char sentences from those papers where the category's hallmark phrases
appear (cap is ``_QUOTE_MAX_CHARS``; bumped from 200 → 600 after the EGFR
audit showed mid-clause truncation on long methodology sentences). The
agent then picks one of the candidate snippets verbatim, pastes it into
``EvidenceClaim.quote``, and the orchestrator's substring check passes by
construction (the snippet was extracted from the cached source body the
substring check normalizes against).

Categories
----------

``ihc``, ``if``, ``flow_cytometry``, ``surface_biotinylation``,
``mass_spec_surfaceome``, ``western_blot_paired``, ``structure_with_ecd``,
``other``.

* ``ihc`` covers all immunohistochemistry, including HPA antibody panels
  and stand-alone IHC literature. HPA's per-tissue reliability call is
  already exposed deterministically via the ``db_panel`` HPA SourceVote;
  ``ihc`` retrieves the broader literature that cites or extends HPA.
* ``if`` covers immunofluorescence in two shapes: non-permeabilized IF
  (only surface epitopes visible) AND permeabilized confocal IF with
  explicit PM-marker colocalization (Na+/K+-ATPase, E-cadherin,
  β1-integrin, pan-cadherin, ZO-1, GM1) — the colocalization is what
  distinguishes "surface" from "generic membranous".
* ``other`` is a catch-all for surface evidence that doesn't fit the
  methodology-specific buckets — pharmacology / radioligand binding /
  BRET for receptor classes, shedding / soluble-form detection,
  proximity labeling (APEX2 / TurboID / BioID), live-cell tomography,
  functional surface assays. Used heavily for tm=7 GPCRs (where the
  bulk of the literature is pharmacology) and shedding-prone
  type-I membrane proteins.

Why a separate tool from ``gene_literature``: the contract is different
(retrieval + extraction, not just bibliography). Keeping the per-category
hallmark-phrase + section-weighting logic out of ``gene_literature`` keeps
that module's four-mode cascade narrow and lets the evidence-retrieval
heuristics evolve independently.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import get_args

from ._shared.europepmc import (
    SectionName,
    europepmc_bulk_by_pmid,
    europepmc_search,
    fetch_fulltext,
    paper_from_europepmc,
)
from ._shared.gene_gazetteer import (
    build_target_names,
    extract_symbol_tokens,
    load_gazetteer,
    sentence_subject,
)
from ._shared.http import CachedHTTP, open_default_client
from ._shared.models import (
    CandidateSnippet,
    EvidenceCategory,
    EvidenceClaimDraft,
    EvidenceRetrievalPack,
    IdentifierBundle,
    Paper,
    PaperSection,
    PaperSection_,
)
from ._shared.pubtator import build_gene_entity_query, pubtator_search
from ._shared.retraction_watch import RetractionIndex, empty as _empty_retraction_index
from .gene_lookup import resolve as _resolve

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Category catalogue
# ---------------------------------------------------------------------------


# Section weights map PaperSection.name → relative score. Antibody-based
# categories prioritize figure legends + methods (where the surface
# readout's identity lives); mass spec prioritizes methods + results;
# structure prioritizes results + figure legends (where the binding mode
# is described).
_DEFAULT_ANTIBODY_WEIGHTS: dict[SectionName, float] = {
    "figure_legends": 3.0,
    "methods": 2.0,
    "results": 1.5,
    "discussion": 0.5,
    "intro": 0.25,
}
_DEFAULT_MS_WEIGHTS: dict[SectionName, float] = {
    "methods": 3.0,
    "results": 2.0,
    "figure_legends": 1.0,
    "discussion": 0.5,
    "intro": 0.25,
}
_DEFAULT_BIOTIN_WEIGHTS: dict[SectionName, float] = {
    "methods": 3.0,
    "results": 2.0,
    "figure_legends": 1.5,
    "discussion": 0.5,
    "intro": 0.25,
}
_DEFAULT_STRUCT_WEIGHTS: dict[SectionName, float] = {
    "results": 3.0,
    "figure_legends": 2.0,
    "methods": 1.0,
    "discussion": 0.5,
    "intro": 0.25,
}


# Map JATS section names (PaperSection.name) → the model's PaperSection_
# enum used on EvidenceClaim / EvidenceSpan. The two enums diverge in two
# places: ``intro`` → ``introduction``, ``figure_legends`` → ``figure_legend``.
_SECTION_TO_CLAIM: dict[SectionName, PaperSection_] = {
    "intro": "introduction",
    "methods": "methods",
    "results": "results",
    "discussion": "discussion",
    "figure_legends": "figure_legend",
}


@dataclass(frozen=True)
class _CategorySpec:
    """Internal config for one EvidenceCategory.

    ``query_clauses`` are AND'd together with the gene-name disjunction
    for the Europe PMC keyword query; ``pubtator_terms`` is the
    free-text tail of the PubTator entity-anchored query (the gene is
    supplied separately as ``@GENE_<symbol>``); ``hallmark_patterns``
    are run sentence-by-sentence over fetched full text;
    ``section_weights`` decide which section's hits float to the top.

    ``accepts_paper_level_evidence`` widens the gene-proximity filter
    for high-throughput methods (``mass_spec_surfaceome``,
    ``surface_biotinylation``, ``western_blot_paired``). In those
    methodologies the methods sentence describes the *experiment*
    generically (e.g. "Cells were biotinylated with sulfo-NHS-SS-biotin")
    and the target gene appears only in a supplementary table or a
    different sentence — never as the subject of the methods sentence.
    With this flag set, the filter treats a competing-gene-only
    sentence as acceptable as long as the *target gene also appears
    somewhere in the same section*; the strict filter still drops
    sentences from sections that don't mention the target at all
    (which is the case for surfaceome papers where the target is
    truly absent from the protein list).
    """

    query_clauses: tuple[str, ...]
    pubtator_terms: str
    hallmark_patterns: tuple[re.Pattern[str], ...]
    section_weights: Mapping[SectionName, float]
    accepts_paper_level_evidence: bool = False


# Per-category retrieval config. Query clauses are joined with AND to
# narrow Europe PMC's recall to papers that are likely to have a
# load-bearing sentence on this category; hallmark patterns are run
# over the *full text* of those papers to pull the actual sentence.
_CATEGORY_SPECS: dict[EvidenceCategory, _CategorySpec] = {
    "ihc": _CategorySpec(
        query_clauses=(
            '("immunohistochemistry" OR "IHC")',
            '("surface" OR "plasma membrane" OR "membranous staining" OR "cell membrane")',
        ),
        pubtator_terms="immunohistochemistry",
        hallmark_patterns=(
            re.compile(
                r"(membranous|plasma\s*membran(?:e|ous)|cell\s*surface|surface)\s+"
                r"(staining|expression|localizat|immunoreactiv|signal|positive|labeling)",
                re.IGNORECASE,
            ),
            re.compile(r"\bIHC\b.*\b(surface|membrane|membranous)\b", re.IGNORECASE),
        ),
        section_weights=_DEFAULT_ANTIBODY_WEIGHTS,
    ),
    "if": _CategorySpec(
        query_clauses=(
            '("immunofluorescence" OR "confocal" OR "live-cell imaging" '
            'OR "IF microscopy")',
            '("non-permeabilized" OR "non permeabilized" OR "unpermeabilized" '
            'OR "live cells" OR "intact cells" OR "surface staining" '
            'OR "Na/K-ATPase" OR "Na+/K+-ATPase" OR "Na,K-ATPase" '
            'OR "E-cadherin" OR "β1-integrin" OR "beta-1 integrin" '
            'OR "pan-cadherin" OR "ZO-1" OR "GM1" '
            'OR "membrane colocalization" OR "plasma membrane marker")',
        ),
        pubtator_terms="immunofluorescence",
        hallmark_patterns=(
            # Non-permeabilized IF — surface epitopes only.
            re.compile(
                r"(non[-\s]?permeabili[sz]ed|unpermeabili[sz]ed|intact|live)\s+(cells|t\s*cells|"
                r"lymphocytes|leukocytes|tumou?r\s*cells)",
                re.IGNORECASE,
            ),
            re.compile(
                r"surface\s+(staining|expression|labeling|fluorescen|signal)",
                re.IGNORECASE,
            ),
            # Permeabilized confocal IF with PM-marker colocalization.
            re.compile(
                r"(colocali[sz]|co[-\s]?localizat|merge[ds]?\s+with|co[-\s]?staining\s+with)"
                r"[^.]{0,150}?(Na\+?[/,]?K\+?[-\s]?ATPase|"
                r"E[-\s]?cadherin|β1[-\s]?integrin|beta[-\s]?1[-\s]?integrin|"
                r"pan[-\s]?cadherin|ZO[-\s]?1|GM1\s+ganglioside|"
                r"plasma\s+membrane\s+marker|cell[-\s]?surface\s+marker)",
                re.IGNORECASE,
            ),
            re.compile(
                r"(Na\+?[/,]?K\+?[-\s]?ATPase|E[-\s]?cadherin|β1[-\s]?integrin|"
                r"beta[-\s]?1[-\s]?integrin|pan[-\s]?cadherin|ZO[-\s]?1)"
                r"[^.]{0,150}?(colocali[sz]|co[-\s]?localizat|merge[ds]?|co[-\s]?staining)",
                re.IGNORECASE,
            ),
        ),
        section_weights=_DEFAULT_ANTIBODY_WEIGHTS,
    ),
    "flow_cytometry": _CategorySpec(
        query_clauses=(
            '("flow cytometry" OR "FACS")',
            '("surface" OR "non-permeabilized" OR "live cells" OR "intact cells")',
        ),
        pubtator_terms="flow cytometry",
        hallmark_patterns=(
            re.compile(
                r"(flow\s*cytometr|FACS)[^.]{0,200}?\b(surface|non[-\s]?permeabili[sz]ed|"
                r"intact|live|extracellular)\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\b(surface|extracellular)\b[^.]{0,80}?(flow\s*cytometr|FACS)",
                re.IGNORECASE,
            ),
        ),
        section_weights=_DEFAULT_ANTIBODY_WEIGHTS,
    ),
    "surface_biotinylation": _CategorySpec(
        query_clauses=(
            '("surface biotinylation" OR "cell surface biotinylation" '
            'OR "biotin labeling" OR "biotinyl" OR "sulfo-NHS-biotin")',
            '("plasma membrane" OR "cell surface" OR "streptavidin")',
        ),
        pubtator_terms="surface biotinylation",
        hallmark_patterns=(
            re.compile(
                r"(sulfo[-\s]?NHS[-\s]?biotin|sulfo[-\s]?NHS[-\s]?SS[-\s]?biotin|"
                r"surface\s*biotinylat|cell\s*surface\s*biotinylat|biotin\s*label)",
                re.IGNORECASE,
            ),
            re.compile(
                r"streptavidin\s+(pull[-\s]?down|enrichment|capture|bead)",
                re.IGNORECASE,
            ),
        ),
        section_weights=_DEFAULT_BIOTIN_WEIGHTS,
        accepts_paper_level_evidence=True,
    ),
    "mass_spec_surfaceome": _CategorySpec(
        query_clauses=(
            '("surfaceome" OR "surface proteome" OR "cell surface proteomics" '
            'OR "cell-surface capture")',
            '("LC-MS/MS" OR "LC-MS" OR "mass spectrometry" OR "proteomic" OR "proteomics")',
        ),
        pubtator_terms="surfaceome mass spectrometry",
        hallmark_patterns=(
            re.compile(
                r"(LC[-\s]?MS/?MS?|mass\s*spectrometr|cell[-\s]?surface\s*capture|CSC|"
                r"surfaceome|surface\s*proteom)",
                re.IGNORECASE,
            ),
            re.compile(
                r"(periodate|sialic[-\s]?acid|hydrazide|biocytin\s*hydrazide).*?"
                r"(biotin|enrichment|capture|labeling)",
                re.IGNORECASE,
            ),
        ),
        section_weights=_DEFAULT_MS_WEIGHTS,
        accepts_paper_level_evidence=True,
    ),
    "western_blot_paired": _CategorySpec(
        query_clauses=(
            '("western blot" OR "immunoblot")',
            '("surface biotinylation" OR "cell surface biotinylation" '
            'OR "streptavidin pull" OR "streptavidin enrichment" '
            'OR "plasma membrane fraction" OR "cell surface fraction" '
            'OR "membrane preparation")',
        ),
        pubtator_terms="surface biotinylation western blot",
        hallmark_patterns=(
            re.compile(
                r"(western\s*blot|immunoblot)[^.]{0,200}?(surface|"
                r"plasma\s*membrane\s*fraction|biotinylat|streptavidin)",
                re.IGNORECASE,
            ),
            re.compile(
                r"(streptavidin|biotinylat|membrane\s*fraction|"
                r"surface\s*biotinylat)[^.]{0,200}?(immunoblot|western)",
                re.IGNORECASE,
            ),
        ),
        section_weights=_DEFAULT_BIOTIN_WEIGHTS,
        accepts_paper_level_evidence=True,
    ),
    "structure_with_ecd": _CategorySpec(
        query_clauses=(
            '("crystal structure" OR "cryo-EM" OR "cryo electron microscopy" '
            'OR "X-ray structure")',
            '("ectodomain" OR "extracellular domain" OR "ECD" OR "extracellular region")',
        ),
        pubtator_terms="crystal structure ectodomain",
        hallmark_patterns=(
            re.compile(
                r"(crystal\s*structure|cryo[-\s]?EM|cryo[-\s]?electron)[^.]{0,200}?"
                r"(ectodomain|extracellular\s*(domain|region)|ECD)",
                re.IGNORECASE,
            ),
            re.compile(
                r"(ectodomain|extracellular\s*(domain|region)|ECD)[^.]{0,200}?"
                r"(crystal\s*structure|cryo[-\s]?EM|resolution|\bÅ\b|angstrom)",
                re.IGNORECASE,
            ),
        ),
        section_weights=_DEFAULT_STRUCT_WEIGHTS,
    ),
    # Catch-all bucket for surface evidence that doesn't fit the
    # methodology-specific categories above:
    #   • Pharmacology — radioligand binding, BRET, β-arrestin recruitment,
    #     agonist potency curves (the dominant evidence type for tm=7 GPCRs).
    #   • Shedding — ADAM/MMP/BACE-mediated ectodomain release, soluble
    #     form in serum / supernatant (implies prior surface presence).
    #   • Proximity labeling — APEX2 / TurboID / BioID anchored at a
    #     known surface marker, identifying neighbors.
    #   • Functional surface assays — internalization / endocytosis
    #     kinetics, live-cell tomography of the surface pool.
    "other": _CategorySpec(
        query_clauses=(
            '("cell surface" OR "plasma membrane" OR "surface expression" '
            'OR "cell-surface" OR "membrane localization")',
            '("radioligand" OR "BRET" OR "β-arrestin" OR "beta-arrestin" '
            'OR "agonist potency" OR "EC50" OR "IC50" '
            'OR "shedding" OR "ectodomain release" OR "soluble form" '
            'OR "proximity labeling" OR "proximity biotinylation" '
            'OR "APEX2" OR "TurboID" OR "BioID" '
            'OR "internalization" OR "endocytosis rate")',
        ),
        pubtator_terms="cell surface ligand binding",
        hallmark_patterns=(
            # Pharmacology / ligand binding — implies surface accessibility.
            re.compile(
                r"(radioligand|BRET|β[-\s]?arrestin|beta[-\s]?arrestin|"
                r"agonist|antagonist|cAMP|EC50|IC50|\bKi\b|\bKd\b)"
                r"[^.]{0,200}?(binding|recruitment|potency|engagement|"
                r"surface|extracellular)",
                re.IGNORECASE,
            ),
            # Shedding / soluble form — implies prior surface presence.
            re.compile(
                r"(shedding|ectodomain\s+release|sheddase|"
                r"ADAM[-\s]?17|ADAM[-\s]?10|BACE[-\s]?1|MMP[-\s]?\d+|"
                r"γ[-\s]?secretase|gamma[-\s]?secretase|soluble\s+form)",
                re.IGNORECASE,
            ),
            # Proximity labeling near the PM / extracellular face.
            re.compile(
                r"(APEX2?|TurboID|BioID|proximity\s+labeling|"
                r"proximity\s+biotinylation)[^.]{0,200}?"
                r"(surface|membrane|extracellular|plasma\s+membrane)",
                re.IGNORECASE,
            ),
            # Internalization implies the protein was at the surface first.
            re.compile(
                r"(internalization|endocytosis|recycling)\s+"
                r"(rate|kinetics|assay|half[-\s]?life)",
                re.IGNORECASE,
            ),
        ),
        section_weights=_DEFAULT_ANTIBODY_WEIGHTS,
        accepts_paper_level_evidence=True,
    ),
}


# ---------------------------------------------------------------------------
# Public dispatch
# ---------------------------------------------------------------------------


def evidence_retrieval(
    *,
    uniprot_acc: str,
    category: EvidenceCategory,
    max_papers: int = 5,
    max_snippets_per_paper: int = 3,
    http: CachedHTTP | None = None,
    retraction_index: RetractionIndex | None = None,
    discover_only: bool = False,
) -> EvidenceRetrievalPack:
    """Run a category-tuned retrieval pass for one gene.

    Resolves the symbol from ``uniprot_acc``, queries Europe PMC with a
    category-specific term set, fetches up to ``max_papers`` PMC-OA full
    texts, and extracts up to ``max_snippets_per_paper`` candidate
    quotes per paper. Returns an :class:`EvidenceRetrievalPack` carrying
    the papers, the snippets, and (when empty) an ``empty_reason`` the
    agent can pass through to ``confidence_reasoning``.

    HPA per-tissue evidence is no longer a retrieval category — the HPA
    surface vote + main_location ride on the deterministic ``db_panel``
    input instead, and broader IHC literature (including papers that
    cite or extend HPA) is covered by ``category="ihc"``.

    ``discover_only=True`` runs only the discovery half (PubTator +
    EuropePMC category search) and skips the body-fetch + hallmark-
    filtered snippet extraction. Returns papers populated, snippets
    empty. Use this when the body-fetch decision is being deferred to
    a downstream agent (e.g. abstract-triage).
    """
    if category not in get_args(EvidenceCategory):
        raise ValueError(
            f"unknown evidence_retrieval category: {category!r}; "
            f"expected one of {get_args(EvidenceCategory)!r}"
        )

    own_client = http is None
    client = http or open_default_client()
    index = retraction_index if retraction_index is not None else _empty_retraction_index()
    try:
        return _pmc_retrieval(
            uniprot_acc=uniprot_acc,
            category=category,
            max_papers=max_papers,
            max_snippets_per_paper=max_snippets_per_paper,
            http=client,
            retraction_index=index,
            discover_only=discover_only,
        )
    finally:
        if own_client:
            client.close()


# ---------------------------------------------------------------------------
# PMC retrieval path
# ---------------------------------------------------------------------------


# The gene-proximity filter can empty a top-ranked paper's snippets, so
# instead of stopping at a fixed ``max_papers`` slice we keep pulling
# deeper into the candidate pool until that many papers have actually
# *yielded* snippets. The fetch cap bounds the cost of that backfill:
# ``max(max_papers * _BACKFILL_FETCH_MULTIPLIER, _BACKFILL_MIN_FETCHES)``
# full-text fetches are attempted before we give up and report an honest
# empty result. The floor keeps small ``max_papers`` calls (e.g. a
# focused ``max_papers=1`` query) from having essentially no backfill
# room — the realistic "good paper ranked below the filtered top"
# scenario needs to look ~8 deep regardless of the target count.
_BACKFILL_FETCH_MULTIPLIER = 3
_BACKFILL_MIN_FETCHES = 8


def _pmc_retrieval(
    *,
    uniprot_acc: str,
    category: EvidenceCategory,
    max_papers: int,
    max_snippets_per_paper: int,
    http: CachedHTTP,
    retraction_index: RetractionIndex,
    discover_only: bool = False,
) -> EvidenceRetrievalPack:
    bundle = _resolve(uniprot_acc, http=http)
    spec = _CATEGORY_SPECS[category]

    # Subject-grounding dictionaries for the snippet filter: the target's
    # own safe name set (from the resolved bundle) and the HGNC gazetteer
    # of every other gene symbol. ``load_gazetteer`` is cached and
    # degrades to an empty set when the LFS-tracked TSV isn't hydrated.
    target_names = build_target_names(
        bundle.hgnc_symbol, bundle.aliases, bundle.previous_symbols
    )
    gazetteer = load_gazetteer()

    # Two discovery sources, unioned. PubTator is entity-anchored
    # (subject-grounded — a hit means NER tagged this gene, not that the
    # string appears somewhere) so its papers rank first; Europe PMC's
    # keyword search backfills recall. Dedup is by PMID.
    pubtator_papers = _pubtator_discovery(
        bundle=bundle,
        spec=spec,
        max_papers=max_papers,
        http=http,
        retraction_index=retraction_index,
    )
    epmc_papers = _europepmc_discovery(
        bundle=bundle,
        spec=spec,
        max_papers=max_papers,
        http=http,
        retraction_index=retraction_index,
    )
    papers = _union_by_pmid(pubtator_papers, epmc_papers)

    # Full PMC-OA, non-retracted candidate pool, ranked PubTator-first
    # via the union order. We walk this pool fetching + extracting; the
    # gene-proximity filter inside _extract_snippets can leave a
    # top-ranked paper with zero on-subject snippets, so we keep going
    # rather than stopping at a fixed slice.
    candidate_pool = [
        p for p in papers
        if p.is_pmc_oa and p.pmc_id and not p.is_retracted
    ]

    if not candidate_pool:
        return EvidenceRetrievalPack(
            uniprot_acc=uniprot_acc,
            category=category,
            n_papers_searched=len(papers),
            n_papers_with_snippets=0,
            papers=papers[:max_papers],
            snippets=[],
            empty_reason=(
                "no PMC-OA full-text hits for this category — try "
                "gene_literature topic_search for abstract-only signal"
            ),
        )

    if discover_only:
        # Body-fetch + hallmark-filtered extraction is deferred to the
        # downstream triage path. Return the discovered candidate pool
        # so the orchestrator can merge it into the unified inventory.
        return EvidenceRetrievalPack(
            uniprot_acc=uniprot_acc,
            category=category,
            n_papers_searched=len(papers),
            n_papers_with_snippets=0,
            papers=candidate_pool,
            snippets=[],
            empty_reason=None,
        )

    # Backfill loop: keep fetching + extracting until ``max_papers``
    # papers have *yielded* snippets, the candidate pool is exhausted,
    # or the fetch cap is hit. ``snippet_papers`` holds only the papers
    # that contributed — papers fetched but filtered empty are not
    # returned (the agent can't cite them, and their full text would be
    # dead weight in the tool result).
    fetch_cap = max(
        max_papers * _BACKFILL_FETCH_MULTIPLIER, _BACKFILL_MIN_FETCHES
    )
    snippet_papers: list[Paper] = []
    all_snippets: list[CandidateSnippet] = []
    n_fetch_attempts = 0
    for paper in candidate_pool:
        if len(snippet_papers) >= max_papers or n_fetch_attempts >= fetch_cap:
            break
        n_fetch_attempts += 1
        try:
            full = fetch_fulltext(
                http=http, pmcid=paper.pmc_id or "", retraction_index=retraction_index
            )
        except (LookupError, ValueError) as exc:
            logger.warning("fetch_fulltext failed for %s: %s", paper.pmc_id, exc)
            continue
        per_paper = _extract_snippets(
            paper=full,
            spec=spec,
            max_snippets=max_snippets_per_paper,
            target_names=target_names,
            gazetteer=gazetteer,
        )
        # For high-throughput categories, additionally pull verbatim
        # target-naming sentences from the paper body. These give the
        # agent a ready-to-quote paper-level attribution that pairs
        # with the methodology snippet for a complete "Paper performed
        # X AND identified target" citation. Dedup against hallmark
        # snippets so a target-naming sentence that ALSO matched a
        # hallmark pattern (e.g. "CD81 was detected by Western blot")
        # is only emitted once.
        already_emitted = {s.text for s in per_paper}
        target_mentions = [
            tm for tm in _extract_target_mentions(
                full, spec=spec, target_names=target_names,
            ) if tm.text not in already_emitted
        ]
        if per_paper or target_mentions:
            # Pin the target-mention excerpts on the paper itself so the
            # agent can find them via the Paper record even if the
            # snippet ranking pushes some out of the top-N.
            full_with_mentions = full.model_copy(
                update={"target_mention_excerpts": [s.text for s in target_mentions]}
            ) if target_mentions else full
            snippet_papers.append(full_with_mentions)
            all_snippets.extend(per_paper)
            all_snippets.extend(target_mentions)

    # Sort across papers by score (descending) so the agent sees the
    # strongest matches first.
    all_snippets.sort(key=lambda s: s.score, reverse=True)

    # Convert every snippet into a pre-built EvidenceClaimDraft so the
    # agent doesn't have to re-type (quote, source_id, section) into a
    # new claim — the (quote, source_id) pair the orchestrator
    # substring-checks at promotion is locked together by construction.
    claim_drafts = [
        _snippet_to_draft(snippet, seq=i + 1)
        for i, snippet in enumerate(all_snippets)
    ]

    empty_reason: str | None = None
    if not all_snippets:
        empty_reason = (
            f"fetched {n_fetch_attempts} of {len(candidate_pool)} PMC-OA candidate "
            "papers; none yielded an on-subject hallmark match — the literature "
            "may lack this category, or the full text uses non-standard phrasing"
        )

    return EvidenceRetrievalPack(
        uniprot_acc=uniprot_acc,
        category=category,
        n_papers_searched=len(papers),
        n_papers_with_snippets=len(snippet_papers),
        papers=snippet_papers,
        snippets=all_snippets,
        evidence_claim_drafts=claim_drafts,
        empty_reason=empty_reason,
    )


# ---------------------------------------------------------------------------
# Discovery sources
# ---------------------------------------------------------------------------


def _europepmc_discovery(
    *,
    bundle: IdentifierBundle,
    spec: _CategorySpec,
    max_papers: int,
    http: CachedHTTP,
    retraction_index: RetractionIndex,
) -> list[Paper]:
    """Keyword discovery: gene-name disjunction AND category clauses.

    High recall, no subject grounding — a paper matches if the gene's
    name (or an alias) appears anywhere the index covers. PubTator's
    entity-anchored results are preferred over these; this backfills
    recall for papers PubTator's NER missed.
    """
    name_terms = [bundle.hgnc_symbol, *bundle.aliases]
    name_disjunction = " OR ".join(f'"{n}"' for n in name_terms if n)
    query = (
        f"({name_disjunction}) AND "
        + " AND ".join(spec.query_clauses)
        + " AND SRC:MED"
    )
    payload = europepmc_search(http=http, query=query, page_size=max_papers * 3)
    hits = (payload.get("resultList") or {}).get("result") or []
    return [
        paper_from_europepmc(record, retraction_index=retraction_index)
        for record in hits
    ]


def _pubtator_discovery(
    *,
    bundle: IdentifierBundle,
    spec: _CategorySpec,
    max_papers: int,
    http: CachedHTTP,
    retraction_index: RetractionIndex,
) -> list[Paper]:
    """Entity-anchored discovery: ``@GENE_<symbol> <category terms>``.

    A PubTator hit means its NER tagged this gene as a subject entity in
    the paper — not just that the name appears — which is the fix for
    the "method paper mentions the gene in passing" failure mode.

    PubTator returns PMIDs + metadata but no open-access status or full
    text, so the PMIDs are resolved against Europe PMC (one bulk call)
    to get the ``Paper`` shape the rest of the pipeline expects.

    Degrades gracefully: any failure on either hop logs a warning and
    returns an empty list, leaving Europe PMC keyword discovery as the
    sole source for that call.
    """
    if not spec.pubtator_terms:
        return []
    query = build_gene_entity_query(bundle.hgnc_symbol, spec.pubtator_terms)
    try:
        result = pubtator_search(http=http, query=query)
    except Exception as exc:  # noqa: BLE001 - degrade to Europe-PMC-only discovery
        logger.warning("PubTator search failed for %r: %s", query, exc)
        return []
    # PubTator pre-sorts by relevance score; take a generous slice so the
    # downstream PMC-OA filter still has candidates to work with.
    pmids = [hit.pmid for hit in result.hits[: max_papers * 2]]
    if not pmids:
        return []
    try:
        return europepmc_bulk_by_pmid(
            http=http, pmids=pmids, retraction_index=retraction_index
        )
    except Exception as exc:  # noqa: BLE001 - degrade to Europe-PMC-only discovery
        logger.warning(
            "Europe PMC bulk resolve of %d PubTator PMIDs failed: %s",
            len(pmids), exc,
        )
        return []


def _union_by_pmid(*paper_lists: list[Paper]) -> list[Paper]:
    """Concatenate paper lists, keeping first occurrence per PMID.

    Order is preserved: papers from earlier lists win, so callers pass
    the higher-precision source (PubTator) first.
    """
    seen: set[int] = set()
    out: list[Paper] = []
    for papers in paper_lists:
        for paper in papers:
            if paper.pmid in seen:
                continue
            seen.add(paper.pmid)
            out.append(paper)
    return out


# ---------------------------------------------------------------------------
# Snippet extraction
# ---------------------------------------------------------------------------


# A sentence-ish splitter. Doesn't try to be perfect — surface biology
# papers use plenty of "Fig. 3A" and "i.e." that throw off naive
# splitters, so we keep a lenient pattern and let the cap do
# the trimming.
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z(])")

# Score bump for a sentence that names the target gene, so on-subject
# snippets outrank anaphoric ones ("the protein was detected...").
_TARGET_MENTION_BOOST = 2.0

# For the high-throughput categories, a sentence that names the target
# but doesn't fire a methodology hallmark is still load-bearing — it is
# the paper-level attribution that ties the methodology (described in a
# different sentence) to this specific gene. We emit those as separate
# CandidateSnippets with this synthetic hallmark_phrase so the agent
# (and audit code) can tell them apart from regex-matched ones.
TARGET_MENTION_HALLMARK = "target_mention"

# Max target-mention snippets emitted per paper. Keeps the snippet
# budget bounded while ensuring at least one target-attribution
# excerpt makes it through alongside the methodology snippets.
_MAX_TARGET_MENTIONS_PER_PAPER = 3

# Verbatim-quote cap for ``CandidateSnippet.text``. Substring-anchored
# into ``SourceTextStore`` at promotion; bumped from 200 → 600 to fit
# up to ~3 sentences of context (EGFR audit, 2026-05-15: 10/37 quotes
# were truncated mid-clause at the old 199-char ceiling). Schema-side
# cap is in ``models.CandidateSnippet.text`` / ``EvidenceClaim.quote``;
# this constant is the snippet extractor's pre-cap target so the schema
# never has to refuse a tool-emitted snippet.
_QUOTE_MAX_CHARS = 600

# Context-excerpt cap. ``CandidateSnippet.text`` is the substring
# anchor; ``context_excerpt`` carries broader surrounding text
# (≤1500 chars) so the agent can READ the snippet in situ. High-
# throughput methodology routinely spans multiple sentences ("Cells
# were biotinylated. Eluted proteins were analyzed by LC-MS/MS")
# and the focal-sentence-only quote is insufficient context without it.
_CONTEXT_EXCERPT_MAX_CHARS = 1500


def _adjacent_context(
    section_text: str,
    focal_sentence: str,
    *,
    max_chars: int = _CONTEXT_EXCERPT_MAX_CHARS,
) -> str | None:
    """Return up to ``max_chars`` of section text around ``focal_sentence``.

    Picks the focal sentence + at most one sentence on each side, joined
    with single spaces. Returns ``None`` when the focal sentence stands
    alone in its section (no extra context to add) or when the lookup
    can't locate it among the split sentences (punctuation-edge cases).

    The window is verbatim from ``section_text`` — if downstream code
    wants to register it as a quote-anchorable excerpt it can; the
    primary use is the agent's understanding of multi-sentence
    methodology context.
    """
    sentences = _split_sentences(section_text)
    try:
        idx = sentences.index(focal_sentence)
    except ValueError:
        return None
    start = max(0, idx - 1)
    end = min(len(sentences), idx + 2)
    chosen = sentences[start:end]
    if len(chosen) <= 1:
        return None  # focal sentence is alone — no useful surrounding context
    window = " ".join(chosen)
    if len(window) <= max_chars:
        return window
    # Window too long: try dropping the further-out sentence first to
    # keep focal + one adjacent.
    if start < idx:
        narrowed = " ".join(sentences[idx:end])
        if len(narrowed) <= max_chars:
            return narrowed
    if end > idx + 1:
        narrowed = " ".join(sentences[start:idx + 1])
        if len(narrowed) <= max_chars:
            return narrowed
    return None  # even minimal context overflows — give up rather than truncate mid-sentence


def _extract_snippets(
    *,
    paper: Paper,
    spec: _CategorySpec,
    max_snippets: int,
    target_names: frozenset[str] = frozenset(),
    gazetteer: frozenset[str] = frozenset(),
) -> list[CandidateSnippet]:
    """Pull up to ``max_snippets`` candidate sentences from ``paper.sections``.

    Per-section: split into sentences, score each by section weight ×
    hallmark-match count, keep the top sentences (capped at
    ``_QUOTE_MAX_CHARS``). Deduplicate against already-emitted snippets
    from the same paper.

    ``target_names`` + ``gazetteer`` drive the subject-grounding filter
    (see :func:`accessible_surfaceome.tools._shared.gene_gazetteer.sentence_subject`):
    a sentence about a *competing* gene — a sibling target on a
    multi-target paper — is dropped, and a sentence that names the
    target is score-boosted. Both default empty, in which case the
    filter is a no-op and extraction behaves as it did pre-filter.
    """
    if not paper.sections or not spec.hallmark_patterns:
        return []
    source_id = f"PMC:{paper.pmc_id}" if paper.pmc_id else f"PMID:{paper.pmid}"
    candidates: list[tuple[float, CandidateSnippet]] = []
    for section in paper.sections:
        weight = spec.section_weights.get(section.name, 0.5)
        if weight <= 0:
            continue
        section_enum = _SECTION_TO_CLAIM.get(section.name, "other")
        # Per-section paper-level relaxation. High-throughput methods
        # describe the experiment generically and only name the target in
        # a different sentence (or supplementary table). When the target
        # appears anywhere in this section's text we keep "competing"
        # sentences too — they're describing the same experiment.
        section_mentions_target = bool(target_names) and any(
            tok in target_names for tok in extract_symbol_tokens(section.text)
        )
        for sentence in _split_sentences(section.text):
            # Subject-grounding: drop sentences about a sibling gene,
            # boost sentences that name the target. Computed once per
            # sentence, before the (pattern-independent) hallmark loop.
            subject = sentence_subject(
                sentence, target_names=target_names, gazetteer=gazetteer
            )
            if subject == "competing" and not (
                spec.accepts_paper_level_evidence and section_mentions_target
            ):
                continue
            for pattern in spec.hallmark_patterns:
                match = pattern.search(sentence)
                if not match:
                    continue
                snippet_text = _trim_to_quote_cap(sentence, match)
                if not snippet_text:
                    continue
                # Confirm the trimmed snippet is a substring of the
                # source body — otherwise the orchestrator's substring
                # check (which runs against the same body) would reject
                # a claim made from this snippet.
                if snippet_text not in section.text:
                    continue
                score = weight + min(2.0, _count_hallmarks(sentence, spec.hallmark_patterns))
                if subject == "target":
                    score += _TARGET_MENTION_BOOST
                candidates.append(
                    (
                        score,
                        CandidateSnippet(
                            source_id=source_id,
                            section=section_enum,
                            figure_or_table_id=None,
                            text=snippet_text,
                            score=score,
                            hallmark_phrase=match.group(0)[:80],
                            context_excerpt=_adjacent_context(section.text, sentence),
                        ),
                    )
                )
                break  # one pattern match per sentence is enough
    candidates.sort(key=lambda pair: pair[0], reverse=True)

    seen: set[str] = set()
    chosen: list[CandidateSnippet] = []
    for _, snippet in candidates:
        # Dedup on normalized text — full-snippet overlap (under the
        # quote cap) is enough to consider the same snippet under
        # different patterns.
        key = re.sub(r"\s+", " ", snippet.text.lower()).strip()
        if key in seen:
            continue
        seen.add(key)
        chosen.append(snippet)
        if len(chosen) >= max_snippets:
            break
    return chosen


def _extract_target_mentions(
    paper: Paper,
    *,
    spec: _CategorySpec,
    target_names: frozenset[str],
    max_mentions: int = _MAX_TARGET_MENTIONS_PER_PAPER,
) -> list[CandidateSnippet]:
    """Emit verbatim ≤``_QUOTE_MAX_CHARS`` sentences where the target gene is named.

    Only fires for ``spec.accepts_paper_level_evidence=True`` categories
    (high-throughput methods) — for antibody assays the existing
    hallmark + target-boost path already covers target-naming sentences.
    The score puts target-mention snippets between the
    hallmark-with-target snippets (which carry both methodology and gene
    in one sentence — the strongest signal) and the methodology-only
    snippets (the paper-level relaxation), so a tier-ranked agent picks
    a target-mention when one is available.

    Sentences over the cap are trimmed around the first target token;
    the trimmed text must still substring-match the source body or the
    snippet is dropped (substring-anchoring guarantee).
    """
    if not spec.accepts_paper_level_evidence or not target_names or not paper.sections:
        return []
    emitted: list[tuple[float, CandidateSnippet]] = []
    seen_norm: set[str] = set()
    source_id = f"PMC:{paper.pmc_id}" if paper.pmc_id else f"PMID:{paper.pmid}"
    for section in paper.sections:
        weight = spec.section_weights.get(section.name, 0.5)
        if weight <= 0:
            continue
        section_enum = _SECTION_TO_CLAIM.get(section.name, "other")
        for sentence in _split_sentences(section.text):
            tokens = extract_symbol_tokens(sentence)
            target_hits = [t for t in tokens if t in target_names]
            if not target_hits:
                continue
            snippet_text = _trim_to_target(sentence, target_hits[0])
            if not snippet_text or snippet_text not in section.text:
                continue
            key = re.sub(r"\s+", " ", snippet_text.lower()).strip()
            if key in seen_norm:
                continue
            seen_norm.add(key)
            # Target-mention scoring: section weight + the existing
            # target boost. A target-named sentence in methods scores
            # weight 3 + boost 2 = 5; in results, 2 + 2 = 4. A
            # hallmark+target sentence still wins (it adds hallmark
            # match credit on top).
            score = weight + _TARGET_MENTION_BOOST
            emitted.append((
                score,
                CandidateSnippet(
                    source_id=source_id,
                    section=section_enum,
                    figure_or_table_id=None,
                    text=snippet_text,
                    score=score,
                    hallmark_phrase=TARGET_MENTION_HALLMARK,
                    context_excerpt=_adjacent_context(section.text, sentence),
                ),
            ))
    emitted.sort(key=lambda pair: pair[0], reverse=True)
    return [snippet for _, snippet in emitted[:max_mentions]]


def _trim_to_target(sentence: str, target_token: str) -> str:
    """Trim a sentence to ``_QUOTE_MAX_CHARS``, biased to keep the target
    token in view. Snaps window edges to the nearest clause boundary so
    the snippet doesn't start or end mid-clause.
    """
    sentence = sentence.strip()
    if len(sentence) <= _QUOTE_MAX_CHARS:
        return sentence
    idx = sentence.find(target_token)
    if idx < 0:
        # Token might be a normalized form (hyphens dropped); fall back to first cap chars.
        return sentence[:_QUOTE_MAX_CHARS].rstrip()
    pad = max(0, (_QUOTE_MAX_CHARS - len(target_token)) // 2)
    start = max(0, idx - pad)
    end = min(len(sentence), start + _QUOTE_MAX_CHARS)
    start = max(0, end - _QUOTE_MAX_CHARS)
    snippet = sentence[start:end]
    if start > 0:
        snippet = _snap_left_to_clause(snippet)
    if end < len(sentence):
        snippet = _snap_right_to_clause(snippet)
    return snippet.strip()


# ---------------------------------------------------------------------------
# Paper-level draft extraction (used by gene_literature.fetch_abstract /
# fetch_fulltext to give the agent verbatim-anchored EvidenceClaimDraft
# skeletons even when the call didn't go through evidence_retrieval).
#
# Motivation: the GPR75 audit (2026-05-15) showed that 6/6 unanchored rows
# came from A2 paraphrasing quotes off papers fetched via gene_literature
# rather than via evidence_retrieval. evidence_retrieval pre-builds
# (quote, source_id)-locked drafts; gene_literature did not. With the same
# pre-extraction pattern here, the agent can't paraphrase what it never
# types — substring anchoring passes by construction.
# ---------------------------------------------------------------------------


# Max drafts per paper, summed across abstract + sections. 30 is enough
# to surface the load-bearing sentences from a typical 8-section
# full-text paper (≈4/section) without blowing up the agent's tool-
# result payload. For an abstract-only fetch this is effectively a
# no-op cap (abstracts rarely have >12 sentences).
_MAX_DRAFTS_PER_PAPER = 30
# Per-section sentence cap inside the per-paper budget. Keeps long
# results / discussion sections from monopolizing the draft list and
# starving the abstract / methods quotes.
_MAX_DRAFTS_PER_SECTION = 8


def extract_paper_drafts(
    *,
    source_id: str,
    abstract: str | None,
    sections: list[PaperSection],
    max_drafts: int = _MAX_DRAFTS_PER_PAPER,
) -> list[EvidenceClaimDraft]:
    """Pre-extract verbatim-anchored EvidenceClaimDraft skeletons from a
    Europe-PMC-style paper's abstract + (optionally) full-text sections.

    Strategy: split each available body into sentences, trim any sentence
    that exceeds ``_QUOTE_MAX_CHARS`` to a clause-snapped substring, and
    emit one draft per sentence that substring-matches its source text.
    No hallmark filter — the agent fetched this paper because they
    already think it's topical, so we hand over every sentence as a
    quotable anchor and let the agent pick. Per-section and per-paper
    caps keep the payload bounded.

    The substring check (``snippet_text not in body``) guarantees that
    every emitted draft will satisfy the orchestrator's promotion-time
    substring anchor by construction — same invariant
    ``_extract_snippets`` provides for the category-bounded path.

    ``sections`` is the same ``list[PaperSection]`` carried on ``Paper``;
    we map each section's ``name`` to the ``PaperSection_`` enum used by
    EvidenceClaim via ``_SECTION_TO_CLAIM`` (unknown names → "other").
    """

    drafts: list[EvidenceClaimDraft] = []
    seq = 0
    bare = source_id.split(":", 1)[-1] if ":" in source_id else source_id

    body_iter: list[tuple[PaperSection_, str]] = []
    if abstract and abstract.strip():
        body_iter.append(("abstract", abstract))
    for sec in sections:
        body_iter.append((_SECTION_TO_CLAIM.get(sec.name, "other"), sec.text))

    for section_enum, text in body_iter:
        if not text or not text.strip():
            continue
        per_section = 0
        # Score by position: earlier sentences score higher. Uniform
        # base so the agent's tier-ranking logic stays compatible with
        # evidence_retrieval-emitted drafts (which use weight + match
        # count); paper-level drafts sit below the methodology snippets
        # by design.
        n_sentences = max(1, len(_split_sentences(text)))
        for pos, sentence in enumerate(_split_sentences(text)):
            if len(drafts) >= max_drafts or per_section >= _MAX_DRAFTS_PER_SECTION:
                break
            quote = sentence.strip()
            if len(quote) > _QUOTE_MAX_CHARS:
                # Sentence is over the cap — center the trim on the
                # first long-enough alphanumeric stretch as a stand-in
                # for "where the content is."
                m = re.search(r"\w{5,}", quote)
                if m is None:
                    continue
                quote = _trim_to_quote_cap(quote, m)
            if not quote or quote not in text:
                continue
            position_score = 1.0 + (n_sentences - pos) / n_sentences  # 1..2
            seq += 1
            per_section += 1
            drafts.append(
                EvidenceClaimDraft(
                    suggested_evidence_id=f"draft_{bare}_{section_enum}_{seq:02d}",
                    quote=quote,
                    source_id=source_id,
                    section=section_enum,
                    figure_or_table_id=None,
                    context_excerpt=None,
                    hallmark_phrase="paper_level",
                    score=position_score,
                )
            )
    return drafts


def _snippet_to_draft(snippet: CandidateSnippet, *, seq: int) -> EvidenceClaimDraft:
    """Convert a ``CandidateSnippet`` into a pre-filled EvidenceClaim skeleton.

    The agent extends the draft into a full :class:`EvidenceClaim` by
    adding the narrative + classification fields; the load-bearing
    anchor fields (``quote``, ``source_id``, ``section``,
    ``figure_or_table_id``) are copied from the snippet verbatim so the
    substring check at promotion passes by construction.
    """
    # source_id like "PMC:PMC10898066" or "PMID:38414005"; strip the
    # prefix for the suggested handle, fall back to the raw value.
    bare = snippet.source_id.split(":", 1)[-1] if ":" in snippet.source_id else snippet.source_id
    return EvidenceClaimDraft(
        suggested_evidence_id=f"draft_{bare}_{snippet.section}_{seq:02d}",
        quote=snippet.text,
        source_id=snippet.source_id,
        section=snippet.section,
        figure_or_table_id=snippet.figure_or_table_id,
        context_excerpt=snippet.context_excerpt,
        hallmark_phrase=snippet.hallmark_phrase,
        score=snippet.score,
    )


def _split_sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_SPLIT.split(text) if s.strip()]


def _count_hallmarks(sentence: str, patterns: tuple[re.Pattern[str], ...]) -> int:
    return sum(1 for p in patterns if p.search(sentence))


def _trim_to_quote_cap(sentence: str, match: re.Match[str]) -> str:
    """Return up to ``_QUOTE_MAX_CHARS`` characters centered on ``match``
    while staying within ``sentence``. Prefer the whole sentence when it
    fits; otherwise carve a window around the match, snapping the edges
    to the nearest clause boundary (sentence-end, semicolon, colon,
    comma) so the snippet doesn't start or end mid-clause.
    """
    sentence = sentence.strip()
    if len(sentence) <= _QUOTE_MAX_CHARS:
        return sentence

    start, end = match.span()
    span_len = end - start
    pad = max(0, (_QUOTE_MAX_CHARS - span_len) // 2)
    window_start = max(0, start - pad)
    window_end = min(len(sentence), window_start + _QUOTE_MAX_CHARS)
    window_start = max(0, window_end - _QUOTE_MAX_CHARS)

    snippet = sentence[window_start:window_end]
    if window_start > 0:
        snippet = _snap_left_to_clause(snippet)
    if window_end < len(sentence):
        snippet = _snap_right_to_clause(snippet)
    return snippet.strip()


# Per-separator snap budgets, ordered by preference. A sentence-end
# boundary is worth giving up the most chars for (the result reads as
# a complete thought); semicolons and colons are strong-enough clause
# breaks to be worth a similar budget; commas get a small budget so
# we don't drop a quarter of the snippet chasing one. Tuned so that
# with cap=600 the trim path (sentence > cap) typically loses <150
# chars when it fires; under cap=600 the trim path doesn't fire at
# all.
_SNAP_BUDGETS: tuple[tuple[str, int], ...] = (
    (". ", 150),
    ("! ", 150),
    ("? ", 150),
    ("; ", 150),
    (": ", 120),
    (", ", 60),
)


def _snap_left_to_clause(text: str) -> str:
    """Drop leading characters up to the nearest clause boundary, with
    per-separator budgets that prefer sentence-end snaps over comma
    snaps. Falls back to a word boundary when no clause boundary is in
    range.
    """

    for sep, budget in _SNAP_BUDGETS:
        idx = text.find(sep, 0, budget)
        if 0 <= idx < budget:
            return text[idx + len(sep) :]
    first_space = text.find(" ")
    if 0 < first_space < 40:
        return text[first_space + 1 :]
    return text


def _snap_right_to_clause(text: str) -> str:
    """Drop trailing characters back to the nearest clause boundary, with
    per-separator budgets. Sentence-end terminators are kept on the
    retained side; mid-clause separators (semicolon, colon, comma) are
    dropped so the snippet doesn't end with a dangling punctuation mark.
    """

    n = len(text)
    for sep, budget in _SNAP_BUDGETS:
        tail_start = max(0, n - budget)
        idx = text.rfind(sep, tail_start)
        if idx >= 0:
            if sep[0] in ".!?":
                return text[: idx + 1]
            return text[:idx]
    last_space = text.rfind(" ")
    if last_space > n - 40:
        return text[:last_space]
    return text


__all__ = [
    "evidence_retrieval",
]
