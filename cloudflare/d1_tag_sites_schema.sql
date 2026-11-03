-- tag_site_public — per-site tag-insertion records served at /v1/tag-sites/:symbol.
-- Canonical DDL; kept in sync with src/accessible_surfaceome/cloud/tag_sites.py::DDL
-- and mirrored into cloudflare/d1_public_schema.sql. One row per TaggedSite (the
-- viewer/lib/tag-sites-types.ts contract). Additive; no existing table touched.

CREATE TABLE IF NOT EXISTS tag_site_public (
  gene_symbol                TEXT NOT NULL,
  uniprot_acc                TEXT NOT NULL,
  site_id                    TEXT NOT NULL,
  provenance                 TEXT NOT NULL,
  det_path                   TEXT,
  site_kind                  TEXT NOT NULL,
  insert_after_residue       INTEGER,
  residue_before             TEXT,
  residue_after              TEXT,
  residue_label              TEXT,
  residue_range              TEXT,
  topology_state             TEXT,
  extracellular              INTEGER NOT NULL,
  compartment                TEXT,
  tag_type                   TEXT,
  tag_length_aa              INTEGER,
  linker                     TEXT,
  evidence_type              TEXT,
  functional_impact_measured TEXT,
  confidence                 TEXT,
  rationale                  TEXT,
  sources_json               TEXT,
  plddt                      REAL,
  conservation_rank          INTEGER,
  median_conservation        REAL,
  tag_sites_version          TEXT NOT NULL,
  synced_at                  TEXT NOT NULL,
  -- Agent metadata. These were added to tag_sites.py::DDL and never mirrored
  -- here, so the "kept in sync" note above was false for five columns; a Worker
  -- reviewer reading only this file could not see what the route serves.
  validation_level           TEXT,
  position_evidence          TEXT,
  source_tier                TEXT,
  cited_tag_residue          INTEGER,
  entailment_verified        INTEGER,
  -- The proteoform frame a citation was numbering in when it was not the
  -- protein's own ("mature", "isoform:P54289-2"); NULL for the ordinary case.
  position_frame             TEXT,
  -- Which library MEMBER this site describes, and the sequence its position is
  -- expressed in. A gene is not a unit: 45 of the 518 internal-site genes have
  -- more than one member, 7 of those disagree about where the tag can go, and
  -- 71 of 566 members are not numbered on the human canonical protein.
  candidate_id               TEXT,
  library                    TEXT,
  numbered_against           TEXT,
  -- inter_tm / n_terminal / c_terminal / no_tm, derived from topology rather
  -- than read off site_kind, which does not discriminate at low positions.
  loop_run_position          TEXT,
  PRIMARY KEY (uniprot_acc, site_id)
);
CREATE INDEX IF NOT EXISTS idx_tag_site_symbol ON tag_site_public (gene_symbol);
CREATE INDEX IF NOT EXISTS idx_tag_site_provenance ON tag_site_public (provenance);

-- ====================================================================
-- tag_site_gene_public — per-GENE tag-site search facts (see
-- src/accessible_surfaceome/cloud/tag_site_genes.py). Presence of a row is the
-- claim "this gene was searched, under this prompt, on this date", so a gene
-- ABSENT here is unsearched — which is the distinction the table exists for.
-- 1,415 of its rows are dated zeros, and a zero that loses its date costs a
-- real literature search to reproduce.
-- Keyed on (gene_symbol, candidate_id, run_series) so a second pass over the
-- same gene, or a second library member of it, is another search rather than
-- an overwrite.
-- ====================================================================
CREATE TABLE IF NOT EXISTS tag_site_gene_public (
    gene_symbol          TEXT NOT NULL,
    -- The library MEMBER this search describes, or '' for a gene-level search.
    -- Empty string rather than NULL: a NULL in a primary key does not compare
    -- equal to itself, so NULL-keyed rows multiply silently on every UPSERT.
    candidate_id         TEXT NOT NULL DEFAULT '',
    -- Which pass this is. The two literature passes are different searches of
    -- the same gene and both answers are worth keeping, so the series is part
    -- of the key rather than something one overwrites the other through.
    run_series           TEXT NOT NULL DEFAULT 'literature_v1',
    uniprot_acc          TEXT,
    searched_at          TEXT,
    prompt_sha           TEXT,
    prompt_version       TEXT,
    model                TEXT,
    schema_version       TEXT,
    n_papers             INTEGER,
    n_sites              INTEGER NOT NULL DEFAULT 0,
    n_other_positions    INTEGER NOT NULL DEFAULT 0,
    other_positions_json TEXT,
    notes                TEXT,
    tag_sites_version    TEXT,
    synced_at            TEXT,
    PRIMARY KEY (gene_symbol, candidate_id, run_series)
);
CREATE INDEX IF NOT EXISTS idx_tsgp_prompt ON tag_site_gene_public (prompt_sha);
CREATE INDEX IF NOT EXISTS idx_tsgp_nsites ON tag_site_gene_public (n_sites);
