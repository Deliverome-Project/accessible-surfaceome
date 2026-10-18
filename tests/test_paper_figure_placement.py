"""PDF figure placement (manifest ``print_place_before``) moves the figure block
to the named text, splitting the paragraph when that text starts mid-paragraph."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

from lxml import html as lxml_html

_ROOT = Path(__file__).resolve().parents[1]

_DOC = """<!DOCTYPE html><html><body>
<p>First paragraph.</p>
<div class="figure-block"><p><span id="figure-3.-title"></span><img src="x.svg"></p><h5>Figure 3. Title.</h5></div>
<p>Second paragraph starts here. It cites <a href="#r1">Ref 2020</a>; then 2) the list goes on.</p>
<p>Third paragraph.</p>
</body></html>"""


def _mod():
    spec = importlib.util.spec_from_file_location("figure_placement", _ROOT / "paper/figure_placement.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run(tmp_path: Path, place: str) -> tuple[list[str], list]:
    path = tmp_path / "doc.html"
    path.write_text(_DOC)
    log = _mod().apply_print_placements(path, {"3": SimpleNamespace(print_place_before=place)})
    body = lxml_html.parse(str(path)).getroot().find("body")
    return log, list(body)


def _desc(el) -> str:
    if "figure-block" in (el.get("class") or ""):
        return "FIG"
    return " ".join(el.text_content().split())


def test_mid_paragraph_placement_splits_the_paragraph(tmp_path: Path) -> None:
    log, els = _run(tmp_path, "2) the list goes on")
    assert [_desc(e) for e in els] == [
        "First paragraph.",
        "Second paragraph starts here. It cites Ref 2020; then",
        "FIG",
        "2) the list goes on.",
        "Third paragraph.",
    ]
    assert els[1].get("class").split() == ["before-figure", "mid-sentence"]
    assert els[1].find("a") is not None  # inline link stays in the first half
    assert "mid-paragraph" in log[0]


def test_paragraph_start_placement_moves_without_splitting(tmp_path: Path) -> None:
    _, els = _run(tmp_path, "Third paragraph")
    assert [_desc(e) for e in els] == [
        "First paragraph.",
        "Second paragraph starts here. It cites Ref 2020; then 2) the list goes on.",
        "FIG",
        "Third paragraph.",
    ]


def test_missing_text_leaves_the_figure_in_place_with_a_warning(tmp_path: Path) -> None:
    log, els = _run(tmp_path, "no such words")
    assert [_desc(e) for e in els][1] == "FIG"
    assert log and "found 0 times" in log[0]


def test_sentence_final_split_is_not_justified(tmp_path: Path) -> None:
    _, els = _run(tmp_path, "It cites")
    assert [_desc(e) for e in els][1:3] == ["Second paragraph starts here.", "FIG"]
    assert els[1].get("class").split() == ["before-figure"]
