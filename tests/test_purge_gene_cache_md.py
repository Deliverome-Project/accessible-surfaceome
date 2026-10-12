"""``purge_gene_cache.py --surfaces md`` targets the markdown brief's cache keys.

The ``.md`` brief is served from R2 through ``withEdgeCache``, keyed on its
path, and nothing else purges it: ``publish_record`` covers the record,
evidence, catalog and gene list only. After the briefs are re-exported, an
unpurged ``.md`` keeps serving the old text for up to a day.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from accessible_surfaceome.cloud import surface_annotation

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def purge(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(surface_annotation, "_cache_epoch", lambda client=None: "EPOCH")
    spec = importlib.util.spec_from_file_location(
        "purge_gene_cache", ROOT / "scripts/cloud/purge_gene_cache.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_md_surface_is_the_record_key_plus_md(purge) -> None:
    urls = purge._gene_urls(["NPM1", "EGFR"], "md")
    keys = purge._gene_kv_keys(["NPM1", "EGFR"], "md")
    record = purge._gene_urls(["NPM1", "EGFR"], "record")
    assert urls == [u + ".md" for u in record]
    assert keys == urls
    assert all(u.endswith(("/v1/genes/NPM1.md", "/v1/genes/EGFR.md")) for u in urls)


def test_md_is_not_part_of_both(purge) -> None:
    assert not any(u.endswith(".md") for u in purge._gene_urls(["NPM1"], "both"))
