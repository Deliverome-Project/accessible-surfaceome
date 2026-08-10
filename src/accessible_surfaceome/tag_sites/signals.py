"""Per-residue signals for the deterministic tag-site gates (Plan 4 Task 3).

The gates (``disorder.py``, ``surface_loop.py``) are pure functions over a
per-residue signal dict. This module computes that dict from source, in-repo:

* ``ortholog_conservation`` — per-residue conservation + indel-tolerance from a
  BLOSUM62 alignment of orthologs to the human canonical, reusing the repo's
  ``merge._sequence_identity`` aligner. This is the in-repo, auditable
  replacement for the external KIBBY conservation predictor.

The structural signals (per-residue pLDDT from the AlphaFold model, RSA via
``freesasa``, DSSP via ``pydssp``, and UniProt-feature 3D distances via
biopython) are the network-dependent half and are added alongside as the
orchestrator (Task 6) is wired to real inputs. They are kept out of this pure,
unit-tested core so the conservation signal can be tested without a network.
"""
from __future__ import annotations

from typing import Any

from accessible_surfaceome.merge._sequence_identity import _aligner, _sanitize


def ortholog_conservation(
    human_seq: str, ortholog_seqs: list[str]
) -> dict[str, dict[int, float]]:
    """Per-residue conservation + indel-tolerance from ortholog alignments.

    For each ortholog, globally align it (BLOSUM62) to the human canonical and,
    walking the alignment by human residue position (1-indexed), record whether
    the ortholog residue is identical, substituted, or a gap. Aggregated across
    orthologs:

    * ``conservation[res]`` = fraction of orthologs with an *identical* residue
      at that human position (high = conserved; the gate ranks LOW-conservation
      sites first). With no orthologs it is ``0.0`` — neutral, never blocking.
    * ``gap_freq[res]`` = fraction of orthologs aligned to a *gap* there (high =
      the position naturally tolerates indels — the indel-tolerance signal).
    """
    n = len(human_seq)
    identical = {r: 0 for r in range(1, n + 1)}
    gap = {r: 0 for r in range(1, n + 1)}
    k = len(ortholog_seqs)
    if k == 0:
        return {
            "conservation": {r: 0.0 for r in range(1, n + 1)},
            "gap_freq": {r: 0.0 for r in range(1, n + 1)},
        }

    aligner = _aligner()
    hs = _sanitize(human_seq)
    for orth in ortholog_seqs:
        os_ = _sanitize(orth)
        alignments = aligner.align(hs, os_)
        aln = alignments[0]
        human_row = str(aln[0])   # human canonical with '-' gaps
        orth_row = str(aln[1])    # ortholog aligned, with '-' gaps
        hpos = 0
        for c_h, c_o in zip(human_row, orth_row):
            if c_h == "-":
                continue          # insertion relative to human — no human position
            hpos += 1
            if c_o == "-":
                gap[hpos] += 1
            elif c_o == c_h:
                identical[hpos] += 1
            # else: substitution — counted implicitly (neither identical nor gap)

    return {
        "conservation": {r: identical[r] / k for r in range(1, n + 1)},
        "gap_freq": {r: gap[r] / k for r in range(1, n + 1)},
    }


def merge_signals(*parts: dict[str, Any]) -> dict[str, Any]:
    """Shallow-merge partial signal dicts (e.g. conservation + structural) into
    the single dict the gates consume. Later parts win on key collisions."""
    out: dict[str, Any] = {}
    for p in parts:
        out.update(p)
    return out
