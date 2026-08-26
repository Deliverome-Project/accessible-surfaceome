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
from .isoform import classify_isoform_sites
from .features import ca_coords, feature_distances
from .signals import (
    merge_signals,
    ortholog_conservation,
    per_residue_plddt,
    per_residue_rsa,
    per_residue_ss,
)
from .surface_loop import surface_loop_candidates
from .terminal import terminal_candidates


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
            "ca": ca_coords(pdb_path),  # for the terminus-proximity filter (3D)
        },
        ortholog_conservation(sequence, ortholog_seqs),  # conservation + gap_freq
    )


# 3D clearance (Å, CA-CA) an internal loop site must have from an EXTRACELLULAR
# terminus. A loop hugging an accessible terminus is redundant with the terminal
# tag (you'd just tag the terminus), so it's dropped. Measured in Angstrom, not
# residues: a loop can be sequence-far yet spatially at the terminus, or vice versa.
TERMINUS_MIN_DIST_A = 15.0


def _terminus_anchor_residue(term: dict[str, Any]) -> int | None:
    """Residue number that spatially represents an extracellular terminal tag:
    the mature first residue for terminal_n (insert_after+1; residue 1 for a
    direct N-term), or the last residue for terminal_c (= insert_after)."""
    if term["site_kind"] == "terminal_n":
        return (term.get("insert_after_residue") or 0) + 1
    if term["site_kind"] == "terminal_c":
        return term.get("insert_after_residue")
    return None


def _drop_near_terminus(
    internal: list[dict[str, Any]], terms: list[dict[str, Any]], signals: dict[str, Any]
) -> list[dict[str, Any]]:
    """Drop internal sites whose CA is within ``TERMINUS_MIN_DIST_A`` of any
    EXTRACELLULAR terminal anchor (det_path 'terminal', i.e. a real ecto-terminus
    — NOT a snorkel). No-op when CA coords are absent (e.g. unit-test signals)."""
    ca: dict[int, tuple[float, float, float]] = signals.get("ca") or {}
    anchors = [
        ca[a]
        for t in terms
        if t.get("det_path") == "terminal"
        for a in (_terminus_anchor_residue(t),)
        if a is not None and a in ca
    ]
    if not ca or not anchors:
        return internal

    def _clear(site: dict[str, Any]) -> bool:
        r = site.get("insert_after_residue")
        if r is None or r not in ca:
            return True  # can't measure -> don't drop
        p = ca[r]
        dmin = min(
            ((p[0] - a[0]) ** 2 + (p[1] - a[1]) ** 2 + (p[2] - a[2]) ** 2) ** 0.5 for a in anchors
        )
        return dmin >= TERMINUS_MIN_DIST_A

    return [s for s in internal if _clear(s)]


def _with_terminals(
    internal: list[dict[str, Any]], signals: dict[str, Any], *, gene_symbol: str, uniprot_acc: str
) -> list[dict[str, Any]]:
    """Prepend the extracellular N-terminal site and append the C-terminal /
    snorkel site around the residue-ordered internal sites. Terminals are single
    named sites (own ``site_id``s) and bypass ``select_representatives`` NMS.
    Internal sites hugging an extracellular terminus (redundant with the terminal
    tag) are dropped first."""
    terms = terminal_candidates(signals, gene_symbol=gene_symbol, uniprot_acc=uniprot_acc)
    internal = _drop_near_terminus(internal, terms, signals)
    n_terms = [s for s in terms if s["site_kind"] == "terminal_n"]
    c_terms = [s for s in terms if s["site_kind"] == "terminal_c"]
    return n_terms + internal + c_terms


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
    internal = sorted(by_res.values(), key=lambda s: s["insert_after_residue"])
    return _with_terminals(internal, signals, gene_symbol=gene_symbol, uniprot_acc=uniprot_acc)


def select_representatives(
    ranked_sites: list[dict[str, Any]], *, min_gap: int = 8, max_sites: int = 20
) -> list[dict[str, Any]]:
    """Greedy non-maximum suppression by residue over a *rank-ordered* site list
    (best first): keep a site only if it is ≥ ``min_gap`` residues from every
    already-kept site, so one representative survives per exposed loop rather than
    a dense run; then cap to ``max_sites``. Keeps the ranking intact."""
    kept: list[dict[str, Any]] = []
    for s in ranked_sites:
        r = s["insert_after_residue"]
        if all(abs(r - k["insert_after_residue"]) >= min_gap for k in kept):
            kept.append(s)
        if len(kept) >= max_sites:
            break
    return kept


def select_deterministic_representatives(
    signals: dict[str, Any], *, gene_symbol: str, uniprot_acc: str
) -> list[dict[str, Any]]:
    """NMS-selected representative insertion sites (surface_loop + disorder,
    deduped by residue, surface_loop preferred on collision) — the ~representative
    set the canonical structure overlay shows. Shared by ``run_gene`` (canonical)
    and ``run_isoform_pins`` (per isoform) so a dense ectodomain yields
    representatives, never hundreds of adjacent candidates."""
    surf = select_representatives(
        surface_loop_candidates(signals, gene_symbol=gene_symbol, uniprot_acc=uniprot_acc)
    )
    diso = select_representatives(
        disorder_candidates(signals, gene_symbol=gene_symbol, uniprot_acc=uniprot_acc)
    )
    by_res: dict[int, dict[str, Any]] = {}
    for s in surf + diso:  # surface_loop first -> preferred on residue collision
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
    """End-to-end for one gene: compute signals → both gates → representative
    selection (so a dense ectodomain doesn't emit hundreds of adjacent sites) →
    emit merged JSON."""
    signals = compute_signals(
        pdb_path,
        topology=topology,
        sequence=sequence,
        ortholog_seqs=ortholog_seqs,
        hazard_res=hazard_res,
    )
    surf = select_representatives(
        surface_loop_candidates(signals, gene_symbol=gene_symbol, uniprot_acc=uniprot_acc)
    )
    diso = select_representatives(
        disorder_candidates(signals, gene_symbol=gene_symbol, uniprot_acc=uniprot_acc)
    )
    by_res: dict[int, dict[str, Any]] = {}
    for s in surf + diso:  # surface_loop first → preferred on residue collision
        by_res.setdefault(s["insert_after_residue"], s)
    internal = sorted(by_res.values(), key=lambda s: s["insert_after_residue"])
    sites = _with_terminals(internal, signals, gene_symbol=gene_symbol, uniprot_acc=uniprot_acc)
    return emit_tag_sites_json(gene_symbol, uniprot_acc, sites, out_dir=out_dir)


def run_isoform_pins(
    gene_symbol: str,
    canonical_acc: str,
    *,
    canonical_sequence: str,
    canonical_sites: list[dict[str, Any]],
    isoforms: list[tuple[str, str, str]],
    fetch_pdb: Any,
    hazard_for: Any = None,
) -> list[dict[str, Any]]:
    """Per-isoform tag pins: run the deterministic gates on each isoform's OWN
    AFDB model, then classify vs the canonical prediction (shared / unique).

    ``isoforms`` is ``[(isoform_id, sequence, topology_str), ...]``.
    ``fetch_pdb(acc)`` returns a local PDB path and should RAISE when AFDB has no
    model for that isoform (it is then skipped — the canonical-lift fallback is
    the caller's job). ``hazard_for(acc) -> set[int]`` is optional (UniProt
    feature veto per isoform); omitted -> empty (no veto)."""
    pins: list[dict[str, Any]] = []
    for iso_id, iso_seq, iso_topo in isoforms:
        if not iso_seq or not iso_topo or len(iso_seq) != len(iso_topo):
            continue  # stale/mismatched isoform record
        try:
            pdb = fetch_pdb(iso_id)
        except Exception:  # noqa: BLE001 — AFDB has no isoform model; skip this isoform
            continue
        topo = {i + 1: c for i, c in enumerate(iso_topo)}
        hazard = hazard_for(iso_id) if hazard_for else set()
        signals = compute_signals(
            pdb, topology=topo, sequence=iso_seq, ortholog_seqs=[], hazard_res=hazard
        )
        iso_sites = select_deterministic_representatives(
            signals, gene_symbol=gene_symbol, uniprot_acc=iso_id
        )
        pins.extend(
            classify_isoform_sites(
                isoform_id=iso_id,
                isoform_sites=iso_sites,
                isoform_sequence=iso_seq,
                canonical_sites=canonical_sites,
                canonical_sequence=canonical_sequence,
            )
        )
    return pins
