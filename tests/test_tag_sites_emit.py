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
