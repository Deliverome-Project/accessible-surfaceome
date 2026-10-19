"""Find Zotero citations in a .docx that Zotero itself no longer tracks.

The Zotero Google Docs integration stores each citation as a link to
``https://www.zotero.org/google-docs/?<key>``. When the citation's hidden
field data is lost (moving the text through the Docs API, some copy-paste
paths, accepting certain suggestions), the link becomes
``?broken=<key>``: the text still reads like a citation, but Zotero has
forgotten which item it points to. The next Refresh then drops that item
from the bibliography if nothing else cites it.

``citations.lua`` only notices this indirectly, as a citation with no
reference entry, and only when the broken citation was the item's sole
use. A broken citation to a paper that is also cited intact elsewhere
still matches by author and year, so it passes every downstream check
while being one Refresh away from vanishing. The manuscript shipped with
seven of these (2026-10-18), two of which had already lost their
reference entries. This check reads the link targets directly, so it
catches all of them.

It reads the .docx without pandoc, so it runs in CI.
"""
from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET

_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_PKG_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
_BROKEN = re.compile(r"zotero\.org/google-docs/\?broken=", re.IGNORECASE)
_REFERENCE_HEADING = re.compile(r"^(supplementary\s+)?references$", re.IGNORECASE)
_CONTEXT_CHARS = 70


@dataclass(frozen=True)
class BrokenCitation:
    text: str
    context: str


def _text(el: ET.Element) -> str:
    return "".join(t.text or "" for t in el.iter(f"{{{_W}}}t"))


def find_broken_zotero_citations(docx: Path) -> list[BrokenCitation]:
    """Every link in the body whose target is a ``?broken=`` Zotero URL."""
    with zipfile.ZipFile(docx) as z:
        body = ET.fromstring(z.read("word/document.xml"))
        rels = ET.fromstring(z.read("word/_rels/document.xml.rels"))
    broken_ids = {
        rel.get("Id")
        for rel in rels.iter(f"{{{_PKG_REL}}}Relationship")
        if _BROKEN.search(rel.get("Target", ""))
    }
    if not broken_ids:
        return []

    found: list[BrokenCitation] = []
    in_reference_list = False
    for para in body.iter(f"{{{_W}}}p"):
        # A reference-list entry is bibliography text, not a citation, so
        # "re-insert it through Zotero" is the wrong fix. The manuscript's
        # Supplementary References list carries such an entry.
        style = para.find(f"{{{_W}}}pPr/{{{_W}}}pStyle")
        if style is not None and style.get(f"{{{_W}}}val", "").startswith("Heading"):
            in_reference_list = bool(_REFERENCE_HEADING.match(_text(para).strip()))
            continue
        if in_reference_list:
            continue
        before = ""
        for child in para:
            text = _text(child)
            if (
                child.tag == f"{{{_W}}}hyperlink"
                and child.get(f"{{{_R}}}id") in broken_ids
            ):
                found.append(BrokenCitation(
                    text=" ".join(text.split()),
                    context=" ".join(before.split())[-_CONTEXT_CHARS:],
                ))
            before += text
    return found


def format_broken_report(broken: list[BrokenCitation]) -> str:
    """A stderr block naming each broken citation, or "" when there are none."""
    if not broken:
        return ""
    lines = [
        f"⚠ {len(broken)} Zotero citation(s) in the .docx are marked broken "
        "(link target ?broken=). Zotero no longer tracks them, so a Refresh "
        "can drop their papers from References. Re-insert each one with "
        "Zotero → Add/edit citation, then Refresh:",
    ]
    for b in broken:
        shown = b.text if len(b.text) <= 90 else b.text[:87] + "..."
        lines.append(f"    {shown}   ← …{b.context}" if b.context else f"    {shown}")
    return "\n".join(lines)
