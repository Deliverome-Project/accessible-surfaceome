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


def topology_runs(topology: str) -> list[tuple[str, int, int]]:
    """``[(char, start, end), ...]`` — the contiguous spans of ``topology``, in
    1-based inclusive coordinates. The authoritative boundary source: derived
    here so neither the model nor a caller has to count the raw string."""
    if not topology:
        return []
    runs: list[tuple[str, int, int]] = []
    start = 1
    for i in range(1, len(topology)):
        if topology[i] != topology[i - 1]:
            runs.append((topology[i - 1], start, i))
            start = i + 1
    runs.append((topology[-1], start, len(topology)))
    return runs


def signal_peptide_end(topology: str) -> int:
    """Length of the leading run of signal-peptide residues ('S'); 0 if none."""
    n = 0
    for ch in topology:
        if ch == "S":
            n += 1
        else:
            break
    return n


def first_mature_residue(topology: str, sp_end: int) -> int:
    """The first residue at/after ``sp_end + 1`` that the topology does NOT call
    signal peptide.

    Needed because ``sp_end`` may be authoritative (UniProt) while ``topology``
    is a prediction (DeepTMHMM), and the two disagree on the cleavage site for a
    real fraction of genes. Skipping the residual 'S' run reads the mature
    N-terminus's true compartment under either numbering."""
    i = max(sp_end, 0)
    while i < len(topology) and topology[i] == "S":
        i += 1
    return i + 1


def compartment_for_site(
    kind: str | None, res: int | None, topology: str, *, sp_end: int
) -> str:
    """The compartment a site is DISPLAYED in — the single derivation the gate
    judges on and the record records.

    It is per-kind, not simply ``compartment_at(res)``: a terminal_c is judged at
    the C-terminus and a terminal_n at the MATURE N-terminus (past any residual
    signal peptide), not at whatever residue the junction names. Returns
    "unknown" rather than guessing, so a caller can never read absence as
    extracellular."""
    if kind == "internal":
        return compartment_at(topology, res)
    if kind == "terminal_c":
        return compartment_at(topology, len(topology) if topology else None)
    if kind == "terminal_n":
        if sp_end > 0:
            return compartment_at(topology, first_mature_residue(topology, sp_end))
        return compartment_at(topology, 1)
    return "unknown"


def topology_gate(
    site: dict[str, Any], topology: str, *, sp_end: int | None = None
) -> tuple[bool, str]:
    """(ok, reason). A site is rejected when it is not displayed extracellularly:
    an internal/terminal_c residue that isn't 'O'; a terminal_n whose mature
    N-terminus is intracellular (no extracellular N-terminus — type II); or a
    terminal_n placed within the signal peptide (cleaved off — a silent failure).

    ``sp_end`` overrides the signal-peptide length derived from ``topology``. Pass
    the UniProt ``Signal`` feature end when you have it: DeepTMHMM and UniProt
    disagree often enough that trusting the prediction drops correct
    mature-N-terminus sites."""
    kind = site.get("site_type") or site.get("site_kind")
    res = site.get("insert_after_residue")
    sp_end = signal_peptide_end(topology) if sp_end is None else sp_end

    # The signal-peptide check is not a compartment question: the residue may sit
    # in an 'S' run that is cleaved away, so it is judged before the compartment.
    if kind == "terminal_n" and sp_end > 0 and res is not None and res < sp_end:
        return False, (f"terminal_n at residue {res} is within the signal peptide "
                       f"(1-{sp_end}) — the tag is cleaved off with the SP (silent failure)")

    if kind not in {"internal", "terminal_c", "terminal_n"}:
        return True, ""  # unknown kind → pass

    c = compartment_for_site(kind, res, topology, sp_end=sp_end)
    if c == "extracellular":
        return True, ""
    where = {
        "internal": f"internal residue {res}",
        "terminal_c": "C-terminus",
        "terminal_n": (f"mature N-terminus (residue {sp_end + 1})" if sp_end > 0
                       else "N-terminus (residue 1)"),
    }[kind]
    tail = " — no extracellular N-terminus to tag (type II)" if (
        kind == "terminal_n" and sp_end == 0) else ", not extracellular"
    return False, f"{where} is {c}{tail}"


def apply_topology_gate(
    sites: list[dict[str, Any]], topology: str, *, sp_end: int | None = None
) -> tuple[list[dict[str, Any]], list[tuple[dict[str, Any], str]]]:
    """Partition sites into (kept, rejected-with-reason) by the topology gate."""
    kept, rejected = [], []
    for s in sites:
        ok, reason = topology_gate(s, topology, sp_end=sp_end)
        (kept if ok else rejected).append(s if ok else (s, reason))
    return kept, rejected
