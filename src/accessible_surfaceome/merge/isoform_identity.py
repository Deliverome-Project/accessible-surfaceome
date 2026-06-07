"""Sequence identity of an alternative isoform against its own canonical.

Alternative isoforms are splice products of the *same* gene, so — unlike
orthologs and paralogs — Ensembl Compara emits no pairwise identity for
them. We compute it directly from the sequences the topology sweep already
landed in ``topology_public.sequence`` (canonical + every ``human_isoforms``
row), reusing the shared BLOSUM62 helper at
:mod:`accessible_surfaceome.merge._sequence_identity` so isoform, paralog,
and ortholog identity numbers are computed by identical arithmetic and
can't drift apart.

Two numbers per isoform, both on a 0–100 scale and both relative to the
*canonical* sequence of the same protein:

* ``full_length_pct_identity`` — global BLOSUM62 alignment of the whole
  isoform against the whole canonical; identity = matches / max(len) * 100.
  ``max(len)`` is intentional: a pure truncation isoform now reads as its
  coverage percentage (e.g. TGOLN2 iso4 at 309/367 residues → ~84%), not
  100%. The old ``min(len)`` convention rounded all truncations to 100%
  which a reader naturally took to mean "identical to canonical" — that
  was wrong for "iso4 is clearly shorter than canonical". See the
  ``_sequence_identity`` docstring for the full reasoning.
* ``ecd_pct_identity`` — length-weighted per-extracellular-loop identity
  via :func:`paralog_ecd_identity.compute_ecd_identity`, same calculation
  as paralog/ortholog ECD numbers so the three columns in the viewer are
  directly comparable. ``None`` when either side has no extracellular
  ('O') residues.
"""

from __future__ import annotations

from dataclasses import dataclass

from accessible_surfaceome.merge._sequence_identity import pct_identity
from accessible_surfaceome.merge.paralog_ecd_identity import compute_ecd_identity


@dataclass(frozen=True)
class IsoformIdentityResult:
    """Identity of one alternative isoform against its canonical sequence."""

    full_length_pct_identity: float | None
    ecd_pct_identity: float | None
    # ECD percent similarity (identity + BLOSUM62-positive substitutions),
    # same definition as the ortholog/paralog ECD similarity. None when there
    # is no ECD to compare.
    ecd_pct_similarity: float | None = None


def compute_isoform_identity(
    *,
    canonical_topology: str,
    canonical_sequence: str,
    isoform_topology: str,
    isoform_sequence: str,
) -> IsoformIdentityResult:
    """Full-length + ECD identity of one isoform vs the canonical sequence.

    Full-length identity uses the shared ``pct_identity`` helper; ECD
    identity uses the paralog ECD aggregator (same per-loop helper).
    """
    full = pct_identity(canonical_sequence, isoform_sequence)
    ecd = compute_ecd_identity(
        human_topology=canonical_topology,
        human_sequence=canonical_sequence,
        paralog_topology=isoform_topology,
        paralog_sequence=isoform_sequence,
    )
    return IsoformIdentityResult(
        full_length_pct_identity=full,
        ecd_pct_identity=ecd.ecd_pct_identity,
        ecd_pct_similarity=ecd.ecd_pct_similarity,
    )
