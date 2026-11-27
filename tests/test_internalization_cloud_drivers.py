"""Unit tests for internalization D1 read-back-merge helpers and Modal driver guards."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest

from accessible_surfaceome.agents.internalization.models import (
    LiteratureTrack,
    ModelPriorTrack,
)
from accessible_surfaceome.cloud.d1_client import D1Client
from accessible_surfaceome.cloud.internalization import (
    read_existing_literature,
    read_existing_model_priors,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


class _FakeD1:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows
        self.queries: list[tuple[str, list[Any]]] = []

    def query(self, sql: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
        self.queries.append((sql, list(params or [])))
        return list(self._rows)


def _sample_lit_track() -> LiteratureTrack:
    return LiteratureTrack(
        model="claude-sonnet-5-5",
        overall_grade="high",
        overall_confidence="high",
        predominant_fate="recycles",
        has_primary_or_invivo_evidence=True,
        n_observations=3,
        n_papers_discovered=12,
        n_papers_fetched=4,
    )


def _sample_prior_track() -> ModelPriorTrack:
    return ModelPriorTrack(
        model="claude-opus-5-5",
        overall_grade="high",
        overall_confidence="moderate",
        model_reasoning="YTRF cytoplasmic sorting motif in canonical N-terminal ICD.",
        per_isoform=[],
    )


def test_read_existing_literature_absent_row_returns_none() -> None:
    d1 = cast(D1Client, _FakeD1([]))
    assert read_existing_literature(d1, "TFRC") is None


def test_read_existing_literature_no_lit_returns_none() -> None:
    d1 = cast(D1Client, _FakeD1([{"has_literature": 0, "lit_json": None}]))
    assert read_existing_literature(d1, "A2ML1") is None


def test_read_existing_literature_preserves_full_track() -> None:
    lit = _sample_lit_track()
    d1 = cast(D1Client, _FakeD1([{"has_literature": 1, "lit_json": lit.model_dump_json()}]))
    got = read_existing_literature(d1, "TFRC")
    assert got is not None
    assert got.overall_grade == "high"
    assert got.overall_confidence == "high"
    assert got.predominant_fate == "recycles"
    assert got.has_primary_or_invivo_evidence is True
    assert got.n_observations == 3


def test_read_existing_literature_refuses_to_clobber_when_json_missing() -> None:
    d1 = cast(D1Client, _FakeD1([{"has_literature": 1, "lit_json": None}]))
    with pytest.raises(RuntimeError, match="Refusing to clobber TFRC"):
        read_existing_literature(d1, "TFRC")


def test_read_existing_model_priors_absent_or_empty_returns_empty() -> None:
    assert read_existing_model_priors(cast(D1Client, _FakeD1([])), "TFRC") == []
    assert (
        read_existing_model_priors(cast(D1Client, _FakeD1([{"seq_model": "", "mp_json": None}])), "TFRC")
        == []
    )


def test_read_existing_model_priors_preserves_opus55_prior() -> None:
    prior = _sample_prior_track()
    raw = json.dumps([prior.model_dump(mode="json")])
    d1 = cast(D1Client, _FakeD1([{"seq_model": "claude-opus-5-5", "mp_json": raw}]))
    got = read_existing_model_priors(d1, "TFRC")
    assert len(got) == 1
    assert got[0].model == "claude-opus-5-5"
    assert got[0].overall_grade == "high"


def test_read_existing_model_priors_refuses_to_clobber_when_json_missing() -> None:
    d1 = cast(D1Client, _FakeD1([{"seq_model": "claude-opus-5-5", "mp_json": None}]))
    with pytest.raises(RuntimeError, match="Refusing to clobber TFRC"):
        read_existing_model_priors(d1, "TFRC")


@pytest.mark.parametrize(
    "rel_path",
    [
        "modal/internalization_lit_app.py",
        "modal/internalization_seq_app.py",
    ],
)
def test_modal_internalization_apps_guard_secrets_and_expose_cloud_driver(rel_path: str) -> None:
    src = (REPO_ROOT / rel_path).read_text(encoding="utf-8")
    for secret_glob in ('".env"', '".env.*"', '"**/wrangler.toml"'):
        assert secret_glob in src, f"{rel_path} missing {secret_glob} in add_local_dir(ignore=...)"
    assert "def driver(" in src, f"{rel_path} missing cloud-resident driver() entrypoint"
    assert "read_existing_" in src, f"{rel_path} must read-back-merge before D1 publish"
