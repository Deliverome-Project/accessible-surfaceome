"""Where record-history revisions live: R2 bytes + a D1 index.

R2 holds each distinct served part once, named by its content hash
(write-once; nothing overwrites or deletes). D1's ``record_revision`` has
one row per actual change. The insert statement numbers the revision and
skips unchanged content in ONE statement, so re-runs are safe. D1 executes
statements serially, so the MAX(revision)+1 computation can't actually race
across concurrent archivers within a single statement — the composite
``PRIMARY KEY (gene_symbol, revision)`` (declared ``COLLATE NOCASE`` on
``gene_symbol`` so two casings of one gene can't independently land
revision 1) is a defensive backstop, not something callers need to handle.

R2 writes prefer the S3-compatible API (:mod:`accessible_surfaceome.cloud.
r2_s3`) — a separate API surface from ``api.cloudflare.com``, so bulk object
I/O doesn't compete with D1 queries for the shared 1,200-req/5-min account
API budget. The REST :mod:`accessible_surfaceome.cloud.r2_client` path is
kept only as a fallback for when the S3 client can't be constructed (e.g. no
``CLOUDFLARE_API_TOKEN`` in this process's env). D1 calls made through this
module are paced by :class:`~accessible_surfaceome.cloud.record_history.
rate_limit.RateLimiter` (default 2.5 qps, ``RECORD_HISTORY_D1_QPS`` to
override, ``0`` to disable) for the same reason.
"""

from __future__ import annotations

import dataclasses
import logging
import threading
from dataclasses import dataclass
from typing import Any, Protocol

from accessible_surfaceome.cloud import r2_client
from accessible_surfaceome.cloud.d1_client import D1Client
from accessible_surfaceome.cloud.r2_client import R2Config
from accessible_surfaceome.cloud.r2_s3 import R2S3CredentialError, r2_s3_client
from accessible_surfaceome.cloud.record_history.rate_limit import (
    RateLimiter,
    d1_qps_from_env,
)

logger = logging.getLogger(__name__)

BUCKET = "surfaceome-record-history"

DDL: list[str] = [
    """CREATE TABLE IF NOT EXISTS record_revision (
    gene_symbol           TEXT NOT NULL COLLATE NOCASE,
    hgnc_id               TEXT,
    revision              INTEGER NOT NULL,
    json_hash             TEXT NOT NULL,
    evidence_hash         TEXT,
    md_hash                TEXT,
    published_at          TEXT NOT NULL,
    source                TEXT NOT NULL,
    schema_version        TEXT,
    prompt_corpus_version TEXT,
    PRIMARY KEY (gene_symbol, revision)
)""",
    "CREATE INDEX IF NOT EXISTS idx_record_revision_hgnc ON record_revision (hgnc_id)",
    """CREATE TABLE IF NOT EXISTS data_release (
    version            TEXT PRIMARY KEY,
    cut_at             TEXT NOT NULL,
    github_tag         TEXT,
    zenodo_version_doi TEXT,
    n_genes            INTEGER NOT NULL,
    notes              TEXT,
    archive_scope      TEXT
)""",
    """CREATE TABLE IF NOT EXISTS data_release_member (
    version     TEXT NOT NULL,
    gene_symbol TEXT NOT NULL COLLATE NOCASE,
    revision    INTEGER NOT NULL,
    PRIMARY KEY (version, gene_symbol)
)""",
]

# A `data_release` table created before `archive_scope` existed needs this
# applied once, idempotently, before the column can be set (`CREATE TABLE IF
# NOT EXISTS` above is a no-op against an already-existing table — it never
# retrofits a column). SQLite/D1 has no `ADD COLUMN IF NOT EXISTS`, so the
# caller runs this and treats a "duplicate column name" error as success —
# see `scripts/cloud/drop_seed_revisions.py::ensure_archive_scope_column`.
ALTER_DATA_RELEASE_ADD_ARCHIVE_SCOPE_SQL = (
    "ALTER TABLE data_release ADD COLUMN archive_scope TEXT"
)

# ?1 gene_symbol, ?2 hgnc_id, ?3 json_hash, ?4 evidence_hash, ?5 md_hash,
# ?6 published_at, ?7 source, ?8 schema_version, ?9 prompt_corpus_version.
# Inserts MAX(revision)+1 unless the gene's latest row already has these
# exact hashes (`IS` so NULL == NULL). Returns the new revision, or no
# row when unchanged. Symbols compare COLLATE NOCASE like every other
# per-gene lookup (the mixed-case `Cxorf` class) — kept explicit here even
# though the column itself is now declared COLLATE NOCASE, so the query
# reads correctly on its own.
INSERT_REVISION_SQL = """
INSERT INTO record_revision (
    gene_symbol, hgnc_id, revision, json_hash, evidence_hash, md_hash,
    published_at, source, schema_version, prompt_corpus_version)
SELECT
    COALESCE((SELECT gene_symbol FROM record_revision
               WHERE gene_symbol = ?1 COLLATE NOCASE LIMIT 1), ?1),
    ?2,
    COALESCE((SELECT MAX(revision) FROM record_revision
               WHERE gene_symbol = ?1 COLLATE NOCASE), 0) + 1,
    ?3, ?4, ?5, ?6, ?7, ?8, ?9
WHERE NOT EXISTS (
    SELECT 1 FROM record_revision r
     WHERE r.gene_symbol = ?1 COLLATE NOCASE
       AND r.revision = (SELECT MAX(revision) FROM record_revision
                          WHERE gene_symbol = ?1 COLLATE NOCASE)
       AND r.json_hash = ?3
       AND r.evidence_hash IS ?4
       AND r.md_hash IS ?5)
RETURNING revision
"""

# The latest-revision lookup `CloudRevisionStore.latest` runs. A module-level
# constant so tests can pin its query plan (composite PK on
# (gene_symbol, revision) should make this an index SEARCH, never a SCAN)
# without duplicating the SQL text.
LATEST_REVISION_SQL = (
    "SELECT revision, json_hash, evidence_hash, md_hash FROM record_revision "
    "WHERE gene_symbol = ? COLLATE NOCASE ORDER BY revision DESC LIMIT 1"
)

# Every gene's latest revision in ONE query, for `CloudRevisionStore.
# prefetch_latest`. `gene_symbol` is declared COLLATE NOCASE on the column
# itself (see DDL above), so both the GROUP BY and the join's equality
# already compare case-insensitively without spelling COLLATE NOCASE again
# here — two casings of one gene group together and the outer SELECT picks
# up whichever row(s) share that gene's MAX(revision).
PREFETCH_LATEST_SQL = """
SELECT r.gene_symbol AS gene_symbol, r.revision AS revision, r.json_hash AS json_hash,
       r.evidence_hash AS evidence_hash, r.md_hash AS md_hash
FROM record_revision r
JOIN (
    SELECT gene_symbol, MAX(revision) AS revision
    FROM record_revision
    GROUP BY gene_symbol
) m ON r.gene_symbol = m.gene_symbol AND r.revision = m.revision
"""


def blob_key(digest: str, ext: str) -> str:
    """R2 key for one content-addressed part (``ext``: ``json`` or ``md``)."""
    return f"records/sha256/{digest}.{ext}"


@dataclass(frozen=True)
class LatestRevision:
    revision: int
    json_hash: str
    evidence_hash: str | None
    md_hash: str | None


class ArchiveError(RuntimeError):
    """A record-history write or refusal failed outside of D1.

    Covers ``put_blob`` (an R2 write failure) as well as the refusals
    ``archive_gene`` raises directly before ever writing anything: a
    missing ``ARCHIVE_BYPASS_TOKEN``, the Worker not echoing the
    bypass-honoured header, an unexpected 404 reason on a served route, or
    a malformed record/evidence body. A D1 insert failure propagates
    unwrapped as :class:`~accessible_surfaceome.cloud.d1_client.D1Error`
    from ``insert_revision`` — it is not translated into an
    ``ArchiveError``.
    """


class RevisionStore(Protocol):
    """What ``archive_gene`` needs."""

    def latest(self, gene_symbol: str) -> LatestRevision | None: ...

    def put_blob(self, key: str, body: bytes, content_type: str) -> None: ...

    def insert_revision(self, params: list[object]) -> int | None: ...


class _D1Queryable(Protocol):
    """What ``CloudRevisionStore.d1`` exposes — just enough for callers like
    ``create_release`` (which only ever calls ``.query``)."""

    def query(self, sql: str, params: list[Any] | None = None) -> list[dict[str, Any]]: ...


# Logged once per process the first time the S3 client can't be built (e.g.
# no CLOUDFLARE_API_TOKEN in this process's env), not once per put_blob call
# — the REST fallback then just runs silently for the rest of the run.
_s3_fallback_warned = False
_s3_fallback_lock = threading.Lock()


def _s3_client_or_none() -> Any | None:
    global _s3_fallback_warned
    try:
        return r2_s3_client()
    except R2S3CredentialError as exc:
        with _s3_fallback_lock:
            if not _s3_fallback_warned:
                logger.warning(
                    "R2 S3 client unavailable (%s); falling back to the REST "
                    "r2_client path for this process",
                    exc,
                )
                _s3_fallback_warned = True
        return None


def is_missing_s3_object(exc: Any) -> bool:
    """True when a botocore ``ClientError`` means "object not found".

    S3-compatible ``head_object``/``get_object`` report a miss as a
    ``ClientError`` whose HTTP status is 404 — some backends additionally
    set ``Error.Code`` to ``"404"``, ``"NoSuchKey"``, or ``"NotFound"``.
    Anything else (403, 5xx, a network error) is a real failure, not a miss.
    """
    response = getattr(exc, "response", None) or {}
    status = (response.get("ResponseMetadata") or {}).get("HTTPStatusCode")
    if status == 404:
        return True
    code = (response.get("Error") or {}).get("Code")
    return code in ("404", "NoSuchKey", "NotFound")


class _RateLimitedD1:
    """Wraps a :class:`D1Client`, pacing every ``.query()`` through a shared
    :class:`RateLimiter` — the one place record history's D1 traffic (both
    ``CloudRevisionStore``'s own calls and anything a caller runs via the
    ``.d1`` property, e.g. the seed's bulk inserts) gets throttled."""

    def __init__(self, d1: D1Client, limiter: RateLimiter) -> None:
        self._d1 = d1
        self._limiter = limiter

    def query(self, sql: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
        self._limiter.acquire()
        return self._d1.query(sql, params)


class CloudRevisionStore:
    """Public D1 + the history R2 bucket."""

    def __init__(
        self,
        d1: D1Client,
        r2: R2Config,
        *,
        d1_qps: float | None = None,
        require_s3: bool = False,
    ) -> None:
        self._d1 = d1
        # Pin the bucket explicitly: R2Config.from_env() honours a
        # CLOUDFLARE_R2_BUCKET override, which would silently redirect
        # history writes into whatever bucket that env var names.
        self._r2 = dataclasses.replace(r2, bucket=BUCKET)
        limiter = RateLimiter(d1_qps if d1_qps is not None else d1_qps_from_env())
        self._d1_view: _D1Queryable = _RateLimitedD1(d1, limiter)
        # None until `prefetch_latest()` primes it; then `latest()` serves
        # from it with no query, and a successful `insert_revision` updates
        # it in place. Keys are case-folded symbols (the column is COLLATE
        # NOCASE, so two casings of one gene must hit the same cache slot).
        self._latest_cache: dict[str, LatestRevision] | None = None
        self._cache_lock = threading.Lock()
        # When True, `put_blob` raises `ArchiveError` instead of silently
        # falling back to the REST `r2_client` path when the S3 client can't
        # be built. A cohort-scale run (seed/sweep) wants that failure loud
        # and immediate, not a silent trip back through the shared
        # api.cloudflare.com budget this whole rewrite exists to avoid. The
        # one-gene publish path leaves this False and keeps the fallback.
        self._require_s3 = require_s3

    @classmethod
    def from_env(cls, *, require_s3: bool = False) -> CloudRevisionStore:
        # D1Client.public() is documented as reads-only-by-convention
        # elsewhere in this codebase, but record history intentionally
        # WRITES to the public mirror here — the Worker only ever reads
        # surfaceome_public, so history has to live there too. The
        # CLOUDFLARE_API_TOKEN therefore needs D1:Edit scope on
        # surfaceome_public, not just the private surfaceome_agents DB.
        return cls(D1Client.public(), R2Config.from_env(), require_s3=require_s3)

    @property
    def d1(self) -> _D1Queryable:
        return self._d1_view

    def __enter__(self) -> CloudRevisionStore:
        return self

    def __exit__(self, *_exc: object) -> None:
        self._d1.close()

    def prefetch_latest(self) -> None:
        """Load every gene's latest revision in one query (plus one cheap
        count query to verify it).

        After this, ``latest()`` serves from the in-memory cache — a gene
        absent from the loaded cache returns ``None`` with no further
        query. That "absent means genuinely absent" contract is exactly
        what would break silently if the join in ``PREFETCH_LATEST_SQL``
        ever dropped rows (a bug, a collation edge case), so this also
        confirms the cache's gene count against a plain
        ``COUNT(DISTINCT gene_symbol)`` and raises :class:`ArchiveError` if
        they disagree, rather than priming a cache that would misreport a
        real gene as never-archived. Call once before a cohort-scale
        sweep; the publish path (which only ever archives one gene) skips
        it and ``latest()`` just falls back to its own per-gene query, as
        before.
        """
        rows = self._d1_view.query(PREFETCH_LATEST_SQL, [])
        cache = {
            r["gene_symbol"].casefold(): LatestRevision(
                revision=int(r["revision"]),
                json_hash=r["json_hash"],
                evidence_hash=r["evidence_hash"],
                md_hash=r["md_hash"],
            )
            for r in rows
        }
        count_rows = self._d1_view.query(
            "SELECT COUNT(DISTINCT gene_symbol) AS n FROM record_revision", []
        )
        n_distinct = int(count_rows[0]["n"]) if count_rows else 0
        if n_distinct != len(cache):
            raise ArchiveError(
                f"prefetch_latest loaded {len(cache)} genes but record_revision "
                f"has {n_distinct} distinct gene_symbol values — refusing to "
                "prime a cache that could misreport a real gene as absent"
            )
        with self._cache_lock:
            self._latest_cache = cache

    def latest(self, gene_symbol: str) -> LatestRevision | None:
        with self._cache_lock:
            primed = self._latest_cache is not None
            if primed:
                return self._latest_cache.get(gene_symbol.casefold())  # type: ignore[union-attr]
        rows = self._d1_view.query(LATEST_REVISION_SQL, [gene_symbol])
        if not rows:
            return None
        r = rows[0]
        return LatestRevision(
            revision=int(r["revision"]),
            json_hash=r["json_hash"],
            evidence_hash=r["evidence_hash"],
            md_hash=r["md_hash"],
        )

    def put_blob(self, key: str, body: bytes, content_type: str) -> None:
        """Write one content-addressed object, skipping an already-present one.

        Always probes first (``head_object``) — the bucket is strictly
        write-once, and an S3-compatible HEAD doesn't touch the shared
        Cloudflare account API budget (it's the whole reason this class
        prefers the S3 path), so there's no cost to skip by omitting it.
        """
        client = _s3_client_or_none()
        if client is not None:
            self._put_blob_s3(client, key, body, content_type)
            return
        if self._require_s3:
            raise ArchiveError(
                f"R2 S3 client unavailable and require_s3=True — refusing to "
                f"fall back to the REST r2_client path for {key}"
            )
        # REST fallback — only reached when the S3 client can't be built
        # and this store was constructed with require_s3=False (the
        # default; the one-gene publish path).
        if r2_client.head_object(key=key, cfg=self._r2) is not None:
            return
        if not r2_client.put_object(
            key=key, body=body, content_type=content_type, cfg=self._r2
        ):
            raise ArchiveError(f"R2 write failed for {key}")

    def _put_blob_s3(
        self, client: Any, key: str, body: bytes, content_type: str
    ) -> None:
        from botocore.exceptions import ClientError

        try:
            client.head_object(Bucket=self._r2.bucket, Key=key)
            return  # already present — content-addressed, nothing to do
        except ClientError as exc:
            if not is_missing_s3_object(exc):
                raise ArchiveError(f"R2 head_object failed for {key}: {exc}") from exc
        try:
            client.put_object(
                Bucket=self._r2.bucket, Key=key, Body=body, ContentType=content_type
            )
        except ClientError as exc:
            raise ArchiveError(f"R2 put_object failed for {key}: {exc}") from exc

    def insert_revision(self, params: list[object]) -> int | None:
        """Insert the next revision if the hashes changed, else no-op.

        Returns the new revision number, or ``None`` when the content is
        unchanged from the gene's latest row. Note: the underlying
        ``D1Client`` retries transient HTTP failures; if a retry fires
        after a write actually committed but its response was lost, the
        retried attempt sees identical hashes already present and reports
        ``None`` ("unchanged") rather than raising — harmless (no
        duplicate row, no lost data), just worth knowing when debugging
        why an expected new revision didn't show up.

        A successful insert also updates the in-memory cache
        ``prefetch_latest()`` primed, if any — built straight from
        ``params`` and the returned revision, no extra query. A ``None``
        (unchanged) result, when the cache is primed, instead re-queries
        this one gene (``LATEST_REVISION_SQL``) and updates the cache from
        that — the row that made this insert "unchanged" might belong to a
        gene our cache never learned about (e.g. another writer inserted
        its very first revision after our ``prefetch_latest()`` snapshot),
        and without this, a caller like ``archive_gene`` would report that
        gene's revision as ``None`` even though D1 has a real row for it.
        """
        rows = self._d1_view.query(INSERT_REVISION_SQL, list(params))
        revision = int(rows[0]["revision"]) if rows else None
        sym = str(params[0])
        if revision is not None:
            with self._cache_lock:
                if self._latest_cache is not None:
                    self._latest_cache[sym.casefold()] = LatestRevision(
                        revision=revision,
                        json_hash=str(params[2]),
                        evidence_hash=None if params[3] is None else str(params[3]),
                        md_hash=None if params[4] is None else str(params[4]),
                    )
        else:
            with self._cache_lock:
                primed = self._latest_cache is not None
            if primed:
                self._refresh_cached_latest(sym)
        return revision

    def _refresh_cached_latest(self, gene_symbol: str) -> None:
        """Re-query one gene's latest row and update the primed cache."""
        rows = self._d1_view.query(LATEST_REVISION_SQL, [gene_symbol])
        with self._cache_lock:
            if self._latest_cache is None:
                return
            key = gene_symbol.casefold()
            if not rows:
                self._latest_cache.pop(key, None)
                return
            r = rows[0]
            self._latest_cache[key] = LatestRevision(
                revision=int(r["revision"]),
                json_hash=r["json_hash"],
                evidence_hash=r["evidence_hash"],
                md_hash=r["md_hash"],
            )
