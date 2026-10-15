"""Numbering a tag position in the MEMBER's own frame.

A Library-1 member's protein is its designed CDS translated, which for a
substantial minority is not the protein its accession names: of the 566
internal-site members, 47 are `human_isoforms`, 24 are `library_designed_orf`
and 43 are non-human ortholog cohorts. A position expressed in canonical
coordinates is, for those, a position in a different protein.

This is not a hypothetical. The 20-gene spike's own verification script resolved
`topology_acc` against `cohort='human_canonical'` and silently failed on KCNN2,
whose `topology_acc` is `l1-p1037` — a designed ORF with no canonical row — and
would have reported two real loop sites as non-loops. The sha256 check below is
what turns that silent miss into a loud one.

The run classifier exists for a second measured reason: `site_kind` does not
discriminate terminal from internal. The five literature sites at positions 4-5
are topologically identical — no signal peptide, extracellular N-terminus,
junction inside the N-terminal `O` run — yet two are labelled `internal` and
three `terminal_n`, with both paralogue pairs disagreeing with their own
partner. Loop-ness has to be derived from topology, not read off a label.
"""

from __future__ import annotations

import hashlib

import pytest

from accessible_surfaceome.agents.tag_site.member_frames import (
    Member,
    resolve_member_frame,
    run_at,
    extracellular_runs,
    loop_inventory,
)


def sha(seq: str) -> str:
    return hashlib.sha256(seq.encode()).hexdigest()


def member(**over) -> Member:
    base = dict(
        candidate_id="l1-p0001",
        library="l1",
        candidate_set="library_reference",
        species="human",
        gene_symbol="GENEX",
        topology_acc="P00001",
        topology_cohort="human_canonical",
        sequence_sha256=sha("MKTAYIAKQR"),
        ordered_length_aa=10,
        tm_count=2,
        longest_inter_tm_ecto_run_aa=5,
        longest_ecto_run_aa=5,
        longest_ecto_run_start=3,
        longest_ecto_run_position="inter_tm",
        placement="internal",
        gpi_rerouted=False,
        shed_risk="",
    )
    base.update(over)
    return Member(**base)


# --------------------------------------------------------------------------
# resolution: the sha256 is the key, not the accession
# --------------------------------------------------------------------------


def test_resolves_the_candidate_whose_sequence_hashes_to_the_members_sha() -> None:
    wanted = "MKTAYIAKQR"
    other = "MKTAYIAKQRQISFVKSHFSRQ"  # a longer, canonical-looking decoy
    frame = resolve_member_frame(
        member(sequence_sha256=sha(wanted)),
        candidates=[
            ("P00001-1", other, "OOMMMIIIOOOMMMIIIOOOOO"),
            ("P00001-3", wanted, "OOMMMIIIOO"),
        ],
    )
    assert frame is not None
    assert frame.sequence == wanted
    assert frame.topology_acc_full == "P00001-3"


def test_refuses_to_substitute_when_no_candidate_matches() -> None:
    """The failure mode this module exists to prevent.

    Returning the canonical because nothing matched is how a cassette lands in
    a different protein. A miss must be a miss, so the caller can report it."""
    frame = resolve_member_frame(
        member(sequence_sha256=sha("MKTAYIAKQR")),
        candidates=[("P00001-1", "WWWWWWWWWW", "OOMMMIIIOO")],
    )
    assert frame is None


def test_refuses_an_empty_candidate_list() -> None:
    """A designed ORF often has no row under its accession at all — 7 of a
    60-member sample. That is a skip-and-report, not a fallback."""
    assert resolve_member_frame(member(), candidates=[]) is None


def test_rejects_a_candidate_whose_topology_length_disagrees() -> None:
    """Sequence and per-residue topology must be the same length, or every
    index into the topology is off. The sha can match while the topology is a
    different vintage, so both are checked."""
    seq = "MKTAYIAKQR"
    frame = resolve_member_frame(
        member(sequence_sha256=sha(seq)),
        candidates=[("P00001-1", seq, "OOMM")],  # 4 chars for a 10-mer
    )
    assert frame is None


def test_the_frame_records_what_it_was_numbered_against() -> None:
    """A published position is only unambiguous if the sequence that defines it
    travels with it."""
    seq = "MKTAYIAKQR"
    frame = resolve_member_frame(
        member(sequence_sha256=sha(seq)),
        candidates=[("P00001-1", seq, "OOMMMIIIOO")],
    )
    assert frame is not None
    assert frame.numbered_against == sha(seq)


# --------------------------------------------------------------------------
# run classification: loop-ness comes from topology, never from a label
# --------------------------------------------------------------------------

#            1234567890123456789012345
#: N-term O run (1-3), TM, I, TM, inter-TM O run (12-16), TM, I, TM, C-term O run
TOPO = "OOO" "MMM" "III" "MMM" "OOOOO" "MMM" "III" "MMM" "OOO"


def test_extracellular_runs_are_classified_by_what_flanks_them() -> None:
    runs = extracellular_runs(TOPO)
    kinds = [(r.start, r.end, r.position) for r in runs]
    assert kinds == [
        (1, 3, "n_terminal"),
        (13, 17, "inter_tm"),
        (27, 29, "c_terminal"),
    ]


def test_a_junction_in_an_n_terminal_tail_is_not_a_loop() -> None:
    """The ABCC1 R4 shape: extracellular, no signal peptide, junction a few
    residues into the N-terminal tail. `site_kind` called this `internal` on two
    of five topologically identical sites — the topology does not."""
    run = run_at(TOPO, 2)
    assert run is not None
    assert run.position == "n_terminal"
    assert run.is_loop is False


def test_a_junction_between_two_tm_helices_is_a_loop() -> None:
    run = run_at(TOPO, 15)
    assert run is not None
    assert run.position == "inter_tm"
    assert run.is_loop is True
    assert (run.start, run.end, run.length) == (13, 17, 5)


def test_a_junction_after_the_last_helix_is_not_a_loop() -> None:
    run = run_at(TOPO, 28)
    assert run is not None
    assert run.position == "c_terminal"
    assert run.is_loop is False


@pytest.mark.parametrize("j", [4, 7, 20])
def test_a_junction_that_is_not_extracellular_has_no_run(j: int) -> None:
    """Membrane and cytoplasmic positions are not sites, and must not be
    silently coerced into the nearest run."""
    assert run_at(TOPO, j) is None


@pytest.mark.parametrize("j", [0, -1, 999])
def test_an_out_of_range_junction_has_no_run(j: int) -> None:
    assert run_at(TOPO, j) is None


def test_a_signal_peptide_does_not_make_the_first_run_a_loop() -> None:
    """After cleavage the mature N-terminus is extracellular, but it still has
    no helix before it, so it is a terminus and not a loop."""
    topo = "SSSS" "OOOO" "MMM" "III" "MMM" "OOO"
    run = run_at(topo, 6)
    assert run is not None
    assert run.position == "n_terminal"
    assert run.is_loop is False


# --------------------------------------------------------------------------
# the loop inventory handed to the synthesis prompt
# --------------------------------------------------------------------------


def test_loop_inventory_lists_only_inter_tm_runs_for_a_multipass_member() -> None:
    """Terminal runs are not insertion targets for a member with no usable
    terminus, and listing them invites the model to propose one."""
    text = loop_inventory(member(longest_ecto_run_position="inter_tm"), TOPO)
    assert "13-17" in text
    assert "1-3" not in text
    assert "27-29" not in text


def test_loop_inventory_gives_the_ectodomain_span_for_a_gpi_rerouted_member() -> None:
    """BST2 and RGMB are single-pass GPI-anchored, internal only because the
    omega site removes the C-terminus. Their site is somewhere in the
    ectodomain, and they have no inter-TM loop at all — so
    `longest_inter_tm_ecto_run_aa` is 0 by construction and must not be read as
    "no site available"."""
    topo = "MMM" + "O" * 120
    text = loop_inventory(
        member(
            gene_symbol="BST2",
            tm_count=1,
            longest_inter_tm_ecto_run_aa=0,
            longest_ecto_run_aa=120,
            longest_ecto_run_start=4,
            longest_ecto_run_position="c_terminal",
            gpi_rerouted=True,
        ),
        topo,
    )
    assert "4" in text and "120" in text
    assert "loop" not in text.lower()


def _members():
    from pathlib import Path

    from accessible_surfaceome.agents.tag_site.member_frames import load_members
    from accessible_surfaceome.paths import REPO_ROOT

    return load_members(Path(REPO_ROOT) / "data/tag_sites/l1_internal_members.tsv")


def _groups(members, keyfn):
    out: dict[object, list] = {}
    for m in members:
        out.setdefault(keyfn(m), []).append(m)
    return out


def test_a_gene_symbol_is_a_lossy_key_for_members() -> None:
    """The bug actually hit: a `{gene_symbol: member}` dict keeps whichever row
    it saw last and drops 48 of the 566.

    This pins the *collapse*, which is real at this key regardless of why the
    rows differ. It deliberately does NOT assert anything about how many
    disagree, because at this key that figure is mostly species conflation —
    see the next test, which is the one a design decision rests on.
    """
    members = _members()
    assert len(members) == 566
    by_gene = _groups(members, lambda m: m.gene_symbol)
    assert len(by_gene) == 518
    multi = {g: v for g, v in by_gene.items() if len(v) > 1}
    assert len(multi) == 45
    assert sum(len(v) - 1 for v in multi.values()) == 48


def test_two_members_of_one_gene_and_species_can_disagree_about_the_loop() -> None:
    """The irreducible fact, and the reason sites are emitted PER MEMBER.

    Keyed on `gene_symbol` alone, 14 groups disagree on their longest inter-TM
    loop — but 9 of those are a human protein against its mouse or cyno
    ortholog, which *should* differ. Keying on (species, gene_symbol) gives
    **7**, and it is 7 rather than the 5 you would get by filtering the 14 to
    same-species, because two genuine same-species conflicts hide inside
    gene-keyed groups that also span species.

    LIM2 is that case and it is the sharpest in the set: human
    `library_reference` 40 aa against human `isoform` 82 aa, both 4 TM, with a
    cyno ortholog in the same gene-keyed group taking the blame for the
    difference. A test pinning only the gene-keyed 14 would stay green if the
    same-species count doubled.
    """
    members = _members()
    by_species_gene = _groups(members, lambda m: (m.species, m.gene_symbol))
    assert len(by_species_gene) == 543
    multi = {k: v for k, v in by_species_gene.items() if len(v) > 1}
    assert len(multi) == 22
    assert sum(len(v) - 1 for v in multi.values()) == 23

    disagree = {
        k: v
        for k, v in multi.items()
        if len({m.longest_inter_tm_ecto_run_aa for m in v}) > 1
    }
    assert len(disagree) == 7
    assert {g for _, g in disagree} == {
        "KCNK4", "LIM2", "PLPP1", "SLC12A4", "SLC15A2", "SLC4A7", "TMEM219",
    }
    # Every one is a designed reference against an isoform of the same protein,
    # so the disagreement is about proteoform, not about species or curation.
    for v in disagree.values():
        assert {m.candidate_set for m in v} == {"library_reference", "isoform"}


def test_the_two_same_species_conflicts_hidden_by_gene_keying() -> None:
    """LIM2 and TMEM219 disagree within one species AND sit in a gene-keyed
    group that spans species, so the gene-keyed view attributes their conflict
    to the ortholog. Pinned by name because they are the counterexample to the
    framing, not just instances of it."""
    members = _members()
    by_gene = _groups(members, lambda m: m.gene_symbol)
    for gene in ("LIM2", "TMEM219"):
        rows = by_gene[gene]
        assert len({m.species for m in rows}) > 1, gene
        human = [m for m in rows if m.species == "human"]
        assert len({m.longest_inter_tm_ecto_run_aa for m in human}) > 1, gene


def test_an_isoform_can_differ_from_its_reference_in_helix_count() -> None:
    """SLC4A7: 14 TM against 12 TM between a reference and its isoform. Two
    members that far apart topologically are not the same design problem, so
    neither a shared loop inventory nor a shared junction is safe."""
    members = _members()
    rows = [m for m in members if m.gene_symbol == "SLC4A7"]
    assert {m.tm_count for m in rows} == {12, 14}


def test_kcnn2_has_only_one_internal_member() -> None:
    """The cautionary case in the other direction. KCNN2 has two L1 members —
    a 791 aa 6-TM designed ORF and a 231 aa 1-TM isoform — but only the designed
    ORF needs an internal site, so the isoform never reaches this table. A
    per-gene lookup landing on the isoform reads a junction at 246 as OUT OF
    RANGE rather than as wrong, and out-of-range reads as bad data while
    wrong-frame reads as a result."""
    members = _members()
    rows = [m for m in members if m.gene_symbol == "KCNN2"]
    assert len(rows) == 1
    assert rows[0].candidate_id == "l1-p1037"
    assert rows[0].topology_cohort == "library_designed_orf"
    assert rows[0].tm_count == 6


def test_loop_inventory_is_explicit_when_there_is_no_loop_at_all() -> None:
    """Silence would read as "no constraint" to the model. A member whose only
    extracellular region is unusable has to be told so."""
    topo = "III" + "MMM" + "III"
    text = loop_inventory(member(), topo)
    assert text.strip() != ""
    assert "no extracellular" in text.lower()
