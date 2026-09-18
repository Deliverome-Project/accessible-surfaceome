"""Protect the biological meaning of the contact-only viewer export."""

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "contact_assets", ROOT / "scripts/audit/build_contact_site_assets.py"
)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_indirect_evidence_never_becomes_contacts():
    for tier in ("intact_binding_region", "intact_mutation_effect"):
        assert module.normalize({"tier": tier}) is None
    for context in ("invalid_mapping", "removed_processing_segment"):
        assert (
            module.normalize({"tier": "existing_reclassified", "context": context})
            is None
        )


def test_export_identity_numbering_and_coverage():
    folder = ROOT / "viewer/public/data/contact-sites"
    genes = {}
    covered = set()
    for path in folder.glob("[0-9a-f][0-9a-f].json"):
        shard = json.loads(path.read_text())
        for acc, gene in shard.items():
            assert sum(map(ord, acc)) % 64 == int(path.stem, 16)
            assert gene["hgnc_id"] not in genes
            genes[gene["hgnc_id"]] = acc
            for site in gene["sites"]:
                assert site["positions"] == sorted(set(site["positions"]))
                assert site["positions"][0] > 0
                assert site["source"] != "IntAct"
                assert not site["reference"] or site["reference"].startswith("https://")
                covered.add(gene["hgnc_id"])
    assert len(genes) == 5106
    assert len(covered) == 1685


def test_reviewed_chemicals_keep_only_validated_pairs(monkeypatch, tmp_path):
    rows = list(module.reviewed_chemical_rows())
    expected = {"O95477", "Q07075", "P42262", "Q9ULK0", "Q9HB14"}
    assert {row["uniprot_acc"] for row in rows} == expected
    assert all(not row["mapping_issues"] for row in rows)
    for acc in expected:
        path = (
            ROOT
            / "viewer/public/data/contact-sites"
            / f"{sum(map(ord, acc)) % 64:02x}.json"
        )
        sites = json.loads(path.read_text())[acc]["sites"]
        assert sites and all(site["category"] != "unclassified" for site in sites)
        assert all(site["context"] == "extracellular_explicit" for site in sites)
        if acc == "Q9HB14":
            assert all("unpublished" in site["confidence"] for site in sites)
        if acc == "O95477":
            assert all(
                "chemical identity uncertain" in site["confidence"] for site in sites
            )

    # A mutated contact must not enter this canonical-only acceptance route.
    rejected = dict(rows[0], mapping_issues=[["A", "205", "ALA", "canonical 205:T"]])
    (tmp_path / "reviewed_chemical_contacts.json").write_text(
        json.dumps({"records": [rejected]})
    )
    monkeypatch.setattr(module, "INPUT", tmp_path)
    with pytest.raises(ValueError, match="valid mappings"):
        list(module.reviewed_chemical_rows())


def test_egfr_has_named_egf_contacts():
    acc = "P00533"
    path = (
        ROOT
        / "viewer/public/data/contact-sites"
        / f"{sum(map(ord, acc)) % 64:02x}.json"
    )
    sites = json.loads(path.read_text())[acc]["sites"]
    egf = [s for s in sites if s["partner"] == "P01133"]
    assert len(egf) == 10
    assert all(s["partner_label"] == "EGF" for s in egf)
    assert all(s["context"] == "extracellular_explicit" for s in egf)
    assert any(s["pdb"] == "1ivo" and len(s["positions"]) == 37 for s in egf)


def test_structure_specific_review_overrides_parent_independent_of_order():
    parent = dict(
        uniprot_acc="P00001",
        names=["Parent Fab"],
        pdb="",
        canonical_name="Parent",
        category="therapeutic",
        reference="https://example.org/parent",
        reason="Parent identity",
        exclude_from_overview=False,
    )
    variant = dict(parent, pdb="1abc", canonical_name="Variant", category="tool")
    for rules in ([parent, variant], [variant, parent]):
        site = dict(
            partner="Parent Fab", pdb="1abc", source="AACDB", category="unclassified"
        )
        module.apply_partner_review(
            site,
            "P00001",
            dict(targets=["P00001"], rules=rules, review_date="2026-09-18"),
            {},
        )
        assert site["canonical_partner_label"] == "Variant"
        assert site["category"] == "tool"


def test_conflicting_reviews_fail_instead_of_silently_relabeling():
    import pytest

    rule = dict(
        uniprot_acc="P00001",
        names=["Clone Fab"],
        pdb="1abc",
        canonical_name="First",
        category="tool",
        reference="https://example.org/first",
        reason="Identity",
        exclude_from_overview=False,
    )
    site = dict(
        partner="Clone Fab", pdb="1abc", source="AACDB", category="unclassified"
    )
    reviews = dict(
        targets=["P00001"],
        rules=[rule, dict(rule, canonical_name="Second")],
        review_date="2026-09-18",
    )
    with pytest.raises(ValueError, match="Conflicting contact reviews"):
        module.apply_partner_review(site, "P00001", reviews, {})


def test_overnight_review_preserves_every_original_observation():
    baseline = json.loads(
        (
            ROOT
            / "data/analysis/deep_dive_binding_sites/contact_review_preservation.json"
        ).read_text()
    )
    folder = ROOT / "viewer/public/data/contact-sites"
    for gene in baseline["proteins"]:
        acc = gene["uniprot_acc"]
        shard = f"{sum(map(ord, acc)) % 64:02x}.json"
        sites = json.loads((folder / shard).read_text())[acc]["sites"]
        values = sorted(
            json.dumps(
                {key: site.get(key) for key in baseline["fields"]},
                sort_keys=True,
                separators=(",", ":"),
            )
            for site in sites
        )
        assert len(values) == gene["observations"], acc
        assert (
            hashlib.sha256("\n".join(values).encode()).hexdigest()
            == gene["original_fields_sha256"]
        ), acc


def test_every_curated_rule_matches_retained_source_evidence():
    reviews = json.loads(
        (
            ROOT
            / "data/analysis/deep_dive_binding_sites/reviewed_contact_partners.json"
        ).read_text()
    )
    genes = {}
    for path in (ROOT / "viewer/public/data/contact-sites").glob(
        "[0-9a-f][0-9a-f].json"
    ):
        genes.update(json.loads(path.read_text()))
    for rule in reviews["rules"]:
        acc = rule["uniprot_acc"]
        matched = False
        for original in genes[acc]["sites"]:
            site = dict(original)
            site.pop("review_date", None)
            module.apply_partner_review(
                site,
                acc,
                dict(targets=[acc], rules=[rule], review_date=reviews["review_date"]),
                {},
            )
            if "review_date" in site:
                matched = True
                break
        assert matched, (acc, rule["names"], rule["pdb"])
