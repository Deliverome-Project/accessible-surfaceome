"""Constructor for deterministic TaggedSite records.

Field set matches ``viewer/lib/tag-sites-types.ts`` exactly, so the Python
pipeline output drops straight into ``viewer/public/tag-sites/{SYMBOL}.json``.
"""
from __future__ import annotations

from typing import Any, Literal, Optional

TAGGED_SITE_KEYS = {
    "site_id", "gene_symbol", "uniprot_acc", "provenance", "det_path", "site_kind",
    "insert_after_residue", "residue_before", "residue_after", "residue_label",
    "residue_range", "topology_state", "extracellular", "compartment", "tag_type", "tag_length_aa",
    "linker", "evidence_type", "functional_impact_measured", "confidence", "rationale",
    "sources", "plddt", "conservation_rank", "median_conservation",
}


def residue_label(
    residue_before: Optional[str], insert_after_residue: Optional[int]
) -> Optional[str]:
    """Canonical single-token residue for downstream analysis, e.g. ``G101``:
    the residue immediately N-terminal to the junction (tag inserted AFTER it).
    Matches the "after N" convention in ``data/tag_sites/positive_controls.md``.
    Returns ``None`` when either input is missing (e.g. a before-residue-1 tag)."""
    if residue_before is None or insert_after_residue is None:
        return None
    return f"{residue_before}{insert_after_residue}"


def residue_range(
    sequence: Optional[str], start: Optional[int], end: Optional[int]
) -> Optional[str]:
    """Span token for the deterministic site's tolerant FEATURE, e.g. ``S98-K105``:
    the low-pLDDT disorder run (disorder path) or the contiguous exposed loop
    (surface_loop path) the representative point sits in. Endpoints carry their
    1-letter residue, same style as :func:`residue_label`. Returns ``None`` when
    the feature is a single residue (``start == end``) or bounds are missing —
    a point, not a range."""
    if start is None or end is None or start >= end:
        return None

    def _aa(pos: int) -> str:
        return sequence[pos - 1] if sequence and 1 <= pos <= len(sequence) else "?"

    return f"{_aa(start)}{start}-{_aa(end)}{end}"

_EVIDENCE = {
    "disorder": "structural inference (disorder path)",
    "surface_loop": "structural inference (surface_loop path)",
    # Terminal lanes are pure-topology calls (no structure): an extracellular
    # N-/C-terminus takes a tag directly; an intracellular C-terminus takes a
    # snorkel that presents the tag on the surface via a TM-snorkeling linker.
    "terminal": "topology inference (extracellular terminus)",
    "snorkel": "topology inference (C-terminal snorkel — no accessible terminus)",
}


def tagged_site(
    *,
    site_id: str,
    gene_symbol: str,
    uniprot_acc: str,
    det_path: Literal["disorder", "surface_loop", "terminal", "snorkel"],
    site_kind: Literal["terminal_n", "terminal_c", "internal"],
    insert_after_residue: Optional[int],
    residue_before: Optional[str],
    residue_after: Optional[str],
    topology_state: Optional[str],
    extracellular: bool,
    compartment: str,
    residue_range_token: Optional[str] = None,
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
        "residue_label": residue_label(residue_before, insert_after_residue),
        "residue_range": residue_range_token,
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
