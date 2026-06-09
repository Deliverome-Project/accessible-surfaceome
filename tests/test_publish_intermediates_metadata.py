"""End-to-end metadata test for ``publish_intermediates`` (Group B).

Verifies the Tier-3 reproducibility wiring documented in
``docs/audit/reproducibility_followup_2026_06_09.md``: a published
intermediates blob carries ``code_sha`` + ``model_id`` at the top
level, and the helper passes ``failure_mode`` through to the D1 row.

We synthesize a minimal intermediates dict mirroring what
``_annotate`` writes on a cost-ceiling abort path (the highest-value
case for the audit trail — failed runs are exactly what an analyst
needs to query later), then drive ``publish_intermediates`` through a
mocked ``D1Client`` to inspect the INSERT call without touching real
D1.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from accessible_surfaceome.agents._support.run_metadata import code_sha
from accessible_surfaceome.cloud.intermediates import publish_intermediates


@pytest.fixture(autouse=True)
def _clear_code_sha_cache() -> None:
    """Reset the ``code_sha`` lru_cache so each test resolves freshly.

    The helper memoizes for the process lifetime so a cohort run pins
    one value, but tests want a fresh resolve per env-var setup.
    """
    code_sha.cache_clear()


def _synthetic_intermediates() -> dict[str, Any]:
    """Build a synthetic intermediates dict shaped like the orchestrator's
    cost-ceiling-abort early-return path (item 6 in the followup spec).

    Captures the post-PTS state with timing baked in — same shape
    ``pts_only_intermediates`` carries when ``MAX_PTS_COST_USD`` trips.
    """
    return {
        "plan_trim_select": {
            "a1": {"n_claims": 12, "claims": []},
            "a2": {"n_claims": 8, "claims": []},
        },
        "bundle": {"hgnc_symbol": "FAKEGENE", "uniprot_acc": "P00000"},
        "cost_total_usd": 5.42,
        "cost_per_pipeline": {
            "plan_trim_select": 5.42,
            "builders": 0.0,
            "synthesizer": 0.0,
        },
        "timing": [
            {
                "step_name": "plan_trim_select_dual",
                "phase": "pts",
                "elapsed_s": 12.5,
            },
        ],
    }


def test_publish_intermediates_stamps_code_sha_and_model_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End-to-end: ``code_sha`` + ``model_id`` are baked into the blob.

    The wave-2 contract says every published row carries these two
    keys at the top level of ``intermediates_json``. We mock D1Client
    so the INSERT goes through but no network round-trip happens; the
    blob the INSERT carries must contain both fields populated.

    The orchestrator's ``AGENT_MODEL`` constant is the source of truth
    for ``model_id`` (it's the bare alias the caller passes to
    ``messages.create``; the resolved dated snapshot lives on the
    per-call ``UsageRecord.api_model``).
    """
    monkeypatch.setenv(
        "CODE_SHA", "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef"
    )
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "fake-account")
    monkeypatch.setenv(
        "CLOUDFLARE_D1_SURFACEOME_AGENTS_ID", "fake-database"
    )
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "fake-token")

    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    with patch(
        "accessible_surfaceome.cloud.intermediates.D1Client",
        return_value=mock_client,
    ):
        result = publish_intermediates(
            gene_symbol="FAKEGENE",
            intermediates=_synthetic_intermediates(),
            schema_version="2.99.0-test",
            record_valid=False,
            cohort_run_id="test-cohort-001",
            failure_mode="cost_ceiling_pts",
        )

    assert result.pushed is True
    assert result.skipped_reason is None

    # The INSERT call should have been issued once; pull its args.
    assert mock_client.query.call_count == 1
    sql, params = mock_client.query.call_args[0]
    assert "INSERT INTO agent_run_intermediates" in sql
    # Columns ordered (gene, schema_version, prompt_corpus, created_at,
    # record_valid, intermediates_bytes, intermediates_json, cohort_run_id,
    # code_sha, failure_mode).
    assert "code_sha" in sql
    assert "failure_mode" in sql

    # The blob (intermediates_json) is params[6] and must carry the
    # stamped top-level keys.
    blob = json.loads(params[6])
    assert blob["code_sha"] == "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef"
    assert blob["model_id"] == "claude-sonnet-4-6"
    # timing list survived round-trip (item 8).
    assert isinstance(blob.get("timing"), list)
    assert blob["timing"][0]["step_name"] == "plan_trim_select_dual"

    # The denormalized columns (code_sha at params[8], failure_mode at
    # params[9]) must match what the blob carries.
    assert params[8] == "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef"
    assert params[9] == "cost_ceiling_pts"


def test_publish_intermediates_failure_mode_none_back_compat(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``failure_mode=None`` falls through to a NULL column.

    Back-compat: a legacy caller that doesn't thread the failure-mode
    arg keeps working — the column is nullable and the helper accepts
    ``None`` rather than synthesizing a value.
    """
    monkeypatch.setenv(
        "CODE_SHA", "cafebabecafebabecafebabecafebabecafebabe"
    )
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "fake-account")
    monkeypatch.setenv(
        "CLOUDFLARE_D1_SURFACEOME_AGENTS_ID", "fake-database"
    )
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "fake-token")

    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    with patch(
        "accessible_surfaceome.cloud.intermediates.D1Client",
        return_value=mock_client,
    ):
        publish_intermediates(
            gene_symbol="FAKEGENE2",
            intermediates=_synthetic_intermediates(),
            schema_version="2.99.0-test",
            record_valid=True,
            # No failure_mode kwarg — default None.
        )

    assert mock_client.query.call_count == 1
    _sql, params = mock_client.query.call_args[0]
    # failure_mode column param is the last positional (index 9).
    assert params[9] is None
    # code_sha still stamped though (no opt-out for that).
    blob = json.loads(params[6])
    assert blob["code_sha"] == "cafebabecafebabecafebabecafebabecafebabe"


def test_publish_intermediates_does_not_mutate_caller_dict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``intermediates`` arg stays unchanged after the call.

    The helper uses the ``{**intermediates, ...}`` spread to build the
    blob — the caller's dict must NOT pick up ``code_sha`` /
    ``model_id`` keys. Mutation would leak Tier-3 metadata into any
    in-memory blob the caller keeps around for other consumers (the
    ``.runs/*.intermediates.json`` writer is the typical example).
    """
    monkeypatch.setenv("CODE_SHA", "0" * 40)
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "fake-account")
    monkeypatch.setenv(
        "CLOUDFLARE_D1_SURFACEOME_AGENTS_ID", "fake-database"
    )
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "fake-token")

    original = _synthetic_intermediates()
    snapshot = json.dumps(original, sort_keys=True)

    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    with patch(
        "accessible_surfaceome.cloud.intermediates.D1Client",
        return_value=mock_client,
    ):
        publish_intermediates(
            gene_symbol="FAKEGENE3",
            intermediates=original,
            schema_version="2.99.0-test",
            record_valid=True,
        )

    # Caller's dict must be byte-identical to the snapshot taken before
    # the call.
    assert json.dumps(original, sort_keys=True) == snapshot
    assert "code_sha" not in original
    assert "model_id" not in original
