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
import sys
from collections import Counter
from collections.abc import Callable
from pathlib import Path

import httpx
import pytest

from accessible_surfaceome.cloud.record_history.archive import Served
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

    def prefetch_latest(self) -> None:
        return None


class _FakeCloudRevisionStore:
    require_s3_seen: list[bool] = []

    @classmethod
    def from_env(cls, *, require_s3: bool = False) -> _FakeStore:
        cls.require_s3_seen.append(require_s3)
        return _FakeStore()


def test_dry_run_does_not_call_archive_gene(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_mod, "load_env", lambda: None)
    monkeypatch.setattr(
        _mod, "annotated_genes", lambda http, token, base=None: ["EGFR", "CD63"]
    )

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

    def _fake_annotated_genes(
        http: object, token: str, base: str | None = None
    ) -> list[str]:
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


def test_r2_s3_client_failure_exits_before_any_archiving(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The eager, main-thread-only build check: a broken/missing S3 client
    must exit loudly before the pool (and CloudRevisionStore) is even
    constructed, let alone before any gene is archived — never a silent
    per-worker REST fallback."""
    monkeypatch.setenv("ARCHIVE_BYPASS_TOKEN", "tok")
    monkeypatch.setattr(_mod, "load_env", lambda: None)
    monkeypatch.setattr(
        _mod, "annotated_genes", lambda http, token, base=None: ["EGFR"]
    )

    def _fail_r2_s3_client() -> None:
        raise _mod.R2S3CredentialError("no token")

    monkeypatch.setattr(_mod, "r2_s3_client", _fail_r2_s3_client)
    monkeypatch.setattr(
        _mod,
        "CloudRevisionStore",
        type(
            "Boom",
            (),
            {
                "from_env": classmethod(
                    lambda cls, **kw: (_ for _ in ()).throw(
                        AssertionError("CloudRevisionStore.from_env must not be reached")
                    )
                )
            },
        ),
    )
    monkeypatch.setattr(
        _mod, "archive_gene", lambda *a, **kw: (_ for _ in ()).throw(AssertionError())
    )

    with pytest.raises(SystemExit) as exc_info:
        _mod.sweep(None, execute=True, workers=1)

    assert exc_info.value.code == 1


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
    monkeypatch.setattr(
        _mod, "annotated_genes", lambda http, token, base=None: list(genes)
    )
    monkeypatch.setattr(_mod, "archive_gene", _fake_archive_gene)
    monkeypatch.setattr(_mod, "r2_s3_client", lambda: object())
    _FakeCloudRevisionStore.require_s3_seen = []
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
    # The sweep constructs its store with require_s3=True — no silent REST
    # fallback at cohort scale.
    assert _FakeCloudRevisionStore.require_s3_seen == [True]


def _served(symbol: str, value: int) -> Served:
    return Served(
        gene_symbol=symbol,
        record_bytes=b"{}",
        record={"gene": {"hgnc_symbol": symbol}, "value": value},
        evidence_bytes=None,
        evidence=None,
        md_bytes=None,
    )


def test_check_stability_all_stable_returns_empty(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        _mod,
        "fetch_served",
        lambda symbol, *, http, token, base=None: _served(symbol, 1),
    )

    with httpx.Client() as http:
        unstable = _mod.check_stability(
            ["EGFR", "CD63"], sample=50, seed=0, http=http, token="tok", workers=1
        )

    assert unstable == {}
    assert "UNSTABLE" not in capsys.readouterr().out


def test_check_stability_names_the_gene_that_flips(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls: dict[str, int] = {}

    def _fake_fetch_served(
        symbol: str, *, http: object, token: str, base: str | None = None
    ) -> Served:
        calls[symbol] = calls.get(symbol, 0) + 1
        # CD63's second fetch differs from its first; EGFR is stable.
        value = calls[symbol] if symbol == "CD63" else 1
        return _served(symbol, value)

    monkeypatch.setattr(_mod, "fetch_served", _fake_fetch_served)

    with httpx.Client() as http:
        unstable = _mod.check_stability(
            ["EGFR", "CD63"], sample=50, seed=0, http=http, token="tok", workers=1
        )

    assert unstable == {"CD63": ["record"]}
    assert "UNSTABLE CD63: record" in capsys.readouterr().out


def test_check_stability_reports_degraded_gene_as_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A gene whose served response carries X-Surfaceome-Degraded makes
    ``fetch_served`` raise ``ArchiveError`` (see
    ``archive._reject_degraded``); ``_check_gene_stability`` doesn't catch
    that itself, so it must surface through ``check_stability`` as an
    ``"error"`` entry — same posture as any other fetch failure — rather
    than being silently compared/diffed."""

    def _fake_fetch_served(
        symbol: str, *, http: object, token: str, base: str | None = None
    ) -> Served:
        if symbol == "S100A7A":
            raise ArchiveError(
                "degraded response for S100A7A (topology_public_canonical) — "
                "not archiving; retry later"
            )
        return _served(symbol, 1)

    monkeypatch.setattr(_mod, "fetch_served", _fake_fetch_served)

    with httpx.Client() as http:
        unstable = _mod.check_stability(
            ["EGFR", "S100A7A"], sample=50, seed=0, http=http, token="tok", workers=1
        )

    assert unstable == {"S100A7A": ["error"]}
    assert "ERROR S100A7A: degraded response for S100A7A" in capsys.readouterr().out


def test_check_stability_requires_a_token() -> None:
    with httpx.Client() as http:
        with pytest.raises(SystemExit) as exc_info:
            _mod.check_stability(
                None, sample=50, seed=0, http=http, token="", workers=1
            )
    assert exc_info.value.code == 1


def test_check_stability_never_touches_the_store(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Only fetch_served (a GET) may be called — no store/R2/D1 write path.
    monkeypatch.setattr(
        _mod, "CloudRevisionStore", lambda: (_ for _ in ()).throw(AssertionError())
    )
    monkeypatch.setattr(
        _mod, "purge_paths", lambda *a, **kw: (_ for _ in ()).throw(AssertionError())
    )
    monkeypatch.setattr(
        _mod,
        "fetch_served",
        lambda symbol, *, http, token, base=None: _served(symbol, 1),
    )

    with httpx.Client() as http:
        unstable = _mod.check_stability(
            ["EGFR"], sample=50, seed=0, http=http, token="tok", workers=1
        )

    assert unstable == {}


def test_check_stability_sample_is_seeded_and_reproducible(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    all_genes = [f"GENE{i}" for i in range(20)]
    monkeypatch.setattr(
        _mod, "annotated_genes", lambda http, token, base=None: list(all_genes)
    )
    seen: list[str] = []
    monkeypatch.setattr(
        _mod,
        "fetch_served",
        lambda symbol, *, http, token, base=None: (
            seen.append(symbol),
            _served(symbol, 1),
        )[1],
    )

    with httpx.Client() as http:
        _mod.check_stability(None, sample=5, seed=42, http=http, token="tok", workers=1)
    first = sorted(set(seen))
    seen.clear()
    with httpx.Client() as http:
        _mod.check_stability(None, sample=5, seed=42, http=http, token="tok", workers=1)
    second = sorted(set(seen))

    assert first == second
    assert len(first) == 5


def test_main_check_stability_honours_genes_and_exits_nonzero_when_unstable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARCHIVE_BYPASS_TOKEN", "tok")
    monkeypatch.setattr(_mod, "load_env", lambda: None)
    monkeypatch.setattr(
        sys, "argv", ["sweep_record_history.py", "--check-stability", "--genes", "EGFR"]
    )
    monkeypatch.setattr(
        _mod,
        "annotated_genes",
        lambda *a, **kw: (_ for _ in ()).throw(
            AssertionError("--genes must skip the listing")
        ),
    )
    calls = {"n": 0}

    def _fake_fetch_served(
        symbol: str, *, http: object, token: str, base: str | None = None
    ) -> Served:
        calls["n"] += 1
        return _served(symbol, calls["n"])  # differs across the two fetches

    monkeypatch.setattr(_mod, "fetch_served", _fake_fetch_served)

    with pytest.raises(SystemExit) as exc_info:
        _mod.main()

    assert exc_info.value.code == 1


def test_main_check_stability_exits_zero_when_stable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARCHIVE_BYPASS_TOKEN", "tok")
    monkeypatch.setattr(_mod, "load_env", lambda: None)
    monkeypatch.setattr(
        sys, "argv", ["sweep_record_history.py", "--check-stability", "--genes", "EGFR"]
    )
    monkeypatch.setattr(
        _mod,
        "fetch_served",
        lambda symbol, *, http, token, base=None: _served(symbol, 1),
    )

    with pytest.raises(SystemExit) as exc_info:
        _mod.main()

    assert exc_info.value.code == 0


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


def test_base_only_allowed_with_check_stability(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        sys, "argv", ["sweep", "--base", "http://127.0.0.1:1", "--execute"]
    )
    with pytest.raises(SystemExit) as exc:
        _mod.main()
    assert exc.value.code == 2
