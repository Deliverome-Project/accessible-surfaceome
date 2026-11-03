-- signalp_public — SignalP 6.0 signal-peptide calls, one row per proteoform per run.
--
-- Apply with:
--   npx --yes wrangler d1 execute surfaceome_public --remote \
--       --file=cloudflare/migrations/signalp_public.sql
--
--
-- WHY A SEPARATE TABLE RATHER THAN COLUMNS ON topology_public
--
-- topology_public is keyed on (topology_version, cohort, uniprot_acc_full) and
-- currently holds five topology_versions. A SignalP prediction depends only on
-- the sequence -- not on which topology run happened to be loaded -- so putting
-- it there would mean either duplicating every call five times or attaching it
-- arbitrarily to one version. Both are wrong, and the second silently breaks as
-- soon as a sixth topology version is added.
--
-- So SignalP gets its own version axis. Join to topology on uniprot_acc_full,
-- or through hgnc_id into gene_identifier_public. Never join on gene_symbol:
-- it is denormalized here for offline reading, and paralogs share accessions
-- (OR4F3 / OR4F16 / OR4F29 are all Q6IEY1).
--
--
-- WHAT THIS RUN CAN AND CANNOT SAY
--
-- Run with --organism eukarya, which post-processes to Sec/SPI only. SignalP 6
-- can also distinguish Sec/SPII (lipoprotein), Tat/SPI, Tat/SPII and Sec/SPIII,
-- but under eukarya those are suppressed by design -- correct for human, and the
-- reason there is no sp_type column. A row saying 'SP' means Sec/SPI. Absence of
-- a lipoprotein call is a property of the run, not evidence against one.
--
-- Run in slow-sequential mode: the full six-model ensemble, one model at a time.
-- Unlike DeepTMHMM2, whose weights resolve from a moving branch, SignalP's
-- checkpoints are a fixed DTU release, so tool_version identifies them.

CREATE TABLE IF NOT EXISTS signalp_public (
    signalp_version      TEXT NOT NULL,     -- e.g. 'sp6_2026_09_28'
    uniprot_acc_full     TEXT NOT NULL,     -- with isoform suffix (e.g. O95800-1)
    uniprot_acc          TEXT NOT NULL,     -- base accession, for joins
    hgnc_id              TEXT,              -- stable join key into gene_identifier_public
    gene_symbol          TEXT,              -- denormalized for offline reads; NEVER a join key
    is_canonical         INTEGER NOT NULL,
    protein_length       INTEGER NOT NULL,

    prediction           TEXT NOT NULL,     -- 'SP' (Sec/SPI) | 'OTHER'
    sp_probability       REAL NOT NULL,     -- P(Sec/SPI)
    other_probability    REAL NOT NULL,     -- P(no signal peptide)

    -- Last residue OF the signal peptide: cleavage occurs between cleavage_site
    -- and cleavage_site + 1, so the mature protein starts at cleavage_site + 1.
    -- SignalP reports this as "CS pos: 24-25"; we store 24. NULL when prediction
    -- is OTHER. Deliberately the same convention as topology_public's
    -- signal_peptide_length, so the two are directly comparable without arithmetic.
    cleavage_site        INTEGER,
    cleavage_probability REAL,              -- the "Pr:" value on the CS call

    -- Tripartite decomposition of the signal peptide. The h-region is the
    -- hydrophobic core, which is what an N-terminal tag must not disrupt, so
    -- these are stored rather than left in the gff3 -- they are the part a
    -- construct designer actually needs and cannot re-derive from the numbers
    -- above. NULL when prediction is OTHER.
    n_region_start       INTEGER,
    n_region_end         INTEGER,
    h_region_start       INTEGER,
    h_region_end         INTEGER,
    c_region_start       INTEGER,
    c_region_end         INTEGER,

    organism             TEXT NOT NULL,     -- 'eukarya' | 'other' (the --organism flag)
    mode                 TEXT NOT NULL,     -- 'fast' | 'slow' | 'slow-sequential'
    tool_version         TEXT NOT NULL,     -- e.g. 'signalp-6.0+h'
    retrieved_at         TEXT NOT NULL,     -- ISO 8601
    synced_at            TEXT NOT NULL DEFAULT (datetime('now')),

    PRIMARY KEY (signalp_version, uniprot_acc_full)
);

CREATE INDEX IF NOT EXISTS idx_signalp_public_hgnc
    ON signalp_public (hgnc_id);
CREATE INDEX IF NOT EXISTS idx_signalp_public_uniprot
    ON signalp_public (uniprot_acc);
CREATE INDEX IF NOT EXISTS idx_signalp_public_call
    ON signalp_public (signalp_version, prediction);
