"""Execute the Cloudflare Worker's evidence-ledger split + KV read-through
end-to-end, in Node, against a mocked D1 — no live network, no deploy.

Why Node and not the live-API pattern of ``test_worker_response_shape.py``:
that test hits the *deployed* ``api.deliverome.org`` Worker, so it can only
verify behavior that is already in production. The evidence split
(``GET /v1/genes/{SYMBOL}`` now OMITS ``evidence``; the new
``GET /v1/genes/{SYMBOL}/evidence`` returns it) and the KV read-through in
``withEdgeCache`` are NOT deployed yet, so they can only be verified by
running the real Worker source. We load the actual
``cloudflare/workers/surfaceome_api/src/index.js`` router in Node with a
stub D1 and stub ``caches.default`` / ``RECORD_CACHE`` and drive its
``fetch(request, env, ctx)`` — the same code path Cloudflare runs.

The only source modification is stubbing the single top-level TS import
(``viewer/lib/catalog-presets``) — a module Node can't resolve without a
bundler and which the deep-dive classification (skipped here: the test
record carries no ``filters``) is the sole caller of. Everything under
test — the router, ``handleGene``'s evidence strip, ``handleGeneEvidence``,
and ``withEdgeCache``'s KV tiering — runs unmodified.

Skips (does not fail) when ``node`` is unavailable, matching the repo's
posture for environment-gated tests. When node is present this runs in the
default ``pytest -q`` gate (it is NOT network-marked).
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from accessible_surfaceome.cloud.surface_annotation import _kv_keys_for
from accessible_surfaceome.paths import REPO_ROOT

WORKER_SRC = (
    REPO_ROOT
    / "cloudflare"
    / "workers"
    / "surfaceome_api"
    / "src"
    / "index.js"
)

# Static Node harness. Imports the patched Worker (written next to it as
# ``worker.mjs``), stubs the Workers runtime globals/bindings, drives the
# real router, and prints one JSON blob for the Python assertions.
_HARNESS = r"""
globalThis.caches = { default: { match: async () => undefined, put: async () => {} } };
const worker = (await import("./worker.mjs")).default;

const RECORD = {
  schema_version: "2.14.0",
  gene: { hgnc_symbol: "TESTG", uniprot_acc: null },
  executive_summary: {},
  evidence: [
    { evidence_id: "a2_evi_01", claim: "surface-localized in flow cytometry" },
    { evidence_id: "a2_evi_02", claim: "shed ectodomain detected in serum" },
  ],
};

function makeDB() {
  return {
    prepare(sql) {
      let boundArgs = [];
      return {
        bind(...args) { boundArgs = args; return this; },
        async first() {
          if (sql.includes("FROM surface_annotation") && boundArgs[0] === "TESTG") {
            return {
              annotation_json: JSON.stringify(RECORD),
              schema_version: "2.14.0",
              annotated_at: "2026-01-01T00:00:00Z",
              prompt_corpus_version: "1.0.0",
              cohort_run_id: null,
            };
          }
          return null;
        },
        async all() { return { results: [] }; },
      };
    },
  };
}

function makeCtx() {
  const pending = [];
  return {
    ctx: { waitUntil(p) { pending.push(p); } },
    drain: async () => { await Promise.all(pending.splice(0)); },
  };
}

async function call(env, path) {
  const { ctx, drain } = makeCtx();
  const req = new Request("https://api.deliverome.org/surfaceome" + path, { method: "GET" });
  const res = await worker.fetch(req, env, ctx);
  const body = await res.text();
  await drain();
  return { status: res.status, ct: res.headers.get("content-type"), body };
}

// --- Scenario A: no KV binding (pre-binding fallback path) ---------------
const envA = { DB: makeDB() };
const recA = await call(envA, "/v1/genes/TESTG");
const eviA = await call(envA, "/v1/genes/TESTG/evidence");
const unknownA = await call(envA, "/v1/genes/NOPEGENE");
const recParsed = JSON.parse(recA.body);
const eviParsed = JSON.parse(eviA.body);

// --- Scenario B: with KV binding (read-through + rebuild) ----------------
const kvStore = new Map();
const putKeys = [];
const kv = {
  async getWithMetadata(key) {
    const e = kvStore.get(key);
    return e ? { value: e.value, metadata: e.metadata } : { value: null, metadata: null };
  },
  async get(key) { const e = kvStore.get(key); return e ? e.value : null; },
  async put(key, value, opts) {
    putKeys.push(key);
    kvStore.set(key, { value, metadata: (opts && opts.metadata) || null });
  },
};
const envB = { DB: makeDB(), RECORD_CACHE: kv };
const recB1 = await call(envB, "/v1/genes/TESTG");   // full miss -> populates KV
await call(envB, "/v1/genes/TESTG/evidence");        // populate the evidence key too
const recB2 = await call(envB, "/v1/genes/TESTG");   // caches.default still empty -> KV hit

console.log(JSON.stringify({
  a: {
    record_status: recA.status,
    record_ct: recA.ct,
    record_has_evidence: Object.prototype.hasOwnProperty.call(recParsed, "evidence"),
    record_gene_hgnc: recParsed?.gene?.hgnc_symbol ?? null,
    evidence_status: eviA.status,
    evidence_ct: eviA.ct,
    evidence_gene: eviParsed.gene,
    evidence_len: Array.isArray(eviParsed.evidence) ? eviParsed.evidence.length : -1,
    evidence_first_id: eviParsed.evidence?.[0]?.evidence_id ?? null,
    unknown_status: unknownA.status,
  },
  b: {
    kv_hit_status: recB2.status,
    kv_hit_ct: recB2.ct,
    kv_hit_body_equals_miss: recB1.body === recB2.body,
    kv_hit_has_evidence: Object.prototype.hasOwnProperty.call(JSON.parse(recB2.body), "evidence"),
    kv_put_keys: Array.from(new Set(putKeys)).sort(),
  },
}));
"""


def _patched_worker_source() -> str:
    """Worker source with its lone TS import replaced by inert stubs.

    ``viewer/lib/catalog-presets`` (a .ts module) is unresolvable in plain
    Node and is only reached from the deep-dive classification, which the
    test record does not trigger (no ``filters`` block). Replacing it keeps
    every code path under test byte-for-byte identical.
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


def _run_worker() -> dict[str, Any]:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node not available — cannot execute the Worker source")
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / "worker.mjs").write_text(_patched_worker_source(), encoding="utf-8")
        (d / "harness.mjs").write_text(_HARNESS, encoding="utf-8")
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


def test_evidence_split_and_kv_readthrough() -> None:
    """The record endpoint omits ``evidence``; ``/evidence`` returns it; and
    the KV read-through serves a rebuilt record with the right headers.
    """
    out = _run_worker()
    a = out["a"]
    b = out["b"]

    # --- CHANGE 2: evidence-ledger split --------------------------------
    # The per-gene record is served WITHOUT the evidence array...
    assert a["record_status"] == 200
    assert a["record_ct"].startswith("application/json")
    assert a["record_has_evidence"] is False, (
        "GET /v1/genes/{symbol} must NOT include the `evidence` field"
    )
    assert a["record_gene_hgnc"] == "TESTG"  # rest of the record is intact

    # ...and the split-out endpoint returns exactly that array.
    assert a["evidence_status"] == 200
    assert a["evidence_ct"].startswith("application/json")
    assert a["evidence_gene"] == "TESTG"
    assert a["evidence_len"] == 2
    assert a["evidence_first_id"] == "a2_evi_01"

    # Same 404 posture as handleGene for an unknown gene.
    assert a["unknown_status"] == 404

    # --- CHANGE 1: KV read-through --------------------------------------
    # Second request (with caches.default cold) is served from KV, rebuilt
    # with the correct status / content-type, byte-identical to the D1 miss,
    # and still carries the evidence strip.
    assert b["kv_hit_status"] == 200
    assert b["kv_hit_ct"].startswith("application/json")
    assert b["kv_hit_body_equals_miss"] is True
    assert b["kv_hit_has_evidence"] is False

    # The KV keys the Worker writes must be exactly the ones the post-publish
    # purge (_kv_keys_for) deletes — otherwise a republish leaves KV stale.
    assert b["kv_put_keys"] == sorted(_kv_keys_for("TESTG"))
