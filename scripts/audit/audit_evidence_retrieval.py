"""Diagnostic: trace ``evidence_retrieval`` retrieval funnel for a gene.

Prints — per category, per discovery source, per paper — what got filtered
where, so we can tell whether 0-anchored categories failed at retrieval,
at the PMC-OA filter, at the fetch, or at hallmark extraction.

Usage:

    uv run python scripts/audit_evidence_retrieval.py P60033 surface_biotinylation western_blot_paired
"""

from __future__ import annotations

import logging
import sys
from collections import Counter

from accessible_surfaceome.env import load_env
from accessible_surfaceome.tools._shared.http import open_default_client
from accessible_surfaceome.tools._shared.retraction_watch import empty as _empty_retraction
from accessible_surfaceome.tools._shared.gene_gazetteer import (
    build_target_names,
    load_gazetteer,
)
from accessible_surfaceome.tools._shared.models import EvidenceCategory
from accessible_surfaceome.tools.gene_lookup import resolve
from accessible_surfaceome.tools.evidence_retrieval import (
    _CATEGORY_SPECS,
    _europepmc_discovery,
    _extract_snippets,
    _extract_target_mentions,
    _pubtator_discovery,
    _union_by_pmid,
)
from accessible_surfaceome.tools._shared.europepmc import fetch_fulltext


def trace_category(uniprot_acc: str, category: EvidenceCategory, http, max_papers: int = 5) -> None:
    print(f"\n========== {category} (uniprot={uniprot_acc}, max_papers={max_papers}) ==========")
    spec = _CATEGORY_SPECS[category]
    print(f"query_clauses: {spec.query_clauses}")
    print(f"pubtator_terms: {spec.pubtator_terms!r}")
    print(f"hallmark patterns: {len(spec.hallmark_patterns)} regex")
    print()

    bundle = resolve(uniprot_acc, http=http)
    retraction_index = _empty_retraction()
    target_names = build_target_names(
        bundle.hgnc_symbol, bundle.aliases, bundle.previous_symbols
    )
    gazetteer = load_gazetteer()

    pt = _pubtator_discovery(
        bundle=bundle, spec=spec, max_papers=max_papers,
        http=http, retraction_index=retraction_index,
    )
    ep = _europepmc_discovery(
        bundle=bundle, spec=spec, max_papers=max_papers,
        http=http, retraction_index=retraction_index,
    )
    union = _union_by_pmid(pt, ep)
    candidate_pool = [p for p in union if p.is_pmc_oa and p.pmc_id and not p.is_retracted]

    print(f"discovery — pubtator: {len(pt)} papers; europepmc: {len(ep)} papers; "
          f"union: {len(union)}; PMC-OA non-retracted: {len(candidate_pool)}")
    print()

    print("top 8 candidate-pool papers (PMC-OA only):")
    for i, p in enumerate(candidate_pool[:8]):
        print(f"  {i:2d}. PMID:{p.pmid} PMC:{p.pmc_id} | {p.year} | {p.title[:90]}")

    # Walk the backfill loop ourselves so we can see WHERE each paper drops out
    print()
    print("backfill trace:")
    fetch_cap = max(max_papers * 3, 8)
    snippet_paper_count = 0
    fetched = 0
    snippets_total: list = []
    for p in candidate_pool:
        if snippet_paper_count >= max_papers or fetched >= fetch_cap:
            break
        fetched += 1
        try:
            full = fetch_fulltext(http=http, pmcid=p.pmc_id or "", retraction_index=retraction_index)
        except Exception as exc:  # noqa: BLE001 — diagnostic
            print(f"  {p.pmc_id} FETCH FAIL: {type(exc).__name__}: {exc}")
            continue
        per_paper = _extract_snippets(
            paper=full, spec=spec, max_snippets=3,
            target_names=target_names, gazetteer=gazetteer,
        )
        already = {s.text for s in per_paper}
        tm = [m for m in _extract_target_mentions(
            full, spec=spec, target_names=target_names,
        ) if m.text not in already]
        section_counts = Counter(s.name for s in full.sections)
        sec_summary = ", ".join(f"{n}={c}" for n, c in section_counts.items())
        if per_paper or tm:
            snippet_paper_count += 1
            snippets_total.extend(per_paper + tm)
            print(f"  ✓ {p.pmc_id} sections=[{sec_summary}] → {len(per_paper)} hallmark + {len(tm)} target-mention snippets")
            for s in per_paper[:3]:
                print(f"      [hallmark] {s.section:15} score={s.score:.1f} {s.hallmark_phrase!r}")
                print(f"      └─ {s.text[:160]!r}")
            for s in tm[:3]:
                print(f"      [target_mention] {s.section:15} score={s.score:.1f}")
                print(f"      └─ {s.text[:160]!r}")
        else:
            print(f"  ✗ {p.pmc_id} sections=[{sec_summary}] → 0 snippets (after gene-proximity filter)")
    print()
    print(f"summary: {fetched} fetches, {snippet_paper_count}/{max_papers} papers contributed, "
          f"{len(snippets_total)} total snippets")


def main(argv: list[str] | None = None) -> int:
    load_env()
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s — %(message)s")
    args = argv if argv is not None else sys.argv[1:]
    if len(args) < 2:
        print("usage: audit_evidence_retrieval.py <uniprot_acc> <category> [<category> ...]")
        return 2
    uniprot_acc = args[0]
    categories = args[1:]

    http = open_default_client()
    try:
        for cat in categories:
            trace_category(uniprot_acc, cat, http=http)  # type: ignore[arg-type]
    finally:
        http.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
