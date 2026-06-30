"""Drift guard: each gist's bundled TSV ↔ canonical repo TSV.

Why: SWHID-of-the-gist is only a stable reproduction identifier if the
bundled TSV matches what the script was tested against in the repo.
If the canonical TSV is regenerated but the gist's bundled copy isn't
re-pushed, the gist publishes a stale data + script pair — anyone
running `uv run make_<slug>.py` from the gist would get different
output than the figure committed in this repo.

This test fetches the bundled TSV from each gist via the public raw
URL (no auth) and SHA256-compares against the canonical TSV in the
repo. Fails CI on any mismatch.

When this test fails: run
``uv run python scripts/sync_figure_gists_bundle_data.py`` to re-push
the affected TSVs, then refresh ``swhid_map.json``.

Marked ``network`` (gated by ``--run-network``) since it hits
gist.githubusercontent.com — keeps the default ``pytest`` invocation
fully offline. CI's nightly cron should run with ``--run-network``.
"""
from __future__ import annotations

import hashlib
import json
import urllib.error
import urllib.request
from pathlib import Path

import pytest

# Mirror the sync helper's TSV bundle so this test doesn't depend on
# importing the script (which lives outside the test path).
TSV_BUNDLE: dict[str, list[str]] = {
    "benchmark_cost_vs_accuracy": [
        "data/eval/triage_benchmark_v1.tsv",
        "data/processed/triage_bench/mainbench_canonical_v2.tsv",
        "data/processed/triage_bench/mainbench_replicates_v2.tsv",
    ],
    "db_correctness_by_class": [
        "data/eval/triage_benchmark_v1.tsv",
        "data/processed/catalog/whole_proteome_catalog.tsv",
        "data/processed/triage_bench/mainbench_canonical_v2.tsv",
        "data/processed/triage_bench/mainbench_replicates_v2.tsv",
        "data/processed/triage_bench/db_optimized_cutoffs.tsv",
    ],
    "db_correctness_overall": [
        "data/eval/triage_benchmark_v1.tsv",
        "data/processed/triage_bench/mainbench_canonical_v2.tsv",
        "data/processed/triage_bench/mainbench_replicates_v2.tsv",
    ],
    "db_cutoff_tradeoff": [
        "data/processed/triage_bench/db_cutoff_tradeoff_points.tsv",
    ],
    "db_overlap_venn": [
        "data/processed/catalog/whole_proteome_catalog.tsv",
    ],
    "db_vs_sonnet_whole_proteome": [
        "data/processed/catalog/whole_proteome_catalog.tsv",
        "data/processed/triage_bench/db_optimized_cutoffs.tsv",
    ],
    "ensemble_vs_best_db_vs_sonnet": [
        "data/eval/triage_benchmark_v1.tsv",
        "data/processed/catalog/whole_proteome_catalog.tsv",
        "data/processed/triage_bench/mainbench_canonical_v2.tsv",
        "data/processed/triage_bench/mainbench_replicates_v2.tsv",
    ],
    "paywall_bot_block_compare": [
        "data/processed/paywall_bot_block/paywall_bot_block_compare.tsv",
    ],
    "positive_control_db_coverage_bars": [
        "data/processed/figures/positive_control_db_coverage_bars.tsv",
    ],
    "bench_topology_vs_universe": [
        "data/processed/figures/bench_topology_vs_universe.tsv",
    ],
    "triage_vs_deep_dive_reason": [
        "data/processed/figures/triage_vs_deep_dive_reason.tsv",
    ],
    "evidence_corpus_vs_selected": [
        "data/processed/figures/evidence_corpus_vs_selected.tsv",
    ],
    "topology_coverage_by_source": [
        "data/analysis/db_vs_sonnet_inclusion/per_protein_features.tsv",
    ],
    "zero_db_rescues_by_triage": [
        "data/processed/catalog/whole_proteome_catalog.tsv",
    ],
}

REPO_ROOT = Path(__file__).resolve().parent.parent
MAP_PATH = REPO_ROOT / "data/analysis/figures/gist_map.json"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _gist_raw_url(gist_id: str, filename: str) -> str:
    """gist.githubusercontent.com serves bundled gist files without auth."""
    return f"https://gist.githubusercontent.com/beccajcarlson/{gist_id}/raw/{filename}"


def _gist_pairs() -> list[tuple[str, str, str]]:
    """Yield (slug, gist_id, tsv_path) for every (slug, TSV) the bundle declares."""
    if not MAP_PATH.is_file():
        return []
    gmap = json.loads(MAP_PATH.read_text())
    out: list[tuple[str, str, str]] = []
    for slug, tsv_paths in TSV_BUNDLE.items():
        if slug not in gmap:
            continue
        for path in tsv_paths:
            out.append((slug, gmap[slug], path))
    return out


@pytest.mark.network
@pytest.mark.parametrize("slug,gist_id,tsv_path", _gist_pairs())
def test_gist_bundled_tsv_matches_canonical(
    slug: str, gist_id: str, tsv_path: str
) -> None:
    """Each gist's bundled TSV must sha256-match the canonical TSV in
    the repo at HEAD. If this fails, the gist publishes a stale
    data/script pair — re-run ``sync_figure_gists_bundle_data.py``."""
    canonical = REPO_ROOT / tsv_path
    if not canonical.is_file():
        pytest.skip(f"canonical {tsv_path} not in this checkout")
    canonical_hash = _sha256_file(canonical)

    filename = Path(tsv_path).name
    url = _gist_raw_url(gist_id, filename)
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:  # noqa: S310
            bundled = resp.read()
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            pytest.fail(
                f"{slug}: bundled TSV {filename} missing from gist {gist_id} "
                f"(404 at {url}). Run scripts/sync_figure_gists_bundle_data.py."
            )
        raise
    bundled_hash = _sha256_bytes(bundled)

    assert bundled_hash == canonical_hash, (
        f"{slug}: bundled {filename} drifted from canonical.\n"
        f"  canonical: {canonical_hash}\n"
        f"  in gist:   {bundled_hash}\n"
        f"  url:       {url}\n"
        f"Fix: re-run `uv run python scripts/sync_figure_gists_bundle_data.py` "
        f"to push the canonical TSV into the gist."
    )
