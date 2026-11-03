"""The MEMBER's own sequence and topology — the frame a tag position must use.

A Library-1 member's protein is its designed CDS translated. For a substantial
minority that is not the protein its accession names: of the 566 internal-site
members, 47 resolve under ``human_isoforms``, 24 under ``library_designed_orf``
and 43 under a non-human ortholog cohort. A position expressed in canonical
coordinates is, for any of those, a position in a *different protein* — with a
plausible length and a plausible helix count, which is what makes it dangerous.

So resolution keys on **sha256 of the sequence**, never on the accession. The
spike's own verification script keyed on the accession, looked KCNN2 up under
``cohort='human_canonical'``, found nothing because its ``topology_acc`` is
``l1-p1037`` (a designed ORF), and read the miss as "junction out of range" —
nearly reporting two real loop sites as non-loops. A miss has to be loud.

This module also owns the question "is this junction in a LOOP?", because
``site_kind`` cannot answer it. The five published literature sites at positions
4-5 are topologically identical — no signal peptide, extracellular N-terminus,
junction inside the N-terminal ``O`` run — yet two are labelled ``internal`` and
three ``terminal_n``, and both paralogue pairs (ABCC1/ABCC2, SLC5A1/SLC5A4)
disagree with their own partner. There is no defined boundary between "terminal"
and "internal" for a tag a few residues into an extracellular tail, so the model
picks per call. Loop-ness is derived from the topology instead: an extracellular
run is a loop only when a membrane helix flanks it on BOTH sides.
"""

from __future__ import annotations

import csv
import hashlib
from dataclasses import dataclass
from pathlib import Path

#: Per-residue topology alphabet (DeepTMHMM): extracellular, membrane,
#: intracellular, signal peptide, beta-barrel strand.
_EXTRACELLULAR = "O"
_MEMBRANE = frozenset({"M", "B"})

#: Where an extracellular run sits relative to the membrane helices.
N_TERMINAL = "n_terminal"
INTER_TM = "inter_tm"
C_TERMINAL = "c_terminal"
NO_TM = "no_tm"


@dataclass(frozen=True)
class Member:
    """One row of ``data/tag_sites/l1_internal_members.tsv``.

    Field names match the vendored TSV's columns exactly. Parse that file by
    column NAME — the three ``longest_ecto_run_*`` columns are inserted at
    positions 13-15 rather than appended, so positional readers shift.
    """

    candidate_id: str
    library: str
    candidate_set: str
    species: str
    gene_symbol: str
    topology_acc: str
    topology_cohort: str
    sequence_sha256: str
    ordered_length_aa: int
    tm_count: int
    longest_inter_tm_ecto_run_aa: int
    longest_ecto_run_aa: int
    longest_ecto_run_start: int
    longest_ecto_run_position: str
    placement: str
    gpi_rerouted: bool
    shed_risk: str


@dataclass(frozen=True)
class MemberFrame:
    """A member paired with the exact sequence its positions are numbered in."""

    member: Member
    topology_acc_full: str
    sequence: str
    topology: str

    @property
    def numbered_against(self) -> str:
        """The sha256 that identifies this frame.

        Stamped on every emitted site. A published position is only
        unambiguous if the sequence defining it travels with it.
        """
        return self.member.sequence_sha256


@dataclass(frozen=True)
class Run:
    """A contiguous extracellular stretch, 1-based and inclusive."""

    start: int
    end: int
    position: str

    @property
    def length(self) -> int:
        return self.end - self.start + 1

    @property
    def is_loop(self) -> bool:
        """True only for a run with a membrane helix on BOTH sides.

        A terminus-adjacent run is not an insertion target for a member that
        reached ``internal`` placement precisely because it has no usable
        terminus — which is the distinction ``site_kind`` fails to make.
        """
        return self.position == INTER_TM


def _sha(sequence: str) -> str:
    return hashlib.sha256(sequence.encode()).hexdigest()


def load_members(path: Path) -> list[Member]:
    """Every row of the vendored member table, typed."""
    with path.open(newline="") as fh:
        return [
            Member(
                candidate_id=r["candidate_id"],
                library=r["library"],
                candidate_set=r["candidate_set"],
                species=r["species"],
                gene_symbol=r["gene_symbol"],
                topology_acc=r["topology_acc"],
                topology_cohort=r["topology_cohort"],
                sequence_sha256=r["sequence_sha256"],
                ordered_length_aa=int(r["ordered_length_aa"]),
                tm_count=int(r["tm_count"]),
                longest_inter_tm_ecto_run_aa=int(r["longest_inter_tm_ecto_run_aa"]),
                longest_ecto_run_aa=int(r["longest_ecto_run_aa"]),
                longest_ecto_run_start=int(r["longest_ecto_run_start"]),
                longest_ecto_run_position=r["longest_ecto_run_position"],
                placement=r["placement"],
                gpi_rerouted=r["gpi_rerouted"] == "1",
                shed_risk=r["shed_risk"],
            )
            for r in csv.DictReader(fh, delimiter="\t")
        ]


def resolve_member_frame(
    member: Member, *, candidates: list[tuple[str, str, str]] | None = None
) -> MemberFrame | None:
    """The candidate whose sequence hashes to the member's ``sequence_sha256``.

    ``candidates`` are ``(uniprot_acc_full, sequence, per_residue_topology)``
    triples — every ``topology_public`` row for the member's ``topology_acc``,
    canonical and isoform alike.

    Returns ``None`` when nothing matches, and the caller must then SKIP AND
    REPORT the member. Falling back to the canonical is the one behaviour this
    function must never have: it is how a position lands in another protein,
    and a plausible length makes it invisible downstream.

    The topology length is checked too. The sha can match while the stored
    topology is a different vintage, and then every index into it is off by
    however much the two disagree.
    """
    want = member.sequence_sha256
    for acc_full, sequence, topology in candidates or []:
        if not sequence or not topology:
            continue
        if _sha(sequence) != want:
            continue
        if len(topology) != len(sequence):
            continue
        return MemberFrame(
            member=member,
            topology_acc_full=acc_full,
            sequence=sequence,
            topology=topology,
        )
    return None


def extracellular_runs(topology: str) -> list[Run]:
    """Every contiguous ``O`` stretch, classified by what flanks it.

    Classification is by the presence of a membrane helix before and after the
    run — not by the run's index — so a signal peptide ahead of the first run
    does not promote it to a loop, and a beta-strand counts as membrane.
    """
    runs: list[Run] = []
    i = 0
    n = len(topology)
    while i < n:
        if topology[i] != _EXTRACELLULAR:
            i += 1
            continue
        j = i
        while j + 1 < n and topology[j + 1] == _EXTRACELLULAR:
            j += 1
        before = any(c in _MEMBRANE for c in topology[:i])
        after = any(c in _MEMBRANE for c in topology[j + 1 :])
        if before and after:
            position = INTER_TM
        elif before:
            position = C_TERMINAL
        elif after:
            position = N_TERMINAL
        else:
            position = NO_TM
        runs.append(Run(start=i + 1, end=j + 1, position=position))
        i = j + 1
    return runs


def run_at(topology: str, junction: int) -> Run | None:
    """The extracellular run containing ``junction`` (1-based), or None.

    None for a membrane or cytoplasmic position and for anything out of range.
    A non-extracellular junction is not a site, and must never be coerced to
    the nearest run — that would manufacture a surface position from a buried
    one.
    """
    if not topology or not 1 <= junction <= len(topology):
        return None
    if topology[junction - 1] != _EXTRACELLULAR:
        return None
    for run in extracellular_runs(topology):
        if run.start <= junction <= run.end:
            return run
    return None


def loop_inventory(member: Member, topology: str) -> str:
    """The extracellular regions a tag may go in, as prompt-ready text.

    Goes in the USER prompt, never the system prompt: the gene-agnostic
    prompt-leak tests exist because a worked example naming a real gene biases
    every other gene's call, and this text names the protein under study.

    Three shapes, because the members are not all the same kind of thing:

    * a genuine multipass member gets its inter-TM loops ONLY. Listing a
      terminal run would invite the model to propose a terminal site, which is
      the one thing a member with two cytoplasmic termini cannot use.
    * a ``gpi_rerouted`` member (BST2, RGMB — single-pass, internal only
      because the omega site removes the C-terminus) has no inter-TM loop at
      all, so it gets its ectodomain span instead. Its
      ``longest_inter_tm_ecto_run_aa`` is 0 **by construction**, and that 0 must
      never be read as "no site available": these two have 137 and 394 residues
      of ectodomain.
    * a member with no usable extracellular region is told so explicitly.
      Silence would read as "no constraint".
    """
    runs = extracellular_runs(topology)
    loops = [r for r in runs if r.is_loop]

    if member.gpi_rerouted or not loops:
        if member.longest_ecto_run_aa > 0:
            start = member.longest_ecto_run_start
            end = start + member.longest_ecto_run_aa - 1
            return (
                f"This construct has no extracellular terminus available and no "
                f"inter-helix extracellular region. Its extracellular segment "
                f"runs from residue {start} to {end} "
                f"({member.longest_ecto_run_aa} aa); place the tag within it."
            )
        return (
            "This construct has no extracellular region that can host a tag: "
            "no inter-helix extracellular segment and no extracellular "
            "terminus. Return an empty sites list."
        )

    listed = ", ".join(f"{r.start}-{r.end} ({r.length} aa)" for r in loops)
    return (
        "This construct has NO extracellular terminus, so N- and C-terminal "
        "tag sites are out of scope. Its extracellular inter-helix loops, in "
        f"residue numbering of this construct's own sequence, are: {listed}. A "
        "tag site must fall inside one of them."
    )
