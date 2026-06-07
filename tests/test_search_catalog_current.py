"""Drift guard: viewer/lib/search-catalog.json must match a fresh build.

``search-catalog.json`` is a generated artifact (scripts/build_search_catalog.py)
that the viewer /prompts page imports at build time. Its generator derives the
per-agent searches from the LIVE deterministic kickoff
(``build_a1_kickoff`` / ``build_a2_kickoff``) + ``_CATEGORY_SPECS``, so any change
to the kickoff templates, the evidence_retrieval categories, or the topic anchors
changes what the catalog *should* contain.

This test rebuilds the catalog in-memory and asserts the committed JSON matches —
so a kickoff/category change that forgets to regenerate fails CI (and local
``check-py``) instead of silently shipping a stale /prompts page. Fix by running::

    uv run python scripts/build_search_catalog.py
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_SCRIPT = _REPO / "scripts" / "build_search_catalog.py"
_JSON = _REPO / "viewer" / "lib" / "search-catalog.json"


def _build_catalog() -> dict:
    spec = importlib.util.spec_from_file_location("build_search_catalog", _SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.build_catalog()


def test_search_catalog_json_matches_fresh_build():
    committed = json.loads(_JSON.read_text())
    fresh = _build_catalog()
    assert committed == fresh, (
        "viewer/lib/search-catalog.json is STALE — it no longer matches the live "
        "deterministic kickoff / evidence_retrieval categories. Regenerate it:\n"
        "    uv run python scripts/build_search_catalog.py"
    )
