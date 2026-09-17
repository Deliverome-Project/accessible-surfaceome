-- Internalization records (separate pass from the deep-dive SurfaceomeRecord).
--
-- One row per (gene_symbol, schema_version). Stores the full InternalizationRecord
-- JSON plus flat, queryable projections of the sequence (model-prior) track and —
-- once a literature run lands — the literature track. The sequence sweep
-- (scripts/internalization_seq_sweep.py) writes model-prior-only rows; a later
-- literature run UPSERTs the same key with has_literature=1 and the lit_* columns
-- filled. A future Worker endpoint reads this table the way /v1/genes reads
-- surface_annotation.
CREATE TABLE IF NOT EXISTS surface_internalization (
  gene_symbol                  TEXT NOT NULL,
  schema_version               TEXT NOT NULL,
  hgnc_id                      TEXT,
  uniprot_acc                  TEXT,
  runner_version               TEXT,
  -- sequence (model-prior) track projections
  seq_model                    TEXT,   -- e.g. claude-opus-4-8
  seq_prompt_sha               TEXT,   -- sha256 of the model_prior system prompt (staleness fingerprint)
  seq_prompt_version           TEXT,   -- human-bumpable prompt label (MODEL_PRIOR_PROMPT_VERSION)
  seq_scope                    TEXT,   -- always intrinsic_propensity
  seq_overall_grade            TEXT,   -- SeqGrade: very_high|high|moderate|low|very_low|unknown
  seq_overall_confidence       TEXT,
  seq_canonical_grade          TEXT,   -- the canonical isoform's grade
  seq_canonical_confidence     TEXT,
  n_seq_motifs                 INTEGER,
  n_seq_functional_motifs      INTEGER,-- motifs in a cytoplasmic (functional) region
  -- literature track projections (NULL until a literature run lands)
  has_literature               INTEGER NOT NULL DEFAULT 0,
  lit_overall_grade            TEXT,
  lit_n_observations           INTEGER,
  lit_n_modulator_observations INTEGER,
  lit_prompt_sha               TEXT,   -- sha256 of the lit prompt corpus (triage+select+grade)
  lit_prompt_version           TEXT,   -- human-bumpable lit-prompt label (LIT_PROMPT_VERSION)
  -- full record + provenance
  record_json                  TEXT NOT NULL,
  generated_at                 TEXT,
  updated_at                   TEXT,
  PRIMARY KEY (gene_symbol, schema_version)
);

CREATE INDEX IF NOT EXISTS idx_surface_internalization_symbol
  ON surface_internalization (gene_symbol);
CREATE INDEX IF NOT EXISTS idx_surface_internalization_seq_grade
  ON surface_internalization (seq_overall_grade);
CREATE INDEX IF NOT EXISTS idx_surface_internalization_has_lit
  ON surface_internalization (has_literature);
