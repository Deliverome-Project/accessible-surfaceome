"""Guard: every place that names the authors for Zenodo or citation agrees.

Author metadata lives in four places: ``.zenodo.json`` (read by the
GitHub-to-Zenodo code archive), ``CITATION.cff``, ``publish-archive.py``'s seed
metadata, and the data record's new versions, which take their creators from
``.zenodo.json`` via ``canonical_creators()``. They drifted apart: the data
record shipped as "Carlson, Rebecca" with no ORCIDs while the code record said
"Carlson, Rebecca J.". This pins names and ORCIDs to ``.zenodo.json``.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import yaml

from accessible_surfaceome.cloud.record_history.zenodo import (
    canonical_creators,
    rdm_creators,
)

ROOT = Path(__file__).resolve().parents[1]
ORCID = re.compile(r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$")


def _zenodo() -> list[dict]:
    return json.loads((ROOT / ".zenodo.json").read_text())["creators"]


def test_every_zenodo_creator_has_a_valid_orcid() -> None:
    for c in _zenodo():
        assert ORCID.match(c.get("orcid", "")), c


def test_citation_cff_matches_zenodo_json() -> None:
    cff = yaml.safe_load((ROOT / "CITATION.cff").read_text())["authors"]
    got = [
        (
            f"{a['family-names']}, {a['given-names']}",
            a.get("orcid", "").removeprefix("https://orcid.org/"),
        )
        for a in cff
    ]
    assert got == [(c["name"], c["orcid"]) for c in _zenodo()]


def test_publish_archive_seed_creators_match_zenodo_json() -> None:
    src = (ROOT / "scripts/release/publish-archive.py").read_text()
    seed = next(
        n.value
        for n in ast.walk(ast.parse(src))
        if isinstance(n, ast.Assign)
        and any(getattr(t, "id", "") == "SEED_METADATA" for t in n.targets)
    )
    creators = ast.literal_eval(seed)["metadata"]["creators"]
    assert creators == _zenodo()


def test_data_record_versions_take_zenodo_json_creators() -> None:
    assert canonical_creators() == _zenodo()


def test_rdm_creators_keep_names_orcids_and_affiliations() -> None:
    got = [
        (
            f"{c['person_or_org']['family_name']}, {c['person_or_org']['given_name']}",
            c["person_or_org"]["identifiers"][0]["identifier"],
            c["affiliations"][0]["name"],
        )
        for c in rdm_creators()
    ]
    assert got == [(c["name"], c["orcid"], c["affiliation"]) for c in _zenodo()]
