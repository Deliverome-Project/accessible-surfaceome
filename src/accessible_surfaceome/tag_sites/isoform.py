"""Per-isoform tag-site classification (shared vs isoform-unique).

AFDB serves per-isoform structures (``AF-{isoform}-F1``) for most isoforms, so the
deterministic gates can run on an isoform's OWN model exactly like the canonical
(same :func:`run.run_gene`, with the isoform accession + sequence + topology).
This module classifies the resulting per-isoform deterministic sites against the
canonical prediction, by aligning the isoform sequence to the canonical:

  * ``"shared"`` — the isoform site maps (via alignment) to a canonical
    deterministic site at the same residue (+/- :data:`SHARED_TOL`). The
    prediction transfers to the isoform.
  * ``"unique"`` — no canonical counterpart: the site sits in an
    isoform-specific region (alt exon / truncation, so the residue has no
    canonical coordinate) or fires on the isoform structure where the canonical
    has no nearby site.

Pins are returned on the isoform's OWN residue axis (``left_pct``), matching a
TopologyBar rendered from the isoform's ``per_residue_topology``.
"""
from __future__ import annotations

from typing import Any

from accessible_surfaceome.merge._sequence_identity import _aligner, _sanitize

SHARED_TOL = 3  # residues: an isoform site within +/-3 of a canonical site is "shared"


def isoform_to_canonical_map(
    canonical_sequence: str, isoform_sequence: str
) -> dict[int, int]:
    """Map each isoform residue (1-indexed) -> the aligned canonical residue
    (1-indexed). Isoform residues with no canonical counterpart (an insertion /
    isoform-specific region) are absent from the map. Global BLOSUM62 alignment,
    the same aligner the identity + canonical-frame projection use."""
    if not canonical_sequence or not isoform_sequence:
        return {}
    if canonical_sequence == isoform_sequence:
        return {i: i for i in range(1, len(isoform_sequence) + 1)}
    try:
        aln = _aligner().align(_sanitize(canonical_sequence), _sanitize(isoform_sequence))[0]
    except (ValueError, KeyError, IndexError):
        return {}
    out: dict[int, int] = {}
    # aligned[0] = canonical blocks, aligned[1] = isoform blocks; each block is a
    # gap-free 1:1 run (0-indexed, half-open) — copy canonical coords onto isoform.
    for (c0, c1), (i0, i1) in zip(aln.aligned[0], aln.aligned[1]):
        for off in range(c1 - c0):
            out[i0 + off + 1] = c0 + off + 1
    return out


def _axis_residue(site: dict[str, Any], length: int) -> int:
    """The residue a site sits at on its sequence's own axis: terminal_c -> the
    C-terminus (length); internal / terminal_n -> insert_after_residue (null->1)."""
    if site["site_kind"] == "terminal_c":
        return length
    r = site.get("insert_after_residue")
    return 1 if (r is None or r == 0) else int(r)


def classify_isoform_sites(
    *,
    isoform_id: str,
    isoform_sites: list[dict[str, Any]],
    isoform_sequence: str,
    canonical_sites: list[dict[str, Any]],
    canonical_sequence: str,
) -> list[dict[str, Any]]:
    """Tag each isoform DETERMINISTIC site ``"shared"`` or ``"unique"`` vs the
    canonical deterministic prediction, and return viewer-ready pins on the
    isoform axis (``left_pct`` in 0..100)."""
    iso_len = len(isoform_sequence)
    if iso_len == 0:
        return []
    imap = isoform_to_canonical_map(canonical_sequence, isoform_sequence)
    canon_len = len(canonical_sequence)
    canon_res = sorted(
        {
            _axis_residue(s, canon_len)
            for s in canonical_sites
            if s.get("provenance") == "deterministic_computed"
        }
    )
    pins: list[dict[str, Any]] = []
    for s in isoform_sites:
        if s.get("provenance") != "deterministic_computed":
            continue
        ri = _axis_residue(s, iso_len)
        rc = imap.get(ri)  # aligned canonical residue, or None (isoform-specific)
        shared = rc is not None and any(abs(rc - c) <= SHARED_TOL for c in canon_res)
        pins.append(
            {
                "site_id": f"{s['site_id']}::iso::{isoform_id}",
                "isoform_id": isoform_id,
                "classification": "shared" if shared else "unique",
                "det_path": s.get("det_path"),
                "site_kind": s["site_kind"],
                "tag_type": s.get("tag_type"),
                "isoform_residue": ri,
                "canonical_residue": rc,
                "left_pct": (ri / iso_len) * 100.0,
            }
        )
    return pins
