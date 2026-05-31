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
    bands (the bands are the ONLY facets not in DDF_KEYS)."""
    assert _dd_facet_keys() == _worker_ddf_keys() | _ECD_BANDS


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
