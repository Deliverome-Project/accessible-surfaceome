"""Tests for UniProt source registration.

Two failure modes the HER2 baseline run surfaced:

1. The bundle registration (from ``gene_lookup mode='resolve'``) was
   blocking the later summary registration (from ``mode='uniprot_summary'``).
   ``store.has(source_id)`` was true after the bundle call, so the summary
   call's strictly-richer body silently dropped — leaving substring checks
   matching against a thin synthetic body and verbatim UniProt quotes
   failing for no observable reason.

2. The summary body rendered topology features purely as a structured
   catalogue (``transmembrane:654-675 (Helical)``). Agents naturally write
   topology quotes in prose ("transmembrane domain at residues 654-675");
   the structured form never matched.

These tests pin both fixes.
"""

from __future__ import annotations

from accessible_surfaceome.agents.surface_annotator.source_registration import (
    _register_uniprot_from_bundle,
    _register_uniprot_from_summary,
)
from accessible_surfaceome.tools._shared.models import (
    IdentifierBundle,
    SubcellularLocation,
    TopologyFeature,
    UniProtSummary,
)
from accessible_surfaceome.tools._shared.normalize import normalize_for_quote_matching
from accessible_surfaceome.tools._shared.source_text import SourceTextStore


def _bundle() -> IdentifierBundle:
    return IdentifierBundle(
        hgnc_symbol="ERBB2",
        hgnc_id="HGNC:3430",
        approved_name="erb-b2 receptor tyrosine kinase 2",
        aliases=["NEU", "HER-2", "CD340", "HER2"],
        uniprot_acc="P04626",
        ncbi_summary="This gene encodes a member of the EGF receptor family.",
    )


def _summary() -> UniProtSummary:
    return UniProtSummary(
        uniprot_acc="P04626",
        protein_name="Receptor tyrosine-protein kinase erbB-2",
        function_text=(
            "Protein tyrosine kinase that is part of several cell surface "
            "receptor complexes, but that apparently needs a coreceptor for "
            "ligand binding."
        ),
        tissue_specificity_text=(
            "Expressed in a variety of tumor tissues including primary breast "
            "tumors and tumors from small bowel, esophagus, kidney and mouth"
        ),
        subcellular_locations=[
            SubcellularLocation(location="Cell membrane"),
            SubcellularLocation(location="Early endosome"),
        ],
        topology_features=[
            TopologyFeature(
                feature_type="signal_peptide", start=1, end=22, description=None
            ),
            TopologyFeature(
                feature_type="transmembrane",
                start=654,
                end=675,
                description="Helical",
            ),
        ],
    )


def test_bundle_then_summary_replaces_skeleton_body() -> None:
    """The summary's prose body must overwrite the bundle's skeleton body
    when both calls happen in the same session — otherwise verbatim
    quotes against UniProt prose substring-fail against the wrong body."""

    store = SourceTextStore()
    _register_uniprot_from_bundle(_bundle(), store)
    skeleton = store.get("UniProt:P04626")
    assert skeleton is not None
    assert "Function:" not in skeleton.raw_text  # bundle has no function prose

    _register_uniprot_from_summary(_summary(), store)
    rich = store.get("UniProt:P04626")
    assert rich is not None
    # Summary body wins: function prose now in raw_text.
    assert "cell surface receptor complexes" in rich.raw_text
    # And the bundle's NCBI summary was overwritten — the body now reflects
    # the canonical UniProt comment blocks, not the synthesized skeleton.
    assert "EGF receptor family" not in rich.raw_text


def test_summary_then_bundle_does_not_clobber() -> None:
    """Reverse order: if the summary registers first, a later bundle call
    must NOT overwrite the rich body."""

    store = SourceTextStore()
    _register_uniprot_from_summary(_summary(), store)
    _register_uniprot_from_bundle(_bundle(), store)
    rich = store.get("UniProt:P04626")
    assert rich is not None
    assert "cell surface receptor complexes" in rich.raw_text
    assert "EGF receptor family" not in rich.raw_text


def test_summary_body_carries_canonical_uniprot_prose() -> None:
    """Substring check (after normalization) finds the verbatim UniProt
    function and tissue_specificity sentences."""

    store = SourceTextStore()
    _register_uniprot_from_summary(_summary(), store)
    src = store.get("UniProt:P04626")
    assert src is not None
    body = src.normalized_text
    # Canonical UniProt fragments — verbatim quotes against either should
    # land in the body after normalization.
    fn_quote = normalize_for_quote_matching("part of several cell surface receptor complexes")
    tissue_quote = normalize_for_quote_matching(
        "primary breast tumors and tumors from small bowel"
    )
    assert fn_quote in body
    assert tissue_quote in body


def test_summary_renders_topology_in_prose() -> None:
    """Topology features get a prose rendering ("Transmembrane domain at
    residues X-Y") in addition to the structured catalogue, so quotes
    against the natural prose form match."""

    store = SourceTextStore()
    _register_uniprot_from_summary(_summary(), store)
    src = store.get("UniProt:P04626")
    assert src is not None
    body = src.normalized_text
    # Both renderings should be present.
    assert "transmembrane:654-675" in body  # structured form
    assert normalize_for_quote_matching(
        "Transmembrane domain at residues 654-675"
    ) in body  # prose form
    assert normalize_for_quote_matching(
        "Signal peptide at residues 1-22"
    ) in body


def test_put_replace_flag_overrides_existing() -> None:
    """Direct ``SourceTextStore.put`` test: ``replace=True`` overwrites an
    existing entry; ``replace=False`` (default) is a no-op."""

    from datetime import UTC, datetime

    from accessible_surfaceome.tools._shared.source_text import SourceText

    def _src(label: str) -> SourceText:
        return SourceText(
            source_id="UniProt:P04626",
            source_type="uniprot",
            url="https://rest.uniprot.org/uniprotkb/P04626.json",
            title=label,
            raw_text=label,
            normalized_text=label.lower(),
            content_sha256="x",
            normalized_source_sha256="x",
            retrieved_at=datetime.now(UTC),
            publication_type="db_entry",
            is_retracted=False,
            retraction_checked_at=datetime.now(UTC),
        )

    store = SourceTextStore()
    store.put(_src("first"))
    store.put(_src("second"))  # default replace=False — no-op
    got = store.get("UniProt:P04626")
    assert got is not None and got.title == "first"
    store.put(_src("third"), replace=True)
    got = store.get("UniProt:P04626")
    assert got is not None and got.title == "third"
