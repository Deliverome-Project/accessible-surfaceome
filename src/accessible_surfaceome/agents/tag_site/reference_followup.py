"""Deterministic ($0-LLM) 1-hop construct-citation follow-up from PMC JATS XML.

Many modern cell-biology papers *use* an ecto-tagged construct without repeating
its insertion residue, writing e.g. ``"BLAP-KCNN3 was generated as previously
described [18]"`` (observed on KCNN3/PMC3429460 in the L1 enrichment pilot).
Because EuropePMC full-text JATS XML already carries structured ``<ref-list>``
entries with PMIDs and DOIs, we can follow those construct citations 1 hop
deterministically and hydrate up to ``max_refs`` original Methods papers.
"""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from collections.abc import Iterable, Mapping
from typing import Any

from accessible_surfaceome.tools._shared.http import CachedHTTP

from .literature_discovery import quote_is_probative

logger = logging.getLogger(__name__)

_NCBI_PMC_EFETCH_URL = (
    "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
    "?db=pmc&id={pmcid}&retmode=xml"
)
_EUROPEPMC_FULLTEXT_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/{pmcid}/fullTextXML"

# Phrases signaling that a tagged construct's construction lives in a cited paper.
_PREV_DESCRIBED_RE = re.compile(
    r"(?:"
    r"previously\s+(?:described|reported|generated|characterized|constructed|published)|"
    r"(?:described|reported|generated|constructed)\s+(?:previously|elsewhere|before|earlier)|"
    r"as\s+described\s+(?:in|by)|"
    r"kind\s+gift\s+(?:of|from)|generously\s+provided\s+by|obtained\s+from"
    r")",
    re.IGNORECASE,
)
# Bracketed numeric citations like "[18]", "[ 25 ]", "[18,19]", "[18-20]" or "ref 18"
_BRACKET_NUM_RE = re.compile(
    r"\[\s*(\d{1,3}(?:\s*[,–\-]\s*\d{1,3})*)\s*\]|\brefs?\.?\s*(\d{1,3})\b",
    re.I,
)
# Author-year citations like "(Gao et al., 2008)" or "(Smith and Jones, 2012)"
_AUTHOR_YEAR_RE = re.compile(
    r"\(([A-Z][A-Za-z\-]{2,25})(?:\s+(?:et\s+al\.?|and\s+[A-Z][A-Za-z\-]+))?,\s*((?:19|20)\d{2}[a-z]?)\)"
)
_TAG_TITLE_HINT_RE = re.compile(
    r"\b(?:tag|tagged|epitope|blap|biotin|bungarotoxin|bbs|alfa|hibit|phluorin|"
    r"insert|insertion|extracellular\s+loop|topology|trafficking|surface|endocyt|"
    r"channel|transporter|receptor)\b",
    re.IGNORECASE,
)


def extract_citation_cues(text: str) -> tuple[set[int], set[tuple[str, str]]]:
    """Return ``(ref_numbers, author_year_pairs)`` referenced in ``text``."""
    nums: set[int] = set()
    for m in _BRACKET_NUM_RE.finditer(text):
        grp = m.group(1) or m.group(2) or ""
        for part in re.split(r"\s*,\s*", grp):
            if "-" in part or "–" in part:
                bounds = re.split(r"\s*[-–]\s*", part)
                if len(bounds) == 2 and bounds[0].isdigit() and bounds[1].isdigit():
                    lo, hi = int(bounds[0]), int(bounds[1])
                    if 1 <= lo <= hi <= lo + 4:
                        nums.update(range(lo, hi + 1))
            elif part.isdigit():
                nums.add(int(part))
    author_years: set[tuple[str, str]] = set()
    for m in _AUTHOR_YEAR_RE.finditer(text):
        author_years.add((m.group(1).lower(), m.group(2)[:4]))
    return nums, author_years


def parse_jats_references(xml_text: str) -> list[dict[str, Any]]:
    """Parse ``<ref>`` entries from PMC JATS XML into structured reference dicts."""
    if not xml_text or "<ref" not in xml_text:
        return []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    refs: list[dict[str, Any]] = []
    for idx, ref in enumerate(root.iter("ref"), start=1):
        ref_id = (ref.attrib.get("id") or "").strip()
        label_el = ref.find("label")
        label_txt = "".join(label_el.itertext()).strip().rstrip(".") if label_el is not None else ""
        ref_num: int | None = None
        if label_txt.isdigit():
            ref_num = int(label_txt)
        else:
            m = re.search(r"(\d+)$", ref_id)
            ref_num = int(m.group(1)) if m else idx

        pmid: str | None = None
        doi: str | None = None
        for pub_id in ref.iter("pub-id"):
            ptype = (pub_id.attrib.get("pub-id-type") or "").lower()
            val = "".join(pub_id.itertext()).strip()
            if ptype == "pmid" and val.isdigit():
                pmid = val
            elif ptype == "doi" and "/" in val:
                doi = val

        surnames = [
            "".join(el.itertext()).strip().lower()
            for el in ref.iter("surname")
            if "".join(el.itertext()).strip()
        ]
        year_el = ref.find(".//year")
        year = ("".join(year_el.itertext()).strip()[:4]) if year_el is not None else ""
        title_el = ref.find(".//article-title")
        title = " ".join("".join(title_el.itertext()).split()) if title_el is not None else ""
        if pmid or doi:
            refs.append(
                {
                    "num": ref_num,
                    "pmid": pmid,
                    "doi": doi,
                    "surnames": surnames,
                    "year": year,
                    "title": title,
                }
            )
    return refs


def find_construct_followup_paper_ids(
    clips: Iterable[Any],
    *,
    papers_by_id: Mapping[str, Any],
    http: CachedHTTP,
    max_refs: int = 3,
    max_source_papers: int = 4,
) -> list[str]:
    """Identify up to ``max_refs`` new PMID/DOI identifiers cited by construct
    clips that say a tagged protein was "previously described [N]" (or cite an
    author-year).

    Only inspects already-known PMC full-text papers (cached in ``http``), never
    calls an LLM, and skips any paper already in ``papers_by_id``.
    """
    if not isinstance(http, CachedHTTP) or max_refs <= 0:
        return []

    known_pmids = {
        str(getattr(p, "pmid", "")) for p in papers_by_id.values() if getattr(p, "pmid", None)
    }
    known_dois = {
        str(getattr(p, "doi", "")).strip().lower()
        for p in papers_by_id.values()
        if getattr(p, "doi", None)
    }

    cues_by_pmc: dict[str, tuple[set[int], set[tuple[str, str]]]] = {}
    for clip in clips:
        sid = getattr(clip, "source_id", None)
        if not sid:
            spans = getattr(clip, "spans", None) or []
            sid = spans[0].source.source_id if spans and spans[0].source else None
        if not sid:
            continue
        paper = papers_by_id.get(sid)
        pmc_id = getattr(paper, "pmc_id", None) if paper is not None else None
        if not pmc_id:
            continue
        text = " ".join(
            filter(
                None,
                (
                    getattr(clip, "quote", None),
                    getattr(clip, "context_excerpt", None),
                    *(getattr(sp, "quote", None) for sp in (getattr(clip, "spans", None) or [])),
                ),
            )
        )
        if not quote_is_probative(text):
            continue
        nums, ays = extract_citation_cues(text)
        if not nums and not ays:
            continue
        if not _PREV_DESCRIBED_RE.search(text) and not nums:
            continue
        bucket = cues_by_pmc.setdefault(str(pmc_id), (set(), set()))
        bucket[0].update(nums)
        bucket[1].update(ays)
        if len(cues_by_pmc) >= max_source_papers:
            break

    candidates: list[tuple[int, str]] = []
    seen_out: set[str] = set()
    for pmc_id, (nums, ays) in cues_by_pmc.items():
        if len(candidates) >= max_refs * 2:
            break
        xml_text = ""
        for url, source_label in (
            (_NCBI_PMC_EFETCH_URL.format(pmcid=pmc_id), "ncbi_pmc_fulltext"),
            (_EUROPEPMC_FULLTEXT_URL.format(pmcid=pmc_id), "europepmc_fulltext"),
        ):
            try:
                candidate_xml = http.get_text(url, source=source_label, ttl_days=30)
            except Exception as exc:  # noqa: BLE001
                logger.debug(
                    "construct ref follow-up XML fetch skipped for %s (%s): %s",
                    pmc_id,
                    source_label,
                    exc,
                )
                continue
            if candidate_xml and "<ref" in candidate_xml:
                xml_text = candidate_xml
                break
        if not xml_text:
            continue
        refs = parse_jats_references(xml_text)
        for ref in refs:
            matched = False
            if ref["num"] in nums:
                matched = True
            elif ays and ref["year"] and ref["surnames"]:
                first_author = ref["surnames"][0]
                if any(a == first_author and y == ref["year"] for a, y in ays):
                    matched = True
            if not matched:
                continue
            ident = f"PMID:{ref['pmid']}" if ref["pmid"] else f"DOI:{ref['doi']}"
            if ref["pmid"] and ref["pmid"] in known_pmids:
                continue
            if ref["doi"] and ref["doi"].strip().lower() in known_dois:
                continue
            if ident in seen_out:
                continue
            seen_out.add(ident)
            priority = 0 if _TAG_TITLE_HINT_RE.search(ref["title"]) else 1
            candidates.append((priority, ident))

    candidates.sort(key=lambda x: x[0])
    return [ident for _, ident in candidates[:max_refs]]
