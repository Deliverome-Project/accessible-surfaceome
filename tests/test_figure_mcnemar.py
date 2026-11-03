"""Guard: every McNemar p-value the manuscript reports has code behind it.

The Supplementary Figure 11 legend reported exact McNemar p-values for the
deep dive against triage, and the Results called two model comparisons "not
significantly" different, but no script computed either. The tests live in the
figure generators now; this pins them to the committed benchmark data so a
data refresh that moves a p-value fails here rather than leaving the legend
stale.

Each figure has a canonical generator and a standalone gist mirror with its
own inlined copy of the test, so the two are checked against each other too.
"""
from __future__ import annotations

import csv
import importlib.util
from pathlib import Path

import pandas as pd
import pytest

from accessible_surfaceome.audit.paired_tests import exact_mcnemar

ROOT = Path(__file__).resolve().parents[1]
DEEP_TSV = ROOT / "data/processed/figures/deep_dive_vs_sonnet_benchmark.tsv"
BENCH_TSV = ROOT / "data/processed/figures/db_correctness_overall.tsv"


def _load(path: str):
    spec = importlib.util.spec_from_file_location(Path(path).stem, ROOT / path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_exact_mcnemar_known_values() -> None:
    # No discordant pairs: nothing to test.
    assert exact_mcnemar([True, False], [True, False]) == (0, 0, 1.0)
    # 3 vs 1 discordant: 2 * P(X <= 1 | n=4, p=.5) = 2 * 5/16.
    a = [True, True, True, False, True]
    b = [False, False, False, True, True]
    assert exact_mcnemar(a, b) == (3, 1, pytest.approx(0.625))
    # 0 vs 2 discordant: 2 * 1/4.
    assert exact_mcnemar([False, False], [True, True])[2] == pytest.approx(0.5)
    # Symmetric in its arguments.
    assert exact_mcnemar(b, a)[2] == exact_mcnemar(a, b)[2]
    with pytest.raises(ValueError):
        exact_mcnemar([True], [True, False])


def test_deep_dive_vs_triage_matches_the_legend() -> None:
    """Supplementary Figure 11: 'overall p = 1.0; contextual p = 0.63;
    not-surface p = 0.50'."""
    mod = _load("scripts/figures/deep_dive_vs_sonnet_benchmark.py")
    with open(DEEP_TSV) as f:
        rows = list(csv.DictReader(f, delimiter="\t"))
    got = {r["subset"]: r for r in mod.mcnemar_rows(rows)}
    assert got["overall"]["n"] == 113
    assert got["overall"]["p"] == pytest.approx(1.0)
    assert got["yes"]["p"] == pytest.approx(1.0)
    assert round(got["contextual"]["p"], 2) == 0.62  # 0.625, printed as 0.63
    assert got["no"]["p"] == pytest.approx(0.5)


def test_model_comparisons_are_not_significant() -> None:
    """Results: web search and pre-fetched abstracts 'did not significantly
    increase accuracy', and Sonnet 5 was 'not significantly' worse."""
    mod = _load("scripts/figures/db_correctness_overall.py")
    rows = mod.mcnemar_rows(pd.read_csv(BENCH_TSV, sep="\t"))
    assert len(rows) == len(mod.MCNEMAR_PAIRS)
    for r in rows:
        assert r["n"] == 147, r
        assert r["p"] > 0.05, r
    by = {(r["a"], r["b"]): r["p"] for r in rows}
    assert by[("claude-sonnet-4-6/ncbi", "claude-sonnet-5/ncbi")] == pytest.approx(0.289, abs=1e-3)


@pytest.mark.parametrize(
    ("canonical", "mirror", "data"),
    [
        ("scripts/figures/deep_dive_vs_sonnet_benchmark.py",
         "data/analysis/figures/make_deep_dive_vs_sonnet_benchmark.py", DEEP_TSV),
        ("scripts/figures/db_correctness_overall.py",
         "data/analysis/figures/make_db_correctness_overall.py", BENCH_TSV),
    ],
)
def test_gist_mirror_computes_the_same_test(canonical: str, mirror: str, data: Path) -> None:
    if data == DEEP_TSV:
        with open(data) as f:
            arg = list(csv.DictReader(f, delimiter="\t"))
    else:
        arg = pd.read_csv(data, sep="\t")
    assert _load(mirror).mcnemar_rows(arg) == _load(canonical).mcnemar_rows(arg)
