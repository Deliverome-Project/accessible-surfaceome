"""Drift guard: every committed figure TSV is byte-reproducible from its
``build_figure_tsvs.py`` builder.

``build_figure_tsvs.py`` is the SINGLE SOURCE OF TRUTH for figure DATA. This
test asserts each committed ``data/processed/figures/<slug>.tsv`` is exactly
what ``BUILDERS[slug](_load_sources())`` produces — so the data can't silently
drift from the builder (an upstream source like the catalog, per_protein_features,
the optimized cutoffs, or mainbench changed but the figure TSV wasn't
regenerated; or a builder's logic changed without re-exporting).

Together with:
  • ``test_figure_gist_data_sync.py``            (gist's bundled TSV == committed TSV)
  • ``test_canonical_mock_reads_bundled_tsv.py`` (mock canonicals read the TSV)
  • ``test_figure_canonical_mirror_sync.py``     (canonical ↔ mirror layout)
this enforces the chain ``builder → committed TSV → gist`` as provably equal,
which is the spine of the figure-drift architecture.

Offline: reads only the local canonical sources via ``_load_sources``. A slug
skips if its sources or committed TSV aren't in the checkout.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
FIG_TSV_DIR = REPO / "data/processed/figures"

# build_figure_tsvs lives in scripts/, not an installed package.
sys.path.insert(0, str(REPO / "scripts"))
import build_figure_tsvs as bft  # noqa: E402


def _is_lfs_pointer(path: Path) -> bool:
    """The per-figure TSVs are LFS-tracked (gist-bundled, not raw-served). On a
    checkout without `git lfs pull` (e.g. CI's bare actions/checkout) they are
    3-line pointer stubs, not data — comparing a builder against a pointer is a
    false failure, so skip. The build_figure_tsvs SOURCES are LFS-exempt text,
    so the builder itself still runs."""
    try:
        return path.read_bytes()[:40].startswith(b"version https://git-lfs")
    except OSError:
        return False


@pytest.fixture(scope="module")
def sources():
    try:
        return bft._load_sources()
    except FileNotFoundError as exc:
        pytest.skip(f"canonical figure sources unavailable in this checkout: {exc}")


@pytest.mark.parametrize("slug", sorted(bft.BUILDERS))
def test_figure_tsv_reproducible_from_builder(slug: str, sources) -> None:
    committed = FIG_TSV_DIR / f"{slug}.tsv"
    if not committed.is_file():
        pytest.skip(f"{slug}: no committed TSV at data/processed/figures/{slug}.tsv")
    if _is_lfs_pointer(committed):
        pytest.skip(f"{slug}: committed TSV is an unsmudged LFS pointer — run "
                    f"`git lfs pull` to enable this guard (or check out with lfs:true)")
    regenerated = bft.BUILDERS[slug](sources).to_csv(sep="\t", index=False)
    assert regenerated == committed.read_text(), (
        f"{slug}: committed data/processed/figures/{slug}.tsv is NOT reproducible "
        f"from build_figure_tsvs.BUILDERS['{slug}'] — the figure DATA has drifted "
        f"from its single source of truth. Re-run "
        f"`uv run python scripts/build_figure_tsvs.py`, commit the TSV, then sync "
        f"the gist with scripts/sync_figure_gists_bundle_data.py."
    )
