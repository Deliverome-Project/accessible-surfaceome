"""Pure helpers for the Tedman GPCR HA control tag-site build.

No I/O — parses the Mendeley `ha_insert_position` string and projects the
junction onto a canonical UniProt sequence, following the "after N" convention
in data/tag_sites/positive_controls.md.
"""
from __future__ import annotations

from dataclasses import dataclass

from accessible_surfaceome.tag_sites.control import control_tag_site


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


def match_isoform_by_length(
    tedman_len: int, isoforms: list[tuple[str, int]], *, canonical_len: int | None = None
) -> str | None:
    """Match a Tedman isoform transcript (known only by protein length) to a UniProt
    isoform by exact length, when UNIQUE. `isoforms` = [(isoform_id, seq_len)].
    Excludes candidates whose length equals the canonical length (those aren't a
    distinct alternative isoform). Returns the isoform_id or None (no/ambiguous match)."""
    cands = [
        iid for iid, ln in isoforms
        if ln == tedman_len and (canonical_len is None or ln != canonical_len)
    ]
    return cands[0] if len(cands) == 1 else None


def _num(v):
    s = str(v).strip()
    if s in ("", "None"):
        return None
    return float(s)


def build_control_sites_for_gene(rows: list[dict], *, sources: list[dict]) -> list[dict]:
    """Turn verified canonical Tedman TSV rows for ONE gene into control TaggedSite
    dicts (screen_validated). Skips rows with verified != "true". site_id is
    ``{gene_symbol}-nterm-tedman``; a re-run overwrites the same id via the emitter's
    merge-by-site_id. junction empty -> bare N-terminal (insert_after_residue None,
    residue_after = expected_residue); junction N -> residue_before = expected_residue."""
    out: list[dict] = []
    for r in rows:
        if str(r.get("verified")).lower() != "true":
            continue
        j = str(r.get("junction_after_residue", "")).strip()
        junction = int(j) if j not in ("", "None") else None
        exp = (r.get("expected_residue") or "").strip() or None
        out.append(control_tag_site(
            site_id=f"{r['gene_symbol']}-nterm-tedman",
            gene_symbol=r["gene_symbol"], uniprot_acc=r["uniprot_acc"],
            insert_after_residue=junction,
            residue_before=exp if junction is not None else None,
            residue_after=None if junction is not None else exp,
            pme=_num(r.get("surface_expression_pme")),
            pme_sd=_num(r.get("surface_expression_sd")),
            sources=sources,
        ))
    return out


@dataclass(frozen=True)
class ProjectedJunction:
    """A junction carried from the construct's own numbering into ours.

    A junction is meaningless without the frame it was measured in. Tedman's positions are
    in the numbering of the specific transcript each plasmid was built from, and those are
    not always our proteoform: ENST00000579344 encodes CCR7 minus its first six residues,
    so his junction 23 is canonical residue 29. Comparing the raw integers made that look
    like a signal-peptide disagreement, which is the failure mode that silently puts a tag
    inside the signal peptide -- so the frame is resolved by sequence, not by trusting an
    isoform identifier to be right.
    """

    junction: int | None
    offset: int | None
    identity: float
    exact: bool
    note: str


MIN_ANCHOR_BLOCK = 15
"""Residues of identical sequence a matching block must have to carry a coordinate.

difflib will happily return a two-residue coincidental match, and taking the first block
containing the junction then produces a confident wrong answer. GABBR1 is the case that
caught it: its construct transcript is isoform Q9UBS5-2, whose N-terminus differs from the
canonical, and a short spurious block mapped junction 34 onto canonical residue 156 -- 137
residues past the canonical cleavage site, inside the folded ectodomain. The junction
residue itself matched by chance (H to H) while the surrounding sequence did not
(SHSPHLPRPHS vs TPKPHCQVNRT). A real correspondence is a long run, so require one.
"""

FLANK_CHECK = 5
"""Residues either side of the junction that must also be identical.

Block length alone is not enough: the junction can sit at the very edge of a long block,
where the context on one side belongs to a different region. Checking the immediate flanks
is what makes "the same position" mean the same local sequence.
"""


def project_junction(
    source_seq: str, target_seq: str, junction: int
) -> ProjectedJunction:
    """Map ``junction`` from ``source_seq``'s numbering into ``target_seq``'s.

    Uses the longest identical blocks between the two sequences rather than an alignment
    score: isoform and truncation differences are insertions and deletions of otherwise
    identical runs, so block matching maps a coordinate exactly where the two agree and
    reports honestly where they do not. A junction inside a block carries across with that
    block's offset; one landing in a gap has no counterpart and returns ``None`` rather
    than the nearest guess.
    """
    import difflib

    if not source_seq or not target_seq:
        return ProjectedJunction(None, None, 0.0, False, "missing sequence")
    sm = difflib.SequenceMatcher(None, source_seq, target_seq, autojunk=False)
    identity = sm.ratio()
    for block in sm.get_matching_blocks():
        if not (block.size and block.a < junction <= block.a + block.size):
            continue
        if block.size < MIN_ANCHOR_BLOCK:
            continue
        offset = block.b - block.a
        lo = max(0, junction - FLANK_CHECK)
        hi = min(len(source_seq), junction + FLANK_CHECK)
        if source_seq[lo:hi] != target_seq[lo + offset : hi + offset]:
            continue
        return ProjectedJunction(
            junction=junction + offset,
            offset=offset,
            identity=identity,
            exact=offset == 0,
            note=("same frame" if offset == 0
                  else f"construct numbering is offset {offset:+d} from ours"),
        )
    return ProjectedJunction(
        None, None, identity, False,
        "junction falls in a region the two sequences do not share",
    )
