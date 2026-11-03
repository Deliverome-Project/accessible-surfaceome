"""``--manifest`` scopes the publish to named genes.

``publish_tag_sites`` replaces all rows for each gene it is handed and leaves other
genes alone, so the file list is the only thing deciding what moves. Publishing the
whole store would also restamp genes produced by an earlier pipeline run with this
run's version, which is what the manifest exists to avoid.
"""
import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "sync_tag_sites_to_d1", REPO / "scripts/sync_tag_sites_to_d1.py"
)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def _store(tmp_path, names):
    for n in names:
        (tmp_path / f"{n}.json").write_text("{}")
    return tmp_path


def test_manifest_selects_only_its_genes(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "TAG_SITES_DIR", _store(tmp_path, ["AAA", "BBB", "CCC"]))
    man = tmp_path / "m.tsv"
    man.write_text("AAA\tQ1\n# a comment\nCCC\tQ3\n\n")
    assert [f.stem for f in mod._files(None, str(man))] == ["AAA", "CCC"]


def test_no_manifest_takes_the_whole_store(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "TAG_SITES_DIR", _store(tmp_path, ["AAA", "BBB"]))
    assert [f.stem for f in mod._files(None, None)] == ["AAA", "BBB"]


def test_gene_wins_over_manifest(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "TAG_SITES_DIR", _store(tmp_path, ["AAA", "BBB"]))
    man = tmp_path / "m.tsv"
    man.write_text("BBB\n")
    assert [f.stem for f in mod._files("AAA", str(man))] == ["AAA"]


def test_manifest_gene_absent_from_store_is_reported_not_fatal(tmp_path, monkeypatch, caplog):
    monkeypatch.setattr(mod, "TAG_SITES_DIR", _store(tmp_path, ["AAA"]))
    man = tmp_path / "m.tsv"
    man.write_text("AAA\nZZZ\n")
    with caplog.at_level("WARNING"):
        assert [f.stem for f in mod._files(None, str(man))] == ["AAA"]
    assert "ZZZ" in caplog.text
