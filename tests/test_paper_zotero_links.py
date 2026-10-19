"""Tests for the broken-Zotero-citation guard.

Why this exists: moving two paragraphs through the Docs API turned seven
Zotero citations into ``?broken=`` links. Five still matched a reference
by author and year because the same papers were cited intact elsewhere,
so ``citations.lua`` passed them; two lost their reference entries
outright. The guard reads link targets straight from the .docx.

Builds minimal .docx archives in memory, so it needs neither pandoc nor
the ``paper`` extra.
"""
from __future__ import annotations

import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "paper"))

_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def _docx(tmp_path: Path, paragraphs: list[list[tuple[str, str | None]] | str],
          targets: dict[str, str]) -> Path:
    """Each paragraph is a list of (text, rel_id or None for plain text);
    a bare string is a Heading2 paragraph."""
    body = []
    for para in paragraphs:
        if isinstance(para, str):
            body.append('<w:p><w:pPr><w:pStyle w:val="Heading2"/></w:pPr>'
                        f"<w:r><w:t>{para}</w:t></w:r></w:p>")
            continue
        parts = []
        for text, rid in para:
            run = f"<w:r><w:t xml:space=\"preserve\">{text}</w:t></w:r>"
            parts.append(f'<w:hyperlink r:id="{rid}">{run}</w:hyperlink>' if rid else run)
        body.append(f"<w:p>{''.join(parts)}</w:p>")
    document = (f'<w:document xmlns:w="{_W}" xmlns:r="{_R}"><w:body>'
                f"{''.join(body)}</w:body></w:document>")
    rels = ('<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            + "".join(f'<Relationship Id="{rid}" Type="{_R}/hyperlink" Target="{url}" '
                      'TargetMode="External"/>' for rid, url in targets.items())
            + "</Relationships>")
    path = tmp_path / "doc.docx"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("word/document.xml", document)
        z.writestr("word/_rels/document.xml.rels", rels)
    return path


def _find(path: Path):
    from zotero_links import find_broken_zotero_citations  # ty: ignore[unresolved-import]

    return find_broken_zotero_citations(path)


def test_a_broken_citation_is_reported_with_its_context(tmp_path: Path) -> None:
    doc = _docx(
        tmp_path,
        [[("where endolysosomal delivery is desirable ", None),
          ("(de Goeij et al., 2016)", "rId1"), (".", None)]],
        {"rId1": "https://www.zotero.org/google-docs/?broken=QqyNI9"},
    )
    found = _find(doc)
    assert [b.text for b in found] == ["(de Goeij et al., 2016)"]
    assert found[0].context.endswith("delivery is desirable")


def test_an_intact_citation_is_not_reported(tmp_path: Path) -> None:
    """A checker that fires on healthy citations is worse than none."""
    doc = _docx(
        tmp_path,
        [[("three databases ", None), ("(Buniello et al., 2025)", "rId1")]],
        {"rId1": "https://www.zotero.org/google-docs/?Wybz1k"},
    )
    assert _find(doc) == []


def test_broken_citation_that_still_matches_a_reference_is_reported(tmp_path: Path) -> None:
    """The case citations.lua cannot see: the same paper is also cited intact."""
    doc = _docx(
        tmp_path,
        [[("DeepTMHMM ", None), ("(Hallgren et al., 2022)", "rId1")],
         [("topology from DeepTMHMM ", None), ("(Hallgren et al., 2022)", "rId2")]],
        {"rId1": "https://www.zotero.org/google-docs/?broken=abc123",
         "rId2": "https://www.zotero.org/google-docs/?k9Lm2p"},
    )
    assert [b.text for b in _find(doc)] == ["(Hallgren et al., 2022)"]


def test_other_links_are_ignored(tmp_path: Path) -> None:
    doc = _docx(
        tmp_path,
        [[("see ", None), ("the viewer", "rId1")]],
        {"rId1": "https://surfaceome.deliverome.org/?broken=1"},
    )
    assert _find(doc) == []


def test_reference_list_entries_are_skipped(tmp_path: Path) -> None:
    """A bibliography entry is not a citation; only the text after the
    reference list ends is checked again."""
    broken = "https://www.zotero.org/google-docs/?broken="
    doc = _docx(
        tmp_path,
        ["Supplementary References",
         [("Westergaard, D., 2018. A comprehensive comparison.", "rId1")],
         "Supplementary Figure 1",
         [("as reported ", None), ("(Westergaard et al., 2018)", "rId2")]],
        {"rId1": broken + "a1", "rId2": broken + "a2"},
    )
    assert [b.text for b in _find(doc)] == ["(Westergaard et al., 2018)"]


def test_report_is_empty_when_nothing_is_broken() -> None:
    from zotero_links import format_broken_report  # ty: ignore[unresolved-import]

    assert format_broken_report([]) == ""
