"""Fetch per-isoform amino-acid sequences + an E/C topology summary.

Topology is sourced DeepTMHMM-first (its inside/outside per-residue call is the
signal the model-prior grade needs — endocytic motifs only function in
cytoplasmic regions). When a protein/isoform has a DeepTMHMM prediction we use
its record's own sequence + topology (guaranteed residue-aligned); otherwise we
fall back to the UniProt FASTA sequence + UniProt topology features:
  * ``deeptmhmm_record`` — precomputed DeepTMHMM E/C topology + sequence
  * ``uniprot_summary`` — topology features + isoform metadata (ids, canonical flag)
  * ``fetch_uniprot_fasta(isoform_id)`` — the isoform's sequence (the FASTA
    endpoint accepts isoform-suffixed accessions like ``P00533-2``)
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from accessible_surfaceome.agents.internalization.deeptmhmm_topology import (
    deeptmhmm_record,
    summarize_deeptmhmm_topology,
)
from accessible_surfaceome.agents.internalization.topology import summarize_topology
from accessible_surfaceome.sources.deeptmhmm import fetch_uniprot_fasta
from accessible_surfaceome.tools._shared.http import CachedHTTP
from accessible_surfaceome.tools._shared.models import IsoformRecord
from accessible_surfaceome.tools.gene_lookup import uniprot_summary

_FASTA_TIMEOUT = 30
_FASTA_RETRIES = 3
_FASTA_INTERVAL_MS = 350


class IsoformContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    isoform_id: str
    is_canonical: bool
    length_aa: int | None
    sequence: str
    topology_summary: str
    topology_source: str = "uniprot"


def fetch_isoform_context(
    uniprot_acc: str, *, http: CachedHTTP, canonical_only: bool = False
) -> list[IsoformContext]:
    summary = uniprot_summary(uniprot_acc, http=http)
    uniprot_topo = summarize_topology(summary.topology_features)

    records: list[IsoformRecord] = list(summary.isoforms) or [
        IsoformRecord(isoform_id=uniprot_acc, is_canonical=True, length_aa=None)
    ]
    if canonical_only:
        # Grade only the canonical isoform (keeps the input prompt small for a
        # cohort-scale sweep); fetch nothing for the alternatives.
        records = [r for r in records if r.is_canonical] or records[:1]

    out: list[IsoformContext] = []
    for iso in records:
        dt = deeptmhmm_record(iso.isoform_id, is_canonical=iso.is_canonical)
        if dt is not None:
            # DeepTMHMM E/C topology paired with its own residue-aligned sequence.
            out.append(
                IsoformContext(
                    isoform_id=iso.isoform_id,
                    is_canonical=iso.is_canonical,
                    length_aa=iso.length_aa or len(dt["sequence"]),
                    sequence=dt["sequence"],
                    topology_summary=summarize_deeptmhmm_topology(dt),
                    topology_source="deeptmhmm",
                )
            )
        else:
            # No DeepTMHMM prediction — fall back to UniProt FASTA + features.
            fasta = fetch_uniprot_fasta(
                iso.isoform_id,
                timeout=_FASTA_TIMEOUT,
                retry_max_attempts=_FASTA_RETRIES,
                min_request_interval_ms=_FASTA_INTERVAL_MS,
            )
            out.append(
                IsoformContext(
                    isoform_id=iso.isoform_id,
                    is_canonical=iso.is_canonical,
                    length_aa=iso.length_aa or len(fasta.sequence),
                    sequence=fasta.sequence,
                    topology_summary=uniprot_topo,
                    topology_source="uniprot",
                )
            )
    return out
