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

    -- which protein (resolver stable IDs — written from gene_identifier via
    -- the HGNC-ID resolver, NOT the bench-pinned uniprot; see triage_upload.py)
    gene_symbol         TEXT NOT NULL,
    uniprot_acc         TEXT,
    hgnc_id             TEXT,
    ensembl_gene        TEXT,
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
    prompt_tokens             INTEGER NOT NULL DEFAULT 0,
    completion_tokens         INTEGER NOT NULL DEFAULT 0,
    cache_creation_tokens     INTEGER NOT NULL DEFAULT 0,   -- system-prompt-cache writes (1.25× input rate)
    cache_read_tokens         INTEGER NOT NULL DEFAULT 0,   -- cache hits (0.10× input rate); 5-min TTL
    n_web_searches            INTEGER NOT NULL DEFAULT 0,
    cost_usd                  REAL NOT NULL DEFAULT 0.0,
    latency_s                 REAL NOT NULL DEFAULT 0.0,

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
    SUM(prompt_tokens)             AS total_prompt_tokens,
    SUM(completion_tokens)         AS total_completion_tokens,
    SUM(cache_creation_tokens)     AS total_cache_creation_tokens,
    SUM(cache_read_tokens)         AS total_cache_read_tokens,
    -- Cache-hit rate: cache reads ÷ (cache reads + cache writes). Goes
    -- ↑ within a 5-min TTL window as more calls share one warm prefix.
    CAST(SUM(cache_read_tokens) AS REAL)
        / NULLIF(SUM(cache_read_tokens) + SUM(cache_creation_tokens), 0)
        AS cache_hit_rate,
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

-- One row per (run_id, gene_symbol). SQLite doesn't support adding a
-- UNIQUE table constraint via ALTER TABLE, so we enforce the natural key
-- via a UNIQUE INDEX — functionally equivalent and works on existing
-- populated tables. Lets the v2 sweep sink use
-- ``INSERT ... ON CONFLICT (run_id, gene_symbol) DO NOTHING`` so
-- two driver processes hitting the same sweep can't race a duplicate row
-- into D1.
CREATE UNIQUE INDEX IF NOT EXISTS idx_deep_dive_run_unique_gene
    ON deep_dive_run (run_id, gene_symbol);


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


-- ---------------------------------------------------------------------------
-- resolver_context_version — content-addressed snapshot of the dynamic
-- task message that gets injected at runtime
-- ---------------------------------------------------------------------------
-- The system prompt is versioned by ``prompt_version`` (above), but the
-- *user message* is generated per-call from live HGNC + UniProt + NCBI
-- queries (the "resolver context") and, for the pubmed_ncbi variant, a
-- PubMed-esearch-derived literature evidence block. NCBI summaries
-- update and re-run results would shift if the context changed — so we
-- content-address the assembled user message and let triage_run join
-- to whichever snapshot it actually saw at run time.

CREATE TABLE IF NOT EXISTS resolver_context_version (
    context_sha       TEXT PRIMARY KEY,              -- sha256(user_message_text), hex
    gene_symbol       TEXT NOT NULL,
    text              TEXT NOT NULL,                 -- full user-message text
    fetched_at        TEXT NOT NULL DEFAULT (datetime('now')),
    -- Denormalized convenience columns parsed out of the resolver
    -- output (NULL for variants that don't include these blocks, e.g.
    -- the naive variants get only the bare gene name).
    hgnc_gene_groups  TEXT,
    cd_designation    TEXT,
    ncbi_summary      TEXT
);

CREATE INDEX IF NOT EXISTS idx_resolver_context_gene
    ON resolver_context_version (gene_symbol);


-- ---------------------------------------------------------------------------
-- triage_search_log — one row per tool call (web_search / pubmed) the
-- agent made on a triage run. Mirror of deep_dive_search_log.
-- ---------------------------------------------------------------------------
-- The triage_run table records the *count* of web searches (n_web_searches)
-- but not the queries themselves or their results. For reproducibility
-- and forensics ("which paper did the agent actually find?") we need
-- the queries + result snippets. Filling this table is opt-in by the
-- runner — historic rows will not be populated.

CREATE TABLE IF NOT EXISTS triage_search_log (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    triage_run_id     INTEGER NOT NULL,                  -- FK → triage_run.id
    step_index        INTEGER NOT NULL,                  -- order within the run
    tool              TEXT NOT NULL,                     -- 'web_search', 'pubmed_lookup', etc.
    query             TEXT,                              -- the query string the agent issued
    n_results         INTEGER,
    top_results_json  TEXT,                              -- [{title,url,snippet}, ...]
    FOREIGN KEY (triage_run_id) REFERENCES triage_run(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_triage_search_run  ON triage_search_log (triage_run_id);
CREATE INDEX IF NOT EXISTS idx_triage_search_tool ON triage_search_log (tool);


-- ---------------------------------------------------------------------------
-- triage_run column additions (post-initial-schema). To re-apply against
-- an existing database, replay this SQL idempotently — SQLite ALTER
-- TABLE ADD COLUMN is a no-op on duplicate columns when wrapped in a
-- try/except by the wrangler client (the local dev path) but will hard-
-- fail in raw d1 execute. New installs run the full file end-to-end
-- and pick these up at table-creation time via a CTAS-style pattern;
-- the alters below are only needed when migrating a previously-applied
-- schema. Skip them on a fresh d1 by deleting the surfaceome_agents
-- database and re-creating from this file in one shot.
-- ---------------------------------------------------------------------------
ALTER TABLE triage_run ADD COLUMN resolver_context_sha TEXT;
-- Model decoding params (currently runner defaults, but record explicitly
-- so a future tweak doesn't silently change historical comparability).
ALTER TABLE triage_run ADD COLUMN temperature REAL;
ALTER TABLE triage_run ADD COLUMN top_p REAL;
ALTER TABLE triage_run ADD COLUMN max_tokens INTEGER;
-- Anthropic API response metadata — `response.id` uniquely identifies
-- the server-side call; stop_reason flags truncation / tool_use exits;
-- response.model can be a dated alias (e.g. "claude-sonnet-4-6-20260301").
ALTER TABLE triage_run ADD COLUMN api_response_id TEXT;
ALTER TABLE triage_run ADD COLUMN api_stop_reason TEXT;
ALTER TABLE triage_run ADD COLUMN api_model TEXT;

CREATE INDEX IF NOT EXISTS idx_triage_run_resolver_ctx
    ON triage_run (resolver_context_sha);


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


-- ---------------------------------------------------------------------------
-- gene_identifier — single source of truth for resolved stable identifiers
-- per gene. Lets every downstream tool (D1 query, viewer, figure script,
-- agent) look up the canonical (uniprot_acc, ensembl_gene, ncbi_gene_id)
-- for a gene without re-resolving from a symbol — which was historically
-- where the symbol-keyed resolver bugs (CCR4 → NOCT, COX1 → PTGS1, WAS →
-- MT-RNR1, etc.) entered the pipeline.
--
-- Populated by scripts/build_gene_identifier_table.py, which iterates the
-- cohort TSV (Homo_sapiens.protein_coding.with_hgnc.tsv) and calls
-- resolve_by_hgnc_id() for every row. Resolver-version-pinned so a future
-- resolver change can repopulate without losing the audit trail.
--
-- HGNC ID is the natural PK because it's the only identifier with all
-- three properties: 1-per-gene (UniProt acc is per-protein, multiple per
-- gene for HLA/Ig/TCR clusters), never reassigned (HGNC retires withdrawn
-- IDs rather than reusing them), and the resolver's canonical entry point
-- per CLAUDE.md's "Gene identifier resolution" section.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS gene_identifier (
    hgnc_id                   TEXT PRIMARY KEY,    -- 'HGNC:1234'

    -- Symbols. Stored for human readability + free-text search joins,
    -- never as a query/join key. `hgnc_symbol` is HGNC's current primary;
    -- `cohort_symbol` is whatever NCBI gene_info had at cohort build time
    -- (the two disagree for ~27 of 19k cohort rows where HGNC has applied
    -- a rename UniProt hasn't synced).
    hgnc_symbol               TEXT NOT NULL,
    cohort_symbol             TEXT,

    -- Stable IDs derived from HGNC + UniProt at resolution time. Every
    -- downstream tool keys on the most appropriate of these per
    -- "Gene identifier resolution" → "Downstream searches" in CLAUDE.md.
    uniprot_acc               TEXT,                -- canonical reviewed Swiss-Prot
    ncbi_gene_id              INTEGER,             -- from HGNC entrez_id
    ensembl_gene              TEXT,                -- ENSG; from HGNC
    ensembl_canonical_protein TEXT,                -- ENSP; from UniProt xref

    -- Provenance — which resolver path / version produced this row.
    -- `resolver_path` ∈ {'hgnc_xref_primary_name_age', 'hgnc_xref_single',
    -- 'hgnc_symbol_fallback', 'hgnc_prev_symbol_fallback'} — see
    -- src/accessible_surfaceome/tools/gene_lookup.py::_pick_canonical_uniprot
    -- and resolve_by_hgnc_id for the path definitions.
    resolver_path             TEXT NOT NULL,
    resolver_version          TEXT NOT NULL,       -- git SHA at resolve time
    resolved_at               TEXT NOT NULL DEFAULT (datetime('now')),

    -- Audit aids: hgnc_xref_count = how many UniProt accs HGNC listed
    -- (1 → unambiguous; ≥2 → went through the primary-name+age picker;
    -- 0 → went through the symbol-search fallback).
    -- `needs_review` = the canonical pick's primary geneName differs from
    -- HGNC's primary symbol (HGNC ahead of UniProt rename — usually
    -- benign but worth eyeballing).
    hgnc_xref_count           INTEGER NOT NULL DEFAULT 0,
    needs_review              INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_gene_identifier_symbol     ON gene_identifier (hgnc_symbol);
CREATE INDEX IF NOT EXISTS idx_gene_identifier_uniprot    ON gene_identifier (uniprot_acc);
CREATE INDEX IF NOT EXISTS idx_gene_identifier_ncbi       ON gene_identifier (ncbi_gene_id);
CREATE INDEX IF NOT EXISTS idx_gene_identifier_ensembl    ON gene_identifier (ensembl_gene);
CREATE INDEX IF NOT EXISTS idx_gene_identifier_needs_rev  ON gene_identifier (needs_review);


-- ---------------------------------------------------------------------------
-- topology_public — per-isoform DeepTMHMM topology + input sequence.
-- Mirror of the table in d1_public_schema.sql; the same schema lives in both
-- DBs so the uploaders can write to both without conditional logic.
--
-- ``hgnc_id`` joins through gene_identifier (stable IDs only, per CLAUDE.md's
-- "Gene identifier resolution" section). NULL on ortholog rows where the
-- gene is mouse/cyno and HGNC IDs don't apply.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS topology_public (
    topology_version           TEXT NOT NULL,
    cohort                     TEXT NOT NULL,
    hgnc_id                    TEXT,                 -- join key into gene_identifier (NULL for non-human cohorts)
    uniprot_acc                TEXT NOT NULL,
    uniprot_acc_full           TEXT NOT NULL,
    isoform_id                 TEXT NOT NULL,
    gene_symbol                TEXT,                 -- denormalized only — never join on this
    species                    TEXT NOT NULL,
    is_canonical               INTEGER NOT NULL,
    sequence                   TEXT NOT NULL,
    protein_length             INTEGER NOT NULL,
    deeptmhmm_label            TEXT NOT NULL,
    tm_helix_count             INTEGER NOT NULL,
    beta_strand_count          INTEGER NOT NULL,
    n_terminal_orientation     TEXT NOT NULL,
    c_terminal_orientation     TEXT NOT NULL,
    signal_peptide_length      INTEGER NOT NULL,
    ecd_length_residues        INTEGER NOT NULL,
    icd_length_residues        INTEGER NOT NULL,
    per_residue_topology       TEXT NOT NULL,
    predicted_surface_membrane INTEGER NOT NULL,
    predicted_secreted         INTEGER NOT NULL,
    tool_version               TEXT NOT NULL,
    retrieved_at               TEXT NOT NULL,
    synced_at                  TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (topology_version, cohort, uniprot_acc_full)
);

CREATE INDEX IF NOT EXISTS idx_topology_public_hgnc
    ON topology_public (hgnc_id);
CREATE INDEX IF NOT EXISTS idx_topology_public_gene
    ON topology_public (gene_symbol);
CREATE INDEX IF NOT EXISTS idx_topology_public_uniprot
    ON topology_public (uniprot_acc);
CREATE INDEX IF NOT EXISTS idx_topology_public_canonical
    ON topology_public (topology_version, cohort, is_canonical);


CREATE TABLE IF NOT EXISTS topology_release (
    topology_version    TEXT PRIMARY KEY,
    n_rows              INTEGER NOT NULL,
    cohorts_present     TEXT NOT NULL,
    deeptmhmm_version   TEXT NOT NULL,
    attribution         TEXT,
    license_url         TEXT,
    loaded_at           TEXT NOT NULL DEFAULT (datetime('now')),
    source_run_dir      TEXT,
    notes               TEXT
);


-- ---------------------------------------------------------------------------
-- compara_paralog — Ensembl Compara within-species paralogs.
-- Mirror of d1_public_schema.sql; both DBs carry paralog data so internal
-- joins (deep_dive_run x compara_paralog) work without a cross-DB query.
--
-- ``human_hgnc_id`` and ``paralog_hgnc_id`` denormalize the stable join
-- keys into gene_identifier. Ensembl gene IDs are NOT resolver-stable
-- across Ensembl release bumps — the HGNC IDs are. Both nullable when
-- the resolver couldn't map a paralog Ensembl ID back to HGNC.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS compara_paralog (
    paralog_version          TEXT NOT NULL,
    human_hgnc_id            TEXT,
    human_ensembl_gene       TEXT NOT NULL,
    human_uniprot_acc        TEXT,
    human_gene_symbol        TEXT,
    paralog_hgnc_id          TEXT,
    paralog_ensembl_gene     TEXT NOT NULL,
    paralog_uniprot_acc      TEXT,
    paralog_gene_symbol      TEXT,
    family_id                TEXT,
    biomart_percent_identity REAL,
    ecd_pct_identity         REAL,
    ecd_pct_similarity       REAL,    -- BLOSUM62 identity + positive substitutions; NULL when no ECD (close pairs >=80%)
    n_ecd_loops_compared     INTEGER,
    rank_by_ecd_identity     INTEGER,
    paralogy_type            TEXT,
    is_high_confidence       INTEGER NOT NULL,
    compara_version          TEXT NOT NULL,
    synced_at                TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (paralog_version, human_ensembl_gene, paralog_ensembl_gene)
);

CREATE INDEX IF NOT EXISTS idx_compara_paralog_human_hgnc
    ON compara_paralog (human_hgnc_id);
CREATE INDEX IF NOT EXISTS idx_compara_paralog_human_uniprot
    ON compara_paralog (human_uniprot_acc);
CREATE INDEX IF NOT EXISTS idx_compara_paralog_human_symbol
    ON compara_paralog (human_gene_symbol);
CREATE INDEX IF NOT EXISTS idx_compara_paralog_version_human
    ON compara_paralog (paralog_version, human_ensembl_gene);


CREATE TABLE IF NOT EXISTS compara_paralog_release (
    paralog_version    TEXT PRIMARY KEY,
    compara_release    TEXT NOT NULL,
    n_pairs            INTEGER NOT NULL,
    n_human_genes      INTEGER NOT NULL,
    fetched_at         TEXT NOT NULL DEFAULT (datetime('now')),
    source_url         TEXT,
    notes              TEXT
);


-- ---------------------------------------------------------------------------
-- compara_ortholog_ecd — locally-computed per-loop ECD identity between
-- a human canonical and its mouse/cyno one2one ortholog.
-- Mirror of d1_public_schema.sql; same shape in both DBs.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS compara_ortholog_ecd (
    ortholog_ecd_version     TEXT NOT NULL,
    human_hgnc_id            TEXT NOT NULL,
    human_uniprot_acc        TEXT,
    human_ensembl_gene       TEXT,
    human_gene_symbol        TEXT,
    species                  TEXT NOT NULL,
    ortholog_uniprot_acc     TEXT NOT NULL,
    ortholog_ensembl_gene    TEXT,
    ortholog_gene_symbol     TEXT,
    biomart_percent_identity REAL,
    ecd_pct_identity         REAL,
    n_ecd_loops_compared     INTEGER,
    compara_release          TEXT NOT NULL,
    synced_at                TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (ortholog_ecd_version, human_hgnc_id, species, ortholog_uniprot_acc)
);

CREATE INDEX IF NOT EXISTS idx_compara_ortholog_ecd_human_hgnc
    ON compara_ortholog_ecd (human_hgnc_id);
CREATE INDEX IF NOT EXISTS idx_compara_ortholog_ecd_species
    ON compara_ortholog_ecd (species);
CREATE INDEX IF NOT EXISTS idx_compara_ortholog_ecd_ortholog_uniprot
    ON compara_ortholog_ecd (ortholog_uniprot_acc);


CREATE TABLE IF NOT EXISTS compara_ortholog_ecd_release (
    ortholog_ecd_version TEXT PRIMARY KEY,
    compara_release      TEXT NOT NULL,
    n_pairs              INTEGER NOT NULL,
    n_human_genes        INTEGER NOT NULL,
    n_species            INTEGER NOT NULL,
    computed_at          TEXT NOT NULL DEFAULT (datetime('now')),
    notes                TEXT
);

-- ---------------------------------------------------------------------------
-- Per-gene feedback submissions (private — PII + audit trail)
-- ---------------------------------------------------------------------------
-- One row per incoming submission from the gene-page "Submit
-- feedback" modal. The Worker writes here from POST
-- /v1/feedback/submit and updates the status column from GET
-- /v1/feedback/moderate when a magic link is clicked. Approved
-- public rows are mirrored (sanitized subset) into
-- surfaceome_public.feedback_public.

CREATE TABLE IF NOT EXISTS feedback (
    id               TEXT PRIMARY KEY,                          -- crypto.randomUUID()
    gene_symbol      TEXT NOT NULL,                             -- e.g. "SRC"
    uniprot_acc      TEXT,                                      -- e.g. "P12931", captured at submit
    submitter_name   TEXT NOT NULL,
    submitter_email  TEXT NOT NULL,
    subject          TEXT NOT NULL,                             -- editable; becomes email subject
    comment          TEXT NOT NULL,                             -- raw; max 4000 chars
    public_requested INTEGER NOT NULL DEFAULT 0,                -- 0|1; mirrors form checkbox
    status           TEXT NOT NULL DEFAULT 'pending',           -- 'pending'|'approved_public'|'discarded'
    referrer         TEXT,                                      -- gene-page URL submitter saw
    user_agent       TEXT,                                      -- navigator.userAgent
    site_version     TEXT,                                      -- git SHA at build time
    ip_hash          TEXT,                                      -- SHA-256(CF-Connecting-IP + day-salt)
    approve_token    TEXT NOT NULL,                             -- HMAC base64url; lives in magic-link
    created_at       TEXT NOT NULL DEFAULT (datetime('now')),
    moderated_at     TEXT                                       -- set when a magic link is clicked
);

CREATE INDEX IF NOT EXISTS idx_feedback_gene
    ON feedback(gene_symbol, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_feedback_status
    ON feedback(status, created_at DESC);
