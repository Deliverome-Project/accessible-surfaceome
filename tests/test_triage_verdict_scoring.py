"""Pin the yes≡contextual equivalence used for triage benchmark scoring.

Per project rule: ``yes`` and ``contextual`` collapse to a single
positive class for accuracy accounting (a tissue/state-restricted
surface hit is operationally the same as a ubiquitous one for
downstream targeting work). Only ``no`` matches ``no`` on the negative
side. The rule lives in TWO places — keep them in lockstep:

* ``scripts/triage_subbench_summary.py::_verdict_match`` — used by the
  dataframe builder, lazy-ensemble, and cascade sweeps.
* ``scripts/triage_subbench_runner.py``'s inline ``correct = …`` block
  — applied live during a run before the JSON gets persisted.

This test pins both implementations against the same truth table so a
future "simplification" back to strict ``==`` is loud, not silent.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


def _load_script_module(name: str):
    """Load a top-level script as a module under a unique name.

    The scripts/ directory is not a package; this avoids polluting the
    actual package import graph while still letting us pull in
    ``_verdict_match`` and the runner's correct-flag logic.
    """
    spec = importlib.util.spec_from_file_location(
        f"_triage_test_{name}", SCRIPTS_DIR / f"{name}.py"
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def summary_mod():
    return _load_script_module("triage_subbench_summary")


# Truth table: (prediction, truth, expected_correct).
# yes/contextual collapse to positive; no is its own class.
_TRUTH_TABLE = [
    # Exact match — always correct.
    ("yes",        "yes",        True),
    ("contextual", "contextual", True),
    ("no",         "no",         True),
    # Cross-positive — both should count as correct (the rule).
    ("yes",        "contextual", True),
    ("contextual", "yes",        True),
    # Positive vs negative — never correct.
    ("yes",        "no",         False),
    ("contextual", "no",         False),
    ("no",         "yes",        False),
    ("no",         "contextual", False),
    # Missing / None — never correct.
    (None,         "yes",        False),
    ("yes",        None,         False),
    (None,         None,         False),
]


@pytest.mark.parametrize("pred,truth,expected", _TRUTH_TABLE)
def test_summary_verdict_match(summary_mod, pred, truth, expected):
    """``_verdict_match`` follows the yes≡contextual rule end-to-end."""
    assert summary_mod._verdict_match(pred, truth) is expected


# The runner script's `correct = …` block is an inline expression, not
# a callable. Re-implement it identically here and assert the same
# truth table — so if someone edits the runner and breaks the rule,
# this test fails alongside the summary test.
def _runner_correct(pred_v: str | None, truth_verdict: str | None) -> bool:
    """Mirror of scripts/triage_subbench_runner.py's `correct` block.

    Edit BOTH places in lockstep when the rule changes. The body must
    stay identical (modulo whitespace) to the source-of-truth.
    """
    _POSITIVE = {"yes", "contextual"}
    return (
        pred_v is not None
        and truth_verdict is not None
        and (
            pred_v == truth_verdict
            or (pred_v in _POSITIVE and truth_verdict in _POSITIVE)
        )
    )


@pytest.mark.parametrize("pred,truth,expected", _TRUTH_TABLE)
def test_runner_correct_mirrors_rule(pred, truth, expected):
    """Runner's inline correct-flag uses the same equivalence."""
    assert _runner_correct(pred, truth) is expected


def test_runner_and_summary_agree(summary_mod):
    """Belt-and-suspenders: both implementations agree on every case."""
    for pred, truth, _ in _TRUTH_TABLE:
        assert summary_mod._verdict_match(pred, truth) == _runner_correct(
            pred, truth
        )


def test_runner_source_uses_positive_equivalence():
    """Guard against a refactor that drops the equivalence from the
    runner. We look for both the positive-set check and the inline
    ``or`` — together they're the rule. If the source ever goes back
    to a bare ``pred_v == truth_verdict``, this test fails."""
    src = (SCRIPTS_DIR / "triage_subbench_runner.py").read_text()
    assert '"yes", "contextual"' in src or "'yes', 'contextual'" in src, (
        "Runner no longer declares the yes/contextual positive set — "
        "did someone revert to strict equality? Update the rule in "
        "both runner + summary, or update this test if the rule has "
        "been intentionally widened."
    )
    assert (
        "in _POSITIVE and truth_verdict in _POSITIVE" in src
        or "in POSITIVE and truth in POSITIVE" in src
    ), (
        "Runner no longer ORs the positive-equivalence check into "
        "`correct`. The yes≡contextual rule has regressed."
    )


def test_summary_source_uses_positive_equivalence(summary_mod):
    """Same guard for the summary module — the rule must remain
    centralized in _verdict_match, not silently expanded into ad-hoc
    `==` checks at the call sites."""
    src = Path(summary_mod.__file__).read_text()
    # The helper is defined.
    assert "def _verdict_match" in src
    # And every chosen-vs-truth comparison routes through it. The two
    # ensemble functions (_lazy_ensemble, _cascade) MUST use
    # _verdict_match, not bare `==`.
    assert 'chosen == truth[g]["ground_truth_verdict"]' not in src, (
        "Found a bare `chosen == truth[...]` comparison — that bypasses "
        "the yes≡contextual rule. Route it through _verdict_match."
    )
