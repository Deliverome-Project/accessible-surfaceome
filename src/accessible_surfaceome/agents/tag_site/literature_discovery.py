"""Hybrid literature discovery for tag sites.

Uses the repo's own EuropePMC + PubTator stack (same primitives as
``agents/internalization/literature_discovery.py``), tuned for tagging-methods
papers, so the tag-site agent stops relying on ``web_search`` alone. A
``web_search`` complement is still valuable — it reaches preprints and
vocabulary-mismatch methods papers the abstract index misses (e.g. hERG's Kanner
2018, whose abstract says "optical monitoring", not "tag") — but its results are
*ranked* by source tier here, not filtered: peer-reviewed papers and preprints
first, then patents, then vendor catalog pages (kept, just lowest tier).

Query tuning is benchmark-validated against ``data/tag_sites/positive_controls.tsv``
(16 controls with identifiable papers):

* EuropePMC alias-expanded + tagging-methods vocabulary: recall 5/16 -> 9/16.
  Synonyms matter most — methods papers say "hERG"/"transferrin receptor", not
  the gene symbol.
* PubTator entity search: keep the free-text MINIMAL. Its NER already resolves
  synonyms; overloading the query with methods terms tanked recall 8/16 -> 1/16.

The union with a paper-ranked ``web_search`` beat either backend alone on every
co-tested control (union 11/11 vs web 10/11 vs lit 9/11).
"""
from __future__ import annotations

import re


from accessible_surfaceome.tools._shared.europepmc import (
    europepmc_bulk_by_pmid,
    europepmc_search,
    fetch_fulltext,
    papers_from_europepmc_records,
)
from accessible_surfaceome.tools._shared.http import CachedHTTP
from accessible_surfaceome.tools._shared.models import Paper, paper_source_id
from accessible_surfaceome.tools._shared.normalize import (
    find_quote_in_normalized,
    normalize_for_quote_matching,
)
from accessible_surfaceome.tools._shared.pubtator import (
    build_gene_entity_query,
    pubtator_search,
)
from accessible_surfaceome.tools._shared.retraction_watch import (
    RetractionIndex,
    empty as _empty_retraction_index,
)

# Tagging-methods vocabulary. Deliberately broad: many surface-labeling constructs
# are never called "tags" in the abstract, so we OR in the concrete modalities.
_TAG_METHODS = (
    '"epitope tag" OR "HA tag" OR "FLAG tag" OR "Myc tag" OR "ecto-tagged" OR '
    '"epitope-tagged" OR "extracellular epitope" OR "surface labeling" OR '
    '"cell surface expression" OR "knock-in" OR pHluorin OR HiBiT OR HaloTag OR '
    'ALFA OR DogTag OR SpyTag OR bungarotoxin OR "extracellular loop"'
)
_MAX_PER_SOURCE = 30


def _alias_or(aliases: list[str]) -> str:
    """OR-join aliases, PHRASE-quoting multi-word ones. Unquoted, ``transferrin
    receptor`` parses as ``transferrin AND receptor`` across all fields and
    inflates the match set — quoting keeps the gene scope tight."""
    parts = [f'"{a}"' if " " in a else a for a in sorted({a for a in aliases if a})]
    return " OR ".join(parts)


def build_tag_site_query(aliases: list[str]) -> str:
    """EuropePMC boolean: (gene aliases) AND (tagging-methods vocabulary)."""
    return f"({_alias_or(aliases)}) AND ({_TAG_METHODS})"


def discover_tag_site_papers(
    *,
    http: CachedHTTP,
    gene_symbol: str,
    aliases: list[str],
    retraction_index: RetractionIndex | None = None,
) -> dict[str, Paper]:
    """Return ``{paper_source_id: Paper}`` for tagging-methods papers on this gene,
    via the repo lit-search: EuropePMC (alias + methods vocabulary) UNION PubTator
    entity search (minimal query), hydrated to full :class:`Paper` objects.

    Keyed on the shared :func:`paper_source_id` (``PMC:`` > ``PMID:`` > ``DOI:``),
    NOT the integer PMID, so DOI-anchored bioRxiv/medRxiv preprints join the same
    corpus — ``papers_from_europepmc_records(..., include_preprints=True)`` keeps
    them (the shared contract from #143) instead of the old PPR skip. ``aliases``
    should include the protein name(s) — methods papers rarely use the symbol."""
    ri = retraction_index or _empty_retraction_index()
    discovered: dict[str, Paper] = {}
    query = build_tag_site_query([gene_symbol, *aliases])

    # Two EuropePMC passes over the same alias+methods query: the default
    # (relevance/recency) sort PLUS a CITATION-sorted pass that surfaces the
    # classic, heavily-cited methods papers the default sort buries. Preprints are
    # kept (DOI-anchored) and retracted papers dropped.
    for sort in (None, "CITED desc"):
        payload = europepmc_search(http=http, query=query, page_size=_MAX_PER_SOURCE, sort=sort)
        records = payload.get("resultList", {}).get("result", [])
        for paper in papers_from_europepmc_records(
            records,
            retraction_index=ri,
            context=f"tag_site:{gene_symbol}",
            include_preprints=True,
        ):
            if not paper.is_retracted:
                discovered.setdefault(paper_source_id(paper), paper)

    # PubTator entity search — MINIMAL free text (overloading it tanks recall),
    # hydrated to Paper objects via EuropePMC. Retracted papers dropped.
    hits = pubtator_search(
        http=http, query=build_gene_entity_query(gene_symbol, "epitope tag")
    ).hits
    known_pmids = {p.pmid for p in discovered.values() if p.pmid}
    pmids = [h.pmid for h in hits if h.pmid and h.pmid not in known_pmids][:_MAX_PER_SOURCE]
    for paper in europepmc_bulk_by_pmid(http=http, pmids=pmids, retraction_index=ri):
        if not paper.is_retracted:
            discovered.setdefault(paper_source_id(paper), paper)

    return discovered


# Source-tier vocabulary for a site's cited evidence (the model sets ``source_tier``
# on each proposal; ``runner._sort_key`` ranks by it). URL-based web tiering now
# lives in the shared ``web_literature.source_tier`` — web hits are hydrated to real
# id-anchored Papers there, so this module no longer classifies raw URLs.
SOURCE_TIERS = ("paper", "patent", "other", "vendor")


_MAX_FULLTEXT_PAPERS = 8


def fetch_fulltext_sections(
    *,
    http: CachedHTTP,
    papers: dict[str, Paper],
    max_papers: int = _MAX_FULLTEXT_PAPERS,
    retraction_index: RetractionIndex | None = None,
) -> dict[str, dict[str, str]]:
    """Fetch full text for the top ``max_papers`` discovered papers that have a
    PMCID, via the repo's ``fetch_fulltext`` (NCBI/PMC, same path evidence_retrieval
    uses), and return ``{paper_source_id: {section: text}}`` for the METHODS +
    RESULTS sections — where the tag construct (exact residue) AND the
    surface/function measurements live. Best-effort: a paper with no PMC-OA full
    text or a fetch error is skipped (preprints have no PMCID -> abstract only), so
    the agent still has the abstract for it. Keyed on ``paper_source_id`` to match
    the ``discover_tag_site_papers`` corpus."""
    ri = retraction_index or _empty_retraction_index()
    out: dict[str, dict[str, str]] = {}
    for sid, paper in list(papers.items())[:max_papers]:
        if not paper.pmc_id:
            continue
        try:
            full = fetch_fulltext(http=http, pmcid=paper.pmc_id, retraction_index=ri)
        except Exception:  # noqa: BLE001 - full text is best-effort
            continue
        secs = {s.name: s.text for s in full.sections if s.name in ("methods", "results")}
        if secs:
            out[sid] = secs
    return out


def quote_supported(quote: str | None, source_text: str) -> bool:
    """True iff ``quote`` (a model-provided verbatim sentence) is found in
    ``source_text`` after the same normalization ``promote_claim`` uses (NFKC +
    Greek + HTML + whitespace + lowercase). The entailment check behind
    ``entailment_verified``: a citation is only trusted if its supporting quote
    actually appears in the fetched source. Quotes under 12 normalized chars are
    too short to anchor and never verify."""
    if not quote or not source_text:
        return False
    nq = normalize_for_quote_matching(quote)
    if len(nq) < 12:
        return False
    return find_quote_in_normalized(nq, normalize_for_quote_matching(source_text)) is not None


# Vocabulary that marks a sentence as actually describing an insertion, rather
# than being background biology. Deliberately broad across modality, because the
# tagging literature names the construct a dozen ways and rarely says "tag" —
# the same reason ``_TAG_METHODS`` above is broad for discovery.
_PROBATIVE_TERMS = (
    "tag", "tagged", "epitope", "insert", "inserted", "insertion", "fusion",
    "fused", "knock-in", "knockin", "knocked in", "appended", "engineered",
    "ha ", "flag", "myc", "alfa", "v5", "gfp", "yfp", "cfp", "mcherry",
    "phluorin", "hibit", "halotag", "snap-tag", "clip-tag", "spytag", "dogtag",
    "bungarotoxin", "avitag", "biotin-acceptor", "tetracysteine", "flash",
    "transposon", "chimera", "chimeric", "reporter",
)


def quote_is_probative(quote: str | None) -> bool:
    """True when ``quote`` actually describes an insertion/tag, not background
    biology.

    ``entailment_verified`` proves a quote came from the cited source; this asks
    the separate question of whether it SUPPORTS the site. A site can be right
    and its quote useless — a reader who clicks through to check then sees
    nothing about a tag."""
    if not quote:
        return False
    q = f" {quote.lower()} "
    return any(t in q for t in _PROBATIVE_TERMS)


def best_supporting_quote(*, residue: int | None, evidence) -> str | None:
    """The strongest ledger quote for a site at ``residue``: one that is probative
    AND names the residue number, else any probative one. None when the ledger
    has nothing better to offer.

    Used to UPGRADE a non-probative citation rather than drop the site — the
    GLUT4 case proved dropping is wrong, since the site and paper were both
    correct and only the quoted sentence was weak."""
    quotes = [sp.quote for e in evidence for sp in (e.spans or []) if sp.quote]
    probative = [q for q in quotes if quote_is_probative(q)]
    if not probative:
        return None
    if residue is not None:
        marker = str(residue)
        for q in probative:
            if marker in q:
                return q
    return probative[0]


# Residue spellings a tagging paper actually uses. The code form alone is not
# enough: EndoNB writes "(Alanine 34)" and "at the codon for glycine 101", and
# its only machine-readable copies sit inside primer tables full of raw DNA.
_AA_FULL = {
    "alanine": "A", "arginine": "R", "asparagine": "N", "aspartate": "D",
    "aspartic acid": "D", "cysteine": "C", "glutamate": "E", "glutamic acid": "E",
    "glutamine": "Q", "glycine": "G", "histidine": "H", "isoleucine": "I",
    "leucine": "L", "lysine": "K", "methionine": "M", "phenylalanine": "F",
    "proline": "P", "serine": "S", "threonine": "T", "tryptophan": "W",
    "tyrosine": "Y", "valine": "V",
}
_AA_THREE = {
    "ala": "A", "arg": "R", "asn": "N", "asp": "D", "cys": "C", "glu": "E",
    "gln": "Q", "gly": "G", "his": "H", "ile": "I", "leu": "L", "lys": "K",
    "met": "M", "phe": "F", "pro": "P", "ser": "S", "thr": "T", "trp": "W",
    "tyr": "Y", "val": "V",
}
_MAX_RESIDUE = 40_000  # longest human protein (titin) ~34k

_RE_FULL = re.compile(rf"\b({'|'.join(_AA_FULL)})\s*-?\s*(\d{{1,5}})\b", re.I)
_RE_THREE = re.compile(rf"\b({'|'.join(_AA_THREE)})\s*-?\s*(\d{{1,5}})\b", re.I)
_RE_CODE = re.compile(r"(?<![A-Za-z0-9])([ACDEFGHIKLMNPQRSTVWY])(\d{1,5})(?![A-Za-z0-9])")
_RE_POSITIONAL = re.compile(r"\b(?:residue|position|codon)\s+(?:no\.?\s*)?(\d{1,5})\b", re.I)
# A long uppercase nucleotide run means we are inside a primer / HDR table, where
# a token like "A33" is sequence formatting rather than a residue label.
_RE_DNA_RUN = re.compile(r"[ACGT]{12,}")


def residue_mentions(text: str | None, *, sequence: str | None = None) -> set[int]:
    """Every residue POSITION ``text`` names, in any spelling a paper might use:
    ``A33``, ``Ala33``, ``Thr 436``, ``alanine 34``, ``residue 64``.

    ``sequence`` unlocks the HDR / primer tables. A code sitting in a block of
    raw nucleotides is normally sequence formatting rather than a residue label,
    so it is ignored — but those tables are also where a tagging paper records
    its authoritative insertion labels, and dropping them loses real sites. When
    the canonical sequence is supplied, a DNA-adjacent code is trusted exactly
    when it MATCHES the sequence at that position, which formatting will not.

    Positions are returned as the text names them. Papers differ on whether the
    label is the residue before or after the junction — EndoNB names the one
    before for four of its genes and the one after for TFRC — so a caller
    converting to a junction must consider both ``n`` and ``n - 1``."""
    if not text:
        return set()
    runs = _RE_DNA_RUN.findall(text)
    clean = _RE_DNA_RUN.sub(" ", text)
    dna_heavy = sum(len(r) for r in runs) > 0.3 * len(text)

    out: set[int] = set()
    for rx in (_RE_FULL, _RE_THREE, _RE_POSITIONAL):
        for m in rx.finditer(clean):
            n = int(m.groups()[-1])
            if 0 < n <= _MAX_RESIDUE:
                out.add(n)

    for m in _RE_CODE.finditer(clean):
        letter, n = m.group(1).upper(), int(m.group(2))
        if not 0 < n <= _MAX_RESIDUE:
            continue
        if not dna_heavy:
            out.add(n)
        elif sequence and n <= len(sequence) and sequence[n - 1].upper() == letter:
            out.add(n)  # a table label the sequence confirms
    return out


def boost_residue_clips(pool, *, sequence: str, topology: str) -> int:
    """Raise the score of every clip that names an EXTRACELLULAR residue, so it
    survives the selector's menu cap. Mutates ``pool`` in place; returns the
    number boosted.

    ``select_clips`` keeps only the top clips by score, which on a well-studied
    gene throws away most of the evidence (TFRC: 746 clips -> 100). A clip that
    pins a real insertion is then never shown to the selector, so reading
    residues at all is pointless unless the clip carrying one survives the cut.

    Only extracellular positions count — a residue in the cytoplasmic tail or a
    TM helix is not a surface tag site. Both ``n`` and ``n - 1`` are tested
    against the topology because papers differ on whether a label names the
    residue before or after the junction.

    This is a tag-site-only pre-pass: the shared selector is untouched, so the
    internalization track keeps its own ranking."""
    if not pool or not sequence or not topology:
        return 0

    def _extracellular(n: int) -> bool:
        for pos in (n, n - 1):
            if 1 <= pos <= len(topology) and topology[pos - 1] == "O":
                return True
        return False

    hits = [
        key
        for key, clip in pool.items()
        if any(
            _extracellular(n)
            for n in residue_mentions(
                " ".join(filter(None, (getattr(clip, "quote", None),
                                       getattr(clip, "context_excerpt", None)))),
                sequence=sequence,
            )
        )
    ]
    if not hits:
        return 0
    # Lift boosted clips above every unboosted one while keeping their order
    # among themselves, so this re-ranks without discarding the pool's own signal.
    ceiling = max((getattr(c, "score", 0.0) or 0.0) for c in pool.values())
    for key in hits:
        pool[key].score = (getattr(pool[key], "score", 0.0) or 0.0) + ceiling + 1.0
    return len(hits)
