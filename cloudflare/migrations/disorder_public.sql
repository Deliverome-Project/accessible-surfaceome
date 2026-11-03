-- disorder_public — per-residue disorder / solvent accessibility, one row per proteoform
-- per predictor per run.
--
-- Apply with:
--   npx --yes wrangler d1 execute surfaceome_public --remote \
--       --file=cloudflare/migrations/disorder_public.sql
--
--
-- WHY ONE TABLE WITH A predictor COLUMN
--
-- Three predictors answer the same question -- where along the sequence is the chain
-- ordered -- and the whole point of running all three is to compare them. One row shape
-- with a predictor column makes that a GROUP BY. Three tables would make it a three-way
-- join on every query, for no gain: the columns genuinely are the same.
--
-- Contrast signalp_public, which is separate from topology_public because SignalP answers
-- a *different* question and could not satisfy that table's NOT NULL columns. Same rule
-- applied both times: shape follows the question, not the tool.
--
--
-- WHAT IS AND IS NOT COMPARABLE ACROSS THE THREE
--
--   metapredict         v3, pLM-based, whole sequence, every proteoform.
--   netsurfp-3.0        the tool Tedman used (as 2.0; 3.0 is the same accuracy, 665x
--                       faster). Run over the N-TERMINAL WINDOW ONLY -- see
--                       window_residues. ESM-1b caps at 1024 tokens and nsp3 does not
--                       chunk, so a whole-protein run is not available at any price.
--   alphafold-disorder  the CAID baseline: windowed RSA (25 residues, +/-12) and
--                       1 - pLDDT, from AlphaFoldDB models. Isoforms included: AFDB does
--                       carry per-isoform models, measured at 99% of this set's 8,835
--                       isoform proteoforms. The isoform accession is requested as-is and
--                       never falls back to the canonical model, so a missing row means
--                       AFDB has no model, not that an isoform was refused.
--
-- So coverage still differs: netsurfp-3.0 rows cover only window_residues, and a few
-- hundred proteins have no AlphaFold model at all. Compare within window_residues.
--
--
-- SCORES ARE QUANTISED TO ONE BYTE PER RESIDUE, HEX-ENCODED
--
-- At full float precision these are ~100 MB of JSON for a signal whose useful resolution
-- is about two decimal places. A byte per residue is ~12.5 MB and loses nothing that
-- matters. Decode: bytes.fromhex(s)[i] / 255.0 for the 0-1 scores; pLDDT is stored as
-- byte/2.55 to recover 0-100. Position i is residue i+1.

CREATE TABLE IF NOT EXISTS disorder_public (
    disorder_version   TEXT NOT NULL,     -- e.g. 'dis_2026_09_28'
    predictor          TEXT NOT NULL,     -- metapredict | netsurfp-3.0 | alphafold-disorder
    uniprot_acc_full   TEXT NOT NULL,     -- with isoform suffix
    uniprot_acc        TEXT NOT NULL,     -- base accession, for joins
    hgnc_id            TEXT,              -- stable join key into gene_identifier_public
    gene_symbol        TEXT,              -- denormalized for offline reads; NEVER a join key
    is_canonical       INTEGER NOT NULL,
    protein_length     INTEGER NOT NULL,  -- of the full protein, not of what was scored

    -- How much of the protein this row actually covers, from residue 1. Equals
    -- protein_length except for netsurfp-3.0, which sees only the N-terminal window.
    -- Every score string below is exactly this long.
    window_residues    INTEGER NOT NULL,

    disorder_hex       TEXT,              -- 0-1 per residue; metapredict and netsurfp
    rsa_hex            TEXT,              -- 0-1 relative solvent accessibility
    plddt_hex          TEXT,              -- 0-100 (byte/2.55); alphafold-disorder only
    ss3                TEXT,              -- H/E/C per residue; netsurfp-3.0 only
    disorder_domains   TEXT,              -- JSON [[start,end],...]; metapredict only

    -- 1 iff a non-standard residue was substituted before prediction (U->C, X->A, ...).
    -- All three predictors reject non-standard letters outright, and dropping those
    -- proteins silently loses the human selenoproteome -- GPX3 and GPX6 are
    -- signal-peptide positive. 27 proteoforms are affected.
    sequence_substituted INTEGER NOT NULL DEFAULT 0,

    tool_version       TEXT NOT NULL,
    modal_app_id       TEXT,              -- the Modal run, e.g. 'ap-...'. The bare id only:
                                          -- the console URL embeds the workspace slug and
                                          -- this database is served publicly.
    git_sha            TEXT,              -- commit the sweep ran from
    git_dirty          INTEGER,           -- 1 iff that tree had uncommitted changes
    retrieved_at       TEXT NOT NULL,
    synced_at          TEXT NOT NULL DEFAULT (datetime('now')),

    PRIMARY KEY (disorder_version, predictor, uniprot_acc_full)
);

CREATE INDEX IF NOT EXISTS idx_disorder_public_hgnc
    ON disorder_public (hgnc_id);
CREATE INDEX IF NOT EXISTS idx_disorder_public_uniprot
    ON disorder_public (uniprot_acc);
CREATE INDEX IF NOT EXISTS idx_disorder_public_predictor
    ON disorder_public (disorder_version, predictor);
