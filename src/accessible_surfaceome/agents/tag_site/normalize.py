"""Topology + signal-peptide gate for literature-agent tag-site output.

The agent is *given* the computed per-residue topology, but it still proposes
topologically invalid sites (e.g. a `terminal_n` on a type-II protein whose
N-terminus is intracellular, or a tag inside a cleaved signal peptide). This
gate re-checks every proposed site against the computed topology and drops the
invalid ones with a reason — the literature-path analogue of the deterministic
path's extracellular gate. It also encodes the signal-peptide-cleavage rule the
tag-site controls emphasize (a tag upstream of the SP cleavage is silently lost).
"""
from __future__ import annotations

from typing import Any

_COMPARTMENT = {"O": "extracellular", "I": "intracellular", "M": "membrane", "S": "signal"}


def compartment_at(topology: str, res: int | None) -> str:
    if not topology or res is None or res < 1 or res > len(topology):
        return "unknown"
    return _COMPARTMENT.get(topology[res - 1], "unknown")


def signal_peptide_end(topology: str) -> int:
    """Length of the leading run of signal-peptide residues ('S'); 0 if none."""
    n = 0
    for ch in topology:
        if ch == "S":
            n += 1
        else:
            break
    return n


def topology_gate(site: dict[str, Any], topology: str) -> tuple[bool, str]:
    """(ok, reason). A site is rejected when it is not displayed extracellularly:
    an internal/terminal_c residue that isn't 'O'; a terminal_n whose mature
    N-terminus is intracellular (no extracellular N-terminus — type II); or a
    terminal_n placed within the signal peptide (cleaved off — a silent failure)."""
    kind = site.get("site_type") or site.get("site_kind")
    res = site.get("insert_after_residue")
    sp_end = signal_peptide_end(topology)

    if kind == "internal":
        c = compartment_at(topology, res)
        return (c == "extracellular", "" if c == "extracellular"
                else f"internal residue {res} is {c}, not extracellular")

    if kind == "terminal_c":
        c = compartment_at(topology, len(topology) if topology else None)
        return (c == "extracellular", "" if c == "extracellular"
                else f"C-terminus is {c}, not extracellular")

    if kind == "terminal_n":
        if sp_end > 0:
            if res is not None and res < sp_end:
                return False, (f"terminal_n at residue {res} is within the signal peptide "
                               f"(1-{sp_end}) — the tag is cleaved off with the SP (silent failure)")
            mature = compartment_at(topology, sp_end + 1)
            return (mature == "extracellular", "" if mature == "extracellular"
                    else f"mature N-terminus (residue {sp_end + 1}) is {mature}, not extracellular")
        c = compartment_at(topology, 1)
        return (c == "extracellular", "" if c == "extracellular"
                else f"N-terminus (residue 1) is {c} — no extracellular N-terminus to tag (type II)")

    return True, ""  # unknown kind → pass


def apply_topology_gate(sites: list[dict[str, Any]], topology: str) -> tuple[list[dict[str, Any]], list[tuple[dict[str, Any], str]]]:
    """Partition sites into (kept, rejected-with-reason) by the topology gate."""
    kept, rejected = [], []
    for s in sites:
        ok, reason = topology_gate(s, topology)
        (kept if ok else rejected).append(s if ok else (s, reason))
    return kept, rejected
