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
