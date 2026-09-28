"""Archive what the public API served for one gene, if it changed.

This is the ONLY code that writes record-history revisions (publish,
sweep, and backfills all call it), so dedup and numbering live in one
place. It reads the Worker with the ``X-Archive-Bypass`` secret so the
bytes are the current D1 state + today's enrichment, not a cached copy,
and refuses to proceed unless the Worker echoes back
``X-Archive-Bypass-Honored: 1`` confirming the secret actually matched
(an old Worker or a wrong token would otherwise look like a quiet,
possibly-cached success).
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
BYPASS_HONORED_HEADER = "X-Archive-Bypass-Honored"

# Set by the Worker (cloudflare/workers/surfaceome_api/src/index.js, the
# DEGRADED_HEADER constant next to `json()`) on an otherwise-200 response
# whose serve-time enrichment hit a real D1 error — i.e. NOT the persistent
# "no such table" deploy-order case, which the Worker keeps silent. A
# degraded response's fields are null where D1 actually has data (this is
# exactly what shipped S100A7A revision 3 with a null canonical_topology
# despite the topology_public row existing), so it must never be archived as
# if it were the record's real content. The Worker also forces
# ``Cache-Control: no-store`` on the same response, so a retry a moment
# later — after the transient D1 error clears — sees fresh, non-degraded
# bytes rather than a cached copy of the failure.
DEGRADED_HEADER = "X-Surfaceome-Degraded"


@dataclass(frozen=True)
class Served:
    gene_symbol: str
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


def _get(http: httpx.Client, url: str, token: str) -> httpx.Response:
    return http.get(url, headers={BYPASS_HEADER: token})


def _safe_json(resp: httpx.Response) -> Any:
    try:
        return resp.json()
    except ValueError:
        return None


def _matches_404_reason(resp: httpx.Response, expected_error: str) -> bool:
    body = _safe_json(resp)
    return isinstance(body, dict) and body.get("error") == expected_error


def _reject_degraded(resp: httpx.Response, symbol: str) -> None:
    """Refuse to treat a serve-time-enrichment-degraded response as archivable.

    See ``DEGRADED_HEADER``'s docstring for why: the response's fields can be
    null where D1 actually has data, so archiving it would write that gap in
    permanently instead of leaving it to self-heal on the next sweep pass.
    """
    labels = resp.headers.get(DEGRADED_HEADER)
    if labels:
        raise ArchiveError(
            f"degraded response for {symbol} ({labels}) — not archiving; retry later"
        )


def _fetch_record(http: httpx.Client, url: str, token: str, *, symbol: str) -> httpx.Response | None:
    """The record route: also enforces the bypass-honoured contract.

    Any non-404 error status raises before we ever look at the honoured
    header, so a plain 5xx from a broken/unreachable Worker still surfaces
    as ``httpx.HTTPStatusError`` rather than being mistaken for an
    un-honoured bypass.
    """
    resp = _get(http, url, token)
    if resp.status_code != 404:
        resp.raise_for_status()
    if resp.headers.get(BYPASS_HONORED_HEADER) != "1":
        raise ArchiveError(
            "archive bypass not honoured — wrong ARCHIVE_BYPASS_TOKEN or old Worker; "
            "refusing to archive possibly-cached bytes"
        )
    _reject_degraded(resp, symbol)
    if resp.status_code == 404:
        if _matches_404_reason(resp, "gene_not_annotated"):
            return None
        raise ArchiveError(
            "unexpected 404 from record route "
            f"(expected error='gene_not_annotated'): {resp.text!r}"
        )
    return resp


def _fetch_optional(
    http: httpx.Client,
    url: str,
    token: str,
    *,
    expected_404_error: str,
    route: str,
    symbol: str,
) -> httpx.Response | None:
    """A route the API may 404 for a known reason; any other status either
    passes through (2xx) or raises (5xx / unexpected 4xx)."""
    resp = _get(http, url, token)
    if resp.status_code == 404:
        if _matches_404_reason(resp, expected_404_error):
            return None
        raise ArchiveError(
            f"unexpected 404 from {route} route "
            f"(expected error={expected_404_error!r}): {resp.text!r}"
        )
    resp.raise_for_status()
    _reject_degraded(resp, symbol)
    return resp


def fetch_served(
    symbol: str, *, http: httpx.Client, token: str, base: str = PUBLIC_API_BASE
) -> Served | None:
    """The three parts the API serves for ``symbol``; ``None`` if not annotated.

    The record fetch uses the caller's ``symbol`` as given; the evidence
    and Markdown fetches use the *canonical* ``gene.hgnc_symbol`` the
    record itself reports, since the Markdown route is matched exactly
    against its R2 key and a caller-supplied casing (e.g. ``egfr``) would
    silently 404 there even though the record route resolved fine.
    """
    rec_resp = _fetch_record(http, f"{base}/v1/genes/{symbol}", token, symbol=symbol)
    if rec_resp is None:
        return None
    rec = rec_resp.json()
    if not isinstance(rec, dict) or "error" in rec:
        raise ArchiveError(f"malformed record body served for {symbol!r}")
    gene = rec.get("gene")
    if not isinstance(gene, dict) or not gene.get("hgnc_symbol"):
        raise ArchiveError(f"record for {symbol!r} is missing gene.hgnc_symbol")
    sym: str = gene["hgnc_symbol"]

    ev_resp = _fetch_optional(
        http,
        f"{base}/v1/genes/{sym}/evidence",
        token,
        expected_404_error="gene_not_annotated",
        route="evidence",
        symbol=sym,
    )
    evidence: dict[str, Any] | None = None
    evidence_bytes: bytes | None = None
    if ev_resp is not None:
        evidence = ev_resp.json()
        if not isinstance(evidence, dict):
            raise ArchiveError(f"malformed evidence body served for {sym!r}")
        evidence_bytes = ev_resp.content

    md_resp = _fetch_optional(
        http,
        f"{base}/v1/genes/{sym}.md",
        token,
        expected_404_error="markdown_not_found",
        route="markdown",
        symbol=sym,
    )
    md_bytes = md_resp.content if md_resp is not None else None

    return Served(
        gene_symbol=sym,
        record_bytes=rec_resp.content,
        record=rec,
        evidence_bytes=evidence_bytes,
        evidence=evidence,
        md_bytes=md_bytes,
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

    sym = served.gene_symbol
    rec = served.record
    gene = rec["gene"]
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
        datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
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

    urls = [f"/v1/genes/{sym}/revisions", "/v1/releases"]
    if revision is None:
        # Another writer (or a retried-but-already-committed insert) beat
        # us to this exact content. Nothing of ours landed, but the gene's
        # cached surfaces may still be stale relative to that other write,
        # so purge unconditionally rather than only on our own inserts.
        latest = store.latest(sym)
        if purge is not None:
            purge(urls)
        return ArchiveResult(sym, "unchanged", latest.revision if latest else None)
    if purge is not None:
        purge(urls)
    logger.info("archived %s revision %d (%s)", sym, revision, source)
    return ArchiveResult(sym, "created", revision)
