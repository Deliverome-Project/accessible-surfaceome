-- Schema for the `surfaceome_public` Cloudflare D1 database.
--
-- Public mirror of selected tables from `surfaceome_agents` (the private
-- agent-runs database). Designed to be world-readable via a Cloudflare
-- Worker at e.g. `api.deliverome.org/surfaceome/...` with no auth.
--
-- Sync direction: ALWAYS private → public. The sync script
-- (scripts/sync_public_d1.py) is one-way and append-only — historical
-- snapshots stay queryable, the public DB is never read by the agent
-- pipeline.
--
-- What does NOT live in this database (by design):
--   * prompt_version.text  — full prompt source is unpublished
--   * triage_run.{cost_usd, prompt_tokens, completion_tokens,
--                 cache_creation_tokens, cache_read_tokens}
--                          — billing data, not useful to public consumers
--   * data/sources/*.json  — cached source bodies (UniProt, PubMed) are
--                            redistributed by Cloudflare R2 / CDN, not D1
--
-- To apply (one-shot after `wrangler d1 create surfaceome_public`):
--
--   wrangler d1 execute surfaceome_public --remote \\
--     --file=cloudflare/d1_public_schema.sql
--
-- Or via D1 HTTP API (no wrangler needed) — see scripts/apply_d1_schema.py.

-- ---------------------------------------------------------------------------
-- compara_release / compara_ortholog
-- Same shape as in surfaceome_agents (cloudflare/d1_compara_schema.sql).
-- Ensembl Compara is inherently public, so this is a straight copy.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS compara_release (
    release_version  TEXT PRIMARY KEY,
    fetched_at       TEXT NOT NULL DEFAULT (datetime('now')),
    n_pairs          INTEGER NOT NULL,
    source_url       TEXT,
    notes            TEXT
);

CREATE TABLE IF NOT EXISTS compara_ortholog (
    release_version       TEXT NOT NULL,
    human_ensembl_gene    TEXT NOT NULL,
    human_uniprot_acc     TEXT,
    human_gene_symbol     TEXT,
    species               TEXT NOT NULL,
    ortholog_ensembl_gene TEXT NOT NULL,
    ortholog_uniprot_acc  TEXT,
    ortholog_gene_symbol  TEXT,
    orthology_type        TEXT NOT NULL,
    percent_identity      REAL,
    is_high_confidence    INTEGER NOT NULL,
    PRIMARY KEY (release_version, human_ensembl_gene, species, ortholog_ensembl_gene),
    FOREIGN KEY (release_version) REFERENCES compara_release(release_version)
);

CREATE INDEX IF NOT EXISTS idx_compara_ortholog_human_uniprot
    ON compara_ortholog (human_uniprot_acc);
CREATE INDEX IF NOT EXISTS idx_compara_ortholog_human_symbol
    ON compara_ortholog (human_gene_symbol);
CREATE INDEX IF NOT EXISTS idx_compara_ortholog_release_species
    ON compara_ortholog (release_version, species);


-- ---------------------------------------------------------------------------
-- benchmark_version — curated truth labels for the triage benchmark
-- Same shape as the private DB; this is curated ground truth and is meant
-- to be public.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS benchmark_version (
    bench_version    TEXT NOT NULL,
    gene_symbol      TEXT NOT NULL,
    uniprot_acc      TEXT NOT NULL,
    class            TEXT NOT NULL,
    truth_verdict    TEXT NOT NULL,         -- yes | contextual | no
    truth_signal     TEXT NOT NULL,         -- likely_accessible | possibly_accessible | unlikely | unknown
    truth_reason     TEXT NOT NULL,
    rationale        TEXT,
    created_at       TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (bench_version, gene_symbol)
);

CREATE INDEX IF NOT EXISTS idx_benchmark_version_uniprot
    ON benchmark_version (uniprot_acc);


-- ---------------------------------------------------------------------------
-- triage_run_public — per-gene triage verdicts with cost + token data
-- Subset of `triage_run` in the private DB. The original design dropped
-- cost_usd + token counts + cache_* columns as "operational metadata",
-- but external reproducibility of figures like benchmark_cost_vs_accuracy
-- requires those exact fields — and there's no security reason to gate
-- aggregate per-model cost data for an LLM eval that is itself public.
-- (Raw prompt text + verdict_reasoning + raw_text stay private; only
-- per-call cost telemetry leaves.)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS triage_run_public (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id              TEXT NOT NULL,
    created_at          TEXT NOT NULL,

    gene_symbol         TEXT NOT NULL,
    uniprot_acc         TEXT,
    bench_version       TEXT NOT NULL,

    model               TEXT NOT NULL,
    prompt_variant      TEXT NOT NULL,
    prompt_sha          TEXT NOT NULL,           -- joins to prompt_version (not mirrored as text)
    prompt_filename     TEXT,                    -- e.g. 'system_web.md' (so consumers know what variant)
    schema_version      TEXT NOT NULL,
    replicate           INTEGER NOT NULL,

    -- Model output
    predicted_verdict       TEXT,
    predicted_reason        TEXT,
    predicted_confidence    TEXT,                 -- low | medium | high
    predicted_key_uncertainty TEXT,
    verdict_reasoning       TEXT,
    correct                 INTEGER,              -- 1/0 against bench_version truth, with yes ≡ contextual

    -- Reproducibility
    latency_s               REAL,
    n_web_searches          INTEGER,
    error                   TEXT,

    -- Cost + token telemetry. Carried through from private D1 so
    -- external readers can reproduce cost_vs_accuracy plots without
    -- needing private credentials. Nullable because rows that
    -- pre-date the policy change have NULL here until backfilled.
    cost_usd                REAL,
    prompt_tokens           INTEGER,
    completion_tokens       INTEGER,
    cache_creation_tokens   INTEGER,
    cache_read_tokens       INTEGER,

    -- When this row landed in the public mirror (separate from created_at
    -- which is the original run timestamp on the private side)
    synced_at               TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_triage_run_public_gene
    ON triage_run_public (gene_symbol);
CREATE INDEX IF NOT EXISTS idx_triage_run_public_bench
    ON triage_run_public (bench_version, gene_symbol);
CREATE INDEX IF NOT EXISTS idx_triage_run_public_model
    ON triage_run_public (model, prompt_variant);

-- Natural-key UNIQUE constraint so `sync_public_d1.py`'s INSERT OR IGNORE
-- actually dedupes. Without this, the AUTOINCREMENT primary key is the
-- only uniqueness signal and every re-sync inserts duplicates, forcing
-- consumers of the sync to always pass `--since` to avoid bloat — which
-- in turn risks permanent gaps if the very first sync was interrupted
-- (which is how 67 Opus naive + 1 Haiku naive rows ended up missing from
-- the mainbench_canonical_v1 sweep).
CREATE UNIQUE INDEX IF NOT EXISTS uq_triage_run_public_natural
    ON triage_run_public (run_id, gene_symbol, model, prompt_variant, replicate, prompt_sha);


-- ---------------------------------------------------------------------------
-- surface_annotation — per-gene deep-dive SurfaceomeRecord (v0.4.0+)
-- One row per (gene_symbol, schema_version). Stores the full record JSON
-- as a blob so the Worker can serve it on `GET /v1/genes/:symbol` with a
-- single round-trip. The agent re-running a gene replaces the row.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS surface_annotation (
    gene_symbol         TEXT NOT NULL,
    uniprot_acc         TEXT,
    schema_version      TEXT NOT NULL,           -- e.g. 'v0.4.0'
    annotation_json     TEXT NOT NULL,           -- the full SurfaceomeRecord, JSON-encoded
    confidence          TEXT,                    -- denormalized for cheap filtering
    triage_signal       TEXT,                    -- denormalized
    surface_status      TEXT,                    -- denormalized
    model_path          TEXT,                    -- e.g. 'sonnet_only'
    evidence_count      INTEGER,
    primary_evidence_count INTEGER,
    annotated_at        TEXT NOT NULL,           -- when the agent run completed
    synced_at           TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (gene_symbol, schema_version)
);

CREATE INDEX IF NOT EXISTS idx_surface_annotation_uniprot
    ON surface_annotation (uniprot_acc);
CREATE INDEX IF NOT EXISTS idx_surface_annotation_surface_status
    ON surface_annotation (surface_status);


-- ---------------------------------------------------------------------------
-- candidate_universe_public — genome-wide DB-vote table the viewer's
-- catalogue index renders. One row per (universe_version, gene, UniProt);
-- carries the seven per-source surface flags + the union count.
--
-- Loaded from `data/processed/candidate_universe/candidate_universe.tsv`
-- (a build artifact, NOT in the private agents DB) by
-- scripts/upload_candidate_universe_to_d1.py. Each merge run bumps
-- universe_version so historical universes stay queryable; the Worker
-- always serves the latest.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS candidate_universe_public (
    universe_version            TEXT NOT NULL,    -- e.g. 'cu_2026_05_12'
    gene_symbol                 TEXT NOT NULL,    -- gene_symbol_resolved from the TSV
    uniprot_acc                 TEXT NOT NULL,    -- uniprot_accession
    n_sources_surface           INTEGER NOT NULL,
    uniprot_surface_flag        INTEGER NOT NULL,
    go_surface_flag             INTEGER NOT NULL,
    surfy_surface_flag          INTEGER NOT NULL,
    cspa_surface_flag           INTEGER NOT NULL,
    hpa_surface_flag            INTEGER NOT NULL,
    deeptmhmm_surface_flag      INTEGER NOT NULL,
    compartments_surface_flag   INTEGER NOT NULL,
    synced_at                   TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (universe_version, gene_symbol, uniprot_acc)
);

CREATE INDEX IF NOT EXISTS idx_candidate_universe_public_gene
    ON candidate_universe_public (gene_symbol);
CREATE INDEX IF NOT EXISTS idx_candidate_universe_public_version
    ON candidate_universe_public (universe_version);


-- ---------------------------------------------------------------------------
-- candidate_universe_release — pointer to the active universe_version so
-- the Worker doesn't have to MAX() across every row to find "latest". One
-- row per universe; the uploader inserts on each fresh load.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS candidate_universe_release (
    universe_version    TEXT PRIMARY KEY,
    n_rows              INTEGER NOT NULL,
    loaded_at           TEXT NOT NULL DEFAULT (datetime('now')),
    source_path         TEXT,                       -- relative path of source TSV
    notes               TEXT
);


-- ---------------------------------------------------------------------------
-- gene_identifier_public — column-whitelisted mirror of the private
-- gene_identifier table. Lets the public Worker (and the viewer) look up
-- canonical stable IDs for any gene without re-resolving from symbol —
-- which historically was where the resolver bugs entered the pipeline
-- (see scripts/audit_resolver_hgnc_id_v3.py for the failure modes).
--
-- Synced from `surfaceome_agents.gene_identifier` by the same one-way
-- script that mirrors candidate_universe + triage_run. Resolver-version
-- carried through so consumers can detect when the resolver has been
-- updated and a re-sync is needed.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS gene_identifier_public (
    hgnc_id                   TEXT PRIMARY KEY,
    hgnc_symbol               TEXT NOT NULL,
    cohort_symbol             TEXT,
    uniprot_acc               TEXT,
    ncbi_gene_id              INTEGER,
    ensembl_gene              TEXT,
    ensembl_canonical_protein TEXT,
    resolver_path             TEXT NOT NULL,
    resolver_version          TEXT NOT NULL,
    resolved_at               TEXT NOT NULL,
    hgnc_xref_count           INTEGER NOT NULL DEFAULT 0,
    needs_review              INTEGER NOT NULL DEFAULT 0,
    synced_at                 TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_gene_identifier_public_symbol  ON gene_identifier_public (hgnc_symbol);
CREATE INDEX IF NOT EXISTS idx_gene_identifier_public_uniprot ON gene_identifier_public (uniprot_acc);
CREATE INDEX IF NOT EXISTS idx_gene_identifier_public_ncbi    ON gene_identifier_public (ncbi_gene_id);
CREATE INDEX IF NOT EXISTS idx_gene_identifier_public_ensembl ON gene_identifier_public (ensembl_gene);
