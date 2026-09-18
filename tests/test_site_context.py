from accessible_surfaceome.binders.site_context import (
    exact_ranges,
    site_context,
    validate_feature,
    feature_records,
)


def feature(kind, a, b, description=""):
    return {
        "type": kind,
        "description": description,
        "location": {"start": {"value": a}, "end": {"value": b}},
    }


def protein():
    return {
        "sequence": {"value": "A" * 100},
        "features": [
            feature("Signal", 1, 10),
            feature("Chain", 11, 80),
            feature("Propeptide", 81, 100),
            feature("Lipidation", 80, 80, "GPI-anchor amidated serine"),
        ],
        "comments": [
            {
                "commentType": "SUBCELLULAR LOCATION",
                "subcellularLocations": [
                    {
                        "location": {"value": "Cell membrane"},
                        "topology": {"value": "Lipid-anchor, GPI-anchor"},
                    }
                ],
            }
        ],
    }


def test_gpi_mature_and_removed_segments():
    p = protein()
    assert site_context([20, 70], p) == "extracellular_gpi_mature"
    assert site_context([70, 90], p) == "removed_processing_segment"
    assert site_context([5, 20], p) == "removed_processing_segment"
    assert site_context([101], p) == "invalid_mapping"


def test_cytoplasmic_and_tm_never_promoted():
    p = protein()
    p["features"].append(feature("Topological domain", 30, 40, "Cytoplasmic"))
    assert site_context([35], p).startswith("non_extracellular")
    p["features"].append(feature("Transmembrane", 50, 60))
    assert site_context([55, 70], p) == "membrane_spanning_site"


def test_secreted_is_not_membrane_extracellular():
    p = protein()
    p["features"] = p["features"][:3]
    p["comments"][0]["subcellularLocations"] = [{"location": {"value": "Secreted"}}]
    assert site_context([20, 70], p) == "secreted_mature"
    p["comments"][0]["subcellularLocations"].append(
        {"location": {"value": "Cytoplasm"}}
    )
    assert site_context([20, 70], p).startswith("unknown")


def test_intact_ranges_and_sequence_validation():
    assert exact_ranges("2..2-3..3,5-5") == [(2, 3), (5, 5)]
    assert exact_ranges("2..4-8") == []
    assert validate_feature("2-3,5-5", "CDG", "ACDEG") == ([2, 3, 5], "exact_sequence")
    assert validate_feature("2-3", "DE", "ACDEG")[1] == "sequence_mismatch"
    assert validate_feature("2-3", "-", "ACDEG")[1] == "missing_original_sequence"
    assert validate_feature("4-8", "EG", "ACDEG")[1] == "out_of_bounds"


def test_bare_newlines_do_not_shift_feature_columns(tmp_path):
    p = tmp_path / "features.tsv"
    p.write_text(
        "# Feature AC\tSequence\tDescription\nEBI-1\tAA\n BB\tlabel\ncontinued\nEBI-2\tCC\tother\n"
    )
    rows = list(feature_records(p))
    assert len(rows) == 2 and len(rows[0][1]) == 3
    assert rows[0][1][1] == "AA\n BB"


def test_explicit_ec_cannot_override_removed_propeptide():
    p = protein()
    p["features"].append(feature("Topological domain", 11, 100, "Extracellular"))
    assert site_context([20, 70], p) == "extracellular_explicit"
    assert site_context([85], p) == "removed_processing_segment"


def test_isoform_only_secreted_location_is_not_canonical():
    p = protein()
    p["features"] = p["features"][:3]
    p["comments"] = [
        {
            "commentType": "SUBCELLULAR LOCATION",
            "molecule": "Isoform 2",
            "subcellularLocations": [{"location": {"value": "Secreted"}}],
        }
    ]
    assert site_context([20], p).startswith("unknown")
