"""Guard the deep-dive filter taxonomy against cross-file drift.

The catalog/compare filter set is mirrored across four places that MUST stay
in sync; a field added to one and forgotten in another silently breaks
filtering. This test pins the relationships so that drift fails CI:

  * viewer/lib/deep-dive-fields.ts  — DD_ENUM_FIELDS / DD_BOOL_FIELDS keys
                                       (+ ECD_BAND_SOURCES)
  * viewer/lib/surfaceome.ts        — DeepDiveFilters interface fields
  * cloudflare/workers/.../index.js — DDF_KEYS (+ ECD_BAND_SOURCES)
  * models.py                       — Filters Pydantic model

No network / no build — pure text + model introspection.
"""
from __future__ import annotations

import re
from pathlib import Path

from accessible_surfaceome.tools._shared.models import Filters

_ROOT = Path(__file__).resolve().parents[1]
_DDF = (_ROOT / "viewer" / "lib" / "deep-dive-fields.ts").read_text()
_SURF = (_ROOT / "viewer" / "lib" / "surfaceome.ts").read_text()
_WORKER = (
    _ROOT / "cloudflare" / "workers" / "surfaceome_api" / "src" / "index.js"
).read_text()

# Derived bands live in the TS/Worker facet set but are NOT Filters fields
# (Python carries the *_ecd_pct_identity floats; the band is derived).
_ECD_BANDS = {"cyno_ortholog_ecd", "mouse_ortholog_ecd", "max_paralog_ecd"}

# Facets sourced from BiologicalContext (not the Filters block) — they
# appear in the catalog/compare filter taxonomy but aren't shipped as flat
# DDF_KEYS by the Worker. The viewer's `pickDeepDiveFilters` and the
# Worker's `projectDeepDiveFilters` both pull these from the deep-dive
# record's biological_context tree directly.
_BIOLOGY_DERIVED = {"primary_compartment"}

# Facets sourced from AccessibilityRisks (not the Filters block). Same
# contract as _BIOLOGY_DERIVED — viewer + Worker pull from the record
# directly, not from the flat filters block.
_ACCESSIBILITY_RISK_DERIVED = {
    "restricted_subdomain_kind",
    "secreted_form_source",
}

# Facets sourced from DeterministicFeatures (tool output baked at
# annotation time + Worker LEFT-JOIN backfill at serve time). Same
# contract as _BIOLOGY_DERIVED — viewer + Worker pull from the record
# directly, not from the flat filters block.
_DETERMINISTIC_FEATURE_DERIVED = {
    "surface_bind_targetability",
    "surface_bind_main_class",
    "is_homo_oligomer",
}


def _dd_facet_keys() -> set[str]:
    """Every catalog facet key — the `key: "..."` literals in the field
    specs and ECD_BAND_SOURCES (deduped to a set)."""
    return set(re.findall(r'key:\s*"([^"]+)"', _DDF))


def _ddf_interface_fields() -> set[str]:
    m = re.search(r"export interface DeepDiveFilters\s*\{(.*?)\n\}", _SURF, re.S)
    assert m, "DeepDiveFilters interface not found"
    return set(re.findall(r"^\s*(\w+)\??:", m.group(1), re.M))


def _worker_ddf_keys() -> set[str]:
    m = re.search(r"const DDF_KEYS\s*=\s*\[(.*?)\]", _WORKER, re.S)
    assert m, "DDF_KEYS not found"
    return set(re.findall(r'"([^"]+)"', m.group(1)))


def _viewer_band_specs() -> set[tuple[str, str, int, int]]:
    block = re.search(r"ECD_BAND_SOURCES[^=]*=\s*\[(.*?)\];", _DDF, re.S)
    assert block, "viewer ECD_BAND_SOURCES not found"
    return {
        (k, s, int(hi), int(mid))
        for k, s, hi, mid in re.findall(
            r'key:\s*"([^"]+)",\s*source:\s*"([^"]+)",\s*hi:\s*(\d+),\s*mid:\s*(\d+)',
            block.group(1),
        )
    }


def _worker_band_specs() -> set[tuple[str, str, int, int]]:
    block = re.search(r"ECD_BAND_SOURCES\s*=\s*\[(.*?)\];", _WORKER, re.S)
    assert block, "Worker ECD_BAND_SOURCES not found"
    return {
        (k, s, int(hi), int(mid))
        for k, s, hi, mid in re.findall(
            r'\[\s*"([^"]+)",\s*"([^"]+)",\s*(\d+),\s*(\d+)\s*\]', block.group(1)
        )
    }


def test_registry_matches_interface() -> None:
    """The TS field registry and the DeepDiveFilters type must list the
    exact same keys."""
    assert _dd_facet_keys() == _ddf_interface_fields()


def test_facets_equal_worker_keys_plus_bands() -> None:
    """Catalog facets = the flat fields the Worker ships + the derived ECD
    bands + facets sourced from BiologicalContext + facets sourced from
    AccessibilityRisks + facets sourced from DeterministicFeatures (these
    are the ONLY ones not in DDF_KEYS)."""
    assert (
        _dd_facet_keys()
        == _worker_ddf_keys()
        | _ECD_BANDS
        | _BIOLOGY_DERIVED
        | _ACCESSIBILITY_RISK_DERIVED
        | _DETERMINISTIC_FEATURE_DERIVED
    )


def test_biology_derived_facets_pulled_from_biological_context() -> None:
    """Every facet in `_BIOLOGY_DERIVED` must be sourced from
    `biological_context` in BOTH the viewer's `pickDeepDiveFilters` and
    the Worker's `projectDeepDiveFilters` — never from the flat `filters`
    block."""
    # Light-weight string check: each derived facet's key should appear
    # alongside a `biological_context` reference in both files. Tightens
    # the parity contract so a future renaming of one side surfaces here.
    for facet in _BIOLOGY_DERIVED:
        assert facet in _DDF and "biological_context" in _DDF, (
            f"viewer pickDeepDiveFilters missing biological_context"
            f" wiring for {facet}"
        )
        assert facet in _WORKER and "biological_context" in _WORKER, (
            f"Worker projectDeepDiveFilters missing biological_context"
            f" wiring for {facet}"
        )


def test_deterministic_feature_derived_facets_pulled_from_deterministic_features() -> None:
    """Every facet in `_DETERMINISTIC_FEATURE_DERIVED` must be sourced from
    `deterministic_features` in BOTH viewer's `pickDeepDiveFilters` and
    the Worker's `projectDeepDiveFilters`, NOT from the flat `filters`
    block. Parallels the BiologicalContext / AccessibilityRisks parity
    tests for the SURFACE-Bind + Schweke projections."""
    for facet in _DETERMINISTIC_FEATURE_DERIVED:
        assert facet in _DDF and "deterministic_features" in _DDF, (
            f"viewer pickDeepDiveFilters missing deterministic_features"
            f" wiring for {facet}"
        )
        assert facet in _WORKER and "deterministic_features" in _WORKER, (
            f"Worker projectDeepDiveFilters missing deterministic_features"
            f" wiring for {facet}"
        )


def test_risk_derived_facets_pulled_from_accessibility_risks() -> None:
    """Every facet in `_ACCESSIBILITY_RISK_DERIVED` must be sourced from
    `accessibility_risks` in BOTH viewer's `pickDeepDiveFilters` and the
    Worker's `projectDeepDiveFilters`, NOT from the flat `filters`
    block. Parallels test_biology_derived_facets_pulled_from_biological_context
    for the AccessibilityRisks → restricted_subdomain projection."""
    for facet in _ACCESSIBILITY_RISK_DERIVED:
        assert facet in _DDF and "accessibility_risks" in _DDF, (
            f"viewer pickDeepDiveFilters missing accessibility_risks"
            f" wiring for {facet}"
        )
        assert facet in _WORKER and "accessibility_risks" in _WORKER, (
            f"Worker projectDeepDiveFilters missing accessibility_risks"
            f" wiring for {facet}"
        )


def test_worker_keys_are_real_filters_fields() -> None:
    """Every DDF_KEY must be a real field on the Python Filters model."""
    missing = _worker_ddf_keys() - set(Filters.model_fields)
    assert not missing, f"DDF_KEYS not present on Filters: {sorted(missing)}"


def test_ecd_bands_consistent_and_real() -> None:
    """The ECD band (key, source, hi, mid) tuples must match viewer↔Worker,
    and every source must be a real numeric Filters field."""
    viewer, worker = _viewer_band_specs(), _worker_band_specs()
    assert viewer == worker, f"ECD band drift: viewer={viewer} worker={worker}"
    assert {k for k, *_ in viewer} == _ECD_BANDS
    fields = set(Filters.model_fields)
    for _key, source, _hi, _mid in viewer:
        assert source in fields, f"band source not a Filters field: {source}"
