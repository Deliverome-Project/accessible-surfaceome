"""Guards for the Zenodo data deposit scripts.

Each test pins a mistake that shipped in an earlier deposit:

* the genome triage file carried one of the four PubMed rescue lanes;
* deep-dive-preset-membership.tsv was built but never uploaded;
* the README and description stated counts that had gone stale;
* the README documented ``deep_dives_all.tar.gz`` with self-contained
  records after releases moved to ``deep_dives_X.Y.Z.tar.gz`` with the
  evidence split out, and its export recipes omitted ``with_reasoning=1``.
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
    uploaded = set(_load(SYNC).TSV_FILENAMES)
    assert built, "found no OUT_DIR / '*.tsv' outputs in the builder"
    assert built <= uploaded, f"built but never uploaded: {sorted(built - uploaded)}"


V = "1.3.0"


def _manifest(sync, **overrides) -> dict:
    """A manifest matching the counts the shipped README states."""
    readme = sync._build_readme(V)
    runs = dict(re.findall(r"\*\*`(genome_[a-z0-9_]+)`\*\*[^0-9]*?([\d,]+) genes", readme))
    manifest = {
        "files": list(sync.TSV_FILENAMES),
        "genome_rows": 33728,
        "genome_runs": {run: int(n.replace(",", "")) for run, n in runs.items()},
        "genome_pubmed_rows": 14404,
        "genome_pubmed_genes": 14395,
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
    assert sum(n for r, n in manifest["genome_runs"].items() if "pubmed" in r) == 14404
    assert sync.check_docs_against_manifest(
        sync._build_readme(V), sync._description_html(V), manifest, V
    ) == []


def test_stale_counts_and_unshipped_files_are_caught():
    sync = _load(SYNC)
    problems = sync.check_docs_against_manifest(
        sync._build_readme(V),
        sync._description_html(V),
        _manifest(sync, deep_dive_records=6000, genome_pubmed_genes=14399,
                  files=[*sync.TSV_FILENAMES, "new-file.tsv"]),
        V,
    )
    assert any("6,000" in p for p in problems)
    assert any("14,399" in p for p in problems)
    assert any("new-file.tsv" in p for p in problems)


def test_readme_documents_exactly_the_release_draft_files():
    """Every file the draft will hold has a README section and is named in the
    description, and no section describes a file the draft lacks — the
    README once documented deep_dives_all.tar.gz long after releases moved to
    deep_dives_X.Y.Z.tar.gz."""
    sync = _load(SYNC)
    readme, desc = sync._build_readme(V), sync._description_html(V)
    assert sync.check_docs_file_list(readme, desc, V) == []
    sections = sync._README_FILE_HEADING.findall(readme)
    assert sections == [n for n in sync.release_filenames(V) if n != "README.md"]
    assert "deep_dives_1.3.0.tar.gz" in sections
    for stale in ("deep_dives_all", "db_optimized_cutoffs", "Reserved DOI",
                  "added to this record in a later draft"):
        assert stale not in readme and stale not in desc, stale


def test_file_list_check_catches_a_stale_or_missing_section():
    sync = _load(SYNC)
    readme, desc = sync._build_readme(V), sync._description_html(V)
    stale = readme.replace("## 3. `deep_dives_1.3.0.tar.gz`", "## 3. `deep_dives_all.tar.gz`")
    problems = sync.check_docs_file_list(stale, desc, V)
    assert any("deep_dives_all.tar.gz" in p for p in problems)
    assert any("no section for deep_dives_1.3.0.tar.gz" in p for p in problems)
    # A README rendered for another release fails against this one.
    other = sync.check_docs_file_list(sync._build_readme("1.4.0"), desc, V)
    assert any("deep_dives_1.3.0.tar.gz" in p for p in other)


def test_readme_documents_both_manifest_hash_families():
    """manifest.tsv carries content hashes AND raw-byte sha256 columns; the
    README has to name every column and say which one verifies files."""
    from accessible_surfaceome.cloud.record_history.releases import MANIFEST_COLUMNS

    readme = _load(SYNC)._build_readme(V)
    for col in MANIFEST_COLUMNS:
        assert f"`{col}`" in readme, col
    assert "not** match `sha256sum`" in readme


def test_readme_api_recipes_reproduce_the_files():
    """Without with_reasoning=1 the export drops verdict_reasoning, so every
    triage recipe must carry it; deep-dive recipes point at the release."""
    readme = _load(SYNC)._build_readme(V)
    exports = re.findall(r"curl '([^']*/triage/export\.tsv[^']*)'", readme)
    assert len(exports) == 6
    assert all(u.endswith("&with_reasoning=1") for u in exports), exports
    for suffix in ("/releases/1.3.0/genes/EGFR'", "/releases/1.3.0/genes/EGFR/evidence'",
                   "/releases/1.3.0/genes/EGFR.md'"):
        assert suffix in readme, suffix


def test_draft_file_check():
    sync = _load(SYNC)
    managed = {*sync.TSV_FILENAMES, "README.md", sync.REPLICATES_TARBALL_NAME}
    ok, undocumented = sync.check_draft_files(
        {"deep_dives_1.3.0.tar.gz", "README.md"}, managed, V
    )
    assert (ok, undocumented) == ([], [])
    # The release tarball missing from the draft is a refusal.
    problems, _ = sync.check_draft_files({"README.md"}, managed, V)
    assert any("deep_dives_1.3.0.tar.gz" in p and "--resume" in p for p in problems)
    # A deep-dive tarball for anything else alongside it is a refusal.
    problems, _ = sync.check_draft_files(
        {"deep_dives_1.3.0.tar.gz", "deep_dives_all.tar.gz"}, managed, V
    )
    assert any("deep_dives_all.tar.gz" in p for p in problems)
    # Other inherited files are reported, not refused.
    problems, undocumented = sync.check_draft_files(
        {"deep_dives_1.3.0.tar.gz", "old-file.tsv"}, managed, V
    )
    assert problems == [] and undocumented == ["old-file.tsv"]


def test_offline_dry_run_renders_docs_without_network(tmp_path, monkeypatch):
    sync = _load(SYNC)

    def no_network(*_a, **_kw):
        raise AssertionError("offline dry-run must not touch the network")

    monkeypatch.setattr(sync.httpx, "Client", no_network)
    monkeypatch.delenv("ZENODO_TOKEN", raising=False)
    assert sync.main(["--dry-run", "--version", V, "--work-dir", str(tmp_path)]) == 0
    readme = (tmp_path / "README.md").read_text()
    assert "data release 1.3.0" in readme
    assert (tmp_path / "description.html").exists()


def test_writes_require_a_deposit_id(tmp_path, monkeypatch):
    sync = _load(SYNC)
    monkeypatch.setattr(sync.httpx, "Client", lambda *a, **kw: (_ for _ in ()).throw(AssertionError))
    assert sync.main(["--work-dir", str(tmp_path)]) == 1
    assert not (tmp_path / "README.md").exists()


def test_deep_dive_flags_are_gone():
    """--with-deep-dives used to add deep_dives_all.tar.gz next to the
    release's own deep_dives_X.Y.Z.tar.gz; cut_data_release.py owns that file."""
    text = SYNC.read_text()
    assert "--with-deep-dives" not in text and "--deep-dives-only" not in text
