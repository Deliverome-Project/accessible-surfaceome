"""Path 2b: confidently-folded surface-loop candidates.

Catches the insertion-tolerant loops in *ordered* (high-pLDDT) domains that the
incumbent low-pLDDT screen structurally misses — the EndoNB TFRC I290/V291
class. pLDDT flips role here: from a *disorder gate* to a *reliability gate*
that makes the RSA/DSSP geometry trustworthy. Every clause is an AND, so the
gate is conservative — it adds ordered-surface-loop catches without loosening
the disorder path. See ``docs/plans/2026-08-04-tagged-sites-04-*`` §7.2.
"""
from __future__ import annotations

from typing import Any

from .model import tagged_site

PLDDT_MIN = 70.0         # reliability gate (NOT a disorder gate)
RSA_MIN = 0.30           # solvent-exposed flank
GAP_MIN = 0.05           # some natural indel tolerance in the MSA column
FEATURE_DIST_MIN = 12.0  # Angstrom, 3D clearance from functional atoms
LOOP_SS = {"C", "T", "S", "G"}  # DSSP coil/turn/bend/3-10 — never mid-helix/strand


def _extracellular(topology_ch: str) -> bool:
    return topology_ch == "O"


def surface_loop_candidates(
    signals: dict[str, Any], *, gene_symbol: str, uniprot_acc: str
) -> list[dict[str, Any]]:
    """Apply the composite gate to per-residue signals, returning TaggedSites.

    ``signals`` carries per-residue dicts keyed by 1-indexed residue:
    ``topology`` (DeepTMHMM char), ``plddt``, ``rsa``, ``ss`` (DSSP char),
    ``gap_freq`` (MSA column gap fraction), ``conservation`` (KIBBY median),
    ``feature_dist`` (Angstrom to nearest functional atom), and ``sequence``.
    Survivors are ranked by low conservation, then high RSA, then high gap
    frequency.
    """
    seq = signals["sequence"]
    picks: list[dict[str, Any]] = []
    for res in sorted(signals["plddt"]):
        topo = signals["topology"].get(res, "?")
        if not _extracellular(topo):
            continue
        if signals["plddt"].get(res, 0.0) < PLDDT_MIN:
            continue  # reliability gate
        if signals["ss"].get(res, "?") not in LOOP_SS:
            continue  # loop/turn only
        if signals["rsa"].get(res, 0.0) < RSA_MIN:
            continue  # surface-exposed
        if signals["gap_freq"].get(res, 0.0) < GAP_MIN:
            continue  # indel-tolerant
        if signals["feature_dist"].get(res, 0.0) < FEATURE_DIST_MIN:
            continue  # 3D clearance veto
        rb = seq[res - 1] if 1 <= res <= len(seq) else None
        ra = seq[res] if 1 <= res < len(seq) else None
        picks.append(
            tagged_site(
                site_id=f"{gene_symbol}-internal-{res}-det",
                gene_symbol=gene_symbol,
                uniprot_acc=uniprot_acc,
                det_path="surface_loop",
                site_kind="internal",
                insert_after_residue=res,
                residue_before=rb,
                residue_after=ra,
                topology_state=topo,
                extracellular=True,
                compartment="extracellular",
                plddt=round(signals["plddt"][res], 1),
                median_conservation=signals["conservation"].get(res),
                rationale=(
                    "ordered surface loop: pLDDT>=70, DSSP loop/turn, high RSA, "
                    "indel-tolerant, 3D-clear of features"
                ),
            )
        )
    picks.sort(
        key=lambda p: (
            p["median_conservation"] if p["median_conservation"] is not None else 1.0,
            -signals["rsa"].get(p["insert_after_residue"], 0.0),
            -signals["gap_freq"].get(p["insert_after_residue"], 0.0),
        )
    )
    return picks
