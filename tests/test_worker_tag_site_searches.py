"""A gene with more than one tag-site search must answer the same way every time.

``tag_site_gene_public`` was re-keyed to ``(gene_symbol, candidate_id,
run_series)`` so the enrichment pass can record a second search without
overwriting the first — 1,415 of that table's rows are dated zeros, and each one
costs a real literature search to reproduce. Every gene still has exactly one
row today, which is the only reason ``.first()`` with no ``ORDER BY`` has been
safe: SQLite may return either row once there are two, so the gene would answer
differently per request, cached per POP. That reads as a bug rather than a
cache, and it is why this has to land before any enrichment row is written.

The contract chosen here, all of it additive:

* the existing six top-level fields describe the gene's MOST RECENT search, so
  "was this searched, and when" stays true and gets more current;
* ``literature_other_positions`` is the UNION across searches, because a
  published cytoplasm-facing or function-abrogating insertion is a fact about
  the protein and does not stop being one because a later pass did not re-cite
  it;
* a new ``searches`` array names every pass by ``run_series`` and
  ``candidate_id``, which is the only place the per-member answers are visible.

The ordering is done in the Worker over all the rows rather than by ``ORDER BY``
+ ``.first()``: the rows are needed anyway for the union and the array, and a
choice made in JS is one this test can actually pin — a SQL ``ORDER BY`` would
be asserted against a stub that cannot honour it, which proves nothing.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

#: Deliberately returned newest-FIRST by one case and newest-LAST by the other,
#: because the whole point is that the DB's order must not decide the answer.
FIRST_PASS = {
    "gene_symbol": "KCNN2",
    "candidate_id": "",
    "run_series": "literature_v1",
    "prompt_sha": "a" * 64,
    "prompt_version": "1.4.0",
    "searched_at": "2026-10-11T00:00:00Z",
    "n_papers": 70,
    "n_sites": 0,
    "other_positions_json": json.dumps([{"position": 12, "why": "intracellular"}]),
    "notes": "no extracellular insertion published",
}
ENRICHED = {
    "gene_symbol": "KCNN2",
    "candidate_id": "l1-p1037",
    "run_series": "literature_enriched_v1",
    "prompt_sha": "b" * 64,
    "prompt_version": "2.0.0",
    "searched_at": "2026-10-18T00:00:00Z",
    "n_papers": 312,
    "n_sites": 1,
    "other_positions_json": json.dumps([{"position": 540, "why": "abrogates current"}]),
    "notes": "ECL2 insertion tolerated",
}


def _run(tmp_path: Path, gene_rows: list[dict], script: str) -> None:
    node = shutil.which("node")
    if node is None:
        if os.environ.get("REQUIRE_WORKER_NODE") == "1":
            pytest.fail("Shared API compatibility checks require Node; refusing to skip")
        pytest.skip("Node is required for Worker tests")
    source = (ROOT / "cloudflare/workers/surfaceome_api/src/index.js").read_text()
    source = source.replace(
        'import { deepDiveTier, isLowLiteratureSurface } from "../../../../viewer/lib/catalog-presets";',
        "const deepDiveTier = () => ({tier: 'no', facet: null}); "
        "const isLowLiteratureSurface = () => false;",
    )
    shutil.copy2(
        ROOT / "cloudflare/workers/surfaceome_api/src/contact-sites.js",
        tmp_path / "contact-sites.js",
    )
    (tmp_path / "worker.mjs").write_text(source)
    (tmp_path / "test.mjs").write_text(
        "import assert from \"node:assert/strict\";\n"
        "import worker from \"./worker.mjs\";\n"
        f"const GENE_ROWS = {json.dumps(gene_rows)};\n"
        """
globalThis.caches = { default: { match: async () => undefined, put: async () => {} } };
const env = {
  CF_VERSION_METADATA: { id: "t" },
  DB: {
    prepare(sql) {
      return {
        bind() { return this; },
        async all() {
          if (/FROM tag_site_gene_public/.test(sql)) return { results: GENE_ROWS };
          return { results: [] };
        },
        async first() {
          if (/FROM tag_site_gene_public/.test(sql)) return GENE_ROWS[0] ?? null;
          return null;
        },
      };
    },
  },
};
const ctx = { waitUntil() {} };
const body = await (await worker.fetch(
  new Request("https://api.test/surfaceome/v1/tag-sites/KCNN2"), env, ctx
)).json();
"""
        + script
    )
    subprocess.run(
        [node, str(tmp_path / "test.mjs")], check=True, capture_output=True, text=True
    )


def test_the_newest_search_answers_whichever_order_the_db_returns(
    tmp_path: Path,
) -> None:
    """Both orders, same answer. With ``.first()`` one of these two returns the
    2026-10-11 row and the other the 2026-10-18 row — the per-request coin
    flip."""
    for rows in ([FIRST_PASS, ENRICHED], [ENRICHED, FIRST_PASS]):
        _run(
            tmp_path,
            rows,
            """
assert.equal(body.generated_at, "2026-10-18T00:00:00Z");
assert.equal(body.prompt_version, "2.0.0");
assert.equal(body.n_papers_searched, 312);
""",
        )


def test_every_search_is_named_with_its_series_and_member(tmp_path: Path) -> None:
    """The only surface on which a per-member answer is visible at all."""
    _run(
        tmp_path,
        [FIRST_PASS, ENRICHED],
        """
assert.equal(body.searches.length, 2);
const byMember = Object.fromEntries(body.searches.map(s => [s.candidate_id, s]));
assert.equal(byMember[""].run_series, "literature_v1");
assert.equal(byMember[""].n_sites, 0);
assert.equal(byMember["l1-p1037"].run_series, "literature_enriched_v1");
assert.equal(byMember["l1-p1037"].n_papers, 312);
assert.equal(byMember["l1-p1037"].prompt_sha, "bbbbbbbbbbbb".padEnd(64, "b"));
""",
    )


def test_the_searches_are_ordered_newest_first(tmp_path: Path) -> None:
    _run(
        tmp_path,
        [FIRST_PASS, ENRICHED],
        """
assert.deepEqual(body.searches.map(s => s.run_series),
                 ["literature_enriched_v1", "literature_v1"]);
""",
    )


def test_no_passs_other_positions_are_lost(tmp_path: Path) -> None:
    """A published insertion that abrogates function is evidence about a
    known-bad site. Taking only the newest row's list would silently drop the
    first pass's — and nothing on the page would indicate it had."""
    _run(
        tmp_path,
        [FIRST_PASS, ENRICHED],
        """
const at = body.literature_other_positions.map(o => o.position).sort((a,b) => a-b);
assert.deepEqual(at, [12, 540]);
""",
    )


def test_a_duplicate_other_position_is_not_counted_twice(tmp_path: Path) -> None:
    """Both passes citing the same paper is the expected case, not the odd one."""
    _run(
        tmp_path,
        [FIRST_PASS, {**ENRICHED, "other_positions_json": FIRST_PASS["other_positions_json"]}],
        """
assert.equal(body.searches.length, 2);
assert.equal(body.literature_other_positions.length, 1);
assert.equal(body.literature_other_positions[0].position, 12);
""",
    )


def test_one_legacy_row_still_answers_exactly_as_before(tmp_path: Path) -> None:
    """2,370 genes have precisely this shape, and the production viewer reads
    ``prompt_sha`` to decide whether to say "Literature-validated (0)" at all."""
    _run(
        tmp_path,
        [FIRST_PASS],
        """
assert.equal(body.prompt_sha, "a".repeat(64));
assert.equal(body.prompt_version, "1.4.0");
assert.equal(body.generated_at, "2026-10-11T00:00:00Z");
assert.equal(body.n_papers_searched, 70);
assert.equal(body.literature_notes, "no extracellular insertion published");
assert.equal(body.literature_other_positions.length, 1);
assert.equal(body.searches.length, 1);
""",
    )


def test_an_unsearched_gene_still_claims_nothing(tmp_path: Path) -> None:
    """Absent row means never searched, which is the claim the table exists to
    make. An empty ``searches`` array must not read as a search."""
    _run(
        tmp_path,
        [],
        """
assert.equal(body.prompt_sha, null);
assert.equal(body.generated_at, null);
assert.deepEqual(body.searches, []);
assert.deepEqual(body.literature_other_positions, []);
assert.equal(body.has_data, false);
""",
    )
