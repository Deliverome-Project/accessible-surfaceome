"""Parse an Unpaywall-sourced publisher PDF into ``PaperSection`` objects.

Third-fallback body source for
``abstract_triage._fetch_body_drafts`` (after PMC JATS and the PMID->PMCID
eLink lookup). The output mirrors ``europepmc.parse_jats_sections`` so that
PDF-derived body clips are indistinguishable downstream: same ``SectionName``
enum, same ``FULLTEXT_CHAR_CAP`` applied through the shared ``_apply_char_cap``,
fed to the same ``extract_paper_drafts``.

Layered for testability:

* ``_pdf_bytes_to_pages(pdf_bytes)``      -> ``list[str]``  (pdfplumber; binary in)
* ``_segment_pages_into_sections(pages)`` -> ``list[PaperSection]``  (pure string)
* ``parse_pdf_to_sections(pdf_bytes)``    -> ``list[PaperSection]``  (compose)

Section detection is exact-phrase / regex based (issue #45 approach "A"). Flat
PDF text lacks JATS's explicit ``<sec>`` boundaries, so boundaries are inferred
from heading lines, and a line must EXACTLY match a known heading phrase (after
stripping an enumerator + trailing punctuation) to count as a heading. This is
deliberately stricter than the unanchored ``\\bword\\b`` search
``europepmc._TITLE_KEYWORD_MAP`` runs on known-heading ``<title>`` text: on flat
body text an unanchored match would misread a sentence like "Results showed..."
as a Results heading.
"""

from __future__ import annotations

import io
import logging
import re
from collections import Counter
from typing import Any

from accessible_surfaceome.tools._shared.europepmc import (
    FULLTEXT_CHAR_CAP,
    SectionName,
    _apply_char_cap,
)
from accessible_surfaceome.tools._shared.models import PaperSection

logger = logging.getLogger(__name__)

# Minimum total extractable characters for a PDF to count as a real text-layer
# paper. Below this it is almost certainly a scanned-image PDF with no usable
# text layer -> return [] (the caller falls back to the abstract).
_MIN_PDF_TEXT_CHARS = 800
# A detected body section needs at least this much text to be worth emitting —
# guards against a stray heading-like line producing an empty section.
_MIN_SECTION_CHARS = 120
# Minimum space-to-char ratio for a section to count as readable prose. Normal
# English runs ~0.15; below this the PDF's text layer is broken (no recoverable
# word boundaries) and the section is dropped rather than emit unquotable
# run-together text. The paper then falls back to its abstract.
_MIN_SPACE_RATIO = 0.06

# Normalized heading phrase -> body ``SectionName``. Matched EXACTLY against the
# output of ``_normalize_heading`` (lowercased, enumerator + trailing ':'/'.'
# stripped). Mirrors the JATS title vocabulary in
# ``europepmc._SEC_TYPE_MAP`` / ``_TITLE_KEYWORD_MAP`` but as exact phrases,
# because PDF heading lines are inferred from flat text (see module docstring).
_HEADING_TO_SECTION: dict[str, SectionName] = {
    "introduction": "intro",
    "background": "intro",
    "methods": "methods",
    "materials and methods": "methods",
    "material and methods": "methods",
    "methods and materials": "methods",
    "experimental procedures": "methods",
    "experimental section": "methods",
    "experimental methods": "methods",
    "methodology": "methods",
    "patients and methods": "methods",
    "subjects and methods": "methods",
    "star methods": "methods",
    "results": "results",
    "results and discussion": "results",
    "discussion": "discussion",
    "conclusion": "discussion",
    "conclusions": "discussion",
    "concluding remarks": "discussion",
    "figure legends": "figure_legends",
    "figure captions": "figure_legends",
    "figures": "figure_legends",
}

# Headings that mark non-body / end-of-body content. Hitting one stops capture
# of the current section (``current`` -> ``None``). ``abstract`` is here on
# purpose: the abstract reaches ``extract_paper_drafts`` via the separate
# ``abstract=`` argument, so a PDF "Abstract" heading would only duplicate it.
_DROP_HEADINGS: frozenset[str] = frozenset(
    {
        "abstract",
        "summary",
        "graphical abstract",
        "highlights",
        "references",
        "reference",
        "bibliography",
        "literature cited",
        "works cited",
        "acknowledgements",
        "acknowledgments",
        "acknowledgement",
        "acknowledgment",
        "author contributions",
        "authors contributions",
        "author information",
        "contributions",
        "funding",
        "funding information",
        "financial support",
        "grant support",
        "conflict of interest",
        "conflicts of interest",
        "competing interests",
        "declaration of competing interest",
        "declarations",
        "disclosure",
        "disclosures",
        "supplementary material",
        "supplementary materials",
        "supplementary information",
        "supporting information",
        "data availability",
        "data availability statement",
        "ethics",
        "ethics statement",
        "ethical approval",
        "consent",
        "abbreviations",
        "keywords",
        "key words",
        "appendix",
        "notes",
        "orcid",
    }
)

_ENUM_PREFIX_RE = re.compile(
    r"^\s*(?:\d{1,2}|[ivxlcdm]{1,5}|[a-z])[.)]\s+", re.IGNORECASE
)
_PAGE_NUM_RE = re.compile(r"^\s*\d{1,4}\s*$")
_JUNK_LINE_RE = re.compile(
    r"(downloaded from|^https?://|this article is protected by copyright|"
    r"all rights reserved|©|\bdoi:\s|see discussions, stats|^\s*page \d+\b)",
    re.IGNORECASE,
)
# A heading candidate line is short.
_HEADING_MAX_CHARS = 48
_HEADING_MAX_WORDS = 6


def parse_pdf_to_sections(pdf_bytes: bytes) -> list[PaperSection]:
    """Parse a PDF byte string into body ``PaperSection`` objects.

    Returns ``[]`` (never raises) when the PDF is empty, encrypted/corrupt, a
    scanned image with no text layer, or has no recognizable body headings —
    every one of which the caller treats as "no body" and falls back to the
    abstract. Only the abstract reaches ``extract_paper_drafts`` separately, so
    a returned section list is purely body content (intro/methods/results/
    discussion/figure_legends), References excluded.
    """

    if not pdf_bytes:
        return []
    try:
        pages = _pdf_bytes_to_pages(pdf_bytes)
    except Exception as exc:  # noqa: BLE001 — corrupt/encrypted/scanned PDF, etc.
        logger.warning("PDF text extraction failed: %s", exc)
        return []
    return _segment_pages_into_sections(pages)


_MIN_WORDS_FOR_COLUMNS = 60
# Defensive caps for parsing untrusted publisher PDFs (DoS hardening). A real
# paper + supplement is well under both; anything larger is skipped before the
# expensive per-page extraction.
_MAX_PDF_PAGES = 80


def _pdf_bytes_to_pages(pdf_bytes: bytes) -> list[str]:
    """Extract per-page text via pdfplumber. The only pdfplumber-bound layer."""

    import pdfplumber  # lazy: keeps the hot agent import path off pdfminer

    pages: list[str] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for i, page in enumerate(pdf.pages):
            if i >= _MAX_PDF_PAGES:
                break
            pages.append(_page_to_text(page))
    return pages


def _page_to_text(page: Any) -> str:
    """Reconstruct reading-order text for one page from word boxes.

    Uses ``extract_words`` rather than ``extract_text`` for two reasons that
    bite real publisher PDFs: (1) word boxes carry reliable inter-word spacing
    (``extract_text`` drops spaces on some fonts, yielding "Surfaceexpression"),
    and (2) two-column layouts are split at the detected gutter so the left
    column is read top-to-bottom before the right — ``extract_text`` interleaves
    the columns row by row, mixing two stories together.
    """

    try:
        words = page.extract_words(keep_blank_chars=False)
    except Exception:  # noqa: BLE001 — fall back to the simple extractor
        return page.extract_text() or ""
    if not words:
        return page.extract_text() or ""

    # Some PDFs (tight kerning / no space glyphs) merge whole phrases into one
    # "word" at the default gap tolerance — e.g. "Surfaceexpressionofthe". When
    # the mean token looks too long, re-extract with a tighter tolerance that
    # splits on the smaller real inter-word gaps.
    if _avg_token_len(words) > 11.0:
        retry = page.extract_words(keep_blank_chars=False, x_tolerance=1.0)
        if retry and _avg_token_len(retry) < _avg_token_len(words):
            words = retry

    width = float(getattr(page, "width", 0) or 0)
    split = _column_split(words, width)
    if split is None:
        return "\n".join(_words_to_lines(words))

    left = [w for w in words if w["x1"] <= split]
    right = [w for w in words if w["x0"] >= split]
    # Full-width straddlers (section headings, figures) join whichever column
    # their center sits in, so a heading line isn't dropped at the gutter.
    for w in words:
        if w["x0"] < split < w["x1"]:
            (left if (w["x0"] + w["x1"]) / 2 < split else right).append(w)
    return "\n".join(_words_to_lines(left) + _words_to_lines(right))


def _column_split(words: list[dict[str, Any]], width: float) -> float | None:
    """Return the gutter x of a cleanly two-column page, else ``None``.

    Sweeps candidate gutters across the central band and picks the one the
    fewest words cross. A real two-column page has a gutter essentially no word
    spans (straddle ~0) with substantial mass on both sides; a single-column
    page has no such clean cut (every candidate split bisects many lines).
    """

    n = len(words)
    if width <= 0 or n < _MIN_WORDS_FOR_COLUMNS:
        return None
    # A true gutter is an empty vertical *band*, not just a point no word's
    # center crosses. Counting words that intersect a ~10pt band rejects the
    # incidental ~4pt gaps between adjacent words (which a point test would
    # mistake for a gutter when many lines happen to break at the same x).
    half = max(4.0, width * 0.008)
    best_straddle = 1.0
    best_x = width / 2.0
    for i in range(38, 63):
        s = width * i / 100.0
        straddle = sum(1 for w in words if w["x0"] < s + half and w["x1"] > s - half) / n
        if straddle < best_straddle:
            best_straddle, best_x = straddle, s
    left = sum(1 for w in words if w["x1"] <= best_x) / n
    right = sum(1 for w in words if w["x0"] >= best_x) / n
    if best_straddle <= 0.02 and left >= 0.25 and right >= 0.25:
        return best_x
    return None


def _words_to_lines(words: list[dict[str, Any]], y_tol: float = 3.0) -> list[str]:
    """Group word boxes into text lines by vertical position, left-to-right."""

    if not words:
        return []
    ws = sorted(words, key=lambda w: (w["top"], w["x0"]))
    lines: list[list[dict[str, Any]]] = [[ws[0]]]
    ref_top = ws[0]["top"]
    for w in ws[1:]:
        if abs(w["top"] - ref_top) <= y_tol:
            lines[-1].append(w)
        else:
            lines.append([w])
            ref_top = w["top"]
    return [
        " ".join(x["text"] for x in sorted(line, key=lambda w: w["x0"]))
        for line in lines
    ]


def _segment_pages_into_sections(pages: list[str]) -> list[PaperSection]:
    """Pure-string segmentation of per-page text into body sections."""

    if sum(len(p) for p in pages) < _MIN_PDF_TEXT_CHARS:
        return []

    lines = _clean_lines(pages)

    buffers: dict[SectionName, list[str]] = {}
    order: list[SectionName] = []
    current: SectionName | None = None
    body_started = False  # have we reached the body proper (intro/methods)?
    for line in lines:
        kind = _heading_kind(line)
        if kind is not None:
            tag, name = kind
            if tag == "drop":
                current = None
            elif name is not None:  # body heading
                # intro/methods start the body proper. A combined "Results and
                # Discussion" also starts it — Brief Reports / short comms use
                # that single heading with no separate intro (and structured
                # abstracts never label a section "Results and Discussion").
                if name in ("intro", "methods") or (
                    name == "results" and _normalize_heading(line) == "results and discussion"
                ):
                    body_started = True
                elif not body_started:
                    # A bare results/discussion/figure_legends heading before
                    # the body proper is a structured-abstract label (the common
                    # "Background / Methods / Results / Conclusions" abstract in
                    # clinical journals). Ignore it so abstract + title-block
                    # text isn't captured as a spurious early section.
                    current = None
                    continue
                current = name
                if name not in buffers:
                    buffers[name] = []
                    order.append(name)
            continue
        if current is not None:
            buffers[current].append(line)

    raw: list[tuple[SectionName, str]] = []
    for name in order:
        text = _reflow(buffers[name])
        if len(text) >= _MIN_SECTION_CHARS and _space_ratio(text) >= _MIN_SPACE_RATIO:
            raw.append((name, text))
    if not raw:
        return []
    sections, _truncated = _apply_char_cap(raw, FULLTEXT_CHAR_CAP)
    return sections


def _clean_lines(pages: list[str]) -> list[str]:
    """Flatten pages to lines, stripping running headers/footers + junk.

    A normalized short line that recurs on >=60% of pages (with >=4 pages) is
    treated as a running header/footer and dropped everywhere. Standalone page
    numbers and a small set of boilerplate patterns (copyright, "downloaded
    from", bare URLs/DOIs) are always dropped.
    """

    per_page = [p.splitlines() for p in pages]
    n_pages = len(per_page)

    freq: Counter[str] = Counter()
    for plines in per_page:
        for key in {_norm(ln) for ln in plines if _norm(ln) and len(_norm(ln)) <= 80}:
            freq[key] += 1
    threshold = max(3, int(0.6 * n_pages))
    boiler = {k for k, c in freq.items() if n_pages >= 4 and c >= threshold}

    out: list[str] = []
    for plines in per_page:
        for ln in plines:
            s = ln.rstrip()
            key = _norm(s)
            if not key or key in boiler:
                continue
            if _PAGE_NUM_RE.match(s) or _JUNK_LINE_RE.search(s):
                continue
            out.append(s)
    return out


def _reflow(lines: list[str]) -> str:
    """Join body lines into continuous text so sentence splitting works.

    De-hyphenates line-break hyphens ("recep-" + "tor" -> "receptor") and joins
    the remaining lines with single spaces. (Occasionally merges a genuine
    end-of-line hyphenated compound, which is harmless: downstream quoting is
    substring-anchored against this exact text.)
    """

    parts: list[str] = []
    for ln in lines:
        ln = ln.strip()
        if not ln:
            continue
        if parts and parts[-1].endswith("-") and parts[-1][-2:-1].isalpha():
            parts[-1] = parts[-1][:-1] + ln
        else:
            parts.append(ln)
    return re.sub(r"[ \t]+", " ", " ".join(parts)).strip()


def _heading_kind(line: str) -> tuple[str, SectionName | None] | None:
    """Classify a line as a heading.

    Returns ``("body", name)`` for a recognized body-section heading,
    ``("drop", None)`` for a recognized non-body heading (references, funding,
    ...), or ``None`` when the line is not a heading (i.e. body text).
    """

    raw = line.strip()
    if not raw or len(raw) > _HEADING_MAX_CHARS:
        return None
    norm = _normalize_heading(line)
    if not norm or len(norm.split()) > _HEADING_MAX_WORDS:
        return None
    if norm in _HEADING_TO_SECTION:
        return ("body", _HEADING_TO_SECTION[norm])
    if norm in _DROP_HEADINGS:
        return ("drop", None)
    return None


def _normalize_heading(line: str) -> str:
    s = _ENUM_PREFIX_RE.sub("", line.strip())
    s = s.strip().strip(":.").strip()
    return re.sub(r"\s+", " ", s).lower()


def _norm(line: str) -> str:
    return re.sub(r"\s+", " ", line.strip()).lower()


def _avg_token_len(words: list[dict[str, Any]]) -> float:
    if not words:
        return 0.0
    return sum(len(w["text"]) for w in words) / len(words)


def _space_ratio(text: str) -> float:
    return text.count(" ") / len(text) if text else 0.0
