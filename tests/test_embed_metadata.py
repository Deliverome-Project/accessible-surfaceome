"""Verifies that ``scripts/figures/embed_figure_gist_metadata.py`` writes a
schema-valid ``provenance`` blob into each managed figure's PNG/PDF
metadata, in addition to the existing back-compat ``Source`` field.
"""
from __future__ import annotations

import json
from pathlib import Path

import pikepdf
import pytest
from PIL import Image

from accessible_surfaceome._provenance import validate_provenance

REPO_ROOT = Path(__file__).resolve().parents[1]
FIGURES_DIR = REPO_ROOT / "data/analysis/figures"
VENN_PNG = FIGURES_DIR / "db_overlap_venn.png"
VENN_PDF = FIGURES_DIR / "db_overlap_venn.pdf"


@pytest.mark.skipif(not VENN_PNG.exists(), reason="figure not yet regenerated")
def test_venn_png_carries_provenance() -> None:
    img = Image.open(VENN_PNG)
    raw = img.info.get("provenance")
    assert raw, "PNG missing 'provenance' tEXt chunk"
    blob = json.loads(raw)
    validate_provenance(blob)
    assert blob["title"] == "M1 surface DB overlap — 5-way Venn"
    assert blob["gist_url"] == "https://gist.github.com/beccajcarlson/d655abfc9c7deeaff1cfbe584de96ffa"


@pytest.mark.skipif(not VENN_PDF.exists(), reason="figure not yet regenerated")
def test_venn_pdf_carries_provenance() -> None:
    with pikepdf.open(VENN_PDF) as pdf:
        with pdf.open_metadata() as meta:
            raw = meta.get("pdf:Keywords") or meta.get("dc:subject")
    assert raw, "PDF missing provenance in Keywords/dc:subject"
    if isinstance(raw, list):
        # dc:subject is a Bag of strings; the provenance JSON is one element
        candidates = [s for s in raw if isinstance(s, str) and s.startswith("{")]
        assert candidates, "no JSON-shaped element in dc:subject Bag"
        raw = candidates[0]
    blob = json.loads(raw)
    validate_provenance(blob)
