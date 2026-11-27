"""Tests for cached rodent ortholog frame resolution and UniProt name lookup."""

from __future__ import annotations

from accessible_surfaceome.agents.tag_site.frames import Frame, resolve
from accessible_surfaceome.agents.tag_site.ortholog_frames import (
    fetch_rodent_ortholog_frames,
    fetch_uniprot_names_cached,
)
from accessible_surfaceome.tools._shared.http import CachedHTTP


class _FakeHTTP(CachedHTTP):
    def __init__(self, responses: dict[str, object]):
        self._responses = responses

    def get_json(self, url: str, *, source: str, ttl_days: int = 30, **kwargs):  # type: ignore[override]
        for key, val in self._responses.items():
            if key in url:
                return val
        return {}


def test_fetch_rodent_ortholog_frames_enables_named_rat_frame_validation() -> None:
    # Human sequence has 5-aa N-terminal insertion compared to rat KCC2b-like ortholog.
    rat_seq = "M" + "A" * 20 + "KDTYGHWPLMNVQRS" + "A" * 30
    human_seq = "MGGGG" + "A" * 20 + "KDTYGHWPLMNVQRS" + "A" * 30

    http = _FakeHTTP(
        {
            "uniprotkb/search": {
                "results": [
                    {
                        "primaryAccession": "Q63633",
                        "organism": {"taxonId": 10116},
                        "sequence": {"value": rat_seq},
                        "features": [],
                    }
                ]
            }
        }
    )
    orthos = fetch_rodent_ortholog_frames("SLC12A5", http=http, exclude_sequences={human_seq})
    assert len(orthos) == 1
    assert orthos[0].label == "ortholog:rat:Q63633"
    assert orthos[0].family == "ortholog"

    frames = [Frame(label="member", sequence=human_seq, offset=0), *orthos]
    # Position 22 in rat_seq is 'K', which maps to 26 in human_seq.
    res = resolve(
        "An HA tag was inserted after Lys-22 of the rat KCC2b subunit.",
        frames=frames,
        reference_label="member",
        target=26,
    )
    assert res.validating_hit is not None
    assert res.validating_hit.frame_label == "ortholog:rat:Q63633"
    assert res.validating_hit.reference_position == 26


def test_fetch_uniprot_names_cached_extracts_names_and_sp() -> None:
    http = _FakeHTTP(
        {
            "Q9UGI6.json": {
                "proteinDescription": {
                    "recommendedName": {
                        "fullName": {"value": "Small conductance calcium-activated potassium channel protein 3"},
                        "shortNames": [{"value": "SK3"}],
                    },
                    "alternativeNames": [
                        {"fullName": {"value": "KCa2.3"}, "shortNames": [{"value": "SKCa3"}]}
                    ],
                },
                "genes": [{"synonyms": [{"value": "SKCA3"}]}],
                "features": [{"type": "Signal", "location": {"end": {"value": 24}}}],
            }
        }
    )
    name, cands, sp = fetch_uniprot_names_cached("Q9UGI6", http=http)
    assert "potassium channel protein 3" in name
    assert "SK3" in cands and "KCa2.3" in cands and "SKCA3" in cands
    assert sp == 24


def test_sync_l1_internal_topology_parses_3line_and_verifies_sha(tmp_path) -> None:
    import hashlib
    import importlib.util
    import pytest

    from accessible_surfaceome.agents.tag_site.member_frames import Member
    from accessible_surfaceome.paths import REPO_ROOT

    spec = importlib.util.spec_from_file_location(
        "sync_l1_internal_topology_to_d1",
        REPO_ROOT / "scripts/cloud/sync_l1_internal_topology_to_d1.py",
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    import sys

    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)

    seq = "M" * 5 + "L" * 10 + "A" * 8 + "V" * 10 + "K" * 5
    topo = "I" * 5 + "M" * 10 + "O" * 8 + "M" * 10 + "I" * 5
    sha = hashlib.sha256(seq.encode()).hexdigest()
    p = tmp_path / "sample.3line"
    p.write_text(f">form001|ATP1A2|ENST00000969831 | TM\n{seq}\n{topo}\n", encoding="utf-8")

    entries = mod.parse_generic_3line(p, rel_root=tmp_path)
    assert len(entries) == 1
    assert entries[0].sequence_sha256 == sha

    m = Member(
        candidate_id="l1-p3227",
        library="l1",
        candidate_set="isoform",
        species="human",
        gene_symbol="ATP1A2",
        topology_acc="ATP1A2:ENST00000969831",
        topology_cohort="human_isoforms",
        sequence_sha256=sha,
        ordered_length_aa=len(seq),
        tm_count=2,
        longest_inter_tm_ecto_run_aa=8,
        longest_ecto_run_aa=8,
        longest_ecto_run_start=16,
        longest_ecto_run_position="inter_tm",
        placement="internal",
        gpi_rerouted=False,
        shed_risk="none",
    )
    row = mod.build_topology_row(
        m, entries[0], hgnc_id="HGNC:800", canonical_uniprot="P50993"
    )
    assert row["cohort"] == "human_isoforms"
    assert row["uniprot_acc"] == "P50993"
    assert row["uniprot_acc_full"] == "ATP1A2:ENST00000969831"
    assert row["tm_helix_count"] == 2
    assert row["ecd_length_residues"] == 8
    assert row["predicted_surface_membrane"] == 1

    from dataclasses import replace

    bad = replace(m, sequence_sha256="0" * 64)
    with pytest.raises(ValueError, match="sha256 mismatch"):
        mod.build_topology_row(bad, entries[0], hgnc_id=None, canonical_uniprot=None)


def test_prior_state_never_treats_deterministic_predictions_as_covered() -> None:
    import importlib.util
    import sys

    from accessible_surfaceome.paths import REPO_ROOT

    spec = importlib.util.spec_from_file_location(
        "enrich_tag_site_lit_test",
        REPO_ROOT / "scripts/enrich_tag_site_lit.py",
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)

    seen_sql: list[str] = []

    class _FakeD1:
        def query(self, sql: str, params=None):
            seen_sql.append(sql)
            return []

    mod.prior_state("AQP4", pri=_FakeD1(), pub=_FakeD1())
    pub_sql = next(s for s in seen_sql if "tag_site_public" in s)
    assert "provenance IN ('literature_retrieved', 'literature_enriched')" in pub_sql
