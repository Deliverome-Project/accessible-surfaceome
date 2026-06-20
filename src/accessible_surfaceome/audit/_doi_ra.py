"""DOI Registration Agency lookup via the free DOI.org RA endpoint.

The DOI Foundation exposes an unauthenticated API that returns each
DOI's registration agency (``Crossref``, ``DataCite``, ``mEDRA``,
``JaLC``, ``KISTI``, ``ISTIC``, ...). Up to ~50 DOIs per call, comma-
separated. We cache results to ``data/external/doi_ra_cache.json`` so
repeat runs of figure builders never re-hit the endpoint.

Used by the paywall+bot-block analysis to distinguish "truly no OA"
from "OA exists on a DataCite-registered repo (arXiv, Zenodo, figshare,
institutional theses) that the production fetch chain — PMC JATS +
Unpaywall PDF — doesn't crawl". Unpaywall indexes Crossref-registered
journal articles; DataCite content sits outside its world.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import httpx

_RA_CACHE_PATH = (
    Path(__file__).resolve().parents[3] / "data/external/doi_ra_cache.json"
)
_BATCH_SIZE = 50
_USER_AGENT = (
    "accessible-surfaceome-doi-ra/1.0 "
    "(mailto:rebeccacarlson95@gmail.com)"
)

# Non-Crossref registration agencies. Their DOIs typically point at OA
# repositories (preprint servers, data archives, institutional thesis
# stores, regional aggregators) that Unpaywall doesn't index — so a
# prod-chain "fetch failed" against them means "we don't crawl that
# host", not "behind a paywall". Crossref-registered DOIs and unknown /
# unresolved DOIs are left in their original bucket.
NON_CROSSREF_OA_AGENCIES = frozenset({"DataCite", "JaLC", "ISTIC", "KISTI", "mEDRA"})


def _load_cache() -> dict[str, str]:
    if _RA_CACHE_PATH.exists():
        try:
            return json.loads(_RA_CACHE_PATH.read_text())
        except json.JSONDecodeError:
            return {}
    return {}


def _save_cache(cache: dict[str, str]) -> None:
    _RA_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _RA_CACHE_PATH.write_text(json.dumps(cache, indent=2, sort_keys=True))


def resolve_registration_agencies(dois: list[str]) -> dict[str, str]:
    """Map each input DOI to its registration agency.

    Caches results on disk; only DOIs not already in the cache hit the
    network. Returns ``"unknown"`` for DOIs the RA endpoint can't
    resolve (typo / withdrawn / not registered with any RA).
    """
    norm = [d.lower().strip() for d in dois if d]
    cache = _load_cache()
    needed = sorted({d for d in norm if d not in cache})
    if needed:
        with httpx.Client(timeout=30.0, headers={"User-Agent": _USER_AGENT}) as c:
            # Batch path.
            for i in range(0, len(needed), _BATCH_SIZE):
                chunk = needed[i:i + _BATCH_SIZE]
                try:
                    r = c.get("https://doi.org/doiRA/" + ",".join(chunk))
                    if r.status_code != 200:
                        continue
                    for entry in r.json():
                        doi = (entry.get("DOI") or "").lower()
                        if doi:
                            cache[doi] = (
                                entry.get("RA") or entry.get("status") or "unknown"
                            )
                except Exception:
                    continue
                time.sleep(0.3)
            # Some DOIs silently drop out of batch responses when the URL
            # gets long. Retry the stragglers individually.
            stragglers = [d for d in needed if d not in cache]
            for doi in stragglers:
                try:
                    r = c.get(f"https://doi.org/doiRA/{doi}")
                    if r.status_code != 200:
                        cache[doi] = "unknown"
                        continue
                    data = r.json()
                    entry = data[0] if data else {}
                    cache[doi] = (
                        entry.get("RA") or entry.get("status") or "unknown"
                    )
                except Exception:
                    cache[doi] = "unknown"
                time.sleep(0.15)
        _save_cache(cache)
    return {d: cache.get(d, "unknown") for d in norm}


def is_non_crossref_oa_agency(ra: str) -> bool:
    return ra in NON_CROSSREF_OA_AGENCIES
