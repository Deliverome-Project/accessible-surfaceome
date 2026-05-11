-- Schema for the `surfaceome_agents` Cloudflare D1 database.
--
-- One D1 database holds both surface_triage runs (per gene × variant ×
-- replicate × model) and surface_annotator (deep-dive) runs (per gene
-- per agent invocation), with full reproducibility joins across them.
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
-- This is a *separate* database from the existing `signups` one on the
-- Deliverome Pages project — see cloudflare/README.md for the provisioning
-- walkthrough.
--
-- To apply (run once after `wrangler d1 create surfaceome_agents`):
--
--   wrangler d1 execute surfaceome_agents \\
--     --remote \\
--     --file=cloudflare/d1_schema.sql

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
    predicted_verdict          TEXT,                       -- nullable on parse-fail / API error
    predicted_reason           TEXT,
    verdict_reasoning          TEXT,
    predicted_confidence       TEXT,                       -- 'low'|'medium'|'high' (schema v0.9.0+)
    predicted_key_uncertainty  TEXT,                       -- ≤200 chars; the one thing the agent is least sure about

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


-- ===========================================================================
-- Deep-dive tables (surface_annotator agent — full provenance + evidence)
-- ===========================================================================
-- One ``deep_dive_run`` per agent invocation that emits a SurfaceomeRecord,
-- with child tables for the evidence chain and the search log. The full
-- nested record is also stored as JSON in ``deep_dive_run.record_json`` so
-- downstream consumers don't have to re-stitch the trees from rows.

CREATE TABLE IF NOT EXISTS deep_dive_run (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id                   TEXT NOT NULL,                 -- groups a sweep (uuid)
    created_at               TEXT NOT NULL DEFAULT (datetime('now')),

    -- which protein + provenance anchors
    gene_symbol              TEXT NOT NULL,
    uniprot_acc              TEXT NOT NULL,
    canonical_isoform        TEXT,
    isoform_flattened        INTEGER NOT NULL DEFAULT 0,

    -- agent setup
    model                    TEXT NOT NULL,                  -- e.g. 'claude-opus-4-7'
    model_path               TEXT NOT NULL,                  -- ModelPath literal
    prompt_sha               TEXT NOT NULL,                  -- joins to prompt_version
    schema_version           TEXT NOT NULL,                  -- SurfaceomeRecord schema version

    -- headline call (denormalized from the record for query speed)
    targetability_verdict    TEXT,                           -- TargetabilityVerdict literal
    confidence               TEXT,                           -- SynthesisConfidence literal
    contradiction_flag       INTEGER NOT NULL DEFAULT 0,

    -- evidence + search summaries (denormalized counts; full data below)
    primary_evidence_count   INTEGER NOT NULL DEFAULT 0,
    secondary_evidence_count INTEGER NOT NULL DEFAULT 0,
    evidence_count           INTEGER NOT NULL DEFAULT 0,
    search_log_count         INTEGER NOT NULL DEFAULT 0,

    -- prose
    rationale                TEXT,
    confidence_reasoning     TEXT,

    -- telemetry
    cost_usd                 REAL NOT NULL DEFAULT 0.0,
    latency_s                REAL NOT NULL DEFAULT 0.0,
    n_tool_calls             INTEGER NOT NULL DEFAULT 0,

    -- full structured record — JSON-encoded SurfaceomeRecord. Keeps the
    -- relational columns lean while preserving every nested field for
    -- consumers that want the whole tree.
    record_json              TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_deep_dive_run_sweep      ON deep_dive_run (run_id);
CREATE INDEX IF NOT EXISTS idx_deep_dive_run_gene       ON deep_dive_run (gene_symbol, created_at);
CREATE INDEX IF NOT EXISTS idx_deep_dive_run_prompt_sha ON deep_dive_run (prompt_sha);
CREATE INDEX IF NOT EXISTS idx_deep_dive_run_verdict    ON deep_dive_run (targetability_verdict);


-- One row per Evidence claim. The triple (run, evidence_id) is the natural
-- key; we autoincrement to avoid composite-PK juggling.
CREATE TABLE IF NOT EXISTS deep_dive_evidence (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    deep_dive_run_id         INTEGER NOT NULL,               -- FK → deep_dive_run.id
    evidence_id              TEXT NOT NULL,                  -- agent-assigned handle
    source_db                TEXT,                           -- 'uniprot', 'pubmed', 'patent', etc.
    source_url               TEXT,
    span_text                TEXT,                           -- verbatim quote
    claim_kind               TEXT,                           -- 'topology', 'expression', etc.
    is_primary               INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (deep_dive_run_id) REFERENCES deep_dive_run(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_dd_evidence_run    ON deep_dive_evidence (deep_dive_run_id);
CREATE INDEX IF NOT EXISTS idx_dd_evidence_source ON deep_dive_evidence (source_db);


-- One row per SearchEntry — every source consultation, whether or not it
-- yielded a citation. Lets us audit comprehensiveness ("did the agent
-- check the shedding lit?") and skip redundant queries on re-annotation.
CREATE TABLE IF NOT EXISTS deep_dive_search_log (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    deep_dive_run_id         INTEGER NOT NULL,
    step_index               INTEGER NOT NULL,               -- order within the run
    source                   TEXT NOT NULL,                  -- which tool / DB
    query                    TEXT,
    hit_count                INTEGER,
    yielded_citation         INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (deep_dive_run_id) REFERENCES deep_dive_run(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_dd_search_run    ON deep_dive_search_log (deep_dive_run_id);
CREATE INDEX IF NOT EXISTS idx_dd_search_source ON deep_dive_search_log (source);


-- Convenience view: most recent deep dive per gene (collapsing replicates).
CREATE VIEW IF NOT EXISTS deep_dive_latest AS
SELECT d.*
FROM deep_dive_run d
JOIN (
    SELECT gene_symbol, MAX(created_at) AS latest
    FROM deep_dive_run
    GROUP BY gene_symbol
) g ON d.gene_symbol = g.gene_symbol AND d.created_at = g.latest;


-- Cross-table view: what does the deep dive say about each triage call?
-- Joins on (gene_symbol, prompt_sha-of-triage) but uses latest deep dive per gene.
CREATE VIEW IF NOT EXISTS triage_vs_deep_dive AS
SELECT
    t.gene_symbol,
    t.model                  AS triage_model,
    t.prompt_variant         AS triage_variant,
    t.predicted_verdict      AS triage_verdict,
    t.truth_verdict          AS triage_truth,
    t.correct                AS triage_correct,
    d.model                  AS deep_dive_model,
    d.targetability_verdict  AS deep_dive_verdict,
    d.confidence             AS deep_dive_confidence,
    d.evidence_count         AS deep_dive_evidence_count,
    d.created_at             AS deep_dive_at
FROM triage_run t
LEFT JOIN deep_dive_latest d ON d.gene_symbol = t.gene_symbol;
