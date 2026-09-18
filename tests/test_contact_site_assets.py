"""Protect the biological meaning of the contact-only viewer export."""

import importlib.util
import json
from pathlib import Path

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
    assert len(covered) == 1680
