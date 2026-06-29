"""The durable mid-run PTS checkpoint publisher hook (gap-1 crash durability).

The orchestrator calls ``_publish_pts_checkpoint`` right after plan-trim-select
completes. It must: invoke an installed publisher with the gene + a blob
carrying the serialized dual; no-op when none is installed (local runs); and
never propagate a publisher exception (best-effort — a failed durable write must
not break a gene).
"""

from __future__ import annotations

from typing import Any, cast

import pytest

from accessible_surfaceome.agents.surfaceome_v2 import orchestrator as orch

# Placeholder dual/timing — never read because the tests monkeypatch
# ``_pts_only_intermediates``; cast through Any to satisfy the type checker.
_DUAL = cast(Any, object())
_TIMING = cast(Any, object())


@pytest.fixture(autouse=True)
def _clear_publisher():
    orch.set_pts_checkpoint_publisher(None)
    yield
    orch.set_pts_checkpoint_publisher(None)


def test_publish_invokes_installed_publisher(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, dict]] = []
    orch.set_pts_checkpoint_publisher(lambda gene, blob: calls.append((gene, blob)))
    # Bypass dual serialization — we're testing the hook plumbing, not _serialize_pts.
    monkeypatch.setattr(orch, "_pts_only_intermediates", lambda dual, timing: {"plan_trim_select": {"gene": "G"}})

    orch._publish_pts_checkpoint("GENEX", _DUAL, _TIMING)

    assert len(calls) == 1
    gene, blob = calls[0]
    assert gene == "GENEX"
    assert "plan_trim_select" in blob


def test_no_publisher_is_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(orch, "_pts_only_intermediates", lambda dual, timing: {})
    # No publisher installed (fixture cleared it) — must not raise.
    orch._publish_pts_checkpoint("GENEX", _DUAL, _TIMING)


def test_publisher_exception_is_swallowed(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(gene: str, blob: dict) -> None:
        raise RuntimeError("durable write failed")

    orch.set_pts_checkpoint_publisher(_boom)
    monkeypatch.setattr(orch, "_pts_only_intermediates", lambda dual, timing: {})
    # Best-effort: a publish failure must not break the gene.
    orch._publish_pts_checkpoint("GENEX", _DUAL, _TIMING)
