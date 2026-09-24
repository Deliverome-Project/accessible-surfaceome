"""Pin the replicate-collapse rule to the MODE of the reason, not row order.

Two places collapse a benchmark cell's 2–3 replicates into one representative
reason: ``curator_vs_agent_reason._representative_reason`` (Supp. Fig. S3) and
``export_mainbench_to_tsv._collapse_to_majority`` (the published
``mainbench_canonical_v2.tsv``). Both used to settle the verdict by majority
and then take the *first* replicate carrying that verdict, using its reason.

Row order carries no information once the verdict is settled, so that scored a
cell on a MINORITY reason whenever every replicate agreed on the verdict and
split on the reason. On SurfaceBench it mislabeled three genes — JAK2 was
counted correct off a 1-of-3 reason, while FN1 and LAMP3 were counted wrong
despite 2-of-3 agreeing with the curator — and moved the headline category in
the paper from 4 genes to 3.

These tests fix the behaviour at the boundary the bug lived on: a cell whose
replicates agree on the verdict and disagree on the reason, with the minority
reason placed FIRST so a row-order implementation cannot pass.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd
import pytest

from accessible_surfaceome.paths import REPO_ROOT


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def fig_mod():
    return _load(
        REPO_ROOT / "scripts" / "figures" / "curator_vs_agent_reason.py",
        "curator_vs_agent_reason",
    )


@pytest.fixture(scope="module")
def export_mod():
    return _load(
        REPO_ROOT / "scripts" / "tsv-export" / "export_mainbench_to_tsv.py",
        "export_mainbench_to_tsv",
    )


def _reps(reasons: list[str], verdict: str = "no") -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"replicate": i + 1, "predicted_verdict": verdict, "predicted_reason": r}
            for i, r in enumerate(reasons)
        ]
    )


def test_figure_collapse_takes_the_mode_not_the_first_row(fig_mod):
    """Minority reason first: a row-order implementation returns it and fails."""
    got = fig_mod._representative_reason(
        _reps(["cytoplasmic", "inner_leaflet_anchored", "inner_leaflet_anchored"])
    )
    assert got == "inner_leaflet_anchored", (
        "collapse returned the first replicate's reason instead of the mode — "
        "this is the JAK2 bug"
    )


def test_figure_collapse_is_order_independent(fig_mod):
    """Same multiset of reasons must collapse the same way in any order."""
    reasons = ["cytoplasmic", "inner_leaflet_anchored", "inner_leaflet_anchored"]
    results = {
        fig_mod._representative_reason(_reps(list(perm)))
        for perm in (
            reasons,
            reasons[::-1],
            [reasons[1], reasons[0], reasons[2]],
        )
    }
    assert results == {"inner_leaflet_anchored"}, results


def test_figure_collapse_keeps_reason_inside_the_winning_verdict(fig_mod):
    """The reason must come from a rep carrying the winning verdict.

    Guards the schema rule that a ``yes`` verdict cannot carry a NO-bucket
    reason: here the lone ``no`` rep is outvoted, so its ``cytoplasmic``
    reason must not surface even though it is the most frequent string.
    """
    df = pd.DataFrame(
        [
            {"replicate": 1, "predicted_verdict": "no", "predicted_reason": "cytoplasmic"},
            {"replicate": 2, "predicted_verdict": "yes", "predicted_reason": "gpi_anchored"},
            {"replicate": 3, "predicted_verdict": "yes", "predicted_reason": "gpi_anchored"},
        ]
    )
    assert fig_mod._representative_reason(df) == "gpi_anchored"


def test_mainbench_export_collapse_takes_the_mode(export_mod):
    rows = [
        {
            "gene_symbol": "JAK2", "model": "m", "prompt_variant": "v",
            "predicted_verdict": "no", "predicted_reason": r,
            "predicted_confidence": c,
        }
        for r, c in (
            ("cytoplasmic", "low"),
            ("inner_leaflet_anchored", "high"),
            ("inner_leaflet_anchored", "high"),
        )
    ]
    out = export_mod._collapse_to_majority(rows)
    assert len(out) == 1
    assert out[0]["predicted_reason"] == "inner_leaflet_anchored"
    assert out[0]["predicted_confidence"] == "high"


def test_both_collapses_agree(fig_mod, export_mod):
    """The figure and the published TSV must not drift apart again.

    They are separate implementations of one rule; S3 read one way and
    mainbench_canonical_v2 the other would reintroduce exactly the
    inconsistency this change removed.
    """
    reasons = ["cytoplasmic", "inner_leaflet_anchored", "inner_leaflet_anchored"]
    from_fig = fig_mod._representative_reason(_reps(reasons))
    from_export = export_mod._collapse_to_majority(
        [
            {
                "gene_symbol": "G", "model": "m", "prompt_variant": "v",
                "predicted_verdict": "no", "predicted_reason": r,
                "predicted_confidence": "high",
            }
            for r in reasons
        ]
    )[0]["predicted_reason"]
    assert from_fig == from_export == "inner_leaflet_anchored"
