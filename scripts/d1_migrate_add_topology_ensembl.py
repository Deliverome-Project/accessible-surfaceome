"""Add `topology_ensembl_public`: DeepTMHMM calls for forms that have no UniProt proteoform.

`topology_public` is keyed on `(topology_version, cohort, uniprot_acc_full)`, and both
UniProt columns are NOT NULL. That is correct for everything sourced from UniProt and makes
it structurally unable to hold a form that exists only in Ensembl — which is most of the
alternate-form universe: 10,880 of 13,687 library alternate forms are Ensembl-only.

Rather than put an ENSP into a column named for a UniProt accession, those rows get their
own table keyed on the Ensembl protein ID. The topology columns are deliberately identical
to `topology_public` so a reader can `UNION ALL` the two and apply one rule to both; the
failure this whole exercise was about is a library ending up with two inconsistent filters,
and that risk is managed by keeping the columns the same, not by forcing one table.

Additive and idempotent: CREATE TABLE / CREATE INDEX IF NOT EXISTS only, no existing table
touched. Dry run unless --apply is passed.

    uv run --locked python scripts/d1_migrate_add_topology_ensembl.py
    uv run --locked python scripts/d1_migrate_add_topology_ensembl.py --apply
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

DATABASE = "surfaceome_public"

STATEMENTS = """
-- topology_ensembl_public — DeepTMHMM topology for Ensembl-only proteoforms.
--
-- One row per (topology_version, cohort, ensembl_protein_id). These are forms with no
-- UniProt proteoform at all, so they cannot live in topology_public, whose primary key
-- requires a UniProt accession. Columns after the key mirror topology_public exactly so the
-- two can be read as one set.
CREATE TABLE IF NOT EXISTS topology_ensembl_public (
    topology_version           TEXT NOT NULL,
    cohort                     TEXT NOT NULL,        -- human_ensembl_forms | mouse_ensembl_forms | cyno_ensembl_forms
    ensembl_protein_id         TEXT NOT NULL,        -- ENSP, unversioned — the key
    ensembl_transcript_id      TEXT,                 -- ENST this translation came from
    ensembl_gene_id            TEXT,                 -- ENSG, for joining to compara/ortholog tables
    hgnc_id                    TEXT,                 -- NULL for non-human rows
    gene_symbol                TEXT,                 -- denormalized for offline reads; NEVER a join key
    species                    TEXT NOT NULL,        -- human | mouse | cynomolgus
    reference_uniprot_acc_full TEXT,                 -- the gene's selected reference, so a form can be compared to it
    sequence                   TEXT NOT NULL,
    protein_length             INTEGER NOT NULL,
    deeptmhmm_label            TEXT NOT NULL,        -- TM | SP | SP+TM | BETA | GLOB
    tm_helix_count             INTEGER NOT NULL,
    beta_strand_count          INTEGER NOT NULL,
    n_terminal_orientation     TEXT NOT NULL,
    c_terminal_orientation     TEXT NOT NULL,
    signal_peptide_length      INTEGER NOT NULL,
    ecd_length_residues        INTEGER NOT NULL,
    icd_length_residues        INTEGER NOT NULL,
    per_residue_topology       TEXT NOT NULL,        -- O/M/I/S/B chars; len == protein_length
    predicted_surface_membrane INTEGER NOT NULL,     -- 1 iff label in {TM, SP+TM}
    predicted_secreted         INTEGER NOT NULL,     -- 1 iff label == SP
    tool_version               TEXT NOT NULL,        -- e.g. 'deeptmhmm-1.0.24'
    retrieved_at               TEXT NOT NULL,
    synced_at                  TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (topology_version, cohort, ensembl_protein_id)
);

CREATE INDEX IF NOT EXISTS idx_topology_ensembl_public_gene
    ON topology_ensembl_public (ensembl_gene_id);
CREATE INDEX IF NOT EXISTS idx_topology_ensembl_public_symbol
    ON topology_ensembl_public (gene_symbol);
CREATE INDEX IF NOT EXISTS idx_topology_ensembl_public_hgnc
    ON topology_ensembl_public (hgnc_id);
CREATE INDEX IF NOT EXISTS idx_topology_ensembl_public_reference
    ON topology_ensembl_public (reference_uniprot_acc_full);
"""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--apply",
        action="store_true",
        help="Execute against the remote database. Without it, print the SQL and stop.",
    )
    ap.add_argument("--database", default=DATABASE)
    args = ap.parse_args()

    if not args.apply:
        print("DRY RUN — pass --apply to execute. SQL that would run:\n")
        print(STATEMENTS)
        print(
            "Take a backup first: trigger the d1-backup workflow, or run\n"
            "  bash scripts/cloud/d1_export_to_r2.sh --db surfaceome_public"
        )
        return 0

    with tempfile.NamedTemporaryFile("w", suffix=".sql", delete=False) as fh:
        fh.write(STATEMENTS)
        path = fh.name
    try:
        proc = subprocess.run(
            [
                "npx", "--yes", "wrangler", "d1", "execute", args.database,
                "--remote", f"--file={path}",
            ],
            capture_output=True,
            text=True,
        )
        sys.stdout.write(proc.stdout)
        sys.stderr.write(proc.stderr)
        return proc.returncode
    finally:
        Path(path).unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
