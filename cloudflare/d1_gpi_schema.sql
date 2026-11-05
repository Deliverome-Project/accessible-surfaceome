-- Per-form predictor output and curation are separate, append-only records.
-- Apply identically to surfaceome_agents and surfaceome_public. This does not
-- change the architecture annotation or any served gene's final GPI decision.
CREATE TABLE IF NOT EXISTS netgpi_prediction (
    run_id TEXT NOT NULL,
    record_id TEXT NOT NULL,
    prediction_number INTEGER NOT NULL,
    tool_version TEXT NOT NULL,
    job_id TEXT,
    sequence_sha256 TEXT,
    sequence TEXT,
    sequence_resolution TEXT NOT NULL,
    sequence_length INTEGER NOT NULL,
    prediction TEXT NOT NULL,
    likelihood_text TEXT NOT NULL,
    omega_position INTEGER,
    omega_residue TEXT,
    raw_line TEXT NOT NULL,
    raw_header TEXT NOT NULL,
    source_uri TEXT NOT NULL,
    source_sha256 TEXT NOT NULL,
    import_code_sha TEXT NOT NULL,
    members_json TEXT NOT NULL,
    PRIMARY KEY (run_id, record_id),
    UNIQUE (run_id, prediction_number)
);
CREATE INDEX IF NOT EXISTS idx_netgpi_sequence ON netgpi_prediction(sequence_sha256);

CREATE TABLE IF NOT EXISTS gpi_curation_record (
    source_sha256 TEXT NOT NULL,
    record_number INTEGER NOT NULL,
    source_kind TEXT NOT NULL,
    gene_symbol TEXT,
    source_uri TEXT NOT NULL,
    import_code_sha TEXT NOT NULL,
    record_json TEXT NOT NULL,
    PRIMARY KEY (source_sha256, record_number)
);
CREATE INDEX IF NOT EXISTS idx_gpi_curation_gene ON gpi_curation_record(gene_symbol);
