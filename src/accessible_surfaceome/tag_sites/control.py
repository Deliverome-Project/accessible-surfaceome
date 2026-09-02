"""Constructors for `screen_validated` control tag sites (Tedman GPCR screen).

Same key set as tag_sites.model.tagged_site, but provenance="screen_validated",
det_path=None, and the measured HA-immunostaining surface expression carried as
free-text in the evidence fields (no schema field — per design decision)."""
from __future__ import annotations

from typing import Any, Optional

from accessible_surfaceome.tag_sites.model import residue_label


def _pme_text(pme: Optional[float], sd: Optional[float]) -> str:
    if pme is None:
        return "Surface-displayed HA tag (Tedman deep receptor scanning)"
    sd_txt = f" ± {sd:g}" if sd is not None else ""
    return f"Surface immunostaining PME {pme:g}{sd_txt} (HA immunostaining, Tedman deep receptor scanning)"


def control_tag_site(
    *,
    site_id: str, gene_symbol: str, uniprot_acc: str,
    insert_after_residue: Optional[int], residue_before: Optional[str], residue_after: Optional[str],
    pme: Optional[float] = None, pme_sd: Optional[float] = None,
    sources: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    return {
        "site_id": site_id, "gene_symbol": gene_symbol, "uniprot_acc": uniprot_acc,
        "provenance": "screen_validated", "det_path": None, "site_kind": "terminal_n",
        "insert_after_residue": insert_after_residue,
        "residue_before": residue_before, "residue_after": residue_after,
        "residue_label": residue_label(residue_before, insert_after_residue),
        "residue_range": None, "topology_state": "S",
        "extracellular": True, "compartment": "extracellular",
        "tag_type": "HA", "tag_length_aa": 9, "linker": None,
        "evidence_type": "N-terminal HA epitope; parallel surface-display screen",
        "functional_impact_measured": _pme_text(pme, pme_sd),
        "confidence": "high",
        "rationale": (
            "Experimentally validated N-terminal HA epitope insertion (after "
            "signal-peptide cleavage where present); surface expression read out by "
            "HA immunostaining in Tedman et al. deep receptor scanning."
        ),
        "sources": sources or [],
        "plddt": None, "conservation_rank": None, "median_conservation": None,
    }
