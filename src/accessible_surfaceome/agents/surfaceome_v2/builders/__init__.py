"""Block builders for the v2 deep-dive pipeline.

Each builder is a focused Sonnet call that takes an ``EvidenceClaim``
ledger slice + a target schema and returns a structured block. The
constellation:

A1 side (surface_evidence sub-blocks):
- :func:`build_methods` → ``list[MethodObservation]``
- :func:`build_contradictions` → ``list[Contradiction]``
- :func:`build_evidence_grade` → ``EvidenceGradeBlock``

A2 side (biological_context sub-blocks):
- :func:`build_expression` → ``list[ExpressionRow]`` (unified tissue ×
  cell-of-origin pivot; replaces the old tissues + cell_types builders)
- :func:`build_cell_states` → ``list[StateContext]`` (csGRP78-class)
- :func:`build_subcellular_localization` → ``SubcellularLocalization``
- :func:`build_anatomical_accessibility` → ``list[AnatomicalAccessibilityObservation]``
- :func:`build_accessibility_modulation` → ``list[AccessibilityModulationObservation]``
"""

from accessible_surfaceome.agents.surfaceome_v2.builders.accessibility_modulation import (
    build_accessibility_modulation,
)
from accessible_surfaceome.agents.surfaceome_v2.builders.anatomical_accessibility import (
    build_anatomical_accessibility,
)
from accessible_surfaceome.agents.surfaceome_v2.builders.cell_states import (
    build_cell_states,
)
from accessible_surfaceome.agents.surfaceome_v2.builders.contradictions import (
    build_contradictions,
)
from accessible_surfaceome.agents.surfaceome_v2.builders.evidence_grade import (
    EvidenceGradeBlock,
    build_evidence_grade,
)
from accessible_surfaceome.agents.surfaceome_v2.builders.expression import (
    build_expression,
)
from accessible_surfaceome.agents.surfaceome_v2.builders.methods import build_methods
from accessible_surfaceome.agents.surfaceome_v2.builders.subcellular_localization import (
    build_subcellular_localization,
)
from accessible_surfaceome.agents.surfaceome_v2.builders.tissues import build_tissues

__all__ = [
    "EvidenceGradeBlock",
    "build_accessibility_modulation",
    "build_anatomical_accessibility",
    "build_cell_states",
    "build_contradictions",
    "build_evidence_grade",
    "build_expression",
    "build_methods",
    "build_subcellular_localization",
    "build_tissues",
]
