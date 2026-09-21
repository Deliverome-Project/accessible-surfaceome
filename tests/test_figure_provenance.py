"""Enforce schema-v1 ``provenance`` metadata on every managed figure.

Companion to ``tests/test_figure_gists_styling.py`` (which enforces
the inline brand-style sentinel in the gists themselves). This test
enforces that, after running ``scripts/embed_figure_gist_metadata.py``,
each canonical PNG and PDF carries a JSON-valid, schema-v1 provenance
blob.

Network-dependent assertions (SWHID resolves, TSV sha256 matches
upstream) are gated behind the ``--run-network`` pytest flag, registered
in ``tests/conftest.py``.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import httpx
import pikepdf
import pytest
from PIL import Image

from accessible_surfaceome._provenance import (
    SCHEMA_VERSION,
    validate_provenance,
)

# Import the registry from the embed script. The script lives in
# ``scripts/figures/`` so add it to the path.
SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts" / "figures"
sys.path.insert(0, str(SCRIPTS_DIR))
from embed_figure_gist_metadata import FIGURE_PROVENANCE, FIGURES_DIR  # noqa: E402  # ty: ignore[unresolved-import]


def _read_png_provenance(path: Path) -> dict:
    img = Image.open(path)
    raw = img.info.get("provenance")
    assert raw, f"{path.name}: missing 'provenance' tEXt chunk"
    return json.loads(raw)


def _read_pdf_provenance(path: Path) -> dict:
    raw = None
    with pikepdf.open(path) as pdf:
        with pdf.open_metadata() as meta:
            raw = meta.get("pdf:Keywords")
            if not raw:
                # Some pikepdf versions expose Keywords via dc:subject Bag.
                subj = meta.get("dc:subject")
                if isinstance(subj, list):
                    candidates = [
                        s for s in subj if isinstance(s, str) and s.startswith("{")
                    ]
                    if candidates:
                        raw = candidates[0]
    assert raw, f"{path.name}: missing provenance in Keywords/dc:subject"
    return json.loads(raw)


@pytest.mark.parametrize("slug", sorted(FIGURE_PROVENANCE))
def test_png_has_valid_provenance(slug: str) -> None:
    path = FIGURES_DIR / f"{slug}.png"
    if not path.exists():
        pytest.skip(f"{path.name} not regenerated yet")
    blob = _read_png_provenance(path)
    assert blob["schema_version"] == SCHEMA_VERSION
    validate_provenance(blob)


@pytest.mark.parametrize("slug", sorted(FIGURE_PROVENANCE))
def test_pdf_has_valid_provenance(slug: str) -> None:
    path = FIGURES_DIR / f"{slug}.pdf"
    if not path.exists():
        pytest.skip(f"{path.name} not regenerated yet")
    blob = _read_pdf_provenance(path)
    assert blob["schema_version"] == SCHEMA_VERSION
    validate_provenance(blob)


@pytest.mark.network
@pytest.mark.parametrize("slug", sorted(FIGURE_PROVENANCE))
def test_swhid_resolves(slug: str) -> None:
    """For any slug whose provenance carries a SWHID, confirm SWH resolves it."""
    swhid = FIGURE_PROVENANCE[slug].get("swhid")
    if not swhid:
        pytest.skip(f"{slug}: no swhid set yet")
    # Strip any optional qualifiers (e.g. ``;origin=...``) before resolving.
    core_swhid = swhid.split(";", 1)[0]
    url = f"https://archive.softwareheritage.org/api/1/resolve/{core_swhid}/"
    r = httpx.get(url, timeout=30, follow_redirects=True)
    assert r.status_code == 200, (
        f"{slug}: SWHID does not resolve: {url} -> {r.status_code}"
    )


@pytest.mark.network
@pytest.mark.parametrize("slug", sorted(FIGURE_PROVENANCE))
def test_data_sha256_matches_upstream(slug: str) -> None:
    """For each data[] entry with sha256 declared, fetch the URL and confirm the digest."""
    entries = FIGURE_PROVENANCE[slug].get("data") or []
    if not entries:
        pytest.skip(f"{slug}: no data entries")
    for i, entry in enumerate(entries):
        url = entry["url"]
        expected = entry.get("sha256")
        if not expected:
            continue
        r = httpx.get(url, timeout=60, follow_redirects=True)
        assert r.status_code == 200, (
            f"{slug}/data[{i}]: fetch failed: {r.status_code}"
        )
        got = hashlib.sha256(r.content).hexdigest()
        assert got == expected, (
            f"{slug}/data[{i}]: sha256 mismatch - declared {expected}, upstream {got}"
        )
