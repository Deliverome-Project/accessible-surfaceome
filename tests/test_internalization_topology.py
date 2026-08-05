from accessible_surfaceome.agents.internalization.topology import summarize_topology
from accessible_surfaceome.tools._shared.models import TopologyFeature


def _f(feature_type, description, start, end):
    return TopologyFeature(
        feature_type=feature_type, description=description, start=start, end=end
    )


def test_summarize_counts_tm_and_notes_sides():
    feats = [
        _f("signal_peptide", "", 1, 24),
        _f("transmembrane", "Helical", 646, 668),
        _f("topological_domain", "Extracellular", 25, 645),
        _f("topological_domain", "Cytoplasmic", 669, 1210),
    ]
    out = summarize_topology(feats)
    assert "1 transmembrane" in out
    assert "signal peptide" in out
    assert "extracellular" in out.lower()
    assert "cytoplasmic" in out.lower()


def test_summarize_empty_is_explicit():
    assert summarize_topology([]) == "No UniProt topology features annotated."
