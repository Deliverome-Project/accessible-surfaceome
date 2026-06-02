"""Pick the single representative experimental structure for a protein.

Queries the PDBe SIFTS ``best_structures`` endpoint (UniProt → PDB mapping
with per-chain coverage + resolution) and returns ONE
:class:`RepresentativeStructure` — the highest-coverage, best-resolution
entry — instead of a flat list of PDB IDs (A1.10).

The ranking core (:func:`_pick_best`) is pure and unit-tested without
network; :func:`fetch_representative_structure` wraps it with the HTTP fetch
and degrades to ``None`` on any error so callers never break on a PDBe miss.
"""

from __future__ import annotations

import logging
from typing import Any

from accessible_surfaceome.tools._shared.http import CachedHTTP
from accessible_surfaceome.tools._shared.models import RepresentativeStructure

logger = logging.getLogger(__name__)

_BEST_STRUCTURES_URL = "https://www.ebi.ac.uk/pdbe/api/mappings/best_structures/{acc}"
_TTL_DAYS = 30


def _rank_key(entry: dict[str, Any]) -> tuple[float, float, str]:
    """Sort key: highest coverage, then best (lowest) resolution.

    Missing coverage sorts last (treated as 0); missing resolution sorts last
    (treated as +inf, e.g. NMR/EM entries with no resolution). PDB id is the
    final deterministic tiebreak.
    """
    coverage = entry.get("coverage")
    resolution = entry.get("resolution")
    cov = float(coverage) if isinstance(coverage, (int, float)) else 0.0
    res = float(resolution) if isinstance(resolution, (int, float)) else float("inf")
    return (-cov, res, str(entry.get("pdb_id", "")))


def _pick_best(entries: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Return the single best mapping entry, or ``None`` for an empty list."""
    ranked = sorted((e for e in entries if e.get("pdb_id")), key=_rank_key)
    return ranked[0] if ranked else None


def _to_representative(entry: dict[str, Any]) -> RepresentativeStructure:
    def _num(v: Any) -> float | None:
        return float(v) if isinstance(v, (int, float)) else None

    def _int(v: Any) -> int | None:
        return int(v) if isinstance(v, (int, float)) else None

    return RepresentativeStructure(
        pdb_id=str(entry["pdb_id"]),
        chain=entry.get("chain_id"),
        method=entry.get("experimental_method"),
        resolution_angstrom=_num(entry.get("resolution")),
        coverage_fraction=_num(entry.get("coverage")),
        residue_start=_int(entry.get("unp_start")),
        residue_end=_int(entry.get("unp_end")),
    )


def fetch_representative_structure(
    uniprot_acc: str, *, http: CachedHTTP
) -> RepresentativeStructure | None:
    """Fetch + rank the best PDBe structure for ``uniprot_acc``.

    Returns ``None`` when the protein has no experimental structure or the
    PDBe lookup fails — never raises, so an annotate run continues.
    """
    url = _BEST_STRUCTURES_URL.format(acc=uniprot_acc)
    try:
        payload = http.get_json(url, source="pdbe_best_structures", ttl_days=_TTL_DAYS)
    except Exception as exc:  # noqa: BLE001 — best-structures is best-effort
        logger.warning("PDBe best_structures fetch failed for %s (%s)", uniprot_acc, exc)
        return None
    entries = (payload or {}).get(uniprot_acc) or []
    best = _pick_best(entries)
    if best is None:
        return None
    return _to_representative(best)


__all__ = ["fetch_representative_structure"]
