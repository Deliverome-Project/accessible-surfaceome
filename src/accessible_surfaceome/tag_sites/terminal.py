"""Path 2c: terminal + snorkel tag candidates (pure-topology, no structure).

Termini are the classic tag sites. Detection needs only the DeepTMHMM per-residue
state at residue 1 and residue L (no pLDDT/RSA/DSSP):

  * extracellular N-terminus ('O' at residue 1)  -> direct N-terminal tag;
  * extracellular C-terminus ('O' at residue L)  -> direct C-terminal tag;
  * C-terminus known-intracellular ('I'/'M')      -> C-terminal *snorkel* (a
    TM-snorkeling linker presents the tag on the surface) as the fallback when
    no accessible terminus exists.

Per the chosen rule (all-applicable + snorkel fallback): every APPLICABLE
extracellular terminus is emitted as its own site, and a C-terminal snorkel is
emitted only when the C-terminus is intracellular. These are single, named sites
(one per terminus) — they do NOT go through ``select_representatives`` NMS.
"""
from __future__ import annotations

from typing import Any

from .model import tagged_site
from .surface_loop import _extracellular


def _plddt_at(plddt: dict[int, float], res: int) -> float | None:
    v = plddt.get(res)
    return round(v, 1) if v is not None else None


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

    # Extracellular C-terminus -> direct C-terminal tag (junction AFTER residue L).
    if _extracellular(c_state):
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
    elif c_state in ("I", "M"):
        # KNOWN intracellular (or within-membrane) C-terminus -> C-terminal SNORKEL: a
        # TM-snorkeling linker presents the C-terminal tag on the cell surface.
        # The fallback terminal option when no terminus is natively accessible.
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
                topology_state=c_state if c_state in ("I", "M") else "I",
                extracellular=False,
                compartment="membrane" if c_state == "M" else "intracellular",
                plddt=_plddt_at(plddt, length),
                confidence="low",
                rationale=(
                    "C-terminus not extracellular (topology "
                    f"'{c_state}' at residue L) — C-terminal snorkel presents the tag on the "
                    "surface via a TM-snorkeling linker (fallback: no accessible terminus)"
                ),
            )
        )

    return out
