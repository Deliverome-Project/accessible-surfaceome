"""Guard: published figures must score/gate the two RECALIBRATED databases
(UniProt, CSPA) on their OPTIMIZED cutoffs — EXCEPT Figure 1 (db_overlap_venn),
which deliberately shows the NATIVE, pre-recalibration per-source membership.

Why this guard exists
---------------------
Only UniProt and CSPA were recalibrated against SurfaceBench (UniProt loosened
to admit transmembrane/signal-peptide proteins; CSPA tightened to high-confidence
only). Their optimized membership lives in the columns ``uniprot_optimized`` /
``cspa_optimized`` — a POSITIVE LIST baked from ``db_optimized_cutoffs.tsv`` where
an accession absent from the list contributes 0 (it passed neither tightened
cutoff). GO CC / HPA / SURFY were NOT recalibrated, so their ``*_surface_flag``
is always the correct (and only) column — this guard does not police them.

A prior bug (commit eda4c0ea2) had ``build_candidate_universe_v3`` fall back to
the INITIAL CSPA flag for accessions absent from the optimized-cutoffs positive
list, re-admitting low-confidence cytoplasmic proteins. This test catches the
figure-side analogue: a published figure that silently scores a recalibrated DB
on its ``*_surface_flag`` (pre-recalibration) cutoff instead of ``*_optimized``.

What it checks
--------------
Each published figure ships a self-contained reader-side reproduction script
``data/analysis/figures/make_<slug>.py`` (the "gist mirror"). A mirror reads
only the columns it actually uses, so a reference to a recalibrated-DB INITIAL
flag means the figure *gates* on the native cutoff. Only Figure 1 may do that.
(The big multi-figure canonical generators under ``scripts/`` legitimately
reference both column sets — e.g. the recalibration figure plots the trade-off
and ``triage_bench_db_barplot`` renders both rule sets — so the clean invariant
is enforced on the published reader mirrors, which are what ships.)
"""
from __future__ import annotations

import re
from pathlib import Path

FIGURES_DIR = Path(__file__).resolve().parents[1] / "data/analysis/figures"

# INITIAL (pre-recalibration) flags for the two RECALIBRATED databases. These
# each have a *_optimized counterpart, so using them to gate a figure means the
# figure is on the wrong (native) cutoff. GO/HPA/SURFY *_surface_flag are
# intentionally NOT policed — they were never recalibrated.
RECALIBRATED_INITIAL_FLAGS = ("uniprot_surface_flag", "cspa_surface_flag")
RECALIBRATED_OPTIMIZED_FLAGS = ("uniprot_optimized", "cspa_optimized")

# The ONLY published figure permitted to use the native recalibrated-DB flags:
# Figure 1 (the five-DB overlap Venn), which by design shows each source's
# native, pre-recalibration membership (see its caption + 01_db_overlap_venn.md).
ALLOWED_INITIAL_CUTOFF_FIGURES = {"db_overlap_venn"}

# Published figures that score/gate on UniProt or CSPA membership and therefore
# MUST read the optimized columns (from the figure audits, 2026-06-30).
OPTIMIZED_CUTOFF_FIGURES = {
    "db_correctness_by_class",
    "db_vs_sonnet_whole_proteome",
    "zero_db_rescues_by_triage",
    "ensemble_vs_best_db_vs_sonnet",
    "topology_coverage_by_source",
}


def _slug(mirror: Path) -> str:
    return mirror.name[len("make_"):-len(".py")]


def _mentions(src: str, col: str) -> bool:
    return re.search(rf"\b{re.escape(col)}\b", src) is not None


def test_recalibrated_db_initial_flags_only_in_figure_1():
    """No published-figure mirror except Figure 1 may reference the native
    recalibrated-DB flags — every other figure must be on the optimized cutoff."""
    offenders: dict[str, list[str]] = {}
    for mirror in sorted(FIGURES_DIR.glob("make_*.py")):
        src = mirror.read_text()
        hits = [c for c in RECALIBRATED_INITIAL_FLAGS if _mentions(src, c)]
        if hits and _slug(mirror) not in ALLOWED_INITIAL_CUTOFF_FIGURES:
            offenders[_slug(mirror)] = hits
    assert not offenders, (
        "Published figure(s) reference a recalibrated-DB INITIAL flag and so "
        f"score UniProt/CSPA on the wrong (native) cutoff: {offenders}. "
        "Use uniprot_optimized / cspa_optimized instead. Only Figure 1 "
        "(db_overlap_venn) may use the native pre-recalibration flags; if a new "
        "figure legitimately needs them, add its slug to "
        "ALLOWED_INITIAL_CUTOFF_FIGURES with a comment explaining why."
    )


def test_figure_1_actually_uses_native_flags():
    """Meaningfulness guard: the Figure-1 whitelist must be earned — its mirror
    genuinely uses the native flags, else the test above is vacuous."""
    venn = FIGURES_DIR / "make_db_overlap_venn.py"
    assert venn.exists(), "make_db_overlap_venn.py (Figure 1) is missing"
    src = venn.read_text()
    used = [c for c in RECALIBRATED_INITIAL_FLAGS if _mentions(src, c)]
    assert used == list(RECALIBRATED_INITIAL_FLAGS), (
        f"Figure 1 mirror should use the native flags {RECALIBRATED_INITIAL_FLAGS}; "
        f"found {used}. If Figure 1 moved off native cutoffs, this whitelist is stale."
    )


def test_recalibrated_db_figures_read_optimized_columns():
    """Every figure that scores UniProt/CSPA membership must read an *_optimized
    column (the positive-set membership), not just carry it as passthrough."""
    missing: dict[str, str] = {}
    for slug in sorted(OPTIMIZED_CUTOFF_FIGURES):
        mirror = FIGURES_DIR / f"make_{slug}.py"
        assert mirror.exists(), f"missing published mirror for {slug}"
        src = mirror.read_text()
        if not any(_mentions(src, c) for c in RECALIBRATED_OPTIMIZED_FLAGS):
            missing[slug] = "no uniprot_optimized/cspa_optimized reference"
    assert not missing, (
        f"Recalibrated-DB figures must read the optimized columns: {missing}"
    )
