"""Geometry verification + repair for literature tag-site proposals.

The synthesis stage is handed the canonical sequence and per-residue topology,
but it reads them as raw strings and mis-derives coordinates from them (the
observed failure: a 26-residue signal-peptide run reported as 18, shifting every
downstream boundary by 8). This module re-derives the geometry IN CODE and either
repairs the proposal or rejects it, so a position that was never checked against
the sequence can no longer reach D1.
"""
from __future__ import annotations

import re

from .normalize import compartment_for_site, topology_gate


def check_residues(
    *, sequence: str, residue: int | None, before: str | None, after: str | None
) -> str | None:
    """None when ``before``/``after`` match ``sequence`` at the junction
    ``residue``|``residue+1``; else a human-readable mismatch reason.

    ``after`` is not checked at the C-terminus (there is no residue+1 there)."""
    if not sequence or residue is None:
        return "no sequence or residue to check"
    if residue < 1 or residue > len(sequence):
        return f"residue {residue} is outside the sequence (1-{len(sequence)})"
    real_before = sequence[residue - 1]
    if before and before != real_before:
        return f"claims {before}{residue} but sequence has {real_before}{residue}"
    if residue < len(sequence):
        real_after = sequence[residue]
        if after and after != real_after:
            return (
                f"claims {after} at {residue + 1} but sequence has "
                f"{real_after}{residue + 1}"
            )
    return None


# A junction the model spelled out in prose, e.g. "HSEAKK|GSKFDT". The pipe is the
# insertion point, so the junction residue is (start + len(left) - 1).
_JUNCTION_RE = re.compile(
    r"(?<![A-Za-z])([ACDEFGHIKLMNPQRSTVWY]{3,})\|([ACDEFGHIKLMNPQRSTVWY]{3,})(?![A-Za-z])"
)


def junction_from_prose(text: str | None, sequence: str) -> int | None:
    """The junction residue a pipe-delimited sequence window in ``text`` pins, or
    None when there is no window or it does not locate UNIQUELY in ``sequence``.

    Recovers the real position when the model described the right window but
    wrote the wrong integer. Ambiguity is a refusal, never a guess."""
    if not text or not sequence:
        return None
    for m in _JUNCTION_RE.finditer(text):
        left, right = m.group(1), m.group(2)
        window = left + right
        first = sequence.find(window)
        if first < 0 or sequence.find(window, first + 1) >= 0:
            continue  # absent, or ambiguous
        return first + len(left)
    return None


def _set_junction(site, residue: int, sequence: str) -> None:
    """Move ``site`` to ``residue`` and re-read its flanking residues FROM the
    sequence, so a repaired site can never keep the model's stale letters."""
    site.insert_after_residue = residue
    site.residue_before = sequence[residue - 1]
    site.residue_after = sequence[residue] if residue < len(sequence) else ""


def repair_proposal(site, *, sequence: str, sp_end: int = 0) -> str | None:  # noqa: ARG001
    """Repair ``site``'s junction in place; return the repair kind, or None when
    nothing was changed (either it already verifies, or it is unrecoverable).

    One repair, deterministic:

    * ``prose_window`` — the model spelled the right sequence window into its
      rationale but wrote the wrong integer; the window re-pins it uniquely.
      This is the TMEM123 K155 class.

    A mismatched site with no recoverable window is left ALONE for the caller to
    reject — relocating it by guesswork would launder a fabricated position.

    There is deliberately NO signal-peptide snap. Moving a ``terminal_n`` to the
    cleavage site looks principled but invents a position: for TMEM123 it yields
    A26, which the curated controls removed twice as topology-derived with no
    publication behind it, while the real validated site is A33 (EndoNB) — seven
    residues further in, in the unstructured region. A tag inside the peptide is
    rejected by the topology gate instead, which is the honest outcome."""
    if not sequence:
        return None

    if check_residues(
        sequence=sequence,
        residue=site.insert_after_residue,
        before=site.residue_before,
        after=site.residue_after,
    ) is None:
        return None  # already verifies

    pinned = junction_from_prose(site.rationale, sequence)
    if pinned is not None:
        _set_junction(site, pinned, sequence)
        return "prose_window"
    return None


def apply_geometry_pass(
    sites, *, sequence: str, topology: str, sp_end: int
):
    """Verify every site's junction against the computed sequence and topology,
    repairing what is deterministically recoverable. Returns
    ``(kept, rejected)`` where ``rejected`` is ``[(site, reason), ...]``.

    Order matters: repair FIRST, then gate. A repair moves the junction, so
    gating the pre-repair position would both miss real failures and drop sites
    the repair would have saved."""
    kept, rejected = [], []
    for site in sites:
        if repair_proposal(site, sequence=sequence, sp_end=sp_end):
            site.position_repaired = True

        mismatch = check_residues(
            sequence=sequence,
            residue=site.insert_after_residue,
            before=site.residue_before,
            after=site.residue_after,
        )
        if mismatch:
            rejected.append((site, f"residue mismatch: {mismatch}"))
            continue

        ok, reason = topology_gate(
            {"site_type": site.site_type, "insert_after_residue": site.insert_after_residue},
            topology,
            sp_end=sp_end,
        )
        if not ok:
            rejected.append((site, f"topology: {reason}"))
            continue

        # Record the compartment the gate just judged, rather than whatever the
        # model called it. The two used to disagree: the gate derived the real
        # compartment and kept the site, then the record stored the model's
        # string, which shipped sites reading `extracellular: false` on sites
        # that had passed the extracellular gate.
        site.topology_state = compartment_for_site(
            site.site_type, site.insert_after_residue, topology, sp_end=sp_end
        )
        kept.append(site)
    return kept, rejected
