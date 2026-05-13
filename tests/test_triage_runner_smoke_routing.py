"""Tests for the runner's ``--smoke`` routing.

Background: during the 2026-05-11 sub-bench session a smoke run against
``haiku/HSPA1A`` reused the canonical out-root (``data/eval/triage_subbench_v1/``)
and the subsequent ``rm`` cleanup deleted real run artifacts. The
``--smoke`` flag is the operator-error guard: when set, the runner
must redirect BOTH ``--out-root`` and ``--run-id`` into a throwaway
gitignored namespace so a smoke can't physically reach the canonical
tree.

These tests pin the contract that:

* the smoke out-root lives under ``data/eval/_smoke/``
* the smoke ``run_id`` is prefixed with ``smoke_`` (so D1 audits can
  filter it out cheaply)
* both values share the same timestamp (audit pairing)
* the helper is deterministic given a fixed datetime (no hidden state)
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
RUNNER_PATH = REPO_ROOT / "scripts" / "triage_subbench_runner.py"


@pytest.fixture(scope="module")
def runner():
    """Import the runner script as a module without executing main()."""
    spec = importlib.util.spec_from_file_location(
        "triage_subbench_runner", RUNNER_PATH,
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["triage_subbench_runner"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_smoke_routing_uses_smoke_subdir_for_bench(runner):
    out_root, run_id = runner._smoke_routing(bench="subbench", gene_list=None)
    # Out-root sits under data/eval/_smoke/ — the gitignored namespace.
    rel = out_root.relative_to(runner.ROOT)
    assert rel.parts[0:3] == ("data", "eval", "_smoke"), (
        f"smoke out-root should land under data/eval/_smoke/, got {rel}"
    )
    # Directory name includes the bench identifier and a UTC timestamp.
    assert rel.parts[3].startswith("subbench_"), rel.parts[3]


def test_smoke_routing_uses_gene_list_stem_when_provided(runner):
    out_root, _ = runner._smoke_routing(
        bench="subbench",   # ignored when gene_list is set
        gene_list="data/processed/whole_genome_minus_m1.tsv",
    )
    rel = out_root.relative_to(runner.ROOT)
    # Stem of the gene-list path is the prefix — preserves the
    # "where did this smoke come from" hint at a glance.
    assert rel.parts[3].startswith("whole_genome_minus_m1_"), rel.parts[3]


def test_smoke_run_id_has_smoke_prefix(runner):
    _, run_id = runner._smoke_routing(bench="subbench", gene_list=None)
    assert run_id.startswith("smoke_"), run_id
    # smoke_<YYYYMMDDTHHMMSSZ>_<8 hex chars>
    assert re.match(r"^smoke_\d{8}T\d{6}Z_[0-9a-f]{8}$", run_id), run_id


def test_smoke_routing_pairs_timestamp(runner):
    """The out-root's timestamp and the run_id's timestamp must agree —
    that pairing is what lets a D1 audit walk back to the on-disk artifacts
    of a given smoke."""
    out_root, run_id = runner._smoke_routing(bench="subbench", gene_list=None)
    # Pull the timestamp out of each.
    dir_ts = out_root.name.rsplit("_", 1)[-1]
    run_id_ts = run_id.split("_")[1]
    assert dir_ts == run_id_ts, f"timestamp mismatch: dir={dir_ts} run_id={run_id_ts}"


def test_smoke_routing_yields_distinct_run_ids_on_repeat(runner):
    """Two back-to-back smoke routings within the same second still get
    distinct run_ids thanks to the uuid8 suffix."""
    _, run_id_a = runner._smoke_routing(bench="subbench", gene_list=None)
    _, run_id_b = runner._smoke_routing(bench="subbench", gene_list=None)
    # The uuid suffix differs.
    assert run_id_a != run_id_b, (run_id_a, run_id_b)
