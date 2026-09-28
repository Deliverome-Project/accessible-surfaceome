"""Exercise the Worker's serve-time-enrichment degraded-response machinery.

Bug this guards: every enrichment query in ``handleGene`` / ``handleGeneEvidence``
used to swallow its own errors with a bare ``.catch(() => null)`` —
including a genuine D1 hiccup, not just "this gene has no row here". A
transient failure therefore served (and, via ``withEdgeCache``,
PERMANENTLY cached for up to a day) a record with those fields null even
though D1 actually had the data. That's exactly what happened to S100A7A's
archived revision 3: ``canonical_topology.protein_length`` /
``beta_strand_count`` / ``predicted_surface_membrane`` / ``predicted_secreted``
were archived null despite the ``topology_public`` row existing.

The fix wraps each enrichment query in ``soft()``: a real (non-missing-table)
failure is recorded in a per-request ``degraded`` list, which sets
``X-Surfaceome-Degraded`` + forces ``Cache-Control: no-store`` on the
response (see ``json()``'s ``degraded`` param), and ``withEdgeCache`` refuses
to persist a degraded response to either cache tier (edge or KV) while still
returning it to the caller. A "no such table" error is the persistent,
intentional deploy-order case (mirrors the existing tolerance in
``handleTagSites`` / ``fetchPaperMetadata``'s doc comment) and stays silent —
no degraded header, normal caching.

Same offline Node-harness pattern as ``test_worker_evidence_split.py``: load
the real ``cloudflare/workers/surfaceome_api/src/index.js`` router in Node
with a mocked D1 + mocked ``caches.default`` / ``RECORD_CACHE``, and drive
its ``fetch(request, env, ctx)`` — the same code path Cloudflare runs. The
only source modification is stubbing the single top-level TS import
(``viewer/lib/catalog-presets``), same as that test.

Skips (does not fail) when ``node`` is unavailable, UNLESS
``REQUIRE_WORKER_NODE=1`` is set (the shared-API-compatibility posture used
elsewhere in this repo), in which case a missing Node runtime fails the test
instead of silently skipping it.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import pytest

from accessible_surfaceome.paths import REPO_ROOT

WORKER_SRC = REPO_ROOT / "cloudflare" / "workers" / "surfaceome_api" / "src" / "index.js"

# A healthy /v1/genes/TESTG response, fully deterministic: `uniprot_acc` is
# set so the enrichment blocks under test actually run, but every OTHER
# enrichment query is made to return no row (see `makeDB` below), so only
# the ONE query each scenario targets can possibly change the outcome.
RECORD = {
    "schema_version": "2.14.4",
    "gene": {"hgnc_symbol": "TESTG", "uniprot_acc": "P00000"},
    "executive_summary": {},
    "evidence": [
        {
            "evidence_id": "a2_evi_01",
            "claim": "surface-localized in flow cytometry",
            "spans": [{"source": {"source_id": "PMC:PMC1"}}],
        },
    ],
}

# Harness template. `{THROW_TABLE}` / `{THROW_MESSAGE}` are substituted per
# scenario by `_run_scenario`; `null` (no throw) is the healthy-path case.
_HARNESS_TEMPLATE = r"""
const worker = (await import("./worker.mjs")).default;

const RECORD = __RECORD__;
const THROW_TABLE = __THROW_TABLE__;   // string substring to match in the SQL text, or null
const THROW_MESSAGE = __THROW_MESSAGE__;

function makeDB() {
  function stmtFor(sql) {
    let boundArgs = [];
    return {
      sql,
      bind(...args) { boundArgs = args; return this; },
      async first() {
        if (THROW_TABLE && sql.includes(THROW_TABLE)) throw new Error(THROW_MESSAGE);
        if (sql.includes("FROM surface_annotation") && boundArgs[0] === "TESTG") {
          return {
            annotation_json: JSON.stringify(RECORD),
            schema_version: "2.14.4",
            annotated_at: "2026-01-01T00:00:00Z",
            prompt_corpus_version: "1.0.0",
            cohort_run_id: null,
          };
        }
        return null;
      },
      async all() {
        if (THROW_TABLE && sql.includes(THROW_TABLE)) throw new Error(THROW_MESSAGE);
        return { results: [] };
      },
    };
  }
  return {
    prepare(sql) { return stmtFor(sql); },
    async batch(statements) {
      for (const s of statements) {
        if (THROW_TABLE && s.sql.includes(THROW_TABLE)) throw new Error(THROW_MESSAGE);
      }
      return statements.map(() => ({ results: [] }));
    },
  };
}

let cachePuts = 0;
globalThis.caches = {
  default: {
    match: async () => undefined,
    put: async () => { cachePuts++; },
  },
};
let kvPuts = 0;
const kv = {
  async getWithMetadata() { return null; },
  async put() { kvPuts++; },
};

function makeCtx() {
  const pending = [];
  return {
    ctx: { waitUntil(p) { pending.push(p); } },
    drain: async () => { await Promise.all(pending.splice(0)); },
  };
}

async function call(path) {
  const env = { DB: makeDB(), RECORD_CACHE: kv };
  const { ctx, drain } = makeCtx();
  const req = new Request("https://api.deliverome.org/surfaceome" + path, { method: "GET" });
  const res = await worker.fetch(req, env, ctx);
  const body = await res.text();
  await drain();
  return {
    status: res.status,
    degraded: res.headers.get("X-Surfaceome-Degraded"),
    cacheControl: res.headers.get("Cache-Control"),
    body,
    cachePuts,
    kvPuts,
  };
}

const result = await call(__PATH__);
console.log(JSON.stringify(result));
"""


def _patched_worker_source() -> str:
    """Worker source with its lone TS import replaced by inert stubs.

    Same rationale as ``test_worker_evidence_split.py``: the test record
    carries no ``filters``, so the deep-dive classification (the sole
    caller of the TS import) is never reached — the stub is purely to make
    the module resolvable in plain Node.
    """
    src = WORKER_SRC.read_text(encoding="utf-8")
    stub = (
        "const deepDiveTier = () => ({ tier: 'no', facet: null });\n"
        "const isLowLiteratureSurface = () => false;"
    )
    patched, n = re.subn(
        r'^import \{[^}]*\} from "[^"]*catalog-presets";\s*$',
        stub,
        src,
        count=1,
        flags=re.MULTILINE,
    )
    assert n == 1, (
        "expected exactly one catalog-presets import to stub in index.js; "
        f"found {n}. The Worker's import shape changed — update this test."
    )
    return patched


def _run_scenario(
    path: str, *, throw_table: str | None, throw_message: str | None
) -> dict[str, Any]:
    node = shutil.which("node")
    if node is None:
        if os.environ.get("REQUIRE_WORKER_NODE") == "1":
            pytest.fail(
                "Shared API compatibility checks require Node; refusing to skip"
            )
        pytest.skip("node not available — cannot execute the Worker source")

    harness = (
        _HARNESS_TEMPLATE.replace("__RECORD__", json.dumps(RECORD))
        .replace("__THROW_TABLE__", json.dumps(throw_table))
        .replace("__THROW_MESSAGE__", json.dumps(throw_message))
        .replace("__PATH__", json.dumps(path))
    )

    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        shutil.copy2(WORKER_SRC.with_name("contact-sites.js"), d / "contact-sites.js")
        (d / "worker.mjs").write_text(_patched_worker_source(), encoding="utf-8")
        (d / "harness.mjs").write_text(harness, encoding="utf-8")
        proc = subprocess.run(  # noqa: S603 — fixed argv, temp files we wrote
            [node, "harness.mjs"],
            cwd=d,
            capture_output=True,
            text=True,
            timeout=60,
        )
    if proc.returncode != 0:
        pytest.fail(
            "Node harness failed to run the Worker source.\n"
            f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )
    return json.loads(proc.stdout.strip().splitlines()[-1])


HEALTHY_CACHE_CONTROL = (
    "public, max-age=86400, s-maxage=86400, "
    "stale-while-revalidate=86400, stale-if-error=86400"
)


def test_generic_enrichment_error_marks_degraded_and_never_caches() -> None:
    """A real (non-missing-table) D1 error on one enrichment query — the
    Schweke homo-oligomer lookup, the first `soft()`-wrapped call in
    `handleGene` — must still return 200, but with `X-Surfaceome-Degraded`
    naming the failed query, `Cache-Control: no-store`, and NEITHER cache
    tier written."""
    out = _run_scenario(
        "/v1/genes/TESTG",
        throw_table="schweke_homomer_public",
        throw_message="D1_ERROR: D1 DB's isolate exceeded its memory limit and was reset",
    )
    assert out["status"] == 200
    assert out["degraded"] == "schweke_homomer_public"
    assert out["cacheControl"] == "no-store"
    assert out["cachePuts"] == 0
    assert out["kvPuts"] == 0
    # The record itself is still served — degraded means "this field may be
    # stale/null", not "the endpoint is broken".
    body = json.loads(out["body"])
    assert body["gene"]["hgnc_symbol"] == "TESTG"


def test_missing_table_error_is_silent_and_caches_normally() -> None:
    """A 'no such table' error is the persistent, intentional deploy-order
    case (mirrors handleTagSites' tolerance) — it must NOT set the degraded
    header, and the response must cache exactly as it does today."""
    out = _run_scenario(
        "/v1/genes/TESTG",
        throw_table="schweke_homomer_public",
        throw_message="D1_ERROR: no such table: schweke_homomer_public: SQLITE_ERROR",
    )
    assert out["status"] == 200
    assert out["degraded"] is None
    assert out["cacheControl"] == HEALTHY_CACHE_CONTROL
    assert out["cachePuts"] == 1
    assert out["kvPuts"] == 1


def test_healthy_request_has_no_degraded_header_and_stable_body() -> None:
    """No enrichment failure at all: response shape must be byte-identical
    to today — no `X-Surfaceome-Degraded` header, the same Cache-Control,
    and a JSON body that matches the fixture record exactly (evidence
    stripped, no enrichment blocks injected since every enrichment query
    here returns no row)."""
    out = _run_scenario("/v1/genes/TESTG", throw_table=None, throw_message=None)
    assert out["status"] == 200
    assert out["degraded"] is None
    assert out["cacheControl"] == HEALTHY_CACHE_CONTROL
    assert out["cachePuts"] == 1
    assert out["kvPuts"] == 1
    body = json.loads(out["body"])
    expected = {**RECORD}
    del expected["evidence"]  # handleGene strips `evidence` unconditionally
    assert body == expected


def test_evidence_route_paper_metadata_error_marks_degraded() -> None:
    """Same machinery on `/v1/genes/{sym}/evidence`: a real `paper_metadata`
    batch failure must degrade+no-store+never-cache; a healthy fetch must
    not."""
    degraded_out = _run_scenario(
        "/v1/genes/TESTG/evidence",
        throw_table="paper_metadata",
        throw_message="D1_ERROR: too many SQL variables",
    )
    assert degraded_out["status"] == 200
    assert degraded_out["degraded"] == "paper_metadata"
    assert degraded_out["cacheControl"] == "no-store"
    assert degraded_out["cachePuts"] == 0
    assert degraded_out["kvPuts"] == 0
    body = json.loads(degraded_out["body"])
    assert body["gene"] == "TESTG"
    assert len(body["evidence"]) == 1
    assert body["papers"] == {}  # degrades to bare accessions, same as before

    healthy_out = _run_scenario(
        "/v1/genes/TESTG/evidence", throw_table=None, throw_message=None
    )
    assert healthy_out["degraded"] is None
    assert healthy_out["cacheControl"] == HEALTHY_CACHE_CONTROL
    assert healthy_out["cachePuts"] == 1
    assert healthy_out["kvPuts"] == 1


def test_evidence_route_missing_paper_metadata_table_is_silent() -> None:
    """`paper_metadata` not existing yet is the same intentional deploy-order
    tolerance fetchPaperMetadata's own doc comment already described —
    must not degrade."""
    out = _run_scenario(
        "/v1/genes/TESTG/evidence",
        throw_table="paper_metadata",
        throw_message="D1_ERROR: no such table: paper_metadata: SQLITE_ERROR",
    )
    assert out["status"] == 200
    assert out["degraded"] is None
    assert out["cacheControl"] == HEALTHY_CACHE_CONTROL
    assert out["cachePuts"] == 1
    assert out["kvPuts"] == 1
