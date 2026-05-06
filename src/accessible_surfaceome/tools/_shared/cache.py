"""SQLite-backed HTTP response cache with per-source TTLs.

Why this exists: every gene_lookup call would otherwise repeat the same UniProt /
HGNC / NCBI fetch on every smoke test, every retry, every agent run. Caching
makes mode escalation cheap, which is what makes progressive disclosure tractable
— the agent can call ``resolve`` then ``uniprot_summary`` without paying twice.

Keyed by (source, sha256(method + url + canonical_body)). TTL is supplied by the
caller per request; this layer doesn't hard-code per-source policy because
different endpoints under the same host (UniProt entry vs UniProt search) have
different staleness tolerances.
"""

from __future__ import annotations

import hashlib
import sqlite3
import time
from pathlib import Path
from threading import Lock


class Cache:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._path = path
        self._lock = Lock()
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS http_cache (
                    source TEXT NOT NULL,
                    key TEXT NOT NULL,
                    body TEXT NOT NULL,
                    fetched_at INTEGER NOT NULL,
                    PRIMARY KEY (source, key)
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def get(self, source: str, key: str, *, ttl_days: int) -> str | None:
        cutoff = int(time.time()) - ttl_days * 86_400
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT body FROM http_cache "
                "WHERE source = ? AND key = ? AND fetched_at >= ?",
                (source, key, cutoff),
            ).fetchone()
        return row[0] if row else None

    def put(self, source: str, key: str, body: str) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO http_cache "
                "(source, key, body, fetched_at) VALUES (?, ?, ?, ?)",
                (source, key, body, int(time.time())),
            )


def cache_key(method: str, url: str, body: bytes | None = None) -> str:
    h = hashlib.sha256()
    h.update(method.encode())
    h.update(b"\0")
    h.update(url.encode())
    if body is not None:
        h.update(b"\0")
        h.update(body)
    return h.hexdigest()
