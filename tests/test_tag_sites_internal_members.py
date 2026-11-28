"""Pin the vendored L1 internal-site member table.

``data/tag_sites/l1_internal_members.tsv`` is a byte-for-byte copy of the
current L1 v1 export from ``deliverome-surfaceome-library-v1`` (see its sibling
``.PROVENANCE.md``). Pinning the sha256 makes it a *copy* rather than a fork.
"""

from __future__ import annotations

import csv
import hashlib
from collections import Counter

import pytest

from accessible_surfaceome.paths import REPO_ROOT

TSV = REPO_ROOT / "data/tag_sites/l1_internal_members.tsv"
PROVENANCE = REPO_ROOT / "data/tag_sites/l1_internal_members.PROVENANCE.md"

#: The upstream L1 v1 export's hash (bundle-2026-11-26 / 2026-11-25-pre-freeze-e).
EXPECTED_SHA256 = "874db68acba95be6aad3c43fef592f866d07aca840fd5859f2766c287680a5f3"

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
    assert len(rows) == 607
    assert len({r["gene_symbol"] for r in rows}) == 548


def test_every_row_is_an_internal_placement(rows: list[dict[str, str]]) -> None:
    assert {r["placement"] for r in rows} == {"internal"}


def test_the_gpi_rerouted_member_is_bst2(rows: list[dict[str, str]]) -> None:
    gpi = {r["gene_symbol"] for r in rows if r["gpi_rerouted"] == "1"}
    assert gpi == {"BST2"}
    by_gene = {r["gene_symbol"]: r for r in rows if r["gpi_rerouted"] == "1"}
    assert int(by_gene["BST2"]["longest_inter_tm_ecto_run_aa"]) == 0
    assert int(by_gene["BST2"]["longest_ecto_run_aa"]) == 137
    assert int(by_gene["BST2"]["longest_ecto_run_start"]) == 44


def test_run_positions_cover_inter_tm_and_ectodomain_routed_members(
    rows: list[dict[str, str]],
) -> None:
    positions = Counter(r["longest_ecto_run_position"] for r in rows)
    assert set(positions) == {"inter_tm", "n_terminal", "c_terminal", "no_tm"}
    assert positions["inter_tm"] == 580


def test_the_hard_stratum_is_confirmed_by_the_unrestricted_measure(
    rows: list[dict[str, str]],
) -> None:
    hard = {"TMEM86A", "TMEM86B", "TMEM169", "TMEM139", "TMEM268"}
    for row in rows:
        if row["gene_symbol"] in hard:
            assert row["longest_ecto_run_aa"] == row["longest_inter_tm_ecto_run_aa"]
            assert row["longest_ecto_run_position"] == "inter_tm"


def test_the_sub_eight_aa_multipass_stratum(rows: list[dict[str, str]]) -> None:
    short = {
        r["gene_symbol"]
        for r in rows
        if int(r["longest_inter_tm_ecto_run_aa"]) < 8
        and row_is_inter_tm(r)
    }
    assert short == {"TMEM86A", "TMEM86B", "TMEM169", "TMEM139", "TMEM268"}


def row_is_inter_tm(r: dict[str, str]) -> bool:
    return r["longest_ecto_run_position"] == "inter_tm" and r["gpi_rerouted"] != "1"


def test_cohort_counts(rows: list[dict[str, str]]) -> None:
    cohorts = Counter(r["topology_cohort"] for r in rows)
    assert cohorts["human_canonical"] == 505
    assert cohorts["human_isoforms"] == 62
    assert cohorts["library_designed_orf"] == 7


def test_every_row_carries_the_sequence_it_was_numbered_against(
    rows: list[dict[str, str]],
) -> None:
    for row in rows:
        assert len(row["sequence_sha256"]) == 64, row["candidate_id"]


def test_provenance_doc_records_the_pinned_hash() -> None:
    assert EXPECTED_SHA256 in PROVENANCE.read_text()
