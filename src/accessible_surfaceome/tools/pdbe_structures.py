"""Representative experimental (PDB) structure via PDBe SIFTS.

PDBe's ``best_structures`` endpoint ranks the deposited structures for a
UniProt accession by coverage (descending) then resolution (ascending), so
``[0]`` is the most complete, best-resolved experimental structure. This is
the reproducible way to pick "the experimental structure" for a protein —
the deep-dive record otherwise carries only a flat list of PDB IDs
(``surface_bind.pdbs``) with no coverage metadata.

Shared by the deterministic-features builder
(:mod:`accessible_surfaceome.agents.surfaceome_v1.d1_deterministic`) and the
backfill script, so the agent-time and backfill paths can't drift. Mirrors
the same selection the markdown exporter does in JS.

Never raises — on outage / 404 / malformed payload it returns ``None`` and
the caller leaves ``representative_experimental_structure`` unset.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import httpx

from accessible_surfaceome.tools._shared.models import RepresentativeStructure

logger = logging.getLogger(__name__)

PDBE_BEST_STRUCTURES = "https://www.ebi.ac.uk/pdbe/api/mappings/best_structures"

# Match the markdown exporter's named UA so server logs attribute both paths
# to the same client.
_UA = "accessible-surfaceome/1.0 (pdbe_structures.py)"


def _coerce_float(value: object) -> float | None:
    try:
        return float(value) if value is not None else None  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def fetch_representative_structure(
    uniprot_acc: str,
) -> RepresentativeStructure | None:
    """Return the highest-coverage / best-resolution PDB for ``uniprot_acc``.

    ``None`` when the protein has no deposited experimental structure (404 /
    empty list) or PDBe is unreachable.
    """
    if not uniprot_acc:
        return None
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(
                f"{PDBE_BEST_STRUCTURES}/{uniprot_acc}",
                headers={"Accept": "application/json", "User-Agent": _UA},
            )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        rows = (resp.json() or {}).get(uniprot_acc) or []
    except Exception as exc:  # noqa: BLE001 — keep the orchestrator running
        logger.warning(
            "PDBe best_structures fetch failed for %s (%s)", uniprot_acc, exc
        )
        return None
    if not rows:
        return None
    # PDBe returns rows pre-sorted by coverage desc, then resolution asc.
    top = rows[0]
    try:
        return RepresentativeStructure(
            pdb_id=str(top["pdb_id"]),
            chain_id=str(top.get("chain_id") or ""),
            unp_start=int(top["unp_start"]),
            unp_end=int(top["unp_end"]),
            coverage=_coerce_float(top.get("coverage")),
            resolution_a=_coerce_float(top.get("resolution")),
            experimental_method=(
                str(top["experimental_method"])
                if top.get("experimental_method")
                else None
            ),
            n_experimental_structures=len(rows),
            retrieved_at=datetime.now(UTC),
        )
    except (KeyError, TypeError, ValueError) as exc:
        logger.warning(
            "malformed PDBe best_structures row for %s: %s (%s)",
            uniprot_acc,
            top,
            exc,
        )
        return None
