"""Deterministic tag-site orchestrator.

Assembles the per-residue signal dict from source (AlphaFold model + record
topology + ortholog conservation + UniProt-feature veto), runs both candidate
paths, and writes the merged sites to the viewer's per-gene JSON. Everything is
re-derived in-repo — nothing ported.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .disorder import disorder_candidates
from .emit import emit_tag_sites_json
from .features import feature_distances
from .signals import (
    merge_signals,
    ortholog_conservation,
    per_residue_plddt,
    per_residue_rsa,
    per_residue_ss,
)
from .surface_loop import surface_loop_candidates


def compute_signals(
    pdb_path: str,
    *,
    topology: dict[int, str],
    sequence: str,
    ortholog_seqs: list[str],
    hazard_res: set[int],
) -> dict[str, Any]:
    """Build the full per-residue signal dict the gates consume, all from
    source: structural signals off the AF model, ortholog-MSA conservation, and
    the UniProt-feature 3D-distance veto."""
    return merge_signals(
        {
            "plddt": per_residue_plddt(pdb_path),
            "rsa": per_residue_rsa(pdb_path),
            "ss": per_residue_ss(pdb_path),
        },
        {
            "topology": topology,
            "sequence": sequence,
            "feature_dist": feature_distances(pdb_path, hazard_res),
        },
        ortholog_conservation(sequence, ortholog_seqs),  # conservation + gap_freq
    )


def derive_deterministic_sites(
    gene_symbol: str, uniprot_acc: str, *, signals: dict[str, Any]
) -> list[dict[str, Any]]:
    """Run both candidate paths and merge, deduping by residue and preferring
    the surface-loop nomination (the more specific, ordered-loop signal) when a
    residue is nominated by both paths."""
    surf = surface_loop_candidates(signals, gene_symbol=gene_symbol, uniprot_acc=uniprot_acc)
    diso = disorder_candidates(signals, gene_symbol=gene_symbol, uniprot_acc=uniprot_acc)
    by_res: dict[int, dict[str, Any]] = {}
    for s in surf:  # surface_loop first → preferred on collision
        by_res.setdefault(s["insert_after_residue"], s)
    for s in diso:
        by_res.setdefault(s["insert_after_residue"], s)
    return sorted(by_res.values(), key=lambda s: s["insert_after_residue"])


def run_gene(
    gene_symbol: str,
    uniprot_acc: str,
    *,
    sequence: str,
    topology: dict[int, str],
    ortholog_seqs: list[str],
    pdb_path: str,
    hazard_res: set[int],
    out_dir: str | Path,
) -> dict[str, Any]:
    """End-to-end for one gene: compute signals → both gates → emit merged JSON."""
    signals = compute_signals(
        pdb_path,
        topology=topology,
        sequence=sequence,
        ortholog_seqs=ortholog_seqs,
        hazard_res=hazard_res,
    )
    sites = derive_deterministic_sites(gene_symbol, uniprot_acc, signals=signals)
    return emit_tag_sites_json(gene_symbol, uniprot_acc, sites, out_dir=out_dir)
