"""Unit tests for the provenance utility module.

These tests validate the in-memory builder/validator, independent of
any figure files on disk.
"""
from __future__ import annotations

import json
from typing import Any

import pytest

from accessible_surfaceome._provenance import (
    SCHEMA_VERSION,
    ProvenanceError,
    build_provenance,
    validate_provenance,
)


def _minimal_fields() -> dict[str, Any]:
    return {
        "title": "M1 surface DB overlap — 5-way Venn",
        "gist_url": "https://gist.github.com/beccajcarlson/d655abfc9c7deeaff1cfbe584de96ffa",
        "swhid": "swh:1:snp:0000000000000000000000000000000000000000",
        "repo": "Deliverome-Project/accessible-surfaceome",
        "repo_path": "scripts/figures/triage_bench_db_venn.py",
        "repo_ref": "898c743d9df4ec7497e7424b80d3408e5ad07c41",
        "data": [
            {
                "url": "https://raw.githubusercontent.com/Deliverome-Project/accessible-surfaceome/898c743d9df4ec7497e7424b80d3408e5ad07c41/data/processed/candidate_universe/candidate_universe.tsv",
                "sha256": "0" * 64,
            }
        ],
    }


def test_build_provenance_includes_schema_version() -> None:
    blob = build_provenance(**_minimal_fields())
    assert blob["schema_version"] == SCHEMA_VERSION


def test_validate_provenance_accepts_minimal() -> None:
    validate_provenance(build_provenance(**_minimal_fields()))


def test_validate_provenance_rejects_missing_schema_version() -> None:
    blob = dict(_minimal_fields())
    blob.pop("schema_version", None)
    with pytest.raises(ProvenanceError, match="schema_version"):
        validate_provenance(blob)


def test_validate_provenance_rejects_short_repo_ref() -> None:
    fields = _minimal_fields()
    fields["repo_ref"] = "main"
    with pytest.raises(ProvenanceError, match="repo_ref must be a 40-char hex commit SHA"):
        validate_provenance(build_provenance(**fields))


def test_validate_provenance_rejects_swhid_with_wrong_prefix() -> None:
    fields = _minimal_fields()
    fields["swhid"] = "not-a-swhid"
    with pytest.raises(ProvenanceError, match="swhid must start with"):
        validate_provenance(build_provenance(**fields))


def test_validate_provenance_requires_some_durable_identifier() -> None:
    fields = _minimal_fields()
    fields["swhid"] = None
    fields["doi"] = None
    fields["repo_ref"] = None
    with pytest.raises(ProvenanceError, match="durable identifier"):
        validate_provenance(build_provenance(**fields))


def test_validate_provenance_accepts_doi_only() -> None:
    fields = _minimal_fields()
    fields["swhid"] = None
    fields["repo_ref"] = None
    fields["doi"] = "10.5281/zenodo.99999999"
    validate_provenance(build_provenance(**fields))


def test_validate_provenance_accepts_data_with_swhid_and_doi() -> None:
    fields = _minimal_fields()
    fields["data"] = [
        {
            "url": fields["data"][0]["url"],
            "sha256": "a" * 64,
            "swhid": "swh:1:cnt:" + "a" * 40,
            "doi": "10.5281/zenodo.42",
        }
    ]
    validate_provenance(build_provenance(**fields))


def test_validate_provenance_rejects_bad_data_swhid() -> None:
    fields = _minimal_fields()
    fields["data"] = [{"url": fields["data"][0]["url"], "swhid": "not-a-swhid"}]
    with pytest.raises(ProvenanceError, match=r"data\[0\]\.swhid"):
        validate_provenance(build_provenance(**fields))


def test_validate_provenance_rejects_bad_data_doi() -> None:
    fields = _minimal_fields()
    fields["data"] = [{"url": fields["data"][0]["url"], "doi": "not-a-doi"}]
    with pytest.raises(ProvenanceError, match=r"data\[0\]\.doi"):
        validate_provenance(build_provenance(**fields))


def test_build_provenance_round_trips_through_json() -> None:
    blob = build_provenance(**_minimal_fields())
    serialized = json.dumps(blob, separators=(",", ":"))
    deserialized = json.loads(serialized)
    validate_provenance(deserialized)
    assert deserialized == blob
