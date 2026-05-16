"""Resolver-collision fix v3 — rerun affected genes through the
HGNC-ID-keyed resolver and insert under a DERIVED run_id.

Differs from ``fix_resolver_collisions.py`` (the v2 fix that ran
against ``run_id=genome_full_sonnet_ncbi_v1`` and DELETED + REPLACED
contaminated rows) in two important ways:

  1. **No clobber.** Originals stay under the canonical run_id; the
     corrected re-runs land under
     ``<original_run_id>__resolver_v3_fix``. Downstream tools
     (``build_universe_v2.py`` etc.) opt into the fix run by name —
     explicit consent contract.
  2. **HGNC-ID-keyed resolution.** The input TSV carries
     ``gene_symbol`` AND ``hgnc_id``. The runner's
     ``_resolve_task_text`` (post-Phase-5) prefers ``hgnc_id`` over
     symbol-keyed lookup, so the rerun cells get the canonical
     UniProt acc the v3 audit identified.

Inputs:
  * ``data/analysis/resolver_definitive_audit_v3_d1_rows_full.tsv``
    — produced by ``scripts/audit_resolver_hgnc_id_v3_extend.py``.
    One row per affected (table, run_id, model, gene_symbol) tuple
    across triage_run + deep_dive_run + benchmark_version.

Outputs:
  * ``data/analysis/resolver_v3_d1_backup_<timestamp>.tsv`` — full
    snapshot of every row that's about to be paired with a
    correction, so the originals are recoverable even though we
    aren't deleting them.
  * ``data/analysis/resolver_v3_rerun_input_<table>_<run_id>.tsv``
    — per-cell rerun input fed to ``triage_subbench_runner.py``.
    Columns: ``gene_symbol``, ``hgnc_id``.
  * D1: new triage_run rows under ``<run_id>__resolver_v3_fix``.

Safety properties:
  * Backup snapshot is the first I/O — we don't proceed if it
    can't be written.
  * Insert-only — no DELETE / UPDATE against D1.
  * Derived run_id makes the corrections discoverable by run_id
    pattern (``run_id LIKE '%__resolver_v3_fix'``) for downstream
    catalog opt-in.
  * Dry-run by default; ``--execute`` to actually invoke the
    runner.

Cost: 45 symbols × ~$0.10 per Sonnet triage call ≈ $5. Wall
time ~5-10 min at the runner's default concurrency.

Usage::

    uv run python scripts/fix_resolver_v3_collisions.py            # dry-run
    uv run python scripts/fix_resolver_v3_collisions.py --execute  # do it
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import subprocess
import sys
from collections import defaultdict

from accessible_surfaceome.cloud.d1_client import D1Client
from accessible_surfaceome.env import load_env
from accessible_surfaceome.paths import REPO_ROOT

load_env()

AUDIT_TSV = (
    REPO_ROOT / "data/analysis/resolver_definitive_audit_v3_d1_rows_full.tsv"
)
ANALYSIS_DIR = REPO_ROOT / "data/analysis"
RUNNER = REPO_ROOT / "scripts/triage_subbench_runner.py"
FIX_SUFFIX = "__resolver_v3_fix"


def _load_affected() -> list[dict[str, str]]:
    if not AUDIT_TSV.exists():
        sys.exit(
            f"missing audit TSV: {AUDIT_TSV.relative_to(REPO_ROOT)}\n"
            f"run scripts/audit_resolver_hgnc_id_v3_extend.py first."
        )
    with AUDIT_TSV.open() as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def _backup_originals(affected: list[dict[str, str]]) -> int:
    """Snapshot every affected row from D1 to a local TSV. Belt-and-
    suspenders: we're not deleting these, but the snapshot is a
    reproducible record of D1 state at fix time."""

    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = ANALYSIS_DIR / f"resolver_v3_d1_backup_{ts}.tsv"

    # Group by table so we can use one query per table.
    by_table: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in affected:
        by_table[row["table"]].append(row)

    all_rows: list[dict] = []
    with D1Client() as d1:
        for table, rows_for_table in by_table.items():
            # Different tables have different PK shapes; query by the
            # (run_id/bench_version, gene_symbol) tuple that uniquely
            # identifies the affected row(s).
            ids = sorted({r["run_id_or_version"] for r in rows_for_table})
            symbols = sorted({r["gene_symbol"] for r in rows_for_table})
            chunk = 50
            for i in range(0, len(symbols), chunk):
                sym_chunk = symbols[i : i + chunk]
                placeholders = ",".join("?" * len(sym_chunk))
                if table == "triage_run":
                    sql = (
                        f"SELECT * FROM triage_run WHERE gene_symbol IN ({placeholders}) "
                        f"AND run_id IN ({','.join('?' * len(ids))});"
                    )
                    params = list(sym_chunk) + list(ids)
                elif table == "deep_dive_run":
                    sql = (
                        f"SELECT * FROM deep_dive_run WHERE gene_symbol IN ({placeholders}) "
                        f"AND run_id IN ({','.join('?' * len(ids))});"
                    )
                    params = list(sym_chunk) + list(ids)
                elif table == "benchmark_version":
                    sql = (
                        f"SELECT * FROM benchmark_version WHERE gene_symbol IN ({placeholders}) "
                        f"AND bench_version IN ({','.join('?' * len(ids))});"
                    )
                    params = list(sym_chunk) + list(ids)
                else:
                    continue
                rows = d1.query(sql, params)
                for r in rows:
                    r["__source_table"] = table
                    all_rows.append(r)

    if not all_rows:
        print("  (no rows matched the snapshot query — D1 may be empty for these symbols)")
        return 0
    # Tables have different columns; union the column sets for the
    # TSV header so each row has its own provenance + all available
    # fields.
    fieldnames: list[str] = []
    seen: set[str] = set()
    for r in all_rows:
        for k in r:
            if k not in seen:
                seen.add(k)
                fieldnames.append(k)
    with backup_path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames, delimiter="\t", extrasaction="ignore")
        w.writeheader()
        w.writerows(all_rows)
    print(
        f"  ✓ snapshot → {backup_path.relative_to(REPO_ROOT)} "
        f"({len(all_rows)} rows across {len(by_table)} tables)"
    )
    return len(all_rows)


def _write_rerun_inputs(affected: list[dict[str, str]]) -> list[tuple[str, str, str, str, dict[str, str]]]:
    """Group affected rows by (table, run_id, model) and write one
    rerun-input TSV per group. Returns the list of (table, run_id,
    model, input_tsv_path, runner_kwargs) tuples for the executor.

    Only triage_run rows are re-runnable via the triage_subbench_runner.
    deep_dive_run / benchmark_version updates would need their own
    re-runners (deep-dive sweeps + bench-snapshot uploaders); audit
    shows zero affected deep_dive_run rows for the v3 set, so this
    script only handles triage_run for now.
    """

    by_group: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for r in affected:
        if r["table"] != "triage_run":
            continue
        key = (r["table"], r["run_id_or_version"], r["model"])
        by_group[key].append(r)

    out: list[tuple[str, str, str, str, dict[str, str]]] = []
    for (table, run_id, model), rows_for_group in by_group.items():
        # Dedupe by (gene_symbol, hgnc_id). Multiple replicates would
        # collide in the input TSV otherwise; the runner's --replicates
        # arg controls re-run count downstream.
        seen_syms = set()
        unique_rows = []
        for r in rows_for_group:
            sym = r["gene_symbol"]
            if sym in seen_syms:
                continue
            seen_syms.add(sym)
            unique_rows.append(r)
        slug = f"{run_id}_{model.replace('/', '_')}".replace(":", "_")
        input_tsv = ANALYSIS_DIR / f"resolver_v3_rerun_input_{slug}.tsv"
        with input_tsv.open("w", newline="") as fh:
            w = csv.DictWriter(
                fh, fieldnames=["gene_symbol", "hgnc_id"], delimiter="\t"
            )
            w.writeheader()
            for r in unique_rows:
                w.writerow(
                    {"gene_symbol": r["gene_symbol"], "hgnc_id": r["hgnc_id"]}
                )
        kwargs = {
            "n_rows": len(unique_rows),
            "fix_run_id": f"{run_id}{FIX_SUFFIX}",
        }
        out.append((table, run_id, model, str(input_tsv), kwargs))
        print(
            f"  ✓ {table} {run_id} {model}: {len(unique_rows)} symbols → "
            f"{input_tsv.relative_to(REPO_ROOT)}"
        )
    return out


def _run_runner(input_tsv: str, model: str, fix_run_id: str, *, execute: bool) -> int:
    """Invoke triage_subbench_runner with the rerun input. The runner
    must pick up hgnc_id from the input row (Phase 5 patch makes
    _resolve_task_text use it). Variant=ncbi is the canonical sweep
    variant; switch if needed.

    Subtle: we deliberately invoke the canonical checkout's venv
    Python rather than ``uv run`` from this worktree. ``uv run`` in
    a fresh worktree triggers a full ``uv sync`` which can fail on
    the matplotlib sdist build (system deps). The canonical venv at
    ``$CANONICAL/.venv`` already has every dependency installed; we
    point PYTHONPATH at this worktree's ``src/`` so the patched
    resolver wins over the canonical's installed package.
    """

    import os

    canonical_root = REPO_ROOT
    # Find the canonical checkout — when running from a worktree,
    # REPO_ROOT is the worktree root, but the canonical venv lives
    # at the original clone root. Use ``git rev-parse --git-common-dir``
    # to find the shared .git dir and infer the canonical from there.
    try:
        common_git = subprocess.check_output(
            ["git", "rev-parse", "--git-common-dir"],
            cwd=str(REPO_ROOT),
            text=True,
        ).strip()
        canonical_root = REPO_ROOT.joinpath(common_git, "..").resolve()
    except (subprocess.CalledProcessError, OSError):
        pass
    py = canonical_root / ".venv" / "bin" / "python"
    if not py.exists():
        py = REPO_ROOT / ".venv" / "bin" / "python"  # worktree fallback
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")

    cmd = [
        str(py), str(RUNNER),
        "--gene-list", input_tsv,
        "--variants", "ncbi",
        "--model", model,
        "--replicates", "1",
        "--d1",
        "--run-id", fix_run_id,
        "--concurrency", "4",
    ]
    print()
    print(f"  Runner command (fix_run_id={fix_run_id}):")
    print("    PYTHONPATH=" + env["PYTHONPATH"].split(os.pathsep)[0] + " \\")
    print("    " + " ".join(cmd))
    if not execute:
        print("  (dry-run) skipping runner invocation")
        return 0
    print()
    return subprocess.call(cmd, cwd=REPO_ROOT, env=env)


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--execute",
        action="store_true",
        help="Actually invoke the runner. Without this flag, the "
        "script writes the backup snapshot and rerun-input TSVs, "
        "prints the planned runner commands, but does NOT call the API.",
    )
    args = ap.parse_args()

    affected = _load_affected()
    print(
        f"Loaded {len(affected)} affected D1 rows from "
        f"{AUDIT_TSV.relative_to(REPO_ROOT)}"
    )
    by_table = defaultdict(int)
    for r in affected:
        by_table[r["table"]] += 1
    for table, n in sorted(by_table.items(), key=lambda kv: -kv[1]):
        print(f"  {table:24} {n}")
    print()

    print("Step 1 — snapshot affected D1 rows (always, even on dry-run):")
    n_backup = _backup_originals(affected)
    if n_backup == 0:
        print("  ! Snapshot returned zero rows — refusing to proceed; check D1 state.")
        return 1
    print()

    print("Step 2 — write rerun input TSVs:")
    rerun_groups = _write_rerun_inputs(affected)
    if not rerun_groups:
        print("  (no triage_run rows to rerun)")
        return 0
    print()

    print(
        f"Step 3 — rerun via triage_subbench_runner under fix_run_id "
        f"= <original>{FIX_SUFFIX} (insert-only, originals untouched):"
    )
    exit_code = 0
    for table, run_id, model, input_tsv, kwargs in rerun_groups:
        ec = _run_runner(
            input_tsv, model=model, fix_run_id=kwargs["fix_run_id"], execute=args.execute
        )
        if ec != 0:
            print(f"  ! runner exited {ec} for {model} / {run_id}")
            exit_code = exit_code or ec

    print()
    if args.execute:
        print(f"Done. Verify with:  SELECT COUNT(*) FROM triage_run WHERE run_id LIKE '%{FIX_SUFFIX}';")
    else:
        print("Dry-run complete. Re-run with --execute to invoke the API.")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
