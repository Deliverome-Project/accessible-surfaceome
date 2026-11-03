"""Guards for the Zenodo data deposit scripts.

Each test pins a mistake that shipped in an earlier deposit:

* the genome triage file carried one of the four PubMed rescue lanes;
* deep-dive-preset-membership.tsv was built but never uploaded;
* the README and description stated counts that had gone stale.
"""
from __future__ import annotations

import ast
import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "scripts/release/build_consolidated_deposit_tsvs.py"
SYNC = ROOT / "scripts/release/update_zenodo_draft.py"
UNIVERSE = ROOT / "scripts/build_candidate_universe_v3.py"


def _load(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec is not None and spec.loader is not None, path
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _constant(path: Path, name: str):
    for node in ast.parse(path.read_text()).body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == name for t in node.targets
        ):
            return ast.literal_eval(node.value)
    raise AssertionError(f"{name} not found in {path}")


def test_deposit_carries_every_rescue_lane():
    """A new rescue lane added to the universe gate must also be deposited."""
    assert list(_constant(BUILDER, "GENOME_PUBMED_RUN_IDS")) == list(
        _constant(UNIVERSE, "RESCUE_RUNS")
    )


def test_every_built_file_is_uploaded():
    built = set(re.findall(r'OUT_DIR / "([^"]+\.tsv)"', BUILDER.read_text()))
    uploaded = {p.name for p in _load(SYNC).NEW_FILES}
    assert built, "found no OUT_DIR / '*.tsv' outputs in the builder"
    assert built <= uploaded, f"built but never uploaded: {sorted(built - uploaded)}"


def _manifest(sync, **overrides) -> dict:
    """A manifest matching the counts the shipped README states."""
    readme = sync._build_readme()
    runs = dict(re.findall(r"\*\*`(genome_[a-z0-9_]+)`\*\*[^0-9]*?([\d,]+) genes", readme))
    manifest = {
        "files": [p.name for p in sync.NEW_FILES],
        "genome_rows": 33728,
        "genome_runs": {run: int(n.replace(",", "")) for run, n in runs.items()},
        "benchmark_rows": 7938,
        "benchmark_cells": 18,
        "deep_dive_records": 5332,
    }
    manifest.update(overrides)
    return manifest


def test_docs_match_a_consistent_manifest():
    sync = _load(SYNC)
    manifest = _manifest(sync)
    assert len(manifest["genome_runs"]) == 5
    assert sync.check_docs_against_manifest(
        sync._build_readme(), sync._DESCRIPTION_HTML, manifest
    ) == []


def test_stale_counts_and_unshipped_files_are_caught():
    sync = _load(SYNC)
    problems = sync.check_docs_against_manifest(
        sync._build_readme(),
        sync._DESCRIPTION_HTML,
        _manifest(sync, deep_dive_records=6000,
                  files=[*(p.name for p in sync.NEW_FILES), "new-file.tsv"]),
    )
    assert any("6,000" in p for p in problems)
    assert any("new-file.tsv" in p for p in problems)
