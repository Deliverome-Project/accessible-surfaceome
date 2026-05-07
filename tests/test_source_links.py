"""Tests for ``highlight_url`` URL construction.

Covers the three source-type translations and the URL-encoding pipeline
applied to the quote text.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import HttpUrl

from accessible_surfaceome.tools._shared.models import SourceRef
from accessible_surfaceome.tools._shared.source_links import highlight_url


def _ref(*, source_type, url: str, source_id: str) -> SourceRef:
    return SourceRef(
        source_type=source_type,
        source_id=source_id,
        url=HttpUrl(url),
        title="Test",
        retrieved_at=datetime.now(UTC),
        content_sha256="x",
        publication_type="primary_research",
        is_retracted=False,
        retraction_checked_at=datetime.now(UTC),
    )


def test_uniprot_api_url_translates_to_entry_page() -> None:
    ref = _ref(
        source_type="uniprot",
        url="https://rest.uniprot.org/uniprotkb/P04626.json",
        source_id="UniProt:P04626",
    )
    url = highlight_url(ref, "cell surface receptor complexes")
    assert url.startswith("https://www.uniprot.org/uniprotkb/P04626/entry#:~:text=")
    assert "cell%20surface%20receptor%20complexes" in url


def test_pubmed_url_translates_to_europepmc() -> None:
    """PubMed text fragments are flaky on hyphen / mixed-case quotes — we
    redirect to Europe PMC, which renders the same MEDLINE bytes verbatim
    and handles fragments reliably."""

    ref = _ref(
        source_type="pubmed",
        url="https://pubmed.ncbi.nlm.nih.gov/20443098/",
        source_id="PMID:20443098",
    )
    url = highlight_url(ref, "approved by the EMEA")
    assert url.startswith("https://europepmc.org/article/MED/20443098#:~:text=")
    assert "approved%20by%20the%20EMEA" in url


def test_pmc_url_passes_through_unchanged() -> None:
    """PMC full-text URLs already point at browsable rendered pages — no
    translation needed."""

    ref = _ref(
        source_type="pmc",
        url="https://www.ncbi.nlm.nih.gov/pmc/articles/PMC2195717/",
        source_id="PMC:PMC2195717",
    )
    url = highlight_url(ref, "single-pass type I membrane protein")
    assert url.startswith(
        "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC2195717/#:~:text="
    )


def test_patent_url_passes_through_unchanged() -> None:
    ref = _ref(
        source_type="patent",
        url="https://patents.google.com/patent/WO2024036333A2/en",
        source_id="WO:WO2024036333A2",
    )
    url = highlight_url(ref, "bispecific binding agent")
    assert url.startswith(
        "https://patents.google.com/patent/WO2024036333A2/en#:~:text="
    )


def test_uniprot_topology_quote_uses_section_anchor() -> None:
    """Synthesized topology renderings — both the structured form
    (``transmembrane:653-675``) and the prose form (``Transmembrane domain
    at residues 653-675``) — appear in our cached UniProt body but NOT on
    UniProt's rendered website (which uses a structured table). Linking
    with a text fragment would silently fail to highlight; instead we
    deep-link to the Subcellular Location section anchor so the user lands
    on the right table."""

    ref = _ref(
        source_type="uniprot",
        url="https://rest.uniprot.org/uniprotkb/P04626.json",
        source_id="UniProt:P04626",
    )
    # Prose form (our orchestrator's topology rendering).
    url = highlight_url(ref, "Transmembrane domain at residues 653-675 (Helical)")
    assert url == "https://www.uniprot.org/uniprotkb/P04626/entry#subcellular_location"
    # Structured form (the catalogue we render alongside the prose).
    url2 = highlight_url(ref, "transmembrane:653-675 (Helical)")
    assert url2 == "https://www.uniprot.org/uniprotkb/P04626/entry#subcellular_location"


def test_uniprot_function_quote_still_uses_text_fragment() -> None:
    """Function and tissue quotes ARE on UniProt's rendered page verbatim
    (they're the canonical comment-block prose), so the text fragment
    behavior must NOT regress to the section anchor for them."""

    ref = _ref(
        source_type="uniprot",
        url="https://rest.uniprot.org/uniprotkb/P04626.json",
        source_id="UniProt:P04626",
    )
    url = highlight_url(ref, "part of several cell surface receptor complexes")
    assert "#:~:text=" in url
    assert "subcellular_location" not in url  # not the fallback anchor


def test_quote_special_chars_percent_encoded() -> None:
    """Punctuation in the quote round-trips correctly: parens, commas,
    hyphens, percent signs all need encoding to survive the fragment
    parser."""

    ref = _ref(
        source_type="uniprot",
        url="https://rest.uniprot.org/uniprotkb/P04626.json",
        source_id="UniProt:P04626",
    )
    url = highlight_url(ref, "11.1 % of early (39.1 % metastatic), p95HER2-positive")
    # Each special char survives as percent-encoded in the fragment.
    assert "%20" in url  # spaces
    assert "%25" in url  # percent sign
    assert "%28" in url and "%29" in url  # parens
    assert "%2C" in url  # comma
    # Hyphens are URL-safe and may or may not be encoded — both forms work.
    assert ("-" in url.split("text=")[1]) or ("%2D" in url)
