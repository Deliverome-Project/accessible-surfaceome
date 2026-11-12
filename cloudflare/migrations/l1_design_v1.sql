-- L1 library design overlay, v1: suggested tag sites and folded structures per L1 member.
--
-- Additive and versioned. No existing table is touched. In particular,
-- library_structure_public and library_topology_public keep their pre-renumbering
-- l1-pNNNN keys, because the viewer's topology <-> structure pairing joins the two
-- on candidate_id. These tables key on the member id (l1-mNNNN) and carry
-- the design id (l1-pNNNN) alongside it.
--
-- Versioning: every row carries load_version, a content address. It is the sha256
-- of the normalized rows, so re-loading identical content is a no-op. The loader
-- writes only INSERT OR IGNORE, so nothing is ever updated or deleted, and it
-- inserts the l1_design_load_public row LAST. The Worker serves the newest load
-- by created_at that has a load row, so a half-applied load is never served.
--
-- Loader:  scripts/cloud/build_l1_design_tables.py
-- Mirrored into cloudflare/d1_public_schema.sql (tests pin the two together).
-- Requested by Becca Carlson, 2026-11-11 ("update the viewer with suggested tag
-- sites as well as with folded versions"). Implemented by Claude Code session
-- l1-viewer-tag-sites.

CREATE TABLE IF NOT EXISTS l1_design_load_public (
    load_version     TEXT PRIMARY KEY,   -- 'l1d-' || first 16 hex of content_sha256
    content_sha256   TEXT NOT NULL,      -- sha256 over the three normalized TSVs
    created_at       TEXT NOT NULL,      -- UTC ISO-8601; the Worker serves the newest
    inputs_json      TEXT NOT NULL,      -- every input: repo, PR, ref, commit, path, sha256 / S3 URI
    n_members        INTEGER NOT NULL,
    n_sites          INTEGER NOT NULL,
    n_structures     INTEGER NOT NULL,
    loader           TEXT NOT NULL,      -- script + accessible-surfaceome commit
    implemented_by   TEXT NOT NULL,
    note             TEXT
);

-- One row per L1 member: its rung, so a member with no site row yet still shows.
CREATE TABLE IF NOT EXISTS l1_member_public (
    load_version       TEXT NOT NULL,
    member_id          TEXT NOT NULL,    -- l1-mNNNN (plate order)
    design_id          TEXT,             -- l1-pNNNN (pre-renumbering design id)
    gene_symbol        TEXT NOT NULL,    -- the member's own gene (cyno orthologs carry the cyno symbol)
    species            TEXT,
    candidate_set      TEXT,             -- library_reference | isoform | ortholog | expression_rescue
    rung               TEXT NOT NULL,    -- l1_tag_paths.placement
    ordered_length_aa  INTEGER,          -- native ordered protein, member numbering
    sequence_sha256    TEXT,
    topology_version   TEXT,
    PRIMARY KEY (load_version, member_id)
);
CREATE INDEX IF NOT EXISTS idx_l1_member_public_symbol
    ON l1_member_public (gene_symbol, load_version);

-- One row per suggested tag site. A member can carry several (internal picks are ranked).
CREATE TABLE IF NOT EXISTS l1_tag_site_design_public (
    load_version          TEXT NOT NULL,
    site_id               TEXT NOT NULL,     -- stable across loads for the same pick
    member_id             TEXT NOT NULL,
    design_id             TEXT,
    gene_symbol           TEXT NOT NULL,
    species               TEXT,
    candidate_set         TEXT,
    rung                  TEXT NOT NULL,
    insert_after_residue  INTEGER,           -- member's OWN native numbering; 0 = before residue 1; NULL = no site chosen
    residue_before        TEXT,
    residue_after         TEXT,
    leader                TEXT,              -- 'igk' when an Igk leader is prepended, else NULL
    cassette              TEXT,              -- as the source states it
    cassette_aa           INTEGER,           -- length actually inserted (protein - native), when built
    rank                  INTEGER,           -- internal-loop pick rank; NULL elsewhere
    status                TEXT NOT NULL,     -- built | proposed | held
    status_detail         TEXT,              -- the source's own status / verdict, verbatim
    tagged_protein_sha256 TEXT,
    source_pr             INTEGER,           -- design-repository PR number
    source_pr_state       TEXT,              -- open | merged, at load time
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
    site_id                 TEXT,            -- tagged: the l1_tag_site_design_public site folded
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
    note                    TEXT,
    decided_by              TEXT NOT NULL,
    implemented_by          TEXT NOT NULL,
    reason                  TEXT,
    PRIMARY KEY (load_version, structure_id)
);
CREATE INDEX IF NOT EXISTS idx_l1_structure_design_public_symbol
    ON l1_structure_design_public (gene_symbol, load_version);
