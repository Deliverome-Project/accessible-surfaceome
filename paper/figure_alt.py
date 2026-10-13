"""Give every figure image alt text taken from its own legend.

Pandoc carries no alt text out of the .docx, so 22 of this paper's 27
images had no ``alt`` attribute at all — not empty, absent. A screen
reader announces nothing for almost every figure in both the PDF and
the web edition.

The legend's lead sentence is the right source: it is the one-line
statement of what the figure shows, it is already written and
copy-edited, and it is what a sighted reader takes from the figure at a
glance. Using it also means the alt text cannot drift from the caption.

An image that already carries alt text keeps it — the brand marks in
the title band (bioRxiv, Zenodo) set their own, and those are better
than anything derivable here.
"""
from __future__ import annotations

import re
from typing import Any

# "Figure 3. The triage agent rescues 1,108 candidates." — the lead is
# the label plus the first sentence, which is what figures.lua already
# marks up as `.caption-lead`.
LEAD = re.compile(
    r"^((?:Supplementary |Appendix )?(?:Figure|Table)\s+S?\d+[.:]?\s+.*?[.!?])(?:\s|$)"
)

# Long enough to be unhelpful read aloud, and a screen reader cannot
# skim. The full legend is adjacent in the document for anyone who
# wants it.
MAX_ALT = 300


def _caption_lead(caption: Any) -> str:
    lead_el = caption.xpath(
        ".//*[contains(concat(' ', @class, ' '), ' caption-lead ')]"
    )
    if lead_el:
        text = " ".join(lead_el[0].text_content().split())
    else:
        # The caption-lead span is absent when figures.lua could not
        # resolve the lead clause; fall back to the caption's own first
        # sentence rather than giving up on alt text entirely.
        whole = " ".join(caption.text_content().split())
        m = LEAD.match(whole)
        text = m.group(1) if m else whole
    if len(text) > MAX_ALT:
        text = text[: MAX_ALT - 1].rsplit(" ", 1)[0] + "…"
    return text


def add_figure_alt_text(root: Any) -> int:
    """Set alt text on figure images that lack it. Returns the count."""
    done = 0
    for block in root.xpath(
        "//*[contains(concat(' ', @class, ' '), ' figure-block ')]"
    ):
        captions = block.xpath(".//h5")
        if not captions:
            continue
        alt = _caption_lead(captions[0])
        if not alt:
            continue
        for img in block.xpath(".//img"):
            if (img.get("alt") or "").strip():
                continue
            img.set("alt", alt)
            done += 1
    return done
