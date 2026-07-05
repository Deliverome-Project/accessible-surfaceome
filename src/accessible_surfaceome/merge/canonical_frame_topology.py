"""Project a variant's per-residue topology onto the canonical coordinate axis.

The viewer's ``IsoformsCard`` renders a per-residue topology bar for every
sequence variant of a protein — the canonical, its alternative isoforms, its
mouse / cynomolgus orthologs, and its close paralogs. Historically each bar
was scaled by the variant's RAW residue length and left-anchored at the
N-terminus (``TopologyBar``'s ``maxResidues`` prop). That layout silently
assumes N-terminal-anchored truncation: it only lines homologous features up
when every variant is a clean prefix of the canonical. It breaks for

* isoforms with alternate N-termini or internal splices,
* orthologs / paralogs of different length,

because a conserved TM helix then lands at a different x-position on each row.
(CD63's isoform P08962-3, for example, carries the canonical's TM3/TM4 but —
being N-terminally shorter — renders near the left edge, mis-aligned with the
canonical's TM3/TM4.)

The fix is a deterministic re-projection onto a SHARED axis: the canonical
sequence's coordinates. This module aligns the variant to the canonical using
the SAME BLOSUM62 global aligner every identity number already flows through
(:mod:`accessible_surfaceome.merge._sequence_identity`) and emits, for each
canonical residue position, the variant's topology character at the aligned
variant residue — or a gap char ``'-'`` where the variant has a gap at that
canonical position. Columns where the CANONICAL is a gap (variant insertions
relative to the canonical) are dropped: they have no canonical coordinate to
sit at, so they aren't representable on the shared axis.

The output string therefore always has ``len == len(canonical_sequence)``, so
the viewer can render every variant's bar full-width on one axis and have
homologous features line up column-for-column. A ``'-'`` renders as a blank /
transparent segment (the variant simply doesn't cover that canonical residue).

Invariant: the canonical projected against itself equals its own
``per_residue_topology`` (identical sequences align 1:1, no gaps). The unit
tests pin this alongside the N-terminal-deletion, internal-deletion, and
insertion cases.

Unlike :mod:`accessible_surfaceome.merge.ortholog_topology_projection` — which
projects the HUMAN topology ONTO an ortholog's residues to *repair* a noisy
ortholog DeepTMHMM call (variant-axis output, ortholog-only) — this projection
is purely a coordinate remap for DISPLAY, applies to all three variant types,
and never invents topology: it only relocates the variant's own per-residue
labels onto canonical coordinates.
"""

from __future__ import annotations

from accessible_surfaceome.merge._sequence_identity import _aligner, _sanitize

# The character emitted at a canonical position the variant doesn't cover (the
# variant has a gap aligned there). Chosen to be outside the DeepTMHMM alphabet
# {M, O, I, S, B} so the viewer can special-case it as a blank segment.
GAP_CHAR = "-"


def project_topology_onto_canonical_frame(
    *,
    canonical_sequence: str,
    variant_sequence: str,
    variant_topology: str,
) -> str | None:
    """Return ``variant_topology`` re-indexed onto the canonical residue axis.

    The output has ``len == len(canonical_sequence)``. For each canonical
    residue position it holds:

    * the variant's topology character, when a variant residue aligns there;
    * :data:`GAP_CHAR` (``'-'``), when the variant has a gap at that canonical
      position (a deletion relative to the canonical).

    Canonical-gap columns (variant insertions — no canonical coordinate) are
    dropped, so a variant that is longer than the canonical still projects to
    exactly ``len(canonical_sequence)`` characters.

    Returns ``None`` — signalling the caller to leave the field unset and let
    the viewer fall back to raw length-scaling — when the projection isn't
    well-defined:

    * any of the three inputs is empty, or
    * ``len(variant_topology) != len(variant_sequence)`` (the topology string
      must index the variant sequence 1:1; a mismatch means one of them is
      stale and the alignment columns wouldn't map cleanly), or
    * the aligner raises (non-standard residues that survive sanitisation,
      pathological input).
    """
    if not canonical_sequence or not variant_sequence or not variant_topology:
        return None
    if len(variant_topology) != len(variant_sequence):
        return None

    # Fast path: identical sequences project 1:1 (the canonical-vs-self case
    # the invariant pins, and any variant whose model sequence equals the
    # canonical). Skips an alignment and guarantees the no-gap result exactly.
    if variant_sequence == canonical_sequence:
        return variant_topology

    c_seq = _sanitize(canonical_sequence)
    v_seq = _sanitize(variant_sequence)
    try:
        alignment = _aligner().align(c_seq, v_seq)[0]
    except (ValueError, KeyError, IndexError):
        return None

    n_canon = len(canonical_sequence)
    # One slot per canonical residue, gap by default; aligned variant residues
    # overwrite their slot below. Canonical positions that never get written
    # (variant-gap columns) stay GAP_CHAR — which is exactly the deletion case.
    out: list[str] = [GAP_CHAR] * n_canon

    # alignment.aligned is shape (2, n_blocks, 2): equal-length, gap-free
    # blocks of [target_start, target_end] (canonical) / [query_start,
    # query_end] (variant). Within a block, canonical residue c_start+k aligns
    # to variant residue v_start+k, so copy the variant's topology char there.
    # Blocks only ever cover match columns, so canonical-gap and variant-gap
    # columns are both naturally excluded from the copy — insertions dropped,
    # deletions left as GAP_CHAR.
    aligned = alignment.aligned
    for (c_start, c_end), (v_start, v_end) in zip(aligned[0], aligned[1]):
        block_len = int(c_end) - int(c_start)
        for k in range(block_len):
            ci = int(c_start) + k
            vi = int(v_start) + k
            if 0 <= ci < n_canon and 0 <= vi < len(variant_topology):
                out[ci] = variant_topology[vi]

    return "".join(out)


__all__ = ["GAP_CHAR", "project_topology_onto_canonical_frame"]
