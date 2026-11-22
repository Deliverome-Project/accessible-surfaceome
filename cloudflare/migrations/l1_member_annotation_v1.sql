-- L1 design overlay: per-member signal-peptide status and UniProt comparison.
--
-- Applied to the PUBLIC mirror (surfaceome_public), like l1_design_v1.sql, and only
-- additive: a new table, CREATE TABLE IF NOT EXISTS, so re-applying is a no-op and no
-- existing row or column is touched. Rows come from the design repository's member
-- annotations export through scripts/cloud/build_l1_design_tables.py (source
-- `member_annotations`, keyed design_id + sequence_sha256); a load without that source
-- writes none, and the Worker then serves these fields as null.
--
-- sp_status:
--   native    the member keeps its own signal peptide
--   igk_swap  an Igk leader replaces the native signal peptide
--   igk_res1  an Igk leader is added at residue 1 (no native signal peptide)
--   none      no signal peptide and no leader
-- native_sp_last_residue: last residue of the cleaved native SP, member numbering,
--   filled even when the SP is replaced (GLP2R: 66).
-- matches_uniprot_canonical: 1 when the ordered protein is identical to the canonical.
-- uniprot_diff_json: global-alignment differences, a JSON list of
--   {kind, member_start, member_end, uniprot_start, uniprot_end, member_aa, uniprot_aa}.
--
-- Requested by Becca Carlson, 2026-11-22 (L1 review page: "where do they see if it is
-- igk or not"; "filters for where it's diff from uniprot and show uniprot alongside it").
-- Implemented by Claude Code session l1-review-ui.

CREATE TABLE IF NOT EXISTS l1_member_annotation_public (
    load_version               TEXT NOT NULL,
    member_id                  TEXT NOT NULL,
    design_id                  TEXT,
    gene_symbol                TEXT NOT NULL,
    sp_status                  TEXT CHECK (sp_status IS NULL OR sp_status IN ('native', 'igk_swap', 'igk_res1', 'none')),
    native_sp_last_residue     INTEGER,
    sp_evidence                TEXT,
    uniprot_canonical_acc      TEXT,
    uniprot_canonical_length   INTEGER,
    matches_uniprot_canonical  INTEGER,
    uniprot_diff_json          TEXT,
    PRIMARY KEY (load_version, member_id)
);
