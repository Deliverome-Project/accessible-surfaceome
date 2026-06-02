"""Tests for the Unpaywall PDF -> PaperSection parser.

The bulk of the logic (``_segment_pages_into_sections`` and helpers) is pure
string handling and is tested directly with synthetic per-page text — no PDF
bytes needed. A couple of integration tests drive the pdfplumber-bound layer
with a hand-built minimal PDF (Helvetica base-14 font, byte-accurate xref) so
``pdfminer`` extracts real selectable text.
"""

from __future__ import annotations

from accessible_surfaceome.agents.plan_trim_select import pdf_parse
from accessible_surfaceome.agents.plan_trim_select.pdf_parse import (
    _reflow,
    _segment_pages_into_sections,
    parse_pdf_to_sections,
)
from accessible_surfaceome.tools._shared.europepmc import SectionName

_VALID_NAMES = {"intro", "methods", "results", "discussion", "figure_legends"}

# A ~82-char body sentence; repeat to clear the per-section + per-PDF minimums.
_SENT = "Surface expression of the receptor was quantified on live cells by flow cytometry."


def _body(n: int = 6) -> str:
    # Default clears both _MIN_SECTION_CHARS (per section) and
    # _MIN_PDF_TEXT_CHARS (per PDF, summed) with margin to spare.
    return "\n".join([_SENT] * n)


def _page(*blocks: str) -> str:
    return "\n".join(blocks)


# ---------------------------------------------------------------------------
# Pure-string segmentation
# ---------------------------------------------------------------------------


def test_basic_four_sections() -> None:
    page = _page(
        "Introduction", _body(), "Methods", _body(),
        "Results", _body(), "Discussion", _body(),
        "References", "1. Smith J et al. Nature. 2009.",
    )
    secs = _segment_pages_into_sections([page])
    names = [s.name for s in secs]
    assert names == ["intro", "methods", "results", "discussion"]
    assert all(s.name in _VALID_NAMES for s in secs)
    # References content is dropped, not captured into discussion.
    assert all("Smith J" not in s.text for s in secs)


def test_numeric_prefixed_headings() -> None:
    page = _page(
        "1. Introduction", _body(), "2. Materials and Methods", _body(),
        "3. Results", _body(),
    )
    secs = _segment_pages_into_sections([page])
    assert [s.name for s in secs] == ["intro", "methods", "results"]


def test_introduction_maps_to_intro_not_introduction() -> None:
    secs = _segment_pages_into_sections([_page("Introduction", _body(), "Results", _body())])
    assert secs[0].name == "intro"  # NOT "introduction" — strict 5-name enum


def test_abstract_heading_is_dropped() -> None:
    page = _page(
        "Abstract", "This abstract should not become a section.", _body(1),
        "Introduction", _body(), "Results", _body(),
    )
    secs = _segment_pages_into_sections([page])
    assert {s.name for s in secs} == {"intro", "results"}
    assert all("should not become a section" not in s.text for s in secs)


def test_unknown_subheading_stays_in_current_section() -> None:
    page = _page(
        "Methods", _body(), "Statistical analysis", _body(),
        "Results", _body(),
    )
    secs = _segment_pages_into_sections([page])
    assert [s.name for s in secs] == ["methods", "results"]
    methods = next(s for s in secs if s.name == "methods")
    # An unrecognized subheading is folded into the current section as body
    # text, not promoted to a new section nor dropped.
    assert "Statistical analysis" in methods.text


def test_running_header_footer_stripped() -> None:
    # 4 identical-structured pages sharing a running header line.
    header = "J. Surface Biol. 2009; 12(3)"
    pages = [
        _page(header, "Introduction" if i == 0 else _SENT, _body())
        for i in range(4)
    ]
    secs = _segment_pages_into_sections(pages)
    assert secs, "expected at least one section"
    assert all(header not in s.text for s in secs), "running header not stripped"


def test_dehyphenation_joins_line_break_hyphen() -> None:
    assert _reflow(["The recep-", "tor binds tightly."]) == "The receptor binds tightly."
    # A non-line-break hyphen (followed by nothing) is left alone within a line.
    assert _reflow(["cell-surface protein"]) == "cell-surface protein"


def test_scanned_pdf_too_little_text_returns_empty() -> None:
    assert _segment_pages_into_sections(["Introduction\nshort"]) == []


def test_no_recognized_headings_returns_empty() -> None:
    prose = "\n".join([_SENT] * 20)  # plenty of text, but no headings
    assert _segment_pages_into_sections([prose]) == []


def test_structured_abstract_labels_before_body_ignored() -> None:
    # Clinical-journal structured abstract: Results/Conclusions labels appear
    # BEFORE the real Introduction. They must not open spurious early sections.
    page = _page(
        "Abstract",
        "Results",
        "Sixty-two patients required intensive care in this abstract label.",
        "Conclusions",
        "We conclude something in the abstract.",
        "Introduction", _body(),
        "Results", _body(),
        "Discussion", _body(),
    )
    secs = _segment_pages_into_sections([page])
    assert [s.name for s in secs] == ["intro", "results", "discussion"]
    assert all("Sixty-two patients" not in s.text for s in secs)


def test_broken_text_layer_section_is_dropped() -> None:
    # 'results' has no spaces (broken text layer) → dropped; clean ones kept.
    runon = "\n".join(["Surfaceexpressionofthereceptorwasquantifiedbyflowcytometry"] * 5)
    page = _page("Introduction", _body(), "Methods", _body(), "Results", runon)
    names = [s.name for s in _segment_pages_into_sections([page])]
    assert "results" not in names
    assert "intro" in names and "methods" in names


def test_column_split_detects_two_columns() -> None:
    width = 600.0
    words = [{"text": "l", "x0": 60, "x1": 240, "top": t} for t in range(100, 460, 12)]
    words += [{"text": "r", "x0": 340, "x1": 520, "top": t} for t in range(100, 460, 12)]
    split = pdf_parse._column_split(words, width)
    assert split is not None and 240 < split < 340


def test_column_split_single_column_returns_none() -> None:
    width = 600.0
    words = [{"text": "w", "x0": 60, "x1": 540, "top": t} for t in range(100, 460, 6)]
    assert pdf_parse._column_split(words, width) is None


def test_is_heading_styled_bold_or_large() -> None:
    assert pdf_parse._is_heading_styled({"fontname": "ABC+Arial-BoldMT", "size": 9}, 9.0)
    assert pdf_parse._is_heading_styled({"fontname": "LOO+AdvOT85.B", "size": 9}, 9.0)  # .B = bold
    assert pdf_parse._is_heading_styled({"fontname": "X+Klavika-Regular", "size": 12}, 9.0)  # large
    assert not pdf_parse._is_heading_styled({"fontname": "X+Klavika-Regular", "size": 9}, 9.0)


def test_run_in_heading_split_off_its_line() -> None:
    # JCI/PNAS style: a bold/large heading run into the first sentence.
    line = [
        {"text": "Results", "x0": 40, "top": 100, "fontname": "X.B", "size": 9},
        {"text": "CD19", "x0": 80, "top": 100, "fontname": "X-Reg", "size": 9},
        {"text": "was", "x0": 112, "top": 100, "fontname": "X-Reg", "size": 9},
    ]
    out = pdf_parse._words_to_lines(line, body_size=9.0)
    assert out[0] == "Results"
    assert out[1] == "CD19 was"


def test_run_in_split_skipped_for_body_sentence() -> None:
    # Precision guard: a body sentence merely starting with "Results" (body
    # font, body size) must NOT be split — only bold/large prefixes are.
    line = [
        {"text": "Results", "x0": 40, "top": 100, "fontname": "X-Reg", "size": 9},
        {"text": "showed", "x0": 80, "top": 100, "fontname": "X-Reg", "size": 9},
    ]
    assert pdf_parse._words_to_lines(line, body_size=9.0) == ["Results showed"]


def test_results_first_kept_when_no_introduction() -> None:
    # PNAS/Nature pattern: no Introduction heading; Results first, Methods last.
    page = _page("Results", _body(), "Discussion", _body(), "Materials and Methods", _body())
    names = [s.name for s in _segment_pages_into_sections([page])]
    assert names == ["results", "discussion", "methods"]


def test_page_to_text_reads_left_column_before_right() -> None:
    class _FakePage:
        width = 600.0

        def __init__(self, words: list[dict[str, object]]) -> None:
            self._w = words

        def extract_words(self, **_kw: object) -> list[dict[str, object]]:
            return self._w

        def extract_text(self) -> str:
            return ""

    words: list[dict[str, object]] = []
    for i, top in enumerate(range(100, 460, 12)):
        words.append({"text": f"L{i}", "x0": 60, "x1": 240, "top": top})
        words.append({"text": f"R{i}", "x0": 340, "x1": 520, "top": top})
    txt = pdf_parse._page_to_text(_FakePage(words))
    assert txt.index("L0") < txt.index("R0")
    assert txt.index("L29") < txt.index("R0")  # entire left column precedes right


# ---------------------------------------------------------------------------
# Binary layer (pdfplumber)
# ---------------------------------------------------------------------------


def _build_pdf(lines: list[str]) -> bytes:
    """Build a minimal valid single-page PDF with Helvetica text.

    Byte-accurate xref offsets; one text line per ``Tj`` moving down by the
    text leading. ``pdfminer`` maps base-14 Helvetica to characters, so
    ``extract_text`` returns the literal text.
    """

    def esc(s: str) -> str:
        return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    ops = ["BT", "/F1 11 Tf", "72 740 Td", "13 TL"]
    for i, ln in enumerate(lines):
        if i:
            ops.append("T*")
        ops.append(f"({esc(ln)}) Tj")
    ops.append("ET")
    content = "\n".join(ops).encode("latin-1")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for i, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
    xref_pos = len(out)
    size = len(objects) + 1
    out += f"xref\n0 {size}\n".encode()
    out += b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += b"trailer\n" + f"<< /Size {size} /Root 1 0 R >>\n".encode()
    out += b"startxref\n" + f"{xref_pos}\n".encode() + b"%%EOF"
    return bytes(out)


def test_pdf_bytes_to_pages_roundtrip() -> None:
    pdf = _build_pdf(["Introduction", "Surface expression was high.", "References"])
    pages = pdf_parse._pdf_bytes_to_pages(pdf)
    assert len(pages) == 1
    assert "Introduction" in pages[0]
    assert "Surface expression was high." in pages[0]


def test_parse_pdf_to_sections_end_to_end() -> None:
    lines = ["Introduction"]
    for heading in ("Introduction", "Methods", "Results", "Discussion"):
        if heading != "Introduction":
            lines.append(heading)
        lines += [_SENT, _SENT, _SENT]
    lines += ["References", "1. Smith J et al. Nature. 2009."]

    secs = parse_pdf_to_sections(_build_pdf(lines))
    names = {s.name for s in secs}
    assert names == {"intro", "methods", "results", "discussion"}
    assert all(s.name in _VALID_NAMES for s in secs)
    assert all("Smith J" not in s.text for s in secs)
    # Every section carries anchorable body text.
    assert all(len(s.text) >= 120 for s in secs)


def test_parse_pdf_garbage_bytes_returns_empty() -> None:
    assert parse_pdf_to_sections(b"this is not a pdf at all") == []


def test_parse_pdf_empty_bytes_returns_empty() -> None:
    assert parse_pdf_to_sections(b"") == []


def test_section_name_type_is_the_shared_enum() -> None:
    # Guard: our names are exactly the europepmc SectionName literal set.
    import typing

    assert set(typing.get_args(SectionName)) == _VALID_NAMES
