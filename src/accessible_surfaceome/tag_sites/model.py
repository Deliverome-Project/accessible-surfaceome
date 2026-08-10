"""Constructor for deterministic TaggedSite records.

Field set matches ``viewer/lib/tag-sites-types.ts`` exactly, so the Python
pipeline output drops straight into ``viewer/public/tag-sites/{SYMBOL}.json``.
"""
from __future__ import annotations

from typing import Any, Literal, Optional

TAGGED_SITE_KEYS = {
    "site_id", "gene_symbol", "uniprot_acc", "provenance", "det_path", "site_kind",
    "insert_after_residue", "residue_before", "residue_after", "topology_state",
    "extracellular", "compartment", "tag_type", "tag_length_aa", "linker",
    "evidence_type", "functional_impact_measured", "confidence", "rationale",
    "sources", "plddt", "conservation_rank", "median_conservation",
}

_EVIDENCE = {
    "disorder": "structural inference (disorder path)",
    "surface_loop": "structural inference (surface_loop path)",
}


def tagged_site(
    *,
    site_id: str,
    gene_symbol: str,
    uniprot_acc: str,
    det_path: Literal["disorder", "surface_loop"],
    site_kind: Literal["terminal_n", "terminal_c", "internal"],
    insert_after_residue: Optional[int],
    residue_before: Optional[str],
    residue_after: Optional[str],
    topology_state: Optional[str],
    extracellular: bool,
    compartment: str,
    tag_type: str = "ALFA",
    tag_length_aa: Optional[int] = 15,
    linker: Optional[str] = "GS both sides",
    confidence: Literal["high", "medium", "low"] = "medium",
    functional_impact_measured: str = "NOT MEASURED",
    rationale: Optional[str] = None,
    sources: Optional[list[dict[str, Any]]] = None,
    plddt: Optional[float] = None,
    conservation_rank: Optional[int] = None,
    median_conservation: Optional[float] = None,
) -> dict[str, Any]:
    """Build one ``deterministic_computed`` TaggedSite dict.

    ``det_path`` selects the ``evidence_type`` string and marks which
    candidate-generation path produced the site. Deterministic-only numeric
    fields (``plddt`` / ``conservation_rank`` / ``median_conservation``)
    default to ``None`` when not supplied.
    """
    if det_path not in _EVIDENCE:
        raise ValueError(f"unknown det_path: {det_path!r}")
    return {
        "site_id": site_id,
        "gene_symbol": gene_symbol,
        "uniprot_acc": uniprot_acc,
        "provenance": "deterministic_computed",
        "det_path": det_path,
        "site_kind": site_kind,
        "insert_after_residue": insert_after_residue,
        "residue_before": residue_before,
        "residue_after": residue_after,
        "topology_state": topology_state,
        "extracellular": extracellular,
        "compartment": compartment,
        "tag_type": tag_type,
        "tag_length_aa": tag_length_aa,
        "linker": linker,
        "evidence_type": _EVIDENCE[det_path],
        "functional_impact_measured": functional_impact_measured,
        "confidence": confidence,
        "rationale": rationale,
        "sources": sources or [],
        "plddt": plddt,
        "conservation_rank": conservation_rank,
        "median_conservation": median_conservation,
    }
