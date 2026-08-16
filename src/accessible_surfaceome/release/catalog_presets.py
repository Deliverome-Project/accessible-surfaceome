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

INDUCTION_NON_NONE: frozenset[str] = frozenset({
    "oncogenic",
    "immune",
    "stress_hypoxia",
    "cell_death",
    "infection",
})

# Discovery-corpus size below which the deep dive rarely reaches a confident
# (canonical) surface call — so a non-surface verdict here may be an evidence
# gap rather than biology. Empirical (PR #130 analysis over the 5,130 cohort):
# canonical rate is ~1-5% below 75 papers and 18% in 75-100, vs 47% at 150-200
# and ~60% above 200 — a clear inflection at ~100. ~bottom 20% of the discovery
# distribution (median ≈ 220 papers found).
LOW_LIT_PAPERS_MAX = 100

# Structural-surface reason codes strong enough to admit a ``weak``-graded gene
# into Likely (the weakStructuralOk carve-out in passes_likely). Surface
# membership is structurally unambiguous for these — classical single-/multi-
# pass receptor, GPI anchor, or constitutively-surface tissue-restricted
# protein — so a weak LITERATURE grade reflects thin coverage, not doubt about
# reaching the surface. EXCLUDES ambiguous reasons (dual_localization,
# cell_state_induced, endomembrane_resident, inner_leaflet_anchored,
# cytoplasmic, secreted_only, …) where a weak grade genuinely could mean the
# surface pool is unproven. Mirror of the TS STRUCTURAL_SURFACE_REASONS.
STRUCTURAL_SURFACE_REASONS: frozenset[str] = frozenset({
    "classical_surface_receptor",
    "multipass_with_exposed_loops",
    "gpi_anchored",
    "tissue_restricted_surface",
})


def effective_evidence_grade(f: dict[str, Any]) -> Any:
    """The grade the tiers gate on: the synthesizer's holistic
    ``evidence_grade_summary`` (what the gene page displays), falling back to
    the deterministic A1-only ``evidence_grade`` when the summary is absent
    (older records / before the Worker ships the ddf field). Mirror of the TS
    ``effectiveEvidenceGrade``. The deterministic grade under-calls genes whose
    surface call rests on rich A2 context (MC2R, EFNA5: deterministic ``weak``
    but summary ``supportive``), so gating on the summary keeps the tiers
    consistent with what the gene page shows."""
    summary = f.get("evidence_grade_summary")
    return summary if summary is not None else f.get("evidence_grade")


def passes_canonical(f: dict[str, Any]) -> bool:
    """Strictest tier — the high-confidence BROAD surface shortlist.

    Byte-for-byte mirror of the TS ``passesCanonical``. Gates, in order:

    1. ``surface_call_reason`` is NEITHER ``tissue_restricted_surface`` NOR
       ``lysosomal_exocytosis`` — those are non-classical surfacing routed to
       Likely + their facet, never the broad Canonical shortlist. (State /
       induced facets still overlay Canonical; only these two reasons are hard
       exclusions here.)
    2. Evidence FLOOR: ``effective_evidence_grade`` (the holistic
       ``evidence_grade_summary``, falling back to A1 ``evidence_grade``) is at
       least ``supportive_but_indirect`` — ``weak`` and ``conflicting`` are
       held out.
    3. ``confidence in {high, moderate}`` — the real quality bar above the
       floor (the A1-only grade under-calls A2-context-driven calls).
    4. ``surface_specificity in {surface_dominant, mixed}``.
    5. State-dependence escape: ``state_dependence in {low, moderate, unclear}``
       OR ``expression_level in {moderate, high}``. Gates on expression LEVEL
       directly, not the derived ``low_endogenous_expression`` boolean (which
       folds in breadth and demoted validated lineage-restricted targets like
       CTLA4 / 4-1BB). Additive — only admits high-state-dependence genes.
    6. ``surface_accessibility in {high, moderate}``.
    7. ``evidence_density in {high, moderate}``.

    Drops the ECD filter (ECD-size is an antibody-design refinement, not a
    surface-membership signal — CLDN18.2 has small loops and a landed
    therapeutic). Canonical certifies *is* it surface; *when* / *where* are the
    state_dependence + breadth facets."""
    g = effective_evidence_grade(f)
    return (
        f.get("surface_call_reason") not in (
            "tissue_restricted_surface", "lysosomal_exocytosis"
        )
        and g in (
            "direct_multi_method", "direct_single_method", "supportive_but_indirect"
        )
        and f.get("confidence") in ("high", "moderate")
        and f.get("surface_specificity") in ("surface_dominant", "mixed")
        and (
            f.get("state_dependence") in ("low", "moderate", "unclear")
            or f.get("expression_level") in ("moderate", "high")
        )
        and f.get("surface_accessibility") in ("high", "moderate")
        and f.get("evidence_density") in ("high", "moderate")
    )


def is_low_literature_surface(f: dict[str, Any], db_surface_positive: bool) -> bool:
    """Badge — NOT a tier preset. Flags a gene with thin surface evidence: a
    small discovery corpus (``n_papers_found < LOW_LIT_PAPERS_MAX``) AND an
    external surface-DB call predicts it surface. Under-studied surface
    candidates worth a targeted re-dive.

    INDEPENDENT of the tier presets — NOT scoped to non-canonical genes, so it
    can co-occur with any tier under the catalog's multi-select toggle (a
    well-studied gene simply won't carry it). That orthogonality is why it's a
    standalone badge, not a member of the ``(filters) -> bool`` preset family.

    The DB flag is passed via ``db_surface_positive``; the viewer wires it to
    **UniProt** (``catalogRow.db.uniprot``), which outperformed the other
    surface databases on our gold-standard positive controls. It's a
    candidate-universe flag, not part of the deep-dive ``filters``, hence the
    extra argument. ``n_papers_found`` missing → not flagged."""
    n = f.get("n_papers_found")
    if n is None:
        return False
    return bool(db_surface_positive) and n < LOW_LIT_PAPERS_MAX


def passes_likely(f: dict[str, Any]) -> bool:
    """Broader shortlist — adds supportive_but_indirect evidence,
    mostly_intracellular specificity (SRC-class lysosomal-exocytosis
    surface, HMGB1-class DAMP release), and high/unclear/null state-dep.

    Byte-for-byte mirror of the TS ``passesLikely``. Evidence gate is a FLOOR
    on ``effective_evidence_grade`` (>= supportive_but_indirect) OR the
    ``weakStructuralOk`` carve-out: a ``weak``-graded gene still qualifies when
    its ``surface_call_reason`` is structurally-unambiguous
    (STRUCTURAL_SURFACE_REASONS) — the weak grade is a literature-coverage
    artifact, not doubt about surface membership (rescues the protocadherin /
    SLAM / butyrophilin / platelet-GPV false-negatives). The remaining gates
    (specificity, moderate+ accessibility, state) still apply.

    Accessibility FLOOR is moderate+ (matches Canonical); a ``low`` call drops
    to the below-Likely ``low`` tier. Inner-leaflet false positives (LYN, BAX)
    and secreted-only (IZUMO4) are excluded because they fail on weak grade AND
    ``surface_accessibility=no``."""
    g = effective_evidence_grade(f)
    grade_floor_ok = g in (
        "direct_multi_method", "direct_single_method", "supportive_but_indirect"
    )
    weak_structural_ok = (
        g == "weak" and f.get("surface_call_reason") in STRUCTURAL_SURFACE_REASONS
    )
    if not grade_floor_ok and not weak_structural_ok:
        return False
    if f.get("surface_specificity") not in (
        "surface_dominant", "mixed", "mostly_intracellular"
    ):
        return False
    if f.get("surface_accessibility") not in ("high", "moderate"):
        return False
    sd = f.get("state_dependence")
    if sd is not None and sd not in ("low", "moderate", "high", "unclear"):
        return False
    return True


def passes_likely_only(f: dict[str, Any]) -> bool:
    """Likely tier MINUS Canonical — the exclusive band the ``Likely`` catalog
    chip filters to, so Canonical and Likely chips are DISJOINT selectable
    bands whose union is the full Likely tier (Canonical ⊂ Likely). Mirror of
    the TS ``passesLikelyOnly``. Tier assignment (``deep_dive_tier``, the
    Figure-5 buckets) still uses full ``passes_likely`` with canonical-first
    precedence, so no double count."""
    return passes_likely(f) and not passes_canonical(f)


def passes_induced(f: dict[str, Any]) -> bool:
    """Cell-state induced — surface presentation is *gained on a cell state*.

    PRIMARY criterion: ``surface_call_reason`` in {cell_state_induced,
    lysosomal_exocytosis} — the reason codes that mean the protein reaches the
    surface because of a state change (induction, degranulation), not
    constitutively. This is the definitional gate.

    An earlier version ALSO admitted any gene with ``induction_trigger`` in
    INDUCTION_NON_NONE. That massively over-counted (2,127): ``induction_trigger
    = 'oncogenic'`` is assigned to essentially every tumour-associated gene
    (99% overlap with ``tumor_associated``), so constitutively-surface receptors
    (classical_surface_receptor / multipass / tissue_restricted) that merely
    correlate with cancer were swept in. Dropping the trigger disjunct restricts
    this to the ~407 genes whose surface presentation is genuinely state-gained.
    The ``induction_trigger`` axis is still exposed as the cancer / disease /
    stress / immune SUB-chips within this set.

    Accepts state_dep ∈ {moderate, high, unclear, null} — moderate
    state-dependence still indicates state-modulation (TROP2-class
    cancer-overexpression records the synthesizer rates "moderate"
    legitimately belong here)."""
    if not passes_likely(f):
        return False
    sd = f.get("state_dependence")
    if sd is not None and sd not in ("moderate", "high", "unclear"):
        return False
    return f.get("surface_call_reason") in (
        "cell_state_induced", "lysosomal_exocytosis"
    )


def passes_cell_type_restricted(f: dict[str, Any]) -> bool:
    """Constitutively surface on specific cell types only (KLK2-class)."""
    if not passes_likely(f):
        return False
    if f.get("state_dependence") not in ("moderate", "high"):
        return False
    return f.get("surface_call_reason") == "tissue_restricted_surface"


def deep_dive_tier(f: dict[str, Any]) -> tuple[str, str | None]:
    """(tier, facet) — the single five-tier deep-dive classification + optional
    sub-facet, mirroring the TS ``deepDiveTier`` and the precedence in
    build_figure_tsvs ``_dd_assign_bucket``. tier ∈ {canonical, likely, low,
    uncertain, no}; facet ∈ {induced, cell_type_restricted, None}. The facet is
    surfaced whenever its predicate holds (including on canonical genes)."""
    facet: str | None = (
        "cell_type_restricted" if passes_cell_type_restricted(f)
        else "induced" if passes_induced(f)
        else None
    )
    if passes_canonical(f):
        return ("canonical", facet)
    if passes_likely(f):
        return ("likely", facet)
    acc = f.get("surface_accessibility")
    if acc == "uncertain":
        return ("uncertain", None)
    if acc in ("low", "moderate"):
        return ("low", None)
    return ("no", None)


# Induction sub-axes — only meaningful when the induced predicate is
# already true; surfaced as standalone bools in the deposit TSV so a
# reanalyst can re-bucket without recomputing. Cancer is split out
# from Disease so the oncogenic bucket (the largest in the cohort)
# doesn't drown the non-oncogenic disease bucket (cell_death,
# infection — HMGB1-class DAMP biology).
def passes_induction_cancer(f: dict[str, Any]) -> bool:
    return f.get("induction_trigger") == "oncogenic"


def passes_induction_disease(f: dict[str, Any]) -> bool:
    return f.get("induction_trigger") in ("cell_death", "infection")


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
    ("cancer", "Cancer (oncogenic)", passes_induction_cancer),
    ("disease", "Other disease (cell-death / infection)", passes_induction_disease),
    ("stress", "Stress / hypoxia", passes_induction_stress),
    ("immune", "Immune", passes_induction_immune),
)
