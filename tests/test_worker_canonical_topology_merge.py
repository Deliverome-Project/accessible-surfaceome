"""Filling DeepTMHMM's call into a stored topology block keeps the block's keys.

Records store ``canonical_topology.predicted_surface_membrane`` (and
``predicted_secreted``, ``beta_strand_count``, ``protein_length``) as explicit
nulls, because the Python builder didn't select those columns until
2026-10-17. #384 made the Worker fill them from ``topology_public``, but it did
so by rebuilding the whole block, which dropped every key the rebuild doesn't
write (``ecd_pct_identity_to_canonical``, ``per_residue_topology_canonical_frame``,
…) from every served record. This runs ``/v1/genes/{SYMBOL}`` on an in-memory
SQLite database and checks that the call is filled while the stored block is
otherwise served exactly as stored, and that a record with no block still gets
a full one.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]

_STORED_BLOCK = {
    "isoform_id": "P00001-1",
    "uniprot_acc": "P00001",
    "tm_helix_count": 1,
    "n_terminal_orientation": "extracellular",
    "c_terminal_orientation": "cytoplasmic",
    "signal_peptide_length": 20,
    "ecd_length_residues": 270,
    "icd_length_residues": 240,
    "per_residue_topology": "S" * 20 + "O" * 270 + "M" * 21 + "I" * 240,
    "sequence": "M" * 551,
    "tool_version": "deeptmhmm-1.0.24",
    "retrieved_at": "2026-07-01T00:00:00Z",
    "ecd_pct_identity_to_canonical": None,
    "ecd_pct_similarity_to_canonical": None,
    "full_length_pct_identity_to_canonical": None,
    "per_residue_topology_canonical_frame": None,
    "predicted_surface_membrane": None,
    "predicted_secreted": None,
    "beta_strand_count": None,
    "protein_length": None,
}

_HARNESS = r"""
import { readFileSync, writeFileSync } from "node:fs";
import { DatabaseSync } from "node:sqlite";
import worker from "./worker.mjs";

const fixture = JSON.parse(readFileSync(process.argv[2], "utf8"));
const db = new DatabaseSync(":memory:");
db.exec(`
  CREATE TABLE surface_annotation (gene_symbol TEXT, schema_version TEXT,
    annotation_json TEXT, annotated_at TEXT, prompt_corpus_version TEXT,
    cohort_run_id TEXT);
  CREATE TABLE topology_release (topology_version TEXT, loaded_at TEXT);
  CREATE TABLE topology_public (uniprot_acc TEXT, uniprot_acc_full TEXT,
    isoform_id TEXT, cohort TEXT, topology_version TEXT, tm_helix_count INTEGER,
    n_terminal_orientation TEXT, c_terminal_orientation TEXT,
    signal_peptide_length INTEGER, ecd_length_residues INTEGER,
    icd_length_residues INTEGER, per_residue_topology TEXT, sequence TEXT,
    tool_version TEXT, retrieved_at TEXT, predicted_surface_membrane INTEGER,
    predicted_secreted INTEGER, beta_strand_count INTEGER, protein_length INTEGER);
  INSERT INTO topology_release VALUES ('v1', '2026-01-01');
`);
const ins = (table, row) => {
  const cols = Object.keys(row);
  db.prepare(`INSERT INTO ${table} (${cols.join(",")}) VALUES (${cols.map(() => "?").join(",")})`)
    .run(...cols.map((c) => row[c]));
};
for (const r of fixture.records) ins("surface_annotation", r);
for (const r of fixture.topology) ins("topology_public", r);

const env = {
  CF_VERSION_METADATA: { id: "test" },
  DB: {
    prepare(sql) {
      let args = [];
      return {
        bind(...v) { args = v; return this; },
        async all() { return { results: db.prepare(sql).all(...args) }; },
        async first() { return db.prepare(sql).get(...args) ?? null; },
      };
    },
  },
};
globalThis.caches = { default: { match: async () => undefined, put: async () => {} } };
const out = {};
for (const sym of fixture.symbols) {
  const pending = [];
  const r = await worker.fetch(
    new Request(`https://api.deliverome.org/surfaceome/v1/genes/${sym}`),
    env, { waitUntil(p) { pending.push(p); } });
  await Promise.all(pending);
  out[sym] = { status: r.status, degraded: r.headers.get("X-Surfaceome-Degraded"), body: await r.json() };
}
writeFileSync(process.argv[3], JSON.stringify(out));
"""


def _record(symbol: str, acc: str, block: dict | None) -> dict:
    df = {} if block is None else {"canonical_topology": block}
    rec = {"gene": {"hgnc_symbol": symbol, "uniprot_acc": acc}, "deterministic_features": df}
    return {
        "gene_symbol": symbol,
        "schema_version": "2.14.2",
        "annotation_json": json.dumps(rec),
        "annotated_at": "2026-07-01",
        "prompt_corpus_version": "1.0.0",
        "cohort_run_id": "test",
    }


def _topology(acc: str) -> dict:
    return {
        "uniprot_acc": acc,
        "uniprot_acc_full": acc,
        "isoform_id": f"{acc}-1",
        "cohort": "human_canonical",
        "topology_version": "v1",
        "tm_helix_count": 9,  # deliberately differs from the stored block
        "n_terminal_orientation": "extracellular",
        "c_terminal_orientation": "cytoplasmic",
        "signal_peptide_length": 0,
        "ecd_length_residues": 1,
        "icd_length_residues": 1,
        "per_residue_topology": "OMI",
        "sequence": "MAA",
        "tool_version": "deeptmhmm-1.0.24",
        "retrieved_at": "2026-08-01T00:00:00Z",
        "predicted_surface_membrane": 1,
        "predicted_secreted": 0,
        "beta_strand_count": 0,
        "protein_length": 551,
    }


@pytest.fixture(scope="module")
def served(tmp_path_factory: pytest.TempPathFactory) -> dict:
    node = shutil.which("node")
    if node is None:
        if os.environ.get("REQUIRE_WORKER_NODE") == "1":
            pytest.fail("Worker checks require Node; refusing to skip")
        pytest.skip("Node is required for Worker tests")
    tmp = tmp_path_factory.mktemp("topology_merge")
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
    fixture = {
        "symbols": ["GENEX", "GENEY"],
        "records": [
            _record("GENEX", "P00001", dict(_STORED_BLOCK)),
            _record("GENEY", "P00002", None),
        ],
        "topology": [_topology("P00001"), _topology("P00002")],
    }
    (tmp / "fixture.json").write_text(json.dumps(fixture))
    result = subprocess.run(
        [node, "--no-warnings", str(tmp / "harness.mjs"), str(tmp / "fixture.json"), str(tmp / "out.json")],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    return json.loads((tmp / "out.json").read_text())


def test_filling_the_call_keeps_every_stored_key(served: dict) -> None:
    resp = served["GENEX"]
    assert resp["status"] == 200 and resp["degraded"] is None
    block = resp["body"]["deterministic_features"]["canonical_topology"]
    assert block["predicted_surface_membrane"] is True
    assert block["predicted_secreted"] is False
    assert block["beta_strand_count"] == 0
    assert block["protein_length"] == 551
    filled = {"predicted_surface_membrane", "predicted_secreted", "beta_strand_count", "protein_length"}
    # Everything else, explicit nulls included, is served exactly as stored.
    assert {k: v for k, v in block.items() if k not in filled} == {
        k: v for k, v in _STORED_BLOCK.items() if k not in filled
    }


def test_a_record_without_a_block_still_gets_a_full_one(served: dict) -> None:
    block = served["GENEY"]["body"]["deterministic_features"]["canonical_topology"]
    assert block["tm_helix_count"] == 9
    assert block["per_residue_topology"] == "OMI"
    assert block["predicted_surface_membrane"] is True and block["protein_length"] == 551
