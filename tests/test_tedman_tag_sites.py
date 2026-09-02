import pytest
from accessible_surfaceome.tag_sites.control import control_tag_site
from accessible_surfaceome.tag_sites.model import TAGGED_SITE_KEYS
from accessible_surfaceome.tag_sites.tedman import parse_ha_position, map_junction_to_canonical


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
