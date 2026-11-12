"""The L1 design overlay: additive tables, an INSERT-only loader, and the Worker route.

Runs end to end on a synthetic design repository built in a temp dir (the real tables
live in a private repository and are never committed here): ``build`` -> ``sql`` ->
SQLite with the committed migration -> the real Worker router under Node.

Guards the regressions that would look fine and be wrong:

* the Worker selecting a column the migration does not define (a null overlay at serve
  time, not an error);
* the migration and the committed public schema drifting apart;
* the loader emitting anything but ``INSERT OR IGNORE`` -- a load must never update or
  delete a row, and re-applying it must be a no-op;
* the load row not going in last, which would let the Worker serve a half-applied load;
* a source table whose member id predates the renumbering being trusted over its design
  id (one real gate table named another gene's member for most of its rows);
* the route serving a missing load as a 500 instead of ``load: null``.
"""

from __future__ import annotations

import csv
import importlib.util
import io
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "cloudflare/migrations/l1_design_v1.sql"
SCHEMA = ROOT / "cloudflare/d1_public_schema.sql"
WORKER = ROOT / "cloudflare/workers/surfaceome_api/src/index.js"
LOADER = ROOT / "scripts/cloud/build_l1_design_tables.py"
BASE = "analysis/design"
SHA = "a" * 64


def _ddl() -> str:
    return "\n".join(
        ln for ln in MIGRATION.read_text().splitlines() if not ln.startswith("--")
    )


def _columns(table: str) -> set[str]:
    text = _ddl()
    block = text[text.index(f"CREATE TABLE IF NOT EXISTS {table}") :]
    block = block[block.index("(") + 1 : block.index(");")]
    cols = set()
    for line in block.splitlines():
        line = line.split("--")[0].strip().rstrip(",")
        if line and not line.upper().startswith("PRIMARY KEY"):
            cols.add(line.split()[0])
    return cols


def _handler() -> str:
    src = WORKER.read_text()
    start = src.index("async function handleL1Design")
    return src[start : src.index("\n}\n", start)]


def _loader():
    spec = importlib.util.spec_from_file_location("build_l1_design_tables", LOADER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_public_schema_mirrors_the_migration():
    assert MIGRATION.read_text() in SCHEMA.read_text()


@pytest.mark.parametrize(
    "table",
    [
        "l1_design_load_public",
        "l1_member_public",
        "l1_tag_site_design_public",
        "l1_structure_design_public",
    ],
)
def test_every_column_the_worker_selects_exists(table):
    found = False
    for m in re.finditer(r"SELECT (.*?)\s+FROM (\w+)", _handler(), re.S):
        if m.group(2) != table:
            continue
        found = True
        missing = {c.strip() for c in m.group(1).split(",")} - _columns(table)
        assert not missing, (
            f"{table}: Worker selects undefined columns {sorted(missing)}"
        )
    assert found, f"the Worker no longer reads {table}"


def test_loader_columns_match_the_migration():
    for table, cols in _loader().TABLES.values():
        assert set(cols) | {"load_version"} == _columns(table), table


# --------------------------------------------------------------------------- fixture


def _tsv(rows: list[dict]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, list(rows[0]), delimiter="\t", lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


def _member(mid, gene, placement, length, cset="library_reference", species="human"):
    return {
        "candidate_id": mid,
        "library": "l1",
        "candidate_set": cset,
        "species": species,
        "gene_symbol": gene,
        "placement": placement,
        "length_aa": str(length),
        "sequence_sha256": SHA,
        "topology_version": "topo_test",
    }


TABLES = {
    "renum.tsv": [
        {"design_id": f"l1-p000{i}", "candidate_id": f"l1-m000{i}"} for i in range(1, 9)
    ],
    "paths.tsv": [
        _member("l1-m0001", "GENEA", "C-terminal", 760),
        _member("l1-m0002", "GENEA", "C-terminal", 732, "ortholog", "cyno"),
        _member("l1-m0003", "GENEB", "N after SP", 894),
        _member("l1-m0004", "GENEC", "N at residue 1, single-pass (type III)", 224),
        _member("l1-m0005", "GENED", "N at residue 1, multipass", 413),
        _member("l1-m0006", "GENEE", "internal", 152),
        _member("l1-m0007", "GENEF", "internal", 424),
        _member("l1-m0008", "GENEG", "internal", 300, "ortholog", "cyno"),
    ],
    "payload.tsv": [
        {
            "release": "cf-test",
            "candidate_id": cid,
            "gene_symbol": g,
            "source": src,
            "r2_key": key,
            "model_url": url,
            "proteoform_match": "identical",
            "residue_offset": "0",
            "ordered_length_aa": "760",
            "model_length_aa": "760",
            "is_chosen": "1",
            "mean_plddt": "",
            "note": "",
        }
        for cid, g, src, key, url in [
            (
                "l1-m0001",
                "GENEA",
                "alphafold_db",
                "",
                "https://alphafold.example/AF-X-F1.pdb",
            ),
            (
                "l1-m0006",
                "GENEE",
                "colabfold",
                "library-colabfold/cf-test/l1-p0006.pdb",
                "",
            ),
            (
                "l1-p0999",
                "GONE",
                "alphafold_db",
                "",
                "https://alphafold.example/AF-Y-F1.pdb",
            ),
        ]
    ],
    "cterm.tsv": [
        {
            "candidate_id": cid,
            "design_id": pid,
            "gene_symbol": "GENEA",
            "candidate_set": cs,
            "species": sp,
            "native_aa": str(n),
            "protein_aa": str(n + 51),
            "placement": "C-terminal",
            "cassette_after_residue": str(n),
            "review_flags": "",
            "decided_by": "",
            "implemented_by": "",
            "reason": "",
            "protein_sha256": SHA,
        }
        for cid, pid, cs, sp, n in [
            ("l1-m0001", "l1-p0001", "library_reference", "human", 760),
            ("l1-m0002", "l1-p0002", "ortholog", "cyno", 732),
        ]
    ],
    "nsp.tsv": [
        {
            "candidate_id": "l1-m0003",
            "design_id": "l1-p0003",
            "gene_symbol": "GENEB",
            "candidate_set": "library_reference",
            "subgroup": "preserved_before_fold",
            "status": "ready",
            "cleavage_site": "32",
            "insert_after_residue": "34",
            "residue_before": "E",
            "residue_after": "S",
            "tagged_protein_sha256": SHA,
            "decided_by": "Becca, test",
            "implemented_by": "test builder",
            "reason": "gated site",
        },
    ],
    "t3.tsv": [
        {
            "candidate_id": "l1-m0004",
            "design_id": "l1-p0004",
            "gene_symbol": "GENEC",
            "candidate_set": "library_reference",
            "species": "human",
            "subgroup": "long_tail",
            "design": "igk_tag",
            "native_aa": "224",
            "protein_aa": "296",
            "mature_aa": "275",
            "cassette": "full 51 aa",
            "decided_by": "Becca, test",
            "implemented_by": "test builder",
            "reason": "risk",
            "protein_sha256": SHA,
        },
    ],
    "mp.tsv": [
        {
            "design_id": "l1-p0005",
            "candidate_id": "l1-m0005",
            "candidate_set": "library_reference",
            "species": "human",
            "gene_symbol": "GENED",
            "group": "GPCR",
            "leader_subgroup": "5 none",
            "planned_leader": "igk",
            "planned_leader_decided_by": "Becca, test",
            "planned_leader_implemented_by": "test builder",
            "planned_leader_reason": "locks N-out",
            "cassette": "full 51 aa",
            "cassette_decided_by": "Becca, test",
        },
    ],
    "lane.tsv": [
        {
            "candidate_id": "l1-m0005",
            "lane_ok": "yes",
            "recommended_lane": "N at residue 1, multipass",
            "confidence": "high",
            "decided_by": "no decision taken",
            "implemented_by": "lane checker",
        },
    ],
    "gate.tsv": [
        # Member id predates the renumbering (names GENEA's member); design id is right.
        {
            "candidate_id": "l1-m0001",
            "design_id": "l1-p0006",
            "gene_symbol": "GENEE",
            "candidate_set": "library_reference",
            "species": "human",
            "source": src,
            "site_id": sid,
            "rank": rank,
            "shipped": shipped,
            "insert_after_residue": res,
            "residue_before": "V",
            "residue_after": "S",
            "height_A": "30.4",
            "plddt": "69.8",
            "verdict": verdict,
            "reason": "r",
            "decided_by": "Becca, test",
            "implemented_by": "gate",
        }
        for src, sid, rank, shipped, res, verdict in [
            ("s5e13_v4", "l1-p0006-v4-r1", "1.0", "1", "94.0", "pass"),
            ("s5e13_v4", "l1-p0006-v4-r2", "2.0", "1", "26.0", "fail_membrane"),
            ("api_surface_loop", "cand-1", "", "0", "40.0", "pass"),
        ]
    ],
    "extra.tsv": [
        {
            "gene": "GENEF",
            "rank": "1",
            "insert_after_residue": "273",
            "why": "only region",
        }
    ],
}

PINS = {
    "renumbering": "renum.tsv",
    "tag_paths": "paths.tsv",
    "structure_payload": "payload.tsv",
    "cterm": "cterm.tsv",
    "nterm_sp": "nsp.tsv",
    "type3": "t3.tsv",
    "multipass": "mp.tsv",
    "multipass_lane_check": "lane.tsv",
    "internal_gate": "gate.tsv",
    "internal_slc67a1": "extra.tsv",
}


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("l1design")
    repo = tmp / "design-repo"
    (repo / BASE).mkdir(parents=True)
    for name, rows in TABLES.items():
        (repo / BASE / name).write_text(_tsv(rows))
    git = ["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t"]
    subprocess.run([*git, "init", "-q"], check=True)
    subprocess.run([*git, "add", "."], check=True)
    subprocess.run([*git, "commit", "-qm", "fixture"], check=True)
    commit = subprocess.run(
        [*git, "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()
    sources = {}
    for key, path in PINS.items():
        sources[key] = {
            "pr": 1,
            "ref": "fixture",
            "commit": commit,
            "path": path,
            "state": "open",
        }
    sources["internal_slc67a1"].update(
        member_id="l1-m0007", gate_note="gate passed (test)"
    )
    pins = tmp / "pins.json"
    pins.write_text(
        json.dumps(
            {
                "analysis_repo": "test/design",
                "base_dir": BASE,
                "sources": sources,
                "tagged_structures": [],
            }
        )
    )
    data = tmp / "data"
    run = [sys.executable, str(LOADER)]
    subprocess.run(
        [
            *run,
            "build",
            "--pins",
            str(pins),
            "--data-dir",
            str(data),
            "--analysis-repo",
            str(repo),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    sql = tmp / "load.sql"
    subprocess.run(
        [*run, "sql", "--data-dir", str(data), "--out", str(sql)],
        check=True,
        capture_output=True,
    )
    redacted = tmp / "load_redacted.sql"
    subprocess.run(
        [
            *run,
            "sql",
            "--data-dir",
            str(data),
            "--out",
            str(redacted),
            "--redact-internal",
        ],
        check=True,
        capture_output=True,
    )
    return {"tmp": tmp, "data": data, "sql": sql, "redacted": redacted}


def _rows(data: Path, name: str) -> dict[str, dict]:
    with (data / f"l1_design_{name}.tsv").open() as fh:
        rows = list(csv.DictReader(fh, delimiter="\t"))
    key = {"members": "member_id", "sites": "site_id", "structures": "structure_id"}[
        name
    ]
    return {r[key]: r for r in rows}


def test_build_maps_every_rung(built):
    sites = _rows(built["data"], "sites")
    assert set(sites) == {
        "l1-m0001-cterm-760",
        "l1-m0002-cterm-732",
        "l1-m0003-nsp-34",
        "l1-m0004-type3-r1",
        "l1-m0005-res1",
        "l1-p0006-v4-r1",
        "l1-p0006-v4-r2",
        "l1-p0007-v4-r1",
    }, "the API candidate pool (api_* rows) must not load as suggestions"
    assert sites["l1-m0001-cterm-760"]["status"] == "built"
    assert sites["l1-m0001-cterm-760"]["cassette_aa"] == "51"
    assert sites["l1-m0001-cterm-760"]["decided_by"].startswith(
        "no individual decision"
    )
    assert (
        sites["l1-m0003-nsp-34"]["residue_before"],
        sites["l1-m0003-nsp-34"]["status"],
    ) == ("E", "built")
    t3 = sites["l1-m0004-type3-r1"]
    assert (t3["leader"], t3["insert_after_residue"], t3["cassette_aa"]) == (
        "igk",
        "1",
        "51",
    )
    mp = sites["l1-m0005-res1"]
    assert (mp["leader"], mp["status"]) == ("igk", "proposed")
    assert "lane_ok=yes" in mp["status_detail"]
    assert sites["l1-p0006-v4-r1"]["status"] == "proposed"
    assert sites["l1-p0006-v4-r2"]["status"] == "held"
    assert sites["l1-p0007-v4-r1"]["member_id"] == "l1-m0007"


def test_stale_member_ids_resolve_by_design_id(built):
    site = _rows(built["data"], "sites")["l1-p0006-v4-r1"]
    assert (site["member_id"], site["gene_symbol"]) == ("l1-m0006", "GENEE")
    assert "pre-renumbering" in site["status_detail"]


def test_structures_skip_ids_with_no_member(built):
    structs = _rows(built["data"], "structures")
    assert {s["member_id"] for s in structs.values()} == {"l1-m0001", "l1-m0006"}
    ours = next(s for s in structs.values() if s["member_id"] == "l1-m0006")
    assert ours["r2_key"] == "library-colabfold/cf-test/l1-p0006.pdb"


def test_members_without_sites_are_reported(built):
    manifest = json.loads((built["data"] / "manifest.json").read_text())
    assert manifest["counts"]["members_without_site"] == ["l1-m0008"]


def _apply(sql: Path, db: sqlite3.Connection) -> dict[str, int]:
    db.executescript(sql.read_text())
    return {
        t: db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        for t in (
            "l1_member_public",
            "l1_tag_site_design_public",
            "l1_structure_design_public",
            "l1_design_load_public",
        )
    }


def test_sql_is_insert_only_idempotent_and_load_row_last(built):
    text = built["sql"].read_text()
    statements = [s.strip() for s in text.split(";\n") if s.strip()]
    bodies = [
        "\n".join(ln for ln in s.splitlines() if not ln.startswith("--")).strip()
        for s in statements
    ]
    bodies = [b for b in bodies if b]
    for b in bodies:
        assert b.startswith("INSERT OR IGNORE INTO "), b[:80]
        assert len(b.encode()) < 100_000, "D1 rejects statements over 100 KB"
    assert bodies[-1].startswith("INSERT OR IGNORE INTO l1_design_load_public")
    assert sum("l1_design_load_public" in b for b in bodies) == 1

    db = sqlite3.connect(":memory:")
    db.executescript(MIGRATION.read_text())
    first = _apply(built["sql"], db)
    assert first == {
        "l1_member_public": 8,
        "l1_tag_site_design_public": 8,
        "l1_structure_design_public": 2,
        "l1_design_load_public": 1,
    }
    assert _apply(built["sql"], db) == first


def test_redacted_sql_drops_the_internal_record(built):
    db = sqlite3.connect(":memory:")
    db.executescript(MIGRATION.read_text())
    _apply(built["redacted"], db)
    rows = db.execute(
        "SELECT source_pr, source_commit, decided_by, implemented_by, reason FROM l1_tag_site_design_public"
    ).fetchall()
    L = _loader()
    assert all(r[0] is None for r in rows)
    assert all(v in (L.REDACTED, None) for r in rows for v in r[1:])
    match = re.search(r"l1d-[0-9a-f]{16}", built["sql"].read_text())
    assert match
    full = match.group(0)
    lv, raw_inputs = db.execute(
        "SELECT load_version, inputs_json FROM l1_design_load_public"
    ).fetchone()
    assert lv != full, "redacted and full loads must not share a load_version"
    inputs = json.loads(raw_inputs)
    assert all(
        set(v) <= {"sha256", "n"} for v in inputs.values() if isinstance(v, dict)
    )
    # The design itself survives.
    assert db.execute(
        "SELECT insert_after_residue FROM l1_tag_site_design_public WHERE site_id = 'l1-m0001-cterm-760'"
    ).fetchone() == (760,)


def test_worker_route_against_sqlite(built):
    node = shutil.which("node")
    if node is None:
        if os.environ.get("REQUIRE_WORKER_NODE") == "1":
            pytest.fail("Worker checks require Node; refusing to skip")
        pytest.skip("Node is required for Worker tests")
    if subprocess.run(
        [node, "-e", "require('node:sqlite')"], capture_output=True
    ).returncode:
        pytest.skip("this Node has no node:sqlite")

    tmp = built["tmp"] / "worker"
    tmp.mkdir()
    db_path = tmp / "public.sqlite"
    db = sqlite3.connect(db_path)
    db.executescript(MIGRATION.read_text())
    db.executescript(built["sql"].read_text())
    db.commit()
    db.close()
    empty_path = tmp / "empty.sqlite"
    sqlite3.connect(empty_path).close()

    source = WORKER.read_text().replace(
        'import { deepDiveTier, isLowLiteratureSurface } from "../../../../viewer/lib/catalog-presets";',
        "const deepDiveTier = () => ({tier: 'no', facet: null}); const isLowLiteratureSurface = () => false;",
    )
    for js in WORKER.parent.glob("*.js"):
        if js.name != "index.js":
            shutil.copy2(js, tmp / js.name)
    (tmp / "worker.mjs").write_text(source)
    (tmp / "test.mjs").write_text(
        r"""
import assert from "node:assert/strict";
import { DatabaseSync } from "node:sqlite";
import worker from "./worker.mjs";

globalThis.caches = { default: { match: async () => undefined, put: async () => {} } };
const d1 = (path) => {
  const db = new DatabaseSync(path);
  return {
    prepare(sql) {
      let args = [];
      return {
        bind(...v) { args = v; return this; },
        async all() { return { results: db.prepare(sql).all(...args) }; },
        async first() { return db.prepare(sql).get(...args) ?? null; },
      };
    },
  };
};
const ctx = { waitUntil() {}, passThroughOnException() {} };
const get = async (path, file) => {
  const res = await worker.fetch(new Request(`https://api.test${path}`), { DB: d1(file) }, ctx);
  return [res.status, res.status === 200 ? await res.json() : null];
};
const [db, empty] = process.argv.slice(2);

let [status, body] = await get("/v1/l1-design/GENEA", db);
assert.equal(status, 200);
assert.match(body.load.load_version, /^l1d-[0-9a-f]{16}$/);
assert.deepEqual(body.members.map((m) => [m.member_id, m.species]), [["l1-m0001", "human"], ["l1-m0002", "cyno"]]);
const ref = body.members[0];
assert.equal(ref.sites[0].insert_after_residue, 760);
assert.equal(ref.sites[0].status, "built");
assert.equal(ref.sites[0].source.pr, 1);
assert.equal(ref.structures[0].kind, "native");
assert.equal(ref.structures[0].is_chosen, true);
assert.equal(ref.structures[0].display_last_model_residue, 760);
const lv = body.load.load_version;

[status, body] = await get("/v1/l1-design/genee", db);  // case-insensitive
assert.deepEqual(body.members[0].sites.map((s) => [s.rank, s.status]), [[1, "proposed"], [2, "held"]]);
assert.equal(body.members[0].structures[0].r2_key, "library-colabfold/cf-test/l1-p0006.pdb");

[status, body] = await get(`/v1/l1-design/GENEA/${lv}`, db);
assert.equal(status, 200);
[status] = await get(`/v1/l1-design/GENEA/l1d-0000000000000000`, db);
assert.equal(status, 404);
[status] = await get(`/v1/l1-design/GENEA/not-a-load`, db);
assert.equal(status, 400);

// A gene with no L1 member: 200, empty.
[status, body] = await get("/v1/l1-design/NOTL1", db);
assert.equal(status, 200);
assert.deepEqual(body.members, []);

// Worker deployed before the migration: degrade, never 500.
[status, body] = await get("/v1/l1-design/GENEA", empty);
assert.equal(status, 200);
assert.equal(body.load, null);
console.log("ok");
"""
    )
    res = subprocess.run(
        [node, "test.mjs", str(db_path), str(empty_path)],
        cwd=tmp,
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, res.stdout + res.stderr
    assert "ok" in res.stdout
