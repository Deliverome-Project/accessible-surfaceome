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
