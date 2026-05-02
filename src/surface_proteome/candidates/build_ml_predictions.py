"""Normalize DeepTMHMM `.3line` predictions for the M1 candidate-universe merge.

Inputs: per-cohort `predicted_topologies.3line` files under
``data/external/deeptmhmm_surfaceome_predictions/<cohort>/`` produced by the
DeepTMHMM 1.0.24 pipeline. The 3-line format is::

    >sp|ACCESSION|ENTRY_NAME | LABEL
    <amino acid sequence>
    <per-residue topology string over alphabet {S, O, M, I, B}>

DeepTMHMM emits one of five class labels per protein:
``TM`` (alpha-helical transmembrane), ``SP`` (signal peptide only, predicted
secreted), ``SP+TM`` (signal peptide + TM helices), ``BETA`` (beta-barrel
transmembrane), ``GLOB`` (globular / soluble, no TM or SP).

Outputs: per-cohort TSVs under ``data/processed/deeptmhmm/`` with one row per
UniProt accession as it appears in the 3-line header (isoform suffix
preserved in ``uniprot_accession_full``; the base accession is written to
``uniprot_accession`` for join convenience). Columns:

- identifiers: ``uniprot_accession``, ``uniprot_accession_full``,
  ``uniprot_entry_name``
- classification: ``deeptmhmm_label`` (one of TM/SP/SP+TM/BETA/GLOB)
- topology summaries: ``protein_length``, ``tm_helix_count``,
  ``beta_strand_count``, ``has_signal_peptide``, ``signal_peptide_length``
- terminal orientation (ignoring SP residues):
  ``n_term_side``, ``c_term_side`` (each ``I``/``O``/``M``/``B`` or empty),
  ``n_term_extracellular``, ``c_term_extracellular``,
  ``n_term_intracellular``, ``c_term_intracellular``
- derived flags: ``predicted_surface_membrane`` (1 iff label in
  {TM, SP+TM}), ``predicted_secreted`` (1 iff label == SP).
  BETA is deliberately excluded: human beta-barrel membrane proteins
  are essentially mitochondrial outer membrane (VDAC1/2/3, TOMM40,
  SAMM50, MTX1/2), not plasma-membrane / cell-surface proteins.

Also writes:
- ``deeptmhmm_build_summary.json`` — per-cohort row counts, label
  distributions, union accession coverage
- ``deeptmhmm_build_traceability.json`` — source file SHA256s and
  capture time

The terminal-orientation logic matches
``annotate_afdb_with_deeptmhmm_orientation.py``: the first/last topology
character *after skipping leading/trailing ``S`` residues* defines the
mature-chain termini side.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from surface_proteome.candidates.traceability import (
    sha256_file,
    utc_now_iso,
)

from surface_proteome.paths import REPO_ROOT as ROOT

DATASET = "deeptmhmm"
DEFAULT_INPUT_DIR = ROOT / "data" / "external" / "deeptmhmm_surfaceome_predictions"
DEFAULT_OUTPUT_DIR = ROOT / "data" / "processed" / "deeptmhmm"
SUMMARY_JSON = "deeptmhmm_build_summary.json"
MANIFEST_JSON = "deeptmhmm_build_traceability.json"

COHORTS: list[tuple[str, str, str]] = [
    # (cohort_key, source_subdir, output_tsv_basename)
    ("human_canonical", "human_canonical_non_hla", "deeptmhmm_human_canonical.tsv"),
    ("human_isoforms", "human_isoforms_from_afdb_non_hla", "deeptmhmm_human_isoforms.tsv"),
    ("mouse_ortholog", "mouse_ortholog_one2one_highconf_non_hla", "deeptmhmm_mouse_ortholog.tsv"),
    ("cyno_ortholog", "cyno_ortholog_one2one_highconf_non_hla", "deeptmhmm_cyno_ortholog.tsv"),
]

VALID_LABELS = {"TM", "SP", "SP+TM", "BETA", "GLOB"}
SURFACE_MEMBRANE_LABELS = {"TM", "SP+TM"}

OUTPUT_COLUMNS = [
    "uniprot_accession",
    "uniprot_accession_full",
    "uniprot_entry_name",
    "deeptmhmm_label",
    "protein_length",
    "tm_helix_count",
    "beta_strand_count",
    "has_signal_peptide",
    "signal_peptide_length",
    "n_term_side",
    "c_term_side",
    "n_term_extracellular",
    "c_term_extracellular",
    "n_term_intracellular",
    "c_term_intracellular",
    "predicted_surface_membrane",
    "predicted_secreted",
]


def _split_base_accession(acc: str) -> str:
    """Strip UniProt isoform suffix (e.g. ``Q9Y6K8-2`` -> ``Q9Y6K8``)."""
    return acc.split("-", 1)[0] if "-" in acc else acc


def _terminal_state(topology: str, *, from_n_term: bool) -> str:
    """First/last topology char after skipping SP residues."""
    if not topology:
        return ""
    chars = topology if from_n_term else reversed(topology)
    for ch in chars:
        if ch != "S":
            return ch
    return ""


def _count_runs(topology: str, state: str) -> int:
    """Count contiguous runs of `state` in the topology string."""
    if not topology or state not in topology:
        return 0
    return len(re.findall(f"{re.escape(state)}+", topology))


def parse_3line(path: Path) -> list[dict]:
    """Parse one predicted_topologies.3line file into records."""
    lines = [ln.rstrip() for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if len(lines) % 3 != 0:
        raise ValueError(f"3line file malformed (not 3-line groups): {path}")

    records: list[dict] = []
    for i in range(0, len(lines), 3):
        header = lines[i]
        sequence = lines[i + 1]
        topology = lines[i + 2].upper()

        if not header.startswith(">"):
            raise ValueError(f"Bad header at offset {i} in {path}: {header!r}")
        payload = header[1:].strip()
        # "sp|ACC|ENTRY_NAME | LABEL"
        if " | " not in payload:
            raise ValueError(f"Header missing ' | LABEL' in {path}: {header!r}")
        seq_id, label = payload.rsplit(" | ", 1)
        label = label.strip()
        if label not in VALID_LABELS:
            raise ValueError(f"Unknown DeepTMHMM label {label!r} in {path}")

        parts = seq_id.split("|")
        if len(parts) < 3:
            raise ValueError(f"Unexpected seq_id format in {path}: {seq_id!r}")
        acc_full = parts[1].strip()
        entry_name = parts[2].strip()
        if not acc_full:
            raise ValueError(f"Empty accession in {path}: {header!r}")

        if len(sequence) != len(topology):
            raise ValueError(
                f"Length mismatch for {acc_full} in {path}: "
                f"seq={len(sequence)} topo={len(topology)}"
            )

        n_side = _terminal_state(topology, from_n_term=True)
        c_side = _terminal_state(topology, from_n_term=False)

        sp_len = 0
        for ch in topology:
            if ch == "S":
                sp_len += 1
            else:
                break

        records.append(
            {
                "uniprot_accession": _split_base_accession(acc_full),
                "uniprot_accession_full": acc_full,
                "uniprot_entry_name": entry_name,
                "deeptmhmm_label": label,
                "protein_length": len(sequence),
                "tm_helix_count": _count_runs(topology, "M"),
                "beta_strand_count": _count_runs(topology, "B"),
                "has_signal_peptide": int("S" in topology),
                "signal_peptide_length": sp_len,
                "n_term_side": n_side,
                "c_term_side": c_side,
                "n_term_extracellular": int(n_side == "O"),
                "c_term_extracellular": int(c_side == "O"),
                "n_term_intracellular": int(n_side == "I"),
                "c_term_intracellular": int(c_side == "I"),
                "predicted_surface_membrane": int(label in SURFACE_MEMBRANE_LABELS),
                "predicted_secreted": int(label == "SP"),
            }
        )
    return records


def write_tsv(records: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    records_sorted = sorted(records, key=lambda r: r["uniprot_accession_full"])
    with path.open("w", encoding="utf-8", newline="") as f:
        f.write("\t".join(OUTPUT_COLUMNS) + "\n")
        for r in records_sorted:
            f.write("\t".join(str(r[c]) for c in OUTPUT_COLUMNS) + "\n")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    p.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    in_dir: Path = args.input_dir
    out_dir: Path = args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    cohort_summaries: dict[str, dict] = {}
    cohort_outputs: dict[str, dict] = {}
    source_files: dict[str, dict] = {}

    union_full = set()
    union_base = set()

    for key, subdir, out_name in COHORTS:
        src_path = in_dir / subdir / "predicted_topologies.3line"
        if not src_path.exists():
            raise FileNotFoundError(f"Missing DeepTMHMM input: {src_path}")

        print(f"parsing cohort={key}  {src_path}")
        records = parse_3line(src_path)

        dup_full = len(records) - len({r["uniprot_accession_full"] for r in records})
        if dup_full:
            print(f"  WARNING: {dup_full} duplicate uniprot_accession_full rows in {key}")

        out_path = out_dir / out_name
        write_tsv(records, out_path)

        labels = sorted({r["deeptmhmm_label"] for r in records})
        label_counts = {
            lab: sum(1 for r in records if r["deeptmhmm_label"] == lab) for lab in labels
        }
        n_surface = sum(1 for r in records if r["predicted_surface_membrane"])
        n_secreted = sum(1 for r in records if r["predicted_secreted"])

        cohort_summaries[key] = {
            "n_proteins": len(records),
            "n_unique_accession_full": len({r["uniprot_accession_full"] for r in records}),
            "n_unique_accession_base": len({r["uniprot_accession"] for r in records}),
            "label_counts": label_counts,
            "n_predicted_surface_membrane": n_surface,
            "n_predicted_secreted": n_secreted,
        }
        cohort_outputs[out_name] = {
            "local_path": str(out_path.relative_to(ROOT)),
            "sha256": sha256_file(out_path),
            "size_bytes": out_path.stat().st_size,
            "n_rows": len(records),
            "primary_key": "uniprot_accession_full",
        }
        source_files[key] = {
            "local_path": str(src_path.relative_to(ROOT)),
            "sha256": sha256_file(src_path),
            "size_bytes": src_path.stat().st_size,
            "n_sequences": len(records),
        }

        if key in {"human_canonical", "human_isoforms"}:
            union_full.update(r["uniprot_accession_full"] for r in records)
            union_base.update(r["uniprot_accession"] for r in records)

        print(
            f"  wrote {out_path.relative_to(ROOT)}  "
            f"n={len(records):,}  surface={n_surface:,}  "
            f"secreted={n_secreted:,}  labels={label_counts}"
        )

    summary = {
        "generated_at_utc": utc_now_iso(),
        "cohorts": cohort_summaries,
        "human_union": {
            "n_unique_accession_full": len(union_full),
            "n_unique_accession_base": len(union_base),
            "description": (
                "union of uniprot accessions across human_canonical + human_isoforms cohorts"
            ),
        },
    }
    (out_dir / SUMMARY_JSON).write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    manifest = {
        "dataset": DATASET,
        "generated_at_utc": utc_now_iso(),
        "script": Path(__file__).relative_to(ROOT).as_posix(),
        "source_files": source_files,
        "outputs": cohort_outputs,
        "label_vocabulary": sorted(VALID_LABELS),
        "derived_columns": [
            {"name": "n_term_side", "rule": "first topology char after skipping leading 'S'"},
            {"name": "c_term_side", "rule": "last topology char after skipping trailing 'S'"},
            {
                "name": "predicted_surface_membrane",
                "rule": "1 iff deeptmhmm_label in {TM, SP+TM} (BETA excluded — human beta-barrels are mitochondrial outer membrane, not plasma-membrane)",
            },
            {"name": "predicted_secreted", "rule": "1 iff deeptmhmm_label == 'SP'"},
            {
                "name": "signal_peptide_length",
                "rule": "count of leading 'S' residues in topology",
            },
        ],
    }
    (out_dir / MANIFEST_JSON).write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    print(
        f"human union (canonical + isoforms): "
        f"n_full={len(union_full):,}  n_base={len(union_base):,}"
    )


if __name__ == "__main__":
    main()
