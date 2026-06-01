"""Pin the deep-block ``Filters`` rollup derivations.

``tumor_associated`` / ``induction_trigger`` / ``has_live_cell_surface_evidence``
are deterministic functions of the deep blocks. The backfill script's
``derive_rollups`` is the literal-mirror of
``surfaceome_v1/orchestrator.py:_derive_filters`` (same bucket map + rules);
these tests pin both behaviours so the catalog facet can't silently drift.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

_SCRIPT = (
    Path(__file__).resolve().parents[1] / "scripts" / "backfill_deep_block_rollups.py"
)
_spec = importlib.util.spec_from_file_location("backfill_deep_block_rollups", _SCRIPT)
assert _spec and _spec.loader
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
derive_rollups = _mod.derive_rollups


def _rec(*, tissues=(), modulation=(), methods=()) -> dict:
    return {
        "biological_context": {
            "tissues": list(tissues),
            "accessibility_modulation": list(modulation),
        },
        "surface_evidence": {"methods": list(methods)},
    }


def test_tumor_associated() -> None:
    assert derive_rollups(
        _rec(tissues=[{"disease_context": "tumor", "present": "moderate"}])
    )["tumor_associated"]
    # tumor context but absent level → not associated
    assert not derive_rollups(
        _rec(tissues=[{"disease_context": "tumor", "present": "absent"}])
    )["tumor_associated"]
    # expressed but normal context → not tumor-associated
    assert not derive_rollups(
        _rec(tissues=[{"disease_context": "normal", "present": "high"}])
    )["tumor_associated"]


def test_induction_trigger_priority_and_bucketing() -> None:
    # Priority: oncogenic wins over immune.
    rec = _rec(
        modulation=[
            {"cell_state_trigger": "immune_activation"},
            {"cell_state_trigger": "oncogenic_transformation"},
        ]
    )
    assert derive_rollups(rec)["induction_trigger"] == "oncogenic"
    # Bucketing.
    assert (
        derive_rollups(_rec(modulation=[{"cell_state_trigger": "hypoxia"}]))[
            "induction_trigger"
        ]
        == "stress_hypoxia"
    )
    assert (
        derive_rollups(_rec(modulation=[{"cell_state_trigger": "apoptosis"}]))[
            "induction_trigger"
        ]
        == "cell_death"
    )
    # No trigger / no modulation → none.
    assert (
        derive_rollups(_rec(modulation=[{"cell_state_trigger": None}]))[
            "induction_trigger"
        ]
        == "none"
    )
    assert derive_rollups(_rec())["induction_trigger"] == "none"


def test_has_live_cell_surface_evidence() -> None:
    direct_flow = {
        "method_family": "flow_cytometry",
        "accessibility_relevance": "direct_surface_accessibility",
        "expression_system": "endogenous",
    }
    assert derive_rollups(_rec(methods=[direct_flow]))[
        "has_live_cell_surface_evidence"
    ]
    # IHC isn't a live-cell family → False (even if direct + endogenous).
    ihc = {**direct_flow, "method_family": "immunohistochemistry"}
    assert not derive_rollups(_rec(methods=[ihc]))["has_live_cell_surface_evidence"]
    # Overexpression context → False (must be endogenous/mixed).
    oe = {**direct_flow, "expression_system": "overexpression"}
    assert not derive_rollups(_rec(methods=[oe]))["has_live_cell_surface_evidence"]
    # Supportive-only relevance → False (must be direct).
    weak = {**direct_flow, "accessibility_relevance": "supports_surface_localization"}
    assert not derive_rollups(_rec(methods=[weak]))["has_live_cell_surface_evidence"]
