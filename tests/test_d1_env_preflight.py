"""Pre-flight + REQUIRE_D1 enforcement for the public-D1 credential check.

The June-2026 regression: 6 deep-dive records shipped with
``triage_signal=unknown`` even though ``triage_run_public`` had Sonnet
verdicts for every gene under priority run_ids. Root cause: the
generating worktree's ``.env`` was symlinked but ``CLOUDFLARE_API_TOKEN``
was empty — so ``_load_triage_record_from_d1`` returned ``None`` silently
(every env-check ran on whitespace-stripped empties and the `if not (...):`
branch returned None) and ``publish_record`` happily shipped the
field-incomplete record.

These tests pin three contracts:

1. All-missing env → ``None``, info log (legitimate fresh-checkout).
2. Partial env → ``None``, **warning** log naming missing vars
   (this is the bug shape we have to surface).
3. ``ACCESSIBLE_SURFACEOME_REQUIRE_D1=1`` → ``D1AuthError`` for any
   miss-or-partial state (production-sweep posture).

Plus a sync check on ``_TRIAGE_COHERENCE_PRIORITY`` vs.
``_D1_TRIAGE_PRIORITY`` so the post-write coherence guard and the
runtime D1 fallback never disagree on which run_ids "count".
"""

from __future__ import annotations

import logging

import pytest

from accessible_surfaceome.cloud.d1_env import (
    REQUIRE_D1_ENV_VAR,
    D1AuthError,
    public_d1_config_or_warn,
)


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Strip every D1 + REQUIRE_D1 var so each test starts from a clean slate.

    Two layers of isolation: (1) ``monkeypatch.delenv`` removes whatever
    the shell / direnv put there; (2) stub ``load_env`` so the helper's
    internal ``.env``-loading call doesn't put the real CLOUDFLARE_*
    values back. Without the stub, ``load_env`` reads ``REPO_ROOT/.env``
    (often symlinked to the developer's secrets) and silently
    repopulates the env behind monkeypatch's back — which used to flake
    these tests when run from a worktree with .env symlinked in.
    """
    for var in (
        "CLOUDFLARE_ACCOUNT_ID",
        "CLOUDFLARE_API_TOKEN",
        "CLOUDFLARE_D1_SURFACEOME_PUBLIC_ID",
        REQUIRE_D1_ENV_VAR,
    ):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(
        "accessible_surfaceome.cloud.d1_env.load_env", lambda: None
    )


def test_all_missing_returns_none_with_info(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="accessible_surfaceome.cloud.d1_env")
    cfg = public_d1_config_or_warn(operation="test_op", symbol="GENE1")
    assert cfg is None
    # Single info-level line; no WARNING.
    info_records = [r for r in caplog.records if r.levelno == logging.INFO]
    warn_records = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert len(info_records) == 1
    assert "no D1 public credentials" in info_records[0].getMessage()
    assert "GENE1" in info_records[0].getMessage()
    assert warn_records == [], (
        "all-missing must be a soft skip (info), not a warning — "
        "this is the legitimate CI / fresh-checkout path"
    )


def test_partial_creds_emits_loud_warning(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """The bug shape: account_id + db_id set, token empty. Silent before
    this guardrail; loud warning now."""
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acct123")
    monkeypatch.setenv("CLOUDFLARE_D1_SURFACEOME_PUBLIC_ID", "db123")
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "")  # empty — the bug shape
    caplog.set_level(logging.WARNING, logger="accessible_surfaceome.cloud.d1_env")
    cfg = public_d1_config_or_warn(operation="triage D1 fallback", symbol="SLC7A5")
    assert cfg is None
    warns = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warns) == 1
    msg = warns[0].getMessage()
    assert "CLOUDFLARE_API_TOKEN" in msg, (
        "warning must name the missing var so the operator can grep for it"
    )
    assert "SLC7A5" in msg, "warning must include the gene symbol for context"
    assert "REQUIRE_D1" in msg or REQUIRE_D1_ENV_VAR in msg, (
        "warning must mention the hard-fail escape hatch"
    )


def test_partial_creds_two_missing_lists_both(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acct123")
    monkeypatch.setenv("CLOUDFLARE_D1_SURFACEOME_PUBLIC_ID", "")
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "")
    caplog.set_level(logging.WARNING, logger="accessible_surfaceome.cloud.d1_env")
    public_d1_config_or_warn(operation="op")
    warns = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warns) == 1
    msg = warns[0].getMessage()
    assert "CLOUDFLARE_API_TOKEN" in msg
    assert "CLOUDFLARE_D1_SURFACEOME_PUBLIC_ID" in msg


def test_all_set_returns_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acct123")
    monkeypatch.setenv("CLOUDFLARE_D1_SURFACEOME_PUBLIC_ID", "db123")
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "tok123")
    cfg = public_d1_config_or_warn(operation="op")
    assert cfg is not None
    assert cfg.account_id == "acct123"
    assert cfg.api_token == "tok123"
    assert cfg.database_id == "db123"


def test_require_d1_raises_on_all_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(REQUIRE_D1_ENV_VAR, "1")
    with pytest.raises(D1AuthError) as ei:
        public_d1_config_or_warn(operation="publish_record", symbol="ABCD1")
    err = ei.value
    assert err.operation == "publish_record"
    assert err.symbol == "ABCD1"
    assert "CLOUDFLARE_ACCOUNT_ID" in err.missing
    assert "CLOUDFLARE_API_TOKEN" in err.missing
    assert "CLOUDFLARE_D1_SURFACEOME_PUBLIC_ID" in err.missing


def test_require_d1_raises_on_partial(monkeypatch: pytest.MonkeyPatch) -> None:
    """Even with two of three set, REQUIRE_D1 means we don't ship a record
    with a silent-fallback triage signal."""
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acct123")
    monkeypatch.setenv("CLOUDFLARE_D1_SURFACEOME_PUBLIC_ID", "db123")
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "")  # bug shape
    monkeypatch.setenv(REQUIRE_D1_ENV_VAR, "1")
    with pytest.raises(D1AuthError) as ei:
        public_d1_config_or_warn(operation="op", symbol="SLC7A5")
    assert ei.value.missing == ["CLOUDFLARE_API_TOKEN"]


@pytest.mark.parametrize("truthy", ["1", "true", "TRUE", "yes", "on", "Yes"])
def test_require_d1_truthy_values(
    truthy: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(REQUIRE_D1_ENV_VAR, truthy)
    with pytest.raises(D1AuthError):
        public_d1_config_or_warn(operation="op")


@pytest.mark.parametrize("falsy", ["0", "false", "no", "off", ""])
def test_require_d1_falsy_values(
    falsy: str,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setenv(REQUIRE_D1_ENV_VAR, falsy)
    caplog.set_level(logging.INFO, logger="accessible_surfaceome.cloud.d1_env")
    cfg = public_d1_config_or_warn(operation="op")
    assert cfg is None  # not raised


def test_whitespace_stripped(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """``"   "`` for a creds env var counts as missing — same shape as
    a shell ``export TOKEN=$EMPTY`` that left whitespace."""
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acct123")
    monkeypatch.setenv("CLOUDFLARE_D1_SURFACEOME_PUBLIC_ID", "db123")
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "   ")
    caplog.set_level(logging.WARNING, logger="accessible_surfaceome.cloud.d1_env")
    cfg = public_d1_config_or_warn(operation="op")
    assert cfg is None
    warns = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warns) == 1
    assert "CLOUDFLARE_API_TOKEN" in warns[0].getMessage()


def test_triage_coherence_priority_in_sync_with_orchestrator() -> None:
    """The post-write coherence guard's run_id list MUST match the runtime
    fallback's list — otherwise the guard would refuse to publish a record
    even when the runtime fallback couldn't have found anything (false
    positive), or pass through a real silent-failure case (false negative).
    """
    from accessible_surfaceome.agents.surfaceome_v1.orchestrator import (
        _D1_TRIAGE_PRIORITY,
    )
    from accessible_surfaceome.cloud.surface_annotation import (
        _TRIAGE_COHERENCE_PRIORITY,
    )

    assert _D1_TRIAGE_PRIORITY == _TRIAGE_COHERENCE_PRIORITY, (
        "post-write triage-coherence guard and runtime D1 fallback "
        "disagree on the priority run_id list — they must stay in lockstep"
    )
