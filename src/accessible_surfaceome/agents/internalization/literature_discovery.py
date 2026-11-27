"""Discover internalization papers + sentence/clip relevance scoring.

Combines EuropePMC (broad, modality/measurement, citation-sorted kinetics, and
constitutive/negative facets) with minimal-free-text PubTator entity searches,
merged by ``paper_source_id`` and backed by an optional local discovery cache.
Also supplies ``internalization_relevance`` (for ``extract_paper_drafts``) and
``boost_internalization_clips`` so quantitative kinetic and direct-assay clips
rise above section preambles instead of getting truncated.
"""

from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from accessible_surfaceome.env import REPO_ROOT
from accessible_surfaceome.tools._shared.europepmc import (
    europepmc_bulk_by_pmid,
    europepmc_search,
    paper_from_europepmc,
)
from accessible_surfaceome.tools._shared.http import CachedHTTP
from accessible_surfaceome.tools._shared.models import (
    EvidenceClaimDraft,
    IdentifierBundle,
    Paper,
    paper_source_id,
)
from accessible_surfaceome.tools._shared.pubtator import (
    build_gene_entity_query,
    pubtator_search,
)

logger = logging.getLogger(__name__)

DISCOVERY_CACHE_DIR = REPO_ROOT / "data" / "external" / "internalization_discovery"

# Broad, modality-agnostic internalization terms.
_INTERNALIZATION_TERMS = (
    'internali* OR endocytos* OR "receptor-mediated endocytosis" OR '
    '"receptor-mediated uptake" OR "receptor internalization" OR '
    '"receptor recycling" OR "internalization rate" OR "endocytic rate" OR '
    '"uptake kinetics" OR "surface half-life" OR "clathrin-mediated" OR '
    '"caveolin-mediated" OR macropinocytosis'
)

# Measurement & delivery-modality query spanning antibodies/ADCs, oligos/GalNAc,
# LNPs, AAV/viral entry, peptides, and explicit assay/negative-control language.
_MEASUREMENT_TERMS = (
    '"receptor-mediated endocytosis" OR "receptor internalization" OR '
    '"internalization assay" OR "internalization kinetics" OR '
    '"internalization rate" OR "receptor endocytosis" OR '
    '"antibody internalization" OR "antibody uptake" OR "ADC internalization" OR '
    '"uptake and turnover" OR '
    '"oligonucleotide uptake" OR "siRNA uptake" OR "antisense oligonucleotide" OR '
    'GalNAc OR "lipid nanoparticle" OR "nanoparticle uptake" OR '
    '"adeno-associated virus" OR "viral entry" OR "entry receptor" OR '
    '"cell-penetrating peptide" OR "peptide uptake" OR '
    '"surface biotinylation" OR "acid wash" OR "acid strip" OR pHrodo OR '
    '"constitutive internalization" OR "constitutive endocytosis" OR '
    '"non-internalizing" OR "poorly internalized"'
)

# Quantitative-kinetics query run under CITATION sort (CITED desc) to surface
# classic rate-constant / half-life papers that recency sort buries.
_KINETICS_TERMS = (
    '"rate constant" OR "internalization rate" OR "endocytic rate" OR '
    '"half-time" OR "half-life" OR "t1/2" OR "percent internalized" OR '
    '"% internalized" OR "per min" OR "per hour" OR "%/min" OR '
    '"constitutive internalization" OR "constitutive endocytosis"'
)

_MAX_PER_SOURCE = 50
_MAX_KINETICS = 40
_MAX_CLASSIC_CITED = 30

# Ultra-short or generic protein-mass aliases (e.g. TR, T9, p90, M1, C1) and
# common English/lab 3-letter words (e.g. BAR on ADRB2, TAG, MAP, NET, SET)
# that collide with thousands of unrelated papers in EuropePMC queries.
_NOISY_SHORT_ALIAS_RE = re.compile(r"^(?:[A-Za-z]{1,2}\d?|p\d{2,3})$")
_COLLISION_ALIAS_WORDS: frozenset[str] = frozenset({
    "act", "add", "age", "aid", "aim", "air", "all", "and", "ant", "any", "arc",
    "are", "arm", "art", "ask", "ate", "avg", "bad", "bag", "ban", "bar", "bat",
    "bay", "bed", "bet", "bid", "big", "bin", "bio", "bit", "box", "boy", "bud",
    "bug", "bus", "but", "buy", "can", "cap", "car", "cat", "cell", "cut", "dad",
    "dam", "day", "den", "did", "die", "dig", "dim", "dip", "dna", "dog", "dot",
    "dry", "due", "ear", "eat", "egg", "end", "era", "eve", "eye", "fab", "fan",
    "far", "fat", "fbs", "fed", "fee", "few", "fig", "fin", "fit", "fix", "fly",
    "for", "fox", "fun", "fur", "gap", "gas", "gdp", "gel", "get", "got", "gtp",
    "gum", "gun", "gut", "guy", "had", "ham", "has", "hat", "her", "hid", "him",
    "hip", "his", "hit", "hot", "how", "hub", "hue", "hug", "ice", "igg", "ill",
    "ink", "inn", "ion", "its", "jam", "jar", "jaw", "jet", "job", "jog", "joy",
    "key", "kid", "kin", "kit", "lab", "lac", "lad", "lag", "lap", "law", "lay",
    "led", "leg", "let", "lid", "lie", "lip", "lit", "log", "lot", "low", "mad",
    "man", "map", "mat", "max", "may", "men", "met", "mid", "min", "mix", "mob",
    "mod", "mom", "mop", "mud", "mug", "nap", "net", "new", "nil", "nod", "nor",
    "not", "now", "nut", "oak", "oar", "odd", "off", "oil", "old", "one", "opt",
    "orb", "ore", "our", "out", "ova", "owe", "owl", "own", "pad", "pan", "par",
    "pat", "paw", "pay", "pbs", "pcr", "pea", "peg", "pen", "pep", "per", "pet",
    "pie", "pig", "pin", "pit", "pod", "pop", "pot", "pro", "pub", "pun", "pup",
    "put", "rad", "rag", "ram", "ran", "rap", "rat", "raw", "ray", "red", "ref",
    "rep", "rib", "rid", "rig", "rim", "rip", "rna", "rob", "rod", "rot", "row",
    "rub", "rug", "run", "rut", "sad", "sag", "sap", "sat", "saw", "say", "sea",
    "sec", "see", "set", "sew", "sex", "she", "shy", "sin", "sip", "sir", "sis",
    "sit", "six", "ski", "sky", "sob", "sod", "son", "sow", "soy", "spa", "spy",
    "std", "sub", "sum", "sun", "sup", "tab", "tag", "tan", "tap", "tar", "tax",
    "tea", "ten", "the", "thy", "tic", "tie", "tin", "tip", "toe", "ton", "too",
    "top", "tot", "tow", "toy", "try", "tub", "tug", "two", "urn", "use", "van",
    "vat", "vet", "via", "vow", "wad", "wag", "war", "was", "wax", "way", "web",
    "wed", "wee", "wet", "who", "why", "wig", "win", "wit", "woe", "wok", "won",
    "woo", "wow", "yak", "yam", "yap", "yaw", "yea", "yen", "yes", "yet", "yew",
    "yin", "yip", "yok", "you", "zap", "zed", "zen", "zip", "zoo",
})

# --- Sentence / clip relevance patterns for extract_paper_drafts + menu boost ---

_QUANT_KINETIC_RE = re.compile(
    r"(?:"
    r"\bt\s*1/2\b|\bt½\b|half[-\s](?:life|time)\b|rate\s+constant|\bk_?e\b|"
    r"\d+(?:\.\d+)?\s*(?:%|percent)\s*(?:per\s*(?:min|minute|h|hr|hour)|/\s*(?:min|h|hr))\b|"
    r"\d+(?:\.\d+)?\s*(?:per\s*(?:min|minute|h|hr|hour)|min\s*[\-−]\s*1|h\s*[\-−]\s*1|/\s*min|/\s*h)\b|"
    r"\d+(?:\.\d+)?\s*(?:%|percent)\s+(?:of\s+(?:surface\s+)?(?:receptors?|pool|bound|label\w*)\s+)?"
    r"(?:was\s+|were\s+)?(?:internali[sz]ed|endocytosed|taken\s+up|protected|cleared|depleted)|"
    r"(?:internali[sz]\w+|endocytos\w+|uptake)\s+(?:of\s+)?(?:about\s+|approximately\s+|~|>\s*|<\s*)?"
    r"\d+(?:\.\d+)?\s*(?:%|percent|min|minutes|h|hr|hours|fold|×|x\b)|"
    r"\d+(?:\.\d+)?[-\s]?fold\s+(?:higher|lower|faster|slower|increase|decrease|greater|less)\b"
    r")",
    re.IGNORECASE,
)

_DIRECT_ASSAY_RE = re.compile(
    r"(?:"
    r"acid[-\s](?:strip|wash)|mesna|surface\s+biotinylat\w*|sulfo[-\s]nhs|"
    r"phrodo|phluorin|pulse[-\s]chase|antibody\s+feeding|surface\s+quench\w*|"
    r"internali[sz]ation\s+(?:assay|kinetics|rate|curve|time[-\s]?course|half[-\s]?(?:life|time))|"
    r"endocyt(?:ic|osis)\s+(?:rate|assay|kinetics|inhibitor)|"
    r"receptor[-\s]mediated\s+(?:endocytosis|uptake|internali[sz]ation)|"
    r"flow\s+cytometr\w*|confocal|live[-\s]cell\s+imaging|radioligand|immunopet|"
    r"\b(?:4\s*°\s*c|4°c|37\s*°\s*c|37°c)\b|"
    r"clathrin|caveolin|caveolae|macropinocytosis|dynamin|dynasore|pitstop|filipin|"
    r"recycling\s+(?:endosome|rate|half[-\s]?(?:life|time)|assay)|"
    r"transcytosis|lysosom\w*\s+(?:degrad|traffick|deliver|colocal)"
    r")",
    re.IGNORECASE,
)

_MODE_AND_DIRECTION_RE = re.compile(
    r"(?:"
    r"constitutive(?:ly)?\s+(?:internali[sz]|endocytos|recycl|turnover)|"
    r"\bbasal\s+(?:internali[sz]|endocytos|uptake)|unstimulated|"
    r"without\s+(?:added\s+)?(?:ligand|agonist|antibody)|in\s+the\s+absence\s+of\s+(?:ligand|agonist)|"
    r"ligand[-\s](?:induced|driven|dependent|independent|stimulated)|"
    r"agonist[-\s](?:induced|driven|dependent|stimulated)|"
    r"antibody[-\s](?:induced|driven|mediated)|adc\s+internali[sz]|"
    r"(?:did\s+not|failed\s+to|does\s+not|rarely|poorly|slowly|rapidly|efficiently|briskly)\s+"
    r"(?:internali[sz]\w*|endocytos\w*)|"
    r"non[-\s]internali[sz]ing|negligible\s+(?:internali[sz]ation|endocytosis|uptake)|"
    r"endogenous(?:ly)?|overexpress\w*|knock[-\s]?in|knockdown|knockout"
    r")",
    re.IGNORECASE,
)

_BACKGROUND_BOILERPLATE_RE = re.compile(
    r"\b(?:is\s+well\s+known\s+to|has\s+been\s+widely\s+used\s+as|in\s+this\s+review|"
    r"here\s+we\s+review|therapeutic\s+potential\s+of|promising\s+target\s+for)\b",
    re.IGNORECASE,
)


def _alias_or(aliases: list[str]) -> str:
    """OR-join aliases, PHRASE-quoting any multi-word alias."""
    parts = [f'"{a}"' if " " in a else a for a in sorted({a.strip() for a in aliases if a and a.strip()})]
    return " OR ".join(parts)


def _is_noisy_short_alias(alias: str, *, primary_symbol: str) -> bool:
    s = alias.strip()
    if not s or s.upper() == primary_symbol.upper():
        return False
    if " " in s:
        return False
    if s.lower() in _COLLISION_ALIAS_WORDS:
        return True
    return bool(_NOISY_SHORT_ALIAS_RE.match(s))


_PAREN_NAME_RE = re.compile(r"\(([^()]{5,60})\)")
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


def _is_disease_alias(name: str) -> bool:
    return bool(_DISEASE_ALIAS_RE.search(name))


def _uniprot_protein_names(uniprot_acc: str | None, http: Any) -> list[str]:
    """Read UniProt's recommended + alternative full/short protein names from
    the already-cached UniProt JSON entry (zero extra network calls after
    ``resolve_by_hgnc_id``). Rescues classic common names missing from HGNC
    (e.g. 'Beta-2 adrenergic receptor' for ADRB2, 'LDL receptor' for LDLR)."""
    if not uniprot_acc or not isinstance(http, CachedHTTP):
        return []
    try:
        data = http.get_json(
            f"https://rest.uniprot.org/uniprotkb/{uniprot_acc}.json",
            source="uniprot_entry",
            ttl_days=30,
        )
    except Exception:  # noqa: BLE001
        return []
    desc = data.get("proteinDescription") if isinstance(data, dict) else None
    if not isinstance(desc, dict):
        return []
    names: list[str] = []

    def _collect(block: Any) -> None:
        if not isinstance(block, dict):
            return
        full = (block.get("fullName") or {}).get("value")
        if isinstance(full, str) and 4 <= len(full.strip()) <= 65:
            names.append(full.strip())
        for sh in block.get("shortNames") or []:
            val = sh.get("value") if isinstance(sh, dict) else None
            if isinstance(val, str) and 3 <= len(val.strip()) <= 40:
                names.append(val.strip())

    _collect(desc.get("recommendedName"))
    for alt in desc.get("alternativeNames") or []:
        _collect(alt)
    return names


def _stem_without_trailing_num(name: str | None) -> str | None:
    """For specific multi-word receptor names like 'asialoglycoprotein receptor 1',
    also return the stem 'asialoglycoprotein receptor' used in classic papers."""
    if not name or " " not in name.strip():
        return None
    m = _TRAILING_NUM_RE.match(name.strip())
    if not m:
        return None
    stem = m.group(1).strip()
    if len(stem) < 12 or " " not in stem or _GENERIC_STEM_RE.match(stem):
        return None
    return stem


def _extract_previous_names(bundle: IdentifierBundle) -> list[str]:
    """Pull useful short protein names from HGNC ``previous_names`` (e.g.
    ``prostate-specific membrane antigen`` from ``folate hydrolase
    (prostate-specific membrane antigen) 1``) while skipping long comma-heavy
    archival HGNC descriptions."""
    out: list[str] = []
    for name in getattr(bundle, "previous_names", ()) or ():
        if not name:
            continue
        for inner in _PAREN_NAME_RE.findall(name):
            inner_clean = inner.strip()
            if inner_clean and "," not in inner_clean:
                out.append(inner_clean)
        clean = name.strip()
        if clean and "," not in clean and "(" not in clean and len(clean) <= 50:
            out.append(clean)
    return out


def clean_query_aliases(
    bundle: IdentifierBundle,
    *,
    extra_names: list[str] | None = None,
) -> list[str]:
    """Aliases for broad/measurement EuropePMC queries: primary symbol + full
    protein names (HGNC + UniProt + CD designation) + non-collision symbol
    aliases (drops 2-char / p90 / clinical-disease noise)."""
    stem = _stem_without_trailing_num(bundle.approved_name)
    raw = [
        bundle.hgnc_symbol,
        bundle.approved_name,
        stem,
        getattr(bundle, "cd_designation", None),
        *(extra_names or []),
        *(bundle.alias_names or []),
        *_extract_previous_names(bundle),
        *(bundle.aliases or []),
        *(bundle.previous_symbols or []),
    ]
    out: list[str] = []
    seen: set[str] = set()
    for a in raw:
        if not a or not a.strip():
            continue
        s = a.strip()
        if _is_noisy_short_alias(s, primary_symbol=bundle.hgnc_symbol):
            continue
        if s.lower() != (bundle.approved_name or "").lower() and _is_disease_alias(s):
            continue
        k = s.lower()
        if k not in seen:
            seen.add(k)
            out.append(s)
    return out


def kinetics_query_aliases(
    bundle: IdentifierBundle,
    *,
    extra_names: list[str] | None = None,
) -> list[str]:
    """Tight name-weighted aliases for the CITED-desc kinetics pass."""
    stem = _stem_without_trailing_num(bundle.approved_name)
    raw = [
        bundle.hgnc_symbol,
        bundle.approved_name,
        stem,
        getattr(bundle, "cd_designation", None),
        *(extra_names or []),
        *(bundle.alias_names or []),
        *_extract_previous_names(bundle),
    ]
    # Also include high-specificity >=4-char symbol aliases (e.g. PSMA, HER2, CXCR7, BCMA, CD71)
    for a in (*(bundle.aliases or []), *(bundle.previous_symbols or [])):
        if a and len(a.strip()) >= 4 and not _is_noisy_short_alias(a, primary_symbol=bundle.hgnc_symbol):
            raw.append(a)
    out: list[str] = []
    seen: set[str] = set()
    for a in raw:
        if not a or not a.strip():
            continue
        s = a.strip()
        if _is_noisy_short_alias(s, primary_symbol=bundle.hgnc_symbol):
            continue
        if s.lower() != (bundle.approved_name or "").lower() and _is_disease_alias(s):
            continue
        k = s.lower()
        if k not in seen:
            seen.add(k)
            out.append(s)
    return out


def build_internalization_query(aliases: list[str]) -> str:
    """Title/abstract-scoped EuropePMC broad internalization query.

    Scoping BOTH clauses to ``TITLE_ABS`` prevents PMC-OA full-text table and
    reference-list mentions from drowning classic MEDLINE-only kinetics papers
    and cuts triage noise by 3-10x on low-literature genes."""
    return f"(TITLE_ABS:({_alias_or(aliases)})) AND (TITLE_ABS:({_INTERNALIZATION_TERMS}))"


def build_measurement_query(aliases: list[str]) -> str:
    return f"(TITLE_ABS:({_alias_or(aliases)})) AND (TITLE_ABS:({_MEASUREMENT_TERMS}))"


def build_kinetics_query(aliases: list[str]) -> str:
    return f"(TITLE_ABS:({_alias_or(aliases)})) AND (TITLE_ABS:({_KINETICS_TERMS}))"


def build_classic_cited_query(aliases: list[str]) -> str:
    """Tight citation-sorted pass for foundational internalization papers whose
    abstracts report kinetics without using exact phrases like 'rate constant'."""
    return f"(TITLE_ABS:({_alias_or(aliases)})) AND (TITLE_ABS:(internali* OR endocytos*))"


def build_preprint_screen_query(aliases: list[str]) -> str:
    """Targeted $0 EuropePMC preprint pass (bioRxiv/medRxiv) searching full text
    so recent endocytosis methods/screen preprints that list a target only in
    Results/Tables (e.g. EndoNB) are discovered even when web_search is skipped."""
    return (
        f"SRC:PPR AND ({_alias_or(aliases)}) AND "
        '(TITLE_ABS:(internali* OR endocytos* OR "surface protein" OR "receptor uptake") OR "EndoNB")'
    )


def internalization_relevance(gene_names: list[str]) -> Callable[[str], float]:
    """Per-sentence relevance boost for ``extract_paper_drafts``.

    Lifts sentences reporting quantitative internalization kinetics, direct
    uptake assays, ±ligand comparisons, and non-internalizing controls ahead of
    section preambles so the per-section cap keeps findings instead of intros.
    """
    clean_names = [
        n.strip()
        for n in dict.fromkeys(gene_names)
        if n and len(n.strip()) >= 3
    ]
    name_pat = (
        re.compile(
            r"\b(?:" + "|".join(re.escape(n) for n in sorted(clean_names, key=len, reverse=True)) + r")\b",
            re.IGNORECASE,
        )
        if clean_names
        else None
    )

    def _score(sentence: str) -> float:
        if not sentence:
            return 0.0
        bonus = 0.0
        has_quant = bool(_QUANT_KINETIC_RE.search(sentence))
        has_assay = bool(_DIRECT_ASSAY_RE.search(sentence))
        has_mode = bool(_MODE_AND_DIRECTION_RE.search(sentence))
        if has_quant:
            bonus += 4.0
        if has_assay:
            bonus += 2.5
        if has_mode:
            bonus += 1.5
        if name_pat is not None and name_pat.search(sentence):
            bonus += 1.0
        if not (has_quant or has_assay) and _BACKGROUND_BOILERPLATE_RE.search(sentence):
            bonus -= 1.0
        return bonus

    return _score


def boost_internalization_clips(
    pool: dict[str, EvidenceClaimDraft],
    *,
    gene_names: list[str],
) -> int:
    """Ensure clips carrying quantitative kinetics or direct internalization
    assays outrank generic clips when the selector slices the pool into menus."""
    scorer = internalization_relevance(gene_names)
    boosted = 0
    for cid, draft in list(pool.items()):
        extra = scorer(draft.quote or "")
        if extra > 0:
            # Abstract clips from keep_abstract arrive without extract_paper_drafts'
            # relevance score — lift them identically so quant abstracts aren't buried.
            base = float(getattr(draft, "score", 0.0) or 0.0)
            target_score = max(base, 1.5 + extra)
            if target_score > base:
                pool[cid] = draft.model_copy(update={"score": target_score})
                boosted += 1
    return boosted


def count_high_signal_papers(
    pool: dict[str, EvidenceClaimDraft],
    *,
    gene_names: list[str],
) -> tuple[int, int]:
    """Return ``(n_assay_papers, n_quant_papers)`` in the clip pool — used by
    adaptive web-search gating to decide whether deterministic discovery already
    found strong direct/quantitative evidence."""
    assay_sources: set[str] = set()
    quant_sources: set[str] = set()
    for draft in pool.values():
        q = draft.quote or ""
        if _QUANT_KINETIC_RE.search(q):
            quant_sources.add(draft.source_id)
            assay_sources.add(draft.source_id)
        elif _DIRECT_ASSAY_RE.search(q):
            assay_sources.add(draft.source_id)
    return len(assay_sources), len(quant_sources)


def load_discovery_cache(
    gene_symbol: str, *, cache_dir: Path | None = None
) -> dict[str, Paper]:
    path = Path(cache_dir or DISCOVERY_CACHE_DIR) / f"{gene_symbol.upper()}.json"
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}
    out: dict[str, Paper] = {}
    if isinstance(raw, dict):
        for sid, payload in raw.items():
            try:
                out[sid] = Paper.model_validate(payload)
            except Exception:  # noqa: BLE001
                continue
    return out


def save_discovery_cache(
    gene_symbol: str,
    papers: dict[str, Paper],
    *,
    cache_dir: Path | None = None,
) -> None:
    if not papers:
        return
    path = Path(cache_dir or DISCOVERY_CACHE_DIR) / f"{gene_symbol.upper()}.json"
    merged = load_discovery_cache(gene_symbol, cache_dir=cache_dir)
    merged.update(papers)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {sid: p.model_dump(mode="json") for sid, p in sorted(merged.items())}
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        logger.warning("could not write internalization discovery cache for %s: %s", gene_symbol, exc)


_WEB_CACHE_TTL_DAYS = 30


def load_web_search_cache(
    gene_symbol: str,
    *,
    model: str,
    max_uses: int,
    ttl_days: int = _WEB_CACHE_TTL_DAYS,
    cache_dir: Path | None = None,
) -> list[str] | None:
    """Return cached web-search paper IDs (possibly ``[]`` for a negative hit),
    or ``None`` on cache miss / expired / different model or max_uses."""
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
    cache_dir: Path | None = None,
) -> None:
    """Record a completed web-search scout call (including 0-hit negative cache)."""
    path = Path(cache_dir or DISCOVERY_CACHE_DIR) / f"{gene_symbol.upper()}.web_cache.json"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "model": model,
            "max_uses": max_uses,
            "ran_at": int(time.time()),
            "paper_ids": sorted(set(paper_ids)),
        }
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        logger.warning("could not write internalization web_search cache for %s: %s", gene_symbol, exc)


def discover_internalization_papers(
    bundle: IdentifierBundle,
    *,
    http: CachedHTTP,
    retraction_index: Any,
    cached: dict[str, Paper] | None = None,
    citation_counts_out: dict[str, int] | None = None,
) -> dict[str, Paper]:
    uniprot_names = _uniprot_protein_names(getattr(bundle, "uniprot_acc", None), http)
    broad_aliases = clean_query_aliases(bundle, extra_names=uniprot_names)
    kinetics_aliases = kinetics_query_aliases(bundle, extra_names=uniprot_names)
    discovered: dict[str, Paper] = {}  # keyed on paper_source_id (PMC>PMID>DOI)

    def _record_rec(rec: dict[str, Any]) -> None:
        try:
            paper = paper_from_europepmc(
                rec, retraction_index=retraction_index, include_preprints=True
            )
        except LookupError:
            return
        if getattr(paper, "is_retracted", False):
            return
        sid = paper_source_id(paper)
        discovered.setdefault(sid, paper)
        if citation_counts_out is not None:
            raw_cited = rec.get("citedByCount")
            if isinstance(raw_cited, (int, float)) or (isinstance(raw_cited, str) and raw_cited.isdigit()):
                c = int(raw_cited)
                if c > citation_counts_out.get(sid, 0):
                    citation_counts_out[sid] = c

    # 1. EuropePMC broad + measurement/delivery/negative queries
    for query in (
        build_internalization_query(broad_aliases),
        build_measurement_query(broad_aliases),
    ):
        try:
            payload = europepmc_search(http=http, query=query, page_size=_MAX_PER_SOURCE)
        except Exception as exc:  # noqa: BLE001 — one query failing must not abort discovery
            logger.warning("EuropePMC query failed for %s: %s", bundle.hgnc_symbol, exc)
            continue
        for rec in payload.get("resultList", {}).get("result", []):
            _record_rec(rec)

    # 2. Citation-sorted passes: (a) quantitative kinetics terms, and (b) top
    # foundational internalization papers (rescues classics like Austin 2004
    # ERBB2 or Ciechanover 1983 TFRC whose abstracts omit 'rate constant').
    for query, limit in (
        (build_kinetics_query(kinetics_aliases), _MAX_KINETICS),
        (build_classic_cited_query(kinetics_aliases), _MAX_CLASSIC_CITED),
    ):
        try:
            payload = europepmc_search(
                http=http,
                query=query,
                page_size=limit,
                sort="CITED desc",
            )
            for rec in payload.get("resultList", {}).get("result", []):
                _record_rec(rec)
        except Exception as exc:  # noqa: BLE001
            logger.warning("EuropePMC cited query failed for %s: %s", bundle.hgnc_symbol, exc)

    # 2b. Targeted $0 EuropePMC preprint/screen pass (bioRxiv/medRxiv).
    try:
        payload = europepmc_search(
            http=http,
            query=build_preprint_screen_query(kinetics_aliases),
            page_size=15,
        )
        for rec in payload.get("resultList", {}).get("result", []):
            _record_rec(rec)
    except Exception as exc:  # noqa: BLE001
        logger.warning("EuropePMC preprint query failed for %s: %s", bundle.hgnc_symbol, exc)

    # 3. PubTator entity search with MINIMAL free text (overloading free-text terms
    # ANDs them and tanks recall). Dedup against ALL already-known PMIDs regardless
    # of whether the existing entry is keyed by PMC: or PMID:.
    known_pmids = {p.pmid for p in discovered.values() if getattr(p, "pmid", None)}
    pubtator_pmids: list[int] = []
    seen_pt: set[int] = set()
    for term in ("internalization", "endocytosis"):
        try:
            hits = pubtator_search(
                http=http,
                query=build_gene_entity_query(bundle.hgnc_symbol, term),
                sort="score desc",
            ).hits
        except Exception as exc:  # noqa: BLE001
            logger.warning("PubTator (%s) failed for %s: %s", term, bundle.hgnc_symbol, exc)
            continue
        for h in hits:
            pmid = getattr(h, "pmid", None)
            if pmid and pmid not in known_pmids and pmid not in seen_pt:
                seen_pt.add(pmid)
                pubtator_pmids.append(pmid)
                if len(pubtator_pmids) >= _MAX_PER_SOURCE:
                    break
        if len(pubtator_pmids) >= _MAX_PER_SOURCE:
            break

    if pubtator_pmids:
        for paper in europepmc_bulk_by_pmid(
            http=http, pmids=pubtator_pmids, retraction_index=retraction_index
        ):
            if not getattr(paper, "is_retracted", False):
                discovered.setdefault(paper_source_id(paper), paper)

    if cached:
        for sid, paper in cached.items():
            if not getattr(paper, "is_retracted", False):
                discovered.setdefault(sid, paper)

    return discovered
