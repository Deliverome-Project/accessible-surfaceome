"""HTML clean-up shared by the print and web paper builds.

Pure lxml (no WeasyPrint), so ``paper/build.py`` and the tests import it
alike. Every function edits a parsed tree in place, except
``polish_print_html``, which reads and rewrites the print HTML file
between pandoc and WeasyPrint.
"""
from __future__ import annotations

from pathlib import Path

from lxml import html as lxml_html


def unnest_wbr(root) -> None:
    """Undo libxml2 treating <wbr> as a container rather than a void tag.

    lxml's HTML parser doesn't know <wbr> (emitted by
    filters/breakable_identifiers.lua) is empty, so it nests the text that
    follows inside it and serializes a stray </wbr>. Hoist that content
    back out, in order, so every <wbr> is empty again.
    """
    for wbr in list(root.iter("wbr")):
        inner, kids, tail = wbr.text, list(wbr), wbr.tail
        if inner is None and not kids:
            continue
        wbr.text = None
        wbr.tail = inner
        last = wbr
        for kid in kids:  # each kid moves with its own tail
            last.addnext(kid)
            last = kid
        last.tail = (last.tail or "") + (tail or "")


def demote_extra_header_rows(body) -> int:
    """Turn every <thead> row after the first into an ordinary body row.

    Word lets an author mark any number of rows as header rows, and pandoc
    puts them all in <thead>. Supplementary Table 1 came through with all
    its rows there, so the stylesheet's header treatment (uppercase, tinted
    band) ran down the whole table. Only the first row is a header.
    """
    moved = 0
    for thead in body.iter("thead"):
        rows = thead.findall("tr")
        if len(rows) < 2:
            continue
        table = thead.getparent()
        tbody = table.find("tbody")
        if tbody is None:
            tbody = thead.makeelement("tbody", {})
            thead.addnext(tbody)
        for i, row in enumerate(rows[1:]):
            for cell in row.findall("th"):
                cell.tag = "td"
            tbody.insert(i, row)
            moved += 1
    return moved


def is_table_caption(el) -> bool:
    text = " ".join((el.text_content() or "").split()).lower()
    return text.startswith(("supplementary table", "table "))


def captions_above_tables(body) -> None:
    """Move each table's caption from below the table to above it.

    Table captions follow their table in the .docx, so in print a page
    break could leave the caption alone at the top of the next page.
    Above the table (class ``table-caption``) the heading keeps with what
    follows, which is the usual convention for tables anyway.
    """
    for table in list(body.iter("table")):
        nxt = table.getnext()
        if nxt is not None and nxt.tag == "h5" and is_table_caption(nxt):
            nxt.set("class", (nxt.get("class", "") + " table-caption").strip())
            table.addprevious(nxt)


def polish_print_html(html_path: Path) -> None:
    """Print-only structural fixes applied between pandoc and WeasyPrint."""
    doc = lxml_html.parse(str(html_path)).getroot()
    body = doc.find("body")
    head = doc.find("head")
    if body is None:
        return

    # The PDF's Title metadata comes from <title>, which pandoc fills with
    # the .docx filename. Use the paper's title (the first <h1>) instead.
    h1 = body.find(".//h1")
    if h1 is not None and head is not None:
        title_text = " ".join((h1.text_content() or "").split())
        title_el = head.find("title")
        if title_text and title_el is not None:
            title_el.text = title_text

    unnest_wbr(body)
    demote_extra_header_rows(body)
    captions_above_tables(body)

    # Weld each table to its caption the way filters/figures.lua welds a
    # figure to its caption: one column-span:all block with
    # break-inside:avoid. WeasyPrint drops the advisory break-after on a
    # spanning caption, so Supplementary Table 1's caption was stranded at
    # the foot of a page with the table on the next. A heading directly
    # before the caption (the "Supplementary information" title) joins
    # the block, so the supplement opens with title, caption and table
    # together rather than leaving the title alone at a page foot.
    for caption in list(body.iter("h5")):
        if "table-caption" not in (caption.get("class") or ""):
            continue
        table = caption.getnext()
        if table is None or table.tag != "table":
            continue
        block = lxml_html.Element("div")
        block.set("class", "figure-block table-block")
        caption.addprevious(block)
        prev = block.getprevious()
        if prev is not None and prev.tag in ("h1", "h2"):
            block.append(prev)
            prev.set("class", (prev.get("class", "") + " table-block-heading").strip())
        block.append(caption)
        block.append(table)

    html_path.write_bytes(
        lxml_html.tostring(
            doc, method="html", encoding="utf-8", doctype="<!DOCTYPE html>"
        ).rstrip(b"\n")
        + b"\n"
    )


FIGURE_BLOCK_XPATH = ".//div[contains(concat(' ', normalize-space(@class), ' '), ' figure-block ')]"


def semantic_captions(body) -> tuple[int, int]:
    """Give the web edition real figure and table captions.

    The .docx styles captions as Heading 5, so pandoc emits ``<h5>``, and
    the print sheet styles that heading as the caption card. On the web a
    caption that is a heading puts every figure into the document outline
    and breaks it (an h5 straight after an h2), which screen readers
    announce as a jump and Lighthouse fails as ``heading-order``.

    Each ``div.figure-block`` (from filters/figures.lua) becomes a
    ``<figure>`` and its caption a ``<figcaption>``. Each table caption
    (``h5.table-caption``, already above its table via
    ``captions_above_tables``) is wrapped with its table in
    ``<figure class="table-block">``. Classes, ids and children are kept,
    so only the tag names change. Web only: the print and JATS builds keep
    their ``<h5>``.

    Raises ``ValueError`` if a figure block has more than one caption or an
    ``<h5>`` is left over afterwards, since either means the generator has
    started emitting a caption shape this function does not know about.

    Returns (figures converted, tables converted).
    """
    figures = 0
    for block in body.xpath(FIGURE_BLOCK_XPATH):
        captions = block.xpath("./h5")
        if len(captions) > 1:
            raise ValueError(
                f"figure block has {len(captions)} <h5> captions; a <figure> takes one"
            )
        block.tag = "figure"
        for caption in captions:
            caption.tag = "figcaption"
        figures += 1

    tables = 0
    for caption in list(body.iter("h5")):
        if "table-caption" not in (caption.get("class") or "").split():
            continue
        table = caption.getnext()
        if table is None or table.tag != "table":
            continue
        wrapper = lxml_html.Element("figure")
        wrapper.set("class", "table-block")
        caption.addprevious(wrapper)
        caption.tag = "figcaption"
        wrapper.append(caption)
        wrapper.append(table)
        tables += 1

    leftover = [
        " ".join((h.text_content() or "").split())[:60] for h in body.iter("h5")
    ]
    if leftover:
        raise ValueError(f"<h5> left after caption conversion: {leftover}")
    return figures, tables


def close_heading_gaps(body) -> int:
    """Re-level headings that skip a level, e.g. an h6 directly under an h4.

    A few Methods sub-subsections are Heading 6 in the .docx directly under
    a Heading 4. Run after ``semantic_captions``, so captions are out of
    the outline and h5 is free. Each heading deeper than one level below
    the heading before it is renamed to that level; the web sheet styles h5
    and h6 alike, so nothing looks different. Returns the number renamed.
    """
    renamed = 0
    # (original level, output level) of each open ancestor heading. Siblings
    # are re-levelled together: the second of two h6s under an h4 must
    # become h5 like the first, not a child of it.
    open_headings: list[tuple[int, int]] = []
    for heading in body.xpath(".//h1 | .//h2 | .//h3 | .//h4 | .//h5 | .//h6"):
        original = int(heading.tag[1])
        while open_headings and open_headings[-1][0] >= original:
            open_headings.pop()
        level = open_headings[-1][1] + 1 if open_headings else original
        if level != original:
            heading.tag = f"h{level}"
            renamed += 1
        open_headings.append((original, level))
    return renamed
