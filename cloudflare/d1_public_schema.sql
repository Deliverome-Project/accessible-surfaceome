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


-- ---------------------------------------------------------------------------
-- topology_public — per-isoform DeepTMHMM topology + input sequence.
--
-- One row per (topology_version, cohort, uniprot_acc_full). Stores the full
-- per-residue topology string + the canonical UniProt sequence so consumers
-- can re-derive any topology feature (loop bounds, ECD boundaries, helix
-- positions) without re-fetching FASTAs or re-running DeepTMHMM.
--
-- Stable-ID join target: ``hgnc_id`` is denormalized into every row so the
-- viewer / agents / SQL consumers can join through ``gene_identifier_public``
-- without ever touching ``gene_symbol``. The (uniprot_acc, gene_symbol)
-- columns stay for backwards compatibility with the M1 merge artifacts,
-- but ``hgnc_id`` is the canonical key after PR #30.
--
-- Cohort distinguishes which input bundle the prediction came from:
--   human_canonical | human_isoforms | mouse_ortholog | cyno_ortholog
-- See sources/deeptmhmm.py:COHORTS for the authoritative list.
--
-- predicted_surface_membrane is 1 iff deeptmhmm_label in {TM, SP+TM} — matches
-- the rule in sources/deeptmhmm.py (BETA explicitly excluded; human BETA hits
-- are mitochondrial outer-membrane barrels, not plasma-membrane).
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS topology_public (
    topology_version           TEXT NOT NULL,
    cohort                     TEXT NOT NULL,        -- human_canonical | human_isoforms | mouse_ortholog | cyno_ortholog
    hgnc_id                    TEXT,                 -- stable join key into gene_identifier_public (NULL for ortholog rows — non-human gene IDs)
    uniprot_acc                TEXT NOT NULL,        -- base accession (e.g. O95800)
    uniprot_acc_full           TEXT NOT NULL,        -- with isoform suffix (e.g. O95800-1)
    isoform_id                 TEXT NOT NULL,
    gene_symbol                TEXT,                 -- denormalized from gene_identifier for offline reads; NEVER use as a join key
    species                    TEXT NOT NULL,        -- human | mouse | cynomolgus
    is_canonical               INTEGER NOT NULL,
    sequence                   TEXT NOT NULL,        -- input UniProt FASTA sequence
    protein_length             INTEGER NOT NULL,
    deeptmhmm_label            TEXT NOT NULL,        -- TM | SP | SP+TM | BETA | GLOB
    tm_helix_count             INTEGER NOT NULL,
    beta_strand_count          INTEGER NOT NULL,
    n_terminal_orientation     TEXT NOT NULL,        -- extracellular | cytoplasmic | indeterminate
    c_terminal_orientation     TEXT NOT NULL,
    signal_peptide_length      INTEGER NOT NULL,
    ecd_length_residues        INTEGER NOT NULL,     -- count of 'O' chars in per_residue_topology
    icd_length_residues        INTEGER NOT NULL,     -- count of 'I' chars
    per_residue_topology       TEXT NOT NULL,        -- O/M/I/S/B chars; len == protein_length
    predicted_surface_membrane INTEGER NOT NULL,     -- 1 iff label in {TM, SP+TM}
    predicted_secreted         INTEGER NOT NULL,     -- 1 iff label == SP
    tool_version               TEXT NOT NULL,        -- e.g. 'deeptmhmm-1.0.24'
    retrieved_at               TEXT NOT NULL,        -- ISO 8601 timestamp
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


-- ---------------------------------------------------------------------------
-- topology_release — pointer to the active topology_version so the Worker
-- doesn't have to MAX() over a 30k-row table to find "latest".
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS topology_release (
    topology_version    TEXT PRIMARY KEY,
    n_rows              INTEGER NOT NULL,
    cohorts_present     TEXT NOT NULL,                -- comma-separated cohort list
    deeptmhmm_version   TEXT NOT NULL,                -- e.g. 'deeptmhmm-1.0.24'
    attribution         TEXT,                         -- e.g. 'DeepTMHMM 1.0.24 (DTU)'
    license_url         TEXT,                         -- DeepTMHMM license URL
    loaded_at           TEXT NOT NULL DEFAULT (datetime('now')),
    source_run_dir      TEXT,                         -- relative path of source run dir
    notes               TEXT
);


-- ---------------------------------------------------------------------------
-- compara_paralog — Ensembl Compara within-species paralogs.
--
-- One row per (paralog_version, human_ensembl_gene, paralog_ensembl_gene).
-- biomart_percent_identity carries the BioMart full-length value verbatim;
-- ecd_pct_identity is computed locally as a per-loop BLOSUM62 length-weighted
-- average (see merge/paralog_ecd_identity.py). NULL when either protein has
-- no extracellular residues per its DeepTMHMM topology.
--
-- Per-gene cap: top 50 paralogs by biomart_percent_identity DESC. Families
-- like IG / TCR have hundreds of members and would explode this table.
--
-- Stable-ID join target: ``human_hgnc_id`` and ``paralog_hgnc_id`` are
-- denormalized for the same reason as topology_public. Ensembl gene IDs
-- (ENSG...) are the actual Compara primary keys but are not resolver-stable
-- across Ensembl release bumps — the HGNC IDs are.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS compara_paralog (
    paralog_version          TEXT NOT NULL,
    human_hgnc_id            TEXT,                    -- stable join key (NULL when gene_identifier lookup fails)
    human_ensembl_gene       TEXT NOT NULL,           -- Compara primary input key
    human_uniprot_acc        TEXT,
    human_gene_symbol        TEXT,
    paralog_hgnc_id          TEXT,                    -- stable join key for the paralog
    paralog_ensembl_gene     TEXT NOT NULL,
    paralog_uniprot_acc      TEXT,
    paralog_gene_symbol      TEXT,
    family_id                TEXT,                    -- ENSFM... Compara family / clade subtype
    biomart_percent_identity REAL,                    -- from BioMart, full-length
    ecd_pct_identity         REAL,                    -- per-loop BLOSUM62 length-weighted; NULL when no ECD
    n_ecd_loops_compared     INTEGER,                 -- # loop pairs aligned
    rank_by_ecd_identity     INTEGER,                 -- 1=closest paralog; NULLs sort last
    paralogy_type            TEXT,                    -- within_species_paralog | other_paralog | gene_split
    is_high_confidence       INTEGER NOT NULL,
    compara_version          TEXT NOT NULL,           -- e.g. 'Compara r112'
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


-- ---------------------------------------------------------------------------
-- compara_paralog_release — pointer to the active paralog_version.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS compara_paralog_release (
    paralog_version    TEXT PRIMARY KEY,
    compara_release    TEXT NOT NULL,                  -- e.g. 'Compara r112'
    n_pairs            INTEGER NOT NULL,
    n_human_genes      INTEGER NOT NULL,
    fetched_at         TEXT NOT NULL DEFAULT (datetime('now')),
    source_url         TEXT,
    notes              TEXT
);


-- ---------------------------------------------------------------------------
-- compara_ortholog_ecd — locally-computed per-loop ECD identity between
-- a human canonical and its mouse/cyno one2one ortholog.
--
-- compara_ortholog (the BioMart row) gives us full-length percent_identity,
-- which is biased AGAINST surface proteins — TM + cytoplasmic regions
-- diverge faster than ECDs. This table carries the per-loop BLOSUM62
-- length-weighted ECD identity computed against the DeepTMHMM topology
-- of both proteins (see merge/paralog_ecd_identity.py — same algorithm,
-- different input pair).
--
-- One row per (ortholog_ecd_version, human_hgnc_id, species,
-- ortholog_uniprot_acc). species column is denormalized so consumers can
-- filter without joining compara_ortholog.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS compara_ortholog_ecd (
    ortholog_ecd_version     TEXT NOT NULL,
    human_hgnc_id            TEXT NOT NULL,             -- stable join into gene_identifier_public
    human_uniprot_acc        TEXT,
    human_ensembl_gene       TEXT,
    human_gene_symbol        TEXT,
    species                  TEXT NOT NULL,             -- mouse | cynomolgus
    ortholog_uniprot_acc     TEXT NOT NULL,
    ortholog_ensembl_gene    TEXT,
    ortholog_gene_symbol     TEXT,
    biomart_percent_identity REAL,                      -- full-length, from compara_ortholog
    ecd_pct_identity         REAL,                      -- per-loop BLOSUM62; NULL when no ECD
    n_ecd_loops_compared     INTEGER,
    compara_release          TEXT NOT NULL,             -- e.g. 'ensembl_compara_2026_05_12'
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
