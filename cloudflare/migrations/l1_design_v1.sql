-- L1 library design overlay, v1: suggested tag sites, folded structures and contact
-- sites per L1 member, for the gene-page card and the L1 review page.
--
-- Additive and versioned. No existing table is touched. In particular,
-- library_structure_public and library_topology_public keep their pre-renumbering
-- l1-pNNNN keys, because the viewer's topology <-> structure pairing joins the two
-- on candidate_id. These tables carry the member id (l1-mNNNN) for display, but the
-- loader JOINS every source on design id + sequence sha256, never on member id: the
-- member numbering is still moving.
--
-- Versioning: every row carries load_version, a content address. It is the sha256
-- of the normalized rows, so re-loading identical content is a no-op. The loader
-- writes only INSERT OR IGNORE, so nothing is ever updated or deleted, and it
-- inserts the l1_design_load_public row LAST. The Worker serves the newest load
-- by created_at that has a load row, so a half-applied load is never served.
--
-- Loader:  scripts/cloud/build_l1_design_tables.py
-- Mirrored into cloudflare/d1_public_schema.sql (tests pin the two together).
-- Requested by Becca Carlson, 2026-11-11 and 2026-11-12. Implemented by Claude Code
-- session l1-viewer-tag-sites.

CREATE TABLE IF NOT EXISTS l1_design_load_public (
    load_version     TEXT PRIMARY KEY,   -- 'l1d-' || 16 hex
    content_sha256   TEXT NOT NULL,      -- sha256 over the normalized TSVs
    created_at       TEXT NOT NULL,      -- UTC ISO-8601; the Worker serves the newest
    inputs_json      TEXT NOT NULL,      -- every input: repo, PR, ref, commit, path / object, sha256
    n_members        INTEGER NOT NULL,
    n_sites          INTEGER NOT NULL,
    n_structures     INTEGER NOT NULL,
    n_contacts       INTEGER NOT NULL,
    loader           TEXT NOT NULL,      -- script + accessible-surfaceome commit
    implemented_by   TEXT NOT NULL,
    note             TEXT
);

-- One row per L1 member: its rung and class, so a member with no site row still shows.
CREATE TABLE IF NOT EXISTS l1_member_public (
    load_version       TEXT NOT NULL,
    member_id          TEXT NOT NULL,    -- l1-mNNNN (display; NOT a join key)
    design_id          TEXT,             -- l1-pNNNN
    gene_symbol        TEXT NOT NULL,    -- the member's own gene (cyno orthologs carry the cyno symbol)
    species            TEXT,
    candidate_set      TEXT,             -- library_reference | isoform | ortholog | expression_rescue
    rung               TEXT NOT NULL,    -- tag-path placement
    membrane_class     TEXT NOT NULL,    -- rule-based class (see the loader's _membrane_class)
    n_tm               INTEGER,
    ordered_length_aa  INTEGER,          -- native ordered protein, member numbering
    sequence_sha256    TEXT,             -- sha256 of the ordered protein (the join key with design_id)
    topology_version   TEXT,
    PRIMARY KEY (load_version, member_id)
);
CREATE INDEX IF NOT EXISTS idx_l1_member_public_symbol
    ON l1_member_public (gene_symbol, load_version);

-- One row per tag site: the current pick(s) (is_primary = 1) and the alternatives a
-- source ranked or proposed (is_primary = 0).
CREATE TABLE IF NOT EXISTS l1_tag_site_design_public (
    load_version          TEXT NOT NULL,
    site_id               TEXT NOT NULL,     -- stable across loads for the same pick
    member_id             TEXT NOT NULL,
    design_id             TEXT,
    gene_symbol           TEXT NOT NULL,
    species               TEXT,
    candidate_set         TEXT,
    rung                  TEXT NOT NULL,
    site_source           TEXT NOT NULL,     -- rung_builder | ranker | agent_proposer
    is_primary            INTEGER NOT NULL,  -- 1 = the member's current pick
    insert_after_residue  INTEGER,           -- member's OWN native numbering; 0 = before residue 1; NULL = no site
    residue_before        TEXT,
    residue_after         TEXT,
    leader                TEXT,              -- 'igk' when an Igk leader is prepended, else NULL
    cassette              TEXT,
    cassette_aa           INTEGER,           -- length actually inserted (protein - native), when built
    rank                  INTEGER,
    status                TEXT NOT NULL,     -- built | decided_not_built | no_tag | pending | alternative
    decision              TEXT,              -- the source's own decision / design value, verbatim
    status_detail         TEXT,              -- the source's own status / verdict, verbatim
    confidence            TEXT,
    rejected_alternative  TEXT,
    rationale_json        TEXT,              -- scores, gate results, lane check, loop evidence, refold verdict
    tagged_protein_sha256 TEXT,
    source_pr             INTEGER,           -- design-repository PR number
    source_pr_state       TEXT,
    source_commit         TEXT NOT NULL,
    source_path           TEXT NOT NULL,
    decided_by            TEXT NOT NULL,
    implemented_by        TEXT NOT NULL,
    reason                TEXT,
    PRIMARY KEY (load_version, site_id)
);
CREATE INDEX IF NOT EXISTS idx_l1_tag_site_design_public_symbol
    ON l1_tag_site_design_public (gene_symbol, load_version);
CREATE INDEX IF NOT EXISTS idx_l1_tag_site_design_public_member
    ON l1_tag_site_design_public (member_id, load_version);

-- One row per (member, structure). kind = 'native' (the payload's choice, plus its
-- labelled alternates) or 'tagged' (a refold of the tagged construct).
CREATE TABLE IF NOT EXISTS l1_structure_design_public (
    load_version            TEXT NOT NULL,
    structure_id            TEXT NOT NULL,
    member_id               TEXT NOT NULL,
    design_id               TEXT,
    gene_symbol             TEXT NOT NULL,
    kind                    TEXT NOT NULL,   -- native | tagged
    site_id                 TEXT,            -- tagged: the site folded
    source                  TEXT NOT NULL,   -- alphafold_db | colabfold | colabfold_tagged
    release                 TEXT,
    s3_uri                  TEXT,            -- object-store provenance of our own models
    r2_key                  TEXT,            -- object under surfaceome-structures; NULL for AFDB
    model_url               TEXT,            -- AFDB URL; NULL for ours
    proteoform_match        TEXT,
    residue_offset          INTEGER NOT NULL DEFAULT 0,  -- native residue i == model residue i + offset
    ordered_length_aa       INTEGER,
    model_length_aa         INTEGER,
    is_chosen               INTEGER NOT NULL,            -- 1 = render this one for its kind
    mean_plddt              REAL,
    cassette_first_model_residue INTEGER,    -- tagged: cassette span in MODEL numbering
    cassette_last_model_residue  INTEGER,
    refold_verdict          TEXT,
    note                    TEXT,
    decided_by              TEXT NOT NULL,
    implemented_by          TEXT NOT NULL,
    reason                  TEXT,
    PRIMARY KEY (load_version, structure_id)
);
CREATE INDEX IF NOT EXISTS idx_l1_structure_design_public_symbol
    ON l1_structure_design_public (gene_symbol, load_version);

-- One row per (member, residue, source) contact annotation, in the member's own
-- numbering. source = literature_agent (agent-extracted from papers, mechanically
-- verified, NOT scored against a truth set) | uniprot_binding.
CREATE TABLE IF NOT EXISTS l1_contact_site_public (
    load_version        TEXT NOT NULL,
    member_id           TEXT NOT NULL,
    design_id           TEXT,
    gene_symbol         TEXT NOT NULL,
    residue             INTEGER NOT NULL,   -- member's own numbering
    aa                  TEXT,
    canonical_residue   INTEGER,
    source              TEXT NOT NULL,
    evidence_types      TEXT,
    contact_classes     TEXT,
    confidence_tier     TEXT NOT NULL,      -- high | lower | hidden (ion / additive)
    ion_site            INTEGER,
    additive_only       INTEGER,
    in_extracellular    INTEGER,
    topology_state      TEXT,
    ligands             TEXT,
    pmids               TEXT,
    PRIMARY KEY (load_version, member_id, residue, source)
);
CREATE INDEX IF NOT EXISTS idx_l1_contact_site_public_symbol
    ON l1_contact_site_public (gene_symbol, load_version);
