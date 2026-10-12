"""The Worker must decode prediction bytes to the numbers Python encoded.

There are two implementations of one encoding — ``encode_scores`` in
:mod:`accessible_surfaceome.cloud.tag_site_predictions` and ``decodeScoreHex``
in the Worker — and nothing but this test keeps them the same function. A drift
here is silent and total: every score comes back a plausible-looking number
that is simply wrong, which is far worse than a crash.

The non-obvious half is the RANGE. ProDomino is a probability on [0,1];
INDELi-E runs roughly [-0.2, 3.2] and is stored over [-0.5, 3.5]. If the Worker
assumed [0,1] for everything, an INDELi-E score of 1.83 would decode as 0.58 —
inside the plausible range for a probability, so no consumer would notice.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from accessible_surfaceome.cloud.tag_site_predictions import (
    encode_scores,
    encoding_config,
)

# One probability-ranged predictor and one that is not, including the endpoints
# and a negative value — the cases an implicit [0,1] assumption gets wrong.
# (lo, hi, scores)
CASES: list[tuple[float, float, list[float]]] = [
    (0.0, 1.0, [0.0, 0.15873, 0.5, 0.98765, 1.0]),
    (-0.5, 3.5, [-0.168, 0.033, 1.834, 2.586, 3.233]),
]


def test_worker_decodes_what_python_encoded(tmp_path: Path) -> None:
    node = shutil.which("node")
    if node is None:
        if os.environ.get("REQUIRE_WORKER_NODE") == "1":
            pytest.fail(
                "Shared API compatibility checks require Node; refusing to skip"
            )
        pytest.skip("Node is required for Worker tests")

    root = Path(__file__).resolve().parents[1]
    source = (root / "cloudflare/workers/surfaceome_api/src/index.js").read_text()

    # Pull the two pure helpers out of the Worker rather than reimplementing
    # them here: a copy in the test would pass while the Worker was broken.
    helpers = []
    for name in ("function decodeScoreHex(", "function parseEncoding("):
        start = source.index(name)
        end = source.index("\n}\n", start) + 3
        helpers.append(source[start:end])

    payload = [
        {
            "lo": lo,
            "hi": hi,
            "scores": scores,
            "hex": encode_scores(scores, lo=lo, hi=hi),
            "model_config": encoding_config(lo, hi),
        }
        for lo, hi, scores in CASES
    ]

    (tmp_path / "check.mjs").write_text(
        "\n".join(helpers)
        + r"""
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
const cases = JSON.parse(readFileSync(process.argv[2], "utf8"));
for (const c of cases) {
  // The range must come off model_config, not be assumed.
  const enc = parseEncoding(c.model_config);
  assert.equal(enc.lo, c.lo, `lo for ${c.model_config}`);
  assert.equal(enc.hi, c.hi, `hi for ${c.model_config}`);

  const got = decodeScoreHex(c.hex, enc.lo, enc.hi);
  assert.equal(got.length, c.scores.length, "one score per residue");
  // Two lossy steps compose: half a byte-step from the quantisation, plus up
  // to 5e-5 from the Worker rounding the decoded float to 4 decimal places.
  const tol = (c.hi - c.lo) / 255 / 2 + 5e-5 + 1e-9;
  for (let i = 0; i < got.length; i++) {
    assert.ok(
      Math.abs(got[i] - c.scores[i]) <= tol,
      `residue ${i + 1}: encoded ${c.scores[i]}, Worker decoded ${got[i]} (tol ${tol})`
    );
  }
}

// A row written before the range was recorded means [0,1] — not a crash, and
// not some other default.
const legacy = parseEncoding(null);
assert.deepEqual(legacy, { lo: 0, hi: 1 });
console.log("ok");
"""
    )
    data = tmp_path / "cases.json"
    data.write_text(json.dumps(payload))

    proc = subprocess.run(
        [node, str(tmp_path / "check.mjs"), str(data)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    assert "ok" in proc.stdout


def test_route_is_registered() -> None:
    """The handler existing is not the same as it being reachable."""
    root = Path(__file__).resolve().parents[1]
    source = (root / "cloudflare/workers/surfaceome_api/src/index.js").read_text()
    assert "handleTagSitePredictions" in source
    assert "/v1/tag-site-predictions/" in source
    # It must go through the edge cache like its sibling route; an uncached
    # per-gene route is how the cohort sweep took public D1 down before.
    assert "withEdgeCache(request, env, ctx, () => handleTagSitePredictions(" in source
