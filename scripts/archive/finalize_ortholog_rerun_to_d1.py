"""Finalize the identity-fix ortholog rerun into D1 — non-destructively.

Takes the output of ``rerun_changed_ortholog_topology.py`` (corrected ortholog
topology + ECD rows for the changed/new genes) and lands it in D1 such that the
viewer / agent auto-pick the corrected data, **without any DELETE** and with the
originals fully preserved:

  1. **Ortholog topology** — the new/changed ortholog UniProt models are
     INSERT-OR-IGNORE'd into the *existing* ``topo_2026_05_16`` topology version
     (new ``uniprot_acc_full`` keys, so no conflict with the unchanged rows).
     ``_latest_topology_version_for_cohort('mouse_ortholog'|'cyno_ortholog')``
     keeps returning ``topo_2026_05_16``, so unchanged orthologs keep their
     topology and the new accs gain theirs.

  2. **ECD identity** — a *complete* new ``ortholog_ecd_version`` is written =
     (every row of the old version, MINUS the changed-gene rows) PLUS the
     corrected rows. Because ``_latest_ortholog_ecd_version()`` selects the
     newest ``computed_at`` release pointer, consumers switch to the new version
     automatically — and because it carries every unchanged gene forward, no
     ortholog disappears.

The old ECD version stays intact (rollback = drop the new release-pointer row,
or delete the new version's rows). The old version is also snapshotted to disk
before any write.

Idempotent: both uploads are INSERT OR IGNORE.

Usage::

    uv run python scripts/finalize_ortholog_rerun_to_d1.py \\
        --rerun-dir data/processed/ortholog_rerun_2026_05_30 \\
        --old-ecd-version orthologecd_topo_2026_05_16 \\
        --new-ecd-version orthologecd_topo_2026_05_16_idfix \\
        --topology-version topo_2026_05_16 \\
        --delta data/processed/topology_run_topo_2026_05_16/ortholog_selection_delta.tsv \\
        --execute
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import Any

from accessible_surfaceome.agents.surfaceome_v1.d1_deterministic import _query_public
from accessible_surfaceome.env import load_env
from accessible_surfaceome.paths import REPO_ROOT

logger = logging.getLogger(__name__)

ECD_COLS = [
    "ortholog_ecd_version",
    "human_hgnc_id",
    "human_uniprot_acc",
    "human_ensembl_gene",
    "human_gene_symbol",
    "species",
    "ortholog_uniprot_acc",
    "ortholog_ensembl_gene",
    "ortholog_gene_symbol",
    "biomart_percent_identity",
    "ecd_pct_identity",
    "n_ecd_loops_compared",
    "compara_release",
]


def _norm_species(token: str) -> str:
    """Canonicalize the species token so 'cyno' and 'cynomolgus' compare equal."""
    t = (token or "").strip().lower()
    return "cynomolgus" if t in ("cyno", "cynomolgus") else t


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _fetch_all_old_ecd_rows(version: str) -> list[dict[str, Any]]:
    """Page through every compara_ortholog_ecd row for ``version``."""
    cols = ", ".join(ECD_COLS)
    out: list[dict[str, Any]] = []
    page = 1000
    offset = 0
    while True:
        rows = _query_public(
            f"SELECT {cols} FROM compara_ortholog_ecd "
            "WHERE ortholog_ecd_version = ? "
            "ORDER BY human_hgnc_id, species, ortholog_uniprot_acc "
            "LIMIT ? OFFSET ?",
            [version, page, offset],
        )
        out.extend(rows)
        if len(rows) < page:
            break
        offset += page
    return out


def _read_delta_statuses(path: Path) -> dict[str, str]:
    """{(hgnc|species_norm): status} from the selection-delta TSV."""
    out: dict[str, str] = {}
    if not path or not path.exists():
        return out
    with path.open(encoding="utf-8") as f:
        header = f.readline().rstrip("\n").split("\t")
        for line in f:
            cells = line.rstrip("\n").split("\t")
            if len(cells) != len(header):
                continue
            rec = dict(zip(header, cells, strict=True))
            # delta 'species' column is the cohort key (mouse_ortholog/cyno_ortholog)
            sp = "cynomolgus" if rec.get("species") == "cyno_ortholog" else "mouse"
            out[f"{rec['human_hgnc_id']}|{sp}"] = rec.get("status", "")
    return out


def _run_upload(cmd: list[str], *, execute: bool) -> None:
    logger.info("$ %s", " ".join(cmd))
    if not execute:
        logger.info("[DRY] (skipped subprocess)")
        return
    subprocess.run(cmd, cwd=REPO_ROOT, check=True)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rerun-dir", type=Path, required=True)
    ap.add_argument("--old-ecd-version", default="orthologecd_topo_2026_05_16")
    ap.add_argument("--new-ecd-version", default="orthologecd_topo_2026_05_16_idfix")
    ap.add_argument("--topology-version", default="topo_2026_05_16")
    ap.add_argument("--compara-release", default="ensembl_compara_2026_05_12")
    ap.add_argument("--delta", type=Path, default=None,
                    help="Selection-delta TSV (for the morning summary only).")
    ap.add_argument("--notes", default="")
    ap.add_argument("--execute", action="store_true",
                    help="Without this flag the script is a dry run (no D1 writes).")
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    load_env()

    # --- Corrected rows from the rerun. ---
    corrected = _read_jsonl(args.rerun_dir / "ortholog_ecd_records.jsonl")
    corrected_keys = {
        f"{r['human_hgnc_id']}|{_norm_species(r['species'])}" for r in corrected
    }
    logger.info("corrected ECD rows from rerun: %d (covering %d gene×species keys)",
                len(corrected), len(corrected_keys))

    mouse_topo = args.rerun_dir / "mouse_ortholog" / "topology_records.jsonl"
    cyno_topo = args.rerun_dir / "cyno_ortholog" / "topology_records.jsonl"
    n_topo = len(_read_jsonl(mouse_topo)) + len(_read_jsonl(cyno_topo))
    logger.info("new ortholog topology rows: %d", n_topo)

    # --- Old version: snapshot + carry-forward (minus changed-gene rows). ---
    old_rows = _fetch_all_old_ecd_rows(args.old_ecd_version)
    logger.info("old ECD version %s: %d rows", args.old_ecd_version, len(old_rows))
    snapshot = args.rerun_dir / "old_ecd_snapshot.jsonl"
    with snapshot.open("w", encoding="utf-8") as f:
        for r in old_rows:
            f.write(json.dumps(r, sort_keys=True) + "\n")
    logger.info("snapshotted old version → %s", snapshot)

    carried: list[dict[str, Any]] = []
    n_replaced = 0
    for r in old_rows:
        key = f"{r['human_hgnc_id']}|{_norm_species(r.get('species', ''))}"
        if key in corrected_keys:
            n_replaced += 1  # superseded by a corrected row; drop the stale one
            continue
        carried.append(r)

    complete = carried + corrected
    complete_path = args.rerun_dir / "ortholog_ecd_complete.jsonl"
    with complete_path.open("w", encoding="utf-8") as f:
        for r in complete:
            f.write(json.dumps(r, sort_keys=True) + "\n")
    logger.info("complete new version: %d carried + %d corrected = %d rows → %s",
                len(carried), len(corrected), len(complete), complete_path)

    # --- Changed-but-not-corrected (DeepTMHMM gap) report. ---
    delta_status = _read_delta_statuses(args.delta) if args.delta else {}
    changed_keys = {k for k, v in delta_status.items() if v == "changed"}
    new_keys = {k for k, v in delta_status.items() if v == "new"}
    dropped_keys = {k for k, v in delta_status.items() if v == "dropped"}
    changed_uncorrected = sorted(changed_keys - corrected_keys)
    new_uncorrected = sorted(new_keys - corrected_keys)

    # --- Uploads (non-destructive). Topology FIRST so the ECD join resolves. ---
    topo_jsonls: list[str] = []
    if mouse_topo.exists():
        topo_jsonls += ["--jsonl", str(mouse_topo)]
    if cyno_topo.exists():
        topo_jsonls += ["--jsonl", str(cyno_topo)]
    if topo_jsonls:
        _run_upload(
            ["uv", "run", "python", "scripts/upload_topology_to_d1.py",
             "--topology-version", args.topology_version,
             *topo_jsonls,
             "--cohorts-present", "mouse_ortholog,cyno_ortholog",
             "--notes", args.notes or "ortholog identity-fix rerun (additive ortholog topology)"],
            execute=args.execute,
        )

    _run_upload(
        ["uv", "run", "python", "scripts/upload_ortholog_ecd_to_d1.py",
         "--ortholog-ecd-version", args.new_ecd_version,
         "--compara-release", args.compara_release,
         "--jsonl", str(complete_path),
         "--notes", args.notes or (
             f"identity-fix: carried {len(carried)} unchanged + {len(corrected)} "
             f"corrected; supersedes {args.old_ecd_version}")],
        execute=args.execute,
    )

    # --- Morning summary. ---
    logger.info("================= FINALIZE SUMMARY =================")
    logger.info("mode: %s", "EXECUTE (D1 written)" if args.execute else "DRY RUN (no writes)")
    logger.info("new ortholog_ecd_version : %s", args.new_ecd_version)
    logger.info("old ortholog_ecd_version : %s (preserved)", args.old_ecd_version)
    logger.info("topology_version (additive): %s", args.topology_version)
    logger.info("new ortholog topology rows inserted: %d", n_topo)
    logger.info("complete ECD version rows: %d (%d carried + %d corrected)",
                len(complete), len(carried), len(corrected))
    logger.info("stale ECD rows superseded (dropped from new version): %d", n_replaced)
    if delta_status:
        logger.info("delta: %d changed, %d new, %d dropped",
                    len(changed_keys), len(new_keys), len(dropped_keys))
    if changed_uncorrected:
        logger.info("WARN %d 'changed' gene×species had NO corrected row "
                    "(DeepTMHMM gap / too-long); old row carried forward: %s",
                    len(changed_uncorrected), changed_uncorrected[:20])
    if new_uncorrected:
        logger.info("WARN %d 'new' gene×species had NO corrected row: %s",
                    len(new_uncorrected), new_uncorrected[:20])
    if dropped_keys:
        logger.info("NOTE %d 'dropped' gene×species (new resolver found nothing) "
                    "kept their old row — not deleted.", len(dropped_keys))
    logger.info("rollback: delete new release pointer + new-version rows, or "
                "re-point consumers; old version untouched. snapshot=%s", snapshot)
    logger.info("===================================================")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
