"""``scripts/cloud/sweep_record_history.py``: dry-run, token guard, abort streak.

Loaded via ``importlib.util.spec_from_file_location`` (the house pattern for
testing a standalone ``scripts/`` entry point — see
``tests/test_deep_block_rollups.py``) since it isn't part of the installed
package. Its ``from accessible_surfaceome... import ...`` statements still
resolve through the real package, so classes like ``ArchiveError`` imported
here directly are the identical objects the script module raises/catches.
"""

from __future__ import annotations

import importlib.util
from collections import Counter
from collections.abc import Callable
from pathlib import Path

import httpx
import pytest

from accessible_surfaceome.cloud.record_history.store import ArchiveError

_SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "cloud"
    / "sweep_record_history.py"
)
_spec = importlib.util.spec_from_file_location("sweep_record_history", _SCRIPT)
assert _spec and _spec.loader
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)


class _FakeStore:
    def __enter__(self) -> "_FakeStore":
        return self

    def __exit__(self, *_exc: object) -> None:
        return None


class _FakeCloudRevisionStore:
    @classmethod
    def from_env(cls) -> _FakeStore:
        return _FakeStore()


def test_dry_run_does_not_call_archive_gene(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_mod, "load_env", lambda: None)
    monkeypatch.setattr(_mod, "annotated_genes", lambda http, token: ["EGFR", "CD63"])

    def _boom(*_a: object, **_kw: object) -> None:
        raise AssertionError("archive_gene must not be called during a dry-run")

    monkeypatch.setattr(_mod, "archive_gene", _boom)

    counts = _mod.sweep(None, execute=False, workers=2)

    assert counts == Counter()


def test_dry_run_works_without_a_token(monkeypatch: pytest.MonkeyPatch) -> None:
    # /v1/genes is public — the dry-run listing must not require
    # ARCHIVE_BYPASS_TOKEN to be set.
    monkeypatch.delenv("ARCHIVE_BYPASS_TOKEN", raising=False)
    monkeypatch.setattr(_mod, "load_env", lambda: None)
    seen_tokens: list[str] = []

    def _fake_annotated_genes(http: object, token: str) -> list[str]:
        seen_tokens.append(token)
        return ["EGFR"]

    monkeypatch.setattr(_mod, "annotated_genes", _fake_annotated_genes)
    monkeypatch.setattr(
        _mod, "archive_gene", lambda *a, **kw: (_ for _ in ()).throw(AssertionError())
    )

    counts = _mod.sweep(None, execute=False, workers=1)

    assert counts == Counter()
    assert seen_tokens == [""]


def test_execute_without_token_exits_nonzero(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ARCHIVE_BYPASS_TOKEN", raising=False)
    monkeypatch.setattr(_mod, "load_env", lambda: None)
    monkeypatch.setattr(
        _mod,
        "annotated_genes",
        lambda *a, **kw: (_ for _ in ()).throw(AssertionError()),
    )
    monkeypatch.setattr(
        _mod, "archive_gene", lambda *a, **kw: (_ for _ in ()).throw(AssertionError())
    )

    with pytest.raises(SystemExit) as exc_info:
        _mod.sweep(["EGFR"], execute=True, workers=2)

    assert exc_info.value.code != 0


@pytest.mark.parametrize(
    "make_error",
    [
        lambda symbol: ArchiveError(f"bad bypass token for {symbol}"),
        lambda symbol: httpx.ConnectError(f"connection refused for {symbol}"),
    ],
    ids=["archive_error", "non_archive_error__httpx_connect_error"],
)
def test_aborts_after_n_consecutive_failures_of_any_kind(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    make_error: Callable[[str], Exception],
) -> None:
    # The guard must trip on ANY exception type — ArchiveError (a bad
    # bypass token) and, just as importantly, something like
    # httpx.ConnectError (the Worker itself is down/unreachable) or a
    # D1Error (public D1 down). It's the systemic-failure signal, not the
    # exception class, that matters.
    genes = [f"GENE{i}" for i in range(20)]
    calls: list[str] = []

    def _fake_archive_gene(
        symbol: str, *, source: str, http: object, store: object, token: str
    ) -> None:
        calls.append(symbol)
        raise make_error(symbol)

    monkeypatch.setenv("ARCHIVE_BYPASS_TOKEN", "tok")
    monkeypatch.setattr(_mod, "load_env", lambda: None)
    monkeypatch.setattr(_mod, "annotated_genes", lambda http, token: list(genes))
    monkeypatch.setattr(_mod, "archive_gene", _fake_archive_gene)
    monkeypatch.setattr(_mod, "CloudRevisionStore", _FakeCloudRevisionStore)
    monkeypatch.setattr(_mod, "purge_paths", lambda *a, **kw: None)

    # workers=1: strictly sequential single-worker execution makes the
    # guard's trip-then-skip transition land inside the SAME thread that
    # runs the very next task, so the call count below is exact rather than
    # a race against the orchestrating thread's own bookkeeping.
    counts = _mod.sweep(None, execute=True, workers=1)

    n = _mod.ABORT_AFTER_N_CONSECUTIVE_FAILURES
    assert len(calls) == n
    # Every skipped-after-abort gene is folded into "failed" too (not just
    # the n real failures that tripped the guard), so the aborted sweep is
    # explicitly a failure end to end.
    assert counts["failed"] == len(genes)
    assert counts["skipped_after_abort"] == len(genes) - n
    assert "ABORTING" in capsys.readouterr().out


def test_annotated_genes_sends_bypass_header_only_when_token_set() -> None:
    seen_headers: list[httpx.Headers] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_headers.append(request.headers)
        return httpx.Response(
            200,
            json={"genes": [{"gene_symbol": "EGFR"}, {"gene_symbol": "CD63"}]},
        )

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as http:
        genes = _mod.annotated_genes(http, "")
        assert genes == ["EGFR", "CD63"]
        assert _mod.BYPASS_HEADER not in seen_headers[-1]

        genes = _mod.annotated_genes(http, "t")
        assert genes == ["EGFR", "CD63"]
        assert seen_headers[-1][_mod.BYPASS_HEADER] == "t"
