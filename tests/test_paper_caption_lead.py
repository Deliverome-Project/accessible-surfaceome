"""Tests for the figure-caption lead clause marked by paper/filters/figures.lua.

Why: the print stylesheet used to paint the caption's "Figure N. Title
sentence." lead with ``::first-line``, which colours whatever text
happens to fall on the first rendered LINE. Column width, not grammar,
decided where the accent stopped — so it cut off mid-sentence on one
caption and ran into the body sentence on the next. The filter now
wraps that clause in ``<span class="caption-lead">`` and the CSS paints
the span, making the extent a property of the text rather than of the
layout.

These tests pin the boundary the filter picks for the caption shapes
this manuscript actually uses, plus the abbreviation / decimal cases
that a naive "split on the first full stop" would get wrong.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

pypandoc = pytest.importorskip("pypandoc")

FILTER = Path(__file__).resolve().parents[1] / "paper/filters/figures.lua"

LEAD_RE = re.compile(
    r'<span\s+class="caption-lead">(.*?)</span>', re.S
)


def lead_of(caption: str) -> str | None:
    """Run one caption through the filter; return the marked lead text.

    Returns None when the filter declined to mark the caption (the
    stylesheet's ``::first-line`` fallback then applies).
    """
    html = pypandoc.convert_text(
        f"##### {caption}\n",
        to="html5",
        format="markdown",
        extra_args=[f"--lua-filter={FILTER}"],
    )
    match = LEAD_RE.search(html)
    if match is None:
        return None
    # Strip the <strong> the .docx convention puts inside the span, and
    # collapse pandoc's soft-wrapped newlines back to single spaces.
    text = re.sub(r"</?strong>", "", match.group(1))
    return re.sub(r"\s+", " ", text).strip()


@pytest.mark.parametrize(
    ("caption", "expected"),
    [
        pytest.param(
            "Figure 1. Databases agree on only 188 proteins genome-wide. "
            "Five-way ellipse Venn over each source's native flag.",
            "Figure 1. Databases agree on only 188 proteins genome-wide.",
            id="plain-label-plus-title",
        ),
        pytest.param(
            "**Figure 2. A tool-free agent classifies hard surface "
            "proteins more accurately.** Classification accuracy on "
            "SurfaceBench, 147 proteins.",
            "Figure 2. A tool-free agent classifies hard surface proteins "
            "more accurately.",
            id="author-bolded-lead-is-respected",
        ),
        pytest.param(
            "Supplementary Figure 1. Identifiers drive the within-tier "
            "gains. Bar height is the mean across replicates.",
            "Supplementary Figure 1. Identifiers drive the within-tier "
            "gains.",
            id="supplementary-label",
        ),
        pytest.param(
            "Appendix Figure 2. Title ending in a version number, Sonnet "
            "4.6. The body sentence starts after it.",
            "Appendix Figure 2. Title ending in a version number, Sonnet "
            "4.6.",
            id="decimal-inside-title-is-not-a-break",
        ),
        pytest.param(
            "Figure 4 | Deep-dive flow, e.g. the schematic version. "
            "Panels show the ordering.",
            "Figure 4 | Deep-dive flow, e.g. the schematic version.",
            id="abbreviation-and-pipe-separator",
        ),
        pytest.param(
            "**Figure 6.** Author bolded the label only. The title was "
            "left plain.",
            "Figure 6. Author bolded the label only.",
            id="strong-holding-only-the-label-falls-through",
        ),
        # Word leaves the closing full stop outside the bold run all the
        # time — the manuscript's own Figure 1 does exactly this. Taken
        # literally the accent stops a character early and the body text
        # opens with an orphaned ".".
        pytest.param(
            "**Figure 1. Databases agree on only 188 proteins**. Five-way "
            "Venn diagram over five databases.",
            "Figure 1. Databases agree on only 188 proteins.",
            id="stray-full-stop-outside-the-bold-is-absorbed",
        ),
        pytest.param(
            "**Figure 4. Bold ends before a parenthetical stop**). Body "
            "text follows.",
            "Figure 4. Bold ends before a parenthetical stop).",
            id="stray-bracket-and-stop-are-absorbed-together",
        ),
        pytest.param(
            "**Figure 3. Bold stopped several words early** in the middle "
            "of the title sentence. Body text follows.",
            "Figure 3. Bold stopped several words early in the middle of "
            "the title sentence.",
            id="bold-ending-mid-sentence-runs-on-to-the-sentence-end",
        ),
    ],
)
def test_lead_is_the_label_plus_first_sentence(caption: str, expected: str) -> None:
    assert lead_of(caption) == expected


def test_unresolvable_caption_is_left_for_the_css_fallback() -> None:
    """No label and no sentence end: mark nothing rather than guess.

    The stylesheet keeps a ``::first-line`` rule scoped with
    ``:not(:has(.caption-lead))`` precisely so this case still gets the
    old treatment instead of no treatment.
    """
    assert lead_of("A caption with no label and no terminal punctuation") is None


def test_lead_is_not_nested_when_the_filter_runs_twice() -> None:
    """Idempotent: re-running must not wrap the span in another span."""
    once = pypandoc.convert_text(
        "##### Figure 1. A title. Body text follows.\n",
        to="html5", format="markdown",
        extra_args=[f"--lua-filter={FILTER}"],
    )
    twice = pypandoc.convert_text(
        once, to="html5", format="html",
        extra_args=[f"--lua-filter={FILTER}"],
    )
    assert twice.count('class="caption-lead"') == 1


def test_print_css_scopes_the_first_line_fallback_off_marked_captions() -> None:
    """``::first-line`` is applied as the INNERMOST fictional wrapper, so
    an unscoped rule would repaint the first line over the span and put
    the bug straight back. Pin the guard."""
    css = (Path(__file__).resolve().parents[1]
           / "paper/deliverome-print.css").read_text()
    for selector in re.findall(r"^([^\n{]*::first-line)\s*\{", css, re.M):
        assert ":not(:has(.caption-lead))" in selector, (
            f"unscoped ::first-line rule would override the lead span: {selector}"
        )


# ── The UNLINKED reporter's panel-letter guard ──────────────────────

def _filter_stderr(markdown: str) -> str:
    """Run the filter and return pandoc's stderr (where the report goes)."""
    import subprocess
    proc = subprocess.run(
        [pypandoc.get_pandoc_path(), "-f", "markdown", "-t", "html5",
         f"--lua-filter={FILTER}"],
        input=markdown, capture_output=True, text=True, check=True,
    )
    return proc.stderr


# A caption to anchor "Figure 5" against, plus body prose referencing it.
_CAPTION = "##### Figure 5. Every protein resolves to a tier. Body text.\n\n"


def test_panel_suffixed_reference_is_not_reported_as_unlinked() -> None:
    """"Figure 5a" is declined by linkify on purpose (tail_match wants a
    bare integer), so reporting it accuses the filter of missing what it
    chose not to match. The manuscript has three such panel references
    and they cried wolf on every build."""
    err = _filter_stderr(_CAPTION + "The calls split by tier (Figure 5a), "
                                    "with facets (Figure 5b).\n")
    assert "UNLINKED" not in err, err


def test_a_genuinely_unlinked_reference_is_still_reported() -> None:
    """The guard must not silence the checker wholesale — a bare
    reference with no matching caption still has to surface."""
    err = _filter_stderr("Nothing here matches (Figure 9).\n")
    assert "UNLINKED" in err and "Figure 9" in err, err
