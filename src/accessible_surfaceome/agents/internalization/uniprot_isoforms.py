"""Fetch per-isoform amino-acid sequences + a canonical-topology summary.

No repo helper returns per-isoform sequences, so we combine:
  * ``uniprot_summary`` — topology features + isoform metadata (ids, canonical flag)
  * ``fetch_uniprot_fasta(isoform_id)`` — the isoform's sequence (the FASTA
    endpoint accepts isoform-suffixed accessions like ``P00533-2``)
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

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


def fetch_isoform_context(uniprot_acc: str, *, http: CachedHTTP) -> list[IsoformContext]:
    summary = uniprot_summary(uniprot_acc, http=http)
    topo = summarize_topology(summary.topology_features)

    records: list[IsoformRecord] = list(summary.isoforms) or [
        IsoformRecord(isoform_id=uniprot_acc, is_canonical=True, length_aa=None)
    ]

    out: list[IsoformContext] = []
    for iso in records:
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
                topology_summary=topo,
            )
        )
    return out
