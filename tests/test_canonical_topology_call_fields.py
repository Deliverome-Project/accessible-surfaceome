"""Guard: DeepTMHMM's own call reaches records and the served API.

``IsoformTopology`` has carried ``predicted_surface_membrane``,
``predicted_secreted``, ``beta_strand_count`` and ``protein_length`` since the
DeepTMHMM call was added, but ``_fetch_canonical_topology`` never selected those
columns, so every record was baked with them null. The Worker's serve-time
fill tested ``=== undefined``, which a stored null never matches. Result: the
"DeepTMHMM call" line was blank on ~99% of genes (found 2026-10-17).
"""

from __future__ import annotations

from accessible_surfaceome.agents.surfaceome_v1 import d1_deterministic as dd
from accessible_surfaceome.paths import REPO_ROOT

ROW = {
    "uniprot_acc_full": "P00533",
    "isoform_id": "P00533-1",
    "tm_helix_count": 1,
    "n_terminal_orientation": "extracellular",
    "c_terminal_orientation": "cytoplasmic",
    "signal_peptide_length": 24,
    "ecd_length_residues": 621,
    "icd_length_residues": 542,
    "per_residue_topology": "S" * 24 + "O" * 621 + "M" * 23 + "I" * 542,
    "tool_version": "deeptmhmm-1.0.24",
    "retrieved_at": "2026-05-16T00:00:00Z",
    "predicted_surface_membrane": 1,
    "predicted_secreted": 0,
    "beta_strand_count": None,
    "protein_length": 1210,
}


def test_canonical_topology_carries_the_deeptmhmm_call(monkeypatch) -> None:
    seen: list[str] = []

    def fake_query(sql, params):
        seen.append(sql)
        return [ROW]

    monkeypatch.setattr(dd, "_query_public", fake_query)
    topo = dd._fetch_canonical_topology("P00533", "topo_2026_05_16")
    assert topo is not None
    assert "predicted_surface_membrane" in seen[0]
    assert topo.predicted_surface_membrane is True
    assert topo.predicted_secreted is False
    assert topo.beta_strand_count is None
    assert topo.protein_length == 1210


def test_worker_fills_the_call_when_stored_as_null() -> None:
    src = (REPO_ROOT / "cloudflare/workers/surfaceome_api/src/index.js").read_text()
    assert "existingCanonTopo.predicted_surface_membrane == null" in src
    assert "existingCanonTopo.predicted_surface_membrane === undefined" not in src
