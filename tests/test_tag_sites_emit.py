import json

from accessible_surfaceome.tag_sites.emit import emit_tag_sites_json
from accessible_surfaceome.tag_sites.model import tagged_site


def _site(site_id, det_path="disorder"):
    return tagged_site(
        site_id=site_id, gene_symbol="TFRC", uniprot_acc="P02786",
        det_path=det_path, site_kind="internal", insert_after_residue=100,
        residue_before="A", residue_after="B", topology_state="O",
        extracellular=True, compartment="extracellular",
    )


def test_writes_file_with_has_data_and_keys(tmp_path):
    out = emit_tag_sites_json("TFRC", "P02786", [_site("a")], out_dir=tmp_path)
    assert out["has_data"] is True and out["gene_symbol"] == "TFRC"
    on_disk = json.loads((tmp_path / "TFRC.json").read_text())
    assert on_disk["uniprot_acc"] == "P02786" and len(on_disk["sites"]) == 1


def test_merges_by_site_id_new_wins(tmp_path):
    emit_tag_sites_json("TFRC", "P02786", [_site("a"), _site("b")], out_dir=tmp_path)
    # a second run adds "c" and updates "a"; b survives, nothing is clobbered
    updated_a = _site("a", det_path="surface_loop")
    emit_tag_sites_json("TFRC", "P02786", [updated_a, _site("c")], out_dir=tmp_path)
    on_disk = json.loads((tmp_path / "TFRC.json").read_text())
    by_id = {s["site_id"]: s for s in on_disk["sites"]}
    assert set(by_id) == {"a", "b", "c"}
    assert by_id["a"]["det_path"] == "surface_loop"  # new wins


def test_empty_sites_marks_has_data_false(tmp_path):
    out = emit_tag_sites_json("EMPTY", "P00000", [], out_dir=tmp_path)
    assert out["has_data"] is False


def test_isoform_pins_round_trip_and_merge(tmp_path):
    pin_a = {"site_id": "X-surface_loop-100::iso::X-2", "isoform_id": "X-2",
             "classification": "shared", "left_pct": 50.0}
    emit_tag_sites_json("TFRC", "P02786", [_site("a")], out_dir=tmp_path, isoform_pins=[pin_a])
    on_disk = json.loads((tmp_path / "TFRC.json").read_text())
    assert on_disk["isoform_pins"] == [pin_a]
    # a second run merges pins by site_id (new wins), preserving existing sites
    pin_a2 = {**pin_a, "classification": "unique"}
    pin_b = {"site_id": "X-surface_loop-100::iso::X-3", "isoform_id": "X-3",
             "classification": "unique", "left_pct": 20.0}
    emit_tag_sites_json("TFRC", "P02786", [], out_dir=tmp_path, isoform_pins=[pin_a2, pin_b])
    on_disk = json.loads((tmp_path / "TFRC.json").read_text())
    by_id = {p["site_id"]: p for p in on_disk["isoform_pins"]}
    assert set(by_id) == {pin_a["site_id"], pin_b["site_id"]}
    assert by_id[pin_a["site_id"]]["classification"] == "unique"  # new wins
    assert len(on_disk["sites"]) == 1  # existing site preserved
