"""Pure helpers for the Tedman GPCR HA control tag-site build.

No I/O — parses the Mendeley `ha_insert_position` string and projects the
junction onto a canonical UniProt sequence, following the "after N" convention
in data/tag_sites/positive_controls.md.
"""
from __future__ import annotations

from dataclasses import dataclass


def parse_ha_position(value: str) -> int:
    """`"0-1"` -> 0, `"27-28"` -> 27 (the residue the HA tag is inserted AFTER,
    in the construct's own 1-indexed numbering). Raises ValueError on junk."""
    left = str(value).strip().split("-", 1)[0]
    if not left.lstrip("-").isdigit():
        raise ValueError(f"unparseable ha_insert_position: {value!r}")
    return int(left)


@dataclass(frozen=True)
class JunctionMapping:
    insert_after_residue: int | None  # None == bare N-terminal (before residue 1)
    residue_before: str | None
    residue_after: str | None
    residue_label: str | None
    verified: bool


def map_junction_to_canonical(junction: int, canonical_seq: str) -> JunctionMapping:
    """Project a construct-ORF junction onto the canonical UniProt sequence.

    junction 0  -> bare N-terminal tag (insert_after_residue None); anchor is
                   residue 1 (residue_after). verified iff the sequence is non-empty.
    junction N>0 -> tag between residues N and N+1; residue_before = seq[N-1].
                    verified iff 1 <= N <= len(seq).
    """
    seq = canonical_seq or ""
    if junction <= 0:
        after = seq[0] if seq else None
        return JunctionMapping(None, None, after, None, verified=bool(seq))
    if junction > len(seq):
        return JunctionMapping(junction, None, None, None, verified=False)
    before = seq[junction - 1]
    after = seq[junction] if junction < len(seq) else None
    return JunctionMapping(junction, before, after, f"{before}{junction}", verified=True)
