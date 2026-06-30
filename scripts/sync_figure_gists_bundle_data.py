"""Bundle canonical TSV(s) into each figure gist + push updated mirror
+ record per-gist SWHID. End state: every published-figure gist is a
self-contained reproduction unit (data + script + README) cited as
``swh:1:rev:<sha>`` of the gist's HEAD commit.

Why: per the discussion in PR #86, the data-stability story is far
simpler when each figure's TSV lives bundled in the gist alongside
the script — one SWHID identifies the whole reproduction bundle
atomically, rather than separate identifiers for the script and the
TSV that can drift. Bundle once → publication-time citation is a
single content-addressed reference.

Drives ``gh gist edit`` for every entry in
``data/analysis/figures/gist_map.json`` whose mirror declares one or
more canonical TSV URLs (``BASE/data/...``). For each:

  1. ``gh gist edit <id> -a <tsv-path>`` for each TSV the mirror reads
  2. ``gh gist edit <id> -f make_<slug>.py <local-mirror>`` to push the
     sibling-first version that prefers the bundled file
  3. ``gh api gists/<id>`` to pull the new HEAD commit SHA
  4. Record ``swh:1:rev:<sha>`` in
     ``data/analysis/figures/swhid_map.json`` (slug → SWHID)

``deep_dive_final_categories`` is skipped — it's a MOCK figure with
hardcoded counts and no TSV to bundle.

Usage:
    uv run python scripts/sync_figure_gists_bundle_data.py [--dry-run]

Idempotent. Safe to re-run; ``gh gist edit -a`` updates existing files
in place.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIGURES_DIR = ROOT / "data/analysis/figures"
MAP_PATH = FIGURES_DIR / "gist_map.json"
SWHID_MAP_PATH = FIGURES_DIR / "swhid_map.json"

# Per-gist TSV bundle. Hand-curated to be robust against multi-line
# URL constants my AST-less extractor couldn't catch. Keep in sync
# when a mirror starts fetching a new TSV. ``deep_dive_final_categories``
# is MOCK and not in this map.
TSV_BUNDLE: dict[str, list[str]] = {
    # Single-TSV-per-gist invariant: each gist bundles exactly ONE TSV
    # that carries everything its mirror script needs. The 6 figures
    # that previously joined multiple sources now read pre-joined
    # per-figure TSVs produced by ``scripts/build_figure_tsvs.py``.
    # Tests in tests/test_gist_single_tsv.py enforce the invariant.
    "benchmark_cost_vs_accuracy": [
        "data/processed/figures/benchmark_cost_vs_accuracy.tsv",
    ],
    "curator_vs_agent_reason": [
        "data/processed/figures/curator_vs_agent_reason.tsv",
    ],
    "db_correctness_by_class": [
        "data/processed/figures/db_correctness_by_class.tsv",
    ],
    "db_correctness_overall": [
        "data/processed/figures/db_correctness_overall.tsv",
    ],
    "db_cutoff_tradeoff": [
        "data/processed/triage_bench/db_cutoff_tradeoff_points.tsv",
    ],
    "db_overlap_venn": [
        "data/processed/catalog/whole_proteome_catalog.tsv",
    ],
    "db_vs_sonnet_whole_proteome": [
        "data/processed/figures/db_vs_sonnet_whole_proteome.tsv",
    ],
    "deep_dive_final_categories": [
        "data/processed/figures/deep_dive_final_categories.tsv",
    ],
    "ensemble_vs_best_db_vs_sonnet": [
        "data/processed/figures/ensemble_vs_best_db_vs_sonnet.tsv",
    ],
    "paywall_bot_block_compare": [
        "data/processed/paywall_bot_block/paywall_bot_block_compare.tsv",
    ],
    "positive_control_db_coverage_bars": [
        # Single per-figure consolidated TSV — pass-through copy of the
        # canonical positive_control_long.tsv into data/processed/figures/
        # so the slug matches the bundled basename per the invariant.
        "data/processed/figures/positive_control_db_coverage_bars.tsv",
    ],
    "bench_topology_vs_universe": [
        # Sonnet 2-tier yes/contextual universe + bench-membership flag.
        # One row per universe protein with all 9 topology flags + is_bench.
        # The figure derives both bars (universe + bench) from this single TSV.
        "data/processed/figures/bench_topology_vs_universe.tsv",
    ],
    "triage_vs_deep_dive_reason": [
        # MOCK long-form 10×10 confusion-matrix counts. Pivoted into a
        # matrix at render time. Bundled rather than re-declared as a dict
        # in the mirror so the gist stays single-source.
        "data/processed/figures/triage_vs_deep_dive_reason.tsv",
    ],
    "evidence_corpus_vs_selected": [
        # MOCK synthesized per-gene (papers_found, papers_selected,
        # verdict) tuples. Bundled rather than synthesized at render time
        # in the mirror so the gist stays single-source.
        "data/processed/figures/evidence_corpus_vs_selected.tsv",
    ],
    "surfaceome_deterministic_features_placeholder": [
        # MOCK-grouped per-gene deterministic features (Supp Fig 13).
        # Single pre-joined TSV built by build_figure_tsvs.py.
        "data/processed/figures/surfaceome_deterministic_features_placeholder.tsv",
    ],
    "topology_coverage_by_source": [
        "data/analysis/db_vs_sonnet_inclusion/per_protein_features.tsv",
    ],
    "zero_db_rescues_by_triage": [
        "data/processed/catalog/whole_proteome_catalog.tsv",
    ],
}


def _run(cmd: list[str], dry: bool, *, tolerate_409: bool = False) -> str:
    """Run a shell command, print it. Returns stdout on success.

    ``tolerate_409``: gh returns HTTP 409 "Gist cannot be updated"
    when the file content matches what's already published (no diff
    to commit). For the per-file mirror push that's not an error —
    just means the previous push already had this content.
    """
    print("  $ " + " ".join(cmd))
    if dry:
        return ""
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        err = (res.stderr or "") + (res.stdout or "")
        if tolerate_409 and "HTTP 409" in err:
            print("    (HTTP 409 — no diff to push, treating as no-op)")
            return ""
        sys.stderr.write(err)
        raise RuntimeError(f"command failed: {' '.join(cmd)}")
    return res.stdout


def _gist_head_sha(gist_id: str) -> str:
    """Latest commit SHA of the gist, via the GitHub API. This SHA is
    the ``sha1_git`` Software Heritage uses for its rev SWHIDs."""
    out = subprocess.run(
        ["gh", "api", f"gists/{gist_id}", "--jq", ".history[0].version"],
        capture_output=True, text=True,
    )
    if out.returncode != 0:
        raise RuntimeError(f"gh api failed for gist {gist_id}: {out.stderr}")
    return out.stdout.strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="print actions without executing gh edits")
    ap.add_argument("--only", action="append",
                    help="restrict to specific slug(s); repeatable")
    args = ap.parse_args()

    gist_map = json.loads(MAP_PATH.read_text())
    swhid_map: dict[str, str] = {}
    if SWHID_MAP_PATH.is_file():
        swhid_map = json.loads(SWHID_MAP_PATH.read_text())

    for slug in sorted(gist_map.keys()):
        if args.only and slug not in args.only:
            continue
        gist_id = gist_map[slug]
        mirror = FIGURES_DIR / f"make_{slug}.py"
        if not mirror.is_file():
            print(f"\n=== {slug}: no mirror, skip")
            continue
        tsv_paths = TSV_BUNDLE.get(slug, [])
        print(f"\n=== {slug}  →  gist {gist_id}")
        if not tsv_paths:
            print("  (no TSV fetches — MOCK figure, skip data bundle)")
            # Still push the script + capture SWHID
            _run(["gh", "gist", "edit", gist_id, "-f", mirror.name, str(mirror)],
                 args.dry_run, tolerate_409=True)
        else:
            for path in tsv_paths:
                tsv_local = ROOT / path
                if not tsv_local.is_file():
                    print(f"  ⚠ {path} not found in repo; skipping")
                    continue
                size_mb = tsv_local.stat().st_size / 1e6
                tag = " ⚠ over 1 MB gist soft cap" if size_mb > 1.0 else ""
                print(f"  bundling {path} ({size_mb:.2f} MB){tag}")
                _run(["gh", "gist", "edit", gist_id, "-a", str(tsv_local)],
                     args.dry_run)
            print("  pushing updated mirror")
            _run(["gh", "gist", "edit", gist_id, "-f", mirror.name, str(mirror)],
                 args.dry_run, tolerate_409=True)

        if not args.dry_run:
            sha = _gist_head_sha(gist_id)
            swhid = f"swh:1:rev:{sha}"
            swhid_map[slug] = swhid
            print(f"  HEAD: {sha}  →  {swhid}")

    if not args.dry_run:
        SWHID_MAP_PATH.write_text(
            json.dumps(swhid_map, indent=2, sort_keys=True) + "\n"
        )
        print(f"\n  wrote {SWHID_MAP_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
