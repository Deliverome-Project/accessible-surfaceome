"""Path 2c: terminal + snorkel tag candidates (pure-topology, no structure).

Termini are the classic tag sites. Detection needs only the DeepTMHMM per-residue
states (no pLDDT/RSA/DSSP):

  * extracellular N-terminus -> direct N-terminal tag. Either 'O' at residue 1,
    OR — for a protein with a signal peptide (leading 'S' run) — the MATURE
    N-terminus after signal-peptide cleavage (the first residue past the 'S' run,
    when it is 'O'); the tag is placed AFTER the cleavage site so the signal
    peptidase can't take it with the cleaved signal;
  * extracellular C-terminus ('O' at residue L)  -> direct C-terminal tag;
  * C-terminus not extracellular ('I'/'M')        -> C-terminal *snorkel* (a
    TM-snorkeling linker presents the tag on the surface), emitted ONLY as the
    last-resort fallback when NEITHER terminus is extracellular.

Per the chosen rule (all-applicable + snorkel fallback): every APPLICABLE
extracellular terminus is emitted as its own site, and a C-terminal snorkel is
emitted only when neither terminus is accessible. These are single, named sites
(one per terminus) — they do NOT go through ``select_representatives`` NMS.
"""
from __future__ import annotations

from typing import Any

from .model import tagged_site
from .surface_loop import _extracellular


def _plddt_at(plddt: dict[int, float], res: int) -> float | None:
    v = plddt.get(res)
    return round(v, 1) if v is not None else None


def _signal_peptide_end(topo: dict[int, str], length: int) -> int:
    """Last residue index of a LEADING signal-peptide run ('S' from residue 1),
    or 0 when residue 1 is not a signal residue. DeepTMHMM emits 'S' for the
    cleaved signal peptide (e.g. EGFR: residues 1-24 'S', then 'O')."""
    if topo.get(1) != "S":
        return 0
    i = 1
    while i <= length and topo.get(i) == "S":
        i += 1
    return i - 1  # last 'S' position


def terminal_candidates(
    signals: dict[str, Any], *, gene_symbol: str, uniprot_acc: str
) -> list[dict[str, Any]]:
    """Emit the applicable terminal tag sites (ecto N-term, ecto C-term) plus a
    C-terminal snorkel fallback when the C-terminus is not extracellular."""
    seq: str = signals["sequence"]
    topo: dict[int, str] = signals["topology"]
    plddt: dict[int, float] = signals.get("plddt") or {}
    length = len(seq)
    if length == 0:
        return []

    out: list[dict[str, Any]] = []
    n_state = topo.get(1, "?")
    c_state = topo.get(length, "?")
    n_term_ec = False  # is there an accessible extracellular N-terminus?

    # Extracellular N-terminus -> direct N-terminal tag (junction BEFORE residue 1;
    # insert_after_residue=None, residue_before=None per the "after N" convention).
    if _extracellular(n_state):
        out.append(
            tagged_site(
                site_id=f"{gene_symbol}-terminal-n",
                gene_symbol=gene_symbol,
                uniprot_acc=uniprot_acc,
                det_path="terminal",
                site_kind="terminal_n",
                insert_after_residue=None,
                residue_before=None,
                residue_after=seq[0],
                topology_state="O",
                extracellular=True,
                compartment="extracellular",
                plddt=_plddt_at(plddt, 1),
                confidence="high",
                rationale="extracellular N-terminus (topology 'O' at residue 1) — direct N-terminal tag",
            )
        )
        n_term_ec = True
    else:
        # Signal-peptide protein: the MATURE N-terminus (first residue past the
        # leading 'S' run) is extracellular after cleavage. Place the tag AFTER the
        # cleavage site so the signal peptidase can't take it with the signal.
        sp_end = _signal_peptide_end(topo, length)
        if sp_end and _extracellular(topo.get(sp_end + 1, "?")):
            out.append(
                tagged_site(
                    site_id=f"{gene_symbol}-terminal-n",
                    gene_symbol=gene_symbol,
                    uniprot_acc=uniprot_acc,
                    det_path="terminal",
                    site_kind="terminal_n",
                    insert_after_residue=sp_end,
                    residue_before=seq[sp_end - 1],  # last signal residue
                    residue_after=seq[sp_end],  # first mature residue
                    topology_state="O",
                    extracellular=True,
                    compartment="extracellular",
                    plddt=_plddt_at(plddt, sp_end + 1),
                    confidence="high",
                    rationale=(
                        "mature extracellular N-terminus after signal-peptide cleavage "
                        f"(signal 1-{sp_end}, 'O' at residue {sp_end + 1}) — N-terminal "
                        "tag placed just after the cleavage site"
                    ),
                )
            )
            n_term_ec = True

    # Extracellular C-terminus -> direct C-terminal tag (junction AFTER residue L).
    c_term_ec = _extracellular(c_state)
    if c_term_ec:
        out.append(
            tagged_site(
                site_id=f"{gene_symbol}-terminal-c",
                gene_symbol=gene_symbol,
                uniprot_acc=uniprot_acc,
                det_path="terminal",
                site_kind="terminal_c",
                insert_after_residue=length,
                residue_before=seq[-1],
                residue_after=None,
                topology_state="O",
                extracellular=True,
                compartment="extracellular",
                plddt=_plddt_at(plddt, length),
                confidence="high",
                rationale="extracellular C-terminus (topology 'O' at residue L) — direct C-terminal tag",
            )
        )

    # C-terminal SNORKEL — last-resort fallback ONLY when NEITHER terminus is
    # extracellular. A TM-snorkeling linker presents the C-terminal tag on the
    # surface. If either terminus is natively accessible (e.g. EGFR's mature
    # N-terminus), that real ecto-terminus is preferred and no snorkel is emitted.
    if not n_term_ec and not c_term_ec and c_state in ("I", "M"):
        out.append(
            tagged_site(
                site_id=f"{gene_symbol}-snorkel-c",
                gene_symbol=gene_symbol,
                uniprot_acc=uniprot_acc,
                det_path="snorkel",
                site_kind="terminal_c",
                insert_after_residue=length,
                residue_before=seq[-1],
                residue_after=None,
                topology_state=c_state,
                extracellular=False,
                compartment="membrane" if c_state == "M" else "intracellular",
                plddt=_plddt_at(plddt, length),
                confidence="low",
                rationale=(
                    "C-terminus not extracellular (topology "
                    f"'{c_state}' at residue L) and no accessible N-terminus — C-terminal "
                    "snorkel presents the tag on the surface via a TM-snorkeling linker "
                    "(fallback: no natively accessible terminus)"
                ),
            )
        )

    return out
