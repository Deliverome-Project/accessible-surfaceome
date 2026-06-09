"""Unit tests for per-run reproducibility metadata helpers.

Verifies the contract documented in
``agents/_support/run_metadata.py``:

* ``code_sha()`` resolves to ``CODE_SHA`` env, then ``GIT_COMMIT`` env,
  then ``git rev-parse HEAD``, then ``"unknown"`` — in that order, and
  never raises.
* ``api_response_metadata()`` extracts ``id`` / ``model`` /
  ``stop_reason`` off an SDK response, and returns an empty dict on any
  malformed input rather than raising.
* ``cohort_temperature()`` defaults to 0.2 and is overridable via the
  ``COHORT_TEMPERATURE`` env var.

The ``code_sha`` helper memoizes its return value via ``lru_cache``, so
every test that depends on a fresh resolution must call
``code_sha.cache_clear()`` first — otherwise the first test that runs
in the suite pins the value for every other test.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest

from accessible_surfaceome.agents._support.run_metadata import (
    api_response_metadata,
    code_sha,
    cohort_temperature,
)


@pytest.fixture(autouse=True)
def _clear_code_sha_cache() -> None:
    """Clear the ``lru_cache`` before each test.

    ``code_sha`` is intentionally cached for the process lifetime (the
    SHA can't change mid-run), but that pin would leak the value from
    the first test into every subsequent one. Tests that depend on a
    specific env-var or subprocess-fallback shape need a fresh resolve.
    """
    code_sha.cache_clear()


# --- code_sha() --------------------------------------------------------


def test_code_sha_prefers_CODE_SHA_env_over_GIT_COMMIT(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When both env vars are set, ``CODE_SHA`` wins."""
    monkeypatch.setenv("CODE_SHA", "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef")
    monkeypatch.setenv("GIT_COMMIT", "cafebabecafebabecafebabecafebabecafebabe")
    assert code_sha() == "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef"


def test_code_sha_falls_back_to_GIT_COMMIT_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When only ``GIT_COMMIT`` is set, it's used (Modal-friendly path)."""
    monkeypatch.delenv("CODE_SHA", raising=False)
    monkeypatch.setenv("GIT_COMMIT", "cafebabecafebabecafebabecafebabecafebabe")
    assert code_sha() == "cafebabecafebabecafebabecafebabecafebabe"


def test_code_sha_truncates_to_40_chars(monkeypatch: pytest.MonkeyPatch) -> None:
    """Defensive truncation — even a malformed long-SHA env var is bounded.

    A full git SHA is 40 hex chars; the helper truncates at 40 so a
    pathological env-var value can't smuggle a giant string into the
    D1 row. (Short SHAs pass through unchanged — they're already
    < 40 chars so the slice is a no-op.)
    """
    monkeypatch.setenv("CODE_SHA", "a" * 80)
    monkeypatch.delenv("GIT_COMMIT", raising=False)
    assert code_sha() == "a" * 40


def test_code_sha_strips_whitespace(monkeypatch: pytest.MonkeyPatch) -> None:
    """Env vars set with trailing newlines (common shell mistake) clean up."""
    monkeypatch.setenv("CODE_SHA", "  deadbeef\n")
    monkeypatch.delenv("GIT_COMMIT", raising=False)
    assert code_sha() == "deadbeef"


def test_code_sha_falls_through_to_git_when_no_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No env vars → ``git rev-parse HEAD`` subprocess.

    We stub the subprocess so the test passes regardless of whether the
    test runner is itself inside a git checkout (CI sandboxes sometimes
    aren't). The real-world path runs the actual subprocess.
    """
    monkeypatch.delenv("CODE_SHA", raising=False)
    monkeypatch.delenv("GIT_COMMIT", raising=False)
    with patch(
        "accessible_surfaceome.agents._support.run_metadata.subprocess.check_output",
        return_value=b"abcd1234abcd1234abcd1234abcd1234abcd1234\n",
    ):
        assert code_sha() == "abcd1234abcd1234abcd1234abcd1234abcd1234"


def test_code_sha_returns_unknown_when_git_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If ``git`` isn't on PATH (Modal image without git), return ``"unknown"``."""
    monkeypatch.delenv("CODE_SHA", raising=False)
    monkeypatch.delenv("GIT_COMMIT", raising=False)
    with patch(
        "accessible_surfaceome.agents._support.run_metadata.subprocess.check_output",
        side_effect=FileNotFoundError("git not found"),
    ):
        assert code_sha() == "unknown"


def test_code_sha_returns_unknown_on_subprocess_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``subprocess`` errors (non-zero exit, etc.) → ``"unknown"``, never raise."""
    import subprocess as _sp

    monkeypatch.delenv("CODE_SHA", raising=False)
    monkeypatch.delenv("GIT_COMMIT", raising=False)
    with patch(
        "accessible_surfaceome.agents._support.run_metadata.subprocess.check_output",
        side_effect=_sp.CalledProcessError(128, ["git", "rev-parse", "HEAD"]),
    ):
        assert code_sha() == "unknown"


# --- api_response_metadata() ------------------------------------------


def test_api_response_metadata_extracts_all_three_fields() -> None:
    """A well-formed SDK response surfaces ``id`` / ``model`` / ``stop_reason``."""
    resp = SimpleNamespace(
        id="anthropic-msg_01ABCDEF",
        model="claude-sonnet-4-6-20251022",
        stop_reason="end_turn",
    )
    assert api_response_metadata(resp) == {
        "api_response_id": "anthropic-msg_01ABCDEF",
        "api_model": "claude-sonnet-4-6-20251022",
        "api_stop_reason": "end_turn",
    }


def test_api_response_metadata_handles_max_tokens_stop() -> None:
    """``stop_reason='max_tokens'`` is the load-bearing failure-mode signal."""
    resp = SimpleNamespace(
        id="anthropic-msg_01XYZ",
        model="claude-sonnet-4-6-20251022",
        stop_reason="max_tokens",
    )
    out = api_response_metadata(resp)
    assert out["api_stop_reason"] == "max_tokens"


def test_api_response_metadata_returns_none_for_missing_attrs() -> None:
    """A response object without the expected attrs returns ``None``s, not raises.

    Some SDK shapes (older versions, mocks in tests) won't have one of
    ``id`` / ``model`` / ``stop_reason``. The helper uses ``getattr(..., None)``
    so each one independently defaults to ``None`` instead of throwing.
    """
    resp = SimpleNamespace()  # no attrs at all
    assert api_response_metadata(resp) == {
        "api_response_id": None,
        "api_model": None,
        "api_stop_reason": None,
    }


def test_api_response_metadata_returns_empty_dict_on_exception() -> None:
    """A malformed object that raises during ``getattr`` returns ``{}``.

    Defensive: we never want a malformed response to crash the hot path.
    Use a class whose ``__getattr__`` raises to force the
    ``except Exception`` branch.
    """

    class _Exploding:
        def __getattr__(self, _name: str) -> Any:  # pragma: no cover - test fixture
            raise RuntimeError("oh no")

    assert api_response_metadata(_Exploding()) == {}


def test_api_response_metadata_with_none() -> None:
    """``None`` response (caught exception path) is the empty dict."""
    # ``getattr(None, "id", None)`` returns ``None`` cleanly, so this is
    # the "no fields" shape, not the "explode" shape.
    assert api_response_metadata(None) == {
        "api_response_id": None,
        "api_model": None,
        "api_stop_reason": None,
    }


# --- cohort_temperature() ---------------------------------------------


def test_cohort_temperature_defaults_to_low_variance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Default 0.2 — the cohort-run "low variance" value."""
    monkeypatch.delenv("COHORT_TEMPERATURE", raising=False)
    assert cohort_temperature() == pytest.approx(0.2)


def test_cohort_temperature_overridable_via_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``COHORT_TEMPERATURE=1.0`` round-trips for SDK-default-behavior probes."""
    monkeypatch.setenv("COHORT_TEMPERATURE", "1.0")
    assert cohort_temperature() == pytest.approx(1.0)


def test_cohort_temperature_returns_float_not_int(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The Anthropic SDK rejects ``int`` for ``temperature``; helper returns ``float``."""
    monkeypatch.setenv("COHORT_TEMPERATURE", "0")
    out = cohort_temperature()
    assert isinstance(out, float)
    assert out == pytest.approx(0.0)
