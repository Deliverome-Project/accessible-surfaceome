"""Exercise the record-history routes of the real Worker router offline.

``env.DB`` is backed by a real in-memory SQLite database (``node:sqlite``'s
``DatabaseSync``, Node 24+) loaded from the ACTUAL D1 DDL for
``record_revision`` / ``data_release`` / ``data_release_member`` /
``surface_annotation`` — extracted straight out of
``cloudflare/d1_public_schema.sql`` — rather than a hand-rolled JS mock that
branches on substrings of the SQL text. That means COLLATE NOCASE,
json_group_array/json_object, and ORDER BY are all exercised against the
real database engine the routes are written for, not re-implemented (and
potentially silently diverged) in JS.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

DDL_TABLES = [
    "record_revision",
    "data_release",
    "data_release_member",
    "surface_annotation",
]


def _split_statements(schema_sql: str) -> list[str]:
    """Split a .sql dump into top-level statements on a ``;`` that
    terminates actual SQL — never one that merely appears inside a ``--``
    line comment. This schema's comments are RST-flavored prose that
    routinely contains semicolons, e.g. ``-- predate the column;
    ``COALESCE(prompt_corpus_version, '0.0.0')`` keeps ordering...`` — a
    naive ``text.split(";")`` cuts that comment in half and hands the second
    half to SQLite as if it were code, which is a syntax error.
    """
    statements: list[str] = []
    buf: list[str] = []
    for line in schema_sql.splitlines():
        buf.append(line)
        code = line.split("--", 1)[0]  # drop anything from a line comment on
        if ";" in code:
            statements.append("\n".join(buf))
            buf = []
    if buf:
        statements.append("\n".join(buf))
    return statements


def _extract_ddl(schema_sql: str, tables: list[str]) -> str:
    """Pull the CREATE TABLE / CREATE INDEX statements for `tables` out of a
    full D1 schema dump, in their original file order.

    Keeps any statement whose text contains one of `tables` as a whole
    identifier. The word-boundary regex is what keeps ``data_release`` from
    matching inside ``data_release_member``: an underscore is a "word"
    character, so there's no boundary between ``data_release`` and
    ``_member`` and a plain substring test would otherwise conflate the two
    tables.
    """
    statements = []
    for stmt in _split_statements(schema_sql):
        stripped = stmt.strip()
        if not stripped:
            continue
        if any(re.search(rf"\b{re.escape(t)}\b", stripped) for t in tables):
            statements.append(stripped)
    return "\n".join(statements)


def test_extract_ddl_does_not_conflate_data_release_and_member() -> None:
    """Regression guard for the word-boundary trick above, independent of
    the real schema file's current contents."""
    schema = (
        "CREATE TABLE IF NOT EXISTS data_release (version TEXT);\n"
        "CREATE TABLE IF NOT EXISTS data_release_member (version TEXT);\n"
        "CREATE TABLE IF NOT EXISTS unrelated (x TEXT);\n"
    )
    ddl = _extract_ddl(schema, ["data_release"])
    assert "data_release_member" not in ddl
    assert "CREATE TABLE IF NOT EXISTS data_release (" in ddl
    assert "unrelated" not in ddl


def test_record_history_routes(tmp_path: Path) -> None:
    node = shutil.which("node")
    if node is None:
        if os.environ.get("REQUIRE_WORKER_NODE") == "1":
            pytest.fail(
                "Shared API compatibility checks require Node; refusing to skip"
            )
        pytest.skip("Node is required for Worker tests")
    root = Path(__file__).resolve().parents[1]
    source = (root / "cloudflare/workers/surfaceome_api/src/index.js").read_text()
    source = source.replace(
        'import { deepDiveTier, isLowLiteratureSurface } from "../../../../viewer/lib/catalog-presets";',
        "const deepDiveTier = () => ({tier: 'no', facet: null}); const isLowLiteratureSurface = () => false;",
    )
    (tmp_path / "worker.mjs").write_text(source)

    schema_sql = (root / "cloudflare/d1_public_schema.sql").read_text()
    ddl = _extract_ddl(schema_sql, DDL_TABLES)
    for table in DDL_TABLES:
        assert f"CREATE TABLE IF NOT EXISTS {table} (" in ddl, (
            f"DDL extraction lost {table!r} — has cloudflare/d1_public_schema.sql "
            "been renamed/restructured?"
        )
    (tmp_path / "ddl.sql").write_text(ddl)

    (tmp_path / "test.mjs").write_text(r"""
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { DatabaseSync } from "node:sqlite";
import worker from "./worker.mjs";

const ddl = readFileSync(new URL("./ddl.sql", import.meta.url), "utf8");
const sqliteDb = new DatabaseSync(":memory:");
sqliteDb.exec(ddl);

function insert(table, columns, rows) {
  const sql = `INSERT INTO ${table} (${columns.join(", ")}) VALUES (${columns.map(() => "?").join(", ")})`;
  const stmt = sqliteDb.prepare(sql);
  for (const row of rows) {
    stmt.run(...columns.map((c) => (row[c] === undefined ? null : row[c])));
  }
}

insert(
  "record_revision",
  ["gene_symbol", "hgnc_id", "revision", "json_hash", "evidence_hash", "md_hash",
   "published_at", "source", "schema_version", "prompt_corpus_version"],
  [
    { gene_symbol: "EGFR", hgnc_id: "HGNC:3236", revision: 1, json_hash: "j1",
      published_at: "2026-08-15T00:00:00Z", source: "seed:zenodo-1.0.0",
      schema_version: "2.14.2", prompt_corpus_version: "2.50.2" },
    { gene_symbol: "EGFR", hgnc_id: "HGNC:3236", revision: 2, json_hash: "j2",
      evidence_hash: "e2", md_hash: "m2", published_at: "2026-09-27T00:00:00Z",
      source: "sweep", schema_version: "2.14.4", prompt_corpus_version: "2.50.2" },
    // Mixed-case HGNC symbol (the `Cxorf` class checkSymbol's own comment
    // warns about) — proves the query-side COLLATE NOCASE actually works
    // against real SQLite, not a JS mock's own up()-comparison.
    { gene_symbol: "C11orf24", hgnc_id: "HGNC:1234", revision: 1, json_hash: "c1",
      published_at: "2026-09-01T00:00:00Z", source: "sweep",
      schema_version: "2.14.4", prompt_corpus_version: "2.50.2" },
  ],
);

insert(
  "data_release",
  ["version", "cut_at", "github_tag", "zenodo_version_doi", "n_genes", "notes"],
  [
    { version: "1.0.0", cut_at: "2026-08-15T00:00:00Z",
      zenodo_version_doi: "10.5281/zenodo.20805384", n_genes: 1 },
    // No DOI yet — exercises the pre-DOI short-TTL / non-immutable branch.
    { version: "2.0.0", cut_at: "2026-09-20T00:00:00Z", n_genes: 1 },
  ],
);

insert(
  "data_release_member",
  ["version", "gene_symbol", "revision"],
  [
    // Deliberately out of version order and non-canonically cased
    // ("egfr") — together these exercise the two fixes under test:
    // handleRevisionList's correlated releases[] subquery must ORDER BY
    // version regardless of insertion order, and handleRelease must report
    // the CANONICAL record_revision.gene_symbol in `members`, not whatever
    // casing data_release_member happens to store.
    { version: "2.0.0", gene_symbol: "EGFR", revision: 1 },
    { version: "1.0.0", gene_symbol: "egfr", revision: 1 },
  ],
);

insert(
  "surface_annotation",
  ["gene_symbol", "schema_version", "annotation_json", "annotated_at", "prompt_corpus_version"],
  [
    // No gene.uniprot_acc — deliberately skips handleGene's enrichment
    // blocks (topology/paralog/ortholog/surface_bind/Schweke), which are
    // all gated on `if (uniprot)`, so this minimal schema doesn't need
    // those extra tables just to exercise the bypass/KV/rate-limiter
    // behavior below.
    { gene_symbol: "EGFR", schema_version: "2.14.4",
      annotation_json: JSON.stringify({ gene: { hgnc_symbol: "EGFR" } }),
      annotated_at: "2026-09-27T00:00:00Z", prompt_corpus_version: "2.50.2" },
  ],
);

// D1-shaped adapter over DatabaseSync: prepare(sql).bind(...args).first()/.all().
// first()/all() MUST be genuine async functions (not plain sync returns) —
// index.js chains bare `.first().catch(() => null)` in many places with no
// `await` first, which only works when the left side is an actual Promise.
function makeDB(db) {
  return {
    prepare(sql) {
      let boundArgs = [];
      return {
        bind(...args) { boundArgs = args; return this; },
        async first() {
          const row = db.prepare(sql).get(...boundArgs);
          return row === undefined ? null : row;
        },
        async all() {
          const rows = db.prepare(sql).all(...boundArgs);
          return { results: rows };
        },
      };
    },
  };
}

let cacheReads = 0;
globalThis.caches = { default: { match: async () => { cacheReads++; return undefined; }, put: async () => {} } };

const blobs = { "records/sha256/j1.json": '{"v":1}', "records/sha256/j2.json": '{"v":2}',
                "records/sha256/e2.json": '{"evidence":[]}', "records/sha256/m2.md": "# EGFR" };

let kvGets = 0, kvPuts = 0;
const recordCacheSpy = {
  async getWithMetadata() { kvGets++; return null; },
  async put() { kvPuts++; },
};
let limiterCalls = 0;
const rateLimiterSpy = { async limit() { limiterCalls++; return { success: true }; } };

const env = {
  ARCHIVE_BYPASS_TOKEN: "secret",
  RECORD_HISTORY: { async get(key) { return key in blobs ? { body: blobs[key] } : null; } },
  RECORD_CACHE: recordCacheSpy,
  RATE_LIMITER: rateLimiterSpy,
  DB: makeDB(sqliteDb),
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
// ORDER BY version inside the correlated subquery: rev 1 belongs to both
// releases (inserted 2.0.0-then-1.0.0 above), so a working ORDER BY must
// still come back sorted ascending, not insertion order.
assert.deepEqual(list.revisions[1].releases.map(r => r.version), ["1.0.0", "2.0.0"]);
assert.equal(list.revisions[1].evidence_url, null);
assert.match(list.revisions[0].url, /\/v1\/genes\/EGFR\/revisions\/2$/);
// A revision that belongs to no release at all gets releases: [], not null
// or a malformed parse of an empty json_group_array.
assert.deepEqual(list.revisions[0].releases, []);

// mixed-case gene symbol lookup — real COLLATE NOCASE, not a JS mock.
const mixedCase = await (await call("/v1/genes/c11ORF24/revisions")).json();
assert.equal(mixedCase.gene_symbol, "C11orf24");
assert.equal(mixedCase.current_revision, 1);

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
// ORDER BY cut_at DESC — "2.0.0" (2026-09-20) is newer than "1.0.0" (2026-08-15).
assert.deepEqual(rl.releases.map(r => r.version), ["2.0.0", "1.0.0"]);

// v-prefix redirects (301, no-store) to the bare canonical path — one cache
// key per release so cut_data_release's (bare-only) purge always hits.
const vRedirect = await call("/v1/releases/v1.0.0");
assert.equal(vRedirect.status, 301);
assert.equal(vRedirect.headers.get("Location"), "https://api.deliverome.org/surfaceome/v1/releases/1.0.0");
assert.equal(vRedirect.headers.get("Cache-Control"), "no-store");
const vRedirectGene = await call("/v1/releases/v1.0.0/genes/EGFR");
assert.equal(vRedirectGene.status, 301);
assert.equal(vRedirectGene.headers.get("Location"), "https://api.deliverome.org/surfaceome/v1/releases/1.0.0/genes/EGFR");
const vRedirectGeneMd = await call("/v1/releases/V1.0.0/genes/EGFR.md");
assert.equal(vRedirectGeneMd.status, 301);
assert.equal(vRedirectGeneMd.headers.get("Location"), "https://api.deliverome.org/surfaceome/v1/releases/1.0.0/genes/EGFR.md");

// bare-path release with a DOI: immutable, 1-year TTL, canonical gene_symbol
// casing from record_revision (not the "egfr" data_release_member stored).
let oneResp = await call("/v1/releases/1.0.0");
assert.match(oneResp.headers.get("Cache-Control"), /immutable/);
assert.match(oneResp.headers.get("Cache-Control"), /max-age=31536000/);
const one = await oneResp.json();
assert.equal(one.version, "1.0.0");
assert.equal(one.members[0].gene_symbol, "EGFR");

// release without a DOI yet: short TTL, NOT immutable.
let noDoiResp = await call("/v1/releases/2.0.0");
assert.doesNotMatch(noDoiResp.headers.get("Cache-Control"), /immutable/);
assert.match(noDoiResp.headers.get("Cache-Control"), /max-age=60\b/);

assert.equal((await call("/v1/releases/one")).status, 400);
assert.equal((await (await call("/v1/releases/9.9.9")).json()).error, "release_not_found");
assert.equal(await (await call("/v1/releases/1.0.0/genes/egfr")).text(), '{"v":1}');
assert.equal((await (await call("/v1/releases/1.0.0/genes/CD63")).json()).error, "gene_not_in_release");

// archive bypass skips the caches only with the right secret
cacheReads = 0;
await call("/v1/genes/EGFR/revisions", { "X-Archive-Bypass": "wrong" });
assert.equal(cacheReads, 1);
cacheReads = 0;
const bypassed = await call("/v1/genes/EGFR/revisions", { "X-Archive-Bypass": "secret" });
assert.equal(cacheReads, 0);
assert.equal(bypassed.headers.get("X-Archive-Bypass-Honored"), "1");
assert.equal((await call("/v1/genes/EGFR/revisions", { "X-Archive-Bypass": "wrong" })).headers.get("X-Archive-Bypass-Honored"), null);

// a bypassed 404 also carries the honoured header — the archiver's
// _fetch_record checks this on every status, including 404, before it
// trusts the body enough to tell gene_not_annotated apart from a stale cache.
const notFoundBypassed = await call("/v1/genes/NOPE/revisions", { "X-Archive-Bypass": "secret" });
assert.equal(notFoundBypassed.status, 404);
assert.equal(notFoundBypassed.headers.get("X-Archive-Bypass-Honored"), "1");

// The bypass matters most on the route the archiver actually calls
// (/v1/genes/{symbol}): a normal request touches both the rate limiter and
// the RECORD_CACHE KV mirror; a bypassed request must touch NEITHER — it
// reads live D1 state directly, every time, so a sweep never archives
// stale cached bytes.
const preNormalGets = kvGets, preNormalPuts = kvPuts, preNormalLimiter = limiterCalls;
const normalGeneResp = await call("/v1/genes/EGFR");
assert.equal(normalGeneResp.status, 200);
assert.equal(limiterCalls, preNormalLimiter + 1, "normal request should call the rate limiter exactly once");
assert.ok(kvGets > preNormalGets, "normal request should read the RECORD_CACHE mirror");
assert.ok(kvPuts > preNormalPuts, "normal 200 response should populate the RECORD_CACHE mirror");
const preBypassGets = kvGets, preBypassPuts = kvPuts, preBypassLimiter = limiterCalls;
const bypassGeneResp = await call("/v1/genes/EGFR", { "X-Archive-Bypass": "secret" });
assert.equal(bypassGeneResp.status, 200);
assert.equal(bypassGeneResp.headers.get("X-Archive-Bypass-Honored"), "1");
assert.equal(kvGets, preBypassGets, "bypass must not read RECORD_CACHE");
assert.equal(kvPuts, preBypassPuts, "bypass must not write RECORD_CACHE");
assert.equal(limiterCalls, preBypassLimiter, "bypass must not call the rate limiter");

// index lists the new endpoints
const idx = await (await call("/v1")).json();
const paths = idx.endpoints.map(e => e.path);
for (const p of ["/v1/genes/{symbol}/revisions", "/v1/genes/{symbol}/revisions/{n}",
                 "/v1/releases", "/v1/releases/{version}", "/v1/releases/{version}/genes/{symbol}"])
  assert(paths.includes(p), p);
console.log("ok");
""")
    out = subprocess.run(
        [node, str(tmp_path / "test.mjs")], capture_output=True, text=True, cwd=tmp_path
    )
    assert out.returncode == 0, out.stderr + out.stdout
    assert out.stdout.strip().endswith("ok")
