"""The surface-proteomics methods export publishes no internal storage paths."""

from __future__ import annotations

import importlib.util
import json
import re
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
        == "Method summarized from the paper (PMC1) during our 2026-10-28/29"
        " literature search."
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


def test_source_sentences() -> None:
    assert b.method_source_sentence(
        "Mol Cell Proteomics 2026, PMC13202573, Experimental Procedures"
    ) == (
        "Method as described in the paper's Experimental Procedures"
        " (Mol Cell Proteomics 2026; full text PMC13202573)."
    )
    assert (
        b.instrument_source_sentence("ProteomeXchange record PXD068779")
        == "Instrument as listed in the ProteomeXchange record PXD068779."
    )
    assert (
        b.instrument_source_sentence("ProteomeXchange record PXD1, PXD2")
        == "Instrument as listed in the ProteomeXchange records PXD1 and PXD2."
    )
    # Read from the same source as the method: no separate instrument line.
    assert (
        b.instrument_source_sentence(
            "methods as recorded in this audit (verified_method)"
        )
        is None
    )
    assert (
        b.instrument_source_sentence("PMC5341332 Methods (Europe PMC XML)")
        == "Instrument as named in the paper's Methods (full text PMC5341332)."
    )
    note = b.instrument_source_sentence(
        "ACS 403; Europe PMC abstract has no instrument; no PMC record"
    )
    assert note and "403" not in note and note.endswith(".")
    assert b.method_source_sentence(None) is None


def test_published_sources_are_sentences() -> None:
    path = ROOT / "viewer" / "public" / "data" / "surface-proteomics" / "methods.json"
    if not path.exists():
        return
    for arm, m in json.loads(path.read_text()).items():
        for key in ("method_source", "instrument_source"):
            text = m.get(key)
            if text:
                assert text.endswith("."), (arm, key, text)
                assert "verified_method" not in text and "this audit" not in text, arm
                assert "same source as the method" not in text, arm


def test_study_citation_style() -> None:
    cite = b.study_citation
    assert cite({"first_author": "George BM", "year": 2026}) == "George et al. 2026"
    assert (
        cite({"author_surname": "Cohen Yaron", "n_authors": 9, "year": 2026})
        == "Cohen Yaron et al. 2026"
    )
    assert cite({"first_author": "Cohen Yaron K", "year": 2026}) == (
        "Cohen Yaron et al. 2026"
    )
    assert (
        cite(
            {
                "author_surname": "Smith",
                "second_author_surname": "Jones",
                "n_authors": 2,
                "year": 2020,
            }
        )
        == "Smith and Jones 2020"
    )
    assert cite({"author_surname": "Smith", "n_authors": 1, "year": 2020}) == (
        "Smith 2020"
    )
    assert cite({"first_author": None, "year": 2019}) is None


def test_published_citations_use_surnames() -> None:
    path = ROOT / "viewer" / "public" / "data" / "surface-proteomics" / "studies.json"
    if not path.exists():
        return
    for arm in json.loads(path.read_text())["arms"]:
        c = arm.get("citation")
        if not c:
            continue
        assert re.fullmatch(r"\S.*?( et al\.| and \S.*)? \d{4}", c), (arm["id"], c)
        assert not re.search(r"\b[A-Z]{2,4} \d{4}$", c), (arm["id"], c)
        if arm.get("n_authors") is None:
            assert " et al. " in c, (arm["id"], c)


def test_raw_locations_keep_public_fields_only() -> None:
    tsv = (
        "key\tstudy_id\trecord\tflag\trepository\taccessions\turl\tnotes\n"
        "a\ta\tregistry\traw_public\tPRIDE\tPXD000001; PXD000002\t"
        "https://www.ebi.ac.uk/pride/archive/projects/PXD000001\tsome note\n"
        "b\tb\tregistry\traw_not_deposited\t\t\t\t\n"
        "x\t\tnot_obtained\traw_public\tPRIDE\tPXD9\t\t\n"
    )
    raw = b.load_raw_locations(tsv)
    assert set(raw) == {"a", "b"}
    assert raw["a"] == {
        "flag": "raw_public",
        "repository": "PRIDE",
        "accessions": ["PXD000001", "PXD000002"],
        "url": "https://www.ebi.ac.uk/pride/archive/projects/PXD000001",
    }
    assert raw["b"] == {"flag": "raw_not_deposited"}


def test_split_arms_use_the_parent_tab_and_raw_row() -> None:
    arms = [{"id": "p-child-2026"}, {"id": "solo-2026"}]
    raw = {"p-2026": {"flag": "raw_public"}, "solo-2026": {"flag": "processed_only"}}
    b.attach_sources(arms, {"p-child-2026": "p-2026"}, raw, {"p-2026", "solo-2026"})
    assert arms[0]["raw_data"] == {"flag": "raw_public"}
    assert arms[0]["sheet_tab"] == "p-2026"
    assert arms[1]["sheet_tab"] == "solo-2026"


def test_workbook_sheet_names() -> None:
    import io
    import zipfile

    xml = (
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<sheets><sheet name="Studies" sheetId="1"/><sheet name="abc-2026" sheetId="2"/>'
        "</sheets></workbook>"
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("xl/workbook.xml", xml)
    assert b.workbook_sheet_names(buf.getvalue()) == ["Studies", "abc-2026"]


def test_published_arms_have_sources() -> None:
    path = ROOT / "viewer" / "public" / "data" / "surface-proteomics" / "studies.json"
    if not path.exists():
        return
    data = json.loads(path.read_text())
    if "study_list" not in data:
        return
    assert data["study_list"]["url"].startswith("https://drive.google.com/")
    for arm in data["arms"]:
        assert arm.get("sheet_tab"), arm["id"]
        assert (arm.get("raw_data") or {}).get("flag") in b.RAW_FLAGS, arm["id"]
        assert "notes" not in (arm.get("raw_data") or {}), arm["id"]


def test_annotation_selected_is_shown_not_counted() -> None:
    assert b.STATUS_BY_ROLE["annotation_selected"] == "annotation_selected"
    reason = b.status_reason(
        {"filter_universe": "surfy", "pct_in_surf": 0.9}, "annotation_selected", 0.2
    )
    assert reason == "author pre-filtered to SURFY-predicted surface proteins"


def test_published_statuses_are_known() -> None:
    path = ROOT / "viewer" / "public" / "data" / "surface-proteomics" / "studies.json"
    if not path.exists():
        return
    known = set(b.STATUS_BY_ROLE.values())
    for arm in json.loads(path.read_text())["arms"]:
        assert arm["status"] in known, (arm["id"], arm["status"])
        assert arm["admitted"] == (arm["status"] in ("core", "provisional")), arm["id"]


def test_imputed_provisional_reason() -> None:
    d = {
        "reason": "provisional: values imputed; presence counted.",
        "pct_in_surf": 0.34,
    }
    assert b.status_reason(d, "provisional", 0.2) == (
        "values are imputed: presence counted, per-sample detection not available"
    )


def test_storage_references_are_scrubbed() -> None:
    text = (
        "bioRxiv supplementary S4 (surface compiled), as banked in "
        "external://cell-surface-proteomics/2026-09-19-george-v1/: mean abundance"
    )
    out = b.americanize(text)
    assert out == "bioRxiv supplementary S4 (surface compiled): mean abundance"
    assert not b._STORAGE_LEAK.search(out)


def test_held_reason_prefers_the_real_reason_over_imputation() -> None:
    lasa = {
        "reason": "hold: current table has imputed abundance and unresolved input/sample selection."
    }
    assert b.status_reason(lasa, "held", 0.2) == (
        "the input sample and baseline can't be identified in the published table"
    )
    mahameed = {
        "reason": "Hold: no unperturbed baseline exists; per-replicate, non-imputed LFQ."
    }
    assert b.status_reason(mahameed, "held", 0.2) == (
        "every arm is treated, so there is no unperturbed baseline"
    )
    only = {"reason": "hold: every value is imputed."}
    assert b.status_reason(only, "held", 0.2) == (
        "values are imputed, so detection can't be read per protein"
    )


def test_published_held_arms_have_specific_reasons() -> None:
    path = ROOT / "viewer" / "public" / "data" / "surface-proteomics" / "studies.json"
    if not path.exists():
        return
    generic = "per-protein detection can't be recovered from the table"
    for arm in json.loads(path.read_text())["arms"]:
        if arm["status"] == "held":
            assert arm.get("status_reason") not in (None, generic), arm["id"]
            assert "imputed" not in arm["status_reason"], arm["id"]
