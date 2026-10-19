"""Pin the vendored L1 internal-site member table.

``data/tag_sites/l1_internal_members.tsv`` is a byte-for-byte copy of an export
from ``deliverome-analysis`` (see its sibling ``.PROVENANCE.md``). Pinning the
sha256 is what makes it a *copy* rather than a fork: re-export upstream, diff
the hash, and you know whether the two have diverged. Reformatting the file —
sorting it, rewriting the line endings, adding a comment header — breaks that
check, which is the point.

The counts are pinned separately from the hash because they are the facts other
code keys on, and a reader should be able to see them without a D1 round trip.
"""

from __future__ import annotations

import csv
import hashlib
from collections import Counter

import pytest

from accessible_surfaceome.paths import REPO_ROOT

TSV = REPO_ROOT / "data/tag_sites/l1_internal_members.tsv"
PROVENANCE = REPO_ROOT / "data/tag_sites/l1_internal_members.PROVENANCE.md"

#: The upstream export's hash, as reported by its generator.
EXPECTED_SHA256 = "c7359a2495925587125ff36bba4644c0a902f1f8fef3a8333da2f5cebe1d9999"

EXPECTED_COLUMNS = [
    "candidate_id",
    "library",
    "candidate_set",
    "species",
    "gene_symbol",
    "topology_acc",
    "topology_cohort",
    "topology_version",
    "sequence_sha256",
    "ordered_length_aa",
    "tm_count",
    "longest_inter_tm_ecto_run_aa",
    # Inserted here rather than appended, so parse this file by column NAME.
    "longest_ecto_run_aa",
    "longest_ecto_run_start",
    "longest_ecto_run_position",
    "placement",
    "gpi_rerouted",
    "shed_risk",
]


@pytest.fixture(scope="module")
def rows() -> list[dict[str, str]]:
    with TSV.open(newline="") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def test_file_is_byte_identical_to_the_upstream_export() -> None:
    assert hashlib.sha256(TSV.read_bytes()).hexdigest() == EXPECTED_SHA256


def test_columns_are_exactly_the_agreed_set() -> None:
    with TSV.open(newline="") as fh:
        header = next(csv.reader(fh, delimiter="\t"))
    assert header == EXPECTED_COLUMNS


def test_row_and_gene_counts(rows: list[dict[str, str]]) -> None:
    assert len(rows) == 566
    assert len({r["gene_symbol"] for r in rows}) == 518


def test_every_row_is_an_internal_placement(rows: list[dict[str, str]]) -> None:
    """The file is the filtered view. A non-internal row means the upstream
    filter changed and every consumer's scope changed with it."""
    assert {r["placement"] for r in rows} == {"internal"}


def test_the_gpi_rerouted_pair_is_exactly_bst2_and_rgmb(
    rows: list[dict[str, str]],
) -> None:
    """These two are single-pass GPI-anchored proteins, internal only because
    the omega site removes the C-terminus. Their site is in the ectodomain, not
    an inter-TM loop, so anything that builds a loop inventory has to branch on
    this column. If the pair changes, that branch needs re-reading."""
    gpi = {r["gene_symbol"] for r in rows if r["gpi_rerouted"] == "1"}
    assert gpi == {"BST2", "RGMB"}


def test_loop_length_is_zero_for_the_gpi_pair_but_the_ectodomain_is_not(
    rows: list[dict[str, str]],
) -> None:
    """``longest_inter_tm_ecto_run_aa`` counts runs with a TM on BOTH sides, so
    a single-pass protein scores 0 no matter how large its ectodomain — the 0
    must never be read as "no site available".

    ``longest_ecto_run_aa`` is the measure without that restriction, and for
    these two it differs by 137 and 394 residues. Pinning both is what stops
    the artefact being mistaken for a finding again."""
    for row in rows:
        if row["gpi_rerouted"] == "1":
            assert int(row["longest_inter_tm_ecto_run_aa"]) == 0
            assert int(row["longest_ecto_run_aa"]) > 100
    by_gene = {r["gene_symbol"]: r for r in rows if r["gpi_rerouted"] == "1"}
    assert int(by_gene["BST2"]["longest_ecto_run_aa"]) == 137
    assert int(by_gene["BST2"]["longest_ecto_run_start"]) == 44
    assert int(by_gene["RGMB"]["longest_ecto_run_aa"]) == 394
    assert int(by_gene["RGMB"]["longest_ecto_run_start"]) == 85


def test_run_position_identifies_the_members_needing_an_ectodomain_site(
    rows: list[dict[str, str]],
) -> None:
    """``longest_ecto_run_position`` is what synthesis context should branch on.

    It replaces "gpi_rerouted plus a hardcoded gene list" with a property of
    the topology: ``inter_tm`` means the site goes in a loop and the loop
    inventory applies; anything else means the extracellular region is a
    terminus-adjacent span and there is no inter-TM loop to describe. Exactly
    the two single-pass GPI members differ, and they are the same two the
    measures disagree on — so one column now carries what took two plus a
    caveat."""
    positions = {r["longest_ecto_run_position"] for r in rows}
    assert positions == {"inter_tm", "c_terminal"}
    not_loop = {r["gene_symbol"] for r in rows if r["longest_ecto_run_position"] != "inter_tm"}
    assert not_loop == {"BST2", "RGMB"}
    disagree = {
        r["gene_symbol"]
        for r in rows
        if r["longest_ecto_run_aa"] != r["longest_inter_tm_ecto_run_aa"]
    }
    assert disagree == not_loop


def test_the_hard_stratum_is_confirmed_by_the_unrestricted_measure(
    rows: list[dict[str, str]],
) -> None:
    """For the five genuinely-multipass short-loop members the ectodomain run
    EQUALS the inter-TM run, because that short loop is their only
    extracellular region. A second, independent measure therefore confirms
    they are the hardest stratum rather than softening it."""
    hard = {"TMEM86A", "TMEM86B", "TMEM169", "TMEM139", "TMEM268"}
    for row in rows:
        if row["gene_symbol"] in hard:
            assert row["longest_ecto_run_aa"] == row["longest_inter_tm_ecto_run_aa"]
            assert row["longest_ecto_run_position"] == "inter_tm"


def test_the_sub_eight_aa_multipass_stratum(rows: list[dict[str, str]]) -> None:
    """An insertion lengthens a loop rather than replacing it, so a short loop
    is not a disqualification — s4e9 placed a real site in a 9-aa loop. These 5
    are the genuinely-multipass short-loop members and the hardest stratum for
    any validation sample; the other 2 under 8 aa are the GPI pair."""
    short = {
        r["gene_symbol"]
        for r in rows
        if int(r["longest_inter_tm_ecto_run_aa"]) < 8 and r["gpi_rerouted"] != "1"
    }
    assert short == {"TMEM86A", "TMEM86B", "TMEM169", "TMEM139", "TMEM268"}


def test_most_members_are_not_numbered_on_the_canonical_sequence_count(
    rows: list[dict[str, str]],
) -> None:
    """71 of 566 members are numbered on something other than the human
    canonical sequence. That is the size of the member-frame problem in this
    exact set, and the reason positions are stamped with the sequence they were
    numbered against rather than assumed canonical."""
    cohorts = Counter(r["topology_cohort"] for r in rows)
    assert cohorts["human_canonical"] == 452
    non_canonical_human = cohorts["human_isoforms"] + cohorts["library_designed_orf"]
    assert non_canonical_human == 71


def test_every_row_carries_the_sequence_it_was_numbered_against(
    rows: list[dict[str, str]],
) -> None:
    """The sha256 is the join key into ``topology_public`` and the stamp that
    makes a published position unambiguous. A blank one is unusable."""
    for row in rows:
        assert len(row["sequence_sha256"]) == 64, row["candidate_id"]


def test_provenance_doc_records_the_pinned_hash() -> None:
    """The hash lives in two places on purpose — the test enforces it, the doc
    tells a human where the bytes came from. They must agree."""
    assert EXPECTED_SHA256 in PROVENANCE.read_text()
