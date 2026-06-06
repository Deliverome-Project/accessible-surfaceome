"""SURFACE-Bind D1-first lookup tests.

Pins the contract the orchestrator + Worker rely on:

* When public D1 returns a row, ``lookup`` materializes a populated
  :class:`SurfaceBindFeatures` from the D1 rows (NOT the JSON fallback).
  Both source layers — annotator and Worker enrichment — share this
  invariant.
* When public D1 returns no row, ``lookup`` falls through to the JSON
  fallback. ``has_data=False`` from D1 is itself a real answer ("scored
  set, not present"), distinct from a D1 failure (env vars absent /
  table missing / network down) which falls through.
* When D1 throws (env vars absent in this worktree, table missing on the
  test DB), ``lookup`` silently falls back to the JSON snapshot — that
  shape is what CI sees today, since CI runs without ``CLOUDFLARE_*``
  secrets.
* ``_decode_pdbs`` handles the canonical JSON-encoded string the sync
  script writes today plus the defensive list / comma-separated string
  shapes so a schema rev can't silently drop the PDB list.

These mock the D1 layer rather than hit the live public DB so they run
offline / in CI without secrets. The shape mirrors
``tests/test_gene_lookup_resolver.py``'s monkeypatching pattern.
"""
from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

from accessible_surfaceome.tools import surface_bind
from accessible_surfaceome.tools._shared.models import SurfaceBindFeatures


class _StubD1Client:
    """Stand-in for ``D1Client.public()`` that replays canned responses.

    The real client opens an httpx connection on construction; this stub
    avoids any I/O and lets the test queue ``(sql_substring_match,
    response_rows)`` pairs that the lookup will pop in order.
    """

    def __init__(self, *, protein_rows: list[dict[str, Any]],
                 site_rows: list[dict[str, Any]],
                 raise_on_query: bool = False):
        self._protein_rows = protein_rows
        self._site_rows = site_rows
        self._raise_on_query = raise_on_query
        self.queries: list[tuple[str, list[Any]]] = []

    def __enter__(self) -> _StubD1Client:
        return self

    def __exit__(self, *_exc: Any) -> None:
        return None

    def query(self, sql: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
        self.queries.append((sql, list(params or [])))
        if self._raise_on_query:
            raise RuntimeError("simulated D1 failure (env vars absent)")
        if "surface_bind_protein" in sql:
            return list(self._protein_rows)
        if "surface_bind_site" in sql:
            return list(self._site_rows)
        raise AssertionError(f"unexpected SQL in stub: {sql!r}")


@pytest.fixture(autouse=True)
def _reset_module_cache() -> Iterator[None]:
    """Drop the JSON cache between tests so the fallback path is
    re-exercised cleanly when a test wants to assert on it."""
    surface_bind._CACHE = None
    yield
    surface_bind._CACHE = None


def _patch_d1(stub: _StubD1Client) -> mock._patch:
    """Patch ``D1Client.public`` at the import surface ``surface_bind``
    sees so the lookup gets the stub instead of a live client."""
    return mock.patch(
        "accessible_surfaceome.cloud.d1_client.D1Client.public",
        return_value=stub,
    )


# ---------------------------------------------------------------------------
# D1-first path: populated row → real SurfaceBindFeatures.
# ---------------------------------------------------------------------------


def test_lookup_returns_populated_features_when_d1_has_row() -> None:
    """The headline contract: a public-D1 hit materializes the
    SurfaceBindFeatures with the protein + sites columns — no JSON read.
    Picks a EGFR-like row so the field shapes match what the sync script
    actually pushes."""
    protein = {
        "chain": "A",
        "main_class": "Receptors",
        "sub_class": "Kinase",
        "protein_name": "Epidermal growth factor receptor",
        "n_sites": 3,
        "n_seeds_alpha": 1,
        "n_seeds_beta": 1500,
        "n_seeds_total": 1501,
        # Canonical wire shape: JSON-encoded array (matches
        # sync_surface_bind_to_d1.py's json.dumps).
        "pdbs": json.dumps(["1IVO", "1M14"]),
    }
    sites = [
        {"site_id": 0, "anchor_residue": 743, "area_a2": 1523.93,
         "n_seeds_alpha": 1, "n_seeds_beta": 878, "hydrophobicity": 6.7},
        {"site_id": 1, "anchor_residue": 1100, "area_a2": 900.0,
         "n_seeds_alpha": 0, "n_seeds_beta": 622, "hydrophobicity": -1.2},
        {"site_id": 2, "anchor_residue": 1234, "area_a2": 600.0,
         "n_seeds_alpha": 0, "n_seeds_beta": 0, "hydrophobicity": 0.0},
    ]
    stub = _StubD1Client(protein_rows=[protein], site_rows=sites)
    with _patch_d1(stub):
        result = surface_bind.lookup("P00533")
    assert isinstance(result, SurfaceBindFeatures)
    assert result.has_data is True
    assert result.n_sites == 3
    assert result.n_seeds_alpha == 1
    assert result.n_seeds_beta == 1500
    assert result.n_seeds_total == 1501
    assert result.chain == "A"
    assert result.main_class == "Receptors"
    assert result.sub_class == "Kinase"
    assert result.protein_name == "Epidermal growth factor receptor"
    assert result.pdbs == ["1IVO", "1M14"]
    assert len(result.sites) == 3
    assert result.sites[0].site_id == 0
    assert result.sites[0].anchor_residue == 743
    assert result.sites[0].area_a2 == pytest.approx(1523.93)
    assert result.sites[0].n_seeds_alpha == 1
    assert result.sites[0].n_seeds_beta == 878
    assert result.sites[0].hydrophobicity == pytest.approx(6.7)
    # The two queries hit the canonical surface_bind tables, in order.
    assert len(stub.queries) == 2
    assert "surface_bind_protein" in stub.queries[0][0]
    assert stub.queries[0][1] == ["P00533"]
    assert "surface_bind_site" in stub.queries[1][0]
    assert stub.queries[1][1] == ["P00533"]
    # Defaults from the Pydantic model carry through (Balbi attribution),
    # so we never have to write them at the D1 layer.
    assert "Balbi" in result.source
    assert "Balbi" in result.attribution
    assert result.citation == "10.1073/pnas.2506269123"


# ---------------------------------------------------------------------------
# D1 "scored set, not in" → has_data=False without touching the JSON.
# ---------------------------------------------------------------------------


def test_lookup_d1_empty_row_returns_has_data_false_without_json_fallback() -> None:
    """A successful D1 query with zero rows is the authoritative
    "not scored" answer — the JSON fallback must NOT get to second-guess
    it. ``has_data=False`` is the explicit "scored set, not in" signal."""
    stub = _StubD1Client(protein_rows=[], site_rows=[])
    with _patch_d1(stub):
        result = surface_bind.lookup("___no_such_acc___")
    assert isinstance(result, SurfaceBindFeatures)
    assert result.has_data is False
    assert result.n_sites == 0
    assert result.pdbs == []
    assert result.sites == []
    # Only the protein query ran (the sites query is skipped when there's
    # no parent row).
    assert len(stub.queries) == 1


# ---------------------------------------------------------------------------
# D1 unreachable / env vars absent → JSON fallback.
# ---------------------------------------------------------------------------


def test_lookup_falls_back_to_json_when_d1_raises(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """When D1 throws (env vars missing in worktree, table missing,
    network down), the lookup silently falls back to the JSON snapshot
    so CI without CLOUDFLARE_* secrets keeps working."""
    # Point at a temp JSON with a known-positive entry.
    snapshot = tmp_path / "surface_bind_summary.json"
    snapshot.write_text(json.dumps({
        "__meta__": {"built_at": "2026-01-01"},
        "P0DUMMY": {
            "n_sites": 1,
            "n_seeds_alpha": 0,
            "n_seeds_beta": 5,
            "n_seeds_total": 5,
            "chain": "A",
            "main_class": "Receptors",
            "sub_class": "GPCR",
            "protein_name": "Dummy receptor",
            "sites": [
                {"site_id": 0, "anchor_residue": 100, "area_a2": 800.0,
                 "n_seeds_alpha": 0, "n_seeds_beta": 5,
                 "hydrophobicity": 0.5},
            ],
            "pdbs": ["1ABC"],
        },
    }))
    monkeypatch.setattr(surface_bind, "SUMMARY_PATH", snapshot)
    stub = _StubD1Client(protein_rows=[], site_rows=[], raise_on_query=True)
    with _patch_d1(stub):
        result = surface_bind.lookup("P0DUMMY")
    assert result.has_data is True
    assert result.n_seeds_beta == 5
    assert result.pdbs == ["1ABC"]
    assert len(result.sites) == 1
    assert result.sites[0].anchor_residue == 100
    # D1 was attempted (and raised); the JSON path then matched.
    assert len(stub.queries) == 1


# ---------------------------------------------------------------------------
# ``pdbs`` column decoding — covers the three shapes the helper accepts.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # Canonical wire shape sync_surface_bind_to_d1.py writes today.
        (json.dumps(["1AA0", "2BB1"]), ["1AA0", "2BB1"]),
        # Forward-compat: D1 might surface a native list one day.
        (["1CC2", "2DD3"], ["1CC2", "2DD3"]),
        # Defensive: empty / null / whitespace → empty list.
        (None, []),
        ("", []),
        ("   ", []),
        ("[]", []),
        # Legacy fallback: comma-separated string.
        ("1EE4, 2FF5,3GG6", ["1EE4", "2FF5", "3GG6"]),
        # Garbled JSON falls through to the comma-split path.
        ("[oops", ["[oops"]),
    ],
)
def test_decode_pdbs_accepts_canonical_and_defensive_shapes(
    raw: Any, expected: list[str]
) -> None:
    assert surface_bind._decode_pdbs(raw) == expected
