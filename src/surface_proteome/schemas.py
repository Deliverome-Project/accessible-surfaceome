"""Shared schema definitions for the surface-proteome annotation pipeline."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SourceRef(BaseModel):
    """Reference to a source record used as evidence."""

    source_type: str
    source_id: str
    title: str | None = None
    url: str | None = None
    retrieved_at_utc: str | None = None
    content_sha256: str | None = None


class EvidenceSpan(BaseModel):
    """Quoted span supporting a structured evidence claim."""

    source: SourceRef
    quote: str
    start_offset: int | None = None
    end_offset: int | None = None


class Evidence(BaseModel):
    """Structured evidence item emitted by retrieval or extraction."""

    source: SourceRef
    evidence_type: str
    claim: str
    spans: list[EvidenceSpan] = Field(default_factory=list)
    species: str | None = None
    cell_type: str | None = None
    isoform: str | None = None
    assay_context: str | None = None


class GeneAnnotation(BaseModel):
    """Per-gene surface-status and topology annotation."""

    gene_symbol: str
    uniprot_primary: str
    surface_status: str
    topology: str
    evidence: list[Evidence] = Field(default_factory=list)
    isoform_flattened: bool = False
