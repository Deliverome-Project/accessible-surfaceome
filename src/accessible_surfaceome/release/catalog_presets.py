"""Python mirror of viewer/lib/catalog-presets.ts.

The viewer ships these predicates as a TypeScript module (the catalog
toolbar imports them). The Zenodo deposit also ships the same membership
as a flat TSV so a reanalyst can read the shortlist without re-running
the predicate themselves. Both surfaces have to evaluate the same rule
on every record — drift between them silently invalidates citations.

This module is the Python side. Keep the rules byte-identical to the
TypeScript at viewer/lib/catalog-presets.ts; the test at
tests/test_catalog_presets_mirror.py asserts membership matches between
the two by running both over a fixture set.

All predicates take a single ``filters`` dict (the body of
``annotation_json["filters"]`` for a SurfaceomeRecord) and return bool.
"""
from __future__ import annotations

from typing import Any, Callable

# Reasons in the YES + CONTEXTUAL buckets (real surface call). Used by
# the ECD-bypass in ``passes_likely`` so e.g. HMGB1 (ecd=none + reason=
# cell_state_induced) and SRC (ecd=none + reason=lysosomal_exocytosis)
# are admitted while LYN (ecd=none + reason=inner_leaflet_anchored) is
# excluded.
POSITIVE_REASONS: frozenset[str] = frozenset({
    # YES bucket
    "classical_surface_receptor",
    "gpi_anchored",
    "multipass_with_exposed_loops",
    "extracellular_face_protein",
    "stable_complex_partner",
    # CONTEXTUAL bucket
    "cell_state_induced",
    "tissue_restricted_surface",
    "lysosomal_exocytosis",
    "dual_localization",
    "stable_surface_attachment",
})

INDUCTION_NON_NONE: frozenset[str] = frozenset({
    "oncogenic",
    "immune",
    "stress_hypoxia",
    "cell_death",
    "infection",
})


def passes_canonical(f: dict[str, Any]) -> bool:
    """Strictest tier — antibody/ADC gold-standard."""
    return (
        f.get("evidence_grade") in ("direct_multi_method", "direct_single_method")
        and f.get("confidence") in ("high", "moderate")
        and f.get("surface_specificity") in ("surface_dominant", "mixed")
        and f.get("state_dependence") in ("low", "moderate")
        and f.get("surface_accessibility") in ("high", "moderate")
        and f.get("evidence_density") in ("high", "moderate")
        and f.get("ecd_accessibility_class") in ("large", "moderate", "small")
    )


def passes_likely(f: dict[str, Any]) -> bool:
    """Broader shortlist — adds supportive_but_indirect evidence,
    mostly_intracellular specificity (SRC-class lysosomal-exocytosis
    surface), high/unclear/null state-dep, and relaxes ecd=none/minimal
    IFF surface_call_reason is in POSITIVE_REASONS."""
    if f.get("evidence_grade") not in (
        "direct_multi_method", "direct_single_method", "supportive_but_indirect"
    ):
        return False
    if f.get("surface_specificity") not in (
        "surface_dominant", "mixed", "mostly_intracellular"
    ):
        return False
    if f.get("surface_accessibility") not in ("high", "moderate", "low"):
        return False
    sd = f.get("state_dependence")
    if sd is not None and sd not in ("low", "moderate", "high", "unclear"):
        return False
    ecd = f.get("ecd_accessibility_class")
    if ecd in ("large", "moderate", "small"):
        return True
    if ecd in ("minimal", "none") and f.get("surface_call_reason") in POSITIVE_REASONS:
        return True
    return False


def passes_induced(f: dict[str, Any]) -> bool:
    """Cell-state induced — surface presentation depends on cell state.
    Matches via EITHER ``surface_call_reason`` in {cell_state_induced,
    lysosomal_exocytosis} OR ``induction_trigger`` in INDUCTION_NON_NONE.
    The latter is the field that schema-1.1.0 records (HSPA5) actually
    populate when surface_call_reason is null."""
    if not passes_likely(f):
        return False
    sd = f.get("state_dependence")
    if sd is not None and sd != "high":
        return False
    if f.get("surface_call_reason") in ("cell_state_induced", "lysosomal_exocytosis"):
        return True
    if f.get("induction_trigger") in INDUCTION_NON_NONE:
        return True
    return False


def passes_cell_type_restricted(f: dict[str, Any]) -> bool:
    """Constitutively surface on specific cell types only (KLK2-class)."""
    if not passes_likely(f):
        return False
    if f.get("state_dependence") not in ("moderate", "high"):
        return False
    return f.get("surface_call_reason") == "tissue_restricted_surface"


# Induction sub-axes — only meaningful when the induced predicate is
# already true; surfaced as standalone bools in the deposit TSV so a
# reanalyst can re-bucket without recomputing.
def passes_induction_disease(f: dict[str, Any]) -> bool:
    return f.get("induction_trigger") in ("oncogenic", "cell_death", "infection")


def passes_induction_stress(f: dict[str, Any]) -> bool:
    return f.get("induction_trigger") == "stress_hypoxia"


def passes_induction_immune(f: dict[str, Any]) -> bool:
    return f.get("induction_trigger") == "immune"


# Ordered registry — same shape the viewer's PRESETS array exposes.
PRESETS: tuple[tuple[str, str, Callable[[dict[str, Any]], bool]], ...] = (
    ("canonical", "Canonical", passes_canonical),
    ("likely", "Likely", passes_likely),
    ("induced", "Cell-state induced", passes_induced),
    ("cell_type_restricted", "Cell-type restricted", passes_cell_type_restricted),
)

INDUCTION_SUBS: tuple[tuple[str, str, Callable[[dict[str, Any]], bool]], ...] = (
    ("disease", "Disease (oncogenic / cell-death / infection)", passes_induction_disease),
    ("stress", "Stress / hypoxia", passes_induction_stress),
    ("immune", "Immune", passes_induction_immune),
)
