"""Parse-time validator regression tests (Chunk 6 of the PR #47 redesign).

Pinned anti-examples for the discipline lifted out of prompt prose into
Pydantic validators: compartment/subdomain canonical-name shape (A5.1),
inner-leaflet redirect (A5.2), modulation contrast-not-context (A7.1), and
oncogenic-transformation cancer-vocab gating (A7.2).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from accessible_surfaceome.tools._shared.models import (
    AccessibilityModulationObservation,
    DualLocalization,
    MembraneSubdomain,
)


# --------------------------------------------------------------------------
# A5.1 — compartment / subdomain are SHORT canonical names
# --------------------------------------------------------------------------


def test_compartment_accepts_short_canonical_name():
    assert DualLocalization(compartment="early endosome").compartment == "early endosome"


def test_compartment_rejects_parenthetical_condition():
    with pytest.raises(ValidationError, match="parenthetical"):
        DualLocalization(compartment="endosome (upon EGF ligand stimulation)")


def test_compartment_rejects_conditional_clause():
    with pytest.raises(ValidationError, match="conditional clause"):
        DualLocalization(compartment="endosome upon ligand stimulation")


def test_compartment_rejects_overlong_value():
    with pytest.raises(ValidationError, match="short canonical name"):
        DualLocalization(
            compartment="the perinuclear recycling endosomal compartment located adjacent to the Golgi apparatus"
        )


def test_compartment_accepts_long_canonical_organelle_name():
    # The full ERGIC name (52 chars) is a real canonical name, not a sentence —
    # the generous length cap + structural guards must let it through.
    name = "endoplasmic reticulum-Golgi intermediate compartment"
    assert DualLocalization(compartment=name).compartment == name


def test_subdomain_accepts_short_canonical_name():
    assert MembraneSubdomain(subdomain="lipid raft").subdomain == "lipid raft"


# --------------------------------------------------------------------------
# A5.2 — inner-leaflet / cytoplasmic-face is NOT a surface subdomain
# --------------------------------------------------------------------------


def test_subdomain_rejects_inner_leaflet():
    with pytest.raises(ValidationError, match="dual_localization"):
        MembraneSubdomain(subdomain="inner leaflet")


def test_subdomain_rejects_cytoplasmic_face():
    with pytest.raises(ValidationError, match="dual_localization"):
        MembraneSubdomain(subdomain="cytoplasmic face microdomain")


# --------------------------------------------------------------------------
# A7.1 / A7.2 — modulation contrast + trigger vocabulary
# --------------------------------------------------------------------------


def _mod(**overrides) -> dict:
    base = {
        "category": "cell_state_induced",
        "cell_state_trigger": "ER_stress",
        "baseline_context": "resting cells",
        "modulating_state": "activated cells",
        "change": "surface pool increases",
        "accessibility_implication": "more accessible when activated",
    }
    base.update(overrides)
    return base


def test_modulation_accepts_distinct_states():
    obs = AccessibilityModulationObservation(**_mod())
    assert obs.direction == "unclear"  # additive default


def test_modulation_direction_field_accepts_enum():
    obs = AccessibilityModulationObservation(**_mod(direction="increases"))
    assert obs.direction == "increases"


def test_modulation_rejects_context_not_contrast():
    # baseline_context == modulating_state → not a documented change.
    with pytest.raises(ValidationError, match="contrast, not a context"):
        AccessibilityModulationObservation(
            **_mod(baseline_context="tumor cells", modulating_state="Tumor Cells")
        )


def test_oncogenic_trigger_requires_cancer_vocab():
    with pytest.raises(ValidationError, match="cancer / tumor context"):
        AccessibilityModulationObservation(
            **_mod(
                cell_state_trigger="oncogenic_transformation",
                baseline_context="healthy epithelium",
                modulating_state="inflamed tissue",
            )
        )


def test_oncogenic_trigger_accepts_cancer_context():
    obs = AccessibilityModulationObservation(
        **_mod(
            cell_state_trigger="oncogenic_transformation",
            baseline_context="normal epithelium",
            modulating_state="lung adenocarcinoma",
        )
    )
    assert obs.cell_state_trigger == "oncogenic_transformation"
