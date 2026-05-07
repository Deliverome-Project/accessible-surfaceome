"""Register sources in a :class:`SourceTextStore` from custom-tool returns.

Each tool produces structured returns that include the canonical source body
(e.g. an abstract, a UniProt JSON entry, a patent claims summary). The
orchestrator's promotion step needs to look those bodies up by ``source_id``
to validate the agent's verbatim quotes, so the tool handlers register every
source they touch as a side effect.

This module is the single place that knows how each tool return maps onto
``SourceText`` records. Tool implementations stay focused on the data they
emit to the agent; the registration shim takes care of pulling out source
identifiers, raw text, and metadata.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any

from accessible_surfaceome.tools._shared.models import (
    DBVotePanel,
    IdentifierBundle,
    LiteraturePack,
    MissDiagnosis,
    Paper,
    PatentSummary,
    PublicationType,
    SourceType,
    UniProtSummary,
)
from accessible_surfaceome.tools._shared.normalize import normalize_for_quote_matching
from accessible_surfaceome.tools._shared.source_text import SourceText, SourceTextStore


def register_from_tool_return(
    *,
    tool: str,
    result: Any,
    store: SourceTextStore,
) -> None:
    """Register every source the tool's return touches.

    Dispatches by ``tool`` name + return type. The function is intentionally
    a long ``isinstance`` ladder rather than a polymorphic abstraction —
    each tool return shape is different enough that dedicated branches read
    more cleanly than an over-general ``register(self, store)`` mixin would.
    """

    if tool == "gene_lookup":
        if isinstance(result, IdentifierBundle):
            _register_uniprot_from_bundle(result, store)
        elif isinstance(result, UniProtSummary):
            _register_uniprot_from_summary(result, store)
        elif isinstance(result, (DBVotePanel, MissDiagnosis)):
            _register_uniprot_from_panel(result, store)
        return

    if tool == "gene_literature":
        if isinstance(result, LiteraturePack):
            for paper in result.papers:
                _register_paper(paper, store)
        elif isinstance(result, Paper):
            _register_paper(result, store)
        return

    if tool == "patent_lookup":
        if isinstance(result, PatentSummary):
            _register_patent(result, store)
        return


# ---------------------------------------------------------------------------
# UniProt
# ---------------------------------------------------------------------------


def _register_uniprot_from_bundle(bundle: IdentifierBundle, store: SourceTextStore) -> None:
    """Register the UniProt entry implied by an ``IdentifierBundle``.

    The bundle doesn't carry the raw entry JSON, but the cached body we'd
    re-fetch via ``_uniprot_entry`` would be identical; we synthesize a
    compact textual representation from the bundle's distilled fields so the
    agent can still cite ``"UniProt:Q9UBP8"`` against e.g. an aliases list or
    the NCBI summary text.
    """

    parts: list[str] = [f"UniProt accession: {bundle.uniprot_acc}"]
    if bundle.approved_name:
        parts.append(f"Approved name: {bundle.approved_name}")
    if bundle.aliases:
        parts.append("Aliases: " + ", ".join(bundle.aliases))
    if bundle.previous_symbols:
        parts.append("Previous symbols: " + ", ".join(bundle.previous_symbols))
    if bundle.ncbi_summary:
        parts.append(f"NCBI summary: {bundle.ncbi_summary}")
    raw_text = "\n".join(parts)
    _put_uniprot(
        acc=bundle.uniprot_acc,
        title=bundle.approved_name or bundle.hgnc_symbol,
        raw_text=raw_text,
        store=store,
    )


def _register_uniprot_from_summary(summary: UniProtSummary, store: SourceTextStore) -> None:
    """Register the UniProt entry distilled by ``uniprot_summary``.

    The summary's prose fields (``function_text``, ``tissue_specificity_text``)
    are usually the load-bearing text an agent quotes from when citing a
    UniProt source — those are the bytes the substring check needs to match.

    Body layout is prose-first (Function then Tissue specificity then
    Subcellular locations) so the verbatim UniProt sentences appear contiguous
    — substring matching is more likely to succeed when the agent quotes a
    fragment of one of these comment blocks. Topology features render after
    the prose and use multiple synonymous phrasings ("Transmembrane domain at
    residues X-Y" + "transmembrane region: X-Y") so quotes against either
    common phrasing find a hit.

    Always replaces an existing UniProt body (from an earlier ``resolve``
    call) — the summary is strictly richer.
    """

    parts: list[str] = []
    if summary.protein_name:
        parts.append(f"Protein: {summary.protein_name}")
    if summary.function_text:
        parts.append(f"Function: {summary.function_text}")
    if summary.tissue_specificity_text:
        parts.append(f"Tissue specificity: {summary.tissue_specificity_text}")
    if summary.subcellular_locations:
        loc_lines = "; ".join(loc.location for loc in summary.subcellular_locations)
        parts.append(f"Subcellular locations: {loc_lines}")
    if summary.topology_features:
        # Render topology twice — once as a structured catalogue (the form
        # downstream tooling expects) and once in prose ("transmembrane
        # domain at residues X-Y") so quotes against either phrasing land.
        topo_struct = "; ".join(
            f"{f.feature_type}:{f.start}-{f.end}" + (f" ({f.description})" if f.description else "")
            for f in summary.topology_features
            if f.start is not None and f.end is not None
        )
        if topo_struct:
            parts.append(f"Topology: {topo_struct}")
        topo_prose_lines: list[str] = []
        for f in summary.topology_features:
            if f.start is None or f.end is None:
                continue
            label = _topology_prose_label(f.feature_type)
            descr = f" ({f.description})" if f.description else ""
            topo_prose_lines.append(
                f"{label} at residues {f.start}-{f.end}{descr}"
            )
        if topo_prose_lines:
            parts.append("Topology features: " + "; ".join(topo_prose_lines) + ".")
    raw_text = "\n".join(parts)
    _put_uniprot(
        acc=summary.uniprot_acc,
        title=summary.protein_name,
        raw_text=raw_text,
        store=store,
        replace=True,
    )


def _topology_prose_label(feature_type: str) -> str:
    """Human-prose label for a UniProt topology feature type.

    Maps ``"transmembrane"`` → ``"Transmembrane domain"`` etc. — the labels
    the agent is most likely to use in a verbatim quote against the UniProt
    body.
    """

    return {
        "signal_peptide": "Signal peptide",
        "transmembrane": "Transmembrane domain",
        "topological_domain": "Topological domain",
        "intramembrane": "Intramembrane region",
        "lipidation": "Lipidation site",
        "gpi_anchor": "GPI anchor",
        "glycosylation": "Glycosylation site",
        "disulfide_bond": "Disulfide bond",
    }.get(feature_type, feature_type.replace("_", " ").title())


def _register_uniprot_from_panel(
    panel: DBVotePanel | MissDiagnosis, store: SourceTextStore
) -> None:
    """Register a minimal UniProt source stub from db_panel / miss_diagnosis.

    These tools return per-source vote tables, not UniProt prose. The agent
    is unlikely to cite ``"UniProt:Q..."`` against a panel result, but
    registering a stub with the available metadata still lets the search
    log pick up the consultation; the substring check will fail loudly if
    the agent does try to anchor a quote here.
    """

    if isinstance(panel, MissDiagnosis):
        raw_text = panel.summary
        title = panel.hgnc_symbol or None
    else:
        raw_text = (
            f"db_panel for {panel.uniprot_acc} ({panel.hgnc_symbol}); "
            f"n_sources_voting_surface={panel.n_sources_voting_surface}; "
            f"in_db_union={panel.in_db_union}; in_patent_handles={panel.in_patent_handles}"
        )
        title = panel.hgnc_symbol or None
    _put_uniprot(acc=panel.uniprot_acc, title=title, raw_text=raw_text, store=store)


def _put_uniprot(
    *, acc: str, title: str | None, raw_text: str, store: SourceTextStore, replace: bool = False
) -> None:
    """Register a UniProt source body.

    ``replace=False`` (default) is first-write-wins — used by the bundle
    and panel registrations, which produce skeleton bodies that should not
    overwrite anything richer that may have arrived from a parallel
    summary call.

    ``replace=True`` is used by the summary registration; the summary's
    body (function_text + tissue_specificity_text + subcellular_locations
    + topology features) is strictly richer than the bundle's, so the
    summary always wins.
    """

    source_id = f"UniProt:{acc}"
    if not replace and store.has(source_id):
        return
    store.put(
        _make_source_text(
            source_id=source_id,
            source_type="uniprot",
            url=f"https://rest.uniprot.org/uniprotkb/{acc}.json",
            title=title,
            raw_text=raw_text,
            publication_type="db_entry",
            is_retracted=False,
        ),
        replace=replace,
    )


# ---------------------------------------------------------------------------
# Literature (PubMed / PMC)
# ---------------------------------------------------------------------------


def _register_paper(paper: Paper, store: SourceTextStore) -> None:
    """Register a literature record under both ``PMID:`` and (if available)
    ``PMC:`` source_ids.

    The PMID source_id always carries the abstract; the PMC source_id (when
    we have full text) carries the concatenated section text. Two distinct
    source_ids because they correspond to different bodies — an agent
    quoting from full text needs the PMC body, an agent quoting from the
    abstract is fine with the PMID body.
    """

    pmid_id = f"PMID:{paper.pmid}"
    if not store.has(pmid_id) and paper.abstract:
        store.put(_make_source_text(
            source_id=pmid_id,
            source_type="pubmed",
            url=f"https://pubmed.ncbi.nlm.nih.gov/{paper.pmid}/",
            title=paper.title,
            raw_text=paper.abstract,
            publication_type=paper.publication_type,
            is_retracted=paper.is_retracted,
            retraction_checked_at=paper.retraction_checked_at,
            authors=tuple(paper.authors),
            year=paper.year,
            journal=paper.journal,
        ))

    if paper.pmc_id and paper.sections:
        pmc_id = f"PMC:{paper.pmc_id}"
        if not store.has(pmc_id):
            full_text = "\n\n".join(f"{s.name.upper()}\n{s.text}" for s in paper.sections)
            store.put(_make_source_text(
                source_id=pmc_id,
                source_type="pmc",
                url=f"https://www.ncbi.nlm.nih.gov/pmc/articles/{paper.pmc_id}/",
                title=paper.title,
                raw_text=full_text,
                publication_type=paper.publication_type,
                is_retracted=paper.is_retracted,
                retraction_checked_at=paper.retraction_checked_at,
                authors=tuple(paper.authors),
                year=paper.year,
                journal=paper.journal,
            ))


# ---------------------------------------------------------------------------
# Patents
# ---------------------------------------------------------------------------


def _register_patent(patent: PatentSummary, store: SourceTextStore) -> None:
    source_id = f"WO:{patent.wo_number}"
    if store.has(source_id):
        return
    raw_parts: list[str] = []
    if patent.title:
        raw_parts.append(f"Title: {patent.title}")
    if patent.applicant:
        raw_parts.append(f"Applicant: {patent.applicant}")
    raw_parts.append(f"Claims summary: {patent.claims_summary}")
    raw_text = "\n".join(raw_parts)
    store.put(_make_source_text(
        source_id=source_id,
        source_type="patent",
        url=f"https://patents.google.com/patent/{patent.wo_number}/en",
        title=patent.title,
        raw_text=raw_text,
        publication_type="other",
        is_retracted=False,
    ))


# ---------------------------------------------------------------------------
# Construction helper
# ---------------------------------------------------------------------------


def _make_source_text(
    *,
    source_id: str,
    source_type: SourceType,
    url: str,
    title: str | None,
    raw_text: str,
    publication_type: PublicationType,
    is_retracted: bool,
    retraction_checked_at: datetime | None = None,
    authors: tuple[str, ...] = (),
    year: int | None = None,
    journal: str | None = None,
) -> SourceText:
    now = datetime.now(UTC)
    normalized = normalize_for_quote_matching(raw_text)
    return SourceText(
        source_id=source_id,
        source_type=source_type,
        url=url,
        title=title,
        raw_text=raw_text,
        normalized_text=normalized,
        content_sha256=_sha256(raw_text),
        normalized_source_sha256=_sha256(normalized),
        retrieved_at=now,
        publication_type=publication_type,
        is_retracted=is_retracted,
        retraction_checked_at=retraction_checked_at or now,
        license="unknown",
        authors=authors,
        year=year,
        journal=journal,
    )


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


__all__ = ["register_from_tool_return"]
