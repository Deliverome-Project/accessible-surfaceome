"""``scripts/release/cut_data_release.py``: version guardrails + dry-run.

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
from pathlib import Path

import pytest

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


def test_dry_run_makes_no_d1_calls(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(_mod, "load_env", lambda: None)
    monkeypatch.setattr(_mod, "sweep", _boom)
    monkeypatch.setattr(_mod.D1Client, "public", classmethod(lambda cls: _boom()))
    monkeypatch.setattr(_mod, "purge_paths", _boom)
    monkeypatch.setattr(
        sys,
        "argv",
        ["cut_data_release.py", "--version", _REAL_PYPROJECT_VERSION],
    )

    _mod.main()

    out = capsys.readouterr().out
    assert "[dry-run]" in out
    assert _REAL_PYPROJECT_VERSION in out
