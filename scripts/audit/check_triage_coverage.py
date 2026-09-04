#!/usr/bin/env python
"""Triage-coverage pre-flight check for a deep-dive cohort sweep.

Verifies that every gene in the input list has a Sonnet-NCBI triage
row in public D1. The synthesizer uses ``triage_summary_json`` as a
prior — when missing, the synth runs without it and quality degrades.

Catches the genome-wide blocker BEFORE the sweep burns cost on
genes the synth can't fully evaluate.

Usage:
    uv run python scripts/check_triage_coverage.py \\
        --gene-list data/processed/candidate_universe/candidate_universe_v2.tsv \\
        --model claude-sonnet-4-6 \\
        --prompt-variant ncbi \\
        --replicate 1

Exits 0 when coverage is complete, 1 when any gene is missing (writes
the missing list to stderr).
"""

from __future__ import annotations

import argparse
import csv
import sys

from accessible_surfaceome.cloud.d1_client import D1Client, D1Config
from accessible_surfaceome.env import load_env


def _load_gene_list(path: str) -> list[str]:
    """Read gene_symbol from a TSV. First column is assumed; first row is header."""
    genes: list[str] = []
    with open(path) as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for row in reader:
            sym = (row.get("gene_symbol") or "").strip()
            if sym:
                genes.append(sym)
    return genes


def _load_triaged(
    *,
    model: str,
    prompt_variant: str,
    replicate: int,
) -> set[str]:
    """All gene symbols that have a triage row at (model, variant, replicate)."""
    with D1Client(D1Config.from_env_public()) as c:
        rows = c.query(
            "SELECT DISTINCT gene_symbol FROM triage_run_public "
            "WHERE model = ? AND prompt_variant = ? AND replicate = ?",
            [model, prompt_variant, replicate],
        )
    return {r["gene_symbol"] for r in rows}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gene-list", required=True, help="TSV with gene_symbol column")
    parser.add_argument("--model", default="claude-sonnet-4-6")
    parser.add_argument("--prompt-variant", default="ncbi")
    parser.add_argument("--replicate", type=int, default=1)
    parser.add_argument(
        "--max-missing",
        type=int,
        default=50,
        help="Print up to this many missing genes to stderr",
    )
    args = parser.parse_args()

    load_env()
    cohort = _load_gene_list(args.gene_list)
    triaged = _load_triaged(
        model=args.model,
        prompt_variant=args.prompt_variant,
        replicate=args.replicate,
    )

    cohort_set = set(cohort)
    missing = sorted(cohort_set - triaged)
    extra = sorted(triaged - cohort_set)

    pct = 100.0 * (len(cohort_set) - len(missing)) / max(len(cohort_set), 1)
    print(
        f"cohort={len(cohort_set):>5}  "
        f"triaged={len(triaged & cohort_set):>5}  "
        f"missing={len(missing):>5}  "
        f"coverage={pct:5.1f}%  "
        f"(model={args.model} variant={args.prompt_variant} rep={args.replicate})"
    )
    print(f"extra-in-triage-not-in-cohort={len(extra)} (drift signal — should usually be 0)")

    if missing:
        head = missing[: args.max_missing]
        sys.stderr.write(
            f"\nMissing triage rows for {len(missing)} gene(s); first {len(head)}:\n"
        )
        for g in head:
            sys.stderr.write(f"  {g}\n")
        if len(missing) > args.max_missing:
            sys.stderr.write(f"  … and {len(missing) - args.max_missing} more\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
