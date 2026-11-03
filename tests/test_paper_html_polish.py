"""Tests for the paper build's HTML clean-up (paper/html_polish.py) and the
breakable-identifier Lua filter.

Why: each of these fixed a visible defect in the rendered manuscript.
- Snake_case identifiers in the Methods were unbreakable, stretching the
  justified two-column text into wide word gaps. The filter inserts <wbr>
  after each underscore — but never inside a table, where any break
  opportunity makes WeasyPrint silently drop every later page.
- lxml's HTML parser treats <wbr> as a container, nesting the following
  text inside it; ``unnest_wbr`` restores it to an empty element.
- Word marks every row of Supplementary Table 1 as a header row, so the
  whole table rendered in the uppercase header style.
- Table captions follow their table in the .docx; in print they were
  stranded at the foot of a page with the table on the next.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

lxml_html = pytest.importorskip("lxml.html")

# build.py imports its paper/ siblings by bare name; do the same.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "paper"))

from html_polish import (  # noqa: E402  # ty: ignore[unresolved-import]
    captions_above_tables,
    demote_extra_header_rows,
    polish_print_html,
    unnest_wbr,
)

FILTER = Path(__file__).resolve().parents[1] / "paper/filters/breakable_identifiers.lua"


def _body(fragment: str):
    return lxml_html.fromstring(f"<html><body>{fragment}</body></html>").find("body")


def _html(el) -> str:
    return lxml_html.tostring(el, encoding="unicode")


def test_unnest_wbr_keeps_text_order_and_empties_wbr():
    body = _body("<p>a plan_<wbr>trim_<wbr>select call, <b>x_<wbr>y</b> end.</p>")
    unnest_wbr(body)
    assert body.text_content() == "a plan_trim_select call, x_y end."
    assert all(len(w) == 0 and not w.text for w in body.iter("wbr"))
    assert len(list(body.iter("wbr"))) == 3


def test_demote_extra_header_rows_keeps_only_first_header_row():
    body = _body(
        "<table><thead>"
        "<tr><th>Surface</th><th>Non-surface</th></tr>"
        "<tr><th><p>gpi_anchored</p></th><th><p>nuclear</p></th></tr>"
        "<tr><th><p>multipass</p></th><th><p>cytoplasmic</p></th></tr>"
        "</thead></table>"
    )
    assert demote_extra_header_rows(body) == 2
    table = body.find("table")
    assert len(table.find("thead").findall("tr")) == 1
    rows = table.find("tbody").findall("tr")
    assert [r.findtext("td/p") for r in rows] == ["gpi_anchored", "multipass"]
    assert not table.find("tbody").findall(".//th")


def test_captions_move_above_their_table_only():
    body = _body(
        "<table><tr><td>x</td></tr></table>"
        "<h5>Supplementary Table 1. Reason codes.</h5>"
        "<p><img src='f.png'></p><h5>Figure 2. A figure caption.</h5>"
    )
    captions_above_tables(body)
    kids = list(body)
    assert kids[0].tag == "h5" and "table-caption" in kids[0].get("class")
    assert kids[1].tag == "table"
    # A figure caption is left where it is (and untagged).
    assert kids[3].tag == "h5" and not kids[3].get("class")


def test_polish_print_html_titles_and_welds_table_block(tmp_path):
    page = tmp_path / "paper.html"
    page.write_text(
        "<!DOCTYPE html><html><head><title>my_draft</title></head><body>"
        "<h1>The accessible human surfaceome</h1><p>Body.</p>"
        "<h1>Supplementary information</h1>"
        "<table><thead><tr><th>A</th></tr><tr><th>b</th></tr></thead></table>"
        "<h5>Supplementary Table 1. Codes.</h5>"
        "</body></html>"
    )
    polish_print_html(page)
    doc = lxml_html.parse(str(page)).getroot()
    assert doc.findtext("head/title") == "The accessible human surfaceome"
    block = doc.find(".//div[@class='figure-block table-block']")
    assert block is not None
    assert [el.tag for el in block] == ["h1", "h5", "table"]
    assert block[0].text_content() == "Supplementary information"


def _filtered(markdown: str) -> str:
    # Skip only the filter tests when pandoc isn't installed.
    pypandoc = pytest.importorskip("pypandoc")
    return pypandoc.convert_text(
        markdown, to="html5", format="markdown",
        extra_args=[f"--lua-filter={FILTER}"],
    )


def test_filter_breaks_identifiers_in_prose():
    html = _filtered("The plan_trim_select step emits executive_summary.\n")
    assert "plan_<wbr>trim_<wbr>select" in html
    assert "executive_<wbr>summary" in html


def test_filter_skips_tables_and_plain_underscores():
    html = _filtered(
        "| code |\n|---|\n| gpi_anchored |\n\nA lone _ stays.\n"
    )
    table = re.search(r"<table.*?</table>", html, re.S)
    assert table is not None
    assert "<wbr>" not in table.group(0)
    assert "lone _ stays" in html
