"""Enforce that the Python catalog-preset predicates stay in sync with the
TypeScript source of truth (``viewer/lib/catalog-presets.ts``).

The viewer computes preset membership from the TS predicates; the figure
pipeline and the Zenodo membership TSV compute it from the Python mirror. When
the two drift, the published figures disagree with the live catalog — which is
exactly what happened when PR #137 changed the TS canonical rule (gate the
state escape on ``expression_level``, exclude ``tissue_restricted_surface``)
without updating the Python side, so the figures showed canonical=2274 while
the viewer showed 1757.

This test has two layers:

1. **Behavioural fixtures** — representative records (one per tier plus the
   edge cases that actually drifted) with the tier the CURRENT TS rule assigns.
   Locks the Python predicates to concrete expected outputs.

2. **Cross-source invariants** — string-scan BOTH the .py and .ts sources and
   assert the load-bearing rule tokens are present in each. A behavioural
   fixture only catches Python regressions; this layer fails if EITHER file
   drops one of the invariants that drifted before (so a future TS-only edit
   trips the test too, prompting a matching Python change).

The durable fix is to have the Worker compute membership once and serve it as
a gene attribute (so both surfaces read the same value); until that lands,
this test is the guard.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from accessible_surfaceome.release import catalog_presets as cp

REPO_ROOT = Path(__file__).resolve().parents[1]
TS_SRC = REPO_ROOT / "viewer" / "lib" / "catalog-presets.ts"
PY_SRC = REPO_ROOT / "src" / "accessible_surfaceome" / "release" / "catalog_presets.py"
WORKER_SRC = REPO_ROOT / "cloudflare" / "workers" / "surfaceome_api" / "src" / "index.js"


def _base(**over):
    """A record that passes Canonical; override fields per case."""
    f = {
        "surface_call_reason": "classical_surface_receptor",
        "evidence_grade": "direct_multi_method",
        "evidence_grade_summary": "direct_multi_method",
        "confidence": "high",
        "surface_specificity": "surface_dominant",
        "state_dependence": "low",
        "expression_level": "high",
        "surface_accessibility": "high",
        "evidence_density": "high",
        "n_papers_found": 300,
    }
    f.update(over)
    return f


# (label, record, expected deep_dive_tier tuple) — tiers per the CURRENT TS rule.
CASES = [
    ("plain canonical", _base(), ("canonical", None)),
    # Tissue-restricted is HARD-EXCLUDED from canonical → likely + facet.
    (
        "tissue-restricted → likely+facet, NOT canonical",
        _base(surface_call_reason="tissue_restricted_surface", state_dependence="high"),
        ("likely", "cell_type_restricted"),
    ),
    # Lysosomal-exocytosis is hard-excluded from canonical.
    (
        "lysosomal-exocytosis → likely+induced, NOT canonical",
        _base(surface_call_reason="lysosomal_exocytosis", state_dependence="high",
              surface_specificity="mostly_intracellular"),
        ("likely", "induced"),
    ),
    # state=high but moderately expressed → still canonical (expression_level escape).
    (
        "state=high + expression moderate → canonical (expression_level escape)",
        _base(state_dependence="high", expression_level="moderate"),
        ("canonical", None),
    ),
    # state=high + low expression → NOT canonical (fails the escape).
    (
        "state=high + expression low → not canonical",
        _base(state_dependence="high", expression_level="low", surface_call_reason="cell_state_induced",
              surface_specificity="mixed"),
        ("likely", "induced"),
    ),
    # weak A1 grade but supportive holistic summary → canonical (effective grade).
    (
        "weak evidence_grade but supportive summary → canonical",
        _base(evidence_grade="weak", evidence_grade_summary="supportive_but_indirect"),
        ("canonical", None),
    ),
    # weak everywhere + structural reason → NOT canonical but IS likely (carve-out).
    (
        "weak grade + structural reason → likely (weakStructuralOk), not canonical",
        _base(evidence_grade="weak", evidence_grade_summary="weak"),
        ("likely", None),
    ),
    # weak everywhere + NON-structural reason → drops out of likely.
    (
        "weak grade + non-structural reason → below likely",
        _base(evidence_grade="weak", evidence_grade_summary="weak",
              surface_call_reason="cell_state_induced", surface_specificity="mixed",
              surface_accessibility="moderate"),
        ("low", None),
    ),
]


@pytest.mark.parametrize("label,rec,expected", CASES, ids=[c[0] for c in CASES])
def test_python_tier_matches_ts_rule(label, rec, expected):
    assert cp.deep_dive_tier(rec) == expected


def test_canonical_subset_of_likely():
    """Canonical ⊂ Likely must hold for every fixture (a Canonical gene always
    passes Likely — the chips are disjoint bands whose union is the tier)."""
    for label, rec, _ in CASES:
        if cp.passes_canonical(rec):
            assert cp.passes_likely(rec), f"{label}: canonical but not likely"


# --- Cross-source invariants: both files must encode the same load-bearing rules ---

@pytest.fixture(scope="module")
def sources():
    assert TS_SRC.exists(), f"TS source missing: {TS_SRC}"
    assert PY_SRC.exists(), f"Python source missing: {PY_SRC}"
    return TS_SRC.read_text(), PY_SRC.read_text()


INVARIANTS = [
    # (human description, token that must appear in BOTH sources)
    ("canonical excludes tissue_restricted_surface", "tissue_restricted_surface"),
    ("canonical excludes lysosomal_exocytosis", "lysosomal_exocytosis"),
    ("state escape gates on expression_level", "expression_level"),
    ("evidence gate uses the holistic summary", "evidence_grade_summary"),
    ("weak carve-out reason: classical_surface_receptor", "classical_surface_receptor"),
    ("weak carve-out reason: multipass_with_exposed_loops", "multipass_with_exposed_loops"),
    ("weak carve-out reason: gpi_anchored", "gpi_anchored"),
]


@pytest.mark.parametrize("desc,token", INVARIANTS, ids=[i[0] for i in INVARIANTS])
def test_rule_token_present_in_both_sources(sources, desc, token):
    ts, py = sources
    assert token in ts, f"TS source lost invariant: {desc} ({token!r})"
    assert token in py, f"Python source lost invariant: {desc} ({token!r})"


def test_worker_imports_shared_predicates_not_a_clone():
    """The Cloudflare Worker must IMPORT the shared TS predicates, never
    reimplement them — that's what keeps the served deep_dive_tier /
    low_lit_uniprot (and the Zenodo deposit records built from /v1/genes) on
    the SAME rule as the viewer. A re-implemented copy would be a fourth
    un-enforced clone."""
    assert WORKER_SRC.exists(), f"Worker source missing: {WORKER_SRC}"
    src = WORKER_SRC.read_text()
    assert 'from "../../../../viewer/lib/catalog-presets"' in src, (
        "Worker must import predicates from the shared catalog-presets module"
    )
    assert "deepDiveTier" in src and "isLowLiteratureSurface" in src
    # Guard against a re-implemented clone sneaking in.
    assert "function deepDiveTier" not in src, "Worker must not define its own deepDiveTier"
    assert "function passesCanonical" not in src, "Worker must not define its own passesCanonical"


def test_python_no_longer_uses_low_endogenous_escape():
    """The pre-#137 canonical rule gated the state escape on
    ``low_endogenous_expression is False``. That was the drift; guard against
    it creeping back into the Python canonical predicate."""
    py = PY_SRC.read_text()
    # Isolate the passes_canonical RETURN body (skip the docstring, which
    # legitimately explains why low_endogenous_expression is no longer used).
    start = py.index("def passes_canonical")
    ret = py.index("return", start)
    end = py.index("def ", start + 1)
    body = py[ret:end]
    assert "low_endogenous_expression" not in body, (
        "passes_canonical must gate on expression_level, not "
        "low_endogenous_expression (see PR #137 / mirror drift)"
    )
