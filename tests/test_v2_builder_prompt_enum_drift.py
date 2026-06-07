"""Catch enum drift between v2 block-builder prompts and the schema.

A builder prompt that lists ``direction="increases_surface"`` for a field
whose schema enum only accepts ``increases`` / ``decreases`` ships records
that fail Pydantic validation at builder runtime. This is exactly the bug
fixed in the same PR that introduced this test:
``accessibility_modulation_builder_system.md`` had defined ``direction``
twice — once with the schema's values (``increases``, ``decreases``, ...)
and once with a parallel ``_surface``-suffixed family — and only the first
matched ``ModulationDirection`` in ``models.py``.

The test enforces two invariants on each (prompt, field) pair in the
registry below:

1. **No drift** — every ``\\`field="VALUE"\\`\\`` pattern in the prompt
   uses a VALUE that exists in the schema's ``Literal[...]`` for that
   field. Inline assignment patterns are the most reliable signal that
   "the prompt is telling the model to emit this value", since they
   appear in tables, bullet lists, and worked examples uniformly.
2. **No duplicate intro** — the field is introduced as a bullet
   (``- \\`field\\` — …``) at most once. The bug pattern is two
   introductions for the same field where the second silently redefines
   the value set.

Add a row to ``ENUM_REGISTRY`` when a new builder closed-enum lands.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import get_args

import pytest

from accessible_surfaceome.tools._shared.models import (
    AccessibilityImplication,
    AccessibilityRelevance,
    CellStateTrigger,
    ClaimStance,
    ClaimWeight,
    ContradictionSeverity,
    ContradictionType,
    DiseaseContext,
    DualLocPartnerCompartment,
    EvidenceGrade,
    MeasurementType,
    MethodFamily,
    MethodSubclass,
    ModulationCategory,
    ModulationDirection,
    Orientation,
    Permeabilization,
    PrimaryCompartment,
    RestrictedLineage,
    SurfaceClaimType,
    TissuePresence,
    ValidationStrategy,
    ValidationStrength,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
PROMPTS_DIR = (
    REPO_ROOT / "src" / "accessible_surfaceome" / "agents" / "surfaceome_v2" / "prompts"
)


# (prompt_filename, field_name, schema_literal_type).
# field_name is the lowercase identifier the prompt uses in backticks
# (e.g. ``\`direction\``); schema_literal_type is the ``Literal[...]``
# declared in ``tools/_shared/models.py``.
ENUM_REGISTRY: list[tuple[str, str, object]] = [
    # methods_builder — every closed-enum on MethodObservation / AntibodyRef
    ("methods_builder_system.md", "method_family", MethodFamily),
    ("methods_builder_system.md", "method_subclass", MethodSubclass),
    ("methods_builder_system.md", "validation_strategy", ValidationStrategy),
    ("methods_builder_system.md", "validation_strength", ValidationStrength),
    ("methods_builder_system.md", "accessibility_relevance", AccessibilityRelevance),
    ("methods_builder_system.md", "surface_claim_type", SurfaceClaimType),
    ("methods_builder_system.md", "permeabilization", Permeabilization),
    # evidence_grade_builder — verdict + per-claim stance/weight
    ("evidence_grade_builder_system.md", "evidence_grade", EvidenceGrade),
    ("evidence_grade_builder_system.md", "stance", ClaimStance),
    ("evidence_grade_builder_system.md", "weight", ClaimWeight),
    ("evidence_grade_builder_system.md", "measurement_type", MeasurementType),
    # accessibility_modulation_builder — the file the duplicate-intro bug lived in
    ("accessibility_modulation_builder_system.md", "category", ModulationCategory),
    ("accessibility_modulation_builder_system.md", "direction", ModulationDirection),
    (
        "accessibility_modulation_builder_system.md",
        "cell_state_trigger",
        CellStateTrigger,
    ),
    (
        "accessibility_modulation_builder_system.md",
        "restricted_lineage",
        RestrictedLineage,
    ),
    (
        "accessibility_modulation_builder_system.md",
        "dual_loc_partner_compartment",
        DualLocPartnerCompartment,
    ),
    # anatomical_accessibility_builder
    ("anatomical_accessibility_builder_system.md", "orientation", Orientation),
    (
        "anatomical_accessibility_builder_system.md",
        "accessibility_implication",
        AccessibilityImplication,
    ),
    # subcellular_localization_builder
    (
        "subcellular_localization_builder_system.md",
        "primary_compartment",
        PrimaryCompartment,
    ),
    # expression_builder
    ("expression_builder_system.md", "present", TissuePresence),
    ("expression_builder_system.md", "disease_context", DiseaseContext),
    # contradiction_builder
    ("contradiction_builder_system.md", "contradiction_type", ContradictionType),
    (
        "contradiction_builder_system.md",
        "severity_for_surface_accessibility",
        ContradictionSeverity,
    ),
]


def _inline_assignment_values(text: str, field_name: str) -> set[str]:
    """Return every VALUE that appears as ``\\`field="VALUE"\\`\\`` in the
    prompt — across tables, bullet lists, and worked examples.

    Tolerates the few common quoting shapes: ``\\`field="X"\\`\\``,
    ``\\`field='X'\\`\\``, and ``field="X"`` (unbackticked, in prose
    examples). Captures the inner VALUE.
    """
    pat = re.compile(rf"`?{re.escape(field_name)}\s*=\s*[\"']([a-z][a-z0-9_]*)[\"']`?")
    return set(pat.findall(text))


def _bullet_intro_count(text: str, field_name: str) -> int:
    """Count occurrences of ``- \\`field\\` —`` as a top-level bullet
    intro. Two or more means the field is introduced twice — the
    duplicate-definition bug pattern this test was added to catch."""
    # Word-boundary on the closing backtick so ``- `direction`` doesn't
    # match ``- `directional``. Allow em-dash (—) or ASCII " - " separator.
    pat = re.compile(
        rf"^-\s+`{re.escape(field_name)}`\s+(—|--|\-\s)",
        re.MULTILINE,
    )
    return len(pat.findall(text))


@pytest.mark.parametrize(
    "prompt_filename,field_name,schema_type",
    ENUM_REGISTRY,
    ids=[
        f"{prompt}::{field}"
        for prompt, field, _ in ENUM_REGISTRY
    ],
)
def test_inline_assignment_values_in_schema(
    prompt_filename: str,
    field_name: str,
    schema_type: object,
) -> None:
    """Every ``\\`field="VALUE"\\`\\`` pattern in the prompt must use a
    VALUE the schema's Literal[...] accepts.

    Worked example: pre-fix ``accessibility_modulation_builder_system.md``
    had ``direction="increases_surface"`` patterns. ``ModulationDirection``
    in ``models.py`` only accepts ``{increases, decreases, bidirectional,
    no_change, unclear}``. Any record the LLM emits using the prompt's
    second definition would fail Pydantic validation at builder
    runtime. This test fails fast at CI rather than at gene-annotation
    time."""
    prompt_path = PROMPTS_DIR / prompt_filename
    assert prompt_path.is_file(), f"missing prompt file: {prompt_path}"
    text = prompt_path.read_text(encoding="utf-8")
    declared = _inline_assignment_values(text, field_name)
    schema_values = set(get_args(schema_type))
    drift = declared - schema_values
    assert not drift, (
        f"{prompt_filename}: field `{field_name}` is assigned values "
        f"{sorted(drift)} (via `{field_name}=\"...\"` patterns) that "
        f"are not in the schema's "
        f"{getattr(schema_type, '__name__', type(schema_type).__name__)}. "
        f"Schema values: {sorted(schema_values)}. "
        f"Either update the prompt to drop the drift values, or add them "
        f"to the Literal[...] in models.py."
    )


@pytest.mark.parametrize(
    "prompt_filename,field_name,schema_type",
    ENUM_REGISTRY,
    ids=[
        f"{prompt}::{field}"
        for prompt, field, _ in ENUM_REGISTRY
    ],
)
def test_field_introduced_as_bullet_at_most_once(
    prompt_filename: str,
    field_name: str,
    schema_type: object,  # noqa: ARG001  # parametrized for symmetric IDs
) -> None:
    """A field can be introduced as a top-level bullet (``- \\`field\\` —
    …``) at most once. Two introductions = the bug pattern that let the
    ``direction`` drift in accessibility_modulation slip through, where a
    second definition silently redefined the value set with non-schema
    values.

    Not every field has a bullet intro (e.g. ``validation_strategy`` is
    defined via a table) — that's fine; the assertion is ≤ 1, not = 1.
    The strict-= 1 case is caught by ``test_inline_assignment_values_in_schema``
    indirectly: if a field with NO documented values has bad values in
    inline assignments, that test fires."""
    prompt_path = PROMPTS_DIR / prompt_filename
    text = prompt_path.read_text(encoding="utf-8")
    count = _bullet_intro_count(text, field_name)
    assert count <= 1, (
        f"{prompt_filename}: `{field_name}` is introduced as a top-level "
        f"bullet ({count} times). Two or more introductions create silent "
        f"enum drift (the second can disagree with the schema and still "
        f"validate-by-pattern). Consolidate into one bullet with the "
        f"schema's canonical values."
    )
