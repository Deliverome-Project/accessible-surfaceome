"""Build the expanded multipass extracellular-loop tag-site cohort TSV.

Combines:
  1. All 607 Library-1 internal-site members (``data/tag_sites/l1_internal_members.tsv``),
     preserving their exact designed-ORF / isoform / ortholog frames and ``l1-p*`` IDs.
  2. Every additional ``likely_accessible`` non-olfactory human canonical multipass
     protein (``TM >= 2`` with >=1 inter-TM extracellular loop) from public D1
     ``topology_public`` x ``surface_annotation`` — covering both:
       * both-termini-cytoplasmic multipass proteins outside L1 internal (e.g.
         large channels/transporters like ``ABCA1``, ``CACNA1*``, ``PIEZO1/2``, ``SCN*``)
       * GPCRs and N-/C-out multipass proteins (e.g. ``ADORA*``, ``ADRB2``, ``ACKR*``,
         ``ADGR*``, ``ABCC*``) for comprehensive extracellular-loop tag-site mining.

Emits a single ``Member``-compatible TSV (default
``data/tag_sites/expanded_multipass_members.tsv``) so ``scripts/enrich_tag_site_lit.py``
and ``modal/tag_site_lit_app.py`` run identically on either the 607-member L1 internal
cohort or the full expanded multipass cohort.

Usage::

    uv run python scripts/build/build_expanded_multipass_members.py
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import logging
import sys
from pathlib import Path

from accessible_surfaceome.agents.tag_site.member_frames import (
    INTER_TM,
    extracellular_runs,
    load_members,
)
from accessible_surfaceome.cloud.d1_client import D1Client
from accessible_surfaceome.env import load_env
from accessible_surfaceome.paths import REPO_ROOT

logger = logging.getLogger(__name__)

DEFAULT_L1_TSV = REPO_ROOT / "data/tag_sites/l1_internal_members.tsv"
DEFAULT_OUT_TSV = REPO_ROOT / "data/tag_sites/expanded_multipass_members.tsv"
TOPOLOGY_VERSION = "topo_2026_05_16"

COLUMNS: tuple[str, ...] = (
    "candidate_id",
    "library",
    "candidate_set",
    "species",
    "gene_symbol",
    "topology_acc",
    "topology_cohort",
    "sequence_sha256",
    "ordered_length_aa",
    "tm_count",
    "longest_inter_tm_ecto_run_aa",
    "longest_ecto_run_aa",
    "longest_ecto_run_start",
    "longest_ecto_run_position",
    "placement",
    "gpi_rerouted",
    "shed_risk",
)


DEFAULT_EVIDENCE_GRADES = ("direct_multi_method", "direct_single_method")


def is_olfactory_receptor(gene_symbol: str) -> bool:
    """True for canonical human olfactory receptor symbols (OR1A1, OR51E2, ...)."""
    return len(gene_symbol) >= 4 and gene_symbol.startswith("OR") and gene_symbol[2].isdigit()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--l1-tsv", type=Path, default=DEFAULT_L1_TSV)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT_TSV)
    ap.add_argument(
        "--evidence-grades",
        default=",".join(DEFAULT_EVIDENCE_GRADES),
        help="Comma-separated surface_evidence.evidence_grade values to include",
    )
    ap.add_argument("--include-or", action="store_true", help="Include olfactory receptors")
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    load_env()
    grades = [g.strip() for g in args.evidence_grades.split(",") if g.strip()]

    # Preserve exact L1 internal member rows first.
    with args.l1_tsv.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        l1_rows = list(reader)
    l1_members = load_members(args.l1_tsv)
    l1_genes = {m.gene_symbol for m in l1_members}
    logger.info("Loaded %d L1 internal members (%d unique genes)", len(l1_rows), len(l1_genes))

    grade_marks = ", ".join(["?"] * len(grades))
    with D1Client.public() as pub:
        cand_rows = pub.query(
            f"""
            SELECT
                t.gene_symbol,
                t.uniprot_acc,
                t.uniprot_acc_full,
                t.tm_helix_count,
                t.n_terminal_orientation,
                t.c_terminal_orientation,
                t.signal_peptide_length,
                t.sequence,
                t.per_residue_topology,
                json_extract(sa.annotation_json, '$.surface_evidence.evidence_grade') AS evidence_grade
            FROM topology_public t
            JOIN surface_annotation sa ON sa.gene_symbol = t.gene_symbol
            WHERE t.cohort = 'human_canonical'
              AND t.topology_version = ?
              AND t.tm_helix_count >= 2
              AND sa.triage_signal = 'likely_accessible'
              AND json_extract(sa.annotation_json, '$.surface_evidence.evidence_grade') IN ({grade_marks})
            ORDER BY t.gene_symbol, t.uniprot_acc;
            """,
            [TOPOLOGY_VERSION, *grades],
        )

    seen_genes: set[str] = set(l1_genes)
    extra_rows: list[dict[str, str]] = []
    n_both_cyto = 0
    n_with_ec_tail = 0

    for r in cand_rows:
        gene = (r.get("gene_symbol") or "").strip()
        acc = (r.get("uniprot_acc") or "").strip()
        seq = (r.get("sequence") or "").strip()
        topo = (r.get("per_residue_topology") or "").strip()
        if not gene or not acc or not seq or len(seq) != len(topo):
            continue
        if gene in seen_genes:
            continue
        if not args.include_or and is_olfactory_receptor(gene):
            continue

        runs = extracellular_runs(topo)
        loops = [run for run in runs if run.position == INTER_TM]
        if not loops:
            continue

        seen_genes.add(gene)
        longest_loop = max(loops, key=lambda run: run.length)
        longest_any = max(runs, key=lambda run: run.length)
        both_cyto = (
            r.get("n_terminal_orientation") == "cytoplasmic"
            and r.get("c_terminal_orientation") == "cytoplasmic"
            and int(r.get("signal_peptide_length") or 0) == 0
        )
        if both_cyto:
            n_both_cyto += 1
            cset = "likely_accessible_both_cyto_multipass"
        else:
            n_with_ec_tail += 1
            cset = "likely_accessible_ec_tail_multipass"

        sha = hashlib.sha256(seq.encode("utf-8")).hexdigest()
        extra_rows.append(
            {
                "candidate_id": f"mp-{acc}",
                "library": "surfaceome_multipass",
                "candidate_set": cset,
                "species": "human",
                "gene_symbol": gene,
                "topology_acc": acc,
                "topology_cohort": "human_canonical",
                "sequence_sha256": sha,
                "ordered_length_aa": str(len(seq)),
                "tm_count": str(int(r.get("tm_helix_count") or 0)),
                "longest_inter_tm_ecto_run_aa": str(longest_loop.length),
                "longest_ecto_run_aa": str(longest_any.length),
                "longest_ecto_run_start": str(longest_any.start),
                "longest_ecto_run_position": longest_any.position,
                "placement": "internal",
                "gpi_rerouted": "False",
                "shed_risk": "none",
            }
        )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for row in l1_rows:
            writer.writerow({c: row[c] for c in COLUMNS})
        for row in extra_rows:
            writer.writerow(row)

    total = len(l1_rows) + len(extra_rows)
    logger.info(
        "Wrote %d total targets to %s: %d L1 internal + %d expanded likely_accessible "
        "multipass (%d both-termini-cytoplasmic + %d GPCR/EC-tail multipass)",
        total,
        args.out,
        len(l1_rows),
        len(extra_rows),
        n_both_cyto,
        n_with_ec_tail,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
