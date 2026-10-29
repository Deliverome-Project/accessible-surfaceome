"""``POST /v1/events`` stores anonymous click counts and nothing identifying.

The viewer beacons one event per link/button click. The Worker writes one
Analytics Engine data point of (page kind, gene, element kind, label) — no IP,
user agent or visitor id — and always answers 204, so junk or foreign-origin
payloads are dropped silently rather than stored. The privacy page promises
exactly this, so these tests pin what reaches ``writeDataPoint``.
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
import { writeFileSync } from "node:fs";
import worker from "./worker.mjs";

const [, , outPath] = process.argv;
const SITE = "https://surfaceome.deliverome.org";
const cases = {
  gene_click: { origin: SITE, body: { path: "/egfr/", kind: "link", label: "  JSON \n ↗ " } },
  home_button: { origin: SITE, body: { path: "/", kind: "button", label: "Download TSV" } },
  section: { origin: SITE, body: { path: "/benchmark/", kind: "external", label: "PubMed" } },
  deep_path: { origin: SITE, body: { path: "/a/b/c", kind: "link", label: "x" } },
  foreign_origin: { origin: "https://evil.example", body: { path: "/", kind: "link", label: "x" } },
  no_origin: { origin: null, body: { path: "/", kind: "link", label: "x" } },
  email_label: { origin: SITE, body: { path: "/", kind: "link", label: "me@example.org" } },
  bad_kind: { origin: SITE, body: { path: "/", kind: "pageview", label: "x" } },
  not_json: { origin: SITE, raw: "{nope" },
  oversize: { origin: SITE, raw: JSON.stringify({ path: "/", kind: "link", label: "x".repeat(3000) }) },
  no_binding: { origin: SITE, body: { path: "/", kind: "link", label: "x" }, noBinding: true },
};
const out = {};
for (const [name, c] of Object.entries(cases)) {
  const writes = [];
  const env = { CF_VERSION_METADATA: { id: "test" } };
  if (!c.noBinding) env.USAGE_EVENTS = { writeDataPoint: (p) => writes.push(p) };
  const headers = { "Content-Type": "text/plain", "CF-Connecting-IP": "203.0.113.9", "User-Agent": "UA/1" };
  if (c.origin) headers.Origin = c.origin;
  const r = await worker.fetch(
    new Request("https://api.deliverome.org/surfaceome/v1/events", {
      method: "POST", headers, body: c.raw ?? JSON.stringify(c.body),
    }),
    env, { waitUntil() {} });
  out[name] = { status: r.status, cors: r.headers.get("Access-Control-Allow-Origin"), writes };
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
    tmp = tmp_path_factory.mktemp("usage_events")
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


def test_every_payload_answers_204_with_cors(results: dict) -> None:
    for name, r in results.items():
        assert r["status"] == 204, name
        assert r["cors"] == "*", name


def test_gene_click_writes_page_gene_kind_and_clean_label(results: dict) -> None:
    assert results["gene_click"]["writes"] == [
        {
            "indexes": ["gene"],
            "blobs": ["gene", "EGFR", "link", "JSON ↗"],
            "doubles": [1],
        }
    ]


def test_pages_are_classified(results: dict) -> None:
    assert results["home_button"]["writes"][0]["blobs"] == [
        "home",
        "",
        "button",
        "Download TSV",
    ]
    assert results["section"]["writes"][0]["blobs"] == [
        "benchmark",
        "",
        "external",
        "PubMed",
    ]
    assert results["deep_path"]["writes"][0]["blobs"][:2] == ["other", ""]


def test_nothing_identifying_is_written(results: dict) -> None:
    for r in results.values():
        for w in r["writes"]:
            flat = json.dumps(w)
            assert "203.0.113.9" not in flat
            assert "UA/1" not in flat
            assert set(w) == {"indexes", "blobs", "doubles"}
            assert len(w["blobs"]) == 4


@pytest.mark.parametrize(
    "case",
    [
        "foreign_origin",
        "no_origin",
        "email_label",
        "bad_kind",
        "not_json",
        "oversize",
        "no_binding",
    ],
)
def test_rejected_payloads_write_nothing(results: dict, case: str) -> None:
    assert results[case]["writes"] == []
