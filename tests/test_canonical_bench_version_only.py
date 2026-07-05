"""Guard: public D1's ``benchmark_version`` table contains exactly one
``bench_version``, equal to the pinned ``CANONICAL_BENCH_VERSION`` in
``scripts/sync_public_d1.py``.

This pins the public-D1 invariant that fell over on 2026-06-30: the
table had accumulated 17 historical bench_version slugs (4 of them
with full 147-row labels), and the
``ORDER BY bench_version DESC LIMIT 1`` heuristic used by the Worker
+ the augment script silently picked the older lex-larger
``fc7ddee89155`` (May 2026) instead of the 2026-06-29
``21731d746b50`` correction set. The figures' Sonnet 4.6 ncbi
accuracy regressed from the real 97.51% to 96.83% on the stale
labels.

After the 2026-06-30 cleanup ``sync_public_d1.py::sync_benchmark``
pushes only the pinned version, and this test asserts no out-of-band
write (a stray INSERT, a re-sync that forgot the pin) re-introduces
the multi-version state.

Offline: skips if ``CLOUDFLARE_*`` env vars are unset (most CI runs).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
import augment_figure_tsvs_with_stable_ids as augment  # noqa: E402  # ty: ignore[unresolved-import]
import sync_public_d1 as sync  # noqa: E402  # ty: ignore[unresolved-import]

_REQUIRED_ENV = (
    "CLOUDFLARE_API_TOKEN",
    "CLOUDFLARE_ACCOUNT_ID",
    "CLOUDFLARE_D1_SURFACEOME_PUBLIC_ID",
)


@pytest.fixture(scope="module")
def public_d1_creds():
    missing = [k for k in _REQUIRED_ENV if not os.environ.get(k, "").strip()]
    if missing:
        pytest.skip(
            f"public D1 creds missing ({', '.join(missing)}); skipping. "
            f"This guard runs against the live public D1 — set the "
            f"CLOUDFLARE_* env vars to exercise it locally."
        )


def test_only_canonical_bench_version_in_public_d1(public_d1_creds) -> None:
    rows = augment._query_public(
        "SELECT DISTINCT bench_version FROM benchmark_version ORDER BY bench_version;"
    )
    versions = sorted(r["bench_version"] for r in rows)
    assert versions == [sync.CANONICAL_BENCH_VERSION], (
        f"public D1 `benchmark_version` should contain exactly the pinned "
        f"canonical bench_version ({sync.CANONICAL_BENCH_VERSION!r}); found "
        f"{len(versions)} distinct version(s): {versions}. "
        f"If a non-canonical version snuck in, run "
        f"`uv run python scripts/sync_public_d1.py` (which pushes only the "
        f"pinned version) and delete the stragglers; if the pin needs to "
        f"move, edit `CANONICAL_BENCH_VERSION` in `scripts/sync_public_d1.py`."
    )


def test_canonical_bench_version_is_fully_labeled(public_d1_creds) -> None:
    """The pinned version must carry truth labels for every gene — empty
    rows can sneak in (cohort registrations etc.) and corrupt downstream
    is_match joins."""
    rows = augment._query_public(
        "SELECT COUNT(*) AS n, "
        "SUM(CASE WHEN truth_verdict = '' THEN 1 ELSE 0 END) AS n_empty "
        "FROM benchmark_version WHERE bench_version = ?;",
        [sync.CANONICAL_BENCH_VERSION],
    )
    assert rows, "canonical bench_version not present in public D1"
    n = int(rows[0]["n"])
    n_empty = int(rows[0]["n_empty"])
    assert n_empty == 0, (
        f"canonical bench_version {sync.CANONICAL_BENCH_VERSION!r} has "
        f"{n_empty}/{n} rows with empty truth_verdict — re-sync from private."
    )
    # 147 is the SurfaceBench size. If this ever changes, both the eval
    # TSV and the pin should move together.
    assert n == 147, (
        f"canonical bench_version has {n} rows; expected 147 (SurfaceBench size)."
    )
