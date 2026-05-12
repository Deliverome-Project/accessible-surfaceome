"""Add prompt-cache telemetry columns to an existing D1 triage_run table.

The schema in cloudflare/d1_schema.sql now declares
``cache_creation_tokens`` and ``cache_read_tokens`` on ``triage_run`` so
we can audit Anthropic prompt-cache hit rates over time
(cache_read ÷ (cache_read + cache_creation) within the 5-min TTL).

Fresh databases get them via ``CREATE TABLE``. Existing databases need
``ALTER TABLE ADD COLUMN`` per missing column — SQLite doesn't support
``ADD COLUMN IF NOT EXISTS``, so we check ``PRAGMA table_info`` first and
only add the columns that are missing.

We also DROP-and-recreate the ``triage_cell_summary`` view so its
aggregate cache columns + ``cache_hit_rate`` show up. The view's
``CREATE VIEW IF NOT EXISTS`` is a no-op against an already-existing
view, so we drop first.

Idempotent: safe to run repeatedly.
"""

from __future__ import annotations

import sys

from accessible_surfaceome.cloud.d1_client import D1Client
from accessible_surfaceome.env import load_env

load_env()

NEW_COLUMNS: list[tuple[str, str, int]] = [
    # (name, sql_type, default for backfill)
    ("cache_creation_tokens", "INTEGER NOT NULL DEFAULT 0", 0),
    ("cache_read_tokens", "INTEGER NOT NULL DEFAULT 0", 0),
]

CELL_SUMMARY_VIEW = """\
CREATE VIEW triage_cell_summary AS
SELECT
    model,
    prompt_variant,
    bench_version,
    prompt_sha,
    COUNT(*)                       AS n_runs,
    SUM(correct)                   AS n_correct,
    CAST(SUM(correct) AS REAL) / NULLIF(COUNT(*), 0) AS verdict_accuracy,
    SUM(cost_usd)                  AS total_cost_usd,
    AVG(latency_s)                 AS mean_latency_s,
    AVG(n_web_searches)            AS mean_web_searches,
    SUM(prompt_tokens)             AS total_prompt_tokens,
    SUM(completion_tokens)         AS total_completion_tokens,
    SUM(cache_creation_tokens)     AS total_cache_creation_tokens,
    SUM(cache_read_tokens)         AS total_cache_read_tokens,
    CAST(SUM(cache_read_tokens) AS REAL)
        / NULLIF(SUM(cache_read_tokens) + SUM(cache_creation_tokens), 0)
        AS cache_hit_rate,
    MIN(created_at)                AS first_run_at,
    MAX(created_at)                AS last_run_at
FROM triage_run
GROUP BY model, prompt_variant, bench_version, prompt_sha
"""


def main() -> int:
    with D1Client() as d1:
        existing = {row["name"] for row in d1.query("PRAGMA table_info(triage_run);")}
        print(f"triage_run currently has {len(existing)} columns")
        for col, typ, _default in NEW_COLUMNS:
            if col in existing:
                print(f"  ✓ {col} already present")
                continue
            print(f"  + adding {col} {typ}")
            d1.query(f"ALTER TABLE triage_run ADD COLUMN {col} {typ};")
        final = {row["name"] for row in d1.query("PRAGMA table_info(triage_run);")}
        added = final - existing
        if added:
            print(f"Added columns: {sorted(added)}")
        else:
            print("No-op on columns — all already existed.")

        # Refresh the cell-summary view so cache_hit_rate is queryable.
        # CREATE VIEW IF NOT EXISTS won't redefine an existing view, so
        # drop first.
        print("Refreshing triage_cell_summary view...")
        d1.query("DROP VIEW IF EXISTS triage_cell_summary;")
        d1.query(CELL_SUMMARY_VIEW + ";")
        print("  ✓ triage_cell_summary recreated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
