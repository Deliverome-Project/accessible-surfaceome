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

import hashlib
import json
import logging
import re
import time
from pathlib import Path


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
    '"epitope tag" OR "HA tag" OR "FLAG tag" OR "Myc tag" OR "V5 tag" OR '
    '"VSV-G" OR "ecto-tagged" OR "epitope-tagged" OR "extracellular epitope" OR '
    '"surface labeling" OR "cell surface expression" OR "knock-in" OR '
    'pHluorin OR HiBiT OR HaloTag OR ALFA OR DogTag OR SpyTag OR '
    'BLAP OR "biotin acceptor peptide" OR bungarotoxin OR "alpha-bungarotoxin" OR '
    '"extracellular loop" OR "domain insertion" OR "insertional mutagenesis"'
)
#: Results per EuropePMC / PubTator pass. Was 30, which with two EuropePMC
#: passes plus PubTator put a ~90-paper ceiling over a measured median of 77
#: discovered papers — so discovery was capped, not exhausted.
_MAX_PER_SOURCE = 60

# Alias-hygiene rules mirrored from ``agents/internalization/literature_discovery.py``:
# drop ultra-short / protein-mass aliases (e.g. TR, T9, p90, M1, C1), common
# 3-letter English/lab words (BAR, TAG, MAP, NET, SET, CAT, FAT, ATP, ION),
# and clinical disease names ("syndrome", "dystrophy", ...) that flood EuropePMC
# with unrelated papers.
_NOISY_SHORT_ALIAS_RE = re.compile(r"^(?:[A-Za-z]{1,2}\d?|p\d{2,3})$")
_COLLISION_ALIAS_WORDS: frozenset[str] = frozenset({
    "act", "add", "age", "aid", "aim", "air", "all", "and", "ant", "any", "arc",
    "are", "arm", "art", "ask", "ate", "atp", "avg", "bad", "bag", "ban", "bar",
    "bat", "bay", "bed", "bet", "bid", "big", "bin", "bio", "bit", "box", "boy",
    "bud", "bug", "bus", "but", "buy", "can", "cap", "car", "cat", "cell", "cut",
    "dad", "dam", "day", "den", "did", "die", "dig", "dim", "dip", "dna", "dog",
    "dot", "dry", "due", "ear", "eat", "egg", "end", "era", "eve", "eye", "fab",
    "fan", "far", "fat", "fbs", "fed", "fee", "few", "fig", "fin", "fit", "fix",
    "fly", "for", "fox", "fun", "fur", "gap", "gas", "gdp", "gel", "get", "got",
    "gtp", "gum", "gun", "gut", "guy", "had", "ham", "has", "hat", "her", "hid",
    "him", "hip", "his", "hit", "hot", "how", "hub", "hue", "hug", "ice", "igg",
    "ill", "ink", "inn", "ion", "its", "jam", "jar", "jaw", "jet", "job", "jog",
    "joy", "key", "kid", "kin", "kit", "lab", "lac", "lad", "lag", "lap", "law",
    "lay", "led", "leg", "let", "lid", "lie", "lip", "lit", "log", "lot", "low",
    "mad", "man", "map", "mat", "max", "may", "men", "met", "mid", "min", "mix",
    "mob", "mod", "mom", "mop", "mud", "mug", "nap", "net", "new", "nil", "nod",
    "nor", "not", "now", "nut", "oak", "oar", "odd", "off", "oil", "old", "one",
    "opt", "orb", "ore", "our", "out", "ova", "owe", "owl", "own", "pad", "pan",
    "par", "pat", "paw", "pay", "pbs", "pcr", "pea", "peg", "pen", "pep", "per",
    "pet", "pie", "pig", "pin", "pit", "pod", "pop", "pot", "pro", "pub", "pun",
    "pup", "put", "rad", "rag", "ram", "ran", "rap", "rat", "raw", "ray", "red",
    "ref", "rep", "rib", "rid", "rig", "rim", "rip", "rna", "rob", "rod", "rot",
    "row", "rub", "rug", "run", "rut", "sad", "sag", "sap", "sat", "saw", "say",
    "sea", "sec", "see", "set", "sew", "sex", "she", "shy", "sin", "sip", "sir",
    "sis", "sit", "six", "ski", "sky", "sob", "sod", "son", "sow", "soy", "spa",
    "spy", "std", "sub", "sum", "sun", "sup", "tab", "tag", "tan", "tap", "tar",
    "tax", "tea", "ten", "the", "thy", "tic", "tie", "tin", "tip", "toe", "ton",
    "too", "top", "tot", "tow", "toy", "try", "tub", "tug", "two", "urn", "use",
    "van", "vat", "vet", "via", "vow", "wad", "wag", "war", "was", "wax", "way",
    "web", "wed", "wee", "wet", "who", "why", "wig", "win", "wit", "woe", "wok",
    "won", "woo", "wow", "yak", "yam", "yap", "yaw", "yea", "yen", "yes", "yet",
    "yew", "yin", "yip", "yok", "you", "zap", "zed", "zen", "zip", "zoo",
})
_DISEASE_ALIAS_RE = re.compile(
    r"\b(?:syndrome|disease|hypercholesterolemia|deficiency|susceptibility|"
    r"dystrophy|carcinoma|leukemia|lymphoma|neuropathy|myopathy|cardiomyopathy|"
    r"ataxia|deafness|blindness|anemia|albinism)\b",
    re.IGNORECASE,
)
_TRAILING_NUM_RE = re.compile(r"^(.+?)\s+[1-9]\d?$")
_GENERIC_STEM_RE = re.compile(
    r"^(?:transmembrane protein|solute carrier|olfactory receptor|taste receptor|"
    r"vomeronasal|membrane spanning|g protein-coupled receptor|"
    r"immunoglobulin superfamily|zinc finger|ring finger|leucine rich repeat|"
    r"chromosome \w+ open reading frame|family with sequence similarity|"
    r"coiled-coil domain|tetraspanin|claudin|cadherin|integrin|protocadherin|"
    r"cell adhesion molecule|receptor tyrosine kinase|protein tyrosine phosphatase)\b",
    re.IGNORECASE,
)

logger = logging.getLogger(__name__)


def _is_noisy_short_alias(alias: str, *, primary_symbol: str) -> bool:
    s = alias.strip()
    if not s or s.upper() == primary_symbol.upper():
        return False
    if " " in s:
        return False
    if s.lower() in _COLLISION_ALIAS_WORDS:
        return True
    return bool(_NOISY_SHORT_ALIAS_RE.match(s))


def _is_disease_alias(name: str) -> bool:
    return bool(_DISEASE_ALIAS_RE.search(name))


def _stem_without_trailing_num(name: str | None) -> str | None:
    if not name or " " not in name.strip():
        return None
    m = _TRAILING_NUM_RE.match(name.strip())
    if not m:
        return None
    stem = m.group(1).strip()
    if len(stem) < 12 or " " not in stem or _GENERIC_STEM_RE.match(stem):
        return None
    return stem


def clean_tag_site_aliases(
    gene_symbol: str,
    aliases: list[str],
    *,
    primary_name: str | None = None,
) -> list[str]:
    """Filter noisy short/collision/disease aliases before building EuropePMC
    queries, while keeping the primary gene symbol, specific protein names, and
    non-generic trailing-number stems (e.g. ``asialoglycoprotein receptor``)."""
    raw: list[str] = [gene_symbol]
    if primary_name:
        raw.append(primary_name)
        stem = _stem_without_trailing_num(primary_name)
        if stem:
            raw.append(stem)
    for a in aliases:
        if not a or not a.strip():
            continue
        raw.append(a)
        stem = _stem_without_trailing_num(a)
        if stem:
            raw.append(stem)

    out: list[str] = []
    seen: set[str] = set()
    primary_lower = (primary_name or "").strip().lower()
    for a in raw:
        s = a.strip()
        if not s:
            continue
        if _is_noisy_short_alias(s, primary_symbol=gene_symbol):
            continue
        if s.lower() != primary_lower and _is_disease_alias(s):
            continue
        k = s.lower()
        if k not in seen:
            seen.add(k)
            out.append(s)
    return out


def _alias_or(aliases: list[str]) -> str:
    """OR-join aliases, PHRASE-quoting multi-word ones. Unquoted, ``transferrin
    receptor`` parses as ``transferrin AND receptor`` across all fields and
    inflates the match set — quoting keeps the gene scope tight."""
    parts = [f'"{a}"' if " " in a else a for a in sorted({a.strip() for a in aliases if a and a.strip()})]
    return " OR ".join(parts)


def build_tag_site_query(aliases: list[str]) -> str:
    """Gene-in-TITLE_ABS EuropePMC boolean: ``(TITLE_ABS:(aliases)) AND (methods)``.

    Scoping the gene alias clause to ``TITLE_ABS`` prevents PMC-OA full-text
    table/reference-list mentions from flooding discovery with 350-450 unrelated
    papers per gene, while leaving the tagging-method clause free to match
    Materials & Methods (where most extracellular loop tag insertions live).
    """
    return f"(TITLE_ABS:({_alias_or(aliases)})) AND ({_TAG_METHODS})"


# The same vocabulary as ``_TAG_METHODS``, split by MODALITY. One monolithic
# OR-clause gets a single relevance ranking and a single top-N cut, so a paper
# matching one narrow facet competes against every other facet's matches. Issued
# separately, each facet gets its own top-N and the union covers more ground --
# which matters because tagging papers are found by the modality they used, not
# by the word "tag".
_TAG_METHOD_FACETS = {
    "epitope": (
        '"epitope tag" OR "HA tag" OR "FLAG tag" OR "Myc tag" OR "V5 tag" OR '
        '"VSV-G" OR ALFA OR BLAP OR "biotin acceptor peptide" OR '
        '"epitope-tagged" OR "extracellular epitope"'
    ),
    "fluorescent": (
        'pHluorin OR "fluorescent protein" OR GFP OR "GFP fusion" OR mCherry OR '
        'HaloTag OR "SNAP-tag" OR HiBiT'
    ),
    "knock_in": (
        '"knock-in" OR "knockin" OR "endogenously tagged" OR "endogenous tagging" OR '
        'CRISPR OR "gene editing"'
    ),
    "surface_display": (
        '"cell surface expression" OR "surface labeling" OR "surface labelling" OR '
        '"non-permeabilized" OR "ecto-tagged" OR "surface display" OR '
        '"intact cells"'
    ),
    "insertion": (
        '"extracellular loop" OR "domain insertion" OR "insertion screen" OR '
        '"transposon insertion" OR "random insertion" OR transposon OR '
        'bungarotoxin OR "alpha-bungarotoxin" OR BBS OR SpyTag OR DogTag'
    ),
    # Every gene in the L1 internal-site set is multipass with no extracellular
    # terminus, so its tag can ONLY go in a loop — and the vocabulary above
    # names loops only generically. Papers name the specific loop ("the second
    # extracellular loop", "ECL2", "S3-S4", "loop C"), which no other facet matches.
    "internal_loop": (
        '"first extracellular loop" OR "second extracellular loop" OR '
        '"third extracellular loop" OR "fourth extracellular loop" OR '
        'ECL1 OR ECL2 OR ECL3 OR ECL4 OR EC1 OR EC2 OR EL1 OR EL2 OR EL3 OR EL4 OR '
        '"extracellular loop 1" OR "extracellular loop 2" OR '
        '"extracellular loop 3" OR "extracellular loop 4" OR '
        '"loop A" OR "loop C" OR "loop E" OR "S1-S2" OR "S3-S4" OR "S5-S6" OR '
        '"P-loop" OR "M1-M2" OR "M3-M4" OR '
        '"loop insertion" OR "inserted into the loop" OR '
        '"insertional mutagenesis" OR snorkel OR "re-entrant loop"'
    ),
}

# Internal-loop-only facets: drop generic GFP/mCherry fusions that flood
# multipass targets with cytoplasmic N-/C-terminal localization constructs,
# keeping extracellular/pH-sensitive/self-labeling/loop-insertion modalities.
_TAG_METHOD_FACETS_INTERNAL = {
    "epitope_ecto": (
        '"extracellular epitope" OR "ecto-tagged" OR "epitope-tagged" OR '
        'ALFA OR BLAP OR "biotin acceptor peptide" OR "biotin ligase acceptor" OR '
        '(("HA tag" OR "HA-tagged" OR "HA epitope") AND ("extracellular" OR "surface" OR "loop")) OR '
        '(("FLAG tag" OR "FLAG-tagged" OR "FLAG epitope") AND ("extracellular" OR "surface" OR "loop")) OR '
        '(("Myc tag" OR "Myc-tagged" OR "Myc epitope") AND ("extracellular" OR "surface" OR "loop"))'
    ),
    "biosensor_self_label": (
        'pHluorin OR HiBiT OR HaloTag OR "SNAP-tag" OR '
        'bungarotoxin OR "alpha-bungarotoxin" OR BBS OR SpyTag OR DogTag'
    ),
    "surface_display": _TAG_METHOD_FACETS["surface_display"],
    "insertion": _TAG_METHOD_FACETS["insertion"],
    "internal_loop": _TAG_METHOD_FACETS["internal_loop"],
}


def build_tag_site_queries(
    aliases: list[str], *, internal_only: bool = False
) -> list[str]:
    """One EuropePMC boolean per tagging MODALITY with the gene aliases scoped
    to ``TITLE_ABS`` and the tagging method free to match Methods/full text."""
    alias_clause = _alias_or(aliases)
    facets = _TAG_METHOD_FACETS_INTERNAL if internal_only else _TAG_METHOD_FACETS
    return [
        f"(TITLE_ABS:({alias_clause})) AND ({facet})"
        for facet in facets.values()
    ]


def build_tag_site_preprint_query(aliases: list[str]) -> str:
    """Targeted $0 EuropePMC preprint pass (bioRxiv/medRxiv) searching full text
    so recent tagging/insertion methods preprints that list a target only in
    Results/Tables (e.g. EndoNB, DMS/domain-insertion screens) are discovered
    even when web_search is skipped."""
    return (
        f"SRC:PPR AND ({_alias_or(aliases)}) AND "
        '(TITLE_ABS:("epitope tag" OR "domain insertion" OR "extracellular loop" '
        'OR "ecto-tagged" OR "surface display" OR HiBiT OR ALFA OR pHluorin '
        'OR "insertional mutagenesis" OR transposon OR snorkel) OR "EndoNB")'
    )


def merge_discovery_cache(*, cached: dict, fresh: dict) -> dict:
    """Union of a gene's previously-discovered papers and this run's, keyed by
    ``paper_source_id``; the fresh record wins on collision.

    Discovery is non-deterministic where it counts -- a preprint whose abstract
    names none of the genes it tags is reachable only through web search, and so
    appears on one run and not the next. Accumulating the union means a paper
    found once is never lost, without biasing the search toward any particular
    paper: whatever discovery surfaces is simply kept."""
    return {**cached, **fresh}


def discover_tag_site_papers(
    *,
    http: CachedHTTP,
    gene_symbol: str,
    aliases: list[str],
    retraction_index: RetractionIndex | None = None,
    cached: dict[str, Paper] | None = None,
    faceted: bool = False,
    internal_only: bool = False,
    include_preprint_pass: bool = False,
    citation_counts_out: dict[str, int] | None = None,
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
    all_aliases = clean_tag_site_aliases(gene_symbol, aliases)

    passes: list[tuple[str, str | None, int]] = [
        (build_tag_site_query(all_aliases), None, _MAX_PER_SOURCE),
        (build_tag_site_query(all_aliases), "CITED desc", _MAX_PER_SOURCE),
    ]
    if faceted:
        passes += [
            (q, None, _MAX_PER_SOURCE)
            for q in build_tag_site_queries(all_aliases, internal_only=internal_only)
        ]
    if include_preprint_pass or faceted:
        passes.append((build_tag_site_preprint_query(all_aliases), None, 20))

    epmc_failures = 0
    for query, sort, page_size in passes:
        try:
            payload = europepmc_search(
                http=http, query=query, page_size=page_size, sort=sort
            )
        except Exception as exc:  # noqa: BLE001 - one facet failing must not lose the rest
            epmc_failures += 1
            logger.warning("EuropePMC query failed for %s: %s", gene_symbol, exc)
            continue
        records = payload.get("resultList", {}).get("result", [])
        cited_by_pmid: dict[int, int] = {}
        cited_by_pmc: dict[str, int] = {}
        cited_by_doi: dict[str, int] = {}
        if citation_counts_out is not None:
            for rec in records:
                raw_cited = rec.get("citedByCount")
                if not (
                    isinstance(raw_cited, (int, float))
                    or (isinstance(raw_cited, str) and raw_cited.isdigit())
                ):
                    continue
                c = int(raw_cited)
                if rec.get("pmcid"):
                    cited_by_pmc[str(rec["pmcid"]).upper()] = max(
                        c, cited_by_pmc.get(str(rec["pmcid"]).upper(), 0)
                    )
                if rec.get("pmid") and str(rec["pmid"]).isdigit():
                    p = int(str(rec["pmid"]))
                    cited_by_pmid[p] = max(c, cited_by_pmid.get(p, 0))
                if rec.get("doi"):
                    d = str(rec["doi"]).strip().lower()
                    cited_by_doi[d] = max(c, cited_by_doi.get(d, 0))

        for paper in papers_from_europepmc_records(
            records,
            retraction_index=ri,
            context=f"tag_site:{gene_symbol}",
            include_preprints=True,
        ):
            if not paper.is_retracted:
                sid = paper_source_id(paper)
                discovered.setdefault(sid, paper)
                if citation_counts_out is not None:
                    c = 0
                    if paper.pmc_id:
                        c = max(c, cited_by_pmc.get(str(paper.pmc_id).upper(), 0))
                    if paper.pmid is not None:
                        c = max(c, cited_by_pmid.get(int(paper.pmid), 0))
                    if paper.doi:
                        c = max(c, cited_by_doi.get(str(paper.doi).strip().lower(), 0))
                    if c > citation_counts_out.get(sid, 0):
                        citation_counts_out[sid] = c

    # Fail loudly when EuropePMC is resetting/outaged rather than silently
    # degrading to PubTator-only recall and publishing a blind empty record
    # under the current prompt SHA. Modal retries the member cleanly.
    degraded_threshold = max(2, (len(passes) + 1) // 2)
    if passes and epmc_failures >= degraded_threshold:
        raise RuntimeError(
            f"EuropePMC discovery degraded for {gene_symbol}: "
            f"{epmc_failures}/{len(passes)} EuropePMC queries failed"
        )

    # PubTator entity search — MINIMAL free text (overloading it tanks recall),
    # hydrated to Paper objects via EuropePMC. Retracted papers dropped.
    pubtator_terms = (
        ("extracellular loop", "epitope tag") if internal_only else ("epitope tag",)
    )
    known_pmids = {p.pmid for p in discovered.values() if p.pmid}
    pmids: list[int] = []
    seen_pt: set[int] = set()
    for term in pubtator_terms:
        try:
            hits = pubtator_search(
                http=http, query=build_gene_entity_query(gene_symbol, term)
            ).hits
        except Exception:  # noqa: BLE001
            continue
        for h in hits:
            if h.pmid and h.pmid not in known_pmids and h.pmid not in seen_pt:
                seen_pt.add(h.pmid)
                pmids.append(h.pmid)
                if len(pmids) >= _MAX_PER_SOURCE:
                    break
        if len(pmids) >= _MAX_PER_SOURCE:
            break
    if pmids:
        try:
            hydrated = europepmc_bulk_by_pmid(
                http=http, pmids=pmids, retraction_index=ri
            )
        except Exception as exc:  # noqa: BLE001 - transient EuropePMC outage must not drop discovered papers
            logger.warning(
                "EuropePMC bulk PMID hydration failed for %s (%d pmids): %s",
                gene_symbol,
                len(pmids),
                exc,
            )
            hydrated = []
        for paper in hydrated:
            if not paper.is_retracted:
                discovered.setdefault(paper_source_id(paper), paper)

    # Union with anything previous runs found for this gene. Discovery is
    # non-deterministic where it counts, so a paper reachable only through web
    # search can vanish between runs; keeping the accumulated set costs one
    # triage pass and removes that failure mode without steering the search.
    return merge_discovery_cache(cached=cached or {}, fresh=discovered)


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
        secs: dict[str, str] = {
            s.name: s.text for s in full.sections if s.name in ("methods", "results")
        }
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


def ledger_clip_within(quote: str | None, evidence) -> str | None:
    """The ledger clip that ``quote`` CONTAINS, when the model quoted a superset
    of what the clip stored. None when no clip is contained.

    ``quote_supported`` asks the other direction — is the quote inside the
    ledger — which drops a site for quoting too FAITHFULLY. Clips are truncated
    at extraction, so a model that reads the source and reproduces the whole
    sentence produces a string no clip contains: KCNH2 T436 was deleted for
    continuing "( Sekine-Aizawa and Huga" to "( Sekine-Aizawa and Huganir, 2004".

    The clip is returned rather than a bool so the caller can store the text it
    actually verified, never the longer string it merely believes.

    A contained clip must be substantial (>=40 normalized chars): a short
    fragment would match inside almost any sentence and would let padded or
    invented text ride in on a few shared words."""
    if not quote:
        return None
    nq = normalize_for_quote_matching(quote)
    if len(nq) < 12:
        return None
    best: str | None = None
    best_len = 0
    for e in evidence:
        for span in getattr(e, "spans", None) or []:
            clip = getattr(span, "quote", None)
            if not clip:
                continue
            nc = normalize_for_quote_matching(clip)
            if len(nc) >= 40 and find_quote_in_normalized(nc, nq) is not None and len(nc) > best_len:
                best, best_len = clip, len(nc)
    return best


# Vocabulary that marks a sentence as actually describing an insertion, rather
# than being background biology. Deliberately broad across modality, because the
# tagging literature names the construct a dozen ways and rarely says "tag" —
# the same reason ``_TAG_METHODS`` above is broad for discovery.
_PROBATIVE_TERMS = (
    "tag", "tagged", "epitope", "insert", "inserted", "insertion", "fusion",
    "fused", "knock-in", "knockin", "knocked in", "appended", "engineered",
    "ha ", "flag", "myc", "alfa", "v5", "vsv-g", "gfp", "yfp", "cfp", "mcherry",
    "phluorin", "hibit", "halotag", "snap-tag", "clip-tag", "spytag", "dogtag",
    "blap", "biotin acceptor", "bungarotoxin", "bbs", "avitag",
    "biotin-acceptor", "tetracysteine", "flash", "snorkel",
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

_RE_FULL = re.compile(rf"\b({'|'.join(_AA_FULL)})\s*-?\s*(\d{{1,5}})(?!\d)", re.I)
_RE_THREE = re.compile(rf"\b({'|'.join(_AA_THREE)})\s*-?\s*(\d{{1,5}})(?!\d)", re.I)
_RE_CODE = re.compile(r"(?<![A-Za-z0-9])([ACDEFGHIKLMNPQRSTVWY])(\d{1,5})(?![A-Za-z0-9])")
# JATS XML tag-stripping turns ``G<sub>60</sub>`` or ``V<sup>141</sup>`` into
# ``position G 60`` / ``at V 141``. Only match uppercase AA letters preceded by
# a positional preposition so English words ("at a 60") never match, and still
# require sequence-letter confirmation when ``sequence`` is supplied.
_RE_CODE_SPACED = re.compile(
    r"(?i:\b(?:position|residue|codon|at|after|before|between|and))\s+"
    r"([ACDEFGHIKLMNPQRSTVWY])\s+(\d{1,5})(?![A-Za-z0-9])"
)
_RE_POSITIONAL = re.compile(r"\b(?:residue|position|codon)\s+(?:no\.?\s*)?(\d{1,5})\b", re.I)
# A SPAN: "residues 484-516", "aa 120 to 135". Both boundaries are real position
# claims — a replaced or deleted segment starts at one and ends at the other —
# and the singular pattern above misses them twice over: on the plural "s" and
# on the range. SLC5A6's strongest citation reads "a segment of the EL3
# (residues 484-516) was replaced with an ALFA-tag", which names the junction
# the site claims, and the record was downgraded to 'inferred' for want of a
# number the quote plainly contains. A replacement or deletion is nearly always
# written as a range, so the forms this missed were exactly the strongest ones.
#: A deletion/replacement marker: "D484-516". Papers write a removed segment
#: this way as often as they spell it out.
_RE_DELTA_SPAN = re.compile(
    r"[\u0394\u2206]\s*(\d{1,5})\s*(?:[-\u2010-\u2015\u2212]|to)\s*(\d{1,5})\b"
)
#: "residues 484 and 516", "aa 484, 516" — a list, not a range.
_RE_LIST = re.compile(
    r"\b(?:residues|positions|codons|aa|amino\s+acids)\s+"
    r"(\d{1,5})\s*(?:,|and|&)\s*(\d{1,5})\b",
    re.I,
)
#: "aa484" / "aa 484" with no separating word.
_RE_AA_TIGHT = re.compile(r"\baa\s*(\d{1,5})\b", re.I)
_RE_SPAN = re.compile(
    r"\b(?:residues?|positions?|codons?|aa|amino\s+acids?)\s+"
    r"(\d{1,5})\s*(?:[-\u2010-\u2015\u2212]|to)\s*(\d{1,5})\b",
    re.I,
)
# A long uppercase nucleotide run means we are inside a primer / HDR table, where
# a token like "A33" is sequence formatting rather than a residue label.
_RE_DNA_RUN = re.compile(r"[ACGT]{12,}")


def residue_mentions(text: str | None, *, sequence: str | None = None) -> set[int]:
    """Every residue POSITION ``text`` names, in any spelling a paper might use:
    ``A33``, ``Ala33``, ``Thr 436``, ``alanine 34``, ``residue 64``,
    ``residues 484-516`` (a span claims both boundaries).

    ``sequence`` is what makes the CODE form (``A33``) safe to read at all. A bare
    letter-number token is extremely common noise: in one run every clip promoted
    on a code match was a false positive -- ``A549`` is a cell line, ``H3K79`` a
    histone mark, and a reagent table's catalogue number read as a residue too.
    When a sequence is supplied, a code is kept only when its letter MATCHES the
    sequence at that position, which rejected five of those six. This applies in
    prose and inside nucleotide blocks alike; the blocks additionally matter
    because a tagging paper's HDR/primer table is often where its authoritative
    insertion label lives, and dropping them loses real sites.

    The same check applies to spelled-out names, which are not immune: "histone
    H3 lysine 79" is not a residue of the protein under study. Any form carrying
    a LETTER is confirmed against the sequence; only bare positional phrases
    ("residue 64") have nothing to confirm and are taken as-is.

    A paper numbering in a different frame (mature protein, another isoform) will
    therefore not match and is dropped here. That is the right trade for this
    function's job -- feeding a position to the topology check -- because an
    unverifiable position cannot be placed on the extracellular face anyway;
    recovering such a frame is the synthesis stage's work, with the REPL.

    Positions are returned as the text names them. Papers differ on whether the
    label is the residue before or after the junction — EndoNB names the one
    before for four of its genes and the one after for TFRC — so a caller
    converting to a junction must consider both ``n`` and ``n - 1``."""
    return set(residue_mentions_detailed(text, sequence=sequence))


#: Forms that carry an amino-acid IDENTITY, and so can be confirmed (or denied)
#: against a sequence: ``A33``, ``Ala33``, ``alanine 33``. The rest —
#: ``residue 33``, ``residues 33-40``, ``aa 33`` — name a number and nothing
#: else, so no sequence can speak to them.
#:
#: The distinction is what makes reading a position out of a FOREIGN proteoform
#: frame safe (see :mod:`accessible_surfaceome.agents.tag_site.frames`). A bare
#: number confirms in every frame trivially, so it is no evidence that the paper
#: was numbering in any particular one; a letter-bearing token that the frame's
#: sequence agrees with is.
LETTER_CONFIRMED_FORMS: frozenset[str] = frozenset({"code", "three", "full"})

#: Of those, the forms that SPELL the residue — "Asn-549", "threonine 436".
#: The bare ``code`` form is the noisy one, as residue_mentions documents
#: ("A549 is a cell line, H3K79 a histone mark"), and its sequence check is
#: near-useless at low positions where any letter has a ~1/20 chance of
#: agreeing: "D1-like ... D2 ... D3 ... D4" reads as three confirmed aspartates
#: in any frame that happens to carry D at 2, 3 and 4. Measured on a real
#: 2,320-clip pool, EVERY clip that only a non-reference frame confirmed was
#: nomenclature of that shape — APOE E3/E4 genotypes, ubiquitin E1/E2/E3
#: enzymes, dopamine D1-D4 receptors — 13 of 13 noise. A spelled residue is not
#: something nomenclature produces, so it is what the frame resolver requires
#: before two tokens may license a frame.
SPELLED_AA_FORMS: frozenset[str] = frozenset({"three", "full"})


def residue_mentions_detailed(
    text: str | None, *, sequence: str | None = None
) -> dict[int, frozenset[str]]:
    """:func:`residue_mentions`, but reporting WHICH spelling produced each
    position: ``{436: frozenset({"three"}), 484: frozenset({"span"})}``.

    One matcher, two views. The set-returning function above is the whole
    contract most callers want; the frame resolver needs to know whether a
    position came from a form carrying a residue letter, because only those can
    distinguish one proteoform frame from another."""
    if not text:
        return {}
    runs = _RE_DNA_RUN.findall(text)
    clean = _RE_DNA_RUN.sub(" ", text)
    dna_heavy = sum(len(r) for r in runs) > 0.3 * len(text)

    out: dict[int, set[str]] = {}

    def _add(n: int, form: str) -> None:
        out.setdefault(n, set()).add(form)

    def _confirmed(letter: str, n: int) -> bool:
        if not sequence:
            return True
        return n <= len(sequence) and sequence[n - 1].upper() == letter.upper()

    for rx, table, form in (
        (_RE_FULL, _AA_FULL, "full"),
        (_RE_THREE, _AA_THREE, "three"),
    ):
        for m in rx.finditer(clean):
            n = int(m.group(2))
            if 0 < n <= _MAX_RESIDUE and _confirmed(table[m.group(1).lower()], n):
                _add(n, form)
    for m in _RE_POSITIONAL.finditer(clean):  # no letter to confirm
        n = int(m.group(1))
        if 0 < n <= _MAX_RESIDUE:
            _add(n, "positional")
    for rx, form in (
        (_RE_SPAN, "span"),
        (_RE_DELTA_SPAN, "delta_span"),
        (_RE_LIST, "list"),
    ):  # these claim BOTH numbers
        for m in rx.finditer(clean):
            for g in (1, 2):
                n = int(m.group(g))
                if 0 < n <= _MAX_RESIDUE:
                    _add(n, form)
    for m in _RE_AA_TIGHT.finditer(clean):
        n = int(m.group(1))
        if 0 < n <= _MAX_RESIDUE:
            _add(n, "aa_tight")

    for rx_code in (_RE_CODE, _RE_CODE_SPACED):
        for m in rx_code.finditer(clean):
            letter, n = m.group(1).upper(), int(m.group(2))
            if not 0 < n <= _MAX_RESIDUE:
                continue
            if sequence:
                if n <= len(sequence) and sequence[n - 1].upper() == letter:
                    _add(n, "code")  # the sequence confirms a residue, not noise
            elif not dna_heavy:
                _add(n, "code")  # nothing to verify against; distrust DNA blocks
    return {n: frozenset(forms) for n, forms in out.items()}


def boost_residue_clips(pool, *, sequence: str, topology: str) -> dict[str, set[int]]:
    """Raise the score of every clip that names an EXTRACELLULAR residue, so it
    survives the selector's menu cap. Mutates ``pool`` in place and returns
    ``{clip_key: positions named}`` for the clips it lifted.

    ``select_clips`` keeps only the top clips by score, which on a well-studied
    gene throws away most of the evidence (one run: 1193 clips -> 100). A clip
    that pins a real insertion is then never shown to the selector, so reading
    residues at all is pointless unless the clip carrying one survives the cut.

    The return value is the diagnostic half. A run that logged only "boosted
    1/123" for a gene whose decisive paper HAD been retrieved left no way to tell
    whether that one clip was the relevant one, and the pool is not persisted, so
    the question could not be answered afterwards.

    A clip qualifies only when it BOTH names an extracellular residue AND reads as
    describing an insertion; see the comment in the loop for why the residue alone
    lets another protein's phosphosite through. The cost is that a pure
    primer-table row, which carries a label but no prose, is no longer lifted --
    acceptable, because such a row is a wall of nucleotides that the model cannot
    quote a site out of, and it still reaches the pool through draft ranking.

    Only extracellular positions count -- a residue in the cytoplasmic tail or a
    TM helix is not a surface tag site. Both ``n`` and ``n - 1`` are tested
    against the topology because papers differ on whether a label names the
    residue before or after the junction.

    This is a tag-site-only pre-pass: the shared selector is untouched, so the
    internalization track keeps its own ranking."""
    if not pool or not sequence or not topology:
        return {}

    def _extracellular(n: int) -> bool:
        return any(
            1 <= pos <= len(topology) and topology[pos - 1] == "O" for pos in (n, n - 1)
        )

    hits: dict[str, set[int]] = {}
    for key, clip in pool.items():
        text = " ".join(
            filter(None, (getattr(clip, "quote", None), getattr(clip, "context_excerpt", None)))
        )
        # A residue alone is not enough. Sequence confirmation rules out tokens the
        # protein does not have, but not text that names a residue it DOES have
        # while talking about something else entirely -- another protein's
        # phosphosite ("FAK Y397", and "phosphorylation of FAK at tyrosine 397"),
        # a spectrophotometry reading ("A260/A280 ratio"), a variant in a different
        # gene. All of those were boosted on one ITGB1 run, where residue 397 is
        # indeed Y and 280 is indeed A. Requiring the clip to describe an insertion
        # as well separated them cleanly: 3 of 3 real clips kept, 0 of 6 noise.
        if not quote_is_probative(text):
            continue
        named = {n for n in residue_mentions(text, sequence=sequence) if _extracellular(n)}
        if named:
            hits[key] = named
    if not hits:
        return {}
    # Lift boosted clips above every unboosted one while keeping their order
    # among themselves, so this re-ranks without discarding the pool's own signal.
    ceiling = max((getattr(c, "score", 0.0) or 0.0) for c in pool.values())
    for key in hits:
        pool[key].score = (getattr(pool[key], "score", 0.0) or 0.0) + ceiling + 1.0
    return hits


# Accumulated per-gene discovery. Derived data, regenerable, and it grows with
# every run — gitignored alongside the other local caches.
DISCOVERY_CACHE_DIR = Path(__file__).resolve().parents[3].parent / "data/external/tag_site_discovery"


def load_discovery_cache(gene_symbol: str, *, cache_dir: Path | None = None) -> dict[str, Paper]:
    """Papers previous runs discovered for this gene. Missing or unreadable cache
    is an empty dict — a stale local file must never take down a run."""
    path = Path(cache_dir or DISCOVERY_CACHE_DIR) / f"{gene_symbol}.json"
    try:
        raw = json.loads(path.read_text())
    except Exception:  # noqa: BLE001 - absent, corrupt, or unreadable
        return {}
    out: dict[str, Paper] = {}
    for sid, payload in (raw or {}).items():
        try:
            out[sid] = Paper.model_validate(payload)
        except Exception:  # noqa: BLE001 - drop rows an older schema wrote
            continue
    return out


def save_discovery_cache(
    gene_symbol: str, papers: dict[str, Paper], *, cache_dir: Path | None = None
) -> None:
    """Persist this gene's accumulated discovery. Best-effort: a cache write
    failing is not a reason to lose a completed run."""
    path = Path(cache_dir or DISCOVERY_CACHE_DIR) / f"{gene_symbol}.json"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({sid: p.model_dump(mode="json") for sid, p in papers.items()}, indent=1)
        )
    except Exception:  # noqa: BLE001
        logger.warning("could not write discovery cache for %s", gene_symbol)


_WEB_CACHE_TTL_DAYS = 30


def _intent_sha(intent: str | None) -> str:
    return hashlib.sha256((intent or "").encode("utf-8")).hexdigest()[:16]


def load_web_search_cache(
    gene_symbol: str,
    *,
    model: str,
    max_uses: int,
    intent: str | None = None,
    ttl_days: int = _WEB_CACHE_TTL_DAYS,
    cache_dir: Path | None = None,
) -> list[str] | None:
    """Return cached web-search paper IDs (possibly ``[]`` for a negative hit),
    or ``None`` on cache miss / expired / different model, max_uses, or intent."""
    path = Path(cache_dir or DISCOVERY_CACHE_DIR) / f"{gene_symbol.upper()}.web_cache.json"
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(raw, dict):
        return None
    if raw.get("model") != model or raw.get("max_uses") != max_uses:
        return None
    if intent is not None and raw.get("intent_sha") != _intent_sha(intent):
        return None
    ran_at = raw.get("ran_at")
    if not isinstance(ran_at, (int, float)):
        return None
    if (time.time() - float(ran_at)) > ttl_days * 86_400:
        return None
    ids = raw.get("paper_ids")
    return [str(x) for x in ids] if isinstance(ids, list) else []


def save_web_search_cache(
    gene_symbol: str,
    paper_ids: list[str],
    *,
    model: str,
    max_uses: int,
    intent: str | None = None,
    cache_dir: Path | None = None,
) -> None:
    """Record a completed web-search scout call (including 0-hit negative cache)."""
    path = Path(cache_dir or DISCOVERY_CACHE_DIR) / f"{gene_symbol.upper()}.web_cache.json"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "model": model,
            "max_uses": max_uses,
            "intent_sha": _intent_sha(intent) if intent is not None else None,
            "ran_at": int(time.time()),
            "paper_ids": sorted(set(paper_ids)),
        }
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        logger.warning("could not write tag-site web_search cache for %s: %s", gene_symbol, exc)
