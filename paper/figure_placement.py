"""Move a figure to a chosen spot in the PDF's text flow.

WeasyPrint cannot float a figure to the bottom of a page, so a figure lands
wherever the .docx anchored it, and can split the surrounding text above and
below it. A manifest entry's ``print_place_before`` names the exact body text
the figure (its ``div.figure-block``: image plus caption) should sit
immediately before. When that text starts mid-paragraph, the paragraph is
split there, the figure goes between the halves, and the text resumes after
the figure, the way a journal page breaks a paragraph around a figure. The
first half gets ``class="before-figure"`` so its last line stays justified.

PDF only: the web edition reflows, so it keeps the .docx order.
"""

from __future__ import annotations

import re
from pathlib import Path

from lxml import html as lxml_html


def _span_id_prefix(key: str) -> str:
    if key.startswith("appendix-"):
        return f"appendix-figure-{key.removeprefix('appendix-')}"
    if key.startswith("supplementary-"):
        return f"supplementary-figure-{key.removeprefix('supplementary-')}"
    return f"figure-{key}"


def _find_block(doc, key: str):
    prefix = _span_id_prefix(key)
    pat = re.compile(rf"^{re.escape(prefix)}(?:[^0-9]|$)")
    for span in doc.iter("span"):
        if pat.match(span.get("id", "")):
            node = span
            while node is not None and "figure-block" not in (node.get("class") or "").split():
                node = node.getparent()
            return node
    return None


def _text_nodes(p):
    """(owner, attr) for each top-level text node of ``p``, in order."""
    yield p, "text"
    for child in p:
        yield child, "tail"


def _split_point(doc, snippet: str):
    """The single (paragraph, owner, attr, offset) where ``snippet`` starts."""
    pattern = re.compile(r"\s+".join(re.escape(w) for w in snippet.split()))
    hits = []
    for p in doc.iter("p"):
        if p.xpath("ancestor::div[contains(concat(' ', @class, ' '), ' figure-block ')]"):
            continue
        for owner, attr in _text_nodes(p):
            text = getattr(owner, attr) or ""
            for m in pattern.finditer(text):
                hits.append((p, owner, attr, m.start()))
    return hits


def _split(p, owner, attr: str, offset: int):
    """Split ``p`` before ``offset`` in the given text node; return the second half."""
    p2 = lxml_html.Element(p.tag, {k: v for k, v in p.attrib.items() if k != "id"})
    text = getattr(owner, attr) or ""
    setattr(owner, attr, text[:offset])
    p2.text = text[offset:]
    movers = list(p) if owner is p else list(owner.itersiblings())
    for child in movers:
        p2.append(child)  # append moves the element (and its tail) out of p
    return p2


def apply_print_placements(html_path: Path, manifest: dict) -> list[str]:
    """Apply every manifest ``print_place_before``; return one log line each."""
    wanted = {k: s for k, s in manifest.items() if getattr(s, "print_place_before", None)}
    if not wanted:
        return []
    doc = lxml_html.parse(str(html_path)).getroot()
    log: list[str] = []
    for key, spec in wanted.items():
        block = _find_block(doc, key)
        if block is None:
            log.append(f"  ! placement {key}: figure block not found; left in place")
            continue
        hits = _split_point(doc, spec.print_place_before)
        if len(hits) != 1:
            log.append(
                f"  ! placement {key}: text {spec.print_place_before!r} found "
                f"{len(hits)} times (need exactly 1); left in place"
            )
            continue
        p, owner, attr, offset = hits[0]
        block.getparent().remove(block)
        at_start = owner is p and not (p.text or "")[:offset].strip()
        if at_start:
            p.addprevious(block)
            log.append(f"  placed figure {key} before the paragraph starting {spec.print_place_before[:40]!r}")
            continue
        p2 = _split(p, owner, attr, offset)
        classes = (p.get("class") or "").split()
        p.set("class", " ".join([*classes, "before-figure"]))
        p.addnext(block)
        block.addnext(p2)
        log.append(f"  placed figure {key} mid-paragraph, before {spec.print_place_before[:40]!r}")
    html_path.write_bytes(
        lxml_html.tostring(doc, method="html", encoding="utf-8", doctype="<!DOCTYPE html>")
    )
    return log
