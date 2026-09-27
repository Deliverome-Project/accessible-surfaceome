"""Where record-history revisions live: R2 bytes + a D1 index.

R2 holds each distinct served part once, named by its content hash
(write-once; nothing overwrites or deletes). D1's ``record_revision`` has
one row per actual change. The insert statement numbers the revision and
skips unchanged content in ONE statement, so re-runs and concurrent
archivers are safe (a lost race surfaces as a PK conflict the caller
retries).
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Protocol

from accessible_surfaceome.cloud import r2_client
from accessible_surfaceome.cloud.d1_client import D1Client
from accessible_surfaceome.cloud.r2_client import R2Config

BUCKET = "surfaceome-record-history"

DDL: list[str] = [
    """CREATE TABLE IF NOT EXISTS record_revision (
    gene_symbol           TEXT NOT NULL,
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
    notes              TEXT
)""",
    """CREATE TABLE IF NOT EXISTS data_release_member (
    version     TEXT NOT NULL,
    gene_symbol TEXT NOT NULL,
    revision    INTEGER NOT NULL,
    PRIMARY KEY (version, gene_symbol)
)""",
]

# ?1 gene_symbol, ?2 hgnc_id, ?3 json_hash, ?4 evidence_hash, ?5 md_hash,
# ?6 published_at, ?7 source, ?8 schema_version, ?9 prompt_corpus_version.
# Inserts MAX(revision)+1 unless the gene's latest row already has these
# exact hashes (`IS` so NULL == NULL). Returns the new revision, or no
# row when unchanged. Symbols compare COLLATE NOCASE like every other
# per-gene lookup (the mixed-case `Cxorf` class).
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
    """A revision could not be archived (R2 write or D1 insert failed)."""


class RevisionStore(Protocol):
    def latest(self, gene_symbol: str) -> LatestRevision | None: ...

    def put_blob(self, key: str, body: bytes, content_type: str) -> None: ...

    def insert_revision(self, params: list[object]) -> int | None: ...


class CloudRevisionStore:
    """Public D1 + the history R2 bucket."""

    def __init__(self, d1: D1Client, r2: R2Config) -> None:
        self._d1 = d1
        # Pin the bucket explicitly: R2Config.from_env() honours a
        # CLOUDFLARE_R2_BUCKET override, which would silently redirect
        # history writes into whatever bucket that env var names.
        self._r2 = dataclasses.replace(r2, bucket=BUCKET)

    @classmethod
    def from_env(cls) -> CloudRevisionStore:
        return cls(D1Client.public(), R2Config.from_env())

    @property
    def d1(self) -> D1Client:
        return self._d1

    def __enter__(self) -> CloudRevisionStore:
        return self

    def __exit__(self, *_exc: object) -> None:
        self._d1.close()

    def latest(self, gene_symbol: str) -> LatestRevision | None:
        rows = self._d1.query(
            "SELECT revision, json_hash, evidence_hash, md_hash FROM record_revision "
            "WHERE gene_symbol = ? COLLATE NOCASE ORDER BY revision DESC LIMIT 1",
            [gene_symbol],
        )
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
        # Content-addressed: an existing object already holds these bytes.
        # A false miss from head_object just re-writes identical bytes.
        if r2_client.head_object(key=key, cfg=self._r2) is not None:
            return
        if not r2_client.put_object(
            key=key, body=body, content_type=content_type, cfg=self._r2
        ):
            raise ArchiveError(f"R2 write failed for {key}")

    def insert_revision(self, params: list[object]) -> int | None:
        rows = self._d1.query(INSERT_REVISION_SQL, list(params))
        return int(rows[0]["revision"]) if rows else None
