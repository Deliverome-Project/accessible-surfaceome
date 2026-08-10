"""Path 2a: disorder-path candidates, re-derived in-repo (NOT ported).

The incumbent private pipeline found internal insertion sites as contiguous runs
of low AlphaFold pLDDT; this re-derives that from source in the open repo, from
the same in-repo signal set the surface-loop path uses. See spec §7.2.
"""
from __future__ import annotations

from typing import Any

from .model import tagged_site
from .surface_loop import FEATURE_DIST_MIN, _extracellular

PLDDT_DISORDER_MAX = 70.0  # a run below this is the disorder/flexibility proxy
MIN_RUN = 4                # contiguous residues (short loops aren't disorder)


def _emit_run(
    run: list[int], signals: dict[str, Any], *, gene_symbol: str, uniprot_acc: str
) -> dict[str, Any] | None:
    """Turn a qualifying residue run into one disorder TaggedSite (anchored at
    the run midpoint), or None when the run is too short."""
    if len(run) < MIN_RUN:
        return None
    seq = signals["sequence"]
    mid = run[len(run) // 2]
    rb = seq[mid - 1] if 1 <= mid <= len(seq) else None
    ra = seq[mid] if 1 <= mid < len(seq) else None
    return tagged_site(
        site_id=f"{gene_symbol}-internal-{mid}-det",
        gene_symbol=gene_symbol,
        uniprot_acc=uniprot_acc,
        det_path="disorder",
        site_kind="internal",
        insert_after_residue=mid,
        residue_before=rb,
        residue_after=ra,
        topology_state="O",
        extracellular=True,
        compartment="extracellular",
        plddt=round(signals["plddt"][mid], 1),
        median_conservation=signals["conservation"].get(mid),
        rationale="low-pLDDT disordered extracellular run (>=4 aa), 3D-clear of features",
    )


def disorder_candidates(
    signals: dict[str, Any], *, gene_symbol: str, uniprot_acc: str
) -> list[dict[str, Any]]:
    """Scan for maximal contiguous residue runs that are low-pLDDT (<70),
    extracellular ('O'), and 3D-clear of functional atoms; emit one site per
    qualifying run, ranked by low ortholog conservation."""
    plddt = signals["plddt"]
    topo = signals["topology"]
    feat = signals["feature_dist"]
    picks: list[dict[str, Any]] = []
    run: list[int] = []
    prev: int | None = None
    for res in sorted(plddt):
        passes = (
            plddt.get(res, 100.0) < PLDDT_DISORDER_MAX
            and _extracellular(topo.get(res, "?"))
            and feat.get(res, 0.0) >= FEATURE_DIST_MIN
        )
        contiguous = prev is not None and res == prev + 1
        if passes and (not run or contiguous):
            run.append(res)
        else:
            site = _emit_run(run, signals, gene_symbol=gene_symbol, uniprot_acc=uniprot_acc)
            if site is not None:
                picks.append(site)
            run = [res] if passes else []
        prev = res
    site = _emit_run(run, signals, gene_symbol=gene_symbol, uniprot_acc=uniprot_acc)
    if site is not None:
        picks.append(site)
    picks.sort(
        key=lambda p: p["median_conservation"] if p["median_conservation"] is not None else 1.0
    )
    return picks
