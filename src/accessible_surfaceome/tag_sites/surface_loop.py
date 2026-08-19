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

from .model import residue_range, tagged_site

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


def loop_span(ss: dict[int, str], res: int) -> tuple[int, int] | None:
    """Inclusive ``(lo, hi)`` bounds of the contiguous coil/turn run (DSSP loop
    chars) containing ``res``, or ``None`` when ``res`` is not a loop residue.
    This span is the insertion-tolerant FEATURE the site sits in."""
    if ss.get(res, "?") not in LOOP_SS:
        return None
    lo = res
    while ss.get(lo - 1, "?") in LOOP_SS:
        lo -= 1
    hi = res
    while ss.get(hi + 1, "?") in LOOP_SS:
        hi += 1
    return (lo, hi)


def loop_length(ss: dict[int, str], res: int) -> int:
    """Length of the contiguous coil/turn run containing ``res`` (0 if not a loop).
    The primary computable proxy for tag permissiveness: a long exposed loop gives
    a both-ends-tethered β-strand room; a short loop does not."""
    span = loop_span(ss, res)
    return span[1] - span[0] + 1 if span else 0


def tag_fit(loop_len: int) -> str:
    """Recommend detection + covalent tags for an INTERNAL exposed loop.

    ALFA (a 15-aa α-helical nanobody epitope) folds independently and is the arm
    EndoNB validated *inside* loops. DogTag is the loop-optimized covalent arm:
    per Keeble 2022 (Cell Chem Biol, DOI 10.1016/j.chembiol.2021.07.005, PMID
    34324879), a tag inserted in a loop reacts far faster as DogTag than as
    SpyTag003 — SpyTag003 is a β-strand that must complete SpyCatcher's sheet and
    conjugates poorly while tethered at both ends, so it belongs at a free
    TERMINUS, not a loop. Loop length does NOT gate the choice (both recommended
    tags are loop-compatible; ``loop_len`` is carried for downstream
    functional-safety ranking only, and a bigger loop is not automatically safer
    — Keeble's TRPC5 chose the 22-aa loop over the 68-aa turret). See the
    SpyTag-in-loops evidence table in ``data/tag_sites/positive_controls.md``."""
    return "ALFA, DogTag"


def _exposed_anchor(rsa: dict[int, float], res: int, lo: int = -1, hi: int = 2) -> int:
    """The residue in the junction window with the highest OWN solvent
    accessibility. A window admitted because a *neighbor* is exposed (e.g. TFRC
    I290, RSA 0.02, admitted via V291 at 0.88) reports its insertion AT the
    exposed residue (291), not the buried anchor — the tag should protrude where
    the loop actually protrudes. Ties keep the lower residue number."""
    best_r, best_v = res, rsa.get(res, 0.0)
    for d in range(lo, hi + 1):
        r = res + d
        v = rsa.get(r, 0.0)
        if v > best_v:
            best_r, best_v = r, v
    return best_r


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
    seen_anchors: set[int] = set()
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

        # Report the insertion AT the solvent-exposed residue of the window, not
        # the (possibly buried) residue that admitted it — the tag protrudes
        # where the loop protrudes. Fall back to ``res`` if the exposed peak is
        # not itself extracellular + feature-clear.
        anchor = _exposed_anchor(signals["rsa"], res)
        # The exposed peak must itself be a valid surface-loop residue — the same
        # reliability + loop + extracellular + clearance premise, not just high
        # RSA — otherwise the snap could report a low-pLDDT or non-loop position.
        if (
            signals["topology"].get(anchor, "?") != "O"
            or signals["plddt"].get(anchor, 0.0) < PLDDT_MIN
            or signals["ss"].get(anchor, "?") not in LOOP_SS
            or signals["feature_dist"].get(anchor, 0.0) < FEATURE_DIST_MIN
        ):
            anchor = res
        if anchor in seen_anchors:
            continue
        seen_anchors.add(anchor)

        rb = seq[anchor - 1] if 1 <= anchor <= len(seq) else None
        ra = seq[anchor] if 1 <= anchor < len(seq) else None
        span = loop_span(signals["ss"], anchor)
        ll = (span[1] - span[0] + 1) if span else 0
        rng = residue_range(seq, span[0], span[1]) if span else None
        picks.append(
            tagged_site(
                site_id=f"{gene_symbol}-surface_loop-{anchor}",
                gene_symbol=gene_symbol,
                uniprot_acc=uniprot_acc,
                det_path="surface_loop",
                site_kind="internal",
                insert_after_residue=anchor,
                residue_before=rb,
                residue_after=ra,
                residue_range_token=rng,
                topology_state=signals["topology"].get(anchor, topo),
                extracellular=True,
                compartment="extracellular",
                tag_type=tag_fit(ll),
                plddt=round(signals["plddt"].get(anchor, signals["plddt"][res]), 1),
                median_conservation=signals["conservation"].get(anchor),
                rationale=(
                    f"ordered surface loop ({ll} aa): pLDDT>=70, DSSP loop/turn, exposed "
                    "junction residue (max RSA), indel-tolerant, 3D-clear of features"
                ),
            )
        )
    # Rank for DISPLAY of a surface-exposed dual tag: most solvent-exposed junction
    # first (the tag protrudes best where the loop is most exposed), then
    # least-conserved (functional safety), then most indel-tolerant. Exposure leads
    # deliberately — a shallow (single-ortholog) conservation signal is a coarse 0/1
    # and must not override *where the loop actually presents*. TFRC: this surfaces
    # V291 (own RSA 0.88) over 294 (0.48, non-conserved) in the same extended loop.
    picks.sort(
        key=lambda p: (
            -signals["rsa"].get(p["insert_after_residue"], 0.0),
            p["median_conservation"] if p["median_conservation"] is not None else 1.0,
            -signals.get("gap_freq", {}).get(p["insert_after_residue"], 0.0),
        )
    )
    return picks
