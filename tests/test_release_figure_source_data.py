"""The figure-source-data tarball every numbered data release carries.

Built from the checkout by ``accessible_surfaceome.release.figure_source_data``
and uploaded by scripts/release/update_zenodo_draft.py. These tests pin:

* the bytes are reproducible: two builds of the same checkout are identical,
  with no build time, owner or filename baked in;
* the member list is exactly the gist bundle list plus the four canonical
  figure-input TSVs, so a figure TSV added to the gists can't be silently
  left out of the data record;
* every manifest row's sha256 matches the file it names.
"""
from __future__ import annotations

import ast
import csv
import gzip
import hashlib
import io
import json
import tarfile
from pathlib import Path

import pytest

from accessible_surfaceome.release import figure_source_data as fsd

ROOT = Path(__file__).resolve().parents[1]
V = "1.3.0"
TOP = f"figure-source-data_{V}"
CANONICAL = {
    "data/processed/candidate_universe/candidate_universe.tsv",
    "data/eval/triage_benchmark_v1.tsv",
    "data/processed/triage_bench/mainbench_canonical_v2.tsv",
    "data/processed/triage_bench/db_optimized_cutoffs.tsv",
}


def _tsv_bundle() -> dict[str, list[str]]:
    """TSV_BUNDLE parsed independently of the module under test."""
    src = (ROOT / "scripts/figures/sync_figure_gists_bundle_data.py").read_text()
    for node in ast.parse(src).body:
        if isinstance(node, ast.AnnAssign) and getattr(node.target, "id", None) == "TSV_BUNDLE":
            assert node.value is not None
            return ast.literal_eval(node.value)
    raise AssertionError("TSV_BUNDLE not found")


@pytest.fixture(scope="module")
def built(tmp_path_factory) -> bytes:
    return fsd.build_figure_source_tarball(tmp_path_factory.mktemp("fsd"), V).read_bytes()


def _members(blob: bytes) -> dict[str, bytes]:
    with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as tar:
        out = {}
        for m in tar.getmembers():
            f = tar.extractfile(m)
            assert f is not None, m.name
            out[m.name] = f.read()
        return out


def test_two_builds_are_byte_identical(built, tmp_path):
    again = fsd.build_figure_source_tarball(tmp_path, V).read_bytes()
    assert again == built
    assert (tmp_path / f"{TOP}.tar.gz").exists()


def test_archive_carries_no_build_time_owner_or_filename(built):
    # gzip header: MTIME (bytes 4-8) zero, FNAME flag (0x08) unset.
    assert built[4:8] == b"\x00\x00\x00\x00"
    assert not built[3] & 0x08
    with tarfile.open(fileobj=io.BytesIO(built), mode="r:gz") as tar:
        members = tar.getmembers()
    names = [m.name for m in members]
    assert names == sorted(names)
    for m in members:
        assert (m.mtime, m.uid, m.gid, m.uname, m.gname, m.mode) == (0, 0, 0, "", "", 0o644), m.name
    assert gzip.decompress(built)  # well-formed


def test_member_list_is_the_gist_bundle_plus_the_canonical_inputs(built):
    bundled = {p for paths in _tsv_bundle().values() for p in paths}
    assert bundled and not bundled & CANONICAL
    panels = {p for _, ps in fsd.PANEL_INPUTS.values() for p in ps}
    expected = {f"{TOP}/{p}" for p in bundled | panels | CANONICAL} | {
        f"{TOP}/README.md", f"{TOP}/manifest.tsv"}
    assert set(_members(built)) == expected
    assert set(fsd.CANONICAL_FIGURE_INPUTS) == CANONICAL


def test_manifest_rows_match_the_files(built):
    members = _members(built)
    rows = list(csv.DictReader(io.StringIO(members[f"{TOP}/manifest.tsv"].decode()), delimiter="\t"))
    assert tuple(rows[0]) == fsd.MANIFEST_COLUMNS
    data_members = {n.removeprefix(f"{TOP}/") for n in members} - {"README.md", "manifest.tsv"}
    assert {r["path"] for r in rows} == data_members
    for r in rows:
        data = members[f"{TOP}/{r['path']}"]
        assert hashlib.sha256(data).hexdigest() == r["sha256"], r["path"]
        assert data == (ROOT / r["path"]).read_bytes(), r["path"]
        assert int(r["rows"]) == fsd.count_rows(data) > 0, r["path"]


def test_figure_rows_are_labelled_and_cited(built):
    members = _members(built)
    rows = list(csv.DictReader(io.StringIO(members[f"{TOP}/manifest.tsv"].decode()), delimiter="\t"))
    gists = json.loads((ROOT / "data/analysis/figures/gist_map.json").read_text())
    swhids = json.loads((ROOT / "data/analysis/figures/swhid_map.json").read_text())
    labels = fsd.figure_labels()
    bundle = _tsv_bundle()
    figure_rows = [r for r in rows if r["role"] == fsd.ROLE_FIGURE]
    panel_rows = [r for r in figure_rows if r["slug"] in fsd.PANEL_INPUTS]
    gist_rows = [r for r in figure_rows if r["slug"] not in fsd.PANEL_INPUTS]
    assert {r["slug"] for r in gist_rows} == set(bundle)
    for r in gist_rows:
        assert r["path"] in bundle[r["slug"]]
        assert r["figure"] == labels.get(r["slug"], "")
        assert r["gist_url"].endswith(gists[r["slug"]]), r["slug"]
        assert r["swhid"] == swhids[r["slug"]], r["slug"]
        assert r["generator"] == f"scripts/figures/{r['slug']}.py"
        assert (ROOT / r["generator"]).is_file()
    # Gist-less panel inputs (Figure 4's funnel): labelled, no gist or SWHID.
    assert {(r["slug"], r["path"]) for r in panel_rows} == {
        (s, p) for s, (_, ps) in fsd.PANEL_INPUTS.items() for p in ps
    }
    for r in panel_rows:
        assert r["figure"] == fsd.PANEL_INPUTS[r["slug"]][0]
        assert r["figure"] in labels.values()
        assert r["gist_url"] == r["swhid"] == ""
        assert (ROOT / r["generator"]).is_file()
    # Every manuscript figure drawn from data has its table here.
    assert {r["figure"] for r in figure_rows if r["figure"]} == {
        labels[s] for s in bundle if s in labels
    } | {label for label, _ in fsd.PANEL_INPUTS.values()}
    canonical = [r for r in rows if r["role"] == fsd.ROLE_CANONICAL]
    assert {r["path"] for r in canonical} == CANONICAL
    assert all(r["figure"] == r["slug"] == r["gist_url"] == "" for r in canonical)


def test_inner_readme_documents_the_layout_and_positive_list(built):
    readme = _members(built)[f"{TOP}/README.md"].decode()
    for col in fsd.MANIFEST_COLUMNS:
        assert f"`{col}`" in readme, col
    assert "uv run make_<slug>.py" in readme
    assert "scripts/figures/<slug>.py" in readme
    assert "CC0 1.0" in readme
    assert "positive list" in readme and "never fall back to its native flag" in readme
    assert f"{fsd.summary(V).optimized_cutoffs_rows:,}" in readme


def test_lfs_pointer_is_refused(tmp_path):
    repo = tmp_path / "repo"
    for rel in (fsd.GIST_BUNDLE_SCRIPT, fsd.FIGURE_MANIFEST, fsd.GIST_MAP, fsd.SWHID_MAP):
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_bytes((ROOT / rel).read_bytes())
    for rel in fsd.member_paths():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_bytes((ROOT / rel).read_bytes())
    (repo / fsd.OPTIMIZED_CUTOFFS).write_bytes(b"version https://git-lfs.github.com/spec/v1\n")
    with pytest.raises(RuntimeError, match="LFS pointer"):
        fsd.build_figure_source_tarball(tmp_path / "out", V, repo_root=repo)
