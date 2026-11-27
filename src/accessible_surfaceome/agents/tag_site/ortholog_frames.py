"""Cached mouse/rat ortholog frame & UniProt metadata lookup for tag-site runs.

Ion channels, transporters, and multipass receptors in L1 are frequently tagged
in rat or mouse cDNAs (e.g. ``"of the rat KCC2b"`` on SLC12A5). ``frames.py``
already supports ``ortholog:<species>:<acc>`` frames (family ``"ortholog"``),
but ``compara_ortholog.ortholog_uniprot_acc`` is NULL in D1 so those frames
were previously unreachable. Querying UniProt's reviewed mouse/rat entries
through ``CachedHTTP`` (30-day TTL) supplies deterministic, auditable ortholog
frames for both clip boosting and position-claim verification.
"""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import quote

from accessible_surfaceome.tools._shared.http import CachedHTTP

from .frames import Frame

logger = logging.getLogger(__name__)

_UNIPROT_BASE = "https://rest.uniprot.org/uniprotkb"
_TAXON_SPECIES = {10090: "mouse", 10116: "rat"}


def _signal_peptide_end(entry: dict[str, Any]) -> int:
    for f in entry.get("features") or []:
        if f.get("type") != "Signal":
            continue
        end = ((f.get("location") or {}).get("end") or {}).get("value")
        if isinstance(end, int):
            return end
    return 0


def fetch_uniprot_names_cached(
    acc: str, *, http: CachedHTTP
) -> tuple[str, list[str], int]:
    """Cached ``(protein_name, alias_candidates, signal_peptide_end)`` from
    UniProtKB JSON via ``CachedHTTP`` (30-day TTL)."""
    data = http.get_json(
        f"{_UNIPROT_BASE}/{acc}.json",
        source="uniprot_entry",
        ttl_days=30,
    )
    if not isinstance(data, dict):
        return acc, [], 0
    pd = data.get("proteinDescription") or {}
    rn = pd.get("recommendedName") or {}
    protein_name = (rn.get("fullName") or {}).get("value")

    cands: list[str] = []
    cands += [s.get("value") for s in rn.get("shortNames") or [] if isinstance(s, dict)]
    for a in pd.get("alternativeNames") or []:
        if not isinstance(a, dict):
            continue
        fn = (a.get("fullName") or {}).get("value")
        if fn:
            cands.append(fn)
        cands += [s.get("value") for s in a.get("shortNames") or [] if isinstance(s, dict)]
    cands += [c.get("value") for c in pd.get("cdAntigenNames") or [] if isinstance(c, dict)]

    if not protein_name:
        for s in pd.get("submissionNames") or []:
            if isinstance(s, dict):
                fn = (s.get("fullName") or {}).get("value")
                if fn:
                    protein_name = fn
                    break
    if not protein_name:
        protein_name = acc

    for g in data.get("genes") or []:
        if isinstance(g, dict):
            cands += [s.get("value") for s in g.get("synonyms") or [] if isinstance(s, dict)]

    return str(protein_name), [str(c) for c in cands if c], _signal_peptide_end(data)


def build_aliases(
    gene_symbol: str, protein_name: str, candidates: list[str]
) -> list[str]:
    """Deduped ``[protein_name, *candidates]`` excluding ``gene_symbol``."""
    seen: set[str] = set()
    out: list[str] = []
    for x in [protein_name, *candidates]:
        if not x:
            continue
        k = x.strip()
        if not k or k.upper() == gene_symbol.upper():
            continue
        if k.lower() in seen:
            continue
        seen.add(k.lower())
        out.append(k)
    return out


def fetch_rodent_ortholog_frames(
    gene_symbol: str,
    *,
    http: CachedHTTP,
    exclude_sequences: set[str] | None = None,
) -> list[Frame]:
    """Return reviewed mouse and rat UniProt ortholog :class:`Frame` objects for
    ``gene_symbol`` (via ``CachedHTTP``, best-effort — never fails a run)."""
    if not gene_symbol or not isinstance(http, CachedHTTP):
        return []
    excluded = set(exclude_sequences or ())
    q = quote(
        f"gene_exact:{gene_symbol} AND (organism_id:10090 OR organism_id:10116) AND reviewed:true"
    )
    url = f"{_UNIPROT_BASE}/search?query={q}&format=json&size=4"
    try:
        payload = http.get_json(url, source="uniprot_ortholog_search", ttl_days=30)
    except Exception as exc:  # noqa: BLE001
        logger.debug("rodent ortholog lookup failed for %s: %s", gene_symbol, exc)
        return []
    if not isinstance(payload, dict):
        return []

    frames: list[Frame] = []
    seen_labels: set[str] = set()
    for entry in payload.get("results") or []:
        if not isinstance(entry, dict):
            continue
        acc = str(entry.get("primaryAccession") or "").strip()
        taxon = (entry.get("organism") or {}).get("taxonId")
        species = _TAXON_SPECIES.get(int(taxon)) if isinstance(taxon, int) else None
        seq = str(((entry.get("sequence") or {}).get("value")) or "").strip()
        if not acc or not species or not seq or seq in excluded:
            continue
        label = f"ortholog:{species}:{acc}"
        if label not in seen_labels:
            seen_labels.add(label)
            frames.append(Frame(label=label, sequence=seq, offset=None))
        sp_end = _signal_peptide_end(entry)
        if sp_end and sp_end < len(seq):
            mature_seq = seq[sp_end:]
            mlabel = f"ortholog:{species}:{acc}:mature"
            if mature_seq not in excluded and mlabel not in seen_labels:
                seen_labels.add(mlabel)
                frames.append(Frame(label=mlabel, sequence=mature_seq, offset=None))
    return frames
