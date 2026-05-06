"""Text-normalization helpers for substring-based quote validation.

The orchestrator promotes ``EvidenceClaim`` → ``Evidence`` by checking that the
agent's verbatim ``quote`` appears as a substring of the cached source body.
Real-world papers and abstracts mix Greek letters with their ASCII spellings,
encode HTML entities, and have inconsistent whitespace; the agent's quote may
not match byte-for-byte even when the citation is correct. We normalize both
sides through the same pipeline so the substring check can stay simple.

The pipeline (idempotent):

1. Unicode NFKC — collapses width and compatibility forms.
2. HTML entity decode — ``&amp;`` / ``&#x2014;`` → their characters.
3. Greek transliteration — every Greek glyph rewrites to its ASCII spelling
   (α → "alpha", β → "beta", …). Because the ASCII spelling is unaffected by
   this step, both ``"α-helix"`` and ``"alpha-helix"`` normalize to the same
   canonical string. That handles bidirectional Greek/ASCII mismatches without
   needing two separate passes.
4. Whitespace collapse — runs of ``\\s+`` → single space, then strip.
5. Lowercase — case-insensitive matching.

Greek letters covered: α β γ δ ε κ λ μ π σ τ ω. These are the ones that show up
in biology papers (chemistry papers also use ζ η θ ι ν ξ ο ρ υ φ χ ψ; we'll
expand the table when a quote-match failure surfaces a missing letter).

The normalization is one-way for matching only — we never reconstruct the
original text from the normalized form. We do persist the
``normalized_source_sha256`` so anyone can re-derive the same normalized body
and verify the recorded ``char_offset``.
"""

from __future__ import annotations

import html
import re
import unicodedata


# Greek letters that appear in biology / pharmacology prose. Both directions:
# the normalizer rewrites Greek glyphs to a canonical ASCII spelling, so a
# quote with "α" matches a source with "alpha" and vice versa.
_GREEK_TO_ASCII: dict[str, str] = {
    "α": "alpha",
    "β": "beta",
    "γ": "gamma",
    "δ": "delta",
    "ε": "epsilon",
    "κ": "kappa",
    "λ": "lambda",
    "μ": "mu",
    "π": "pi",
    "σ": "sigma",
    "τ": "tau",
    "ω": "omega",
}

_WHITESPACE_RE = re.compile(r"\s+")


def normalize_for_quote_matching(text: str) -> str:
    """Normalize text for substring-based quote validation.

    Idempotent: ``f(f(x)) == f(x)``. Returns a canonical form that collapses
    Greek/ASCII Greek letter mismatches, HTML entity escapes, and whitespace
    quirks. Lowercased so substring matching is case-insensitive (case
    sensitivity is rarely load-bearing in the prose we cite).

    The normalization is for *matching* only; the original raw_text and
    its sha256 are still preserved separately so the persisted
    ``content_sha256`` anchors the actual fetched bytes.
    """

    if not text:
        return ""
    # 1. Unicode NFKC — collapses width / compatibility forms (e.g. full-width
    #    digits → ASCII, ligatures → component letters).
    out = unicodedata.normalize("NFKC", text)
    # 2. HTML entity decode — Europe PMC abstracts retain &amp;, &lt;, etc.
    out = html.unescape(out)
    # 3. Lowercase — chemistry names sometimes lose info (PD-L1 vs pd-l1) but
    #    biology prose almost never does. Lowercase first so the Greek
    #    word-boundary regex doesn't have to be case-insensitive.
    out = out.lower()
    # 4. Greek transliteration → canonical ASCII form. Both directions: rewrite
    #    glyphs to ASCII spellings, so "α-helix" and "alpha-helix" produce the
    #    same normalized output. The function is idempotent because after one
    #    pass every Greek expression sits in the ASCII form; subsequent passes
    #    are no-ops.
    out = _expand_greek_glyphs(out)
    # 5. Whitespace — runs collapse to single space, then strip.
    out = _WHITESPACE_RE.sub(" ", out).strip()
    return out


def find_quote_in_normalized(normalized_quote: str, normalized_source: str) -> int | None:
    """Return the char offset of ``normalized_quote`` in ``normalized_source``,
    or ``None`` if it doesn't appear.

    Plain substring search. Pre-condition: both inputs come from the same
    ``normalize_for_quote_matching`` pipeline; otherwise the match rate
    collapses.
    """

    if not normalized_quote:
        return None
    idx = normalized_source.find(normalized_quote)
    return idx if idx >= 0 else None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _expand_greek_glyphs(text: str) -> str:
    """Replace every Greek glyph with its ASCII spelling."""

    if not any(g in text for g in _GREEK_TO_ASCII):
        return text
    out = text
    for glyph, ascii_form in _GREEK_TO_ASCII.items():
        if glyph in out:
            out = out.replace(glyph, ascii_form)
    return out


__all__ = ["normalize_for_quote_matching", "find_quote_in_normalized"]
