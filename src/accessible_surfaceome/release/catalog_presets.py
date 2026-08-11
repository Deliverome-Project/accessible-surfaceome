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


def passes_canonical(f: dict[str, Any]) -> bool:
    """Strictest tier — antibody/ADC gold-standard.

    Drops the ECD filter (ECD-size is a design refinement, not a
    surface-membership signal — Claudin-18.2 has small loops and a
    landed therapeutic). Accepts ``state_dependence='unclear'`` so a
    deep-dive that can't call low vs high doesn't drop out.

    Evidence bar is the synthesizer's OVERALL ``confidence`` ruling, NOT
    the deterministic A1-only ``evidence_grade``. That grade scores an
    empty A1 (direct-method) ledger as ``weak`` even when the surface
    call rests on rich A2 (biological-context) evidence — ICAM1 has
    A1=0 / A2=36 (23 strong), grade ``weak`` yet ``confidence='moderate'``
    and ``evidence_grade_summary='supportive_but_indirect'``. Gating on
    the grade excluded ~480 confidently-surface genes. We keep only a
    fail-closed guard on ``evidence_grade`` (never admit
    ``conflicting``); ``confidence in {high, moderate}`` is the real
    bar. Fixing ``evidence_grade`` at source is tracked in issue #131.

    State-dependence is NOT a hard exclusion. A gene with
    ``state_dependence='high'`` still qualifies if it carries a
    constitutive baseline (``low_endogenous_expression is False``). This
    keeps constitutively-expressed-but-further-inducible surface
    proteins in canonical — ICAM1-class: present at low/moderate levels
    in normal tissue (endothelium, epithelium) and strongly upregulated
    by inflammation/oncogenesis — while proteins that reach the surface
    only when induced off a low/absent baseline
    (``low_endogenous_expression is True`` — CTLA4, TNFRSF9/4-1BB) stay
    in the 'Cell-state induced' tier. Rationale: canonical certifies
    *is* it a surface protein (the five evidence/verdict gates), and
    *when* it is surface is carried as the ``state_dependence`` facet
    rather than used to gate membership. The disjunct is additive — it
    only admits high-state-dependence genes, never drops a low/moderate
    one that lacks a constitutive baseline."""
    return (
        # Fail-closed guard only — anything but self-contradictory evidence.
        # The confidence gate below is the real evidence bar (see docstring).
        f.get("evidence_grade") in (
            "direct_multi_method",
            "direct_single_method",
            "supportive_but_indirect",
            "weak",
        )
        and f.get("confidence") in ("high", "moderate")
        and f.get("surface_specificity") in ("surface_dominant", "mixed")
        and (
            f.get("state_dependence") in ("low", "moderate", "unclear")
            or f.get("low_endogenous_expression") is False
        )
        and f.get("surface_accessibility") in ("high", "moderate")
        and f.get("evidence_density") in ("high", "moderate")
    )


def is_low_literature_surface(f: dict[str, Any], db_surface_positive: bool) -> bool:
    """Badge — NOT a tier preset. Flags a NON-canonical gene whose non-surface
    (or below-canonical) verdict is plausibly evidence-limited rather than
    biological: a thin discovery corpus (``n_papers_found < LOW_LIT_PAPERS_MAX``)
    AND an external surface-DB call predicts it surface. Under-studied
    surface candidates worth a targeted re-dive.

    The DB flag is passed via ``db_surface_positive``. The viewer wires this to
    **UniProt** (``catalogRow.db.uniprot``): among the low-lit population UniProt
    is the better predictor — it catches the understudied olfactory/taste-GPCR
    class that SURFY structurally blind-spots, and its unique low-lit additions
    read more surface-leaning by the deep dive's own accessibility/specificity
    (SURFY's skew intracellular). UniProt's localization is itself a hybrid of
    curated evidence + similarity + sequence-feature prediction (signal peptide /
    TM topology), so it is not purely knowledge-based. Taking the flag as an
    argument (rather than reading ``filters``) is why this is a standalone badge
    and not a member of the ``(filters) -> bool`` preset family — the DB call is
    a candidate-universe flag, not part of the deep-dive record.

    Scoped to NON-canonical genes: a gene that already cleared ``passes_canonical``
    doesn't need an evidence-gap caveat, so canonical genes never carry the badge.
    ``n_papers_found`` missing → not flagged (can't establish 'low')."""
    if passes_canonical(f):
        return False
    n = f.get("n_papers_found")
    if n is None:
        return False
    return bool(db_surface_positive) and n < LOW_LIT_PAPERS_MAX


def passes_likely(f: dict[str, Any]) -> bool:
    """Broader shortlist — adds supportive_but_indirect evidence,
    mostly_intracellular specificity (SRC-class lysosomal-exocytosis
    surface, HMGB1-class DAMP release), and high/unclear/null
    state-dep.

    Drops the ECD filter for the same reason Canonical did. Inner-
    leaflet false positives (LYN, BAX) are still excluded here
    because they fail on ``evidence_grade=weak`` AND
    ``surface_accessibility=no``; IZUMO4 (secreted-only) fails the
    same way. The ECD gate was load-bearing only for biology, never
    for defending against the inner-leaflet bucket."""
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
    return True


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
