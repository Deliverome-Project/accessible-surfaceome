"""Path 2a: disorder-path candidates, re-derived in-repo (NOT ported).

The incumbent private pipeline found internal insertion sites as contiguous runs
of low AlphaFold pLDDT; this re-derives that from source in the open repo, from
the same in-repo signal set the surface-loop path uses. See spec §7.2.

A low-pLDDT extracellular *run* defines a disordered loop, but a long disordered
ectodomain (e.g. TMEM123, ~110 aa of pLDDT<70) has many valid tag positions, not
one. So we emit a candidate at every solvent-exposed, feature-clear residue in the
run, ranked exposure-first, and let ``run.select_representatives`` (NMS) space them
across the loop — rather than collapsing the whole region to a single anchor.
"""
from __future__ import annotations

from typing import Any

from .model import residue_range, tagged_site
from .surface_loop import FEATURE_DIST_MIN, _extracellular

PLDDT_DISORDER_MAX = 70.0  # fallback proxy when no predictor track is available
MIN_RUN = 4                # contiguous residues (short loops aren't disorder)
DISORDER_PCT_MIN = 60.0
"""Within-protein disorder percentile a residue must reach to count as flexible.

Measured, not chosen: Tedman's 112 screen-validated junctions sit at the 88th-93rd
percentile of their own receptor, and our own 25 curated internal positive controls at
the 73rd-83rd. 60 admits both populations with margin while still excluding the ordered
half of every protein."""


def _flexible_runs(signals: dict[str, Any], topo: dict[int, str]) -> list[list[int]]:
    """Maximal contiguous extracellular runs that the disorder predictors call flexible.

    Prefers the consensus of metapredict, NetSurfP-3.0 and AlphaFold-disorder over raw
    pLDDT. They are not interchangeable in practice: scoring the predictors by
    within-protein rank puts the top extracellular site a median 3 aa from Tedman's
    junction, where a contiguous pLDDT<70 run puts it 40 aa away. pLDDT remains the
    fallback for genes with no published track.
    """
    disorder = signals.get("disorder") or {}
    if disorder:
        return _runs(lambda r: disorder.get(r, 0.0) >= DISORDER_PCT_MIN, disorder, topo)
    plddt = signals.get("plddt") or {}
    return _runs(lambda r: plddt.get(r, 100.0) < PLDDT_DISORDER_MAX, plddt, topo)


def _runs(passes_score, domain, topo: dict[int, str]) -> list[list[int]]:
    """Contiguous extracellular residues passing ``passes_score``, length >= MIN_RUN."""
    runs: list[list[int]] = []
    run: list[int] = []
    prev: int | None = None
    for res in sorted(domain):
        ok = passes_score(res) and _extracellular(topo.get(res, "?"))
        contiguous = prev is not None and res == prev + 1
        if ok and (not run or contiguous):
            run.append(res)
        else:
            if len(run) >= MIN_RUN:
                runs.append(run)
            run = [res] if ok else []
        prev = res
    if len(run) >= MIN_RUN:
        runs.append(run)
    return runs




def _site(
    res: int, run: list[int], signals: dict[str, Any], *, gene_symbol: str, uniprot_acc: str
) -> dict[str, Any]:
    seq = signals["sequence"]
    rb = seq[res - 1] if 1 <= res <= len(seq) else None
    ra = seq[res] if 1 <= res < len(seq) else None
    # The tolerant FEATURE is the whole low-pLDDT run; report its span so callers
    # know the insertion-tolerant region, not just the representative point.
    rng = residue_range(seq, run[0], run[-1]) if run else None
    return tagged_site(
        site_id=f"{gene_symbol}-disorder-{res}",
        gene_symbol=gene_symbol,
        uniprot_acc=uniprot_acc,
        det_path="disorder",
        site_kind="internal",
        insert_after_residue=res,
        residue_before=rb,
        residue_after=ra,
        residue_range_token=rng,
        topology_state="O",
        extracellular=True,
        compartment="extracellular",
        plddt=round(signals["plddt"][res], 1),
        median_conservation=signals["conservation"].get(res),
        rationale=(
            "exposed, 3D-clear insertion point within a low-pLDDT disordered "
            "extracellular run (>=4 aa)"
        ),
    )


def disorder_candidates(
    signals: dict[str, Any], *, gene_symbol: str, uniprot_acc: str
) -> list[dict[str, Any]]:
    """Emit a candidate at each solvent-exposed, feature-clear residue inside a
    low-pLDDT extracellular run, ranked exposure-first (then least-conserved).
    Downstream ``select_representatives`` NMS-thins these to representatives spaced
    across the loop, so both a short loop (ITGB1 98-105) and a long disordered
    ectodomain (TMEM123 27-140) get well-placed sites instead of one coarse anchor."""
    topo = signals["topology"]
    rsa = signals.get("rsa") or {}
    feat = signals["feature_dist"]
    picks: list[dict[str, Any]] = []
    for run in _flexible_runs(signals, topo):
        for res in run:
            if feat.get(res, 0.0) < FEATURE_DIST_MIN:
                continue  # the insertion point itself must clear functional atoms
            picks.append(_site(res, run, signals, gene_symbol=gene_symbol, uniprot_acc=uniprot_acc))
    disorder = signals.get("disorder") or {}
    picks.sort(
        key=lambda p: (
            # most flexible first. Both experimental sets say the working site is the most
            # flexible one available, not the most exposed: Tedman's junctions sit at the
            # 88th-93rd within-protein disorder percentile and our curated internal
            # positive controls at the 73rd-83rd. Exposure breaks ties below it.
            -disorder.get(p["insert_after_residue"], 0.0),
            -rsa.get(p["insert_after_residue"], 0.0),
            p["median_conservation"] if p["median_conservation"] is not None else 1.0,
        )
    )
    return picks
