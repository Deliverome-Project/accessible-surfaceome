"""Tests for the public-D1 deterministic-features loader.

Specifically covers the ``_fetch_paralogs`` + ``_fetch_orthologs`` paths
after the topology bars were threaded through to ParalogEntry +
OrthologEntry: when the LEFT JOIN against ``topology_public`` hits, the
per-residue topology + categorical label populate; when it misses
(paralog whose canonical isn't in the cohort yet), the loader
gracefully returns ``per_residue_topology=None`` rather than dropping
the row.

The Cloudflare HTTP API is mocked at the ``_query_public`` boundary
inside the module under test — same monkeypatch pattern used by
``tests/test_topology_isoform_resolution.py``. No real network calls.
"""
from __future__ import annotations

import pytest

from accessible_surfaceome.agents.surfaceome_v1 import d1_deterministic
from accessible_surfaceome.tools._shared.models import OrthologEntry, ParalogEntry


# ---------------------------------------------------------------------------
# _latest_topology_version_for_cohort — per-cohort version resolution
# ---------------------------------------------------------------------------


def test_per_cohort_version_picks_release_match(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cohort exists under multiple versions; pick the one the
    topology_release table lists most recently. Scenario: 2026-05-25
    isoforms-only sweep means topo_2026_05_25 has human_isoforms but
    not human_canonical; querying for human_canonical should return
    topo_2026_05_16 (the older release that does carry it)."""
    calls: list[tuple[str, list]] = []

    def fake_query(sql: str, params: list) -> list[dict]:
        calls.append((sql, params))
        if "topology_public WHERE cohort" in sql:
            # human_canonical exists in two versions
            return [
                {"topology_version": "topo_2026_05_16"},
                {"topology_version": "topo_test_optA_full"},
            ]
        if "topology_release" in sql:
            # Release order: newest first. topo_2026_05_25 wins overall
            # but isn't in the cohort set; topo_2026_05_16 is and is
            # the next-newest.
            return [
                {"topology_version": "topo_2026_05_25"},
                {"topology_version": "topo_2026_05_16"},
                {"topology_version": "topo_test_optA_full"},
            ]
        return []

    monkeypatch.setattr(d1_deterministic, "_query_public", fake_query)
    assert (
        d1_deterministic._latest_topology_version_for_cohort("human_canonical")
        == "topo_2026_05_16"
    )
    # Sanity: both queries fired (DISTINCT cohort + release lookup).
    assert any("WHERE cohort" in sql for sql, _ in calls)
    assert any("topology_release" in sql for sql, _ in calls)


def test_per_cohort_version_returns_empty_when_cohort_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cohort not present in topology_public → empty string (caller's
    short-circuit prevents the JOIN from running)."""

    def fake_query(sql: str, params: list) -> list[dict]:
        if "topology_public" in sql:
            return []  # no rows for this cohort
        if "topology_release" in sql:
            return [{"topology_version": "topo_2026_05_25"}]
        return []

    monkeypatch.setattr(d1_deterministic, "_query_public", fake_query)
    assert (
        d1_deterministic._latest_topology_version_for_cohort("nonexistent_cohort")
        == ""
    )


def test_per_cohort_version_falls_back_when_no_release_match(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cohort exists under a version that isn't in topology_release
    (defensive — shouldn't happen in prod). Loader picks the lexically-
    last cohort version so the result is at least stable across runs."""

    def fake_query(sql: str, params: list) -> list[dict]:
        if "topology_public WHERE cohort" in sql:
            return [
                {"topology_version": "topo_orphan_a"},
                {"topology_version": "topo_orphan_b"},
            ]
        if "topology_release" in sql:
            return []  # no release rows match
        return []

    monkeypatch.setattr(d1_deterministic, "_query_public", fake_query)
    assert (
        d1_deterministic._latest_topology_version_for_cohort("human_canonical")
        == "topo_orphan_b"
    )


# ---------------------------------------------------------------------------
# _fetch_paralogs
# ---------------------------------------------------------------------------


def test_fetch_paralogs_basic_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    """ParalogEntry rows surface paralog_symbol / acc / family_id /
    ecd_pct_identity / compara_version from the SQL row. No topology
    JOIN — that field was added in 6a220a90 and reverted shortly after
    (SRC's 32 paralogs are all GLOB so the bars rendered as solid
    intracellular blue with no signal)."""
    rows = [
        {
            "paralog_gene_symbol": "FYN",
            "paralog_uniprot_acc": "P06241",
            "ecd_pct_identity": 72.5,
            "family_id": "ENSGT00940000158534",
            "compara_version": "112",
            "rank_by_ecd_identity": 1,
        }
    ]

    monkeypatch.setattr(
        d1_deterministic, "_query_public", lambda sql, params: list(rows)
    )

    entries = d1_deterministic._fetch_paralogs("P12931", "compara-v112")

    assert len(entries) == 1
    p = entries[0]
    assert isinstance(p, ParalogEntry)
    assert p.paralog_symbol == "FYN"
    assert p.paralog_uniprot_acc == "P06241"
    assert p.ecd_pct_identity == pytest.approx(72.5)
    assert p.family_id == "ENSGT00940000158534"
    assert p.compara_version == "112"


def test_fetch_paralogs_handles_null_ecd_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ECD-less paralog (NULL ecd_pct_identity, common for inner-leaflet
    kinases like SRC's family) still surfaces — the loader keeps the
    row instead of silently dropping it. Family membership stays
    meaningful for the cross-reactivity-risk discipline even without
    a numeric ECD identity."""
    rows = [
        {
            "paralog_gene_symbol": "FYN",
            "paralog_uniprot_acc": "P06241",
            "ecd_pct_identity": None,
            "family_id": "ENSGT00940000158534",
            "compara_version": "112",
            "rank_by_ecd_identity": 1,
        }
    ]

    monkeypatch.setattr(
        d1_deterministic, "_query_public", lambda sql, params: list(rows)
    )

    entries = d1_deterministic._fetch_paralogs("P12931", "compara-v112")
    assert len(entries) == 1
    assert entries[0].ecd_pct_identity is None
    assert entries[0].paralog_symbol == "FYN"


# ---------------------------------------------------------------------------
# _fetch_orthologs
# ---------------------------------------------------------------------------


def test_fetch_orthologs_populates_topology_when_join_hits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The mouse / cyno topology join lands per_residue_topology +
    deeptmhmm_label on the OrthologEntry."""
    rows = [
        {
            "species": "mouse",
            "ortholog_uniprot_acc": "P00528",
            "ortholog_ensembl_gene": "ENSMUSG00000000028",
            "ortholog_gene_symbol": "Src",
            "ecd_pct_identity": 88.2,
            "full_length_pct_identity": 99.0,
            "tm_helix_count": 1,
            "ecd_length_residues": 250,
            "per_residue_topology": "OOOOMMMIIII",
            "deeptmhmm_label": "TM",
            "compara_release": "112",
        }
    ]

    monkeypatch.setattr(
        d1_deterministic, "_query_public", lambda sql, params: list(rows)
    )

    out = d1_deterministic._fetch_orthologs(
        "P12931", topology_version="tv1", ortholog_ecd_version="ev1"
    )

    assert len(out.mouse) == 1
    assert len(out.cynomolgus) == 0
    o = out.mouse[0]
    assert isinstance(o, OrthologEntry)
    assert o.per_residue_topology == "OOOOMMMIIII"
    assert o.deeptmhmm_label == "TM"
    # Existing fields still populate alongside the new ones.
    assert o.ecd_pct_identity_to_human_canonical == pytest.approx(88.2)
    assert o.tm_helix_count == 1
    assert o.ecd_length_residues == 250


def test_fetch_orthologs_topology_none_when_join_misses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """LEFT JOIN miss against ``topology_public`` → both topology fields
    are None but the ortholog row is still returned."""
    rows = [
        {
            "species": "cyno",
            "ortholog_uniprot_acc": "Q9BCYTEST",
            "ortholog_ensembl_gene": "ENSMFAG00000000001",
            "ortholog_gene_symbol": "SRC",
            "ecd_pct_identity": 95.1,
            "full_length_pct_identity": 99.4,
            "tm_helix_count": None,
            "ecd_length_residues": None,
            "per_residue_topology": None,
            "deeptmhmm_label": None,
            "compara_release": "112",
        }
    ]

    monkeypatch.setattr(
        d1_deterministic, "_query_public", lambda sql, params: list(rows)
    )

    out = d1_deterministic._fetch_orthologs(
        "P12931", topology_version="tv1", ortholog_ecd_version="ev1"
    )

    assert len(out.mouse) == 0
    assert len(out.cynomolgus) == 1
    o = out.cynomolgus[0]
    assert o.per_residue_topology is None
    assert o.deeptmhmm_label is None
    # tm_helix_count + ecd_length_residues coerce to 0 (legacy behavior:
    # OrthologEntry requires non-null ints for those — the LEFT JOIN
    # miss falls into the `int(... or 0)` branch).
    assert o.tm_helix_count == 0
    assert o.ecd_length_residues == 0
