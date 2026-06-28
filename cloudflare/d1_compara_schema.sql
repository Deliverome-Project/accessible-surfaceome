-- NOTE: This file is a REFERENCE schema only.
-- Production tables are named differently (e.g. compara_ortholog_ecd
-- not compara_ortholog); see scripts/audit/audit_evidence_retrieval.py
-- and the live D1 console for current names. Do not apply this file
-- directly to production D1.
--
-- Ensembl Compara ortholog tables for the surfaceome_agents D1 database.
--
-- Layered on top of `cloudflare/d1_schema.sql`. The deep-dive agent's
-- DeepDivePackLoader reads from `compara_ortholog` in production; the
-- CSV at data/external/ensembl_compara_surfaceome_expressed/ becomes a
-- refresh artifact, not a runtime dependency.
--
-- Reproducibility goal: every Compara pull is stamped with a release
-- version (e.g. "ensembl_compara_2026_05_11"), so older deep-dive
-- annotations can be replayed against the exact ortholog snapshot they
-- saw at the time. Re-fetching produces a new release_version row;
-- the old one stays queryable.
--
-- To apply (once after `cloudflare/d1_schema.sql` is provisioned):
--
--   wrangler d1 execute surfaceome_agents \
--     --remote \
--     --file=cloudflare/d1_compara_schema.sql

-- ---------------------------------------------------------------------------
-- compara_release — one row per BioMart fetch (Ensembl release × date)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS compara_release (
    release_version  TEXT PRIMARY KEY,     -- e.g. "ensembl_compara_2026_05_11"
    fetched_at       TEXT NOT NULL DEFAULT (datetime('now')),
    n_pairs          INTEGER NOT NULL,     -- total ortholog rows in this release
    source_url       TEXT,                 -- BioMart endpoint that produced the rows
    notes            TEXT                  -- optional free-text refresh notes
);


-- ---------------------------------------------------------------------------
-- compara_ortholog — one row per (release × human-gene × species × ortholog)
-- ---------------------------------------------------------------------------
--
-- Scope: one-to-one + high-confidence orthologs only (matches the producer
-- in src/accessible_surfaceome/sources/ensembl_compara.py). One row per
-- (human gene, species), so a human gene has at most 2 rows per release
-- (mouse + cynomolgus).

CREATE TABLE IF NOT EXISTS compara_ortholog (
    release_version       TEXT NOT NULL,
    human_ensembl_gene    TEXT NOT NULL,           -- ENSG…
    human_uniprot_acc     TEXT,                    -- UniProt acc of the human protein (may be NULL for genes without a reviewed entry)
    human_gene_symbol     TEXT,                    -- HGNC symbol
    species               TEXT NOT NULL,           -- "mouse" | "cynomolgus"
    ortholog_ensembl_gene TEXT NOT NULL,           -- ENSMUSG… / ENSMFAG…
    ortholog_uniprot_acc  TEXT,                    -- UniProt of the ortholog (may be NULL)
    ortholog_gene_symbol  TEXT,                    -- MGI / cyno symbol
    orthology_type        TEXT NOT NULL,           -- one_to_one | one_to_many | many_to_many | no_ortholog | unknown
    percent_identity      REAL,                    -- Compara percent_identity (0–100)
    is_high_confidence    INTEGER NOT NULL,        -- 1 iff Compara flagged this pair high-confidence
    PRIMARY KEY (release_version, human_ensembl_gene, species, ortholog_ensembl_gene),
    FOREIGN KEY (release_version) REFERENCES compara_release(release_version)
);

CREATE INDEX IF NOT EXISTS idx_compara_ortholog_human_uniprot
    ON compara_ortholog (human_uniprot_acc);
CREATE INDEX IF NOT EXISTS idx_compara_ortholog_human_symbol
    ON compara_ortholog (human_gene_symbol);
CREATE INDEX IF NOT EXISTS idx_compara_ortholog_release_species
    ON compara_ortholog (release_version, species);
