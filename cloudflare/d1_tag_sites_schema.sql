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
  PRIMARY KEY (uniprot_acc, site_id)
);
CREATE INDEX IF NOT EXISTS idx_tag_site_symbol ON tag_site_public (gene_symbol);
CREATE INDEX IF NOT EXISTS idx_tag_site_provenance ON tag_site_public (provenance);
