from accessible_surfaceome.tag_sites.model import tagged_site, TAGGED_SITE_KEYS


def test_tagged_site_has_exact_keys():
    s = tagged_site(
        site_id="TFRC-internal-290-det", gene_symbol="TFRC", uniprot_acc="P02786",
        det_path="surface_loop", site_kind="internal", insert_after_residue=290,
        residue_before="I", residue_after="V", topology_state="O", extracellular=True,
        compartment="extracellular", tag_type="ALFA", tag_length_aa=15,
        plddt=96.0, conservation_rank=7, median_conservation=0.28,
        rationale="ordered surface loop", sources=[{"citation": "det surface_loop"}],
    )
    assert set(s.keys()) == TAGGED_SITE_KEYS
    assert s["provenance"] == "deterministic_computed"
    assert s["confidence"] in ("high", "medium", "low")


def test_literature_only_fields_default_null_for_det():
    s = tagged_site(
        site_id="x", gene_symbol="TFRC", uniprot_acc="P02786",
        det_path="disorder", site_kind="internal", insert_after_residue=100,
        residue_before="A", residue_after="B", topology_state="O",
        extracellular=True, compartment="extracellular",
    )
    assert s["evidence_type"] == "structural inference (disorder path)"
    assert s["plddt"] is None  # not provided
