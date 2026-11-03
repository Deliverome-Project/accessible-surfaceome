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


def _c_terminus_cleaved(
    signals: dict[str, Any], length: int
) -> tuple[int, int] | None:
    """The C-terminal propeptide covering residue ``length``, if any.

    A GPI-anchored protein's C-terminal propeptide is cleaved at the omega site
    and replaced by the anchor, so the precursor C-terminus is not a position on
    the mature protein. The topology string cannot see this: it ends
    extracellular either way.

    The mechanism is worth stating correctly, because the obvious guess is wrong.
    A tag appended there is not simply carried off with the propeptide -- the GPI
    signal has to BE the C-terminus to be recognised, so appending past it
    prevents anchoring instead. Either way the result is not a surface-anchored
    tagged protein, which is what this lane claims to propose. The literature
    does it the other way round: IgSF21's HA tag went in "4 aa residues upstream
    of the putative C-terminal GPI anchor signal sequence" (Tanabe et al. 2017,
    PMID 28864826) and CA-IV's HA tag REPLACED the anchor rather than following
    it (Lin et al. 2025, PMID 41175373).

    Only a propeptide COVERING the C-terminus counts. An N-terminal or internal
    propeptide says nothing about that end, and refusing on the mere presence of
    a Propeptide feature would be the over-broad version of this.
    """
    span = signals.get("propeptide")
    if not span:
        return None
    start, end = int(span[0]), int(span[1])
    return (start, end) if start <= length <= end else None


def terminal_candidates(
    signals: dict[str, Any],
    *,
    gene_symbol: str,
    uniprot_acc: str,
    rejected_sink: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Emit the applicable terminal tag sites (ecto N-term, ecto C-term) plus a
    C-terminal snorkel fallback when the C-terminus is not extracellular.

    A C-terminus inside a cleaved propeptide is REFUSED — categorically, not
    ranked down. Cohort-wide, 115 of the 981 deterministic ``terminal_c`` rows in
    ``tag_site_public`` are on genes NetGPI calls anchored, and every one sits
    past its omega site at the full precursor length: the one position guaranteed
    absent from the mature chain. That is the same
    category as a glycosylation sequon ("this residue has a job"), not the
    threshold category where this repo has learned to rank instead of veto.

    ``rejected_sink`` receives each refusal, because a veto whose false
    negatives leave no trace is how three bad gates survived here until audits
    went looking. Without it a reader cannot tell "no C-terminal site because it
    is cleaved" from "no C-terminal site because the terminus is intracellular".
    """
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
    cleaved = _c_terminus_cleaved(signals, length)
    if cleaved and (c_term_ec or c_state in ("I", "M")):
        # Refused for BOTH the direct tag and the snorkel below: a snorkel
        # presents a C-terminal tag through a TM-snorkeling linker, so it needs
        # a C-terminus to attach to. Emitting it here would relabel the same
        # dead position rather than offer an alternative.
        if rejected_sink is not None:
            rejected_sink.append(
                {
                    "gene_symbol": gene_symbol,
                    "uniprot_acc": uniprot_acc,
                    "site_kind": "terminal_c",
                    "insert_after_residue": length,
                    "gate": "propeptide_cleaved",
                    "reason": (
                        f"residue {length} lies in the cleaved C-terminal "
                        f"propeptide {cleaved[0]}-{cleaved[1]}; the terminus is "
                        "removed and replaced (GPI anchor) before the protein "
                        "reaches the surface"
                    ),
                }
            )
        c_term_ec = False
        c_state = "cleaved"
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
