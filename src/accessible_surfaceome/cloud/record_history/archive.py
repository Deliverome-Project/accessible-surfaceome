"""Archive what the public API served for one gene, if it changed.

This is the ONLY code that writes record-history revisions (publish,
sweep, and backfills all call it), so dedup and numbering live in one
place. It reads the Worker with the ``X-Archive-Bypass`` secret so the
bytes are the current D1 state + today's enrichment, not a cached copy.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

import httpx

from accessible_surfaceome.cloud.d1_client import D1Error
from accessible_surfaceome.cloud.record_history.hashing import (
    content_hash_evidence,
    content_hash_md,
    content_hash_record,
)
from accessible_surfaceome.cloud.record_history.store import (
    ArchiveError,
    RevisionStore,
    blob_key,
)

logger = logging.getLogger(__name__)

PUBLIC_API_BASE = "https://api.deliverome.org/surfaceome"
BYPASS_HEADER = "X-Archive-Bypass"


@dataclass(frozen=True)
class Served:
    record_bytes: bytes
    record: dict[str, Any]
    evidence_bytes: bytes | None
    evidence: dict[str, Any] | None
    md_bytes: bytes | None


@dataclass(frozen=True)
class ArchiveResult:
    gene_symbol: str
    status: Literal["created", "unchanged", "not_annotated"]
    revision: int | None


def _get(http: httpx.Client, url: str, token: str) -> httpx.Response | None:
    resp = http.get(url, headers={BYPASS_HEADER: token})
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp


def fetch_served(
    symbol: str, *, http: httpx.Client, token: str, base: str = PUBLIC_API_BASE
) -> Served | None:
    """The three parts the API serves for ``symbol``; ``None`` if not annotated."""
    rec = _get(http, f"{base}/v1/genes/{symbol}", token)
    if rec is None:
        return None
    ev = _get(http, f"{base}/v1/genes/{symbol}/evidence", token)
    md = _get(http, f"{base}/v1/genes/{symbol}.md", token)
    return Served(
        record_bytes=rec.content,
        record=rec.json(),
        evidence_bytes=ev.content if ev else None,
        evidence=ev.json() if ev else None,
        md_bytes=md.content if md else None,
    )


def archive_gene(
    symbol: str,
    *,
    source: Literal["publish", "sweep"],
    http: httpx.Client,
    store: RevisionStore,
    token: str,
    base: str = PUBLIC_API_BASE,
    purge: Callable[[list[str]], object] | None = None,
) -> ArchiveResult:
    if not token:
        raise ArchiveError(
            "ARCHIVE_BYPASS_TOKEN is unset — refusing to archive cached responses"
        )
    served = fetch_served(symbol, http=http, token=token, base=base)
    if served is None:
        return ArchiveResult(symbol, "not_annotated", None)

    rec = served.record
    gene = rec.get("gene") or {}
    sym = gene.get("hgnc_symbol") or symbol
    json_hash = content_hash_record(rec)
    evidence_hash = (
        content_hash_evidence(served.evidence) if served.evidence is not None else None
    )
    md_hash = (
        content_hash_md(served.md_bytes.decode("utf-8"))
        if served.md_bytes is not None
        else None
    )

    latest = store.latest(sym)
    if latest and (latest.json_hash, latest.evidence_hash, latest.md_hash) == (
        json_hash,
        evidence_hash,
        md_hash,
    ):
        return ArchiveResult(sym, "unchanged", latest.revision)

    store.put_blob(blob_key(json_hash, "json"), served.record_bytes, "application/json")
    if evidence_hash and served.evidence_bytes is not None:
        store.put_blob(
            blob_key(evidence_hash, "json"), served.evidence_bytes, "application/json"
        )
    if md_hash and served.md_bytes is not None:
        store.put_blob(
            blob_key(md_hash, "md"), served.md_bytes, "text/markdown; charset=utf-8"
        )

    params: list[object] = [
        sym,
        gene.get("hgnc_id"),
        json_hash,
        evidence_hash,
        md_hash,
        datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        source,
        rec.get("schema_version"),
        rec.get("prompt_corpus_version"),
    ]
    try:
        revision = store.insert_revision(params)
    except D1Error as exc:
        # Two archivers raced to the same MAX(revision)+1; the PK rejected
        # one. Retrying re-reads MAX and re-checks "unchanged".
        if "UNIQUE" not in str(exc):
            raise
        revision = store.insert_revision(params)

    if revision is None:
        latest = store.latest(sym)
        return ArchiveResult(sym, "unchanged", latest.revision if latest else None)
    if purge is not None:
        purge([f"/v1/genes/{sym}/revisions", "/v1/releases"])
    logger.info("archived %s revision %d (%s)", sym, revision, source)
    return ArchiveResult(sym, "created", revision)
