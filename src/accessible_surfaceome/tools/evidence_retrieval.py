"""``evidence_retrieval`` — per-category, retrieval-grounded surface evidence.

The deep-dive agent's job is to anchor every load-bearing surface call to a
verbatim quote from a paper or database it actually fetched. ``gene_literature``
gives the agent bibliographic access; this tool drives the agent to specific
*assay-category* evidence with pre-extracted candidate quotes.

One call → one (uniprot_acc, category) pair → a small set of papers + the
≤200-char sentences from those papers where the category's hallmark phrases
appear. The agent then picks one of the candidate snippets verbatim, pastes
it into ``EvidenceClaim.quote``, and the orchestrator's substring check
passes by construction (the snippet was extracted from the cached source
body the substring check normalizes against).

Categories
----------

``ihc``, ``if_intact``, ``flow_cytometry``, ``surface_biotinylation``,
``mass_spec_surfaceome``, ``western_blot_paired``, ``structure_with_ecd``,
``hpa_ihc``.

``hpa_ihc`` short-circuits HTTP and reads the cached HPA snapshot at
``data/processed/hpa/hpa_human_snapshot.tsv``. The synthetic ``HPA:<symbol>``
source body is registered with the SourceTextStore by the orchestrator's
source-registration shim, so substring validation works the same way as
for PMC quotes.

Why a separate tool from ``gene_literature``: the contract is different
(retrieval + extraction, not just bibliography). Keeping the per-category
hallmark-phrase + section-weighting logic out of ``gene_literature`` keeps
that module's four-mode cascade narrow and lets the evidence-retrieval
heuristics evolve independently.
"""

from __future__ import annotations

import csv
import logging
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal, get_args

from ._shared.europepmc import (
    SectionName,
    europepmc_search,
    fetch_fulltext,
    paper_from_europepmc,
)
from ._shared.http import CachedHTTP, open_default_client
from ._shared.models import (
    CandidateSnippet,
    EvidenceCategory,
    EvidenceRetrievalPack,
    Paper,
    PaperSection_,
    SyntheticSource,
)
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

    ``query_clauses`` are AND'd together with the gene-name disjunction;
    ``hallmark_patterns`` are run sentence-by-sentence over fetched full
    text; ``section_weights`` decide which section's hits float to the
    top.
    """

    query_clauses: tuple[str, ...]
    hallmark_patterns: tuple[re.Pattern[str], ...]
    section_weights: Mapping[SectionName, float]


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
    "if_intact": _CategorySpec(
        query_clauses=(
            '("immunofluorescence" OR "confocal" OR "live-cell imaging")',
            '("non-permeabilized" OR "non permeabilized" OR "unpermeabilized" '
            'OR "live cells" OR "intact cells" OR "surface staining")',
        ),
        hallmark_patterns=(
            re.compile(
                r"(non[-\s]?permeabili[sz]ed|unpermeabili[sz]ed|intact|live)\s+(cells|t\s*cells|"
                r"lymphocytes|leukocytes|tumou?r\s*cells)",
                re.IGNORECASE,
            ),
            re.compile(
                r"surface\s+(staining|expression|labeling|fluorescen|signal)",
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
    ),
    "mass_spec_surfaceome": _CategorySpec(
        query_clauses=(
            '("surfaceome" OR "surface proteome" OR "cell surface proteomics" '
            'OR "cell-surface capture")',
            '("LC-MS/MS" OR "LC-MS" OR "mass spectrometry" OR "proteomic" OR "proteomics")',
        ),
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
    ),
    "western_blot_paired": _CategorySpec(
        query_clauses=(
            '("western blot" OR "immunoblot")',
            '("surface biotinylation" OR "cell surface biotinylation" '
            'OR "streptavidin pull" OR "streptavidin enrichment" '
            'OR "plasma membrane fraction" OR "cell surface fraction" '
            'OR "membrane preparation")',
        ),
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
    ),
    "structure_with_ecd": _CategorySpec(
        query_clauses=(
            '("crystal structure" OR "cryo-EM" OR "cryo electron microscopy" '
            'OR "X-ray structure")',
            '("ectodomain" OR "extracellular domain" OR "ECD" OR "extracellular region")',
        ),
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
    # hpa_ihc has no Europe PMC query — it's served from the cached
    # HPA snapshot.
    "hpa_ihc": _CategorySpec(
        query_clauses=(),
        hallmark_patterns=(),
        section_weights={},
    ),
}


# ---------------------------------------------------------------------------
# HPA snapshot path
# ---------------------------------------------------------------------------


# Import lazily inside _hpa_ihc to keep module import cheap and avoid
# import-time coupling to paths.py (the path is only used for HPA queries).


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
) -> EvidenceRetrievalPack:
    """Run a category-tuned retrieval pass for one gene.

    Resolves the symbol from ``uniprot_acc``, queries Europe PMC with a
    category-specific term set, fetches up to ``max_papers`` PMC-OA full
    texts, and extracts up to ``max_snippets_per_paper`` candidate
    quotes per paper. Returns an :class:`EvidenceRetrievalPack` carrying
    the papers, the snippets, and (when empty) an ``empty_reason`` the
    agent can pass through to ``confidence_reasoning``.

    For ``category="hpa_ihc"`` no HTTP is issued — the HPA snapshot at
    ``data/processed/hpa/hpa_human_snapshot.tsv`` is read directly and
    a synthetic ``HPA:<symbol>`` source is emitted.
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
        if category == "hpa_ihc":
            return _hpa_ihc(uniprot_acc=uniprot_acc, http=client)
        return _pmc_retrieval(
            uniprot_acc=uniprot_acc,
            category=category,
            max_papers=max_papers,
            max_snippets_per_paper=max_snippets_per_paper,
            http=client,
            retraction_index=index,
        )
    finally:
        if own_client:
            client.close()


# ---------------------------------------------------------------------------
# PMC retrieval path (everything except hpa_ihc)
# ---------------------------------------------------------------------------


def _pmc_retrieval(
    *,
    uniprot_acc: str,
    category: EvidenceCategory,
    max_papers: int,
    max_snippets_per_paper: int,
    http: CachedHTTP,
    retraction_index: RetractionIndex,
) -> EvidenceRetrievalPack:
    bundle = _resolve(uniprot_acc, http=http)
    name_terms = [bundle.hgnc_symbol, *bundle.aliases]
    name_disjunction = " OR ".join(f'"{n}"' for n in name_terms if n)

    spec = _CATEGORY_SPECS[category]
    query = (
        f"({name_disjunction}) AND "
        + " AND ".join(spec.query_clauses)
        + " AND SRC:MED"
    )
    payload = europepmc_search(http=http, query=query, page_size=max_papers * 3)
    hits = (payload.get("resultList") or {}).get("result") or []
    papers = [
        paper_from_europepmc(record, retraction_index=retraction_index)
        for record in hits
    ]
    # Prefer PMC OA + non-retracted papers; cap to max_papers.
    candidates = [
        p for p in papers
        if p.is_pmc_oa and p.pmc_id and not p.is_retracted
    ][:max_papers]

    if not candidates:
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

    fetched: list[Paper] = []
    all_snippets: list[CandidateSnippet] = []
    n_with_snippets = 0
    for paper in candidates:
        try:
            full = fetch_fulltext(
                http=http, pmcid=paper.pmc_id or "", retraction_index=retraction_index
            )
        except (LookupError, ValueError) as exc:
            logger.warning("fetch_fulltext failed for %s: %s", paper.pmc_id, exc)
            fetched.append(paper)
            continue
        fetched.append(full)
        per_paper = _extract_snippets(
            paper=full,
            spec=spec,
            max_snippets=max_snippets_per_paper,
        )
        if per_paper:
            n_with_snippets += 1
            all_snippets.extend(per_paper)

    # Sort across papers by score (descending) so the agent sees the
    # strongest matches first.
    all_snippets.sort(key=lambda s: s.score, reverse=True)

    empty_reason: str | None = None
    if not all_snippets:
        empty_reason = (
            "PMC-OA hits present but no hallmark-phrase match in "
            "intro/methods/results/discussion/figure_legends — full text "
            "may use non-standard phrasing"
        )

    return EvidenceRetrievalPack(
        uniprot_acc=uniprot_acc,
        category=category,
        n_papers_searched=len(papers),
        n_papers_with_snippets=n_with_snippets,
        papers=fetched,
        snippets=all_snippets,
        empty_reason=empty_reason,
    )


# ---------------------------------------------------------------------------
# Snippet extraction
# ---------------------------------------------------------------------------


# A sentence-ish splitter. Doesn't try to be perfect — surface biology
# papers use plenty of "Fig. 3A" and "i.e." that throw off naive
# splitters, so we keep a lenient pattern and let the ≤200-char cap do
# the trimming.
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z(])")


def _extract_snippets(
    *,
    paper: Paper,
    spec: _CategorySpec,
    max_snippets: int,
) -> list[CandidateSnippet]:
    """Pull up to ``max_snippets`` candidate sentences from ``paper.sections``.

    Per-section: split into sentences, score each by section weight ×
    hallmark-match count, keep the top sentences (capped at 200 chars).
    Deduplicate against already-emitted snippets from the same paper.
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
        for sentence in _split_sentences(section.text):
            for pattern in spec.hallmark_patterns:
                match = pattern.search(sentence)
                if not match:
                    continue
                snippet_text = _trim_to_200_chars(sentence, match)
                if not snippet_text:
                    continue
                # Confirm the trimmed snippet is a substring of the
                # source body — otherwise the orchestrator's substring
                # check (which runs against the same body) would reject
                # a claim made from this snippet.
                if snippet_text not in section.text:
                    continue
                score = weight + min(2.0, _count_hallmarks(sentence, spec.hallmark_patterns))
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
                        ),
                    )
                )
                break  # one pattern match per sentence is enough
    candidates.sort(key=lambda pair: pair[0], reverse=True)

    seen: set[str] = set()
    chosen: list[CandidateSnippet] = []
    for _, snippet in candidates:
        # Dedup on normalized text — first-200-chars overlap is enough
        # to consider the same snippet under different patterns.
        key = re.sub(r"\s+", " ", snippet.text.lower()).strip()
        if key in seen:
            continue
        seen.add(key)
        chosen.append(snippet)
        if len(chosen) >= max_snippets:
            break
    return chosen


def _split_sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_SPLIT.split(text) if s.strip()]


def _count_hallmarks(sentence: str, patterns: tuple[re.Pattern[str], ...]) -> int:
    return sum(1 for p in patterns if p.search(sentence))


def _trim_to_200_chars(sentence: str, match: re.Match[str]) -> str:
    """Return up to 200 chars centered on ``match`` while staying within
    ``sentence``. Prefer the whole sentence when it fits; otherwise carve
    a window around the match, breaking on whitespace.
    """
    sentence = sentence.strip()
    if len(sentence) <= 200:
        return sentence

    start, end = match.span()
    # Center 200-char window on the match, biased to capture the full
    # match if possible.
    span_len = end - start
    pad = max(0, (200 - span_len) // 2)
    window_start = max(0, start - pad)
    window_end = min(len(sentence), window_start + 200)
    window_start = max(0, window_end - 200)

    snippet = sentence[window_start:window_end]
    # Break on whitespace at edges so we don't emit a half-word.
    if window_start > 0:
        first_space = snippet.find(" ")
        if 0 < first_space < 40:
            snippet = snippet[first_space + 1 :]
    if window_end < len(sentence):
        last_space = snippet.rfind(" ")
        if last_space > len(snippet) - 40:
            snippet = snippet[:last_space]
    return snippet.strip()


# ---------------------------------------------------------------------------
# HPA short-circuit
# ---------------------------------------------------------------------------


_HPA_RELIABILITY_TIERS: tuple[str, ...] = ("enhanced", "supported", "approved", "uncertain")


def _hpa_ihc(*, uniprot_acc: str, http: CachedHTTP) -> EvidenceRetrievalPack:
    """Read the HPA snapshot, find this gene, emit deterministic snippets.

    The snippet text uses :func:`format_hpa_body` so the orchestrator's
    body-registration shim can rebuild the exact same string and the
    substring check still works.
    """
    from ..paths import DATA_DIR  # local import to keep paths.py optional at import time

    bundle = _resolve(uniprot_acc, http=http)
    symbol = bundle.hgnc_symbol
    snapshot = DATA_DIR / "processed" / "hpa" / "hpa_human_snapshot.tsv"
    if not snapshot.exists():
        return EvidenceRetrievalPack(
            uniprot_acc=uniprot_acc,
            category="hpa_ihc",
            empty_reason="HPA snapshot not found on disk; bootstrap with `bootstrap-worktree.sh candidate`",
        )

    row = _find_hpa_row(snapshot, symbol=symbol, uniprot_acc=bundle.uniprot_acc)
    if row is None:
        return EvidenceRetrievalPack(
            uniprot_acc=uniprot_acc,
            category="hpa_ihc",
            empty_reason=f"no HPA snapshot row for {symbol} / {bundle.uniprot_acc}",
        )

    body = format_hpa_body(row)
    snippets = [
        CandidateSnippet(
            source_id=f"HPA:{symbol}",
            section="other",
            figure_or_table_id=None,
            text=line.strip(),
            score=1.0,
            hallmark_phrase="hpa_snapshot",
        )
        for line in body.splitlines()
        if line.strip() and len(line.strip()) <= 200
    ]
    ensembl = (row.get("ensembl_gene_id") or "").strip()
    hpa_url = (
        f"https://www.proteinatlas.org/{ensembl}/cell"
        if ensembl
        else f"https://www.proteinatlas.org/?query={symbol}"
    )
    synthetic = [
        SyntheticSource(
            source_id=f"HPA:{symbol}",
            source_type="hpa_ihc",
            url=hpa_url,
            title=f"HPA snapshot for {symbol}",
            raw_text=body,
        )
    ] if body else []
    return EvidenceRetrievalPack(
        uniprot_acc=uniprot_acc,
        category="hpa_ihc",
        n_papers_searched=1,
        n_papers_with_snippets=1 if snippets else 0,
        papers=[],
        snippets=snippets,
        synthetic_sources=synthetic,
        empty_reason=None if snippets else "HPA row matched but no quotable lines emitted",
    )


HPA_SOURCE_PREFIX: Literal["HPA"] = "HPA"


def format_hpa_body(row: Mapping[str, str]) -> str:
    """Render the HPA per-gene snapshot row as the canonical multi-line
    source body for ``HPA:<symbol>``.

    Used by both the tool (to emit candidate snippets) and the orchestrator
    (to register the body for substring validation). Deterministic so the
    two sides agree byte-for-byte.
    """
    parts: list[str] = []
    symbol = (row.get("hpa_gene_symbol") or "").strip()
    if symbol:
        parts.append(f"HPA gene symbol: {symbol}.")
    reliability = (row.get("hpa_reliability") or "").strip()
    if reliability:
        parts.append(f"HPA reliability for IHC: {reliability}.")
    locations = (row.get("hpa_locations") or "").strip()
    if locations:
        parts.append(f"HPA subcellular locations: {locations}.")
    if (row.get("hpa_pm_accessible") or "").strip() in {"1", "true", "True"}:
        parts.append("HPA flags this gene as plasma-membrane accessible.")
    if (row.get("hpa_junctional") or "").strip() in {"1", "true", "True"}:
        parts.append("HPA flags this gene as junctional.")
    pm_tiers: list[str] = []
    for tier in _HPA_RELIABILITY_TIERS:
        col = f"hpa_pm_in_{tier}"
        if (row.get(col) or "").strip() in {"1", "true", "True"}:
            pm_tiers.append(tier)
    if pm_tiers:
        parts.append(f"HPA plasma-membrane reliability tiers: {', '.join(pm_tiers)}.")
    return "\n".join(parts)


def _find_hpa_row(
    snapshot_path,
    *,
    symbol: str | None,
    uniprot_acc: str | None,
) -> Mapping[str, str] | None:
    target_symbol = (symbol or "").strip().upper()
    target_acc = (uniprot_acc or "").strip().upper()
    with snapshot_path.open() as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for raw in reader:
            row_sym = (raw.get("hpa_gene_symbol") or "").strip().upper()
            row_acc = (raw.get("uniprot_accession") or "").strip().upper()
            if target_symbol and row_sym == target_symbol:
                return raw
            if target_acc and row_acc == target_acc:
                return raw
    return None


__all__ = [
    "evidence_retrieval",
    "format_hpa_body",
    "HPA_SOURCE_PREFIX",
]
