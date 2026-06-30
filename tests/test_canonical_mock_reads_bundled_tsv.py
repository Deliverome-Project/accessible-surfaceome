"""Drift guard: MOCK / synthesized figures must read their bundled TSV.

The failure this prevents (observed 2026-06): a figure whose data is
synthesized or hand-authored (no upstream ground truth) had its
canonical generator ``scripts/<slug>.py`` hardcode or re-synthesize a
dataset *in the script*, while the gist mirror
``data/analysis/figures/make_<slug>.py`` read the bundled per-figure
TSV at ``data/processed/figures/<slug>.tsv``. The two then diverged —
the committed PNG showed one dataset (e.g. 220 mock genes, or a
fictional thousands-scale heatmap) while the published gist shipped a
different one (1,500 genes; the real n=20 matrix). Readers reproducing
from the gist got a figure that didn't match the paper.

For these figures the bundled TSV is the SINGLE SOURCE OF TRUTH —
produced once by ``scripts/build_figure_tsvs.py`` and read by both the
canonical generator and the gist mirror. This test asserts the
canonical actually reads it, so a future edit can't reintroduce an
in-script dataset that silently drifts from the gist.

Scope — only the figures whose data is synthesized/mock (the TSV is
the sole source). Figures whose canonical *computes* from real upstream
data (the catalog, the benchmark TSVs, the per-protein-features table,
or D1) are intentionally excluded: there the per-figure TSV is a
downstream export, and the canonical recomputing from the upstream
truth is correct by design. Those are covered for byte-identity on the
gist side by ``tests/test_figure_gist_data_sync.py`` and for layout by
``tests/test_figure_canonical_mirror_sync.py``.
"""
from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"

# Figures whose canonical generator reads its dedicated per-figure TSV
# (``data/processed/figures/<slug>.tsv``) as the single source of truth,
# so the committed figure can't drift from the gist mirror (which reads
# the same TSV). Two kinds live here:
#   • MOCK / synthesized figures (the TSV is the only data that exists)
#   • real-data figures consolidated onto a dedicated TSV so the
#     cutoff/membership definition lives in ONE place — zero_db_rescues
#     and topology_coverage were moved here when they switched to the
#     optimized-cutoff TSV (their old initial-flag reads from the raw
#     catalog / per-protein-features were the drift hazard).
READS_BUNDLED_TSV = [
    "deep_dive_final_categories",
    "deep_dive_record_richness",
    "evidence_corpus_vs_selected",
    "triage_vs_deep_dive_reason",
    "zero_db_rescues_by_triage",
    "topology_coverage_by_source",
    # Migrated off the triage_bench_db_barplot monolith (2026-06-30): its own
    # canonical now reads the figure TSV, so the model list comes from the data
    # — fixes the opus-4-7 hardcode that shipped empty bars on Supp Fig 1.
    "db_correctness_overall",
]

# Figures whose canonical recomputes from real upstream sources by
# design (documented exemption — NOT covered by this guard). The
# per-figure TSV is a downstream export; the canonical recomputing from
# the upstream truth is correct. Byte-identity on the gist side is
# covered by tests/test_figure_gist_data_sync.py.
COMPUTES_FROM_UPSTREAM = {
    "bench_topology_vs_universe",      # per-protein-features table
    "curator_vs_agent_reason",         # eval bench + mainbench predictions
    "db_vs_sonnet_whole_proteome",     # whole-proteome catalog + cutoffs
    "ensemble_vs_best_db_vs_sonnet",   # whole-proteome catalog + cutoffs
}


@pytest.mark.parametrize("slug", READS_BUNDLED_TSV)
def test_mock_canonical_reads_bundled_tsv(slug: str) -> None:
    """The canonical generator for a mock figure must reference its
    bundled per-figure TSV path — i.e. read the single source of truth
    rather than hardcode the dataset in the script."""
    script = SCRIPTS / f"{slug}.py"
    assert script.is_file(), f"missing canonical generator scripts/{slug}.py"
    src = script.read_text()
    needle = f"data/processed/figures/{slug}.tsv"
    assert needle in src, (
        f"scripts/{slug}.py does not read its bundled TSV ({needle}). "
        f"This figure is MOCK/synthesized — the bundled TSV is the sole "
        f"source of truth and the canonical must read it, or it will "
        f"drift from the gist mirror (which does). Point the render path "
        f"at the TSV instead of hardcoding the dataset."
    )


@pytest.mark.parametrize("slug", READS_BUNDLED_TSV)
def test_mock_canonical_has_no_hardcoded_dataset(slug: str) -> None:
    """Belt-and-suspenders: the in-script dataset constants/helpers that
    caused the original drift must not reappear ANYWHERE in the file —
    not as a call, a definition, a dead helper, or a docstring mention.
    A dead synthesizer is still a drift hazard (a future edit can
    re-wire it), so we ban the tokens outright once a figure is on the
    read-the-bundled-TSV path."""
    src = (SCRIPTS / f"{slug}.py").read_text()
    banned = ["_MOCK_COUNTS", "_PLACEHOLDER_CANONICAL", "_synthesize_mock_data"]
    present = [b for b in banned if b in src]
    assert not present, (
        f"scripts/{slug}.py still references an in-script dataset "
        f"synthesizer/placeholder ({present}). This figure reads its "
        f"bundled TSV — remove the dead synthesis code (and any mention "
        f"of it) so it can't be re-wired and drift from the gist."
    )


def test_mock_and_upstream_lists_are_disjoint_and_complete() -> None:
    """Keep the two lists honest: no slug in both, and every figure with
    a per-figure TSV + a canonical script is classified."""
    overlap = set(READS_BUNDLED_TSV) & COMPUTES_FROM_UPSTREAM
    assert not overlap, f"slug in both lists: {overlap}"
    tsv_dir = REPO_ROOT / "data/processed/figures"
    classified = set(READS_BUNDLED_TSV) | COMPUTES_FROM_UPSTREAM
    for tsv in tsv_dir.glob("*.tsv"):
        slug = tsv.stem
        if (SCRIPTS / f"{slug}.py").is_file() and slug not in classified:
            pytest.fail(
                f"{slug} has a per-figure TSV + a canonical scripts/{slug}.py "
                f"but is in neither READS_BUNDLED_TSV nor COMPUTES_FROM_UPSTREAM. "
                f"Classify it: is the TSV its source (READS_BUNDLED_TSV) or "
                f"does the canonical compute from upstream (COMPUTES_FROM_UPSTREAM)?"
            )
