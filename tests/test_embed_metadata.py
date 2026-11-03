"""Verifies that ``scripts/embed_figure_gist_metadata.py`` writes a
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
# Figure 1 is the UpSet. It was the 5-way Venn until the Venn was demoted to a
# blog figure; this test used to read db_overlap_venn.{png,pdf}, which went on
# carrying a provenance blob naming the UpSet's gist long after the standalone
# Venn stopped being a published figure. Those artifacts are deleted — point the
# guard at the figure that gist actually serves.
UPSET_PNG = FIGURES_DIR / "db_overlap_upset.png"
UPSET_PDF = FIGURES_DIR / "db_overlap_upset.pdf"


@pytest.mark.skipif(not UPSET_PNG.exists(), reason="figure not yet regenerated")
def test_upset_png_carries_provenance() -> None:
    img = Image.open(UPSET_PNG)
    raw = img.info.get("provenance")
    assert raw, "PNG missing 'provenance' tEXt chunk"
    blob = json.loads(raw)
    validate_provenance(blob)
    assert blob["title"] == "M1 surface DB overlap — UpSet (Figure 1)"
    assert blob["gist_url"] == "https://gist.github.com/beccajcarlson/d655abfc9c7deeaff1cfbe584de96ffa"


@pytest.mark.skipif(not UPSET_PDF.exists(), reason="figure not yet regenerated")
def test_upset_pdf_carries_provenance() -> None:
    with pikepdf.open(UPSET_PDF) as pdf:
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
