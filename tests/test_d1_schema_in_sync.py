"""Pin ``cloudflare/d1_public_schema.sql`` to the live public-D1 state.

The June-2026 drift: ``schweke_homomer_public`` + ``schweke_homomer_release``
were applied to production D1 via direct migration but never backfilled
into the schema file. Result: the Worker's `handleGene` enrichment didn't
even consider Schweke (commented "homo_oligomerization isn't synced as a
public D1 table today"), so 1,205 proteins with predicted homomer state
shipped with ``is_homo_oligomer=False``. The bake-time tool (``tools/
schweke_homomer.lookup``) still hit D1 correctly, so the symptom was a
silent Worker-overlay gap rather than wrong data — but the schema file
being stale meant future PR review couldn't spot the missing Worker
enrichment from the file alone.

This test queries ``sqlite_master`` on the live public DB and asserts
every table + index name appears in the schema file. Skipped when
``CLOUDFLARE_D1_SURFACEOME_PUBLIC_ID`` (et al.) aren't set — same posture
as every other D1-touching test, so CI without secrets stays green.

When the test fails:
1. Add the new objects to ``cloudflare/d1_public_schema.sql`` (verbatim
   ``CREATE TABLE`` / ``CREATE INDEX`` from
   ``SELECT sql FROM sqlite_master WHERE name = ?``).
2. If a NEW table is meant to feed a deterministic-features field, also
   wire it into ``cloudflare/workers/surfaceome_api/src/index.js::handleGene``
   per the "Worker enriches D1-backed deterministic features" pattern.
3. Re-deploy the Worker.

This test isn't a substitute for a proper migrations table; it's a
guardrail to make sure the human-readable schema reference doesn't drift
silently from production while we're still pre-migration.
"""

from __future__ import annotations

import os

import pytest

from accessible_surfaceome.cloud.d1_client import D1Client, D1Config
from accessible_surfaceome.env import load_env
from accessible_surfaceome.paths import REPO_ROOT


_SCHEMA_FILE = REPO_ROOT / "cloudflare" / "d1_public_schema.sql"

# Cloudflare's per-DB virtual tables — Worker/D1 surfaces them in
# ``sqlite_master`` but they're managed by Cloudflare, not by us. Same
# pattern other D1 consumers use for ignore lists.
_IGNORED_NAMES = frozenset(
    {
        "_cf_KV",
        "sqlite_sequence",
        "sqlite_stat1",
        "sqlite_stat4",
    }
)


def _public_d1_or_skip() -> D1Config:
    """Build a public-D1 config from env, or skip the test when missing."""
    load_env()
    acct = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
    token = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
    db = os.environ.get("CLOUDFLARE_D1_SURFACEOME_PUBLIC_ID", "").strip()
    if not (acct and token and db):
        pytest.skip(
            "CLOUDFLARE_* env vars not set — schema-drift test needs the "
            "live public-D1 binding to enumerate tables / indices. CI "
            "without secrets skips this; local dev with .env runs it."
        )
    return D1Config(account_id=acct, database_id=db, api_token=token)


def _live_objects() -> list[dict]:
    """List of {type, name, tbl_name} for everything in sqlite_master.

    Filters out:
    * Explicitly-ignored names (Cloudflare-managed virtual tables).
    * ``sqlite_autoindex_*`` indexes — SQLite auto-creates these for
      every PRIMARY KEY / UNIQUE column constraint. They aren't user-
      authored so they're not in the schema file by design; whether
      they exist follows mechanically from the table DDL.
    """
    cfg = _public_d1_or_skip()
    with D1Client(cfg) as d1:
        rows = d1.query(
            """
            SELECT type, name, tbl_name
            FROM sqlite_master
            WHERE type IN ('table', 'index')
            ORDER BY tbl_name, type DESC, name
            """,
            [],
        )
    return [
        r
        for r in rows
        if r["name"] not in _IGNORED_NAMES
        and not r["name"].startswith("sqlite_autoindex_")
    ]


def _schema_file_text() -> str:
    """The on-disk schema as one string — case-sensitive substring matches.

    Whitespace inside the file varies (different sections use different
    column-alignment widths), so this test uses substring containment
    rather than parsed equality. Names are unique enough that false
    positives are vanishingly unlikely.
    """
    return _SCHEMA_FILE.read_text()


def test_every_live_table_in_schema_file() -> None:
    """Every CREATE TABLE in live D1 is mirrored in the checked-in file."""
    text = _schema_file_text()
    live = _live_objects()
    tables = [r for r in live if r["type"] == "table"]
    missing: list[str] = []
    for r in tables:
        # Match the file's two valid forms: ``CREATE TABLE foo (`` and
        # ``CREATE TABLE IF NOT EXISTS foo (``. Indexes follow below.
        name = r["name"]
        if (
            f"CREATE TABLE IF NOT EXISTS {name}" not in text
            and f"CREATE TABLE {name}" not in text
        ):
            missing.append(name)
    assert not missing, (
        f"Live D1 has {len(missing)} table(s) not in "
        f"cloudflare/d1_public_schema.sql: {missing}. "
        "Backfill the schema file from `SELECT sql FROM sqlite_master "
        "WHERE name = ?`; if the new table maps to a deterministic_features "
        "field, also wire it into the Worker's handleGene enrichment."
    )


def test_every_live_index_in_schema_file() -> None:
    """Every CREATE INDEX in live D1 is mirrored in the checked-in file.

    Indices are easier to forget when applying a migration directly —
    drop them and a high-cardinality query falls back to a full scan
    silently. Tracking them in-file keeps query plans deterministic
    across re-provisions.
    """
    text = _schema_file_text()
    live = _live_objects()
    indexes = [r for r in live if r["type"] == "index"]
    missing: list[str] = []
    for r in indexes:
        name = r["name"]
        # CREATE [UNIQUE] INDEX [IF NOT EXISTS] <name>  ON <table> (<cols>);
        # UNIQUE indexes get the same treatment as plain ones; the schema
        # file uses both forms (uq_triage_run_public_natural is UNIQUE).
        candidates = (
            f"CREATE INDEX IF NOT EXISTS {name}",
            f"CREATE INDEX {name}",
            f"CREATE UNIQUE INDEX IF NOT EXISTS {name}",
            f"CREATE UNIQUE INDEX {name}",
        )
        if not any(c in text for c in candidates):
            missing.append(name)
    assert not missing, (
        f"Live D1 has {len(missing)} index(es) not in "
        f"cloudflare/d1_public_schema.sql: {missing}. "
        "Mirror them in-file so re-provisioning the DB from the schema "
        "file produces the same query plans."
    )
