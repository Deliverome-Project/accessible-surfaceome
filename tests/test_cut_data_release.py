"""``scripts/release/cut_data_release.py``: version guardrails, the
existing-release / --resume gate, and the failure paths that must not
touch D1 or re-cut an already-cut release.

Loaded via ``importlib.util.spec_from_file_location`` (the house pattern for
testing a standalone ``scripts/`` entry point — see
``tests/test_sweep_record_history.py``). Its
``from accessible_surfaceome... import ...`` statements still resolve
through the real package, and the script's own
``from sweep_record_history import sweep`` resolves relative to
``scripts/cloud`` (which the script itself inserts onto ``sys.path``).
"""

from __future__ import annotations

import importlib.util
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import httpx
import pytest

from accessible_surfaceome.cloud.record_history.zenodo import ZenodoDraftError

_SCRIPT = (
    Path(__file__).resolve().parents[1] / "scripts" / "release" / "cut_data_release.py"
)
_spec = importlib.util.spec_from_file_location("cut_data_release", _SCRIPT)
assert _spec and _spec.loader
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

_REAL_PYPROJECT_VERSION = _mod.pyproject_version()


def _boom(*_a: object, **_kw: object) -> None:
    raise AssertionError("must not be called on this code path")


class _FakeD1:
    """Stands in for ``D1Client.public()`` as a context manager."""

    def __init__(self, *, release_rows: list[dict[str, Any]] | None = None) -> None:
        self.release_rows = release_rows or []
        self.queries: list[tuple[str, list[Any]]] = []

    def __enter__(self) -> "_FakeD1":
        return self

    def __exit__(self, *_exc: object) -> None:
        return None

    def query(self, sql: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
        self.queries.append((sql, params or []))
        if "FROM data_release WHERE version" in sql:
            return self.release_rows
        return []


def _patch_common(
    monkeypatch: pytest.MonkeyPatch,
    *,
    d1: _FakeD1,
    sweep_result: Counter[str] | None = None,
) -> None:
    monkeypatch.setattr(_mod, "load_env", lambda: None)
    monkeypatch.setattr(_mod.D1Client, "public", classmethod(lambda cls: d1))
    monkeypatch.setattr(_mod, "purge_paths", lambda *a, **kw: None)
    # R2Config.from_env() is built unconditionally before get_blob/export in
    # both the fresh and --resume paths, even though these tests fake out
    # the actual R2 calls (export_release / get_blob) — it just needs any
    # non-empty values to construct.
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "test-account")
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "test-token")
    if sweep_result is not None:
        monkeypatch.setattr(_mod, "sweep", lambda *a, **kw: sweep_result)
    else:
        monkeypatch.setattr(_mod, "sweep", _boom)


def test_bad_version_string_exits_nonzero(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_mod, "load_env", lambda: None)
    monkeypatch.setattr(sys, "argv", ["cut_data_release.py", "--version", "1.2"])

    with pytest.raises(SystemExit, match="--version must look like"):
        _mod.main()


def test_version_mismatch_vs_pyproject_exits_nonzero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mismatched = "9.9.9"
    assert mismatched != _REAL_PYPROJECT_VERSION
    monkeypatch.setattr(_mod, "load_env", lambda: None)
    monkeypatch.setattr(sys, "argv", ["cut_data_release.py", "--version", mismatched])

    with pytest.raises(SystemExit, match="pyproject.toml says"):
        _mod.main()


def test_existing_release_without_resume_exits_before_sweep(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    d1 = _FakeD1(release_rows=[{"zenodo_version_doi": None}])
    _patch_common(monkeypatch, d1=d1)  # sweep -> _boom: must not be called
    monkeypatch.setattr(
        sys,
        "argv",
        ["cut_data_release.py", "--version", _REAL_PYPROJECT_VERSION, "--execute"],
    )

    with pytest.raises(SystemExit, match="already exists"):
        _mod.main()


def test_resume_on_published_release_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    d1 = _FakeD1(release_rows=[{"zenodo_version_doi": "10.5281/zenodo.123"}])
    _patch_common(monkeypatch, d1=d1)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "cut_data_release.py",
            "--version",
            _REAL_PYPROJECT_VERSION,
            "--resume",
            "--execute",
        ],
    )

    with pytest.raises(SystemExit, match="already published"):
        _mod.main()


def test_resume_skips_sweep_and_create_release_goes_to_export_and_draft(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    d1 = _FakeD1(release_rows=[{"zenodo_version_doi": None}])
    _patch_common(monkeypatch, d1=d1)
    monkeypatch.setattr(
        _mod.rel,
        "create_release",
        lambda *a, **kw: (_ for _ in ()).throw(AssertionError),
    )
    monkeypatch.setattr(
        _mod.rel,
        "latest_members",
        lambda *a, **kw: (_ for _ in ()).throw(AssertionError),
    )
    exported = tmp_path / "deep_dives_x.tar.gz"
    exported.write_bytes(b"tarball")
    export_calls: list[Any] = []

    def fake_export_release(
        d1_arg: object, version: str, out_dir: Path, *, get_blob: Any
    ) -> Path:
        export_calls.append((version, out_dir))
        return exported

    monkeypatch.setattr(_mod.rel, "export_release", fake_export_release)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "cut_data_release.py",
            "--version",
            _REAL_PYPROJECT_VERSION,
            "--resume",
            "--execute",
            "--out-dir",
            str(tmp_path),
        ],
    )
    # No ZENODO_TOKEN in the environment -> stop right after export, which is
    # enough to prove sweep/create_release were skipped and export ran.
    monkeypatch.delenv("ZENODO_TOKEN", raising=False)

    _mod.main()

    assert len(export_calls) == 1
    assert export_calls[0][0] == _REAL_PYPROJECT_VERSION


def test_sweep_failures_exit_before_any_d1_write(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    d1 = _FakeD1(release_rows=[])
    _patch_common(monkeypatch, d1=d1, sweep_result=Counter({"failed": 3}))
    monkeypatch.setattr(
        _mod.rel,
        "create_release",
        lambda *a, **kw: (_ for _ in ()).throw(AssertionError),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["cut_data_release.py", "--version", _REAL_PYPROJECT_VERSION, "--execute"],
    )

    # If create_release had been reached, the monkeypatch above would have
    # raised AssertionError instead of the sweep-failure SystemExit below.
    with pytest.raises(SystemExit, match="sweep had 3 failures"):
        _mod.main()


def test_zenodo_draft_error_exits_1_and_create_release_called_once(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    d1 = _FakeD1(release_rows=[])
    _patch_common(monkeypatch, d1=d1, sweep_result=Counter())
    create_release_calls: list[Any] = []

    def fake_create_release(d1_arg: object, **kwargs: Any) -> None:
        create_release_calls.append(kwargs)

    monkeypatch.setattr(_mod.rel, "create_release", fake_create_release)
    monkeypatch.setattr(_mod.rel, "latest_members", lambda *a, **kw: [("EGFR", 1)])
    exported = tmp_path / "deep_dives_x.tar.gz"
    exported.write_bytes(b"tarball")
    monkeypatch.setattr(_mod.rel, "export_release", lambda *a, **kw: exported)
    monkeypatch.setenv("ZENODO_TOKEN", "tok")

    def fake_create_draft_version(**_kw: Any) -> str:
        raise ZenodoDraftError("draft already exists")

    monkeypatch.setattr(_mod, "create_draft_version", fake_create_draft_version)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "cut_data_release.py",
            "--version",
            _REAL_PYPROJECT_VERSION,
            "--execute",
            "--out-dir",
            str(tmp_path),
        ],
    )

    with pytest.raises(SystemExit) as exc_info:
        _mod.main()

    assert exc_info.value.code == 1
    assert len(create_release_calls) == 1


def test_zenodo_http_status_error_exits_1_with_resume_hint(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    d1 = _FakeD1(release_rows=[])
    _patch_common(monkeypatch, d1=d1, sweep_result=Counter())
    monkeypatch.setattr(_mod.rel, "create_release", lambda *a, **kw: None)
    monkeypatch.setattr(_mod.rel, "latest_members", lambda *a, **kw: [("EGFR", 1)])
    exported = tmp_path / "deep_dives_x.tar.gz"
    exported.write_bytes(b"tarball")
    monkeypatch.setattr(_mod.rel, "export_release", lambda *a, **kw: exported)
    monkeypatch.setenv("ZENODO_TOKEN", "tok")

    def fake_create_draft_version(**_kw: Any) -> str:
        request = httpx.Request("PUT", "https://zenodo.test/x")
        response = httpx.Response(502, request=request)
        raise httpx.HTTPStatusError("boom", request=request, response=response)

    monkeypatch.setattr(_mod, "create_draft_version", fake_create_draft_version)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "cut_data_release.py",
            "--version",
            _REAL_PYPROJECT_VERSION,
            "--execute",
            "--out-dir",
            str(tmp_path),
        ],
    )

    with pytest.raises(SystemExit) as exc_info:
        _mod.main()

    assert exc_info.value.code == 1
    assert "--resume" in capsys.readouterr().out


def test_nondefault_zenodo_api_without_resume_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(_mod, "load_env", lambda: None)
    monkeypatch.setattr(_mod.D1Client, "public", classmethod(lambda cls: _boom()))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "cut_data_release.py",
            "--version",
            _REAL_PYPROJECT_VERSION,
            "--zenodo-api",
            "https://sandbox.zenodo.org/api",
        ],
    )

    with pytest.raises(SystemExit, match="requires --resume"):
        _mod.main()
