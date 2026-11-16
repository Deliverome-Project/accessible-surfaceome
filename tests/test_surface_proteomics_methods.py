"""The surface-proteomics methods export publishes no internal storage paths."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "build_surface_proteomics_studies",
    ROOT / "scripts" / "build" / "build_surface_proteomics_studies.py",
)
assert _spec and _spec.loader
b = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = b
_spec.loader.exec_module(b)

KEY = "cell-surface-proteomics/2026-10-28-sweep-v1/sources/x-2020/table.xlsx"


def test_source_file_drops_storage_keys() -> None:
    f = b.source_file(
        {
            "key": KEY,
            "local_path": "x-2020/table.xlsx",
            "sha256": "ab" * 32,
            "sheet": "S1",
            "manual_download": {
                "page": "https://doi.org/10.1/x (publisher zip, member table.xlsx)",
                "note": "downloaded by hand; the archived S3 copy is the record",
            },
        }
    )
    assert f == {
        "file": "table.xlsx",
        "sheet": "S1",
        "page": "https://doi.org/10.1/x",
        "sha256": "ab" * 32,
    }


def test_nested_archive_and_derived_table() -> None:
    f = b.source_file(
        {
            "key": KEY,
            "url": "https://example.org/supp.zip",
            "archive_member": ["inner.zip", "Table S3.xlsx"],
            "derived_from": [KEY, {"archive_member": "m.xlsx", "key": KEY}],
            "derivation": "rows split at the header",
        }
    )
    assert f["file"] == "Table S3.xlsx"
    assert f["archive"] == "supp.zip › inner.zip"
    assert f["derived_from"] == [{"file": "table.xlsx"}, {"file": "m.xlsx"}]
    assert "cell-surface-proteomics/" not in json.dumps(f)


def test_filters_and_rationale() -> None:
    e = {
        "source": 0,
        "accession": "Accession",
        "equals": {"Master": "IsMasterProtein", "Contaminant": False},
        "minimum": {"# Unique Peptides": 2},
        "exclude_flags": ["Reverse"],
        "sample_groups": [
            {
                "cell_type": "line A",
                "columns": ["c1"],
                "min_observed": 1,
                "scale": "linear",
            }
        ],
    }
    x = b.extraction(e, [{"file": "t.txt"}])
    assert x["file"] == "t.txt"
    assert x["filters"] == [
        "Master = IsMasterProtein",
        "Contaminant = false",
        "# Unique Peptides ≥ 2",
        "drop rows flagged Reverse",
    ]
    manifest = {
        "datasets": [
            {
                "study_id": "x-2020",
                "reason": "hold: threshold 20.0000%; borderline allowance 0.0%. Imputed matrix.",
                "sources": [{"key": KEY}],
                "extractions": [e],
            }
        ]
    }
    audit = {
        "datasets": {
            "x-2020": {
                "source": "S3E8 sweep registry (sweep_sources.json), method summarized "
                "from PMC1 during the 2026-10-28/29 sweep",
                "beads": "not recorded (sweep registry entry; not audited)",
                "instrument": "Orbitrap",
            }
        }
    }
    m = b.build_methods(manifest, audit, [{"id": "x-2020"}])["x-2020"]
    assert m["rationale"] == "Imputed matrix."
    assert (
        m["method_source"]
        == "Summarized from PMC1 during our 2026-10-28/29 literature sweep"
    )
    assert m["beads"] == "not recorded (not audited)"
    assert "S3E8" not in json.dumps(m) and KEY not in json.dumps(m)


def test_published_methods_carry_no_storage_paths() -> None:
    path = ROOT / "viewer" / "public" / "data" / "surface-proteomics" / "methods.json"
    if not path.exists():
        return
    text = path.read_text()
    for bad in (
        "cell-surface-proteomics/",
        "sprint3/",
        "s3://",
        "outreach",
        "sweep_sources.json",
    ):
        assert bad not in text, bad
