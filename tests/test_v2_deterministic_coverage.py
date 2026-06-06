from accessible_surfaceome.audit.v2_deterministic_coverage import (
    FeaturePresence,
    classify_gene,
)


def test_all_present_yields_present():
    p = FeaturePresence(
        canonical=True, isoforms=True, paralogs=True, orthologs=True
    )
    row = classify_gene("EGFR", "P00533", p)
    assert row["canonical_topology_status"] == "present"
    assert row["paralogs_status"] == "present"
    assert row["orthologs_status"] == "present"
    assert row["isoform_topology_status"] == "present"


def test_missing_canonical_is_needs_backfill():
    p = FeaturePresence(
        canonical=False, isoforms=False, paralogs=False, orthologs=False
    )
    row = classify_gene("FOO1", "Q00001", p)
    # Canonical is never "genuinely absent" — every protein has a main sequence.
    assert row["canonical_topology_status"] == "needs-backfill"
    # The others are "needs-backfill" in pass 1 (genuine-absence resolved post-sweep).
    assert row["paralogs_status"] == "needs-backfill"
    assert row["orthologs_status"] == "needs-backfill"
    assert row["isoform_topology_status"] == "needs-backfill"


def test_row_carries_identifiers():
    p = FeaturePresence(True, True, True, True)
    row = classify_gene("EGFR", "P00533", p)
    assert row["hgnc_symbol"] == "EGFR"
    assert row["uniprot_acc"] == "P00533"
