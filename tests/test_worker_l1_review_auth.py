"""``POST /v1/l1-review`` takes a name (rate-limited per IP), or the optional token.

Outside reviewers of the L1 library type a name without a CAPTCHA or shared token
(Turnstile was removed on 2026-11-26 at Becca Carlson's request). The name is trusted
as typed because reviews are advisory and a person reads each one; a per-IP limit keeps
out floods. The ``X-L1-Review-Token`` header still works and skips the rate limit.

These tests pin, against the real Worker router with D1 and KV stubbed:

* a missing or over-long name is rejected before consuming rate-limit quota;
* a normal submission without Turnstile succeeds with ``auth_method == "rate_limited"``
  and never calls ``challenges.cloudflare.com``;
* the 31st submission from one IP in an hour gets 429, under its own KV counter
  (the feedback form's 5/hour counter is untouched);
* a success stores the row with the name as typed and ``auth_method``;
* the token path skips the rate limit; a wrong token falls through to the rate-limited
  path instead of getting ``auth_method == "token"``;
* with no KV rate-limit binding and no token the endpoint answers 503, never runs open;
* a Worker deployed before migration ``l1_review_v2`` still stores the row;
* reads still need the token.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_WORKER = _ROOT / "cloudflare/workers/surfaceome_api/src/index.js"

_HARNESS = r"""
import { writeFileSync } from "node:fs";
import worker from "./worker.mjs";

const [, , outPath] = process.argv;
globalThis.caches = { default: { match: async () => undefined, put: async () => {} } };

// Any outbound fetch (e.g. Turnstile siteverify) must fail loudly — L1 review writes do not use Turnstile.
const fetchCalls = [];
globalThis.fetch = async (url) => {
  fetchCalls.push(String(url));
  throw new Error(`unexpected fetch ${url}`);
};

// D1 stub: records INSERTs; `legacy` rejects the auth_method column like a
// database that has only migration l1_review_v1.
const makeDb = ({ legacy = false } = {}) => {
  const inserts = [];
  return {
    inserts,
    prepare(sql) {
      let args = [];
      return {
        bind(...v) { args = v; return this; },
        async run() {
          if (legacy && sql.includes("auth_method")) {
            throw new Error("D1_ERROR: table l1_review has no column named auth_method: SQLITE_ERROR");
          }
          const cols = sql.match(/\(([^)]*)\)\s*VALUES/s)[1].split(",").map((c) => c.trim());
          inserts.push(Object.fromEntries(cols.map((c, i) => [c, args[i]])));
          return { success: true };
        },
        async all() { return { results: [] }; },
        async first() { return null; },
      };
    },
  };
};
const makeKv = () => {
  const store = new Map();
  return { store, get: async (k) => store.get(k) ?? null, put: async (k, v) => { store.set(k, v); } };
};

const verdict = { kind: "verdict", reviewer: "  Dr. Ada Q. Reviewer  ", member_id: "l1-m0006",
  design_id: "l1-p0006", sequence_sha256: "f".repeat(64), gene_symbol: "GENEE", verdict: "good",
  reason: "", load_version: "l1d-0123456789abcdef" };
const alt = { kind: "alt_tag", reviewer: "Ada", member_id: "l1-m0006", design_id: "l1-p0006",
  gene_symbol: "GENEE", insert_after_residue: 60, placement: "internal", reason: "loop 2",
  load_version: "l1d-0123456789abcdef" };

const ctx = { waitUntil() {}, passThroughOnException() {} };
const call = async (env, { method = "POST", path = "/v1/l1-review", body, token, ip = "203.0.113.9" } = {}) => {
  const headers = { "Content-Type": "application/json", "CF-Connecting-IP": ip };
  if (token) headers["X-L1-Review-Token"] = token;
  const r = await worker.fetch(
    new Request(`https://api.test${path}`, { method, headers, body: body && JSON.stringify(body) }), env, ctx);
  const text = await r.text();
  let parsed = text;
  try { parsed = JSON.parse(text); } catch {}
  return { status: r.status, body: parsed };
};
const baseEnv = (over = {}) => ({
  DB: makeDb(), FEEDBACK_DB: makeDb(), FEEDBACK_RATELIMIT: makeKv(),
  L1_REVIEW_TOKEN: "s3cret", ...over,
});

const out = {};
const run = async (name, env, opts) => {
  const before = fetchCalls.length;
  const r = await call(env, opts);
  out[name] = {
    ...r,
    inserts: env.FEEDBACK_DB.inserts.slice(),
    fetches: fetchCalls.slice(before),
    kv_keys: env.FEEDBACK_RATELIMIT ? [...env.FEEDBACK_RATELIMIT.store.keys()] : [],
  };
};

await run("missing_name", baseEnv(), { body: { ...verdict, reviewer: "   " } });
await run("long_name", baseEnv(), { body: { ...verdict, reviewer: "x".repeat(81) } });
await run("wrong_token", baseEnv(), { body: verdict, token: "wrong" });
await run("success_verdict", baseEnv(), { body: verdict });
await run("success_alt", baseEnv(), { body: alt });
await run("token_path", baseEnv(), { body: verdict, token: "s3cret" });
await run("no_ratelimit_no_token", baseEnv({ FEEDBACK_RATELIMIT: undefined, L1_REVIEW_TOKEN: undefined }),
  { body: verdict });
await run("token_only_deploy", baseEnv({ FEEDBACK_RATELIMIT: undefined }), { body: verdict, token: "s3cret" });
await run("legacy_db", baseEnv({ FEEDBACK_DB: makeDb({ legacy: true }) }), { body: verdict });

// Rate limit: 30 per IP per hour, then 429; another IP is unaffected; the token
// path is not counted.
{
  const env = baseEnv();
  const statuses = [];
  for (let i = 0; i < 31; i++) {
    statuses.push((await call(env, { body: verdict })).status);
  }
  const other = await call(env, { body: verdict, ip: "198.51.100.7" });
  const viaToken = await call(env, { body: verdict, token: "s3cret" });
  out.rate = {
    statuses, last: (await call(env, { body: verdict })).body,
    other: other.status, via_token: viaToken.status,
    stored: env.FEEDBACK_DB.inserts.length,
    keys: [...env.FEEDBACK_RATELIMIT.store.keys()],
  };
}

// Reads unchanged: token required.
out.read_no_token = await call(baseEnv(), { method: "GET" });
out.read_token = await call(baseEnv(), { method: "GET", token: "s3cret" });
out.export_no_token = await call(baseEnv(), { method: "GET", path: "/v1/l1-review/export.tsv" });

writeFileSync(outPath, JSON.stringify(out));
"""


@pytest.fixture(scope="module")
def results(tmp_path_factory: pytest.TempPathFactory) -> dict:
    node = shutil.which("node")
    if node is None:
        if os.environ.get("REQUIRE_WORKER_NODE") == "1":
            pytest.fail("Worker checks require Node; refusing to skip")
        pytest.skip("Node is required for Worker tests")
    tmp = tmp_path_factory.mktemp("l1_review_auth")
    source = _WORKER.read_text().replace(
        'import { deepDiveTier, isLowLiteratureSurface } from "../../../../viewer/lib/catalog-presets";',
        "const deepDiveTier = () => ({tier: 'likely', facet: null}); "
        "const isLowLiteratureSurface = () => false;",
    )
    for js in _WORKER.parent.glob("*.js"):
        if js.name != "index.js":
            shutil.copy2(js, tmp / js.name)
    (tmp / "worker.mjs").write_text(source)
    (tmp / "harness.mjs").write_text(_HARNESS)
    result = subprocess.run(
        [node, "--no-warnings", str(tmp / "harness.mjs"), str(tmp / "out.json")],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    return json.loads((tmp / "out.json").read_text())


@pytest.mark.parametrize("case", ["missing_name", "long_name"])
def test_name_is_required_and_checked_before_rate_limit(
    results: dict, case: str
) -> None:
    r = results[case]
    assert r["status"] == 400
    assert r["body"] == {"error": "invalid_reviewer"}
    assert r["kv_keys"] == [], "a form error must not consume rate-limit quota"
    assert r["fetches"] == []
    assert r["inserts"] == []


def test_success_stores_the_name_as_typed_without_turnstile(results: dict) -> None:
    r = results["success_verdict"]
    assert r["status"] == 201
    assert r["fetches"] == []
    assert r["body"]["auth_method"] == "rate_limited"
    (row,) = r["inserts"]
    assert row["reviewer"] == "Dr. Ada Q. Reviewer"
    assert row["auth_method"] == "rate_limited"
    assert row["verdict"] == "good"
    a = results["success_alt"]
    assert a["status"] == 201
    assert a["fetches"] == []
    assert a["inserts"][0]["auth_method"] == "rate_limited"
    assert a["inserts"][0]["insert_after_residue"] == 60


def test_wrong_token_falls_back_to_rate_limited_path(results: dict) -> None:
    r = results["wrong_token"]
    assert r["status"] == 201
    assert r["body"]["auth_method"] == "rate_limited"
    assert r["kv_keys"] and all(k.startswith("l1rl:") for k in r["kv_keys"])


def test_token_path_skips_rate_limit(results: dict) -> None:
    for case in ("token_path", "token_only_deploy"):
        r = results[case]
        assert r["status"] == 201, case
        assert r["fetches"] == [], case
        assert r["kv_keys"] == [], case
        assert r["inserts"][0]["auth_method"] == "token", case


def test_no_ratelimit_binding_and_no_token_is_closed(results: dict) -> None:
    r = results["no_ratelimit_no_token"]
    assert r["status"] == 503
    assert r["body"] == {"error": "review_disabled"}
    assert r["inserts"] == []


def test_worker_before_migration_v2_still_stores_the_review(results: dict) -> None:
    r = results["legacy_db"]
    assert r["status"] == 201
    (row,) = r["inserts"]
    assert "auth_method" not in row
    assert row["reviewer"] == "Dr. Ada Q. Reviewer"


def test_rate_limit_is_30_per_ip_per_hour(results: dict) -> None:
    rate = results["rate"]
    assert rate["statuses"][:30] == [201] * 30
    assert rate["statuses"][30] == 429
    assert rate["last"] == {"error": "rate_limited"}
    assert rate["other"] == 201, "another IP has its own counter"
    assert rate["via_token"] == 201, "the token path is not rate-limited"
    assert rate["stored"] == 32
    assert rate["keys"] and all(k.startswith("l1rl:") for k in rate["keys"]), (
        "must not share the feedback form's rl: counter"
    )


def test_reads_still_need_the_token(results: dict) -> None:
    assert results["read_no_token"]["status"] == 401
    assert results["export_no_token"]["status"] == 401
    assert results["read_token"]["status"] == 200
