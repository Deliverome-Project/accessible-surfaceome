# Public Record History Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep every served revision of every gene's public record (record JSON, evidence ledger, Markdown export) retrievable forever, and name numbered data releases over those revisions that match the GitHub release, the site badge, and a Zenodo data-record version.

**Architecture:** A Python archiver fetches what the public Worker actually serves for a gene (bypassing its caches with a secret header), hashes each part, writes new bytes to a write-once content-addressed R2 bucket, and appends a row to a `record_revision` table in public D1 only when something changed. Releases are rows in `data_release` + `data_release_member` pointing at revisions. The Worker gains read-only, path-based history endpoints; the live endpoints are untouched.

**Tech Stack:** Python 3 (httpx, pytest, `D1Client`, `r2_client`), Cloudflare Worker (plain JS module, tested by copying `index.js` into a temp dir and running Node), Cloudflare D1 + R2, Zenodo REST API, Next.js viewer (client component, `node:test` + `tsx` tests).

**Spec:** [docs/superpowers/specs/2026-09-27-record-history-design.md](../specs/2026-09-27-record-history-design.md)

**Branch:** `claude/record-history-api`. Commit with `git commit -- <paths>` (other sessions may share the index). No `Co-Authored-By` trailers.

---

## Conventions every task follows

- Run Python tests with `uv run pytest -q <path>`; the full gate is `bash scripts/check-py.sh` (ruff + ty + compile + pytest).
- Worker tests need Node from `.nvmrc`; they `pytest.skip` without it locally (CI sets `REQUIRE_WORKER_NODE=1`).
- Viewer tests: `cd viewer && npx --yes tsx --import ./tests/helpers/register.mjs --test tests/<file>`. Type-check with `cd viewer && npm run check`.
- **Nothing in Tasks 1–16 touches production.** Live D1/R2/Worker/Zenodo actions happen only in Task 17, and each one needs the user's explicit go-ahead.

## File map

| File | Responsibility |
|---|---|
| `src/accessible_surfaceome/cloud/record_history/__init__.py` | Package marker; re-exports nothing |
| `src/accessible_surfaceome/cloud/record_history/hashing.py` | Canonical JSON + the three content hashes + the pinned volatile-field list |
| `src/accessible_surfaceome/cloud/record_history/store.py` | DDL, R2 key scheme, `RevisionStore` protocol, `CloudRevisionStore` (D1 + R2) |
| `src/accessible_surfaceome/cloud/record_history/archive.py` | `fetch_served` + `archive_gene` (the one write path) |
| `src/accessible_surfaceome/cloud/record_history/releases.py` | Create a release, list latest members, set DOI, export a release tarball |
| `src/accessible_surfaceome/cloud/record_history/zenodo.py` | Draft a new version of the Zenodo data record |
| `src/accessible_surfaceome/cloud/r2_client.py` | + `get_object` |
| `src/accessible_surfaceome/cloud/surface_annotation.py` | + generic `purge_paths`; `_publish_dict` archives after publishing |
| `scripts/cloud/apply_record_history_ddl.py` | Apply the three tables to public D1 (dry-run default) |
| `scripts/cloud/sweep_record_history.py` | Archive every annotated gene |
| `scripts/cloud/seed_record_history.py` | One-off: seed revision 1 + release 1.0.0 from the Zenodo tarball |
| `scripts/release/cut_data_release.py` | Cut a numbered release; draft the Zenodo version; record the DOI |
| `scripts/build/backfill_deep_block_rollups.py` | Archive after each direct D1 `UPDATE` |
| `cloudflare/d1_public_schema.sql` | The three tables (documentation of record) |
| `cloudflare/workers/surfaceome_api/src/index.js` | Bypass header; 9 history endpoints; `/v1` index entries |
| `cloudflare/workers/surfaceome_api/wrangler.toml.example` | `RECORD_HISTORY` R2 binding + secret note |
| `viewer/lib/revisions.ts` | Revision-list types + parser |
| `viewer/components/surfaceome/RevisionStrip/RevisionStrip.tsx` (+ `.module.css`) | The one-line citation strip |
| `viewer/app/gene/page.tsx`, `viewer/components/surfaceome/GeneDetail/GeneDetail.tsx` | Fetch + render the strip |
| `viewer/next.config.mjs`, `viewer/components/Shell/Shell.tsx` | Badge from `pyproject.toml` (already edited, uncommitted) |
| Tests | `tests/test_record_history_hashing.py`, `tests/test_record_history_store.py`, `tests/test_record_history_archive.py`, `tests/test_record_history_releases.py`, `tests/test_record_history_zenodo.py`, `tests/test_r2_client.py` (+get), `tests/test_publish_archives.py`, `tests/test_worker_record_history.py`, `viewer/tests/revision_strip.test.tsx` |

---

### Task 1: Commit the release badge

The badge change from the start of the session is already in the working tree (spec + this plan are committed).

**Files:**
- Modify: `viewer/next.config.mjs`, `viewer/components/Shell/Shell.tsx` (already edited)

- [ ] **Step 1: Type-check the viewer**

Run: `cd viewer && npm run check`
Expected: exits 0, no output.

- [ ] **Step 2: Confirm the badge resolves**

Run: `cd viewer && node -e 'import("./next.config.mjs").then(m=>console.log(m.default.env.NEXT_PUBLIC_RELEASE_VERSION))'`
Expected: `1.2.0`

- [ ] **Step 3: Commit**

```bash
git commit -m "fix(viewer): show the current release version in the header badge" -- viewer/next.config.mjs viewer/components/Shell/Shell.tsx
```

---

### Task 2: Content hashing

**Files:**
- Create: `src/accessible_surfaceome/cloud/record_history/__init__.py`
- Create: `src/accessible_surfaceome/cloud/record_history/hashing.py`
- Test: `tests/test_record_history_hashing.py`

- [ ] **Step 1: Write the failing tests**

```python
"""Pins the content hash that decides whether a served record is a new revision."""

from __future__ import annotations

from accessible_surfaceome.cloud.record_history.hashing import (
    VOLATILE_RECORD_FIELDS,
    canonical_json,
    content_hash_evidence,
    content_hash_md,
    content_hash_record,
)


def test_canonical_json_is_key_order_independent() -> None:
    assert canonical_json({"b": 1, "a": [1, {"d": 2, "c": 3}]}) == canonical_json(
        {"a": [1, {"c": 3, "d": 2}], "b": 1}
    )


def test_canonical_json_keeps_unicode_verbatim() -> None:
    assert canonical_json({"q": "TGFβ"}) == '{"q":"TGFβ"}'.encode()


def test_record_hash_ignores_only_volatile_fields() -> None:
    a = {"gene": {"hgnc_symbol": "X"}, "confidence": "high", "record_generated_at": "2026-01-01T00:00:00Z"}
    b = {**a, "record_generated_at": "2026-09-27T12:00:00Z"}
    c = {**a, "confidence": "low"}
    assert content_hash_record(a) == content_hash_record(b)
    assert content_hash_record(a) != content_hash_record(c)


def test_volatile_field_list_is_pinned() -> None:
    # Adding a field here hides real changes from history; do it only after
    # fetching one gene twice and seeing the field differ with nothing else.
    assert VOLATILE_RECORD_FIELDS == frozenset({"record_generated_at"})


def test_evidence_hash_covers_everything() -> None:
    a = {"gene": "X", "evidence": [{"id": "e1"}], "papers": {}}
    b = {**a, "papers": {"PMID:1": {"title": "t"}}}
    assert content_hash_evidence(a) != content_hash_evidence(b)


def test_md_hash_ignores_the_generated_timestamp_only() -> None:
    head = "*Schema v2.14.2 · generated {ts} · model `claude-sonnet-4-6`*\n\nBody"
    a = head.format(ts="2026-07-06T01:33:13.907867Z")
    b = head.format(ts="2026-09-27T10:00:00Z")
    assert content_hash_md(a) == content_hash_md(b)
    assert content_hash_md(a) != content_hash_md(a.replace("Body", "Changed"))


def test_hashes_are_sha256_hex() -> None:
    h = content_hash_record({"a": 1})
    assert len(h) == 64 and all(ch in "0123456789abcdef" for ch in h)
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest -q tests/test_record_history_hashing.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'accessible_surfaceome.cloud.record_history'`

- [ ] **Step 3: Implement**

`src/accessible_surfaceome/cloud/record_history/__init__.py`:

```python
"""Public record history: content-addressed revisions + numbered data releases.

See docs/superpowers/specs/2026-09-27-record-history-design.md.
"""
```

`src/accessible_surfaceome/cloud/record_history/hashing.py`:

```python
"""Content hashes that decide whether a served record is a new revision.

A revision is written only when one of these hashes changes, so the hash
must ignore fields that differ on every run without changing what the
record says — and nothing else. The stored bytes are always the full
response exactly as served; only the *comparison* ignores these fields.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

# Top-level record fields that change on every run without changing the
# record's content. Pinned by tests/test_record_history_hashing.py — add a
# field only after fetching one gene twice and seeing it alone differ.
VOLATILE_RECORD_FIELDS: frozenset[str] = frozenset({"record_generated_at"})

# The Markdown export's header line stamps the record's generation time
# ("*Schema v2.14.2 · generated 2026-07-06T01:33:13.907867Z · model …*").
_MD_GENERATED = re.compile(r"generated \d{4}-\d{2}-\d{2}T[0-9:.]+(?:Z|[+-]\d{2}:\d{2})?")


def canonical_json(obj: Any) -> bytes:
    """Key-sorted, whitespace-free UTF-8 JSON — stable across serializers."""
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def content_hash_record(body: dict[str, Any]) -> str:
    """Hash of a served ``/v1/genes/{sym}`` record, minus volatile fields."""
    stable = {k: v for k, v in body.items() if k not in VOLATILE_RECORD_FIELDS}
    return _sha256(canonical_json(stable))


def content_hash_evidence(body: dict[str, Any]) -> str:
    """Hash of a served ``/v1/genes/{sym}/evidence`` ledger (quotes + papers)."""
    return _sha256(canonical_json(body))


def content_hash_md(text: str) -> str:
    """Hash of a served ``/v1/genes/{sym}.md`` export, timestamp normalized."""
    return _sha256(_MD_GENERATED.sub("generated <ts>", text).encode("utf-8"))
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest -q tests/test_record_history_hashing.py`
Expected: `7 passed`

- [ ] **Step 5: Commit**

```bash
git add src/accessible_surfaceome/cloud/record_history tests/test_record_history_hashing.py
git commit -m "feat(surface-proteome): content hashes for record-history revisions" -- src/accessible_surfaceome/cloud/record_history tests/test_record_history_hashing.py
```

---

### Task 3: `r2_client.get_object`

The release export reads archived bytes back out of R2; `r2_client` has no GET.

**Files:**
- Modify: `src/accessible_surfaceome/cloud/r2_client.py` (add after `head_object`, extend `__all__`)
- Test: `tests/test_r2_client.py` (append)

- [ ] **Step 1: Write the failing tests** (append to `tests/test_r2_client.py`; it already defines `_cfg` and `_patch_client`)

```python
from accessible_surfaceome.cloud.r2_client import get_object


def test_get_object_returns_bytes_on_200(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = _patch_client(monkeypatch, lambda _: httpx.Response(200, content=b'{"a":1}'))
    assert get_object(key="records/sha256/abc.json", cfg=_cfg()) == b'{"a":1}'
    req = captured["request"]
    assert req.method == "GET"
    assert req.url.path.endswith("/r2/buckets/buk/objects/records/sha256/abc.json")
    assert "Range" not in req.headers


def test_get_object_returns_none_on_404(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_client(monkeypatch, lambda _: httpx.Response(404))
    assert get_object(key="missing", cfg=_cfg()) is None


def test_get_object_raises_on_server_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_client(monkeypatch, lambda _: httpx.Response(500, text="boom"))
    with pytest.raises(httpx.HTTPStatusError):
        get_object(key="x", cfg=_cfg())
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest -q tests/test_r2_client.py -k get_object`
Expected: FAIL with `ImportError: cannot import name 'get_object'`

- [ ] **Step 3: Implement** (insert after `head_object`)

```python
def get_object(
    *,
    key: str,
    cfg: R2Config | None = None,
) -> bytes | None:
    """Download one object. ``None`` on a 404; raises on any other failure.

    Unlike :func:`put_object` this is not best-effort: the only caller (the
    record-history release export) must not silently ship a tarball with a
    missing record, so non-404 errors propagate.
    """
    cfg = cfg or R2Config.from_env()
    with httpx.Client(timeout=_R2_OBJECT_TIMEOUT_S) as c:
        resp = c.get(
            _object_url(cfg, key),
            headers={"Authorization": f"Bearer {cfg.api_token}"},
        )
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.content
```

Add `"get_object",` to `__all__`.

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest -q tests/test_r2_client.py`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(surface-proteome): r2_client.get_object for reading archived records" -- src/accessible_surfaceome/cloud/r2_client.py tests/test_r2_client.py
```

---

### Task 4: Revision store (DDL, keys, D1 + R2 adapter)

**Files:**
- Create: `src/accessible_surfaceome/cloud/record_history/store.py`
- Modify: `cloudflare/d1_public_schema.sql` (append the three tables)
- Test: `tests/test_record_history_store.py`

- [ ] **Step 1: Write the failing tests**

```python
"""Record-history store: DDL shape, key scheme, and the insert-if-changed SQL."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from accessible_surfaceome.cloud.record_history.store import (
    BUCKET,
    DDL,
    INSERT_REVISION_SQL,
    blob_key,
)

_ROOT = Path(__file__).resolve().parents[1]


def _db() -> sqlite3.Connection:
    con = sqlite3.connect(":memory:")
    for stmt in DDL:
        con.execute(stmt)
    return con


def _insert(con: sqlite3.Connection, sym: str, j: str, e: str | None, m: str | None) -> list:
    return con.execute(
        INSERT_REVISION_SQL,
        [sym, "HGNC:1", j, e, m, "2026-09-27T00:00:00Z", "sweep", "2.14.4", "2.50.2"],
    ).fetchall()


def test_blob_key_and_bucket() -> None:
    assert BUCKET == "surfaceome-record-history"
    assert blob_key("ab" * 32, "json") == f"records/sha256/{'ab' * 32}.json"


def test_first_insert_is_revision_one() -> None:
    con = _db()
    assert _insert(con, "EGFR", "h1", "e1", "m1") == [(1,)]


def test_unchanged_insert_writes_nothing() -> None:
    con = _db()
    _insert(con, "EGFR", "h1", "e1", None)
    assert _insert(con, "EGFR", "h1", "e1", None) == []
    assert con.execute("SELECT count(*) FROM record_revision").fetchone() == (1,)


def test_any_part_change_is_a_new_revision() -> None:
    con = _db()
    _insert(con, "EGFR", "h1", "e1", "m1")
    assert _insert(con, "EGFR", "h1", "e1", "m2") == [(2,)]
    assert _insert(con, "EGFR", "h1", "e2", "m2") == [(3,)]


def test_revert_is_a_new_revision() -> None:
    con = _db()
    _insert(con, "EGFR", "h1", None, None)
    _insert(con, "EGFR", "h2", None, None)
    assert _insert(con, "EGFR", "h1", None, None) == [(3,)]


def test_revisions_are_per_gene_and_case_insensitive() -> None:
    con = _db()
    _insert(con, "C11orf24", "h1", None, None)
    assert _insert(con, "EGFR", "h9", None, None) == [(1,)]
    assert _insert(con, "c11ORF24", "h1", None, None) == []


def test_public_schema_file_documents_every_table() -> None:
    sql = (_ROOT / "cloudflare/d1_public_schema.sql").read_text()
    for table in ("record_revision", "data_release", "data_release_member"):
        assert f"CREATE TABLE IF NOT EXISTS {table}" in sql
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest -q tests/test_record_history_store.py`
Expected: FAIL with `ModuleNotFoundError: ... record_history.store`

- [ ] **Step 3: Implement `store.py`**

```python
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
    md_hash               TEXT,
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
```

Append to `cloudflare/d1_public_schema.sql` (same statements as `DDL`, with comments):

```sql
-- ---------------------------------------------------------------------------
-- Record history (2026-09-27; spec docs/superpowers/specs/2026-09-27-record-history-design.md)
-- One row per ACTUAL change to what the API served for a gene: record,
-- evidence ledger, Markdown export. Bytes live write-once in R2 bucket
-- surfaceome-record-history at records/sha256/{hash}.{json|md}. Written
-- only by accessible_surfaceome.cloud.record_history; the Worker reads.
-- DDL of record: record_history/store.py::DDL (applied by
-- scripts/cloud/apply_record_history_ddl.py). Keep the two identical.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS record_revision (
    gene_symbol           TEXT NOT NULL,
    hgnc_id               TEXT,
    revision              INTEGER NOT NULL,   -- 1, 2, 3 … per gene
    json_hash             TEXT NOT NULL,      -- sha256 of the served record
    evidence_hash         TEXT,               -- NULL: evidence inline (seed) or absent
    md_hash               TEXT,               -- NULL: no .md existed
    published_at          TEXT NOT NULL,      -- ISO-8601 UTC, when archived
    source                TEXT NOT NULL,      -- seed:zenodo-1.0.0 | publish | sweep
    schema_version        TEXT,
    prompt_corpus_version TEXT,
    PRIMARY KEY (gene_symbol, revision)
);
CREATE INDEX IF NOT EXISTS idx_record_revision_hgnc ON record_revision (hgnc_id);

-- A numbered data release: a fixed pointer per gene to one revision.
CREATE TABLE IF NOT EXISTS data_release (
    version            TEXT PRIMARY KEY,   -- '1.3.0'
    cut_at             TEXT NOT NULL,
    github_tag         TEXT,               -- 'v1.3.0'; NULL for 1.0.0
    zenodo_version_doi TEXT,               -- set once the Zenodo version is published
    n_genes            INTEGER NOT NULL,
    notes              TEXT
);

CREATE TABLE IF NOT EXISTS data_release_member (
    version     TEXT NOT NULL,
    gene_symbol TEXT NOT NULL,
    revision    INTEGER NOT NULL,
    PRIMARY KEY (version, gene_symbol)
);
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest -q tests/test_record_history_store.py`
Expected: `7 passed`. (If the local SQLite rejects `RETURNING`, it is older than 3.35 — run with `uv run` so the project's Python is used; D1 supports `RETURNING`.)

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(surface-proteome): record-history store — D1 index, R2 keys, insert-if-changed" -- src/accessible_surfaceome/cloud/record_history/store.py cloudflare/d1_public_schema.sql tests/test_record_history_store.py
```

---

### Task 5: `archive_gene` — the single write path

**Files:**
- Create: `src/accessible_surfaceome/cloud/record_history/archive.py`
- Test: `tests/test_record_history_archive.py`

- [ ] **Step 1: Write the failing tests**

```python
"""archive_gene: fetch what the Worker served, write only what changed."""

from __future__ import annotations

import json

import httpx
import pytest

from accessible_surfaceome.cloud.d1_client import D1Error
from accessible_surfaceome.cloud.record_history.archive import (
    BYPASS_HEADER,
    archive_gene,
)
from accessible_surfaceome.cloud.record_history.hashing import content_hash_record
from accessible_surfaceome.cloud.record_history.store import (
    ArchiveError,
    LatestRevision,
    blob_key,
)

BASE = "https://api.test/surfaceome"
RECORD = {
    "gene": {"hgnc_symbol": "EGFR", "hgnc_id": "HGNC:3236"},
    "schema_version": "2.14.4",
    "prompt_corpus_version": "2.50.2",
    "record_generated_at": "2026-09-27T00:00:00Z",
    "confidence": "high",
}
EVIDENCE = {"gene": "EGFR", "evidence": [{"id": "e1"}], "papers": {}}
MD = "# EGFR\n\n*Schema v2.14.4 · generated 2026-09-27T00:00:00Z · model `m`*\n"


class FakeStore:
    def __init__(self, latest: LatestRevision | None = None) -> None:
        self._latest = latest
        self.blobs: dict[str, bytes] = {}
        self.inserts: list[list[object]] = []
        self.fail_insert_once = False

    def latest(self, gene_symbol: str) -> LatestRevision | None:
        return self._latest

    def put_blob(self, key: str, body: bytes, content_type: str) -> None:
        self.blobs[key] = body

    def insert_revision(self, params: list[object]) -> int | None:
        if self.fail_insert_once:
            self.fail_insert_once = False
            raise D1Error("UNIQUE constraint failed: record_revision.gene_symbol")
        self.inserts.append(params)
        return (self._latest.revision if self._latest else 0) + 1


def _http(record=RECORD, evidence=EVIDENCE, md=MD, seen: list | None = None) -> httpx.Client:
    def handler(req: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(req)
        path = req.url.path
        if path.endswith("/v1/genes/EGFR"):
            return httpx.Response(200, json=record) if record else httpx.Response(404)
        if path.endswith("/v1/genes/EGFR/evidence"):
            return httpx.Response(200, json=evidence) if evidence else httpx.Response(404)
        if path.endswith("/v1/genes/EGFR.md"):
            return httpx.Response(200, text=md) if md else httpx.Response(404)
        return httpx.Response(404)

    return httpx.Client(transport=httpx.MockTransport(handler))


def _run(store, http, **kw):
    return archive_gene("EGFR", source="sweep", http=http, store=store, token="tok", base=BASE, **kw)


def test_first_archive_writes_three_blobs_and_revision_one() -> None:
    store, seen = FakeStore(), []
    purged: list[list[str]] = []
    result = _run(store, _http(seen=seen), purge=purged.append)
    assert (result.status, result.revision) == ("created", 1)
    assert len(store.blobs) == 3
    # Stored bytes are exactly what the server sent; compare parsed.
    assert json.loads(store.blobs[blob_key(content_hash_record(RECORD), "json")]) == RECORD
    params = store.inserts[0]
    assert params[0] == "EGFR" and params[1] == "HGNC:3236" and params[6] == "sweep"
    assert all(r.headers[BYPASS_HEADER] == "tok" for r in seen)
    assert purged == [["/v1/genes/EGFR/revisions", "/v1/releases"]]


def test_unchanged_writes_nothing() -> None:
    first = FakeStore()
    _run(first, _http())
    p = first.inserts[0]
    latest = LatestRevision(revision=4, json_hash=p[2], evidence_hash=p[3], md_hash=p[4])
    store = FakeStore(latest)
    result = _run(store, _http())
    assert (result.status, result.revision) == ("unchanged", 4)
    assert store.blobs == {} and store.inserts == []


def test_timestamp_only_change_is_unchanged() -> None:
    first = FakeStore()
    _run(first, _http())
    p = first.inserts[0]
    latest = LatestRevision(revision=1, json_hash=p[2], evidence_hash=p[3], md_hash=p[4])
    bumped = {**RECORD, "record_generated_at": "2026-10-01T00:00:00Z"}
    md2 = MD.replace("2026-09-27T00:00:00Z", "2026-10-01T00:00:00Z")
    assert _run(FakeStore(latest), _http(record=bumped, md=md2)).status == "unchanged"


def test_missing_md_and_evidence_are_null_hashes() -> None:
    store = FakeStore()
    _run(store, _http(evidence=None, md=None))
    assert store.inserts[0][3] is None and store.inserts[0][4] is None
    assert len(store.blobs) == 1


def test_not_annotated_gene() -> None:
    store = FakeStore()
    assert _run(store, _http(record=None)).status == "not_annotated"
    assert store.inserts == []


def test_lost_race_is_retried_once() -> None:
    store = FakeStore()
    store.fail_insert_once = True
    assert _run(store, _http()).status == "created"


def test_missing_token_refuses() -> None:
    with pytest.raises(ArchiveError, match="ARCHIVE_BYPASS_TOKEN"):
        archive_gene("EGFR", source="sweep", http=_http(), store=FakeStore(), token="", base=BASE)


def test_server_error_propagates() -> None:
    http = httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(503)))
    with pytest.raises(httpx.HTTPStatusError):
        _run(FakeStore(), http)
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest -q tests/test_record_history_archive.py`
Expected: FAIL with `ModuleNotFoundError: ... record_history.archive`

- [ ] **Step 3: Implement `archive.py`**

```python
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


def fetch_served(symbol: str, *, http: httpx.Client, token: str, base: str = PUBLIC_API_BASE) -> Served | None:
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
    evidence_hash = content_hash_evidence(served.evidence) if served.evidence is not None else None
    md_hash = content_hash_md(served.md_bytes.decode("utf-8")) if served.md_bytes is not None else None

    latest = store.latest(sym)
    if latest and (latest.json_hash, latest.evidence_hash, latest.md_hash) == (json_hash, evidence_hash, md_hash):
        return ArchiveResult(sym, "unchanged", latest.revision)

    store.put_blob(blob_key(json_hash, "json"), served.record_bytes, "application/json")
    if evidence_hash and served.evidence_bytes is not None:
        store.put_blob(blob_key(evidence_hash, "json"), served.evidence_bytes, "application/json")
    if md_hash and served.md_bytes is not None:
        store.put_blob(blob_key(md_hash, "md"), served.md_bytes, "text/markdown; charset=utf-8")

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
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest -q tests/test_record_history_archive.py`
Expected: `8 passed`

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(surface-proteome): archive_gene — the single record-history write path" -- src/accessible_surfaceome/cloud/record_history/archive.py tests/test_record_history_archive.py
```

---

### Task 6: Generic `purge_paths` + archive after every publish

**Files:**
- Modify: `src/accessible_surfaceome/cloud/surface_annotation.py` — `purge_cohort_surfaces` (≈line 357), `PublishResult` (≈line 87), `_publish_dict` tail (≈line 1057)
- Test: `tests/test_publish_archives.py`; existing `tests/test_cohort_cache_purge.py` must still pass

- [ ] **Step 1: Write the failing tests**

```python
"""A publish archives the new record; failures never fail the publish."""

from __future__ import annotations

import httpx
import pytest

from accessible_surfaceome.cloud import surface_annotation as sa


def test_purge_paths_is_public_and_reused_by_cohort_purge() -> None:
    assert callable(sa.purge_paths)
    assert sa.purge_cohort_surfaces([]) is None  # no paths → nothing to do


def test_maybe_archive_skips_without_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ARCHIVE_BYPASS_TOKEN", raising=False)
    assert sa._maybe_archive("EGFR", client=httpx.Client()) is None


def test_maybe_archive_swallows_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARCHIVE_BYPASS_TOKEN", "tok")

    def boom(*_a, **_k):
        raise RuntimeError("R2 down")

    monkeypatch.setattr(sa, "_open_revision_store", boom)
    assert sa._maybe_archive("EGFR", client=httpx.Client()) == "failed"


def test_maybe_archive_reports_status(monkeypatch: pytest.MonkeyPatch) -> None:
    from accessible_surfaceome.cloud.record_history import archive as arch

    monkeypatch.setenv("ARCHIVE_BYPASS_TOKEN", "tok")

    class _Store:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

    monkeypatch.setattr(sa, "_open_revision_store", lambda: _Store())
    monkeypatch.setattr(
        arch, "archive_gene",
        lambda sym, **kw: arch.ArchiveResult(sym, "created", 3),
    )
    assert sa._maybe_archive("EGFR", client=httpx.Client()) == "created"


def test_publish_result_carries_archive_status() -> None:
    r = sa.PublishResult(
        gene_symbol="X", snapshot_path=None, d1_written=False,
        d1_database_id=None, stale_versions_dropped=[],
    )
    assert r.archive_status is None
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest -q tests/test_publish_archives.py`
Expected: FAIL with `AttributeError: module ... has no attribute 'purge_paths'`

- [ ] **Step 3: Implement**

(a) Split `purge_cohort_surfaces`: rename its body (everything after `paths = cohort_purge_paths(tables)` / `if not paths: return None`) into a new public function, replacing the word "cohort" in its log messages with "path":

```python
def purge_paths(
    paths: list[str], *, client: httpx.Client | None = None
) -> bool | None:
    """Best-effort purge of Worker cache surfaces by API path (edge + KV).

    ``paths`` are route paths like ``/v1/releases`` (no ``/surfaceome``
    prefix). Same posture as :func:`purge_cohort_surfaces`, which now
    delegates here: soft-skips without Cloudflare config, never raises.
    """
    if not paths:
        return None
    # … the existing body of purge_cohort_surfaces from `cfg = _public_config_from_env()`
    #   through its `finally:` block, unchanged except the log wording …


def purge_cohort_surfaces(
    tables: Iterable[str], *, client: httpx.Client | None = None
) -> bool | None:
    """Purge the cohort surfaces a public-D1 sync of ``tables`` invalidated."""
    return purge_paths(cohort_purge_paths(tables), client=client)
```

(b) Add to `PublishResult` after `cache_purged`:

```python
    # Record-history archive after the D1 write:
    #   None       — not attempted (no D1 write, or ARCHIVE_BYPASS_TOKEN unset)
    #   "created" / "unchanged" / "not_annotated" — archive_gene's status
    #   "failed"   — archiving raised; the next sweep captures the revision
    archive_status: str | None = None
```

(c) Add helpers above `_publish_dict`:

```python
def _open_revision_store():  # indirection so tests can stub it
    from accessible_surfaceome.cloud.record_history.store import CloudRevisionStore

    return CloudRevisionStore.from_env()


def _maybe_archive(sym: str, *, client: httpx.Client) -> str | None:
    """Best-effort record-history archive after a publish.

    Never fails the publish: a miss is backstopped by
    ``scripts/cloud/sweep_record_history.py``.
    """
    token = os.environ.get("ARCHIVE_BYPASS_TOKEN", "").strip()
    if not token:
        logger.warning(
            "ARCHIVE_BYPASS_TOKEN not set — %s not archived to record history; "
            "run scripts/cloud/sweep_record_history.py to catch up.",
            sym,
        )
        return None
    try:
        from accessible_surfaceome.cloud.record_history import archive as arch

        with _open_revision_store() as store:
            result = arch.archive_gene(
                sym, source="publish", http=client, store=store,
                token=token, purge=purge_paths,
            )
        return result.status
    except Exception as exc:  # noqa: BLE001 — archiving is best-effort here
        logger.warning(
            "record-history archive failed for %s (%s) — the next sweep captures it",
            sym, exc,
        )
        return "failed"
```

(d) In `_publish_dict`, after `_maybe_purge_kv(sym, cfg=cfg, client=client)`:

```python
        # Archive what the API now serves for this gene into record
        # history (after the purges, though the archiver bypasses the
        # caches anyway). Best-effort; see _maybe_archive.
        archive_status = _maybe_archive(sym, client=client)
```

and pass `archive_status=archive_status,` in the final `PublishResult(...)`. Declare `archive_status: str | None = None` before the `with`/`if` block that performs the D1 write so the name is always bound.

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest -q tests/test_publish_archives.py tests/test_cohort_cache_purge.py`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(surface-proteome): archive every published record to history; generic purge_paths" -- src/accessible_surfaceome/cloud/surface_annotation.py tests/test_publish_archives.py
```

---

### Task 7: Archive after direct-UPDATE backfills

`scripts/build/backfill_deep_block_rollups.py` rewrites `annotation_json` with its own `UPDATE` (≈line 160), bypassing `_publish_dict`.

**Files:**
- Modify: `scripts/build/backfill_deep_block_rollups.py`

- [ ] **Step 1: Read the update loop**

Run: `sed -n 120,200p scripts/build/backfill_deep_block_rollups.py`
Identify the loop variable holding the gene symbol and the `httpx.Client` (or `D1Client`) in scope after the `UPDATE`.

- [ ] **Step 2: Add the archive call right after each successful `UPDATE`**

```python
from accessible_surfaceome.cloud.surface_annotation import _maybe_archive  # top of file
...
                # Record history: this path writes D1 directly, so it must
                # archive for itself (publish_record would have).
                _maybe_archive(sym, client=http)
```

Use the script's own symbol and client names from Step 1. If the script has no `httpx.Client` in scope, open one: `with httpx.Client(timeout=30) as http:` around the loop.

- [ ] **Step 3: Verify it still imports and dry-runs**

Run: `uv run python scripts/build/backfill_deep_block_rollups.py --help`
Expected: usage text, exit 0.

- [ ] **Step 4: Commit**

```bash
git commit -m "fix(surface-proteome): archive to record history after the rollup backfill's direct D1 writes" -- scripts/build/backfill_deep_block_rollups.py
```

---

### Task 8: DDL apply script

**Files:**
- Create: `scripts/cloud/apply_record_history_ddl.py`

- [ ] **Step 1: Write the script**

```python
#!/usr/bin/env python3
"""Create the record-history tables in public D1 (dry-run by default).

    uv run python scripts/cloud/apply_record_history_ddl.py            # print
    uv run python scripts/cloud/apply_record_history_ddl.py --execute  # apply

Idempotent (CREATE ... IF NOT EXISTS). D1's HTTP API takes one statement
per call, so each DDL statement is sent separately.
"""

from __future__ import annotations

import argparse

from accessible_surfaceome.cloud.d1_client import D1Client
from accessible_surfaceome.cloud.record_history.store import DDL
from accessible_surfaceome.env import load_env


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--execute", action="store_true", help="apply to public D1")
    args = ap.parse_args()
    if not args.execute:
        for stmt in DDL:
            print(stmt.strip() + ";\n")
        print(f"[dry-run] {len(DDL)} statements; pass --execute to apply.")
        return
    load_env()
    with D1Client.public() as d1:
        for stmt in DDL:
            d1.query(stmt, [])
            print("applied:", stmt.split("(")[0].strip())


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Dry-run**

Run: `uv run python scripts/cloud/apply_record_history_ddl.py`
Expected: four statements printed, then `[dry-run] 4 statements; pass --execute to apply.`

- [ ] **Step 3: Commit**

```bash
git add scripts/cloud/apply_record_history_ddl.py
git commit -m "feat(surface-proteome): script to create the record-history tables in public D1" -- scripts/cloud/apply_record_history_ddl.py
```

---

### Task 9: Sweep script

**Files:**
- Create: `scripts/cloud/sweep_record_history.py`

- [ ] **Step 1: Write the script**

```python
#!/usr/bin/env python3
"""Archive what the API serves for every annotated gene (dry-run by default).

Run after any bulk deterministic-table sync (enrichment-only changes are
not caught by publish-time archiving) and as step 1 of every release.

    uv run python scripts/cloud/sweep_record_history.py                 # list genes
    uv run python scripts/cloud/sweep_record_history.py --execute
    uv run python scripts/cloud/sweep_record_history.py --execute --genes EGFR,CD63
"""

from __future__ import annotations

import argparse
import os
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx

from accessible_surfaceome.cloud.record_history.archive import (
    PUBLIC_API_BASE,
    BYPASS_HEADER,
    archive_gene,
)
from accessible_surfaceome.cloud.record_history.store import CloudRevisionStore
from accessible_surfaceome.cloud.surface_annotation import purge_paths
from accessible_surfaceome.env import load_env


def annotated_genes(http: httpx.Client, token: str) -> list[str]:
    resp = http.get(f"{PUBLIC_API_BASE}/v1/genes", headers={BYPASS_HEADER: token})
    resp.raise_for_status()
    return [g["gene_symbol"] for g in resp.json()["genes"]]


def sweep(genes: list[str] | None, *, execute: bool, workers: int) -> Counter[str]:
    load_env()
    token = os.environ.get("ARCHIVE_BYPASS_TOKEN", "").strip()
    counts: Counter[str] = Counter()
    with httpx.Client(timeout=60) as http:
        todo = genes or annotated_genes(http, token)
        if not execute:
            print(f"[dry-run] would archive {len(todo)} genes; pass --execute.")
            return counts
        with CloudRevisionStore.from_env() as store, ThreadPoolExecutor(workers) as pool:
            futs = {
                pool.submit(archive_gene, g, source="sweep", http=http, store=store, token=token): g
                for g in todo
            }
            for i, fut in enumerate(as_completed(futs), 1):
                g = futs[fut]
                try:
                    counts[fut.result().status] += 1
                except Exception as exc:  # noqa: BLE001 — report and keep sweeping
                    counts["failed"] += 1
                    print(f"FAILED {g}: {exc}")
                if i % 250 == 0:
                    print(f"{i}/{len(todo)} {dict(counts)}")
    if counts["created"]:
        purge_paths(["/v1/releases"])
    print(dict(counts))
    return counts


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--genes", help="comma-separated symbols (default: all annotated)")
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()
    genes = [g.strip() for g in args.genes.split(",")] if args.genes else None
    counts = sweep(genes, execute=args.execute, workers=args.workers)
    raise SystemExit(1 if counts["failed"] else 0)


if __name__ == "__main__":
    main()
```

Per-gene `/revisions` purges are skipped during a sweep (`purge=None` default) to spare purge quota on the shared zone; those lists are 60-second TTL and self-heal.

- [ ] **Step 2: Dry-run against the live gene list (read-only)**

Run: `uv run python scripts/cloud/sweep_record_history.py`
Expected: `[dry-run] would archive 5332 genes; pass --execute.` (count may differ slightly).

- [ ] **Step 3: Commit**

```bash
git add scripts/cloud/sweep_record_history.py
git commit -m "feat(surface-proteome): sweep script that archives every gene's served record" -- scripts/cloud/sweep_record_history.py
```

---

### Task 10: Releases — create, latest members, set DOI, export

**Files:**
- Create: `src/accessible_surfaceome/cloud/record_history/releases.py`
- Test: `tests/test_record_history_releases.py`

- [ ] **Step 1: Write the failing tests**

```python
"""Release rows, member batching, DOI immutability, and the export tarball."""

from __future__ import annotations

import json
import sqlite3
import tarfile
from pathlib import Path

import pytest

from accessible_surfaceome.cloud.record_history import releases as rel
from accessible_surfaceome.cloud.record_history.store import DDL


class SqliteD1:
    """D1Client stand-in backed by in-memory SQLite (same SQL dialect)."""

    def __init__(self) -> None:
        self.con = sqlite3.connect(":memory:")
        self.con.row_factory = sqlite3.Row
        for s in DDL:
            self.con.execute(s)
        self.con.execute("CREATE TABLE surface_annotation (gene_symbol TEXT)")

    def query(self, sql: str, params: list | None = None) -> list[dict]:
        cur = self.con.execute(sql, params or [])
        return [dict(r) for r in cur.fetchall()]


def _rev(d1: SqliteD1, sym: str, n: int, j: str) -> None:
    d1.query(
        "INSERT INTO record_revision VALUES (?,?,?,?,?,?,?,?,?,?)",
        [sym, f"HGNC:{sym}", n, j, None, None, "2026-09-27T00:00:00Z", "sweep", "2.14.4", "2.50.2"],
    )


def test_latest_members_only_live_genes_and_latest_revision() -> None:
    d1 = SqliteD1()
    _rev(d1, "A", 1, "a1")
    _rev(d1, "A", 2, "a2")
    _rev(d1, "GONE", 1, "g1")
    d1.query("INSERT INTO surface_annotation VALUES ('A')")
    assert rel.latest_members(d1) == [("A", 2)]


def test_create_release_batches_members_and_refuses_duplicates() -> None:
    d1 = SqliteD1()
    members = [(f"G{i}", 1) for i in range(70)]  # > one 33-row batch
    rel.create_release(d1, version="1.3.0", cut_at="2026-09-27T00:00:00Z",
                       github_tag="v1.3.0", zenodo_version_doi=None, notes=None, members=members)
    assert d1.query("SELECT n_genes FROM data_release")[0]["n_genes"] == 70
    assert d1.query("SELECT count(*) AS n FROM data_release_member")[0]["n"] == 70
    with pytest.raises(rel.ReleaseExistsError):
        rel.create_release(d1, version="1.3.0", cut_at="x", github_tag=None,
                           zenodo_version_doi=None, notes=None, members=members)


def test_member_batch_fits_d1_parameter_cap() -> None:
    assert rel.MEMBER_ROWS_PER_INSERT * 3 <= 100


def test_set_doi_only_once() -> None:
    d1 = SqliteD1()
    rel.create_release(d1, version="1.3.0", cut_at="t", github_tag=None,
                       zenodo_version_doi=None, notes=None, members=[("A", 1)])
    rel.set_zenodo_doi(d1, "1.3.0", "10.5281/zenodo.1")
    with pytest.raises(rel.ReleaseError):
        rel.set_zenodo_doi(d1, "1.3.0", "10.5281/zenodo.2")


def test_export_release_writes_parts_and_manifest(tmp_path: Path) -> None:
    d1 = SqliteD1()
    d1.query("INSERT INTO record_revision VALUES (?,?,?,?,?,?,?,?,?,?)",
             ["A", "HGNC:1", 1, "j", "e", "m", "t", "sweep", "2.14.4", "2.50.2"])
    rel.create_release(d1, version="1.3.0", cut_at="t", github_tag=None,
                       zenodo_version_doi=None, notes=None, members=[("A", 1)])
    blobs = {"records/sha256/j.json": b'{"r":1}', "records/sha256/e.json": b'{"e":1}',
             "records/sha256/m.md": b"# A"}
    out = rel.export_release(d1, "1.3.0", tmp_path, get_blob=blobs.__getitem__)
    assert out.name == "deep_dives_1.3.0.tar.gz"
    with tarfile.open(out) as tf:
        names = sorted(tf.getnames())
        manifest = tf.extractfile("manifest.tsv").read().decode()
        record = json.loads(tf.extractfile("genes/A.json").read())
    assert names == ["genes/A.evidence.json", "genes/A.json", "genes/A.md", "manifest.tsv"]
    assert manifest.splitlines()[1] == "A\tHGNC:1\t1\tj\te\tm"
    assert record == {"r": 1}
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest -q tests/test_record_history_releases.py`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement `releases.py`**

```python
"""Numbered data releases: fixed per-gene pointers into record history."""

from __future__ import annotations

import io
import tarfile
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

from accessible_surfaceome.cloud.record_history.store import blob_key

# 3 columns per member row; D1 caps a statement at 100 bound parameters.
MEMBER_ROWS_PER_INSERT = 100 // 3


class ReleaseError(RuntimeError):
    pass


class ReleaseExistsError(ReleaseError):
    pass


class _D1(Protocol):
    def query(self, sql: str, params: list[Any] | None = None) -> list[dict[str, Any]]: ...


def latest_members(d1: _D1) -> list[tuple[str, int]]:
    """(gene_symbol, latest revision) for every gene currently live."""
    rows = d1.query(
        "SELECT r.gene_symbol AS gene_symbol, MAX(r.revision) AS revision "
        "FROM record_revision r "
        "WHERE EXISTS (SELECT 1 FROM surface_annotation s "
        "               WHERE s.gene_symbol = r.gene_symbol COLLATE NOCASE) "
        "GROUP BY r.gene_symbol ORDER BY r.gene_symbol",
        [],
    )
    return [(r["gene_symbol"], int(r["revision"])) for r in rows]


def create_release(
    d1: _D1,
    *,
    version: str,
    cut_at: str,
    github_tag: str | None,
    zenodo_version_doi: str | None,
    notes: str | None,
    members: list[tuple[str, int]],
) -> None:
    if d1.query("SELECT 1 FROM data_release WHERE version = ?", [version]):
        raise ReleaseExistsError(f"release {version} already exists")
    d1.query(
        "INSERT INTO data_release (version, cut_at, github_tag, zenodo_version_doi, n_genes, notes) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        [version, cut_at, github_tag, zenodo_version_doi, len(members), notes],
    )
    for i in range(0, len(members), MEMBER_ROWS_PER_INSERT):
        chunk = members[i : i + MEMBER_ROWS_PER_INSERT]
        placeholders = ",".join(["(?, ?, ?)"] * len(chunk))
        params: list[Any] = []
        for sym, revision in chunk:
            params += [version, sym, revision]
        d1.query(
            f"INSERT INTO data_release_member (version, gene_symbol, revision) VALUES {placeholders}",
            params,
        )


def set_zenodo_doi(d1: _D1, version: str, doi: str) -> None:
    """Record the published Zenodo version DOI. Allowed exactly once."""
    rows = d1.query("SELECT zenodo_version_doi FROM data_release WHERE version = ?", [version])
    if not rows:
        raise ReleaseError(f"release {version} does not exist")
    if rows[0]["zenodo_version_doi"]:
        raise ReleaseError(f"release {version} already has DOI {rows[0]['zenodo_version_doi']}")
    d1.query("UPDATE data_release SET zenodo_version_doi = ? WHERE version = ?", [doi, version])


def export_release(
    d1: _D1,
    version: str,
    out_dir: Path,
    *,
    get_blob: Callable[[str], bytes],
) -> Path:
    """Write ``deep_dives_{version}.tar.gz`` from the release's archived parts.

    ``get_blob(key)`` must return the bytes or raise — a release export
    with a missing record is never acceptable.
    """
    rows = d1.query(
        "SELECT m.gene_symbol AS gene_symbol, r.hgnc_id AS hgnc_id, m.revision AS revision, "
        "       r.json_hash AS json_hash, r.evidence_hash AS evidence_hash, r.md_hash AS md_hash "
        "FROM data_release_member m JOIN record_revision r "
        "  ON r.gene_symbol = m.gene_symbol AND r.revision = m.revision "
        "WHERE m.version = ? ORDER BY m.gene_symbol",
        [version],
    )
    if not rows:
        raise ReleaseError(f"release {version} has no members")
    out = out_dir / f"deep_dives_{version}.tar.gz"
    lines = ["gene_symbol\thgnc_id\trevision\tjson_hash\tevidence_hash\tmd_hash"]

    def add(tf: tarfile.TarFile, name: str, data: bytes) -> None:
        info = tarfile.TarInfo(name)
        info.size = len(data)
        tf.addfile(info, io.BytesIO(data))

    with tarfile.open(out, "w:gz") as tf:
        for r in rows:
            sym = r["gene_symbol"]
            add(tf, f"genes/{sym}.json", get_blob(blob_key(r["json_hash"], "json")))
            if r["evidence_hash"]:
                add(tf, f"genes/{sym}.evidence.json", get_blob(blob_key(r["evidence_hash"], "json")))
            if r["md_hash"]:
                add(tf, f"genes/{sym}.md", get_blob(blob_key(r["md_hash"], "md")))
            lines.append("\t".join(str(r[k] or "") for k in
                                   ("gene_symbol", "hgnc_id", "revision", "json_hash", "evidence_hash", "md_hash")))
        add(tf, "manifest.tsv", ("\n".join(lines) + "\n").encode())
    return out
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest -q tests/test_record_history_releases.py`
Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(surface-proteome): numbered data releases — create, members, DOI, export" -- src/accessible_surfaceome/cloud/record_history/releases.py tests/test_record_history_releases.py
```

---

### Task 11: Zenodo draft new version

**Files:**
- Create: `src/accessible_surfaceome/cloud/record_history/zenodo.py`
- Test: `tests/test_record_history_zenodo.py`

- [ ] **Step 1: Write the failing test**

```python
"""Drafting a new Zenodo data-record version never publishes."""

from __future__ import annotations

from pathlib import Path

import httpx

from accessible_surfaceome.cloud.record_history.zenodo import create_draft_version

API = "https://zenodo.test/api"


def test_draft_version_flow(tmp_path: Path) -> None:
    tarball = tmp_path / "deep_dives_1.3.0.tar.gz"
    tarball.write_bytes(b"tgz")
    calls: list[tuple[str, str]] = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append((req.method, req.url.path))
        p = req.url.path
        if p == "/api/records/20805383/versions/latest":
            return httpx.Response(200, json={"id": 20805384})
        if p == "/api/deposit/depositions/20805384/actions/newversion":
            return httpx.Response(201, json={"links": {"latest_draft": f"{API}/deposit/depositions/999"}})
        if p == "/api/deposit/depositions/999" and req.method == "GET":
            return httpx.Response(200, json={
                "metadata": {"title": "t", "version": ""},
                "files": [
                    {"filename": "deep_dives_all.tar.gz", "links": {"self": f"{API}/files/old"}},
                    {"filename": "README.md", "links": {"self": f"{API}/files/readme"}},
                ],
                "links": {"bucket": f"{API}/files/bucket", "self": f"{API}/deposit/depositions/999",
                          "html": "https://zenodo.test/deposit/999"},
            })
        return httpx.Response(200, json={})

    http = httpx.Client(transport=httpx.MockTransport(handler))
    url = create_draft_version(token="t", tarball=tarball, version="1.3.0", http=http, api=API)

    assert url == "https://zenodo.test/deposit/999"
    assert ("DELETE", "/api/files/old") in calls           # old tarball replaced
    assert ("DELETE", "/api/files/readme") not in calls    # other files kept
    assert ("PUT", "/api/files/bucket/deep_dives_1.3.0.tar.gz") in calls
    assert ("PUT", "/api/deposit/depositions/999") in calls  # metadata
    assert not any("publish" in path for _, path in calls)
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest -q tests/test_record_history_zenodo.py`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement `zenodo.py`**

```python
"""Draft a new version of the Zenodo data record for a numbered release.

Deliberately stops at a DRAFT: publishing a Zenodo version is
irreversible, so a human reviews the draft (files, README, metadata) and
clicks Publish, then records the DOI with
``cut_data_release.py --set-doi``.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import httpx

ZENODO_API = "https://zenodo.org/api"
DATA_CONCEPT_RECID = "20805383"  # concept DOI 10.5281/zenodo.20805383


def create_draft_version(
    *,
    token: str,
    tarball: Path,
    version: str,
    http: httpx.Client,
    api: str = ZENODO_API,
) -> str:
    """Create the draft; return its web URL for review."""
    auth = {"access_token": token}
    latest = http.get(f"{api}/records/{DATA_CONCEPT_RECID}/versions/latest", follow_redirects=True)
    latest.raise_for_status()
    latest_id = latest.json()["id"]

    nv = http.post(f"{api}/deposit/depositions/{latest_id}/actions/newversion", params=auth)
    nv.raise_for_status()
    draft_url = nv.json()["links"]["latest_draft"]
    draft = http.get(draft_url, params=auth)
    draft.raise_for_status()
    d = draft.json()

    # The new version inherits the previous version's files; replace only
    # the deep-dive tarball. Triage TSVs + README carry over (refresh them
    # by hand in the draft if they changed).
    for f in d.get("files", []):
        if f["filename"].startswith("deep_dives"):
            http.delete(f["links"]["self"], params=auth).raise_for_status()
    with tarball.open("rb") as fh:
        http.put(f"{d['links']['bucket']}/{tarball.name}", params=auth, content=fh.read()).raise_for_status()

    meta = dict(d["metadata"])
    meta["version"] = version
    meta["publication_date"] = date.today().isoformat()
    http.put(d["links"]["self"], params=auth, json={"metadata": meta}).raise_for_status()
    return d["links"]["html"]
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest -q tests/test_record_history_zenodo.py`
Expected: `1 passed`

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(surface-proteome): draft a new Zenodo data-record version per release" -- src/accessible_surfaceome/cloud/record_history/zenodo.py tests/test_record_history_zenodo.py
```

---

### Task 12: Seed script (revision 1 + release 1.0.0 from Zenodo)

**Files:**
- Create: `scripts/cloud/seed_record_history.py`

- [ ] **Step 1: Write the script**

```python
#!/usr/bin/env python3
"""One-off: seed record history from the 2026-08-15 Zenodo deposit.

Writes each record in deep_dives_all.tar.gz (Zenodo record 20805384) as
revision 1 (source seed:zenodo-1.0.0, evidence inline, no .md), then
creates data release 1.0.0 over them. Refuses if record_revision already
has rows. Run the sweep afterwards: changed genes get revision 2, genes
annotated after 2026-08-15 start at revision 1.

    uv run python scripts/cloud/seed_record_history.py --tarball PATH             # dry-run
    uv run python scripts/cloud/seed_record_history.py --tarball PATH --execute

Download the tarball first (116 MB, gitignored location):
    curl -L -o data/external/zenodo/deep_dives_all_1.0.0.tar.gz \\
      "https://zenodo.org/records/20805384/files/deep_dives_all.tar.gz?download=1"
"""

from __future__ import annotations

import argparse
import json
import tarfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from accessible_surfaceome.cloud.record_history.hashing import content_hash_record
from accessible_surfaceome.cloud.record_history.releases import create_release
from accessible_surfaceome.cloud.record_history.store import CloudRevisionStore, blob_key
from accessible_surfaceome.env import load_env

SEED_SOURCE = "seed:zenodo-1.0.0"
SEED_AT = "2026-08-15T00:00:00Z"
SEED_DOI = "10.5281/zenodo.20805384"


def read_records(tarball: Path) -> list[tuple[str, bytes, dict]]:
    out = []
    with tarfile.open(tarball) as tf:
        for m in tf.getmembers():
            if not (m.isfile() and m.name.endswith(".json")):
                continue
            raw = tf.extractfile(m).read()  # type: ignore[union-attr]
            rec = json.loads(raw)
            out.append((rec["gene"]["hgnc_symbol"], raw, rec))
    return sorted(out, key=lambda t: t[0])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tarball", type=Path, required=True)
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()

    records = read_records(args.tarball)
    print(f"{len(records)} records in {args.tarball.name}")
    if not args.execute:
        print("[dry-run] pass --execute to write revision 1 + release 1.0.0")
        return

    load_env()
    with CloudRevisionStore.from_env() as store:
        if store.d1.query("SELECT 1 FROM record_revision LIMIT 1", []):
            raise SystemExit("record_revision is not empty — refusing to seed twice")

        def put(item: tuple[str, bytes, dict]) -> None:
            _, raw, rec = item
            store.put_blob(blob_key(content_hash_record(rec), "json"), raw, "application/json")

        with ThreadPoolExecutor(8) as pool:
            list(pool.map(put, records))
        print("R2 blobs written")

        members: list[tuple[str, int]] = []
        for sym, _, rec in records:
            rev = store.insert_revision([
                sym, rec["gene"].get("hgnc_id"), content_hash_record(rec), None, None,
                SEED_AT, SEED_SOURCE, rec.get("schema_version"), rec.get("prompt_corpus_version"),
            ])
            if rev != 1:
                raise SystemExit(f"{sym}: expected revision 1, got {rev}")
            members.append((sym, 1))
        create_release(
            store.d1, version="1.0.0", cut_at=SEED_AT, github_tag=None,
            zenodo_version_doi=SEED_DOI,
            notes="Initial data deposit (Zenodo record 20805384); records as deposited, evidence inline, no Markdown.",
            members=members,
        )
    print(f"seeded {len(members)} genes; release 1.0.0 created. Now run sweep_record_history.py --execute")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Download the tarball and dry-run**

```bash
mkdir -p data/external/zenodo
curl -L -o data/external/zenodo/deep_dives_all_1.0.0.tar.gz "https://zenodo.org/records/20805384/files/deep_dives_all.tar.gz?download=1"
uv run python scripts/cloud/seed_record_history.py --tarball data/external/zenodo/deep_dives_all_1.0.0.tar.gz
```

Expected: `5130 records in deep_dives_all_1.0.0.tar.gz` then the dry-run line. Confirm `git status` does not list the tarball (`data/external/` must be gitignored; if it is not, move the file to the scratchpad instead).

- [ ] **Step 3: Commit**

```bash
git add scripts/cloud/seed_record_history.py
git commit -m "feat(surface-proteome): one-off seed of record history + release 1.0.0 from Zenodo" -- scripts/cloud/seed_record_history.py
```

---

### Task 13: Release-cut script

**Files:**
- Create: `scripts/release/cut_data_release.py`

- [ ] **Step 1: Write the script**

```python
#!/usr/bin/env python3
"""Cut a numbered data release (dry-run by default).

    uv run python scripts/release/cut_data_release.py --version 1.3.0              # plan
    uv run python scripts/release/cut_data_release.py --version 1.3.0 --execute    # cut + draft Zenodo
    uv run python scripts/release/cut_data_release.py --set-doi 1.3.0 10.5281/zenodo.NNN

--execute: (1) refuses unless pyproject.toml says the same version,
(2) sweeps every gene, (3) writes the release + members (immutable),
(4) exports deep_dives_X.Y.Z.tar.gz from R2, (5) creates a DRAFT new
version of the Zenodo data record. Then YOU review + publish the draft on
Zenodo, run --set-doi with the version DOI, and create GitHub release vX.Y.Z.
"""

from __future__ import annotations

import argparse
import dataclasses
import os
import re
import sys
import tomllib
from datetime import UTC, datetime
from pathlib import Path

import httpx

from accessible_surfaceome.cloud import r2_client
from accessible_surfaceome.cloud.d1_client import D1Client
from accessible_surfaceome.cloud.r2_client import R2Config
from accessible_surfaceome.cloud.record_history import releases as rel
from accessible_surfaceome.cloud.record_history.store import BUCKET
from accessible_surfaceome.cloud.record_history.zenodo import create_draft_version
from accessible_surfaceome.cloud.surface_annotation import purge_paths
from accessible_surfaceome.env import load_env

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "cloud"))
from sweep_record_history import sweep  # noqa: E402

VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")


def pyproject_version() -> str:
    return tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--version")
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--set-doi", nargs=2, metavar=("VERSION", "DOI"))
    ap.add_argument("--out-dir", type=Path, default=ROOT / "data" / "external" / "zenodo")
    args = ap.parse_args()
    load_env()

    if args.set_doi:
        version, doi = args.set_doi
        with D1Client.public() as d1:
            rel.set_zenodo_doi(d1, version, doi)
        purge_paths(["/v1/releases", f"/v1/releases/{version}"])
        print(f"release {version} → {doi}")
        return

    version = (args.version or "").removeprefix("v")
    if not VERSION_RE.match(version):
        raise SystemExit("--version must look like 1.3.0")
    if pyproject_version() != version:
        raise SystemExit(f"pyproject.toml says {pyproject_version()}, not {version} — bump it first")
    if not args.execute:
        print(f"[dry-run] would sweep, cut release {version}, export, and draft a Zenodo version.")
        return

    counts = sweep(None, execute=True, workers=8)
    if counts["failed"]:
        raise SystemExit(f"sweep had {counts['failed']} failures — fix and re-run before cutting")

    with D1Client.public() as d1:
        members = rel.latest_members(d1)
        rel.create_release(
            d1, version=version, cut_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            github_tag=f"v{version}", zenodo_version_doi=None, notes=None, members=members,
        )
        print(f"release {version}: {len(members)} genes")
        r2cfg = dataclasses.replace(R2Config.from_env(), bucket=BUCKET)

        def get_blob(key: str) -> bytes:
            data = r2_client.get_object(key=key, cfg=r2cfg)
            if data is None:
                raise SystemExit(f"archived object missing: {key}")
            return data

        args.out_dir.mkdir(parents=True, exist_ok=True)
        tarball = rel.export_release(d1, version, args.out_dir, get_blob=get_blob)
    purge_paths(["/v1/releases"])
    print(f"exported {tarball}")

    token = os.environ.get("ZENODO_TOKEN", "").strip()
    if not token:
        print("ZENODO_TOKEN unset — upload the tarball as a new version by hand.")
        return
    with httpx.Client(timeout=900) as http:
        url = create_draft_version(token=token, tarball=tarball, version=version, http=http)
    print(f"Zenodo DRAFT: {url}\nReview + publish it, then: --set-doi {version} <version DOI>")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Dry-run**

Run: `uv run python scripts/release/cut_data_release.py --version 1.2.0`
Expected: `[dry-run] would sweep, cut release 1.2.0, export, and draft a Zenodo version.`
Run: `uv run python scripts/release/cut_data_release.py --version 1.3.0`
Expected: exits with `pyproject.toml says 1.2.0, not 1.3.0 — bump it first`.

- [ ] **Step 3: Commit**

```bash
git add scripts/release/cut_data_release.py
git commit -m "feat(surface-proteome): cut_data_release — sweep, release rows, export, Zenodo draft" -- scripts/release/cut_data_release.py
```

---

### Task 14: Worker — archive bypass + history endpoints

**Files:**
- Modify: `cloudflare/workers/surfaceome_api/src/index.js`
- Modify: `cloudflare/workers/surfaceome_api/wrangler.toml.example`
- Test: `tests/test_worker_record_history.py`

- [ ] **Step 1: Write the failing Worker test**

```python
"""Exercise the record-history routes of the real Worker router offline."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest


def test_record_history_routes(tmp_path: Path) -> None:
    node = shutil.which("node")
    if node is None:
        if os.environ.get("REQUIRE_WORKER_NODE") == "1":
            pytest.fail("Shared API compatibility checks require Node; refusing to skip")
        pytest.skip("Node is required for Worker tests")
    root = Path(__file__).resolve().parents[1]
    source = (root / "cloudflare/workers/surfaceome_api/src/index.js").read_text()
    source = source.replace(
        'import { deepDiveTier, isLowLiteratureSurface } from "../../../../viewer/lib/catalog-presets";',
        "const deepDiveTier = () => ({tier: 'no', facet: null}); const isLowLiteratureSurface = () => false;",
    )
    (tmp_path / "worker.mjs").write_text(source)
    (tmp_path / "test.mjs").write_text(r'''
import assert from "node:assert/strict";
import worker from "./worker.mjs";

let cacheReads = 0;
globalThis.caches = { default: { match: async () => { cacheReads++; return undefined; }, put: async () => {} } };

const revisions = [
  { gene_symbol: "EGFR", hgnc_id: "HGNC:3236", revision: 1, published_at: "2026-08-15T00:00:00Z",
    source: "seed:zenodo-1.0.0", json_hash: "j1", evidence_hash: null, md_hash: null,
    schema_version: "2.14.2", prompt_corpus_version: "2.50.2" },
  { gene_symbol: "EGFR", hgnc_id: "HGNC:3236", revision: 2, published_at: "2026-09-27T00:00:00Z",
    source: "sweep", json_hash: "j2", evidence_hash: "e2", md_hash: "m2",
    schema_version: "2.14.4", prompt_corpus_version: "2.50.2" },
];
const releases = [{ version: "1.0.0", cut_at: "2026-08-15T00:00:00Z", github_tag: null,
  zenodo_version_doi: "10.5281/zenodo.20805384", n_genes: 1, notes: null }];
const members = [{ version: "1.0.0", gene_symbol: "EGFR", revision: 1 }];
const blobs = { "records/sha256/j1.json": '{"v":1}', "records/sha256/j2.json": '{"v":2}',
                "records/sha256/e2.json": '{"evidence":[]}', "records/sha256/m2.md": "# EGFR" };

const up = (s) => (s || "").toUpperCase();
const env = {
  ARCHIVE_BYPASS_TOKEN: "secret",
  RECORD_HISTORY: { async get(key) { return key in blobs ? { body: blobs[key] } : null; } },
  DB: { prepare(sql) { let a = []; return {
    bind(...v) { a = v; return this; },
    async first() {
      if (sql.includes("FROM data_release_member m") && sql.includes("JOIN record_revision")) {
        const mem = members.find(m => m.version === a[0] && up(m.gene_symbol) === up(a[1]));
        return mem ? revisions.find(r => r.revision === mem.revision) : null;
      }
      if (sql.includes("FROM data_release")) return releases.find(r => r.version === a[0]) || null;
      if (sql.includes("FROM record_revision"))
        return revisions.find(r => up(r.gene_symbol) === up(a[0]) && r.revision === a[1]) || null;
      return null;
    },
    async all() {
      if (sql.includes("FROM record_revision r") && sql.includes("ORDER BY r.revision DESC")) {
        const rows = revisions.filter(r => up(r.gene_symbol) === up(a[0])).slice().reverse();
        return { results: rows.map(r => ({ ...r, releases: JSON.stringify(
          members.filter(m => m.revision === r.revision).map(m => ({
            version: m.version, zenodo_version_doi: releases[0].zenodo_version_doi }))) })) };
      }
      if (sql.includes("FROM data_release_member m")) return { results: members.map(m => ({
        gene_symbol: m.gene_symbol, hgnc_id: "HGNC:3236", revision: m.revision, json_hash: "j1",
        evidence_hash: null, md_hash: null })) };
      if (sql.includes("FROM data_release")) return { results: releases };
      return { results: [] };
    },
  }; } },
};
async function call(path, headers = {}) {
  const pending = [];
  const r = await worker.fetch(new Request("https://api.deliverome.org/surfaceome" + path, { headers }),
    env, { waitUntil(p) { pending.push(p); } });
  await Promise.all(pending);
  return r;
}

// revision list
const list = await (await call("/v1/genes/egfr/revisions")).json();
assert.equal(list.current_revision, 2);
assert.deepEqual(list.revisions.map(r => r.revision), [2, 1]);
assert.equal(list.revisions[1].releases[0].version, "1.0.0");
assert.equal(list.revisions[1].evidence_url, null);
assert.match(list.revisions[0].url, /\/v1\/genes\/EGFR\/revisions\/2$/);

// revision bodies
let r = await call("/v1/genes/EGFR/revisions/2");
assert.equal(r.status, 200);
assert.equal(await r.text(), '{"v":2}');
assert.equal(r.headers.get("ETag"), '"j2"');
assert.equal(r.headers.get("X-Surfaceome-Revision"), "2");
assert.match(r.headers.get("Cache-Control"), /immutable/);
assert.equal(await (await call("/v1/genes/EGFR/revisions/2/evidence")).text(), '{"evidence":[]}');
r = await call("/v1/genes/EGFR/revisions/2.md");
assert.equal(await r.text(), "# EGFR");
assert.match(r.headers.get("Content-Type"), /text\/markdown/);
assert.equal((await (await call("/v1/genes/EGFR/revisions/1/evidence")).json()).error, "evidence_not_archived");
assert.equal((await (await call("/v1/genes/EGFR/revisions/1.md")).json()).error, "markdown_not_archived");
assert.equal((await (await call("/v1/genes/EGFR/revisions/9")).json()).error, "revision_not_found");
assert.equal((await call("/v1/genes/EGFR/revisions/0")).status, 400);
assert.equal((await (await call("/v1/genes/NOPE/revisions")).json()).error, "gene_not_annotated");

// missing R2 object never falls back to live
delete blobs["records/sha256/j1.json"];
r = await call("/v1/genes/EGFR/revisions/1");
assert.equal(r.status, 500);
assert.equal((await r.json()).error, "archive_body_missing");
blobs["records/sha256/j1.json"] = '{"v":1}';

// releases
const rl = await (await call("/v1/releases")).json();
assert.equal(rl.releases[0].version, "1.0.0");
const one = await (await call("/v1/releases/v1.0.0")).json();   // v-prefix normalized
assert.equal(one.version, "1.0.0");
assert.equal(one.members[0].gene_symbol, "EGFR");
assert.equal((await call("/v1/releases/one")).status, 400);
assert.equal((await (await call("/v1/releases/9.9.9")).json()).error, "release_not_found");
assert.equal(await (await call("/v1/releases/1.0.0/genes/egfr")).text(), '{"v":1}');
assert.equal((await (await call("/v1/releases/1.0.0/genes/CD63")).json()).error, "gene_not_in_release");

// archive bypass skips the caches only with the right secret
cacheReads = 0;
await call("/v1/genes/EGFR/revisions", { "X-Archive-Bypass": "wrong" });
assert.equal(cacheReads, 1);
cacheReads = 0;
await call("/v1/genes/EGFR/revisions", { "X-Archive-Bypass": "secret" });
assert.equal(cacheReads, 0);

// index lists the new endpoints
const idx = await (await call("/v1")).json();
const paths = idx.endpoints.map(e => e.path);
for (const p of ["/v1/genes/{symbol}/revisions", "/v1/genes/{symbol}/revisions/{n}",
                 "/v1/releases", "/v1/releases/{version}", "/v1/releases/{version}/genes/{symbol}"])
  assert(paths.includes(p), p);
console.log("ok");
''')
    out = subprocess.run([node, str(tmp_path / "test.mjs")], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr + out.stdout
    assert out.stdout.strip().endswith("ok")
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest -q tests/test_worker_record_history.py`
Expected: FAIL (assertion on `/v1/genes/egfr/revisions` — currently routed to `handleGene`'s 404 or `route_not_found`).

- [ ] **Step 3: Implement in `index.js`**

(a) After `function checkSymbol` add:

```js
// --- Record history (spec docs/superpowers/specs/2026-09-27-record-history-design.md) ---
// Archived bodies live write-once in the RECORD_HISTORY R2 bucket, named by
// content hash, so they are cacheable forever. They are read straight from
// R2 rather than through withEdgeCache, which would rebuild the response
// with only Content-Type + Cache-Control and drop ETag / X-Surfaceome-*.
const CACHE_TTL_IMMUTABLE = 31536000;  // 1 year
const RELEASE_VERSION_OK = /^v?(\d+\.\d+\.\d+)$/;
const REVISION_OK = /^[1-9]\d{0,5}$/;
const HISTORY_BASE = "https://api.deliverome.org/surfaceome/v1";
const REVISION_PARTS = {
  record:   { col: "json_hash",     ext: "json", ct: "application/json; charset=utf-8" },
  evidence: { col: "evidence_hash", ext: "json", ct: "application/json; charset=utf-8", missing: "evidence_not_archived" },
  md:       { col: "md_hash",       ext: "md",   ct: "text/markdown; charset=utf-8",   missing: "markdown_not_archived" },
};

// The archiver (accessible_surfaceome.cloud.record_history) must see the
// current D1 state, not a cached copy, and sweeps ~5k genes from one IP.
// A request carrying the ARCHIVE_BYPASS_TOKEN secret skips both cache tiers
// and the rate limiter. Without the exact secret nothing changes.
function isArchiveBypass(request, env) {
  const token = env?.ARCHIVE_BYPASS_TOKEN;
  return Boolean(token) && request.headers.get("X-Archive-Bypass") === token;
}

function normalizeVersion(v) {
  const m = RELEASE_VERSION_OK.exec(v || "");
  return m ? m[1] : null;
}

async function archivedPart(env, row, part) {
  const p = REVISION_PARTS[part];
  const hash = row[p.col];
  if (!hash) return notFound(p.missing);
  if (!env.RECORD_HISTORY) return json({ error: "history_unavailable" }, { status: 503, ttl: 0 });
  const obj = await env.RECORD_HISTORY.get(`records/sha256/${hash}.${p.ext}`);
  if (!obj) return json({ error: "archive_body_missing" }, { status: 500, ttl: 0 });
  return new Response(obj.body, {
    status: 200,
    headers: {
      "Content-Type": p.ct,
      "Cache-Control": `public, max-age=${CACHE_TTL_IMMUTABLE}, s-maxage=${CACHE_TTL_IMMUTABLE}, immutable`,
      "ETag": `"${hash}"`,
      "X-Surfaceome-Revision": String(row.revision),
      "X-Surfaceome-Content-Hash": hash,
      ...CORS_HEADERS,
    },
  });
}

async function handleRevisionList(env, symbol) {
  const sym = checkSymbol(symbol);
  if (!sym) return badRequest("invalid_symbol");
  const { results } = await env.DB.prepare(
    `SELECT r.gene_symbol, r.hgnc_id, r.revision, r.published_at, r.source,
            r.json_hash, r.evidence_hash, r.md_hash, r.schema_version, r.prompt_corpus_version,
            (SELECT json_group_array(json_object('version', m.version,
                                                 'zenodo_version_doi', d.zenodo_version_doi))
               FROM data_release_member m JOIN data_release d ON d.version = m.version
              WHERE m.gene_symbol = r.gene_symbol COLLATE NOCASE AND m.revision = r.revision) AS releases
       FROM record_revision r
      WHERE r.gene_symbol = ? COLLATE NOCASE
      ORDER BY r.revision DESC`
  ).bind(sym).all();
  if (!results.length) return notFound("gene_not_annotated");
  const g = results[0];
  const base = `${HISTORY_BASE}/genes/${g.gene_symbol}/revisions`;
  return json({
    gene_symbol: g.gene_symbol,
    hgnc_id: g.hgnc_id,
    current_revision: g.revision,
    revisions: results.map((r) => ({
      revision: r.revision,
      published_at: r.published_at,
      source: r.source,
      json_hash: r.json_hash,
      evidence_hash: r.evidence_hash,
      md_hash: r.md_hash,
      schema_version: r.schema_version,
      prompt_corpus_version: r.prompt_corpus_version,
      releases: r.releases ? JSON.parse(r.releases) : [],
      url: `${base}/${r.revision}`,
      evidence_url: r.evidence_hash ? `${base}/${r.revision}/evidence` : null,
      md_url: r.md_hash ? `${base}/${r.revision}.md` : null,
    })),
  });
}

async function handleRevisionBody(env, symbol, n, part) {
  const sym = checkSymbol(symbol);
  if (!sym) return badRequest("invalid_symbol");
  if (!REVISION_OK.test(n)) return badRequest("invalid_revision");
  const row = await env.DB.prepare(
    `SELECT revision, json_hash, evidence_hash, md_hash FROM record_revision
      WHERE gene_symbol = ? COLLATE NOCASE AND revision = ?`
  ).bind(sym, Number(n)).first();
  if (!row) return notFound("revision_not_found");
  return archivedPart(env, row, part);
}

async function handleReleaseList(env) {
  const { results } = await env.DB.prepare(
    `SELECT version, cut_at, github_tag, zenodo_version_doi, n_genes, notes
       FROM data_release ORDER BY cut_at DESC`
  ).all();
  return json({ releases: results });
}

async function handleRelease(env, ver) {
  const v = normalizeVersion(ver);
  if (!v) return badRequest("invalid_version");
  const rel = await env.DB.prepare(
    `SELECT version, cut_at, github_tag, zenodo_version_doi, n_genes, notes
       FROM data_release WHERE version = ?`
  ).bind(v).first();
  if (!rel) return notFound("release_not_found");
  const { results } = await env.DB.prepare(
    `SELECT m.gene_symbol, r.hgnc_id, m.revision, r.json_hash, r.evidence_hash, r.md_hash
       FROM data_release_member m
       JOIN record_revision r ON r.gene_symbol = m.gene_symbol AND r.revision = m.revision
      WHERE m.version = ? ORDER BY m.gene_symbol`
  ).bind(v).all();
  // Immutable once its Zenodo version is published; until then a short TTL
  // so --set-doi shows up promptly.
  const ttl = rel.zenodo_version_doi ? CACHE_TTL_IMMUTABLE : CACHE_TTL_SHORT;
  return json({ ...rel, members: results }, { ttl });
}

async function handleReleaseGene(env, ver, symbol, part) {
  const v = normalizeVersion(ver);
  if (!v) return badRequest("invalid_version");
  const sym = checkSymbol(symbol);
  if (!sym) return badRequest("invalid_symbol");
  const rel = await env.DB.prepare(`SELECT version FROM data_release WHERE version = ?`).bind(v).first();
  if (!rel) return notFound("release_not_found");
  const row = await env.DB.prepare(
    `SELECT r.revision, r.json_hash, r.evidence_hash, r.md_hash
       FROM data_release_member m
       JOIN record_revision r ON r.gene_symbol = m.gene_symbol AND r.revision = m.revision
      WHERE m.version = ? AND m.gene_symbol = ? COLLATE NOCASE`
  ).bind(v, sym).first();
  if (!row) return notFound("gene_not_in_release");
  return archivedPart(env, row, part);
}
```

(b) In `checkRate`, after the `BUILD_BYPASS_TOKEN` check:

```js
  if (isArchiveBypass(request, env)) return null;
```

and extend the heavy test:

```js
  const heavy = path === "/v1/catalog" || path.endsWith(".tsv") || /^\/v1\/releases\/[^/]+$/.test(path);
```

(c) First lines of `withEdgeCache`:

```js
  // Archiver reads the live state: no cache read, no cache write.
  if (isArchiveBypass(request, env)) return handler();
```

(d) In the router, immediately **before** the existing `.md` route (`/^\/v1\/genes\/([^/]+)\.md$/`):

```js
    // Record history — more specific than every /v1/genes/{sym}… route below.
    if ((m = path.match(/^\/v1\/genes\/([^/]+)\/revisions$/))) return withEdgeCache(request, env, ctx, () => handleRevisionList(env, m[1]));
    if ((m = path.match(/^\/v1\/genes\/([^/]+)\/revisions\/([^/]+)\.md$/))) return handleRevisionBody(env, m[1], m[2], "md");
    if ((m = path.match(/^\/v1\/genes\/([^/]+)\/revisions\/([^/]+)\/evidence$/))) return handleRevisionBody(env, m[1], m[2], "evidence");
    if ((m = path.match(/^\/v1\/genes\/([^/]+)\/revisions\/([^/]+)$/))) return handleRevisionBody(env, m[1], m[2], "record");
    if ((m = path.match(/^\/v1\/releases\/([^/]+)\/genes\/([^/]+)\.md$/))) return handleReleaseGene(env, m[1], m[2], "md");
    if ((m = path.match(/^\/v1\/releases\/([^/]+)\/genes\/([^/]+)\/evidence$/))) return handleReleaseGene(env, m[1], m[2], "evidence");
    if ((m = path.match(/^\/v1\/releases\/([^/]+)\/genes\/([^/]+)$/))) return handleReleaseGene(env, m[1], m[2], "record");
    if ((m = path.match(/^\/v1\/releases\/([^/]+)$/))) return withEdgeCache(request, env, ctx, () => handleRelease(env, m[1]));
```

and next to the other exact-path routes (after `/v1/meta/sizes`):

```js
    if (path === "/v1/releases") return withEdgeCache(request, env, ctx, () => handleReleaseList(env));
```

(e) In the endpoint index array, after the `/v1/genes/{symbol}.md` entry:

```js
  { group: "History", method: "GET", path: "/v1/genes/{symbol}/revisions", summary: "Every archived revision of this gene's served record (newest first), with the releases each belongs to" },
  { group: "History", method: "GET", path: "/v1/genes/{symbol}/revisions/{n}", summary: "Revision n of the record, byte-for-byte as served; also /evidence and .md" },
  { group: "History", method: "GET", path: "/v1/releases", summary: "Numbered data releases with their GitHub tag and Zenodo version DOI" },
  { group: "History", method: "GET", path: "/v1/releases/{version}", summary: "One release: metadata + the revision of every gene in it" },
  { group: "History", method: "GET", path: "/v1/releases/{version}/genes/{symbol}", summary: "A gene as it was in that release; also /evidence and .md" },
```

(f) `wrangler.toml.example`, after the `GENE_MD` block:

```toml
# Record history (write-once, content-addressed). Read-only here; written by
# accessible_surfaceome.cloud.record_history. Create once with:
#   npx --yes wrangler r2 bucket create surfaceome-record-history
# The archiver's cache/rate-limit bypass secret is set separately:
#   npx --yes wrangler secret put ARCHIVE_BYPASS_TOKEN
[[r2_buckets]]
binding = "RECORD_HISTORY"
bucket_name = "surfaceome-record-history"
```

- [ ] **Step 4: Run the new and existing Worker/purge tests**

Run: `uv run pytest -q tests/test_worker_record_history.py tests/test_worker_internalization.py tests/test_worker_evidence_split.py tests/test_worker_response_shape.py tests/test_cohort_cache_purge.py`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(surface-proteome): record-history + release endpoints on the public Worker" -- cloudflare/workers/surfaceome_api/src/index.js cloudflare/workers/surfaceome_api/wrangler.toml.example tests/test_worker_record_history.py
```

---

### Task 15: Viewer citation strip

**Files:**
- Create: `viewer/lib/revisions.ts`
- Create: `viewer/components/surfaceome/RevisionStrip/RevisionStrip.tsx`, `RevisionStrip.module.css`
- Modify: `viewer/app/gene/page.tsx` (`ReadyData`, first `setState`, secondary `Promise.all`)
- Modify: `viewer/components/surfaceome/GeneDetail/GeneDetail.tsx` (props + render after `</nav>`)
- Test: `viewer/tests/revision_strip.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
/*
 *   npx --yes tsx --import ./tests/helpers/register.mjs --test tests/revision_strip.test.tsx
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { parseRevisions } from "../lib/revisions";
import { RevisionStrip } from "../components/surfaceome/RevisionStrip/RevisionStrip";

const payload = {
  gene_symbol: "EGFR",
  hgnc_id: "HGNC:3236",
  current_revision: 2,
  revisions: [
    { revision: 2, published_at: "2026-09-27T10:00:00Z", source: "sweep",
      releases: [{ version: "1.3.0", zenodo_version_doi: "10.5281/zenodo.999" }],
      url: "https://api.deliverome.org/surfaceome/v1/genes/EGFR/revisions/2" },
    { revision: 1, published_at: "2026-08-15T00:00:00Z", source: "seed:zenodo-1.0.0",
      releases: [], url: "https://api.deliverome.org/surfaceome/v1/genes/EGFR/revisions/1" },
  ],
};

test("parseRevisions rejects junk", () => {
  assert.equal(parseRevisions(null), null);
  assert.equal(parseRevisions({ error: "gene_not_annotated" }), null);
  assert.equal(parseRevisions(payload)?.current.revision, 2);
});

test("strip shows revision, date, release, citation and history links", () => {
  const html = renderToStaticMarkup(
    React.createElement(RevisionStrip, { revisions: parseRevisions(payload)! }),
  );
  assert.match(html, /Revision 2/);
  assert.match(html, /2026-09-27/);
  assert.match(html, /release v1\.3\.0/);
  assert.match(html, /href="https:\/\/api\.deliverome\.org\/surfaceome\/v1\/genes\/EGFR\/revisions\/2"/);
  assert.match(html, /href="https:\/\/doi\.org\/10\.5281\/zenodo\.999"/);
  assert.match(html, /revisions"[^>]*>All revisions/);
});

test("strip omits the release when the revision is in none", () => {
  const p = { ...payload, current_revision: 1, revisions: [payload.revisions[1]] };
  const html = renderToStaticMarkup(React.createElement(RevisionStrip, { revisions: parseRevisions(p)! }));
  assert.doesNotMatch(html, /release v/);
  assert.doesNotMatch(html, /doi\.org/);
});
```

- [ ] **Step 2: Run to verify failure**

Run: `cd viewer && npx --yes tsx --import ./tests/helpers/register.mjs --test tests/revision_strip.test.tsx`
Expected: FAIL — cannot resolve `../lib/revisions`.

- [ ] **Step 3: Implement**

`viewer/lib/revisions.ts`:

```ts
/** `/v1/genes/{sym}/revisions` payload — see the record-history spec. */
export interface RevisionRelease {
  version: string;
  zenodo_version_doi: string | null;
}

export interface RevisionEntry {
  revision: number;
  published_at: string;
  source: string;
  releases: RevisionRelease[];
  url: string;
}

export interface Revisions {
  geneSymbol: string;
  current: RevisionEntry;
  listUrl: string;
}

export function parseRevisions(json: unknown): Revisions | null {
  if (!json || typeof json !== "object") return null;
  const p = json as { gene_symbol?: string; current_revision?: number; revisions?: RevisionEntry[] };
  if (!p.gene_symbol || !Array.isArray(p.revisions) || !p.revisions.length) return null;
  const current = p.revisions.find((r) => r.revision === p.current_revision) ?? p.revisions[0];
  return {
    geneSymbol: p.gene_symbol,
    current,
    listUrl: current.url.replace(/\/\d+$/, ""),
  };
}
```

`viewer/components/surfaceome/RevisionStrip/RevisionStrip.tsx`:

```tsx
import type { Revisions } from "../../../lib/revisions";
import styles from "./RevisionStrip.module.css";

/** One-line "cite this version" strip for the gene page (record history). */
export function RevisionStrip({ revisions }: { revisions: Revisions }) {
  const { current, listUrl } = revisions;
  const release = current.releases[0];
  return (
    <p className={styles.strip}>
      <span>{`Revision ${current.revision}`}</span>
      <span aria-hidden="true"> · </span>
      <span>{`published ${current.published_at.slice(0, 10)}`}</span>
      {release ? (
        <>
          <span aria-hidden="true"> · </span>
          <span>{`in release v${release.version}`}</span>
        </>
      ) : null}
      <span aria-hidden="true"> · </span>
      <a href={current.url} target="_blank" rel="noopener noreferrer"
         data-hint="Permanent link to exactly this version of the record. It never changes, even after the record is updated.">
        Cite this version
      </a>
      {release?.zenodo_version_doi ? (
        <>
          {" ("}
          <a href={`https://doi.org/${release.zenodo_version_doi}`} target="_blank" rel="noopener noreferrer">
            {release.zenodo_version_doi}
          </a>
          {")"}
        </>
      ) : null}
      <span aria-hidden="true"> · </span>
      <a href={listUrl} target="_blank" rel="noopener noreferrer">All revisions</a>
    </p>
  );
}
```

Note the test's last regex expects `href="…/revisions"` immediately followed by other attributes then `>All revisions`; `listUrl` ends in `/revisions`, which satisfies it.

`viewer/components/surfaceome/RevisionStrip/RevisionStrip.module.css`:

```css
.strip {
  margin: 0 0 var(--space-3, 12px);
  font-size: 0.8125rem;
  color: var(--color-text-muted, #6b6b6b);
}
.strip a {
  color: inherit;
  text-decoration: underline;
  text-underline-offset: 2px;
}
```

Wire-up in `viewer/app/gene/page.tsx`:
- `import { parseRevisions, type Revisions } from "../../lib/revisions";`
- In `ReadyData` add `revisions: Revisions | null;`
- In the first `setState({ kind: "ready", data: { … } })` add `revisions: null,`
- Extend the secondary fetch:

```ts
      const [triageJson, benchJson, catalogJson, revisionsJson] = await Promise.all([
        fetchJson(`${API_BASE}/v1/triage/${symbol}`),
        fetchJson(`${API_BASE}/v1/benchmark/${symbol}`),
        fetchJson(`${API_BASE}/v1/catalog/${symbol}`),
        fetchJson(`${API_BASE}/v1/genes/${symbol}/revisions`),
      ]);
```

and in the following `setState` add `revisions: parseRevisions(revisionsJson),`.

In `GeneDetail.tsx`:
- `import { RevisionStrip } from "../RevisionStrip/RevisionStrip";` and `import type { Revisions } from "../../../lib/revisions";`
- Add to `GeneDetailProps`: `/** Latest archived revision (record history); null until fetched or on a miss — the strip is then omitted. */ revisions: Revisions | null;`
- Destructure `revisions` in `GeneDetail({ … })`.
- Directly after the closing `</nav>` of the page-actions crumbs, render `{revisions ? <RevisionStrip revisions={revisions} /> : null}`.

- [ ] **Step 4: Run tests + type-check**

Run: `cd viewer && npx --yes tsx --import ./tests/helpers/register.mjs --test tests/revision_strip.test.tsx && npm run check`
Expected: 3 tests pass; `tsc` exits 0.

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(viewer): cite-this-version strip on the gene page from record history" -- viewer/lib/revisions.ts viewer/components/surfaceome/RevisionStrip viewer/app/gene/page.tsx viewer/components/surfaceome/GeneDetail/GeneDetail.tsx viewer/tests/revision_strip.test.tsx
```

---

### Task 16: Docs + full gate

**Files:**
- Modify: `CLAUDE.md`, `AGENTS.md` (keep aligned — Doc Sync Rule)
- Modify: `viewer/app/api/page.tsx`, `viewer/public/llms.txt`, `viewer/public/surfaceome-api.skill.md`

- [ ] **Step 1: CLAUDE.md + AGENTS.md**

In CLAUDE.md, after the "Edge-cache purge-on-publish." paragraph, add:

```markdown
**Record history + numbered data releases.** Every distinct state the API served for a gene — record, `/evidence` ledger, `.md` export — is archived write-once to R2 bucket `surfaceome-record-history` (`records/sha256/{hash}.{json|md}`) with one `record_revision` row per actual change in public D1 ([`cloud/record_history/`](src/accessible_surfaceome/cloud/record_history/)). `publish_record` archives after every publish (needs `ARCHIVE_BYPASS_TOKEN`; a miss is a warning, never a failed publish). **Anything that writes `surface_annotation` directly, or bulk-updates a deterministic table the Worker joins at serve time, must be followed by** `uv run python scripts/cloud/sweep_record_history.py --execute`, or those states never enter history. Releases (`data_release` / `data_release_member`) are cut with `scripts/release/cut_data_release.py --version X.Y.Z` after bumping `pyproject.toml` (which is also what the viewer badge shows); it drafts — never publishes — the Zenodo data-record version. History endpoints: `/v1/genes/{sym}/revisions[/{n}[/evidence|.md]]`, `/v1/releases[/{ver}[/genes/{sym}[/evidence|.md]]]` — path-based only, because the zone cache rule ignores query strings.
```

Mirror a shortened version (same facts, same commands) into the matching section of AGENTS.md (find it with `grep -n "purge" AGENTS.md`).

- [ ] **Step 2: API docs, llms.txt, skill file**

Run: `grep -n "/v1/genes/{symbol}.md\|genes/{symbol}.md" viewer/app/api/page.tsx viewer/public/llms.txt viewer/public/surfaceome-api.skill.md`
Next to each hit, add the five History endpoints with the same summaries as the Worker index (Task 14e), plus one sentence: "Revision and release bodies never change; cite them by URL, or by the release's Zenodo version DOI."

- [ ] **Step 3: Full gate**

Run: `bash scripts/check-py.sh`
Expected: ruff, ty, compile and pytest all pass. Fix anything reported (ty will flag untyped `tf.extractfile(...).read()` — the `# type: ignore[union-attr]` in Task 12 covers it).

Run: `cd viewer && npm run check`
Expected: exit 0.

- [ ] **Step 4: Commit**

```bash
git commit -m "docs(surface-proteome): document record history, sweeps and data releases" -- CLAUDE.md AGENTS.md viewer/app/api/page.tsx viewer/public/llms.txt viewer/public/surfaceome-api.skill.md
```

- [ ] **Step 5: Push and open the PR** (only after the user confirms)

```bash
git push -u origin claude/record-history-api
gh pr create --title "feat(surface-proteome): public record history and numbered data releases" --body "<summary of the spec, the rollout checklist from Task 17, test evidence>"
```

---

### Task 17: Rollout (production — each step needs the user's explicit go-ahead)

- [ ] **Step 1: Tables.** `uv run python scripts/cloud/apply_record_history_ddl.py --execute`
- [ ] **Step 2: Bucket + secret.** `npx --yes wrangler r2 bucket create surfaceome-record-history`; generate a token (`python -c "import secrets;print(secrets.token_urlsafe(32))"`), set it with `npx --yes wrangler secret put ARCHIVE_BYPASS_TOKEN` (in `cloudflare/workers/surfaceome_api/`), and add `ARCHIVE_BYPASS_TOKEN=` to the canonical `.env` (never commit it). Add the `RECORD_HISTORY` block to the local `wrangler.toml`.
- [ ] **Step 3: Worker deploy.** `git fetch && git log origin/main -- cloudflare/workers/surfaceome_api/src/index.js` — reconcile anything main or dev changed since this branch; run `REQUIRE_WORKER_NODE=1 uv run pytest -q tests/test_worker_*.py`; deploy. Check `curl -s https://api.deliverome.org/surfaceome/v1 | grep releases`.
- [ ] **Step 4: Pin the volatile-field list.** Fetch one gene's record twice with the bypass header a minute apart and diff: `for i in 1 2; do curl -s -H "X-Archive-Bypass: $ARCHIVE_BYPASS_TOKEN" https://api.deliverome.org/surfaceome/v1/genes/EGFR | python -m json.tool --sort-keys > /tmp/egfr$i.json; sleep 60; done; diff /tmp/egfr1.json /tmp/egfr2.json`. Expected: no diff. If a field differs, add it to `VOLATILE_RECORD_FIELDS` + the pinning test, and commit before seeding.
- [ ] **Step 5: Seed.** `uv run python scripts/cloud/seed_record_history.py --tarball data/external/zenodo/deep_dives_all_1.0.0.tar.gz --execute`
- [ ] **Step 6: Sweep.** `uv run python scripts/cloud/sweep_record_history.py --execute` — expect ~5,332 `created` (every gene gets its first served revision) and 0 `failed`. Re-run once: expect all `unchanged` (this is the dedup check).
- [ ] **Step 7: Spot-check.** `curl -s https://api.deliverome.org/surfaceome/v1/genes/EGFR/revisions`, `/revisions/1`, `/revisions/2/evidence`, `/revisions/2.md`, `/v1/releases`, `/v1/releases/1.0.0/genes/EGFR`.
- [ ] **Step 8: Release 1.3.0.** Bump `pyproject.toml` (+ `CITATION.cff`, `.zenodo.json`) to 1.3.0 in a PR; after merge: `uv run python scripts/release/cut_data_release.py --version 1.3.0 --execute`; review + publish the Zenodo draft; `--set-doi 1.3.0 <DOI>`; `gh release create v1.3.0 --generate-notes`.
- [ ] **Step 9: Viewer deploy** (prod Pages builds from main) and confirm the badge reads v1.3.0 and a gene page shows its strip.
