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
-- (Raw prompt text + raw_text stay private. verdict_reasoning IS
-- mirrored here — it's served per-gene at /v1/triage/:symbol and in
-- the bulk triage export when with_reasoning=1, so the genome-wide
-- agent reasoning is public; only the raw prompt/response text
-- distinguishes private from public.)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS triage_run_public (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id              TEXT NOT NULL,
    created_at          TEXT NOT NULL,

    gene_symbol         TEXT NOT NULL,
    uniprot_acc         TEXT,
    hgnc_id             TEXT,
    ensembl_gene        TEXT,
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

CREATE INDEX IF NOT EXISTS idx_gene_identifier_public_symbol       ON gene_identifier_public (hgnc_symbol);
CREATE INDEX IF NOT EXISTS idx_gene_identifier_public_uniprot      ON gene_identifier_public (uniprot_acc);
CREATE INDEX IF NOT EXISTS idx_gene_identifier_public_ncbi         ON gene_identifier_public (ncbi_gene_id);
CREATE INDEX IF NOT EXISTS idx_gene_identifier_public_ensembl      ON gene_identifier_public (ensembl_gene);
CREATE INDEX IF NOT EXISTS idx_gene_identifier_public_cohort       ON gene_identifier_public (cohort_symbol);
CREATE INDEX IF NOT EXISTS idx_gene_identifier_public_needs_review ON gene_identifier_public (needs_review);


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
    ecd_pct_identity         REAL,                    -- per-loop BLOSUM62 length-weighted identity; NULL when no ECD
    ecd_pct_similarity       REAL,                    -- per-loop BLOSUM62 identity + positive substitutions; NULL when no ECD (populated for close pairs >=80% full-length)
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


-- ---------------------------------------------------------------------------
-- SURFACE-Bind (Balbi et al. 2026 PNAS, doi:10.1073/pnas.2506269123)
--
-- Per-UniProt patch-targetability summary + per-site detail from the
-- Correia lab's MaSIF / surface-fingerprinting mapping of the human
-- surfaceome. Sourced from the SURFACE-Bind GitHub repo's
-- `database/results_no_TM_pnames.csv` (per-site data) and the
-- `seed_count_*.txt` files (chain identifier xref).
--
-- Two tables: protein-level aggregate (one row per UniProt acc) +
-- site-level detail (one row per (acc, site_id)). Sync script:
-- scripts/sync_surface_bind_to_d1.py reads from
-- data/external/surface_bind/surface_bind_summary.json and UPSERTs.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS surface_bind_protein (
    uniprot_acc      TEXT PRIMARY KEY,
    chain            TEXT,                              -- PDB-chain ID; 'A' for most entries
    main_class       TEXT,                              -- Receptors / Enzymes / Transporters / Miscellaneous / Unclassified / Unmatched
    sub_class        TEXT,                              -- e.g. Kinase, GPCR, SLC, Hydrolases
    protein_name     TEXT,                              -- human-readable; UniProt-sourced via SURFACE-Bind
    n_sites          INTEGER NOT NULL,                  -- count of scored patches
    n_seeds_alpha    INTEGER NOT NULL,                  -- α-helical binder seed total across sites
    n_seeds_beta     INTEGER NOT NULL,                  -- β-strand binder seed total across sites
    n_seeds_total    INTEGER NOT NULL,
    pdbs             TEXT,                              -- JSON list of PDB IDs (often 100+)
    surfacebind_version TEXT NOT NULL,                  -- e.g. '2024-08-09'
    synced_at        TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_surface_bind_protein_main_class
    ON surface_bind_protein (main_class);
CREATE INDEX IF NOT EXISTS idx_surface_bind_protein_sub_class
    ON surface_bind_protein (sub_class);
CREATE INDEX IF NOT EXISTS idx_surface_bind_protein_n_sites
    ON surface_bind_protein (n_sites);


CREATE TABLE IF NOT EXISTS surface_bind_site (
    uniprot_acc      TEXT NOT NULL,
    site_id          INTEGER NOT NULL,                  -- 0-indexed within the protein
    anchor_residue   INTEGER NOT NULL,                  -- center residue of the MaSIF patch
    area_a2          REAL NOT NULL,                     -- buried surface area in Å²
    n_seeds_alpha    INTEGER NOT NULL,                  -- per-site α-seed count
    n_seeds_beta     INTEGER NOT NULL,                  -- per-site β-seed count
    hydrophobicity   REAL NOT NULL,                     -- Eisenberg-style patch hydrophobicity
    surfacebind_version TEXT NOT NULL,
    synced_at        TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (uniprot_acc, site_id),
    FOREIGN KEY (uniprot_acc) REFERENCES surface_bind_protein (uniprot_acc)
);

CREATE INDEX IF NOT EXISTS idx_surface_bind_site_area
    ON surface_bind_site (area_a2);
CREATE INDEX IF NOT EXISTS idx_surface_bind_site_alpha
    ON surface_bind_site (n_seeds_alpha);
CREATE INDEX IF NOT EXISTS idx_surface_bind_site_beta
    ON surface_bind_site (n_seeds_beta);

-- ---------------------------------------------------------------------------
-- Schweke 2024 homo-oligomer prediction (public mirror)
-- ---------------------------------------------------------------------------
-- Schweke et al. 2024 (Cell 187:999, PMID 38325366, DOI
-- 10.1016/j.cell.2024.01.022) — AF2-based per-UniProt homo-oligomer
-- atlas. The published refset covers ~8,195 proteins across four
-- proteomes; the intersection with our candidate-universe surfaceome
-- is 1,205 proteins (~273 with higher-order complexes c >=3, max
-- stoichiometry 13).
--
-- **Positives-only.** A row means "predicted homo-oligomer at the
-- configured ``dimer_proba`` threshold"; a missing row means "not in
-- the positive set" rather than "AF2 explicitly disagrees" (well-
-- documented under-call: KCNQ1/KCNMA1, EGFR/INSR, etc. are missing
-- despite being known dimers). Consumers default ``is_homo_oligomer
-- =False`` for any uniprot_acc with no row.
--
-- Sync script: ``scripts/build_schweke_d1_table.py`` reads the figshare
-- deposit (see ``data/external/schweke_homomer_atlas/PROVENANCE.md``)
-- and UPSERTs per ``(universe_version, uniprot_acc)``. Released here as
-- a public mirror — CC-BY 4.0 per Schweke's deposit, attribution
-- "Schweke et al. 2024, Cell 187:999, CC-BY 4.0".

CREATE TABLE IF NOT EXISTS schweke_homomer_public (
    universe_version          TEXT NOT NULL,                         -- joins to candidate_universe_release
    hgnc_id                   TEXT,
    uniprot_acc               TEXT NOT NULL,                         -- the join key consumers use
    gene_symbol               TEXT,
    ensembl_gene              TEXT,
    ncbi_gene_id              TEXT,
    af_model_num              INTEGER NOT NULL,                      -- AF2 model rank 1..5 Schweke retained
    stoichiometry             INTEGER NOT NULL,                      -- cyclic-symmetry order N (2..13)
    has_higher_order_complex  INTEGER NOT NULL,                      -- 1 iff a c>=3 complex was reconstructed
    is_ecd_only               INTEGER NOT NULL,                      -- 1 iff Schweke's nodiso3 stripped TM
    dimer_pdb_filename        TEXT NOT NULL,                         -- ``{ACC}_V1_{model_num}.pdb`` convention
    complex_pdb_filename      TEXT,                                  -- ``{ACC}_V1_{model_num}_c{N}_model_0_rank_1.pdb`` when has_higher_order=1
    schweke_version           TEXT NOT NULL,                         -- e.g. 'schweke-2024-cell'
    synced_at                 TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (universe_version, uniprot_acc),
    FOREIGN KEY (universe_version) REFERENCES candidate_universe_release (universe_version)
);

CREATE INDEX IF NOT EXISTS idx_schweke_homomer_public_uniprot
    ON schweke_homomer_public (uniprot_acc);
CREATE INDEX IF NOT EXISTS idx_schweke_homomer_public_hgnc
    ON schweke_homomer_public (hgnc_id);
CREATE INDEX IF NOT EXISTS idx_schweke_homomer_public_symbol
    ON schweke_homomer_public (gene_symbol);
CREATE INDEX IF NOT EXISTS idx_schweke_homomer_public_stoich
    ON schweke_homomer_public (universe_version, stoichiometry);
CREATE INDEX IF NOT EXISTS idx_schweke_homomer_public_ecd_only
    ON schweke_homomer_public (universe_version, is_ecd_only);


CREATE TABLE IF NOT EXISTS schweke_homomer_release (
    schweke_version            TEXT PRIMARY KEY,                     -- e.g. 'schweke-2024-cell'
    universe_version           TEXT NOT NULL,                        -- candidate-universe snapshot intersected against
    paper_doi                  TEXT NOT NULL,                        -- '10.1016/j.cell.2024.01.022'
    pmid                       TEXT NOT NULL,                        -- '38325366'
    figshare_doi               TEXT NOT NULL,                        -- '10.6084/m9.figshare.22309177'
    figshare_share_link        TEXT NOT NULL,                        -- private-link recovery path
    n_proteins_in_schweke      INTEGER NOT NULL,                     -- full Schweke positives (across proteomes)
    n_proteins_in_intersection INTEGER NOT NULL,                     -- positives ∩ candidate_universe (~1205)
    n_with_higher_order        INTEGER NOT NULL,                     -- subset with c >= 3
    max_stoichiometry          INTEGER NOT NULL,                     -- 13 in the 2024-cell release
    attribution                TEXT NOT NULL,                        -- 'Schweke et al. 2024, Cell 187:999, CC-BY 4.0'
    license_url                TEXT,                                 -- 'https://creativecommons.org/licenses/by/4.0/'
    loaded_at                  TEXT NOT NULL DEFAULT (datetime('now')),
    notes                      TEXT
);


-- ---------------------------------------------------------------------------
-- Approved-only community notes (public mirror)
-- ---------------------------------------------------------------------------
-- Sanitized subset of surfaceome_agents.feedback rows where status =
-- 'approved_public'. Inserted by the Worker's magic-link approval
-- handler. The viewer fetches from here via GET /v1/feedback/public.

CREATE TABLE IF NOT EXISTS feedback_public (
    id              TEXT PRIMARY KEY,                          -- same id as private feedback row
    gene_symbol     TEXT NOT NULL,                             -- e.g. "SRC"
    submitter_name  TEXT NOT NULL,                             -- attribution; e-mail never published
    comment         TEXT NOT NULL,                             -- sanitized at insert time
    approved_at     TEXT NOT NULL DEFAULT (datetime('now'))    -- both moderation timestamp and public-mirror write time
);

CREATE INDEX IF NOT EXISTS idx_feedback_public_gene
    ON feedback_public(gene_symbol, approved_at DESC);
