"""Targeted DeepTMHMM rerun for ortholog models whose identity-based selection changed.

Consumes the delta TSV from ``diff_ortholog_model_selection.py`` and runs
DeepTMHMM (1 worker by default, against the local install via
``DEEPTMHMM_ROOT``) on ONLY the new/changed ortholog UniProt models — e.g.
cyno EGFR's full-length ``A0A2K5WK39`` replacing the 704-aa fragment
``A0A2K5WKD8``. Topology is *not* projected at write time (projection onto the
human canonical happens at read in ``d1_deterministic``); each ortholog row
stores its own DeepTMHMM topology + sequence.

Human canonical topology for the ECD comparison is read from D1
(``topology_public``, ``cohort='human_canonical'``) — NOT re-run — so this
driver only spends DeepTMHMM compute on the changed ortholog models.

Emits, in the exact shape the existing upload scripts consume:

  * ``<out>/mouse_ortholog/topology_records.jsonl``
  * ``<out>/cyno_ortholog/topology_records.jsonl``
  * ``<out>/ortholog_ecd_records.jsonl``

Does **NOT** write to D1. Upload is a deliberate, separate step via
``scripts/upload_topology_to_d1.py`` + ``scripts/upload_ortholog_ecd_to_d1.py``
once the target version + scope is confirmed.

Usage::

    DEEPTMHMM_ROOT=/Users/.../Git/deliverome-internal/analyses/surface-proteome \\
    uv run python scripts/rerun_changed_ortholog_topology.py \\
        --delta data/processed/topology_run_topo_2026_05_16/ortholog_selection_delta.tsv \\
        --max-workers 1
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import logging
import os
import sys
from datetime import UTC, datetime
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

# Delta `species` token → topology cohort key. compara_ortholog `species` uses
# 'cynomolgus' (older rows may use 'cyno').
_ECD_SPECIES_TOKENS = {"mouse_ortholog": ("mouse",), "cyno_ortholog": ("cynomolgus", "cyno")}


def _read_delta(path: Path, statuses: set[str]) -> list[dict[str, str]]:
    """Read the selection-delta TSV; keep rows in ``statuses`` with a new_acc."""
    rows: list[dict[str, str]] = []
    with path.open(encoding="utf-8") as f:
        header = f.readline().rstrip("\n").split("\t")
        for line in f:
            cells = line.rstrip("\n").split("\t")
            if len(cells) != len(header):
                continue
            rec = dict(zip(header, cells, strict=True))
            if rec.get("status") in statuses and (rec.get("new_acc") or "").strip():
                rows.append(rec)
    return rows


def _human_canonical_topo_from_d1(
    *, topology_version: str, hgnc_ids: set[str]
) -> list[dict[str, object]]:
    """Read human_canonical topology rows for the affected genes from D1.

    Returns JSONL-shaped records carrying exactly the keys
    ``compute_ortholog_ecd_records`` indexes on: ``uniprot_accession``,
    ``hgnc_id``, ``per_residue_topology``, ``sequence``.
    """
    out: list[dict[str, object]] = []
    ids = sorted(hgnc_ids)
    for start in range(0, len(ids), 50):
        chunk = ids[start : start + 50]
        placeholders = ", ".join(["?"] * len(chunk))
        sql = (
            "SELECT hgnc_id, uniprot_acc, sequence, per_residue_topology "
            "FROM topology_public "
            "WHERE topology_version = ? AND cohort = 'human_canonical' "
            f"AND hgnc_id IN ({placeholders})"
        )
        for r in _query_public(sql, [topology_version, *chunk]):
            hgnc = (r.get("hgnc_id") or "").strip()
            acc = (r.get("uniprot_acc") or "").strip()
            seq = (r.get("sequence") or "").strip()
            topo = (r.get("per_residue_topology") or "").strip()
            if not hgnc or not acc or not seq or not topo:
                continue
            out.append({
                "uniprot_accession": acc,
                "hgnc_id": hgnc,
                "sequence": seq,
                "per_residue_topology": topo,
            })
    return out


def _ortholog_symbols_from_d1(species_tokens: tuple[str, ...], ensgs: set[str]) -> dict[str, str]:
    """{ortholog_ensembl_gene: ortholog_gene_symbol} from compara_ortholog."""
    out: dict[str, str] = {}
    ids = sorted(ensgs)
    sp_ph = ", ".join(["?"] * len(species_tokens))
    for start in range(0, len(ids), 50):
        chunk = ids[start : start + 50]
        placeholders = ", ".join(["?"] * len(chunk))
        sql = (
            "SELECT ortholog_ensembl_gene, ortholog_gene_symbol "
            "FROM compara_ortholog "
            f"WHERE species IN ({sp_ph}) AND ortholog_ensembl_gene IN ({placeholders})"
        )
        for r in _query_public(sql, [*species_tokens, *chunk]):
            ensg = (r.get("ortholog_ensembl_gene") or "").strip()
            sym = (r.get("ortholog_gene_symbol") or "").strip()
            if ensg and sym and ensg not in out:
                out[ensg] = sym
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--delta",
        type=Path,
        default=REPO_ROOT
        / "data" / "processed" / "topology_run_topo_2026_05_16"
        / "ortholog_selection_delta.tsv",
    )
    ap.add_argument(
        "--candidate-set",
        type=Path,
        default=REPO_ROOT
        / "data" / "processed" / "topology_run_topo_2026_05_16"
        / "candidate_accessions.tsv",
    )
    ap.add_argument(
        "--human-topology-version",
        default="topo_2026_05_16",
        help="topology_version to read human_canonical topology from (for ECD).",
    )
    ap.add_argument(
        "--statuses",
        default="changed,new",
        help="comma-separated delta statuses to rerun (default: changed,new).",
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=REPO_ROOT / "data" / "processed"
        / f"ortholog_rerun_{datetime.now(UTC):%Y_%m_%d}",
    )
    ap.add_argument("--deeptmhmm-root", type=Path, default=None)
    ap.add_argument("--max-workers", type=int, default=1)
    ap.add_argument("--batch-size", type=int, default=rts.DEFAULT_BATCH_SIZE)
    ap.add_argument("--fetch-workers", type=int, default=8)
    # Version stamps written into the JSONL. The upload scripts re-stamp these,
    # so they're cosmetic here — but keep them meaningful for provenance.
    ap.add_argument("--topology-version", default="topo_ortholog_rerun")
    ap.add_argument("--ortholog-ecd-version", default="orthologecd_ortholog_rerun")
    ap.add_argument(
        "--compara-release",
        required=True,
        help="Compara release label — required; see run_topology_sweep.py "
        "module-level comment for rationale.",
    )
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    load_env()
    if args.deeptmhmm_root:
        os.environ["DEEPTMHMM_ROOT"] = str(args.deeptmhmm_root)
    if not os.environ.get("DEEPTMHMM_ROOT"):
        logger.warning("DEEPTMHMM_ROOT not set — DeepTMHMM batches will fail to resolve the install")

    statuses = {s.strip() for s in args.statuses.split(",") if s.strip()}
    delta_rows = _read_delta(args.delta, statuses)
    logger.info("delta: %d rows in statuses=%s with a new_acc", len(delta_rows), sorted(statuses))
    if not delta_rows:
        logger.info("nothing to rerun — exiting")
        return 0

    # Candidate objects (for human-side denormalization in the ECD rows).
    candidates = rts.load_candidate_set(args.candidate_set)
    cand_by_hgnc = {c.hgnc_id: c for c in candidates}
    affected_hgnc = {r["human_hgnc_id"] for r in delta_rows}
    affected_candidates = [cand_by_hgnc[h] for h in sorted(affected_hgnc) if h in cand_by_hgnc]

    args.out.mkdir(parents=True, exist_ok=True)

    # --- Per-species: fetch + DeepTMHMM + parse to ortholog topology JSONL. ---
    cohort_jsonl_paths: dict[str, Path] = {}
    ortholog_human_hgnc_maps: dict[str, dict[str, str]] = {}
    ortholog_metadata_maps: dict[str, dict[str, dict[str, str]]] = {}

    for cohort in ("mouse_ortholog", "cyno_ortholog"):
        species_rows = [r for r in delta_rows if r["species"] == cohort]
        if not species_rows:
            continue
        # new_acc → human_hgnc_id (first-match-wins; a single ortholog acc maps
        # back to one human gene).
        human_hgnc_by_acc: dict[str, str] = {}
        ensg_by_acc: dict[str, str] = {}
        for r in species_rows:
            acc = r["new_acc"].strip().upper()
            if acc and acc not in human_hgnc_by_acc:
                human_hgnc_by_acc[acc] = r["human_hgnc_id"]
                ensg_by_acc[acc] = (r.get("ortholog_ensembl_gene") or "").strip()
        sym_by_ensg = _ortholog_symbols_from_d1(
            _ECD_SPECIES_TOKENS[cohort], set(ensg_by_acc.values()) - {""}
        )
        metadata_by_acc = {
            acc: {
                "ortholog_ensembl_gene": ensg,
                "ortholog_gene_symbol": sym_by_ensg.get(ensg, ""),
            }
            for acc, ensg in ensg_by_acc.items()
        }
        logger.info("[%s] %d new/changed ortholog accs", cohort, len(human_hgnc_by_acc))

        fasta_paths = rts.fetch_sequences_for_accessions(
            sorted(human_hgnc_by_acc),
            cache_dir=rts.SEQUENCE_CACHE_DIR,
            max_workers=args.fetch_workers,
        )
        cohort_dir = args.out / cohort
        output_3line_paths, skipped = rts.run_cohort_deeptmhmm(
            cohort=cohort,
            cohort_dir=cohort_dir,
            fasta_paths=list(fasta_paths.values()),
            max_workers=args.max_workers,
            batch_size=args.batch_size,
        )
        logger.info("[%s] DeepTMHMM: %d .3line outputs, %d skipped (too long)",
                    cohort, len(output_3line_paths), len(skipped))
        if not output_3line_paths:
            logger.warning("[%s] no .3line outputs — skipping cohort", cohort)
            continue

        jsonl = rts.parse_cohort_to_jsonl(
            cohort=cohort,
            output_3line_paths=output_3line_paths,
            cohort_dir=cohort_dir,
            topology_version=args.topology_version,
            candidate_by_acc={},  # ortholog cohort uses the maps below, not this
            ortholog_human_hgnc_by_acc=human_hgnc_by_acc,
            ortholog_metadata_by_acc=metadata_by_acc,
        )
        cohort_jsonl_paths[cohort] = jsonl
        ortholog_human_hgnc_maps[cohort] = human_hgnc_by_acc
        ortholog_metadata_maps[cohort] = metadata_by_acc

    if not cohort_jsonl_paths:
        logger.warning("no ortholog cohorts produced topology — exiting")
        return 0

    # --- Human canonical topology from D1 (read-only) for the ECD compare. ---
    human_topo_records = _human_canonical_topo_from_d1(
        topology_version=args.human_topology_version, hgnc_ids=affected_hgnc
    )
    human_jsonl = args.out / "human_canonical" / "topology_records.jsonl"
    human_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with human_jsonl.open("w", encoding="utf-8") as f:
        for rec in human_topo_records:
            f.write(json.dumps(rec, sort_keys=True) + "\n")
    cohort_jsonl_paths["human_canonical"] = human_jsonl
    logger.info("human_canonical topology from D1: %d/%d affected genes",
                len(human_topo_records), len(affected_hgnc))

    # --- ECD identity (cross-species, per-loop BLOSUM62). ---
    ortholog_ecd_rows = rts.compute_ortholog_ecd_records(
        candidates=affected_candidates,
        cohort_jsonl_paths=cohort_jsonl_paths,
        ortholog_human_hgnc_maps=ortholog_human_hgnc_maps,
        ortholog_metadata_maps=ortholog_metadata_maps,
        ortholog_ecd_version=args.ortholog_ecd_version,
        compara_release=args.compara_release,
    )
    ortholog_ecd_jsonl = args.out / "ortholog_ecd_records.jsonl"
    rts.write_ortholog_ecd_jsonl(ortholog_ecd_jsonl, ortholog_ecd_rows)
    n_with_ecd = sum(1 for r in ortholog_ecd_rows if r.get("ecd_pct_identity") is not None)

    logger.info("=== rerun summary ===")
    for cohort in ("mouse_ortholog", "cyno_ortholog"):
        if cohort in cohort_jsonl_paths:
            logger.info("  %-16s topology JSONL → %s", cohort, cohort_jsonl_paths[cohort])
    logger.info("  ortholog ECD rows: %d (%d with ECD) → %s",
                len(ortholog_ecd_rows), n_with_ecd, ortholog_ecd_jsonl)
    logger.info("NOTE: no D1 writes. Upload with upload_topology_to_d1.py + "
                "upload_ortholog_ecd_to_d1.py once the target version is confirmed.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
