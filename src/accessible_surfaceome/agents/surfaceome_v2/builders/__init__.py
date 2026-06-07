"""Block builders for the v2 deep-dive pipeline.

Each builder is a focused Sonnet call that takes an ``EvidenceClaim``
ledger slice + a target schema and returns a structured block. The
constellation:

A1 side (surface_evidence sub-blocks):
- :func:`build_methods` → ``list[MethodObservation]``
- :func:`build_contradictions` → ``list[Contradiction]``
- :func:`build_evidence_grade` → ``EvidenceGradeBlock``

A2 side (biological_context sub-blocks). Schema 2.5.0 merged the
former ``build_cell_states`` builder into
``build_accessibility_modulation`` — single-context state observations
now emit as modulation rows with ``baseline_context=None`` +
``modulating_state=None``.

- :func:`build_expression` → ``list[ExpressionRow]`` (unified tissue × cell_type)
- :func:`build_subcellular_localization` → ``SubcellularLocalization``
- :func:`build_anatomical_accessibility` → ``list[AnatomicalAccessibilityObservation]``
- :func:`build_accessibility_modulation` → ``list[AccessibilityModulationObservation]``
- :func:`build_biological_context_grade` → ``BiologicalContextGradeBlock``
  (A2 rollup — the A2 analog of ``build_evidence_grade``)

Cross-focus (merged A1+A2 ledger):
- :func:`build_risks` → ``AccessibilityRisks`` (the six accessibility-risk
  sub-blocks; consumes the merged ledger + deterministic features)
"""

from accessible_surfaceome.agents.surfaceome_v2.builders.accessibility_modulation import (
    build_accessibility_modulation,
)
from accessible_surfaceome.agents.surfaceome_v2.builders.anatomical_accessibility import (
    build_anatomical_accessibility,
)
from accessible_surfaceome.agents.surfaceome_v2.builders.biological_context_grade import (
    BiologicalContextGradeBlock,
    build_biological_context_grade,
)
from accessible_surfaceome.agents.surfaceome_v2.builders.contradictions import (
    build_contradictions,
)
from accessible_surfaceome.agents.surfaceome_v2.builders.expression import (
    build_expression,
)
from accessible_surfaceome.agents.surfaceome_v2.builders.evidence_grade import (
    EvidenceGradeBlock,
    build_evidence_grade,
)
from accessible_surfaceome.agents.surfaceome_v2.builders.methods import build_methods
from accessible_surfaceome.agents.surfaceome_v2.builders.risks import build_risks
from accessible_surfaceome.agents.surfaceome_v2.builders.subcellular_localization import (
    build_subcellular_localization,
)

__all__ = [
    "BiologicalContextGradeBlock",
    "EvidenceGradeBlock",
    "build_accessibility_modulation",
    "build_anatomical_accessibility",
    "build_biological_context_grade",
    "build_contradictions",
    "build_evidence_grade",
    "build_expression",
    "build_methods",
    "build_risks",
    "build_subcellular_localization",
]
