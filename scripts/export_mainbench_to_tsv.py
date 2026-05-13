"""Export the canonical main-bench triage_run records to a plain-git TSV.

The full 147-gene × 10-cell main bench landed in D1 under
``run_id='mainbench_canonical_v1'`` (1,470 records: haiku × 4 variants +
sonnet × 4 variants + opus × 2 variants). The gist scripts under
``data/analysis/triage_bench_d1/`` fetch this TSV via
``raw.githubusercontent.com`` so a reader can ``uv run`` the
``make_*.py`` scripts without D1 credentials.

Source-of-truth: D1 ``triage_run`` table. This TSV is a thin export.
Re-run after any sweep that updates the canonical mainbench data.

Output: ``data/processed/triage_bench/mainbench_canonical_v1.tsv``
(plain git via ``.gitattributes`` exemption — LFS pointers don't
resolve over raw.githubusercontent.com).
"""
from __future__ import annotations

import csv

from accessible_surfaceome.cloud.d1_client import D1Client
from accessible_surfaceome.env import load_env
from accessible_surfaceome.paths import REPO_ROOT

load_env()

RUN_ID = "mainbench_canonical_v1"
OUT = REPO_ROOT / "data/processed/triage_bench/mainbench_canonical_v1.tsv"

# Only the fields the gist plot scripts consume. Keep this set narrow
# so the TSV stays small + readable; expand only when a new figure
# needs a new column.
COLUMNS = [
    "gene_symbol",
    "model",
    "prompt_variant",
    "replicate",
    "predicted_verdict",
    "predicted_reason",
    "predicted_confidence",
    "prompt_tokens",
    "completion_tokens",
    "cache_creation_tokens",
    "cache_read_tokens",
    "n_web_searches",
    "cost_usd",
    "latency_s",
]


def main() -> int:
    with D1Client() as d1:
        rows = d1.query(
            f"SELECT {', '.join(COLUMNS)} FROM triage_run "
            f"WHERE run_id = ? AND replicate = 1 "
            f"ORDER BY model, prompt_variant, gene_symbol;",
            [RUN_ID],
        )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS, delimiter="\t")
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote {OUT.relative_to(REPO_ROOT)}  ({len(rows):,} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
