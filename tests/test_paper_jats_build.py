"""paper/jats_build.py: the one manuscript → JATS step that both
paper/build.py and scripts/release/publish-archive.py call.

They used to convert separately, and the deposited XML was pandoc's raw
output while the build's was structured. This runs the shared step end to
end on a small manuscript and pins the two properties the release script
depends on: the XML is the structured one, and with ``href_prefix=""``
every figure it names is a file returned for upload beside it.
"""
from __future__ import annotations

import sys
from pathlib import Path

import lxml.etree as ET  # ty: ignore[unresolved-import]
import pytest

pypandoc = pytest.importorskip("pypandoc")

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "paper"))

HREF = "{http://www.w3.org/1999/xlink}href"
ZOTERO = "https://www.zotero.org/google-docs/?x"

MANUSCRIPT = f"""# A small manuscript

Ada Lovelace^1,\\*^, Alan Turing^2^

^1^First Institute

^2^Second Institute

^\\*^Corresponding author: ada@example.org

## Abstract

The abstract.

## Introduction

Prior work [(Betts et al., 2003)]({ZOTERO}) and Figure 1.

![](missing-image.png)

##### Figure 1. Five databases agree on little. An UpSet plot.

## References

1. [Betts, M.R., Koup, R.A., 2003. A flow assay. J. Immunol. Methods 281, 65–78. https://doi.org/10.1016/s0022-1759(03)00265-5]({ZOTERO})

1. [Zhang, Y., 2010. Another paper. J. Biol. Chem. 285, 1. https://doi.org/10.1/z]({ZOTERO})
"""


def _build(tmp_path: Path, **kwargs):
    from jats_build import build_jats  # ty: ignore[unresolved-import]

    src = tmp_path / "manuscript.md"
    src.write_text(MANUSCRIPT, encoding="utf-8")
    xml = tmp_path / "out" / "manuscript.xml"
    report, files = build_jats(src, xml, pandoc=pypandoc.get_pandoc_path(), **kwargs)
    return ET.parse(str(xml)).getroot(), report, files, xml


def test_the_shared_step_yields_structured_jats(tmp_path: Path) -> None:
    root, report, _, _ = _build(tmp_path)
    meta = root.find("front/article-meta")
    assert "".join(meta.find("title-group/article-title").itertext()) == "A small manuscript"
    assert report.authors == ["Ada Lovelace", "Alan Turing"]
    assert meta.find("abstract") is not None
    assert [r.get("id") for r in root.iter("ref")] == ["ref-betts-2003", "ref-zhang-2010"]
    cite = next(x for x in root.iter("xref") if x.get("ref-type") == "bibr")
    assert cite.get("rid") == "ref-betts-2003"
    assert not [e for e in root.iter("ext-link") if "zotero.org" in (e.get(HREF) or "")]


def test_figures_are_written_flat_beside_the_xml_for_a_deposit(tmp_path: Path) -> None:
    root, report, files, xml = _build(tmp_path, figures_out=tmp_path / "out", href_prefix="")
    assert report.figures == ["Figure 1"]
    hrefs = [g.get(HREF) for g in root.iter("graphic")]
    # Figure 1 is in the manifest, so it resolves to its canonical asset.
    assert len(hrefs) == 1 and "/" not in hrefs[0]
    assert [f.name for f in files] == hrefs
    assert (xml.parent / hrefs[0]).is_file()
    fig_xref = next(x for x in root.iter("xref") if x.get("ref-type") == "fig")
    assert fig_xref.get("rid") == "fig1"


def test_without_a_figures_directory_nothing_is_copied(tmp_path: Path) -> None:
    root, report, files, _ = _build(tmp_path)
    assert files == []
    assert report.unswapped_figures == ["Figure 1"]
