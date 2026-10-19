"""The batch driver must source the signal-peptide cleavage site from UniProt's
curated ``Signal`` feature, not from DeepTMHMM's prediction.

They disagree by 1-3 residues on a real fraction of genes (LDLR: predicted 24,
curated 21). An N-terminal tag placed before the true cleavage site is carried
off with the peptide, so the curated number is the one that must reach both the
prompt landmarks and the geometry gate.
"""
import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "regenerate_tag_site_lit",
    Path(__file__).resolve().parents[1] / "scripts/regenerate_tag_site_lit.py",
)
assert _spec is not None and _spec.loader is not None
regen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(regen)


def test_reads_the_curated_signal_peptide_end():
    entry = {"features": [
        {"type": "Chain", "location": {"start": {"value": 22}, "end": {"value": 860}}},
        {"type": "Signal", "location": {"start": {"value": 1}, "end": {"value": 21}}},
    ]}
    assert regen.signal_peptide_end_from_entry(entry) == 21


def test_returns_zero_when_the_entry_annotates_no_signal_peptide():
    entry = {"features": [
        {"type": "Transmembrane", "location": {"start": {"value": 68}, "end": {"value": 88}}},
    ]}
    assert regen.signal_peptide_end_from_entry(entry) == 0


def test_returns_zero_on_a_malformed_or_empty_entry():
    assert regen.signal_peptide_end_from_entry({}) == 0
    assert regen.signal_peptide_end_from_entry({"features": [{"type": "Signal"}]}) == 0


# --- merging literature sites into a tag-site record ---------------------------
#
# 1,805 of the 2,344 FG-library genes have no committed tag-sites JSON, so a
# driver that can only UPDATE existing files cannot reach most of the library.

def _lit(site_id, res):
    return {"site_id": site_id, "provenance": "literature_retrieved",
            "insert_after_residue": res, "gene_symbol": "X"}


def _det(site_id):
    return {"site_id": site_id, "provenance": "deterministic_computed",
            "gene_symbol": "X"}


def test_merge_swaps_literature_sites_and_keeps_everything_else():
    existing = {
        "has_data": True, "gene_symbol": "X", "uniprot_acc": "Q0",
        "sites": [_det("X-det-1"), _lit("X-old-lit", 10)],
        "isoform_pins": [{"site_id": "p1"}], "ortholog_pins": [{"site_id": "p2"}],
    }
    out = regen.merge_lit_sites(existing, [_lit("X-new-lit", 20)],
                                symbol="X", uniprot_acc="Q0")
    provs = sorted(s["provenance"] for s in out["sites"])
    assert provs == ["deterministic_computed", "literature_retrieved"]
    assert [s["site_id"] for s in out["sites"]] == ["X-det-1", "X-new-lit"]  # sorted
    assert out["isoform_pins"] == [{"site_id": "p1"}]   # pins untouched
    assert out["ortholog_pins"] == [{"site_id": "p2"}]
    assert out["has_data"] is True


def test_merge_creates_a_record_for_a_gene_with_no_existing_file():
    out = regen.merge_lit_sites(None, [_lit("X-lit-1", 20)],
                                symbol="X", uniprot_acc="Q0")
    assert out["gene_symbol"] == "X"
    assert out["uniprot_acc"] == "Q0"
    assert out["has_data"] is True
    assert [s["site_id"] for s in out["sites"]] == ["X-lit-1"]
    assert out["isoform_pins"] == [] and out["ortholog_pins"] == []


def test_merge_marks_has_data_false_when_a_new_gene_yields_no_sites():
    """A gene with no qualifying published insertion is a real, expected answer —
    it must still produce a valid record, not an error."""
    out = regen.merge_lit_sites(None, [], symbol="X", uniprot_acc="Q0")
    assert out["has_data"] is False
    assert out["sites"] == []
