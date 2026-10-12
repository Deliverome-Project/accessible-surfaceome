"""Guard the surface-evidence method categories against cross-file drift.

Supplementary Figure 13 and the catalog's "Direct surface method" /
"Supporting method" facets must sort the record's ``surface_evidence.methods``
rows into the same categories. The ordered rule table lives in three places:

  * scripts/build_figure_tsvs.py            — SURFACE_METHOD_RULES (the figure)
  * cloudflare/workers/.../src/index.js     — SURFACE_METHOD_RULES (catalog API)
  * viewer/lib/deep-dive-fields.ts          — SURFACE_METHOD_RULES (build-time
                                              re-derivation from records)

A rule added to one and not the others would make the catalog filter and the
paper figure disagree on what, say, "cell-surface capture MS" means.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "cloudflare/workers/surfaceome_api/src/index.js"
VIEWER = ROOT / "viewer/lib/deep-dive-fields.ts"

_spec = importlib.util.spec_from_file_location("_bft", ROOT / "scripts/build_figure_tsvs.py")
assert _spec and _spec.loader
_bft = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_bft)
SURFACE_METHOD_RULES = _bft.SURFACE_METHOD_RULES
_surface_method = _bft._surface_method


def _js_rules(text: str) -> list[tuple[str, str, str]]:
    m = re.search(r"SURFACE_METHOD_RULES[^=]*=\s*(\[.*?\n\]);", text, re.S)
    assert m, "SURFACE_METHOD_RULES not found"
    return [tuple(r) for r in json.loads(re.sub(r",\s*\]$", "]", m.group(1).strip()))]


def test_rule_tables_identical() -> None:
    py = [tuple(r) for r in SURFACE_METHOD_RULES]
    assert _js_rules(WORKER.read_text()) == py, "Worker rules drifted from the figure"
    assert _js_rules(VIEWER.read_text()) == py, "viewer rules drifted from the figure"


def test_viewer_facet_values_cover_every_category() -> None:
    """Every category a rule can emit (plus "other") is a selectable chip."""
    text = VIEWER.read_text()
    m = re.search(r"const SURFACE_METHOD_VALUES = \[(.*?)\]", text, re.S)
    assert m, "SURFACE_METHOD_VALUES not found"
    values = set(re.findall(r'"([^"]+)"', m.group(1)))
    assert values == {r[2] for r in SURFACE_METHOD_RULES} | {"other"}


def test_worker_projection(tmp_path: Path) -> None:
    """The Worker's projectSurfaceMethods on packed rows: categories match the
    Python rules, direct wins over supporting, other relevances are dropped,
    and the native flag needs a direct row in a native expression system."""
    node = shutil.which("node")
    if node is None:
        if os.environ.get("REQUIRE_WORKER_NODE") == "1":
            pytest.fail("Worker checks require Node; refusing to skip")
        pytest.skip("Node is required for Worker tests")
    source = WORKER.read_text().replace(
        'import { deepDiveTier, isLowLiteratureSurface } from "../../../../viewer/lib/catalog-presets";',
        "const deepDiveTier = () => ({tier: 'likely', facet: null}); "
        "const isLowLiteratureSurface = () => false;",
    )
    shutil.copy2(WORKER.parent / "contact-sites.js", tmp_path / "contact-sites.js")
    source += "\nexport { projectSurfaceMethods };\n"
    (tmp_path / "worker.mjs").write_text(source)

    rows = [
        ("glycoproteomics", "cell_surface_capture", "direct_surface_accessibility", "overexpression", "live_cell"),
        ("flow_cytometry", "live_cell_flow", "direct_surface_accessibility", "overexpression", "live_cell"),
        ("flow_cytometry", "live_cell_flow", "supports_surface_localization", "endogenous", "live_cell"),
        ("immunohistochemistry", "IHC_membranous", "supports_surface_localization", "endogenous", "unknown"),
        ("immunofluorescence", "permeabilized_IF", "expression_only", "endogenous", "permeabilized"),
        ("other", "whole_cell_proteomics", "supports_surface_localization", "unknown", "unknown"),
    ]
    packed = ",".join("|".join(r) for r in rows)
    (tmp_path / "test.mjs").write_text(
        'import { projectSurfaceMethods } from "./worker.mjs";\n'
        f"console.log(JSON.stringify(projectSurfaceMethods({json.dumps(packed)})));\n"
        "console.log(JSON.stringify(projectSurfaceMethods(null)));\n"
        'console.log(JSON.stringify(projectSurfaceMethods("proximity_labeling|surface_biotinylation|direct_surface_accessibility|knock_in_tag|live_cell")));\n'
        # Native + live but a functional assay: native yes, live-cell no.
        'console.log(JSON.stringify(projectSurfaceMethods("functional_surface_assay|functional_surface_assay|direct_surface_accessibility|endogenous|live_cell")));\n'
        # Native + direct IF, but fixed rather than live: live-cell no.
        'console.log(JSON.stringify(projectSurfaceMethods("immunofluorescence|nonpermeabilized_IF|direct_surface_accessibility|endogenous|nonpermeabilized")));\n'
        # Surface biotinylation labeled "nonpermeabilized": still live-cell
        # (the chemistry needs intact cells); explicitly permeabilized: not.
        'console.log(JSON.stringify(projectSurfaceMethods("biotinylation|surface_biotinylation|direct_surface_accessibility|endogenous|nonpermeabilized")));\n'
        'console.log(JSON.stringify(projectSurfaceMethods("biotinylation|surface_biotinylation|direct_surface_accessibility|endogenous|permeabilized")));\n'
    )
    out = subprocess.run(
        [node, str(tmp_path / "test.mjs")], capture_output=True, text=True, check=True
    ).stdout.splitlines()
    got, empty, native, functional, fixed_if, biotin, biotin_perm = (
        json.loads(line) for line in out
    )

    direct = sorted({_surface_method(f, s) for f, s, rel, _sys, _perm in rows
                     if rel == "direct_surface_accessibility"})
    assert got["surface_method_direct"] == direct == ["cell_surface_capture_ms", "flow_cytometry"]
    # Flow has a direct row, so its supporting row is not repeated; the
    # expression-only permeabilized IF row is not surface evidence at all.
    assert got["surface_method_supporting"] == ["immunohistochemistry", "other"]
    # Direct rows are all overexpression: neither native nor live-cell.
    assert got["has_native_direct_surface_evidence"] is False
    assert got["has_live_cell_surface_evidence"] is False
    assert empty == {"surface_method_direct": [], "surface_method_supporting": [],
                     "has_native_direct_surface_evidence": False,
                     "has_live_cell_surface_evidence": False}
    # Proximity labeling is matched on family before the biotin subclass; a
    # knock-in tag counts as native expression.
    assert native == {"surface_method_direct": ["proximity_labeling"],
                      "surface_method_supporting": [],
                      "has_native_direct_surface_evidence": True,
                      "has_live_cell_surface_evidence": True}
    assert functional["has_native_direct_surface_evidence"] is True
    assert functional["has_live_cell_surface_evidence"] is False
    assert fixed_if["has_native_direct_surface_evidence"] is True
    assert fixed_if["has_live_cell_surface_evidence"] is False
    assert biotin["has_live_cell_surface_evidence"] is True
    assert biotin_perm["has_live_cell_surface_evidence"] is False
