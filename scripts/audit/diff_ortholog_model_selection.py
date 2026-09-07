"""Diff identity-based ortholog-model selection vs the accessions in D1.

Read-only blast-radius analysis for the ortholog-model-selection fix. Re-
resolves every mouse + cyno ortholog for the topology candidate cohort using
the NEW coverage-normalized-identity resolver
(``resolve_uniprot_by_ensembl_gene`` with ``human_canonical_sequence``), then
diffs the selected accession against what is currently stored in
``compara_ortholog_ecd`` (the live ``orthologecd_topo_2026_05_16`` version).

The genes whose selected accession *changes* are exactly the set that needs a
DeepTMHMM re-prediction + ECD recompute in the at-scale rerun — e.g. cyno
EGFR flips from the 704-aa fragment ``A0A2K5WKD8`` to the full-length
``A0A2K5WK39``. No D1 writes; this only reads.

Usage::

    uv run python scripts/diff_ortholog_model_selection.py \\
        --candidate-set data/processed/topology_run_topo_2026_05_16/candidate_accessions.tsv \\
        --ortholog-ecd-version orthologecd_topo_2026_05_16
"""

from __future__ import annotations

import argparse
import importlib.util
import logging
import sys
from collections import Counter
from pathlib import Path

from accessible_surfaceome.agents.surfaceome_v1.d1_deterministic import _query_public
from accessible_surfaceome.env import load_env
from accessible_surfaceome.paths import REPO_ROOT

logger = logging.getLogger(__name__)

# Import the sweep module by path (scripts/ isn't an importable package).
_SWEEP_PATH = Path(__file__).parent / "run_topology_sweep.py"
_spec = importlib.util.spec_from_file_location("_run_topology_sweep", _SWEEP_PATH)
assert _spec and _spec.loader
rts = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = rts  # dataclass() needs the module discoverable
_spec.loader.exec_module(rts)

# ECD `species` token per cohort key (the table uses 'cynomolgus'; older rows
# may use 'cyno').
_ECD_SPECIES = {"mouse_ortholog": ("mouse",), "cyno_ortholog": ("cynomolgus", "cyno")}


def _current_ecd_accs(version: str) -> dict[tuple[str, str], str]:
    """{(human_hgnc_id, species_key): ortholog_uniprot_acc} from D1."""
    rows = _query_public(
        "SELECT human_hgnc_id, species, ortholog_uniprot_acc "
        "FROM compara_ortholog_ecd WHERE ortholog_ecd_version = ?",
        [version],
    )
    out: dict[tuple[str, str], str] = {}
    for r in rows:
        hgnc = (r.get("human_hgnc_id") or "").strip()
        sp = (r.get("species") or "").strip().lower()
        acc = (r.get("ortholog_uniprot_acc") or "").strip().upper()
        if not hgnc or not acc:
            continue
        species_key = "mouse_ortholog" if sp == "mouse" else "cyno_ortholog"
        out[(hgnc, species_key)] = acc
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--candidate-set",
        type=Path,
        default=REPO_ROOT
        / "data" / "processed" / "topology_run_topo_2026_05_16"
        / "candidate_accessions.tsv",
    )
    ap.add_argument("--ortholog-ecd-version", default="orthologecd_topo_2026_05_16")
    ap.add_argument("--fetch-workers", type=int, default=8)
    ap.add_argument(
        "--out",
        type=Path,
        default=REPO_ROOT
        / "data" / "processed" / "topology_run_topo_2026_05_16"
        / "ortholog_selection_delta.tsv",
    )
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    load_env()

    candidates = rts.load_candidate_set(args.candidate_set)
    logger.info("loaded %d candidates", len(candidates))

    # Human canonical sequences for identity-based selection.
    human_acc_by_hgnc = {c.hgnc_id: c.uniprot_acc for c in candidates}
    human_fasta_paths = rts.fetch_sequences_for_accessions(
        sorted(set(human_acc_by_hgnc.values())),
        cache_dir=rts.SEQUENCE_CACHE_DIR,
        max_workers=args.fetch_workers,
    )
    human_seq_by_hgnc: dict[str, str] = {}
    for hgnc_id, h_acc in human_acc_by_hgnc.items():
        p = human_fasta_paths.get(h_acc)
        seq = rts._read_fasta_sequence(p) if p else ""
        if seq:
            human_seq_by_hgnc[hgnc_id] = seq
    logger.info("human canonical sequences: %d", len(human_seq_by_hgnc))

    current = _current_ecd_accs(args.ortholog_ecd_version)
    logger.info("current ECD accs in D1 (%s): %d", args.ortholog_ecd_version, len(current))

    cache_path = (
        REPO_ROOT / "data" / "external" / "ortholog_uniprot_resolution_byidentity.tsv"
    )

    rows_out: list[dict[str, str]] = []
    stats: Counter[str] = Counter()
    for species_key in ("mouse_ortholog", "cyno_ortholog"):
        targets = rts._resolve_ortholog_targets_from_d1(candidates, species_key=species_key)
        logger.info("[%s] %d ortholog targets", species_key, len(targets))
        ensg_to_acc = rts._resolve_ortholog_uniprots(
            targets, cache_path=cache_path, max_workers=4,
            human_seq_by_hgnc=human_seq_by_hgnc,
        )
        # First-match-wins per (human_hgnc, species), mirroring the sweep.
        new_by_hgnc: dict[str, tuple[str, str]] = {}
        for t in targets:
            acc = (ensg_to_acc.get(t.ortholog_ensembl_gene) or "").strip().upper()
            if acc and t.human_hgnc_id not in new_by_hgnc:
                new_by_hgnc[t.human_hgnc_id] = (acc, t.ortholog_ensembl_gene)

        seen_hgnc = set(new_by_hgnc) | {
            h for (h, sk) in current if sk == species_key
        }
        for hgnc in sorted(seen_hgnc):
            new_acc, ensg = new_by_hgnc.get(hgnc, ("", ""))
            old_acc = current.get((hgnc, species_key), "")
            if new_acc and old_acc:
                status = "same" if new_acc == old_acc else "changed"
            elif new_acc and not old_acc:
                status = "new"
            elif old_acc and not new_acc:
                status = "dropped"
            else:
                status = "none"
            stats[f"{species_key}:{status}"] += 1
            if status in ("changed", "new", "dropped"):
                rows_out.append({
                    "human_hgnc_id": hgnc,
                    "species": species_key,
                    "old_acc": old_acc,
                    "new_acc": new_acc,
                    "ortholog_ensembl_gene": ensg,
                    "status": status,
                })

    args.out.parent.mkdir(parents=True, exist_ok=True)
    header = ["human_hgnc_id", "species", "old_acc", "new_acc", "ortholog_ensembl_gene", "status"]
    with args.out.open("w", encoding="utf-8") as f:
        f.write("\t".join(header) + "\n")
        for r in sorted(rows_out, key=lambda d: (d["species"], d["status"], d["human_hgnc_id"])):
            f.write("\t".join(r[h] for h in header) + "\n")

    logger.info("=== delta summary ===")
    for k in sorted(stats):
        logger.info("  %-28s %d", k, stats[k])
    logger.info("wrote %d changed/new/dropped rows to %s", len(rows_out), args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
