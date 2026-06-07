"""Post-write triage-coherence guard in ``publish_record``.

The June-2026 bug: when ``_load_triage_record_from_d1`` failed silently
(partial creds → empty token → ``Bearer `` → swallowed exception →
``None``), the orchestrator built a record with ``triage_signal=unknown``
and the publish helper happily wrote it to D1. The Worker then served
``unknown`` even though ``triage_run_public`` had a Sonnet "yes" verdict
for every gene under the priority run_id.

The pre-flight check (``test_d1_env_preflight.py``) makes the silent
failure loud. This guard catches the bug from the other side: even when
the operator misses every warning, the publish itself refuses to ship a
record whose triage signal disagrees with D1.

Tests:

* Drift case (record says ``unknown``, D1 has Sonnet row) → refused.
* Non-drift case (record carries a real signal) → no D1 round trip, publish
  proceeds.
* Genuinely-untriaged case (record ``unknown``, D1 has no row) → publish
  proceeds.
* Transport failure on the coherence query → fail-open (publish proceeds).
* ``force=True`` bypasses the guard (operator override).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import httpx
import pytest

from accessible_surfaceome.cloud.d1_client import D1Config
from accessible_surfaceome.cloud.surface_annotation import (
    _is_triage_signal_drift,
)


def _mock_client(handler) -> httpx.Client:
    transport = httpx.MockTransport(handler)
    return httpx.Client(transport=transport)


def _ok(results: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "success": True,
        "result": [{"results": results, "success": True}],
        "errors": [],
        "messages": [],
    }


def test_drift_detected_when_unknown_and_d1_has_row() -> None:
    """Record carries ``triage_signal=unknown`` but D1 has a verdict — drift."""
    rec = {
        "gene": {"hgnc_symbol": "SLC7A5"},
        "triage_signal": "unknown",
    }
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return httpx.Response(200, json=_ok([{"1": 1}]))

    cfg = D1Config(account_id="a", database_id="d", api_token="t")
    with _mock_client(handler) as client:
        assert _is_triage_signal_drift(rec, cfg, client=client) is True
    # First priority run_id wins — only one D1 round trip.
    assert len(calls) == 1


def test_no_drift_when_record_has_real_signal() -> None:
    """``triage_signal != "unknown"`` short-circuits — no D1 round trip."""
    rec = {
        "gene": {"hgnc_symbol": "SLC7A5"},
        "triage_signal": "yes_surface",
    }
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        return httpx.Response(200, json=_ok([{"1": 1}]))

    cfg = D1Config(account_id="a", database_id="d", api_token="t")
    with _mock_client(handler) as client:
        assert _is_triage_signal_drift(rec, cfg, client=client) is False
    assert seen == [], (
        "non-unknown signal must not trigger a D1 round trip — keeping the "
        "guard cheap on the common case"
    )


def test_no_drift_when_unknown_and_d1_empty() -> None:
    """Record carries ``unknown`` and D1 has no row — legitimate untriaged
    gene (e.g. a fresh annotate on a benchmark sample not in the genome sweep).
    """
    rec = {
        "gene": {"hgnc_symbol": "NEWGENE1"},
        "triage_signal": "unknown",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_ok([]))  # empty result set

    cfg = D1Config(account_id="a", database_id="d", api_token="t")
    with _mock_client(handler) as client:
        assert _is_triage_signal_drift(rec, cfg, client=client) is False


def test_no_drift_when_record_missing_gene_symbol() -> None:
    """Record without ``gene.hgnc_symbol`` — can't query, fail open."""
    rec = {"triage_signal": "unknown"}  # no gene field

    def handler(request: httpx.Request) -> httpx.Response:
        pytest.fail("must not call D1 when gene_symbol is unresolvable")
        return httpx.Response(500)

    cfg = D1Config(account_id="a", database_id="d", api_token="t")
    with _mock_client(handler) as client:
        assert _is_triage_signal_drift(rec, cfg, client=client) is False


def test_transport_failure_fails_open() -> None:
    """A timeout / 500 on the coherence query must not break publish."""
    rec = {
        "gene": {"hgnc_symbol": "SLC7A5"},
        "triage_signal": "unknown",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("D1 timeout")

    cfg = D1Config(account_id="a", database_id="d", api_token="t")
    with _mock_client(handler) as client:
        # Fail open — drift returns False, the publish proceeds, the other
        # guards (regression / staleness) still apply.
        assert _is_triage_signal_drift(rec, cfg, client=client) is False


def test_d1_returns_non_success_fails_open() -> None:
    """A ``success: false`` response is treated like transport failure."""
    rec = {
        "gene": {"hgnc_symbol": "SLC7A5"},
        "triage_signal": "unknown",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"success": False, "errors": [{"message": "boom"}]}
        )

    cfg = D1Config(account_id="a", database_id="d", api_token="t")
    with _mock_client(handler) as client:
        assert _is_triage_signal_drift(rec, cfg, client=client) is False


def test_drift_falls_through_priority_runs() -> None:
    """Empty first priority but hit on a later run_id still flags drift.

    Mirrors the runtime fallback's behaviour — it walks the priority
    list until it finds a row. The guard does the same so a record that
    was *only* covered by the genome-wide sweep (not the bench) still
    gets the coherence check. Number of mock responses MUST match the
    priority-list length; if the list changes (e.g. a v3 sweep ships
    and replaces v2), update both sides.
    """
    rec = {
        "gene": {"hgnc_symbol": "GPR75"},
        "triage_signal": "unknown",
    }
    responses = [
        _ok([]),  # mainbench_canonical_v2 — no hit
        _ok([{"1": 1}]),  # genome_full_sonnet_ncbi_v2 — hit
    ]
    iter_responses = iter(responses)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=next(iter_responses))

    cfg = D1Config(account_id="a", database_id="d", api_token="t")
    with _mock_client(handler) as client:
        assert _is_triage_signal_drift(rec, cfg, client=client) is True


# -- Higher-level: full publish_record path under drift / force ---------------


def test_publish_refuses_under_drift(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """Integration: ``publish_record_dict`` returns a refusal when drift fires.

    Stubs ``_is_triage_signal_drift`` directly so we don't have to wire up
    the full D1 mock stack — the unit tests above already cover the drift
    detector. We just verify the orchestrator-level wiring.
    """
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "a")
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "t")
    monkeypatch.setenv("CLOUDFLARE_D1_SURFACEOME_PUBLIC_ID", "d")
    from accessible_surfaceome.cloud import surface_annotation

    rec = {
        "gene": {
            "hgnc_symbol": "SLC7A5",
            "hgnc_id": "HGNC:11050",
            "uniprot_acc": "Q01650",
        },
        "schema_version": "2.6.0",
        "triage_signal": "unknown",
        "confidence": "moderate",
        "executive_summary": {"uniprot_family": "fake fam", "hgnc_gene_groups": ["g"]},
    }
    with patch.object(
        surface_annotation, "_is_triage_signal_drift", return_value=True
    ):
        result = surface_annotation.publish_record_dict(
            rec, snapshot_dir=tmp_path, write_snapshot=False
        )
    assert result.d1_written is False
    assert result.skipped_reason is not None
    assert "triage-coherence" in result.skipped_reason


def test_force_bypasses_drift(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """``force=True`` is the operator-knows-best escape hatch — same posture
    as the regression and staleness guards."""
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "a")
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "t")
    monkeypatch.setenv("CLOUDFLARE_D1_SURFACEOME_PUBLIC_ID", "d")
    from accessible_surfaceome.cloud import surface_annotation

    drift_called = {"n": 0}

    def fake_drift(*args, **kwargs):
        drift_called["n"] += 1
        return True

    rec = {
        "gene": {
            "hgnc_symbol": "SLC7A5",
            "hgnc_id": "HGNC:11050",
            "uniprot_acc": "Q01650",
        },
        "schema_version": "2.6.0",
        "triage_signal": "unknown",
        "confidence": "moderate",
        "executive_summary": {"uniprot_family": "fake fam", "hgnc_gene_groups": ["g"]},
    }
    # Stub D1 transport to no-op all writes; force=True still walks past
    # the coherence guard, so we just need every D1 call to succeed.
    with patch.object(
        surface_annotation, "_is_triage_signal_drift", side_effect=fake_drift
    ), patch.object(
        surface_annotation,
        "_post",
        return_value={"result": [{"results": []}], "success": True},
    ), patch.object(
        surface_annotation, "_maybe_purge", return_value=None
    ):
        result = surface_annotation.publish_record_dict(
            rec, snapshot_dir=tmp_path, write_snapshot=False, force=True
        )
    assert drift_called["n"] == 0, (
        "force=True must short-circuit before the coherence guard runs"
    )
    assert result.d1_written is True
