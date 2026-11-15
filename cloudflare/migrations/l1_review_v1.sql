-- L1 review page: reviewer verdicts and alternative-tag suggestions.
--
-- Applied to the PRIVATE surfaceome_agents database (the Worker's FEEDBACK_DB
-- binding), not the public mirror: reviews are internal and are read back only
-- through token-gated endpoints (/v1/l1-review*, header X-L1-Review-Token, checked
-- against the L1_REVIEW_TOKEN secret).
--
-- Append-only. A changed mind is a new row; the page shows each reviewer's latest
-- row per member, and the export carries every row. Members are identified by
-- design_id + sequence_sha256, the join key that survives member renumbering;
-- member_id is recorded as shown.
--
-- Requested by Becca Carlson, 2026-11-12 ("simple buttons for looks good vs no and
-- free text as to why"; "allow users to also suggest alt tags"). Implemented by
-- Claude Code session l1-viewer-tag-sites.

CREATE TABLE IF NOT EXISTS l1_review (
    review_id        TEXT PRIMARY KEY,     -- random UUID
    created_at       TEXT NOT NULL,        -- UTC ISO-8601, set by the Worker
    reviewer         TEXT NOT NULL,
    member_id        TEXT NOT NULL,
    design_id        TEXT NOT NULL,
    sequence_sha256  TEXT,
    gene_symbol      TEXT NOT NULL,
    site_id          TEXT,                 -- NULL = the member as a whole
    verdict          TEXT NOT NULL CHECK (verdict IN ('good', 'no')),
    reason           TEXT,
    load_version     TEXT NOT NULL         -- the design load the reviewer was looking at
);
CREATE INDEX IF NOT EXISTS idx_l1_review_design ON l1_review (design_id, created_at);

CREATE TABLE IF NOT EXISTS l1_alt_tag (
    suggestion_id         TEXT PRIMARY KEY,
    created_at            TEXT NOT NULL,
    reviewer              TEXT NOT NULL,
    member_id             TEXT NOT NULL,
    design_id             TEXT NOT NULL,
    sequence_sha256       TEXT,
    gene_symbol           TEXT NOT NULL,
    insert_after_residue  INTEGER,          -- member's own numbering; NULL for N-/C-term-only placements
    placement             TEXT NOT NULL CHECK (placement IN
                            ('rung_default', 'n_term', 'c_term', 'internal', 'after_sp', 'igk_tag')),
    cassette_variant      TEXT,
    reason                TEXT,
    load_version          TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_l1_alt_tag_design ON l1_alt_tag (design_id, created_at);
