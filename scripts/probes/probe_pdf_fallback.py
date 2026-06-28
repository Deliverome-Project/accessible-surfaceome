"""Probe the Unpaywall + PDF-parsing body fallback on real papers.

Network-only (Europe PMC + Unpaywall + publisher PDF hosts); spends **no**
Anthropic tokens. Discovers papers for a query via Europe PMC, then for those
WITHOUT a PMCID but WITH a DOI — exactly the papers that hit the new fallback —
runs lookup -> best-PDF -> download -> pdfplumber parse and prints a per-paper
quality report.

Usage:
    uv run python scripts/probe_pdf_fallback.py "CD20 MS4A1 rituximab" --max 25
    uv run python scripts/probe_pdf_fallback.py --doi 10.1182/blood-2010-09-305847
"""

from __future__ import annotations

import argparse
from typing import Any

from accessible_surfaceome.agents.plan_trim_select.abstract_triage import (
    _DEFAULT_UNPAYWALL_EMAIL,
    _lookup_oa_via_unpaywall,
    _pick_best_pdf_url,
)
from accessible_surfaceome.agents.plan_trim_select.pdf_parse import parse_pdf_to_sections
from accessible_surfaceome.env import load_env
from accessible_surfaceome.tools._shared.europepmc import europepmc_search
from accessible_surfaceome.tools._shared.http import CachedHTTP, open_default_client


def _discover(http: CachedHTTP, query: str, max_n: int) -> list[dict[str, Any]]:
    payload = europepmc_search(http=http, query=query, page_size=max_n)
    hits = (payload.get("resultList") or {}).get("result") or []
    out = []
    for r in hits:
        out.append(
            {
                "doi": r.get("doi"),
                "pmcid": r.get("pmcid"),
                "pmid": r.get("pmid"),
                "year": r.get("pubYear"),
                "title": (r.get("title") or "")[:80],
            }
        )
    return out


def _probe_doi(http: CachedHTTP, doi: str, email: str) -> dict[str, Any]:
    rec: dict[str, Any] = {"doi": doi}
    locs = _lookup_oa_via_unpaywall(doi, http=http, email=email)
    rec["n_oa_locations"] = len(locs)
    pdf_url = _pick_best_pdf_url(locs)
    rec["pdf_url"] = pdf_url
    if not pdf_url:
        rec["status"] = "no_oa_pdf"
        return rec
    try:
        data = http.get_bytes(pdf_url, source="unpaywall_pdf", ttl_days=180,
                              headers={"Accept": "application/pdf"})
    except Exception as exc:  # noqa: BLE001
        rec["status"] = f"download_error: {type(exc).__name__}: {exc}"
        return rec
    rec["n_bytes"] = len(data)
    rec["is_pdf"] = b"%PDF" in data[:1024]
    if not rec["is_pdf"]:
        rec["status"] = "not_a_pdf"
        return rec
    sections = parse_pdf_to_sections(data)
    rec["sections"] = [(s.name, len(s.text)) for s in sections]
    rec["body_chars"] = sum(len(s.text) for s in sections)
    rec["status"] = "parsed_ok" if sections else "parsed_empty"
    results = [s for s in sections if s.name == "results"]
    rec["sample"] = (results[0].text[:240] if results else
                     (sections[0].text[:240] if sections else ""))
    return rec


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("query", nargs="?", default="CD20 MS4A1 rituximab obinutuzumab")
    ap.add_argument("--max", type=int, default=25)
    ap.add_argument("--doi", action="append", default=[], help="probe explicit DOI(s)")
    args = ap.parse_args()

    load_env()
    email = _DEFAULT_UNPAYWALL_EMAIL
    with open_default_client() as http:
        if args.doi:
            dois = [(d, None, None) for d in args.doi]
        else:
            papers = _discover(http, args.query, args.max)
            # Target the fallback's actual population: no PMCID but has a DOI.
            dois = [(p["doi"], p["pmcid"], p["year"]) for p in papers
                    if p["doi"] and not p["pmcid"]]
            print(f"discovered {len(papers)} papers; "
                  f"{len(dois)} have a DOI but no PMCID (fallback population)\n")

        n_ok = n_pdf = 0
        for doi, pmcid, year in dois:
            rec = _probe_doi(http, doi, email)
            status = rec.get("status", "?")
            if rec.get("is_pdf"):
                n_pdf += 1
            if status == "parsed_ok":
                n_ok += 1
            print(f"[{year or '----'}] {doi}")
            print(f"    -> {status}; oa_locs={rec.get('n_oa_locations')} "
                  f"bytes={rec.get('n_bytes')} sections={rec.get('sections')}")
            if rec.get("sample"):
                print(f"    sample: {rec['sample']!r}")
        print(f"\nSUMMARY: {len(dois)} probed; {n_pdf} downloaded a PDF; "
              f"{n_ok} parsed into >=1 body section")


if __name__ == "__main__":
    main()
