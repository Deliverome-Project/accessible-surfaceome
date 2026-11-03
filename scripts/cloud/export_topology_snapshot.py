"""Export ``topology_public`` to a parquet snapshot keyed by sequence sha256.

WHY A SEQUENCE KEY. Consumers outside this repo need to ask "what is the topology of
*this* protein", where "this" is a sequence they are about to synthesise. Accessions
cannot answer that: an Ensembl-transcript ORF usually corresponds to a UniProt *isoform*
record rather than the canonical one, so looking the gene up by its canonical accession
returns the topology of a different protein -- silently, and with plausible-looking
numbers. Keying on the sha256 of the sequence makes the join exact or absent, never wrong.

``sequence`` is not indexed in D1 (the indexes are on hgnc_id, gene_symbol, uniprot_acc
and cohort+version), so a sequence join there is a full scan of ~71k long TEXT rows. That
is fine offline and wrong for a serve path, which is the other reason this is a published
snapshot rather than a live query.

The snapshot is uploaded to ``deliverome-external`` by the analysis repo, which owns the
S3 helper and its provenance stamping. This script only writes the local file.

    uv run --extra modal python scripts/cloud/export_topology_snapshot.py --out topology.parquet
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

COLUMNS = (
    "topology_version",
    "cohort",
    "hgnc_id",
    "uniprot_acc",
    "uniprot_acc_full",
    "isoform_id",
    "gene_symbol",
    "species",
    "is_canonical",
    "protein_length",
    "deeptmhmm_label",
    "tm_helix_count",
    "beta_strand_count",
    "n_terminal_orientation",
    "c_terminal_orientation",
    "signal_peptide_length",
    "ecd_length_residues",
    "icd_length_residues",
    "per_residue_topology",
    "predicted_surface_membrane",
    "predicted_secreted",
    "tool_version",
    "retrieved_at",
    "dtm2_structural_type",
    "dtm2_topology_string",
    "dtm2_v1_alphabet_lossy",
    "dtm2_main_membrane_type",
    "dtm2_plasma_membrane",
    "dtm2_plasma_membrane_prob",
    "dtm2_reentrant_count",
    "dtm2_interfacial_count",
    "dtm2_transit_peptide_length",
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--page", type=int, default=800)
    args = ap.parse_args()

    import pandas as pd

    from accessible_surfaceome.cloud.d1_client import D1Client
    from accessible_surfaceome.env import load_env

    load_env()
    cols = ", ".join(COLUMNS)
    rows: list[dict] = []
    with D1Client.public() as d1:
        total = d1.query("SELECT COUNT(*) AS n FROM topology_public")[0]["n"]
        print(f"topology_public rows: {total:,}")
        offset = 0
        while True:
            page = d1.query(
                f"SELECT {cols}, sequence FROM topology_public "
                f"ORDER BY topology_version, cohort, uniprot_acc_full "
                f"LIMIT {args.page} OFFSET {offset}"
            )
            if not page:
                break
            for r in page:
                seq = r.pop("sequence") or ""
                r["sequence_sha256"] = (
                    hashlib.sha256(seq.encode()).hexdigest() if seq else None
                )
                r["sequence_length"] = len(seq) or None
                rows.append(r)
            offset += len(page)
            print(f"  {offset:,}/{total:,}", flush=True)
            if len(page) < args.page:
                break

    df = pd.DataFrame(rows)
    if len(df) != total:
        raise SystemExit(f"exported {len(df):,} rows but the table holds {total:,}")
    missing = df["sequence_sha256"].isna().sum()
    if missing:
        print(
            f"WARNING: {missing:,} rows have no stored sequence and cannot be matched"
        )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    # parquet needs pyarrow, which this repo's env does not carry. Fall back to a
    # gzipped TSV, which the analysis repo converts to the published parquet -- better
    # than adding a dependency here just to change container format.
    if args.out.suffixes[:1] == [".parquet"] or args.out.suffix == ".parquet":
        df.to_parquet(args.out, compression="zstd", index=False)
    else:
        df.to_csv(args.out, sep="\t", index=False, compression="gzip")
    mb = args.out.stat().st_size / 1e6
    print(
        f"\nwrote {args.out} ({mb:.1f} MB)\n"
        f"  rows {len(df):,}   distinct sequences {df['sequence_sha256'].nunique():,}\n"
        f"  cohorts {sorted(df['cohort'].unique())}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
