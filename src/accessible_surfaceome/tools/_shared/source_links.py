"""Construct human-browsable URLs that highlight a verbatim quote on a source page.

Uses the W3C `Text Fragments`_ spec (``#:~:text=...``) — supported in
Chrome/Edge/Safari/Firefox-as-of-2024. The browser scrolls to and yellow-
highlights the first occurrence of the encoded text on the rendered page.

The persisted ``SourceRef.url`` points at the *API* endpoint we fetched
from (``https://rest.uniprot.org/uniprotkb/P04626.json``), which isn't
human-browsable. This module maps each ``source_type`` to the canonical
human-facing page (``/uniprotkb/P04626/entry``) and appends the text
fragment.

.. _Text Fragments: https://wicg.github.io/scroll-to-text-fragment/
"""

from __future__ import annotations

import re
from urllib.parse import quote, urlparse, urlunparse

from .models import EvidenceSpan, SourceRef


_UNIPROT_API_PATH = re.compile(r"^/uniprotkb/(?P<acc>[A-Z0-9]+)\.json$")
_PUBMED_PATH = re.compile(r"^/(?P<pmid>\d+)/?$")

# Patterns that distinguish our orchestrator's synthesized topology
# rendering from UniProt's verbatim comment-block prose. Match either:
#   - structured form: ``transmembrane:653-675`` (feature_type then a
#     colon then a residue range)
#   - prose form: ``Transmembrane domain at residues 653-675`` (one of our
#     prose labels followed by ``at residues``)
_TOPOLOGY_FEATURE_TYPES = (
    "signal_peptide",
    "transmembrane",
    "topological_domain",
    "intramembrane",
    "lipidation",
    "gpi_anchor",
    "glycosylation",
    "disulfide_bond",
)
_SYNTHESIZED_TOPOLOGY_STRUCTURED = re.compile(
    r"\b(?:" + "|".join(_TOPOLOGY_FEATURE_TYPES) + r"):\d+-\d+",
    re.IGNORECASE,
)
_SYNTHESIZED_TOPOLOGY_PROSE = re.compile(
    r"\bat residues\s+\d+-\d+", re.IGNORECASE
)


def highlight_url(source: SourceRef, quote_text: str) -> str:
    """Return a human-browsable URL that highlights ``quote_text`` on the page.

    The result is the canonical entry page URL for the source, plus a
    ``#:~:text=...`` fragment that browsers use to scroll-to-and-highlight
    the first occurrence of the encoded text.

    Quote encoding: the text fragment spec uses percent-encoding within the
    fragment. We URL-quote the text, leaving spaces as ``%20`` (the spec
    permits ``+`` for space too, but ``%20`` is more portable across
    browsers' renderers). Punctuation is encoded as well so quotes
    containing characters like ``,`` or ``;`` round-trip correctly.

    The fragment matches against the rendered DOM, not the API response we
    cached. UniProt's website renders the same prose blocks we register, so
    UniProt-anchored quotes resolve. PubMed pages render the abstract;
    PMC renders full text; Google Patents renders the abstract + claims.

    Special case for UniProt topology quotes: our orchestrator renders
    topology features in two synthesized forms (``transmembrane:653-675
    (Helical)`` and ``Transmembrane domain at residues 653-675 (Helical)``)
    that the agent quotes against, but neither form appears on UniProt's
    rendered website — UniProt shows topology in a structured table.
    Highlighting would silently fail. Instead we return a deep-link to the
    Subcellular Location section anchor so the user lands on the table
    that *does* contain the equivalent feature.
    """

    if source.source_type == "uniprot" and _looks_like_synthesized_topology(quote_text):
        return _uniprot_section_url(source, "subcellular_location")

    base = _human_url(source)
    encoded = quote(quote_text, safe="")
    return f"{base}#:~:text={encoded}"


def highlight_url_for_span(span: EvidenceSpan) -> str:
    """Convenience: pull the source + quote off an :class:`EvidenceSpan`."""

    return highlight_url(span.source, span.quote)


def _human_url(source: SourceRef) -> str:
    """Map an API-endpoint URL to the human-facing entry page.

    UniProt: the cached URL is the JSON API endpoint
    (``rest.uniprot.org/uniprotkb/<acc>.json``); we redirect to the
    rendered entry page (``www.uniprot.org/uniprotkb/<acc>/entry``).

    PubMed: the cached URL is ``pubmed.ncbi.nlm.nih.gov/<pmid>/``, but
    PubMed's rendered DOM has known text-fragment-matching flakiness on
    quotes with hyphens, mixed case, or special characters — even when
    the bytes are present on the page. We prefer Europe PMC
    (``europepmc.org/article/MED/<pmid>``), which is the same MEDLINE
    record (the bytes we cached came from Europe PMC's API) and renders
    the abstract verbatim, with reliable fragment scrolling. Same
    authoritative source, better browser compatibility.

    PMC and Google Patents URLs we cache are already browsable entry
    pages — passed through unchanged.
    """

    raw = str(source.url)
    parsed = urlparse(raw)
    if source.source_type == "uniprot":
        match = _UNIPROT_API_PATH.match(parsed.path)
        if match:
            acc = match.group("acc")
            return f"https://www.uniprot.org/uniprotkb/{acc}/entry"
    if source.source_type == "pubmed" and parsed.netloc == "pubmed.ncbi.nlm.nih.gov":
        match = _PUBMED_PATH.match(parsed.path)
        if match:
            pmid = match.group("pmid")
            return f"https://europepmc.org/article/MED/{pmid}"
    return urlunparse(parsed)


def _looks_like_synthesized_topology(quote_text: str) -> bool:
    """``True`` if the quote is from our orchestrator's synthesized topology
    rendering (and therefore won't appear on UniProt's rendered page)."""

    if _SYNTHESIZED_TOPOLOGY_STRUCTURED.search(quote_text):
        return True
    if _SYNTHESIZED_TOPOLOGY_PROSE.search(quote_text):
        return True
    return False


def _uniprot_section_url(source: SourceRef, section_anchor: str) -> str:
    """Build a UniProt entry-page URL with a section anchor (no text fragment).

    Used as a fallback for UniProt quotes that won't text-fragment-match
    the rendered DOM — the user lands at the right section even though
    nothing is highlighted.
    """

    raw = str(source.url)
    parsed = urlparse(raw)
    match = _UNIPROT_API_PATH.match(parsed.path)
    if match:
        acc = match.group("acc")
        return f"https://www.uniprot.org/uniprotkb/{acc}/entry#{section_anchor}"
    # Fallback: append the anchor to whatever URL we have.
    return f"{urlunparse(parsed)}#{section_anchor}"


__all__ = ["highlight_url", "highlight_url_for_span"]
