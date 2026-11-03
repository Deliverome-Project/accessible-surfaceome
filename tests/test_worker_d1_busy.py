"""A busy D1 (export in progress, overloaded) answers 503 + Retry-After, not a 500.

D1 refuses queries while a database export runs. The backup workflow exported
the public database on every qualifying push, and each export made every
uncached API request fail with an uncaught exception (345 of them across two
backups on 2026-10-17/18). The Worker now catches those errors at the router
and answers ``503`` with ``Retry-After`` and ``Cache-Control: no-store``. Any
other error still propagates.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]

_HARNESS = r"""
import { readFileSync, writeFileSync } from "node:fs";
import worker from "./worker.mjs";

const [, , outPath] = process.argv;
const cases = {
  export: "D1_ERROR: Currently processing a long-running export.",
  overloaded: "D1 DB is overloaded. Requests queued for too long.",
  other: "TypeError: something genuinely broken",
};
globalThis.caches = { default: { match: async () => undefined, put: async () => {} } };
const out = {};
for (const [name, message] of Object.entries(cases)) {
  const fail = async () => { throw new Error(message); };
  const env = {
    CF_VERSION_METADATA: { id: "test" },
    DB: { prepare() { return { bind() { return this; }, all: fail, first: fail, run: fail }; } },
  };
  try {
    const r = await worker.fetch(
      new Request("https://api.deliverome.org/surfaceome/v1/genes/CD19"),
      env, { waitUntil() {} });
    out[name] = {
      status: r.status,
      retryAfter: r.headers.get("Retry-After"),
      cacheControl: r.headers.get("Cache-Control"),
      body: await r.json(),
    };
  } catch (e) {
    out[name] = { threw: String(e?.message ?? e) };
  }
}
writeFileSync(outPath, JSON.stringify(out));
"""


@pytest.fixture(scope="module")
def results(tmp_path_factory: pytest.TempPathFactory) -> dict:
    node = shutil.which("node")
    if node is None:
        if os.environ.get("REQUIRE_WORKER_NODE") == "1":
            pytest.fail("Worker checks require Node; refusing to skip")
        pytest.skip("Node is required for Worker tests")
    tmp = tmp_path_factory.mktemp("d1_busy")
    source = (_ROOT / "cloudflare/workers/surfaceome_api/src/index.js").read_text()
    source = source.replace(
        'import { deepDiveTier, isLowLiteratureSurface } from "../../../../viewer/lib/catalog-presets";',
        "const deepDiveTier = () => ({tier: 'likely', facet: null}); "
        "const isLowLiteratureSurface = () => false;",
    )
    shutil.copy2(
        _ROOT / "cloudflare/workers/surfaceome_api/src/contact-sites.js",
        tmp / "contact-sites.js",
    )
    (tmp / "worker.mjs").write_text(source)
    (tmp / "harness.mjs").write_text(_HARNESS)
    result = subprocess.run(
        [node, "--no-warnings", str(tmp / "harness.mjs"), str(tmp / "out.json")],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    return json.loads((tmp / "out.json").read_text())


@pytest.mark.parametrize("case", ["export", "overloaded"])
def test_a_busy_database_answers_503_with_retry_after(results: dict, case: str) -> None:
    r = results[case]
    assert r["status"] == 503
    assert r["retryAfter"] == "30"
    assert r["cacheControl"] == "no-store"
    assert r["body"]["error"] == "database_busy"


def test_other_errors_still_propagate(results: dict) -> None:
    assert "genuinely broken" in results["other"]["threw"]
