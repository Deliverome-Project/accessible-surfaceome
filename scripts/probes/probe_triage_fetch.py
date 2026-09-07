"""Measure the triage body-fetch recovery rate on real papers — no model cost.

Runs the actual ``_fetch_body_drafts`` chain (PMC JATS → PMID→PMCID eLink →
Unpaywall OA PDF) over papers discovered via Europe PMC, and reports the
per-path breakdown. This is the integration check for issue #45's headline
metric without paying for LLM triage: it fetches every discovered paper rather
than only the ones a Haiku call would route to ``worth_fetching``.

Usage:
    uv run python scripts/probe_triage_fetch.py "MS4A1 OR CD20 surface" --max 30
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import UTC, datetime

from accessible_surfaceome.agents.plan_trim_select.abstract_triage import (
    TriageOutcome,
    apply_triage_outcomes,
    paper_source_id,
)
from accessible_surfaceome.agents.plan_trim_select.runner import _add_to_pool
from accessible_surfaceome.agents.plan_trim_select.schemas import AbstractTriageResponse
from accessible_surfaceome.env import load_env
from accessible_surfaceome.tools._shared.europepmc import europepmc_search
from accessible_surfaceome.tools._shared.http import open_default_client
from accessible_surfaceome.tools._shared.models import Paper
from accessible_surfaceome.tools._shared.retraction_watch import RetractionIndex


def _paper(rec: dict) -> Paper | None:
    pmid = rec.get("pmid")
    if not pmid:
        return None
    return Paper(
        pmid=int(pmid),
        pmc_id=rec.get("pmcid"),
        doi=rec.get("doi"),
        year=int(rec["pubYear"]) if rec.get("pubYear") else None,
        title=rec.get("title") or "(no title)",
        abstract=rec.get("abstractText"),
        retraction_checked_at=datetime.now(UTC),
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("query", nargs="?", default="MS4A1 OR CD20 surface")
    ap.add_argument("--max", type=int, default=30)
    ap.add_argument("--years", default="2008-2014", help="PUB_YEAR range filter")
    args = ap.parse_args()
    lo, hi = args.years.split("-")

    load_env()
    retraction = RetractionIndex()
    counts: Counter[str] = Counter()
    with open_default_client() as http:
        payload = europepmc_search(
            http=http,
            query=f"({args.query}) AND PUB_YEAR:[{lo} TO {hi}]",
            page_size=args.max,
        )
        recs = (payload.get("resultList") or {}).get("result") or []
        papers = [p for p in (_paper(r) for r in recs) if p]
        print(f"discovered {len(papers)} papers ({lo}-{hi})\n")

        # Drive the REAL action layer: mark every paper worth_fetching (skipping
        # the Haiku routing we don't need to test) and let apply_triage_outcomes
        # run the fetch chain + populate the pool + attribute fetch_source.
        papers_by_id = {paper_source_id(p): p for p in papers}
        outcomes = [
            TriageOutcome(
                paper_id=pid,
                response=AbstractTriageResponse(
                    paper_id=pid, decision="worth_fetching", reason="probe"
                ),
                usage=None,
                elapsed_s=0.0,
            )
            for pid in papers_by_id
        ]
        pool: dict = {}
        by_source: dict = defaultdict(list)
        actions = apply_triage_outcomes(
            outcomes,
            papers_by_id,
            pool=pool,
            by_source=by_source,
            http=http,
            retraction_index=retraction,
            add_to_pool_fn=_add_to_pool,
        )

        for a in actions:
            if a.fetched_body:
                counts[a.fetch_source or "?"] += 1
                print(f"  OK    {a.paper_id} via {a.fetch_source}: {a.drafts_added} drafts")
            else:
                counts["fell_back_to_abstract"] += 1

        n = len(papers)
        ok = counts["pmc_xml"] + counts["unpaywall_pdf"]
        print(f"\nSUMMARY ({n} papers): "
              f"pmc_xml={counts['pmc_xml']} unpaywall_pdf={counts['unpaywall_pdf']} "
              f"fell_back_to_abstract={counts['fell_back_to_abstract']} | "
              f"bodies recovered={ok}/{n} ({100 * ok // max(1, n)}%)")
        print(f"  pool now holds {len(pool)} clips across {len(by_source)} sources.")
        print(f"  Unpaywall-PDF recovered {counts['unpaywall_pdf']} papers the "
              f"PMC-only path would have dropped to abstract.")


if __name__ == "__main__":
    main()
