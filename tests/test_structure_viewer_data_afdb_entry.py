"""Which AFDB entry gets baked into ``viewer/public/structure-viewer/*.json``.

The build script's baked ``pdb_url`` is what the gene page loads before it
resolves anything live, so picking the wrong entry here puts a different —
usually much shorter — sequence under the page's "Canonical" tab. That is
how an external reviewer came to read LRP1's structure as truncated:
``/api/prediction/Q07954`` answers 200 with a single entry
``AF-Q07954-2-F1`` (isoform 2, residues 1-292 of a 4,544-aa protein) and no
canonical model at all, and a positional ``payload[0]`` pick takes it.

Pinned here because the hazards are all invisible in a passing build: the
array order is not a contract, AFDB federates third-party models that reuse
the same bare accession, and a fragmented entry cannot be represented by one
URL.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location(
    "_build_structure_viewer_data",
    ROOT / "scripts" / "build" / "build_structure_viewer_data.py",
)
assert _SPEC is not None and _SPEC.loader is not None
_MOD = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MOD)
extract = _MOD._extract_pdb_url


def entry(entry_id: str, acc: str, url: str, **extra: Any) -> dict[str, Any]:
    return {
        "entryId": entry_id,
        "uniprotAccession": acc,
        "pdbUrl": url,
        "latestVersion": 6,
        **extra,
    }


def test_single_canonical_entry_is_baked() -> None:
    payload = [entry("AF-P12931-F1", "P12931", "canon.pdb")]
    assert extract(payload, "P12931") == ("canon.pdb", 6)


def test_isoform_only_response_bakes_nothing() -> None:
    """LRP1. A 200 whose only model is an alternative isoform.

    ``(None, None)`` makes the viewer resolve live, where the no-model state
    is surfaced honestly instead of a 292-aa isoform being drawn as the
    canonical fold.
    """
    payload = [entry("AF-Q07954-2-F1", "Q07954-2", "isoform2.pdb")]
    assert extract(payload, "Q07954") == (None, None)


def test_canonical_is_picked_even_when_an_isoform_sorts_first() -> None:
    payload = [
        entry("AF-P14209-3-F1", "P14209-3", "iso3.pdb"),
        entry("AF-P14209-2-F1", "P14209-2", "iso2.pdb"),
        entry("AF-P14209-F1", "P14209", "canon.pdb"),
    ]
    assert extract(payload, "P14209") == ("canon.pdb", 6)


def test_afdbs_own_model_beats_a_federated_one_on_the_same_accession() -> None:
    """Observed on CD164/CD99: an externally contributed model (opaque
    ``AF-00000000…`` entry id, provider other than GDM) carries the same bare
    accession. It is a different pipeline's prediction, not the AlphaFold DB
    model the page names, and position does not protect us."""
    payload = [
        entry("AF-0000000015138413", "Q04900", "colabfold.pdb", latestVersion=1),
        entry("AF-Q04900-F1", "Q04900", "afdb.pdb"),
    ]
    assert extract(payload, "Q04900") == ("afdb.pdb", 6)


def test_a_fragmented_entry_bakes_nothing_rather_than_fragment_one() -> None:
    """AFDB splits an entry past its 2,700-residue cap into overlapping
    fragments. One baked URL cannot be a multi-fragment model, and baking F1
    renders the first ~1,400 residues and calls it the protein."""
    payload = [
        entry("AF-Q6ZZZ9-F1", "Q6ZZZ9", "f1.pdb"),
        entry("AF-Q6ZZZ9-F2", "Q6ZZZ9", "f2.pdb"),
        entry("AF-Q6ZZZ9-F3", "Q6ZZZ9", "f3.pdb"),
    ]
    assert extract(payload, "Q6ZZZ9") == (None, None)


def test_complex_predictions_are_not_baked() -> None:
    payload = [entry("AF-P12931-F1", "P12931", "complex.pdb", isComplex=True)]
    assert extract(payload, "P12931") == (None, None)


def test_empty_and_malformed_payloads() -> None:
    assert extract([], "P12931") == (None, None)
    assert extract(None, "P12931") == (None, None)
    assert extract({"not": "a list"}, "P12931") == (None, None)
    assert extract(["not a dict"], "P12931") == (None, None)


def test_non_string_url_and_non_int_version_are_dropped() -> None:
    payload = [entry("AF-P12931-F1", "P12931", "x.pdb")]
    payload[0]["pdbUrl"] = 42
    payload[0]["latestVersion"] = "six"
    assert extract(payload, "P12931") == (None, None)


def test_committed_snapshots_carry_a_first_party_single_fragment_url() -> None:
    """The two committed baked files must not drift to an isoform or a
    fragment URL. Cheap, offline, and catches a bad refresh at review time."""
    import json
    import re

    snap_dir = ROOT / "viewer" / "public" / "structure-viewer"
    paths = sorted(snap_dir.glob("*.json"))
    assert paths, "no baked structure-viewer snapshots found"
    for path in paths:
        rec = json.loads(path.read_text())
        url = rec.get("pdb_url")
        if url is None:
            continue
        acc = rec["uniprot_acc"]
        assert re.fullmatch(
            rf"https://alphafold\.ebi\.ac\.uk/files/AF-{re.escape(acc)}-F1-model_v\d+\.pdb",
            url,
        ), f"{path.name} baked an unexpected AFDB URL: {url}"
