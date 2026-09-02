import pytest
from accessible_surfaceome.tag_sites.control import control_tag_site
from accessible_surfaceome.tag_sites.model import TAGGED_SITE_KEYS
from accessible_surfaceome.tag_sites.tedman import parse_ha_position, map_junction_to_canonical
from accessible_surfaceome.tag_sites.tedman import build_control_sites_for_gene
from accessible_surfaceome.tag_sites.tedman import match_isoform_by_length
from accessible_surfaceome.tag_sites.control import control_isoform_pin


def test_parse_ha_position_nterm():
    assert parse_ha_position("0-1") == 0


def test_parse_ha_position_post_sp():
    assert parse_ha_position("27-28") == 27


def test_parse_ha_position_bad():
    with pytest.raises(ValueError):
        parse_ha_position("garbage")


def test_map_junction_zero_is_bare_nterm():
    r = map_junction_to_canonical(0, "MKTIIALSYIFCLVFA")
    assert r.insert_after_residue is None
    assert r.residue_before is None
    assert r.residue_after == "M"
    assert r.verified is True


def test_map_junction_post_sp_matches_sequence():
    seq = "MKTIIALSYIFCLVFA" + "QDLPPQ"  # residue 16 = A (end of a 16-aa SP)
    r = map_junction_to_canonical(16, seq)
    assert r.insert_after_residue == 16
    assert r.residue_before == "A"       # residue 16
    assert r.residue_after == "Q"        # residue 17
    assert r.residue_label == "A16"
    assert r.verified is True


def test_map_junction_out_of_range_unverified():
    r = map_junction_to_canonical(999, "MKT")
    assert r.verified is False


def test_control_tag_site_shape_and_provenance():
    s = control_tag_site(
        site_id="ADRB2-nterm-tedman", gene_symbol="ADRB2", uniprot_acc="P07550",
        insert_after_residue=None, residue_before=None, residue_after="M",
        pme=1234.5, pme_sd=67.8,
        sources=[{"citation": "Tedman et al. 2026", "doi": "10.1038/s41467-026-76564-7"}],
    )
    assert set(s.keys()) == TAGGED_SITE_KEYS
    assert s["provenance"] == "screen_validated"
    assert s["det_path"] is None
    assert s["site_kind"] == "terminal_n"
    assert s["tag_type"] == "HA"
    assert s["extracellular"] is True
    assert "1234.5" in s["functional_impact_measured"]


def test_build_control_sites_for_gene_bare_nterm():
    row = {"gene_symbol": "ADRB2", "uniprot_acc": "P07550", "junction_after_residue": "",
           "expected_residue": "M", "surface_expression_pme": "1234.5",
           "surface_expression_sd": "67.8", "verified": "true"}
    sites = build_control_sites_for_gene([row], sources=[{"citation": "Tedman et al. 2026"}])
    assert len(sites) == 1
    assert sites[0]["provenance"] == "screen_validated"
    assert sites[0]["site_id"] == "ADRB2-nterm-tedman"
    assert sites[0]["insert_after_residue"] is None
    assert sites[0]["residue_after"] == "M"
    assert "1234.5" in sites[0]["functional_impact_measured"]


def test_build_control_sites_for_gene_post_sp_and_skips_unverified():
    rows = [
        {"gene_symbol": "GIPR", "uniprot_acc": "P48546", "junction_after_residue": "28",
         "expected_residue": "K", "surface_expression_pme": "6435.0",
         "surface_expression_sd": "100.0", "verified": "true"},
        {"gene_symbol": "GIPR", "uniprot_acc": "P48546", "junction_after_residue": "5",
         "expected_residue": "X", "surface_expression_pme": "", "surface_expression_sd": "",
         "verified": "false"},
    ]
    sites = build_control_sites_for_gene(rows, sources=[])
    assert len(sites) == 1  # unverified row skipped
    assert sites[0]["insert_after_residue"] == 28
    assert sites[0]["residue_before"] == "K"
    assert sites[0]["residue_label"] == "K28"


def test_match_isoform_by_length_unique():
    assert match_isoform_by_length(300, [("P1-2", 300), ("P1-3", 250)]) == "P1-2"


def test_match_isoform_by_length_ambiguous_returns_none():
    assert match_isoform_by_length(300, [("P1-2", 300), ("P1-3", 300)]) is None


def test_match_isoform_by_length_excludes_canonical_length():
    assert match_isoform_by_length(300, [("P1-1", 300)], canonical_len=300) is None


def test_match_isoform_by_length_no_match():
    assert match_isoform_by_length(999, [("P1-2", 300)]) is None


def test_control_isoform_pin_shape():
    pin = control_isoform_pin(
        canonical_site_id="X-nterm-tedman", isoform_id="P1-2",
        isoform_residue=5, isoform_len=250, canonical_residue=5, note="PME 100 (-40% vs canonical)",
    )
    assert pin["site_id"] == "X-nterm-tedman::iso::P1-2"
    assert pin["isoform_id"] == "P1-2"
    assert pin["classification"] == "control"
    assert pin["site_kind"] == "terminal_n"
    assert pin["tag_type"] == "HA"
    assert pin["isoform_residue"] == 5
    assert abs(pin["left_pct"] - (5 / 250 * 100)) < 1e-9
    assert pin["note"] == "PME 100 (-40% vs canonical)"
