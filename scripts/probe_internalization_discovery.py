"""$0 probe for the internalization literature discovery stage.

Runs discovery (EuropePMC + PubTator union) for one or more genes and prints the
corpus size + sample titles — NO model calls by default, so it costs nothing.
Use it to validate retrieval before spending on triage/select/grade.

    uv run python scripts/probe_internalization_discovery.py TFRC EGFR ENPP3
    uv run python scripts/probe_internalization_discovery.py MS4A1 --triage  # + Haiku triage counts
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter

from accessible_surfaceome.agents.internalization.ids import resolve_hgnc_id
from accessible_surfaceome.agents.internalization.literature_discovery import (
    discover_internalization_papers,
)
from accessible_surfaceome.env import load_env
from accessible_surfaceome.tools._shared.http import open_default_client
from accessible_surfaceome.tools._shared.retraction_watch import empty as empty_retraction
from accessible_surfaceome.tools.gene_lookup import resolve_by_hgnc_id


def main(argv: list[str] | None = None) -> int:
    load_env()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("genes", nargs="+", help="Gene symbols or HGNC:ids")
    parser.add_argument(
        "--triage",
        action="store_true",
        help="Also run Haiku abstract triage and print decision counts (costs a little).",
    )
    parser.add_argument("--limit-titles", type=int, default=5)
    args = parser.parse_args(argv)

    http = open_default_client()
    retraction = empty_retraction()

    for gene in args.genes:
        bundle = resolve_by_hgnc_id(resolve_hgnc_id(gene), http=http)
        papers = discover_internalization_papers(
            bundle, http=http, retraction_index=retraction
        )
        print(f"\n{bundle.hgnc_symbol} ({bundle.uniprot_acc}): {len(papers)} papers discovered")
        for p in list(papers.values())[: args.limit_titles]:
            print(f"  {p.pmid}  {(p.title or '')[:90]}")

        if args.triage:
            from accessible_surfaceome.agents._support.client import get_client
            from accessible_surfaceome.agents.internalization.literature_triage import (
                triage_internalization_abstracts,
            )

            outcomes = triage_internalization_abstracts(
                get_client(), papers=list(papers.values()), gene=bundle.hgnc_symbol
            )
            counts = Counter(
                o.response.decision if o.response else "error" for o in outcomes
            )
            print(f"  triage: {dict(counts)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
