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
RSA_MIN = 0.30           # solvent-exposed junction (window max)
FEATURE_DIST_MIN = 12.0  # Angstrom, 3D clearance from functional atoms
LOOP_SS = {"C", "T", "S", "G"}  # DSSP coil/turn/bend/3-10 — never mid-helix/strand


def _extracellular(topology_ch: str) -> bool:
    return topology_ch == "O"


def _window_max(values: dict[int, float], res: int, lo: int = -1, hi: int = 2) -> float:
    """Max over the junction window {res-1 .. res+2}. The tag inserts *between*
    ``res`` and ``res+1``, so exposure of the junction — not the anchor
    side-chain alone — is what matters. TFRC I290 is the motivating case: its
    own side-chain RSA is 0.02 (buried), but the junction is flanked by
    P289 (0.48) and V291 (0.88), so the site is surface-exposed."""
    return max((values.get(res + d, 0.0) for d in range(lo, hi + 1)), default=0.0)


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
        if _window_max(signals["rsa"], res) < RSA_MIN:
            continue  # surface-exposed (junction window, not just the anchor side-chain)
        if signals["feature_dist"].get(res, 0.0) < FEATURE_DIST_MIN:
            continue  # 3D clearance veto
        # NOTE: indel-tolerance (gap_freq) is a RANKING signal, not a hard gate —
        # a good site (e.g. TFRC I290) need not sit at a natural indel, and with a
        # shallow ortholog set gap_freq is 0 at most positions.
        rb = seq[res - 1] if 1 <= res <= len(seq) else None
        ra = seq[res] if 1 <= res < len(seq) else None
        picks.append(
            tagged_site(
                site_id=f"{gene_symbol}-surface_loop-{res}",
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
            -_window_max(signals["rsa"], p["insert_after_residue"]),
            -signals.get("gap_freq", {}).get(p["insert_after_residue"], 0.0),
        )
    )
    return picks
