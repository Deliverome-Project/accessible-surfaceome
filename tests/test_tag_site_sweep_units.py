"""The sweep's work units: genes for the first pass, MEMBERS for the enrichment.

The enrichment pass runs once per library member, not once per gene — 566
members across 518 genes, 45 of which have several and 7 of which disagree
about where the tag can go. So the sweep needs a second kind of work unit with
its own resume key, and the two key spaces must not be confused: a gene the
first pass finished says nothing about whether a member of it has been enriched.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MEMBERS_TSV = ROOT / "data/tag_sites/l1_internal_members.tsv"


def _load():
    spec = importlib.util.spec_from_file_location(
        "sweep_tag_site_lit", ROOT / "scripts/sweep_tag_site_lit.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    # Register before exec: the module defines a dataclass, and
    # ``dataclasses`` resolves field types through ``sys.modules[__module__]``,
    # which raises for a module that was never registered.
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


sweep = _load()


@pytest.fixture
def members_tsv(tmp_path: Path) -> Path:
    """Two members of one gene plus one of another, on the REAL header.

    The header is read from the vendored table rather than written out here, so
    a column added there cannot leave this fixture passing against a loader
    that now needs it.
    """
    header = MEMBERS_TSV.read_text().splitlines()[0]
    cols = header.split("\t")
    idx = {c: i for i, c in enumerate(cols)}

    def row(cid: str, gene: str) -> str:
        f = [""] * len(cols)
        f[idx["candidate_id"]] = cid
        f[idx["library"]] = "l1"
        f[idx["candidate_set"]] = "library_reference"
        f[idx["species"]] = "human"
        f[idx["gene_symbol"]] = gene
        f[idx["topology_acc"]] = "O94911"
        f[idx["topology_cohort"]] = "human_canonical"
        f[idx["topology_version"]] = "topo_2026_05_16"
        f[idx["sequence_sha256"]] = "0" * 64
        for n in ("ordered_length_aa", "tm_count", "longest_inter_tm_ecto_run_aa",
                  "longest_ecto_run_aa", "longest_ecto_run_start"):
            f[idx[n]] = "1"
        f[idx["longest_ecto_run_position"]] = "inter_tm"
        f[idx["placement"]] = "internal"
        f[idx["gpi_rerouted"]] = "0"
        return "\t".join(f)

    p = tmp_path / "members.tsv"
    p.write_text("\n".join([header, row("l1-p1037", "KCNN2"),
                            row("l1-p2461", "KCNN2"), row("l1-p0001", "ABCA8")]) + "\n")
    return p


# --------------------------------------------------------------------------
# what a unit is
# --------------------------------------------------------------------------


def test_each_member_is_its_own_unit(members_tsv: Path) -> None:
    units = sweep.member_units(members_tsv)
    assert [u.label for u in units] == ["l1-p0001", "l1-p1037", "l1-p2461"]


def test_a_member_unit_runs_the_enrichment_driver_by_candidate_id(
    members_tsv: Path,
) -> None:
    """Not the gene-keyed control-panel driver: that one numbers against the
    public record's canonical topology, which for 71 of the members is a
    different protein from the construct being tagged."""
    u = next(u for u in sweep.member_units(members_tsv) if u.label == "l1-p1037")
    assert u.driver.name == "enrich_tag_site_lit.py"
    assert u.args == ["--candidate-id", "l1-p1037"]


def test_a_gene_unit_runs_the_control_panel_driver_by_symbol(tmp_path: Path) -> None:
    p = tmp_path / "genes.txt"
    p.write_text("CD63\nTFRC\n")
    units = sweep.gene_units(p)
    assert [u.label for u in units] == ["CD63", "TFRC"]
    assert units[0].driver.name == "regenerate_tag_site_lit.py"
    assert units[0].args == ["--gene", "CD63"]


# --------------------------------------------------------------------------
# the two key spaces
# --------------------------------------------------------------------------


def test_a_member_is_keyed_by_gene_and_candidate(members_tsv: Path) -> None:
    u = next(u for u in sweep.member_units(members_tsv) if u.label == "l1-p1037")
    assert u.key == ("KCNN2", "l1-p1037")


def test_a_finished_gene_does_not_satisfy_a_member(members_tsv: Path) -> None:
    """The failure this separation prevents: a gene-keyed skip set would strand
    every member of the 518 genes the first pass already searched."""
    units = sweep.member_units(members_tsv)
    assert sweep.pending(units, {"KCNN2", "ABCA8"}) == units


def test_a_finished_member_is_dropped_and_its_sibling_is_not(
    members_tsv: Path,
) -> None:
    pending = sweep.pending(sweep.member_units(members_tsv), {("KCNN2", "l1-p1037")})
    assert [u.label for u in pending] == ["l1-p0001", "l1-p2461"]


# --------------------------------------------------------------------------
# what the child process is told
# --------------------------------------------------------------------------


def test_the_run_series_reaches_the_child(monkeypatch, tmp_path: Path) -> None:
    """The series decides which rows the member writes AND which rows its own
    resume reads, so a sweep that keeps it to itself would have the child write
    under the default and then never skip them."""
    seen: dict = {}

    class _Proc:
        stdout, stderr, returncode = "", "", 0

    def fake_run(cmd, **kw):
        seen["cmd"] = cmd
        seen["env"] = kw["env"]
        return _Proc()

    monkeypatch.setattr(sweep.subprocess, "run", fake_run)
    unit = sweep.Unit(
        label="l1-p1037", gene="KCNN2", driver=sweep.ENRICH_DRIVER,
        args=["--candidate-id", "l1-p1037"], key=("KCNN2", "l1-p1037"),
    )
    sweep.run_unit(unit, run_id="r1", run_series="literature_enriched_v1",
                   log_dir=tmp_path, env_extra={})

    assert seen["env"]["TAG_SITE_RUN_SERIES"] == "literature_enriched_v1"
    assert seen["env"]["TAG_SITE_RUN_ID"] == "r1"
    assert seen["cmd"][1:] == [str(sweep.ENRICH_DRIVER), "--candidate-id", "l1-p1037"]


def test_a_units_log_is_named_for_the_unit_not_the_gene(
    monkeypatch, tmp_path: Path
) -> None:
    """Two members of one gene would otherwise overwrite each other's log, and
    the log is the only place a failed run's reason survives."""

    class _Proc:
        stdout, stderr, returncode = "out", "", 0

    monkeypatch.setattr(sweep.subprocess, "run", lambda cmd, **kw: _Proc())
    for cid in ("l1-p1037", "l1-p2461"):
        sweep.run_unit(
            sweep.Unit(label=cid, gene="KCNN2", driver=sweep.ENRICH_DRIVER,
                       args=["--candidate-id", cid], key=("KCNN2", cid)),
            run_id="r1", run_series="s", log_dir=tmp_path, env_extra={},
        )
    assert sorted(p.name for p in tmp_path.glob("*.log")) == [
        "l1-p1037.log", "l1-p2461.log",
    ]


# --------------------------------------------------------------------------
# the CLI
# --------------------------------------------------------------------------


def test_members_file_and_run_series_are_accepted() -> None:
    args = sweep.build_parser().parse_args(
        ["--run-id", "x", "--members-file", "m.tsv",
         "--run-series", "literature_enriched_v1"]
    )
    assert args.members_file == Path("m.tsv")
    assert sweep.resolve_series(args) == "literature_enriched_v1"


def test_a_gene_sweep_defaults_to_the_first_pass_series() -> None:
    """So the existing sweep keeps writing where it always has."""
    args = sweep.build_parser().parse_args(["--run-id", "x"])
    assert args.members_file is None
    assert sweep.resolve_series(args) == "literature_v1"


def test_a_members_sweep_defaults_to_the_enrichment_series() -> None:
    """Not the first pass's. The series the sweep passes down is the series the
    child WRITES, so inheriting ``literature_v1`` here would file member rows
    into the first pass's series — the one thing this pass promised not to
    touch — and its own resume would then never match them."""
    args = sweep.build_parser().parse_args(["--run-id", "x", "--members-file", "m.tsv"])
    assert sweep.resolve_series(args) == "literature_enriched_v1"
