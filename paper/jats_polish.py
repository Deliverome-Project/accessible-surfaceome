"""Turn pandoc's JATS output into structured JATS.

Pandoc's JATS writer is faithful to the document it is handed, and a
manuscript ``.docx`` is a title, some paragraphs and a run of headings.
Converted directly it is well-formed XML that says nothing a machine can
use: the front matter is empty, the title and abstract are body sections,
every figure is a section whose heading is its legend, the reference list
is a numbered list, and each citation is a link to zotero.org.

The build already knows better than that. ``paper/filters/*.lua`` resolve
citations to reference entries, wrap each figure with its legend, and mark
the legend's lead sentence, so the JATS conversion runs through the same
filters and this module then moves what they found into the elements JATS
has for it:

  front    article-title, contrib-group, aff, author-notes, abstract,
           funding-group, custom-meta (the Viewer / Code / Data links)
  body     the sections, with ``<fig>`` for figures
  back     ack, ref-list, and the supplement as an appendix

It works on the XML tree alone (lxml, no pandoc), so it is tested in CI
without the paper extras. Anything it does not recognise is left where
pandoc put it rather than dropped: a manuscript with an unexpected
section keeps that section in the body.

Usage from the build::

    report = polish_jats(xml_path, graphic_for=...)
"""
from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from lxml import etree

XLINK = "http://www.w3.org/1999/xlink"
HREF = f"{{{XLINK}}}href"

# "Figure 3." / "Supplementary Figure 12." / "Supplementary Table 1."
LABEL = re.compile(r"^\s*((Supplementary\s+)?(Figure|Table)\s+(\d+))\.?\s*", re.I)
NCNAME = re.compile(r"^[A-Za-z_][\w.\-]*$")
DOI_URL = re.compile(r"^https?://(?:dx\.)?doi\.org/(10\.\S+)$", re.I)
ROR_URL = re.compile(r"^https?://ror\.org/\S+$", re.I)

# Front-matter resource links, keyed on the label the filter gives each.
BACK_SECTIONS = {
    "references": "refs",
    "bibliography": "refs",
    "acknowledgments": "ack",
    "acknowledgements": "ack",
    "competing interest statement": "coi",
    "competing interests": "coi",
    "conflict of interest": "coi",
    "author contributions": "con",
    "funding": "funding",
}

# The only elements whose content model includes <break/>.
BREAK_PARENTS = {"td", "th", "title", "article-title", "subtitle", "alt-title",
                 "trans-title", "sig", "sig-block", "disp-formula", "label"}

#: ``graphic_for("3")`` / ``graphic_for("supplementary-12")`` → the href
#: to write for that figure's canonical asset, or None to keep the image
#: the ``.docx`` embedded.
GraphicFor = Callable[[str], str | None]

MIME = {
    "svg": ("image", "svg+xml"),
    "png": ("image", "png"),
    "jpg": ("image", "jpeg"),
    "jpeg": ("image", "jpeg"),
    "webp": ("image", "webp"),
    "tif": ("image", "tiff"),
    "tiff": ("image", "tiff"),
}


@dataclass
class PolishReport:
    title: str = ""
    authors: list[str] = field(default_factory=list)
    affiliations: int = 0
    has_abstract: bool = False
    figures: list[str] = field(default_factory=list)
    tables: list[str] = field(default_factory=list)
    references: int = 0
    citations: int = 0
    figure_xrefs: int = 0
    section_xrefs: int = 0
    #: xrefs whose target no longer exists; unwrapped to plain text.
    dropped_xrefs: list[str] = field(default_factory=list)
    #: figures left pointing at the .docx's embedded image.
    unswapped_figures: list[str] = field(default_factory=list)
    #: things a JATS consumer would expect that the manuscript lacked.
    problems: list[str] = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            f"  front: title, {len(self.authors)} author(s), "
            f"{self.affiliations} affiliation(s), "
            f"{'abstract' if self.has_abstract else 'NO abstract'}",
            f"  {len(self.figures)} fig, {len(self.tables)} table-wrap, "
            f"{self.references} ref",
            f"  xref: {self.citations} bibr, {self.figure_xrefs} fig/table, "
            f"{self.section_xrefs} sec",
        ]
        if self.unswapped_figures:
            lines.append("  ⚠ no canonical asset for: " + ", ".join(self.unswapped_figures))
        if self.dropped_xrefs:
            lines.append(f"  ⚠ {len(self.dropped_xrefs)} cross-reference(s) had no target: "
                         + "; ".join(self.dropped_xrefs[:8]))
        for p in self.problems:
            lines.append(f"  ⚠ {p}")
        return "\n".join(lines)


# ── small tree helpers ────────────────────────────────────────────────


def _text(el: Any) -> str:
    return re.sub(r"\s+", " ", "".join(el.itertext())).strip() if el is not None else ""


def _el(tag: str, text: str | None = None, **attrib: str) -> Any:
    e = etree.Element(tag, {k.replace("_", "-"): v for k, v in attrib.items()})
    if text is not None:
        e.text = text
    return e


def _title_of(sec: Any) -> str:
    return _text(sec.find("title"))


def _unwrap(el: Any) -> None:
    """Replace ``el`` with its own content (text and children)."""
    parent = el.getparent()
    if parent is None:
        return
    idx = parent.index(el)
    prev = parent[idx - 1] if idx > 0 else None
    head = el.text or ""
    children = list(el)
    tail = el.tail or ""
    if prev is not None:
        prev.tail = (prev.tail or "") + head
    else:
        parent.text = (parent.text or "") + head
    for i, c in enumerate(children):
        parent.insert(idx + i, c)
    last = children[-1] if children else prev
    if last is not None:
        last.tail = (last.tail or "") + tail
    else:
        parent.text = (parent.text or "") + tail
    parent.remove(el)


def _drop(el: Any) -> None:
    """Remove ``el`` but keep the text that followed it."""
    parent = el.getparent()
    if parent is None:
        return
    tail = el.tail or ""
    prev = el.getprevious()
    if prev is not None:
        prev.tail = (prev.tail or "") + tail
    else:
        parent.text = (parent.text or "") + tail
    parent.remove(el)


def _move_content(src: Any, dest: Any, *, after: Any = None) -> None:
    """Move ``src``'s mixed content into ``dest``.

    With ``after`` (a child of ``src``), only what follows that child
    moves, starting with its tail.
    """
    if after is None:
        dest.text = (dest.text or "") + (src.text or "")
        src.text = None
        nodes = list(src)
    else:
        dest.text = (dest.text or "") + (after.tail or "")
        after.tail = None
        nodes = list(after.itersiblings())
    for n in nodes:
        dest.append(n)


def _blank(s: str | None) -> bool:
    return not (s or "").strip()


# ── front matter ──────────────────────────────────────────────────────


def _split_name(full: str) -> tuple[str, str]:
    parts = full.split()
    if len(parts) < 2:
        return full, ""
    return parts[-1], " ".join(parts[:-1])


def _parse_authors(p: Any) -> list[tuple[str, list[str]]]:
    """``Name<sup>1, *</sup>, Name<sup>2</sup>`` → [(name, [marks])]."""
    out: list[tuple[str, list[str]]] = []
    pending = p.text or ""
    for child in p:
        if child.tag == "sup":
            name = pending.strip(" ,;\n\t")
            name = re.sub(r"^and\s+", "", name)
            marks = [m.strip() for m in _text(child).split(",") if m.strip()]
            if name:
                out.append((re.sub(r"\s+", " ", name), marks))
            pending = child.tail or ""
        else:
            pending += _text(child) + (child.tail or "")
    return out


def _build_front(root: Any, main: Any, report: PolishReport) -> dict[str, list[Any]]:
    """Fill ``article-meta`` from the title section's leading blocks.

    Returns the pieces the back-matter pass adds to it afterwards
    (``author-notes`` footnotes and the funding group), since those live
    at the end of the manuscript.
    """
    front = root.find("front")
    if front is None:
        front = etree.Element("front")
        root.insert(0, front)
    for jm in front.findall("journal-meta"):
        front.remove(jm)  # a preprint has no journal
    meta = front.find("article-meta")
    if meta is None:
        meta = etree.SubElement(front, "article-meta")
    for child in list(meta):
        meta.remove(child)

    title = main.find("title")
    report.title = _text(title)
    tg = etree.SubElement(meta, "title-group")
    at = etree.SubElement(tg, "article-title")
    if title is not None:
        _move_content(title, at)
        main.remove(title)
    if not report.title:
        report.problems.append("no article title found")

    # Everything before the first section is front matter.
    lead: list[Any] = []
    for child in list(main):
        if child.tag == "sec":
            break
        lead.append(child)

    authors: list[tuple[str, list[str]]] = []
    affs: list[tuple[str, Any]] = []
    corresp: Any = None
    notes: list[Any] = []
    resources: list[tuple[str, str]] = []

    for block in lead:
        main.remove(block)
        if block.tag == "boxed-text":
            for link in block.iter("ext-link"):
                for icon in list(link.iter("inline-graphic")):
                    _drop(icon)  # its alt text repeats the label
                label = _text(link)
                if label and link.get(HREF):
                    resources.append((label, link.get(HREF)))
            continue
        if block.tag != "p":
            continue
        first = block[0] if len(block) else None
        starts_with_sup = first is not None and first.tag == "sup" and _blank(block.text)
        if starts_with_sup and _text(first).isdigit():
            affs.append((_text(first), block))
        elif starts_with_sup and _text(first) in {"*", "†", "‡", "§"}:
            corresp = block
        elif not authors and block.find("sup") is not None:
            authors = _parse_authors(block)
        elif _text(block):
            notes.append(block)

    if authors:
        group = etree.SubElement(meta, "contrib-group")
        for name, marks in authors:
            is_corresp = "*" in marks
            contrib = etree.SubElement(group, "contrib", {"contrib-type": "author"})
            if is_corresp:
                contrib.set("corresp", "yes")
            surname, given = _split_name(name)
            n = etree.SubElement(contrib, "name")
            etree.SubElement(n, "surname").text = surname
            if given:
                etree.SubElement(n, "given-names").text = given
            for m in marks:
                if m.isdigit():
                    x = etree.SubElement(contrib, "xref", {"ref-type": "aff", "rid": f"aff{m}"})
                    etree.SubElement(x, "sup").text = m
                elif m == "*" and corresp is not None:
                    x = etree.SubElement(contrib, "xref", {"ref-type": "corresp", "rid": "cor1"})
                    etree.SubElement(x, "sup").text = "*"
            report.authors.append(name)
    else:
        report.problems.append("no author line found (expected names with superscript affiliations)")

    for num, block in affs:
        aff = etree.SubElement(meta, "aff", {"id": f"aff{num}"})
        etree.SubElement(aff, "label").text = num
        aff[0].tail = (block[0].tail or "").strip()
        for extra in list(block)[1:]:
            aff.append(extra)
    report.affiliations = len(affs)

    author_notes = etree.Element("author-notes")
    if corresp is not None:
        c = etree.SubElement(author_notes, "corresp", {"id": "cor1"})
        mark = corresp[0]
        etree.SubElement(c, "label").text = _text(mark)
        c[0].tail = (mark.tail or "").lstrip()
        for extra in list(corresp)[1:]:
            c.append(extra)
    for block in notes:
        fn = etree.SubElement(author_notes, "fn", {"fn-type": "other"})
        fn.append(block)
    meta.append(author_notes)  # removed again below if it stays empty

    abstract_sec = next(
        (s for s in main.findall("sec") if _title_of(s).lower() == "abstract"), None
    )
    if abstract_sec is not None:
        abstract = etree.SubElement(meta, "abstract")
        for child in list(abstract_sec):
            if child.tag != "title":
                abstract.append(child)
        main.remove(abstract_sec)
        report.has_abstract = True
    else:
        report.problems.append("no Abstract section found")

    return {"author_notes": [author_notes], "resources": resources}  # type: ignore[dict-item]


def _funding_group(sec: Any) -> Any:
    """One award-group per funder paragraph; a ror.org link becomes its id."""
    group = etree.Element("funding-group")
    statement_parts: list[str] = []
    for p in sec.findall("p"):
        ror = next(
            (link.get(HREF) for link in p.iter("ext-link") if ROR_URL.match(link.get(HREF) or "")),
            None,
        )
        for link in list(p.iter("ext-link")):
            if ROR_URL.match(link.get(HREF) or ""):
                _drop(link)
        name = _text(p).rstrip(". ")
        if not name:
            continue
        statement_parts.append(name)
        award = etree.SubElement(group, "award-group")
        source = etree.SubElement(award, "funding-source")
        wrap = etree.SubElement(source, "institution-wrap")
        etree.SubElement(wrap, "institution").text = name
        if ror:
            etree.SubElement(
                wrap, "institution-id", {"institution-id-type": "ror"}
            ).text = ror
    if statement_parts:
        etree.SubElement(group, "funding-statement").text = (
            "Funding: " + "; ".join(statement_parts) + "."
        )
    return group


# ── figures and tables ────────────────────────────────────────────────


def _label_parts(text: str) -> tuple[str, str, str] | None:
    """("Supplementary Figure 12", kind, key) for a caption's opening."""
    m = LABEL.match(text)
    if not m:
        return None
    label = re.sub(r"\s+", " ", m.group(1))
    supp = bool(m.group(2))
    kind = m.group(3).lower()
    n = m.group(4)
    if kind == "figure":
        key = f"supplementary-{n}" if supp else n
    else:
        key = f"table-S{n}" if supp else f"table-{n}"
    return label, kind, key


def _new_id(label: str, kind: str) -> str:
    n = re.search(r"(\d+)$", label)
    num = n.group(1) if n else ""
    supp = label.lower().startswith("supplementary")
    prefix = "fig" if kind == "figure" else "tbl"
    return f"{prefix}{'S' if supp else ''}{num}"


def _caption_from_title(title: Any) -> tuple[Any, str]:
    """Build ``<caption>`` from a legend held in a section ``<title>``.

    The lead sentence (marked by figures.lua) becomes the caption title,
    minus its "Figure N." label; the rest becomes the caption paragraph.
    Returns (caption, full plain-text legend).
    """
    full = _text(title)
    caption = etree.Element("caption")
    lead = title.find("named-content[@content-type='caption-lead']")
    cap_title = etree.SubElement(caption, "title")
    body = etree.Element("p")
    if lead is not None:
        cap_title.text = LABEL.sub("", _text(lead), count=1).strip()
        _move_content(title, body, after=lead)
    else:
        # No marked lead: first sentence is the title, the rest the body.
        rest = LABEL.sub("", full, count=1)
        m = re.match(r"(.+?[.!?])(\s+|$)", rest)
        cap_title.text = (m.group(1) if m else rest).strip()
        remainder = rest[m.end():] if m else ""
        body.text = remainder
    if _text(body) or len(body):
        body.text = (body.text or "").lstrip()
        caption.append(body)
    return caption, full


def _convert_figures(root: Any, graphic_for: GraphicFor | None,
                     id_map: dict[str, str], report: PolishReport) -> None:
    for box in list(root.iter("boxed-text")):
        graphic = next(box.iter("inline-graphic"), None)
        legend_sec = box.find("sec")
        legend_title = legend_sec.find("title") if legend_sec is not None else None
        if graphic is None or legend_title is None:
            continue
        parts = _label_parts(_text(legend_title))
        if parts is None or parts[1] != "figure":
            continue
        label, kind, key = parts
        fig_id = _new_id(label, kind)

        # Every anchor the filters left on this figure resolves to it.
        for anchor in box.iter("styled-content"):
            if anchor.get("id"):
                id_map[anchor.get("id")] = fig_id
        if legend_sec.get("id"):
            id_map[legend_sec.get("id")] = fig_id

        fig = etree.Element("fig", {"id": fig_id, "position": "float"})
        etree.SubElement(fig, "label").text = label
        caption, _ = _caption_from_title(legend_title)
        fig.append(caption)
        alt = graphic.find("alt-text")
        if alt is not None and _text(alt):
            fig.append(alt)

        href = graphic_for(key) if graphic_for else None
        if href is None:
            href = graphic.get(HREF) or ""
            report.unswapped_figures.append(label)
        ext = href.rsplit(".", 1)[-1].lower() if "." in href else ""
        mimetype, subtype = MIME.get(ext, ("image", ext or "png"))
        g = etree.SubElement(fig, "graphic", {"mimetype": mimetype, "mime-subtype": subtype})
        g.set(HREF, href)

        fig.tail = box.tail
        box.getparent().replace(box, fig)
        report.figures.append(label)


def _convert_tables(root: Any, id_map: dict[str, str], report: PolishReport) -> None:
    """A "Table N." caption section becomes the caption of its table.

    The caption is a heading in the .docx, so pandoc makes it a section
    and nests everything up to the next heading inside it. That content
    is hoisted back out to where it belongs.
    """
    for sec in list(root.iter("sec")):
        title = sec.find("title")
        if title is None:
            continue
        parts = _label_parts(_text(title))
        if parts is None or parts[1] != "table":
            continue
        label, kind, _ = parts
        parent = sec.getparent()
        prev, nxt = sec.getprevious(), None
        inner = [c for c in sec if c.tag != "title"]
        wrap = None
        if prev is not None and prev.tag == "table-wrap" and prev.find("caption") is None:
            wrap = prev
        elif inner and inner[0].tag == "table-wrap":
            wrap = inner[0]
        else:
            nxt = sec.getnext()
            if nxt is not None and nxt.tag == "table-wrap":
                wrap = nxt
        if wrap is None:
            continue
        tbl_id = _new_id(label, kind)
        if sec.get("id"):
            id_map[sec.get("id")] = tbl_id
        wrap.set("id", tbl_id)
        caption, _ = _caption_from_title(title)
        lab = _el("label", label)
        wrap.insert(0, caption)
        wrap.insert(0, lab)
        # Hoist the section's other children to follow it, then drop it.
        idx = parent.index(sec)
        for offset, child in enumerate(c for c in inner if c is not wrap):
            parent.insert(idx + 1 + offset, child)
        if wrap.getparent() is sec:
            parent.insert(idx, wrap)
        parent.remove(sec)
        report.tables.append(label)

    # Pandoc reads a .docx table's rows as header rows and leaves the
    # body empty, which no JATS consumer accepts: keep the first row as
    # the header and move the rest to the body as data cells.
    for table in root.iter("table"):
        thead, tbody = table.find("thead"), table.find("tbody")
        if thead is None or tbody is None or len(tbody) or len(thead) < 2:
            continue
        for row in list(thead)[1:]:
            for cell in row.iter("th"):
                cell.tag = "td"
            tbody.append(row)


# ── references ────────────────────────────────────────────────────────


def _ref_list(sec: Any, report: PolishReport) -> Any:
    ref_list = etree.Element("ref-list")
    if sec.get("id") and NCNAME.match(sec.get("id")):
        ref_list.set("id", sec.get("id"))
    title = sec.find("title")
    if title is not None:
        ref_list.append(title)
    entries: list[Any] = []
    for child in sec:
        if child.tag == "list":
            entries.extend(item.find("p") for item in child.findall("list-item"))
        elif child.tag == "p":
            entries.append(child)
    seen: set[str] = set()
    for i, p in enumerate(e for e in entries if e is not None):
        anchor = next((a for a in p.iter("styled-content") if a.get("id")), None)
        rid = anchor.get("id") if anchor is not None else f"ref-{i + 1}"
        if rid in seen:
            rid = f"{rid}-{i + 1}"
        seen.add(rid)
        ref = etree.SubElement(ref_list, "ref", {"id": rid})
        cite = etree.SubElement(ref, "mixed-citation")
        if anchor is not None:
            _drop(anchor)
        _move_content(p, cite)
        for link in list(cite.iter("ext-link")):
            m = DOI_URL.match(link.get(HREF) or "")
            if m:
                link.tag = "pub-id"
                for attr in list(link.attrib):
                    del link.attrib[attr]
                link.set("pub-id-type", "doi")
                for inner in list(link):
                    link.remove(inner)
                link.text = m.group(1)
        cite.text = (cite.text or "").lstrip()
        report.references += 1
    return ref_list


# ── the pass ──────────────────────────────────────────────────────────


def polish(root: Any, graphic_for: GraphicFor | None = None) -> PolishReport:
    """Restructure a pandoc JATS tree in place."""
    report = PolishReport()
    body = root.find("body")
    if body is None:
        report.problems.append("no <body>")
        return report
    tops = body.findall("sec")
    if not tops:
        report.problems.append("no sections in <body>")
        return report
    main = tops[0]
    supplement = next(
        (s for s in tops[1:] if _title_of(s).lower().startswith("supplement")), None
    )

    root.set("article-type", "preprint")
    front_parts = _build_front(root, main, report)
    meta = root.find("front/article-meta")
    author_notes = front_parts["author_notes"][0]

    id_map: dict[str, str] = {}
    _convert_figures(root, graphic_for, id_map, report)
    _convert_tables(root, id_map, report)

    back = root.find("back")
    if back is None:
        back = etree.SubElement(root, "back")
    for child in list(back):
        back.remove(child)

    # The title section dissolves: its sections become the body's, and
    # the back-matter ones go where JATS keeps them.
    position = body.index(main)
    ack = funding = None
    ref_lists: list[Any] = []
    for child in list(main):
        kind = BACK_SECTIONS.get(_title_of(child).lower()) if child.tag == "sec" else None
        main.remove(child)
        if kind == "refs":
            ref_lists.append(_ref_list(child, report))
        elif kind == "ack":
            ack = etree.Element("ack")
            for c in list(child):
                ack.append(c)
        elif kind in {"coi", "con"}:
            fn = etree.SubElement(
                author_notes, "fn",
                {"fn-type": "COI-statement" if kind == "coi" else "con"},
            )
            for c in list(child):
                if c.tag != "title":
                    fn.append(c)
        elif kind == "funding":
            funding = _funding_group(child)
        else:
            body.insert(position, child)
            position += 1
    body.remove(main)

    if not len(author_notes):
        meta.remove(author_notes)
    if funding is not None and len(funding):
        meta.append(funding)
    resources = front_parts["resources"]
    if resources:
        group = etree.SubElement(meta, "custom-meta-group")
        for label, url in resources:  # type: ignore[misc]
            cm = etree.SubElement(group, "custom-meta")
            etree.SubElement(cm, "meta-name").text = label
            value = etree.SubElement(cm, "meta-value")
            link = etree.SubElement(value, "ext-link", {"ext-link-type": "uri"})
            link.set(HREF, url)
            link.text = url

    if ack is not None:
        back.append(ack)
    for rl in ref_lists:
        back.append(rl)
    if not ref_lists:
        report.problems.append("no References section found")

    if supplement is not None:
        body.remove(supplement)
        group = etree.SubElement(back, "app-group")
        app = etree.SubElement(group, "app", {"id": "app-supplementary"})
        tail_lists: list[Any] = []
        for child in list(supplement):
            if child.tag == "sec" and BACK_SECTIONS.get(
                re.sub(r"^supplement(ary|al)\s+", "", _title_of(child).lower())
            ) == "refs":
                tail_lists.append(_ref_list(child, report))
            else:
                app.append(child)
        for rl in tail_lists:
            app.append(rl)

    _order_block_content(root)
    _fix_ids_and_xrefs(root, id_map, report)
    _tidy(root)
    return report


def _order_block_content(root: Any) -> None:
    """Sections come after a container's own paragraphs, figures and tables."""
    for container in list(root.iter("sec", "app", "body")):
        first_sec = container.find("sec")
        if first_sec is None:
            continue
        idx = container.index(first_sec)
        for child in list(container)[idx:]:
            if child.tag in {"fig", "table-wrap", "p", "boxed-text", "list"}:
                container.remove(child)
                container.insert(container.index(first_sec), child)


def _fix_ids_and_xrefs(root: Any, id_map: dict[str, str], report: PolishReport) -> None:
    # Section ids come from heading text; one that starts with a digit
    # ("1.-cross-species-orthology") is not a legal XML id.
    for sec in root.iter("sec", "app", "ref-list"):
        sid = sec.get("id")
        if sid and not NCNAME.match(sid):
            fixed = "sec-" + re.sub(r"[^\w.\-]", "-", sid)
            id_map[sid] = fixed
            sec.set("id", fixed)

    ids: dict[str, Any] = {}
    for el in root.iter():
        if isinstance(el.tag, str) and el.get("id"):
            ids.setdefault(el.get("id"), el)

    for xref in list(root.iter("xref")):
        if xref.get("ref-type") in {"aff", "corresp"}:
            continue
        rid = id_map.get(xref.get("rid") or "", xref.get("rid") or "")
        target = ids.get(rid)
        if target is None:
            report.dropped_xrefs.append(_text(xref))
            _unwrap(xref)
            continue
        xref.set("rid", rid)
        if target.tag == "ref":
            xref.set("ref-type", "bibr")
            report.citations += 1
        elif target.tag == "fig":
            xref.set("ref-type", "fig")
            report.figure_xrefs += 1
        elif target.tag == "table-wrap":
            xref.set("ref-type", "table")
            report.figure_xrefs += 1
        else:
            xref.set("ref-type", "sec")
            report.section_xrefs += 1


def _tidy(root: Any) -> None:
    # A soft line break in the .docx becomes <break/>, which JATS allows
    # in titles and table cells but not in a paragraph.
    for br in list(root.iter("break")):
        parent = br.getparent()
        if parent is not None and parent.tag not in BREAK_PARENTS:
            br.tail = " " + (br.tail or "").lstrip()
            _drop(br)
    # Anchors the filters planted for HTML have done their job.
    for anchor in list(root.iter("styled-content")):
        if not _text(anchor) and not len(anchor):
            _drop(anchor)
    # Google Docs underlines its links; in XML the link is the markup.
    for link in root.iter("ext-link"):
        for u in list(link.iter("underline")):
            _unwrap(u)
    # The lead marker is an HTML styling hook with no JATS meaning.
    for marker in list(root.iter("named-content")):
        if marker.get("content-type") == "caption-lead":
            _unwrap(marker)
    # Icons from the HTML resource row, if any survived.
    for icon in list(root.iter("inline-graphic")):
        href = icon.get(HREF) or ""
        if href.startswith("/") or "/assets/" in href:
            _drop(icon)
    for meta in root.iter("article-meta"):
        for perm in meta.findall("permissions"):
            if not len(perm):
                meta.remove(perm)


# Elements article-meta places after <pub-date> (JATS 1.2 content model).
# A pub-date is inserted before the first of these that is present.
_AFTER_PUB_DATE = (
    "volume", "issue", "fpage", "elocation-id", "history", "permissions",
    "self-uri", "related-article", "abstract", "trans-abstract", "kwd-group",
    "funding-group", "conference", "counts", "custom-meta-group",
)


def set_article_identity(root: Any, doi: str | None = None,
                         pub_date: date | None = None) -> None:
    """Record the article's own DOI and posting date in ``article-meta``.

    The .docx has neither: a preprint server assigns the DOI after the
    manuscript is submitted. Without them a reader of the XML alone cannot
    tell which article it is, so a deposit made after posting passes both
    in. Re-running replaces earlier values rather than duplicating them.
    """
    meta = root.find("front/article-meta")
    if meta is None:
        return
    if doi:
        for old in meta.findall("article-id[@pub-id-type='doi']"):
            meta.remove(old)
        meta.insert(0, _el("article-id", doi, **{"pub-id-type": "doi"}))
    if pub_date is not None:
        for old in meta.findall("pub-date"):
            meta.remove(old)
        pd = etree.Element("pub-date", {"publication-format": "electronic", "date-type": "pub"})
        etree.SubElement(pd, "day").text = f"{pub_date.day:02d}"
        etree.SubElement(pd, "month").text = f"{pub_date.month:02d}"
        etree.SubElement(pd, "year").text = str(pub_date.year)
        anchor = next((c for c in meta if c.tag in _AFTER_PUB_DATE), None)
        if anchor is None:
            meta.append(pd)
        else:
            anchor.addprevious(pd)


def polish_jats(xml_path: Path, graphic_for: GraphicFor | None = None, *,
                doi: str | None = None, pub_date: date | None = None) -> PolishReport:
    """Polish the JATS file at ``xml_path`` in place and return the report."""
    parser = etree.XMLParser(remove_blank_text=False, resolve_entities=False, no_network=True)
    tree = etree.parse(str(xml_path), parser)
    report = polish(tree.getroot(), graphic_for)
    set_article_identity(tree.getroot(), doi, pub_date)
    tree.write(str(xml_path), xml_declaration=True, encoding="utf-8",
               doctype=tree.docinfo.doctype or None)
    return report
