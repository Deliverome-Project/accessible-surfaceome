"""Score the agent against the curated positive controls.

The validation run I did earlier diffed new output against the pipeline's OWN
prior output, which measures churn, not correctness — it scored TMEM123 3->0 as
a win while the one real answer (A33, EndoNB) was missed by both runs.
`data/tag_sites/positive_controls.tsv` carries 16 known-correct residues; that
is the instrument.
"""
from pathlib import Path

from accessible_surfaceome.agents.tag_site.benchmark import (
    load_controls,
    score_predictions,
)

CONTROLS = Path("data/tag_sites/positive_controls.tsv")


def test_controls_load_with_their_truth_residues():
    cs = {c.id: c for c in load_controls(CONTROLS)}
    a16 = cs["A16"]
    assert (a16.gene_symbol, a16.junction, a16.expected_residue) == ("TMEM123", 33, "A")
    assert a16.source_key == "endonb"
    assert cs["A9"].gene_symbol == "ITGB1" and cs["A9"].junction == 101


def test_an_exact_junction_scores_as_a_hit():
    cs = [c for c in load_controls(CONTROLS) if c.id == "A16"]
    rep = score_predictions({"TMEM123": [33]}, cs, tolerance=0)
    assert rep.outcomes["A16"] == "exact"
    assert rep.n_exact == 1 and rep.n_miss == 0


def test_a_nearby_junction_scores_as_near_not_exact():
    cs = [c for c in load_controls(CONTROLS) if c.id == "A16"]
    rep = score_predictions({"TMEM123": [34]}, cs, tolerance=3)
    assert rep.outcomes["A16"] == "near"
    assert rep.n_exact == 0 and rep.n_near == 1


def test_the_signal_peptide_snap_is_scored_a_miss():
    """My snap repair produces TMEM123 A26 — seven residues short of the real
    site, and a candidate the curators removed twice as topology-derived."""
    cs = [c for c in load_controls(CONTROLS) if c.id == "A16"]
    rep = score_predictions({"TMEM123": [26]}, cs, tolerance=3)
    assert rep.outcomes["A16"] == "miss"


def test_a_gene_with_no_prediction_is_a_miss_not_an_error():
    cs = [c for c in load_controls(CONTROLS) if c.id == "A16"]
    rep = score_predictions({}, cs, tolerance=3)
    assert rep.outcomes["A16"] == "miss"
    assert rep.n_miss == 1


def test_recall_counts_each_control_once_even_when_a_gene_repeats():
    """ITGB1 carries four controls at the same junction (ALFA/eGFP/pHluorin/
    HaloTag) — one correct prediction satisfies all four."""
    cs = [c for c in load_controls(CONTROLS) if c.gene_symbol == "ITGB1"]
    assert len(cs) >= 4
    rep = score_predictions({"ITGB1": [101]}, cs, tolerance=0)
    assert rep.n_exact == len(cs)
