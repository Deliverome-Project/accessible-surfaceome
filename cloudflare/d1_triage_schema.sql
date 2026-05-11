-- Schema for the `triage_results` Cloudflare D1 database.
--
-- This is a *separate* D1 database from the existing `signups` one on the
-- Deliverome Pages project — created so triage agent runs land in a fully
-- reproducible store without polluting the website's signups table.
--
-- Reproducibility goals:
--   * For every persisted run we can answer: which model, which prompt
--     (down to byte-exact SHA), which benchmark version, which truth label.
--   * Prompt text is versioned by content SHA — editing a prompt creates a
--     new prompt_version row; the old one stays queryable forever.
--   * Benchmark labels are versioned by `bench_version` — re-labeling a
--     protein creates a new benchmark_version row; older runs still join
--     to the labels that were live when they ran.
--
-- To apply (run once after `wrangler d1 create triage_results`):
--
--   wrangler d1 execute triage_results \\
--     --remote \\
--     --file=cloudflare/d1_triage_schema.sql
--
-- See cloudflare/README.md for the full provisioning walkthrough.

-- ---------------------------------------------------------------------------
-- prompt_version — content-addressed snapshot of every prompt seen
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS prompt_version (
    prompt_sha       TEXT PRIMARY KEY,             -- sha256(prompt_text), hex
    prompt_filename  TEXT NOT NULL,                 -- e.g. 'system_web_naive.md'
    schema_version   TEXT NOT NULL,                 -- TriageRecordDraft schema, e.g. 'v0.9.0'
    text             TEXT NOT NULL,                 -- full prompt source
    n_lines          INTEGER NOT NULL,
    first_seen_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_prompt_version_filename
    ON prompt_version (prompt_filename);


-- ---------------------------------------------------------------------------
-- benchmark_version — point-in-time snapshot of each gene's ground truth
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS benchmark_version (
    bench_version    TEXT NOT NULL,                 -- e.g. 'v1' or sha of the TSV
    gene_symbol      TEXT NOT NULL,
    uniprot_acc      TEXT NOT NULL,
    class            TEXT NOT NULL,
    truth_verdict    TEXT NOT NULL,                 -- yes|contextual|no
    truth_signal     TEXT NOT NULL,
    truth_reason     TEXT NOT NULL,
    rationale        TEXT,
    created_at       TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (bench_version, gene_symbol)
);


-- ---------------------------------------------------------------------------
-- triage_run — one row per (model × variant × replicate × gene) API call
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS triage_run (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id              TEXT NOT NULL,             -- groups one sweep (uuid)
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),

    -- which protein
    gene_symbol         TEXT NOT NULL,
    uniprot_acc         TEXT,
    bench_version       TEXT NOT NULL,             -- joins to benchmark_version

    -- which agent setup
    model               TEXT NOT NULL,             -- 'claude-haiku-4-5' etc.
    prompt_variant      TEXT NOT NULL,             -- 'naive'|'ncbi'|'web_naive'|'web_ncbi'
    prompt_sha          TEXT NOT NULL,             -- joins to prompt_version
    schema_version      TEXT NOT NULL,             -- TriageRecordDraft version
    replicate           INTEGER NOT NULL,

    -- agent output
    predicted_verdict   TEXT,                       -- nullable on parse-fail / API error
    predicted_reason    TEXT,
    verdict_reasoning   TEXT,

    -- evaluation (denormalized for query speed; same fields are in
    -- benchmark_version, but storing here avoids a join for hot dashboards)
    truth_verdict       TEXT NOT NULL,
    truth_class         TEXT NOT NULL,
    correct             INTEGER NOT NULL,           -- 0|1

    -- telemetry
    prompt_tokens       INTEGER NOT NULL DEFAULT 0,
    completion_tokens   INTEGER NOT NULL DEFAULT 0,
    n_web_searches      INTEGER NOT NULL DEFAULT 0,
    cost_usd            REAL NOT NULL DEFAULT 0.0,
    latency_s           REAL NOT NULL DEFAULT 0.0,

    -- failure / debug
    error               TEXT,                       -- nullable
    raw_text            TEXT                        -- nullable; raw model output on parse-fail
);

CREATE INDEX IF NOT EXISTS idx_triage_run_sweep        ON triage_run (run_id);
CREATE INDEX IF NOT EXISTS idx_triage_run_gene_model   ON triage_run (gene_symbol, model, prompt_variant);
CREATE INDEX IF NOT EXISTS idx_triage_run_prompt_sha   ON triage_run (prompt_sha);
CREATE INDEX IF NOT EXISTS idx_triage_run_bench        ON triage_run (bench_version);
CREATE INDEX IF NOT EXISTS idx_triage_run_created      ON triage_run (created_at);


-- ---------------------------------------------------------------------------
-- Helper view: per-cell accuracy + cost (one row per model × variant ×
-- bench_version × prompt_sha × replicate-budget)
-- ---------------------------------------------------------------------------

CREATE VIEW IF NOT EXISTS triage_cell_summary AS
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
    MIN(created_at)                AS first_run_at,
    MAX(created_at)                AS last_run_at
FROM triage_run
GROUP BY model, prompt_variant, bench_version, prompt_sha;
