from accessible_surfaceome.tools._shared.models import (
    DeterministicFeatures,
    Orthologs,
)


def test_orthologs_checked_defaults_false():
    assert Orthologs().checked is False


def test_deterministic_features_checked_flags_default_false():
    fields = DeterministicFeatures.model_fields
    assert "paralogs_checked" in fields
    assert "isoform_topologies_checked" in fields
    assert fields["paralogs_checked"].default is False
    assert fields["isoform_topologies_checked"].default is False


def test_orthologs_checked_roundtrips_true():
    assert Orthologs(checked=True).checked is True
