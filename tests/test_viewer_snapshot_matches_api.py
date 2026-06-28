"""The committed per-gene viewer snapshots must equal what the public
Worker serves from D1.

``viewer/public/data/surfaceome/{SYMBOL}.json`` is the in-tree source of
truth and the SSG fallback; the live gene page reads the *same* record
from the public ``surfaceome_public`` D1 mirror via
``api.deliverome.org/surfaceome/v1/genes/{SYMBOL}``. If the two drift,
the live page renders a stale D1 row while the repo looks correct — the
exact failure mode CLAUDE.md's "records source of truth" rule warns
about (e.g. a JSON edited without re-syncing D1).

This test pins the invariant: ``parsed(snapshot) == parsed(api)`` for
every committed snapshot. It is **network-gated** (``@pytest.mark.network``
→ only runs under ``pytest --run-network``) so the default offline unit
run never depends on the live Worker. When it does run:

* a content mismatch FAILS (real snapshot↔D1 drift),
* an HTTP error FAILS (snapshot exists in-tree but the Worker won't serve
  it — unpublished / drifted),
* a connection/timeout error SKIPS (transient network unavailability, not
  a drift signal).
"""
from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.request
from pathlib import Path

import pytest

SNAPSHOT_DIR = (
    Path(__file__).resolve().parents[1] / "viewer" / "public" / "data" / "surfaceome"
)
API_BASE = "https://api.deliverome.org/surfaceome/v1/genes"

_SNAPSHOTS = sorted(SNAPSHOT_DIR.glob("*.json"))


def _ssl_context() -> ssl.SSLContext | None:
    """Prefer certifi's current CA roots — the venv's default bundle can be
    stale, which would otherwise turn a healthy run into a skip on an
    expired-certificate error. Falls back to the default context."""
    try:
        import certifi
    except ImportError:
        return None
    return ssl.create_default_context(cafile=certifi.where())


def _fetch_api(symbol: str) -> dict:
    req = urllib.request.Request(
        f"{API_BASE}/{symbol}",
        headers={
            "User-Agent": "accessible-surfaceome-tests/1.0",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(  # noqa: S310 (fixed https host)
        req, timeout=30, context=_ssl_context()
    ) as resp:
        return json.loads(resp.read().decode("utf-8"))


def test_snapshots_exist() -> None:
    """Guard the parametrize list against silently going empty (a path
    typo would otherwise make the network test vacuously pass)."""
    assert _SNAPSHOTS, f"no per-gene snapshots found under {SNAPSHOT_DIR}"


@pytest.mark.network
@pytest.mark.parametrize("snapshot", _SNAPSHOTS, ids=[p.stem for p in _SNAPSHOTS])
def test_snapshot_equals_public_api(snapshot: Path) -> None:
    symbol = snapshot.stem
    record = json.loads(snapshot.read_text(encoding="utf-8"))
    try:
        served = _fetch_api(symbol)
    except urllib.error.HTTPError as exc:
        pytest.fail(
            f"{symbol}: public API returned HTTP {exc.code} — the snapshot "
            f"exists in-tree but the Worker won't serve it. Publish it "
            f"(scripts/upload/upload_viewer_snapshots_to_d1.py --execute) or re-run "
            f"the annotator so D1 carries the record."
        )
    except (urllib.error.URLError, TimeoutError) as exc:
        pytest.skip(f"public API unreachable for {symbol}: {exc}")

    assert served == record, (
        f"{symbol}: committed snapshot differs from what the public API "
        f"(api.deliverome.org) serves from D1. Re-sync D1 — run "
        f"scripts/upload/upload_viewer_snapshots_to_d1.py --execute, or re-run the "
        f"annotator — so the Worker and the in-tree snapshot stop drifting."
    )
