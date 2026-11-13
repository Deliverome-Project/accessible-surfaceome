"""The L1 design overlay and review page: additive tables, an INSERT-only loader, and
the Worker routes.

Runs end to end on a synthetic design repository built in a temp dir (the real tables
live in a private repository and are never committed here): ``build`` -> ``sql`` ->
SQLite with the committed migrations -> the real Worker router under Node.

Guards the regressions that would look fine and be wrong:

* the Worker selecting a column the migration does not define (a null overlay at serve
  time, not an error);
* the migration and the committed public schema drifting apart;
* the loader emitting anything but ``INSERT OR IGNORE`` -- a load must never update or
  delete a row, and re-applying it must be a no-op;
* the load row not going in last, which would let the Worker serve a half-applied load;
* a source row joined on member id (still being renumbered) instead of design id +
  sequence sha256, or a stale row (sequence changed) loaded as current;
* agent picks numbered on the canonical loaded onto a member whose protein differs;
* the review endpoints accepting a write without the token, or running open when the
  token secret is unset;
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
REVIEW_MIGRATION = ROOT / "cloudflare/migrations/l1_review_v1.sql"
SCHEMA = ROOT / "cloudflare/d1_public_schema.sql"
WORKER = ROOT / "cloudflare/workers/surfaceome_api/src/index.js"
LOADER = ROOT / "scripts/cloud/build_l1_design_tables.py"
BASE = "analysis/design"
SHA = {g: (c * 64) for g, c in zip("ABCDEFGH", "abcdef01", strict=True)}


def _ddl(path: Path = MIGRATION) -> str:
    return "\n".join(
        ln for ln in path.read_text().splitlines() if not ln.startswith("--")
    )


def _columns(table: str, path: Path = MIGRATION) -> set[str]:
    text = _ddl(path)
    block = text[text.index(f"CREATE TABLE IF NOT EXISTS {table}") :]
    block = block[block.index("(") + 1 : block.index(");")]
    cols = set()
    for line in block.splitlines():
        line = line.split("--")[0].strip().rstrip(",")
        if (
            line
            and not line.upper().startswith(("PRIMARY KEY", "("))
            and not line.startswith("'")
        ):
            cols.add(line.split()[0])
    return cols


def _worker_fn(name: str) -> str:
    src = WORKER.read_text()
    start = src.index(f"async function {name}(")
    return src[start : src.index("\n}\n", start)]


def _loader():
    spec = importlib.util.spec_from_file_location("build_l1_design_tables", LOADER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_public_schema_mirrors_the_migration():
    assert MIGRATION.read_text() in SCHEMA.read_text()


def test_review_tables_are_not_in_the_public_schema():
    """Reviews live in the private agents database only."""
    public = SCHEMA.read_text()
    assert "l1_review" not in public and "l1_alt_tag" not in public


@pytest.mark.parametrize(
    "table",
    [
        "l1_design_load_public",
        "l1_member_public",
        "l1_tag_site_design_public",
        "l1_structure_design_public",
        "l1_contact_site_public",
    ],
)
def test_every_column_the_worker_selects_exists(table):
    src = (
        _worker_fn("handleL1Design")
        + _worker_fn("handleL1DesignIndex")
        + _worker_fn("l1Load")
    )
    load_cols = re.search(r'L1_LOAD_COLS =\s*"([^"]+)"', WORKER.read_text())
    assert load_cols, "L1_LOAD_COLS moved"
    src = src.replace("${L1_LOAD_COLS}", load_cols.group(1))
    found = False
    for m in re.finditer(r"SELECT (.*?)\s+FROM (\w+)", src, re.S):
        if m.group(2) != table:
            continue
        found = True
        selected = {
            re.sub(r"\s+AS\s+\w+$", "", c.strip()) for c in m.group(1).split(",")
        }
        selected = {c for c in selected if not c.upper().startswith("COUNT(")}
        missing = selected - _columns(table)
        assert not missing, (
            f"{table}: Worker selects undefined columns {sorted(missing)}"
        )
    assert found, f"the Worker no longer reads {table}"


def test_review_inserts_match_the_review_migration():
    src = _worker_fn("handleL1ReviewSubmit")
    for table in ("l1_review", "l1_alt_tag"):
        m = re.search(rf"INSERT INTO {table} \((.*?)\)", src, re.S)
        assert m, table
        cols = {c.strip() for c in m.group(1).split(",")}
        assert cols == _columns(table, REVIEW_MIGRATION), table


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


def _member(
    mid, gene, placement, length, n_tm, key, cset="library_reference", species="human"
):
    return {
        "candidate_id": mid, "library": "l1", "candidate_set": cset, "species": species,
        "gene_symbol": gene, "placement": placement, "n_tm": str(n_tm), "length_aa": str(length),
        "sequence_sha256": SHA[key], "topology_version": "topo_test",
    }  # fmt: skip


def _ranker(design, gene, sha, res, rank, **kw):
    return {
        "member_id": "l1-m9999", "design_id": design, "gene": gene, "candidate_set": "library_reference",
        "sequence_sha256": sha, "insert_after_residue": f"{res}.0" if res != "" else "", "rank": str(rank),
        "rank_score": "0.8",
        "absolute_score": "0.7", "best_region_pct_of_published_regions": "0.5",
        "this_region_length": "19", "snorkel_candidate": "False",
        "decided_by": "ranker session (delegated by Becca 2026-11-12)", "implemented_by": "ranker",
        **kw,
    }  # fmt: skip


GIT_TABLES = {
    "renum.tsv": [
        {"design_id": f"l1-p000{i}", "candidate_id": f"l1-m000{i}"} for i in range(1, 9)
    ],
    "paths.tsv": [
        _member("l1-m0001", "GENEA", "C-terminal", 760, 1, "A"),
        _member("l1-m0002", "GENEA", "C-terminal", 732, 1, "B", "ortholog", "cyno"),
        _member("l1-m0003", "GENEB", "N after SP", 894, 1, "C"),
        _member(
            "l1-m0004", "GENEC", "N at residue 1, single-pass (type III)", 224, 1, "D"
        ),
        _member("l1-m0005", "GENED", "N at residue 1, multipass", 413, 7, "E"),
        _member("l1-m0006", "GENEE", "internal", 152, 4, "F"),
        _member("l1-m0007", "SLC9Z9", "internal", 424, 12, "G"),
        _member("l1-m0008", "GENEG", "internal", 300, 4, "H", "ortholog", "cyno"),
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
    ],  # fmt: skip
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
            "junction_edit": "",
            "worst_partner_tract_nt": "33",
            "worst_partner": "l1-m0002",
            "cassette_features": "",
            "review_flags": "",
            "decided_by": "",
            "implemented_by": "",
            "reason": "",
            "protein_sha256": SHA["A"],
        }
        for cid, pid, cs, sp, n in [
            # The member id here is deliberately wrong (renumbered since): the loader
            # must resolve on design id.
            ("l1-m0077", "l1-p0001", "library_reference", "human", 760),
            # l1-p0002 has no construct: its decision is a hold (cterm_decisions.tsv).
            ("l1-m0099", "l1-p3001", "ortholog", "cyno", 500),  # not in the universe
        ]
    ]
    + [
        # A snorkel built by the C-terminal builder for an internal-rung member; its
        # cassette_after_residue counts the added 55-aa TM module.
        {
            "candidate_id": "l1-m0008",
            "design_id": "l1-p0008",
            "gene_symbol": "GENEG",
            "candidate_set": "ortholog",
            "species": "cyno",
            "native_aa": "300",
            "protein_aa": "406",
            "placement": "snorkel (TM module, then cassette)",
            "cassette_after_residue": "355",
            "junction_edit": "",
            "worst_partner_tract_nt": "",
            "worst_partner": "",
            "cassette_features": "",
            "review_flags": "",
            "decided_by": "",
            "implemented_by": "",
            "reason": "",
            "protein_sha256": "5" * 64,
        },
    ],  # fmt: skip
    "cterm_decisions.tsv": [
        {
            "scope": "l1-m0001 (l1-p0001) GENEA human",
            "question": "terminus inside a fold",
            "decision": "keep the cassette at the C-terminus",
            "rejected_alternatives": "stalk site 700",
            "evidence": "terminal pLDDT 86",
            "decided_by": "cterm session (delegated by the reviewer 2026-11-12)",
            "implemented_by": "cterm builder",
            "reason": "no stalk",
            "would_change_it": "a failed refold",
        },
        {
            "scope": "l1-m0002 (l1-p0002) GENEA cyno",
            "question": "tagged refold failed",
            "decision": "hold (not built)",
            "rejected_alternatives": "keep the C-terminal tag",
            "evidence": "site lDDT 0.39",
            "decided_by": "cterm session (delegated by the reviewer 2026-11-12)",
            "implemented_by": "cterm builder",
            "reason": "a failed fold is held",
            "would_change_it": "a passing alternative site",
        },
    ],  # fmt: skip
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
            "tagged_protein_sha256": SHA["C"],
            "decided_by": "Becca, test",
            "implemented_by": "test builder",
            "reason": "gated site",
        },
    ],  # fmt: skip
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
            "cassette_decided_by": "Becca",
            "reviewed_by": "",
            "implemented_by": "test builder",
            "reason": "risk",
            "protein_sha256": SHA["D"],
        },
    ],  # fmt: skip
    "mp.tsv": [
        {
            "construct_id": f"l1-p0005:{d}",
            "design_id": "l1-p0005",
            "candidate_id": "l1-m0005",
            "gene_symbol": "GENED",
            "candidate_set": "library_reference",
            "species": "human",
            "gpcr": "1",
            "design": d,
            "status": st,
            "native_aa": "413",
            "protein_aa": "485",
            "mature_aa": "464",
            "cassette": "full 51 aa",
            "decided_by": "Becca, test",
            "cassette_decided_by": "Becca",
            "implemented_by": "mp builder",
            "reason": "locks N-out",
            "protein_sha256": SHA["E"],
            "native_sha256": SHA["E"],
        }
        for d, st in [("tag_alone", "proposed"), ("igk_tag", "decided")]
    ],  # fmt: skip
    "lane.tsv": [
        {
            "design_id": "l1-p0005",
            "candidate_id": "l1-m0005",
            "lane_ok": "yes",
            "recommended_lane": "N at residue 1, multipass",
            "confidence": "high",
            "evidence": "v1",
            "decided_by": "no decision taken",
            "implemented_by": "lane checker",
        },
    ],  # fmt: skip
    "gate.tsv": [
        {
            "candidate_id": "l1-m0001",
            "design_id": "l1-p0006",
            "gene_symbol": "GENEE",
            "candidate_set": "library_reference",
            "species": "human",
            "source": src,
            "site_id": sid,
            "rank": "",
            "shipped": shipped,
            "insert_after_residue": "120.0",
            "residue_before": "F",
            "residue_after": "L",
            "height_A": "19.3",
            "plddt": "75.9",
            "verdict": "pass",
            "reason": "r",
            "decided_by": "Becca, test",
            "implemented_by": "gate",
        }
        for src, sid, shipped in [
            ("built_loop_arm", "GENEE-F120", "1"),
            ("api_surface_loop", "cand-1", "0"),
        ]
    ],  # fmt: skip
    "internal_constructs.tsv": [
        # Built at 26, but the decision is 94: the decision must NOT show as built.
        {
            "design_id": "l1-p0006",
            "cassette_after_residue": "26",
            "junction": "G26|T27",
            "native_aa": "152",
            "protein_aa": "203",
            "protein_sha256": "4" * 64,
            "refold_verdict": "pass",
            "built_by": "integration",
        },
    ],  # fmt: skip
    "proteoform.tsv": [
        {
            "design_id": "l1-p0004",
            "gene_symbol": "GENEC",
            "decision": "repair",
            "target": "start at Met5",
            "status": "apply",
            "flags": "",
            "flag_class": "proposed",
            "reason": "extension",
            "alternative_rejected": "keep",
            "decided_by": "audit session",
            "implemented_by": "audit",
        },
    ],  # fmt: skip
    "agent.tsv": [
        {
            "arm": arm,
            "gene": gene,
            "uniprot_acc": "PX",
            "rank": "1",
            "insert_after_residue": "88",
            "residue_before": "K",
            "residue_after": "D",
            "loop_index": "0",
            "confidence": "medium",
            "fields_used": "plddt",
            "reason": "long loop",
            "abstained": "False",
            "validation": "",
            "n_rejected_loops": "2",
        }
        for arm, gene in [("full", "GENEE"), ("noranker", "GENEE"), ("full", "GENEG")]
    ],  # fmt: skip
}
S3_TABLES = {
    "decisions.tsv": [
        _ranker(
            "l1-p0006",
            "GENEE",
            SHA["F"],
            94,
            1,
            pick_rank="1.0",
            decision="internal_loop",
            confidence="medium",
            reason="v5 rank-1",
            rejected_alternative="v5 rank-2 pick",
            decided_on="2026-11-12",
            refold_verdict="pending",
        ),
        _ranker(
            "l1-p0007",
            "SLC9Z9",
            SHA["G"],
            "",
            1,
            pick_rank="",
            decision="route_to_nterm_after_sp",
            confidence="low",
            reason="no loop",
            rejected_alternative="snorkel",
            decided_on="2026-11-12",
            refold_verdict="",
        ),
        # Stale: the member's sequence changed since the decision was made.
        _ranker(
            "l1-p0008",
            "GENEG",
            "0" * 64,
            40,
            1,
            pick_rank="1.0",
            decision="internal_loop",
            confidence="low",
            reason="x",
            rejected_alternative="",
            decided_on="",
            refold_verdict="",
        ),
        _ranker(
            "l1-p0008",
            "GENEG",
            SHA["H"],
            "",
            1,
            pick_rank="",
            decision="snorkel",
            confidence="low",
            reason="no usable loop",
            rejected_alternative="internal loop 2",
            decided_on="2026-11-12",
            refold_verdict="",
        ),  # fmt: skip
    ],
    "proposed.tsv": [
        _ranker(
            "l1-p0006",
            "GENEE",
            SHA["F"],
            94,
            1,
            junction="V94|S95",
            why="best",
            refold_priority="1",
        ),
        _ranker(
            "l1-p0006",
            "GENEE",
            SHA["F"],
            26,
            2,
            junction="G26|T27",
            why="runner-up",
            refold_priority="2",
        ),
        _ranker(
            "l1-p0006",
            "GENEE",
            SHA["F"],
            60,
            3,
            junction="A60|B61",
            why="third",
            refold_priority="3",
        ),
    ],
    "snorkel.tsv": [
        {
            "member_id": "l1-m9",
            "design_id": "l1-p0008",
            "gene": "GENEG",
            "sequence_sha256": SHA["H"],
            "native_length": "300",
            "module_length": "106",
            "snorkel_protein_sha256": "e" * 64,
            "components": "linker|PDGFRB TM|linker|cassette",
            "status": "decided",
            "reason": "C-term snorkel",
            "rejected_alternative": "",
            "decided_by": "ranker",
            "implemented_by": "ranker",
        },
    ],  # fmt: skip
    "tagged_index.tsv": [
        {
            "fold_id": fid,
            "candidate_id": "l1-m0444",
            "gene_symbol": "GENEE",
            "rung": rung,
            "tagged": tagged,
            "tagged_sha256": "9" * 64,
            "native_sha256": SHA["F"],
            "cassette_start_1based": "95",
            "cassette_end_1based": "145",
            "pdb_key": f"processed://x/tagged/2026-11-12/{fid}.pdb",
            "settings": "model_1",
            "implemented_by": "refold session",
        }
        for fid, rung, tagged in [
            ("l1-m0444.internal", "internal", "yes"),
            ("l1-m0444.control", "control", "no"),
        ]
    ],  # fmt: skip
    "tagged_index_v2.tsv": [
        {
            "fold_id": fid,
            "kind": kind,
            "rung": "cterm",
            "design_id": "l1-p0001",
            "gene_symbol": "GENEA",
            "tagged_sha256": "8" * 64,
            "native_sha256": SHA["A"],
            "cassette_start_1based": "761",
            "cassette_end_1based": "811",
            "insert_after_native_residue": "760",
            "mean_plddt": "77.0",
            "verdict": verdict,
            "pdb_key": f"processed://x/tagged/2026-11-12/{fid}.pdb",
            "implemented_by": "refold",
        }
        for fid, kind, verdict in [
            ("t.8888", "tagged", "fail"),
            ("l1-m0077.cterm", "superseded", "pass"),
        ]
    ]
    + [
        {
            "fold_id": "n.cccc",
            "kind": "native",
            "rung": "native",
            "design_id": "l1-p0003",
            "gene_symbol": "GENEB",
            "tagged_sha256": SHA["C"],
            "native_sha256": SHA["C"],
            "cassette_start_1based": "",
            "cassette_end_1based": "",
            "insert_after_native_residue": "",
            "mean_plddt": "70.1",
            "verdict": "native_model",
            "pdb_key": "processed://x/tagged/2026-11-12/n.cccc.pdb",
            "implemented_by": "refold",
        },
    ],  # fmt: skip
    "nterm_decisions.tsv": [
        {
            "candidate_id": "l1-m0999",
            "design_id": "l1-p0003",
            "gene_symbol": "GENEB",
            "candidate_set": "library_reference",
            "arm": "igk_swap",
            "insert_after_residue": "24",
            "igk_replaces_residues": "1-22",
            "native_after_residue": "34",
            "cleavage_site": "32",
            "inside_predicted_fold": "0",
            "tagged_cleavage_probability": "0.97",
            "tagged_sha256": "7" * 64,
            "evidence": "SignalP",
            "refold_verdict": "pass",
            "decided_by": "nterm session (delegated by the reviewer 2026-11-12)",
            "implemented_by": "nterm builder",
            "reason": "native SP weak",
            "rejected_alternative": "native site 34",
        },
    ],  # fmt: skip
    "tagged_metrics.tsv": [
        {
            "fold_id": "l1-m0444.internal",
            "insert_after_residue": "94",
            "tagged_aa": "203",
            "mean_plddt": "81.5",
            "tm_native": "0.97",
            "lddt_site": "0.88",
            "sp_state": "",
            "verdict": "pass",
            "verdict_reasons": "",
        },
    ],  # fmt: skip
    "loops.tsv": [
        {
            "member_id": "l1-m9",
            "candidate_id": "l1-p0006",
            "segment_index": "1",
            "start": "80",
            "end": "110",
            "segment_rank": "1",
            "segment_score": "0.7",
            "best_residue": "94",
            "glycan_n": "100",
            "disulfide_cys": "",
            "median_plddt": "80",
        },
    ],
    "contacts.tsv": [
        {
            "candidate_id": "l1-m0006",
            "gene": "GENEE",
            "sequence_sha256": SHA["F"],
            "residue": str(res),
            "aa": "Y",
            "canonical_acc": "PX",
            "canonical_residue": str(res),
            "canonical_sequence_sha256": SHA["F"],
            "in_extracellular": "True",
            "deeptmhmm_v1_state": "O",
            "evidence_class": ec,
            "evidence_types": et,
            "contact_classes": "protein_ligand",
            "ion_site": ion,
            "additive_only": "False",
            "ligands": "LIG",
            "pmids": "123",
            "in_run": "True",
        }
        for res, ec, et, ion in [
            (90, "predicted_literature", "structure", "False"),
            (91, "predicted_literature", "homology", "False"),
            (92, "predicted_literature", "mutagenesis", "True"),
            (93, "uniprot_binding", "", "False"),
        ]
    ],  # fmt: skip
}

PINS = {
    "renumbering": "renum.tsv", "tag_paths": "paths.tsv", "structure_payload": "payload.tsv",
    "cterm": "cterm.tsv", "nterm_sp": "nsp.tsv", "type3": "t3.tsv", "multipass": "mp.tsv",
    "multipass_lane_check": "lane.tsv", "internal_gate": "gate.tsv", "agent_picks": "agent.tsv",
    "proteoform_decisions": "proteoform.tsv", "cterm_decisions": "cterm_decisions.tsv",
    "internal_constructs": "internal_constructs.tsv",
}  # fmt: skip
OBJECT_PINS = {
    "internal_decisions": "decisions.tsv", "internal_proposed": "proposed.tsv",
    "loop_evidence": "loops.tsv", "lit_contacts": "contacts.tsv",
    "nterm_decisions": "nterm_decisions.tsv",
    "snorkel_designs": "snorkel.tsv",
}  # fmt: skip


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("l1design")
    repo = tmp / "design-repo"
    (repo / BASE).mkdir(parents=True)
    for name, rows in GIT_TABLES.items():
        (repo / BASE / name).write_text(_tsv(rows))
    objects = tmp / "s3"
    objects.mkdir()
    for name, rows in S3_TABLES.items():
        (objects / name).write_text(_tsv(rows))
    git = ["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t"]
    subprocess.run([*git, "init", "-q"], check=True)
    subprocess.run([*git, "add", "."], check=True)
    subprocess.run([*git, "commit", "-qm", "fixture"], check=True)
    commit = subprocess.run(
        [*git, "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()
    sources = {
        k: {"pr": 1, "ref": "fixture", "commit": commit, "path": p}
        for k, p in PINS.items()
    }
    sources |= {
        k: {"pr": 2, "ref": "fixture", "object": f"file://{objects / p}"}
        for k, p in OBJECT_PINS.items()
    }
    sources["type3"]["pending_note"] = "pending #9 re-push"
    pins = tmp / "pins.json"
    tagged = [
        {"format": "l1_tag_refold_v1", "object": f"file://{objects / 'tagged_index.tsv'}",
         "metrics": f"file://{objects / 'tagged_metrics.tsv'}", "release": "2026-11-12",
         "decided_by": "Becca, test", "implemented_by": "refold session"},
        {"format": "l1_tag_refold_v1", "object": f"file://{objects / 'tagged_index_v2.tsv'}",
         "metrics": f"file://{objects / 'tagged_metrics.tsv'}", "release": "2026-11-12",
         "decided_by": "Becca, test", "implemented_by": "refold session"},
    ]  # fmt: skip
    pins.write_text(
        json.dumps(
            {
                "analysis_repo": "test/design",
                "base_dir": BASE,
                "sources": sources,
                "tagged_structures": tagged,
            }
        )
    )
    data = tmp / "data"
    run = [sys.executable, str(LOADER)]
    res = subprocess.run(
        [*run, "build", "--pins", str(pins), "--data-dir", str(data), "--analysis-repo", str(repo)],
        capture_output=True, text=True,
    )  # fmt: skip
    assert res.returncode == 0, res.stdout + res.stderr
    sql = tmp / "load.sql"
    subprocess.run(
        [*run, "sql", "--data-dir", str(data), "--out", str(sql)],
        check=True,
        capture_output=True,
    )
    redacted = tmp / "load_redacted.sql"
    subprocess.run(
        [*run, "sql", "--data-dir", str(data), "--out", str(redacted), "--redact-internal"],
        check=True, capture_output=True,
    )  # fmt: skip
    return {"tmp": tmp, "data": data, "sql": sql, "redacted": redacted}


def _rows(data: Path, name: str) -> list[dict]:
    with (data / f"l1_design_{name}.tsv").open() as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def _sites(data: Path) -> dict[str, dict]:
    return {r["site_id"]: r for r in _rows(data, "sites")}


def test_build_maps_every_rung(built):
    sites = _sites(built["data"])
    assert set(sites) == {
        "l1-p0001-cterm-760", "l1-p0002-cterm-held", "l1-p0003-nsp-34", "l1-p0004-type3-r1",
        "l1-p0005-res1-igk_tag", "l1-p0005-res1-tag_alone", "l1-p0006-internal-94",
        "l1-p0006-v5-r2", "GENEE-F120", "l1-p0007-internal-route_to_nterm_after_sp",
        "l1-p0006-agent-r1",
        "l1-p0008-internal-snorkel",
    }  # fmt: skip
    c = sites["l1-p0001-cterm-760"]
    assert (c["member_id"], c["status"], c["cassette_aa"]) == (
        "l1-m0001",
        "built",
        "51",
    )
    t3 = sites["l1-p0004-type3-r1"]
    # The type III source is pinned with a pending note: visible, never a settled pick.
    assert (t3["leader"], t3["insert_after_residue"], t3["status"]) == (
        "igk",
        "1",
        "pending",
    )
    assert t3["status_detail"].startswith("pending #9 re-push; was built")
    igk, alone = sites["l1-p0005-res1-igk_tag"], sites["l1-p0005-res1-tag_alone"]
    assert (igk["is_primary"], igk["status"]) == ("1", "built")
    assert (alone["is_primary"], alone["status"]) == ("0", "alternative")
    assert json.loads(igk["rationale_json"])["lane_check"]["lane_ok"] == "yes"


def test_internal_decision_carries_rationale_and_rejected_alternative(built):
    sites = _sites(built["data"])
    d = sites["l1-p0006-internal-94"]
    assert (d["status"], d["is_primary"], d["site_source"]) == (
        "decided_not_built",
        "1",
        "ranker",
    )
    assert d["rejected_alternative"] == "v5 rank-2 pick"
    why = json.loads(d["rationale_json"])
    assert why["rank_score"] == 0.8 and why["refold_verdict"] == "pending"
    assert why["loop_evidence"]["glycan_n"] == "100"
    assert (d["residue_before"], d["residue_after"]) == (
        "V",
        "S",
    )  # from the ranked table's junction
    route = sites["l1-p0007-internal-route_to_nterm_after_sp"]
    assert (route["status"], route["insert_after_residue"]) == ("no_tag", "")
    # The runner-up loads as an alternative; rank 3 and the decided pick itself do not.
    alt = sites["l1-p0006-v5-r2"]
    assert (alt["status"], alt["is_primary"], alt["residue_before"]) == (
        "alternative",
        "0",
        "G",
    )
    assert "l1-p0006-v5-r1" not in sites and "l1-p0006-v5-r3" not in sites


def test_joins_never_use_member_id_and_drop_stale_rows(built):
    manifest = json.loads((built["data"] / "manifest.json").read_text())
    dropped = manifest["counts"]["dropped_rows"]
    assert dropped["cterm"]["examples"] == [
        "l1-p3001: not a member of the pinned universe"
    ]
    assert "stale" in dropped["internal_decisions"]["examples"][0]
    assert manifest["counts"]["members_without_primary_site"] == []


def test_tagged_refolds_resolve_by_native_sequence_and_link_their_site(built):
    rows = [r for r in _rows(built["data"], "structures") if r["kind"] == "tagged"]
    assert len(rows) == 2, "untagged controls and superseded models are skipped"
    v2 = next(r for r in rows if r["member_id"] == "l1-m0001")
    assert (v2["site_id"], v2["refold_verdict"], v2["mean_plddt"]) == (
        "l1-p0001-cterm-760",
        "fail",
        "77.0",
    )
    t = next(r for r in rows if r["member_id"] == "l1-m0006")
    assert (t["member_id"], t["site_id"], t["refold_verdict"]) == (
        "l1-m0006",
        "l1-p0006-internal-94",
        "pass",
    )
    assert (t["cassette_first_model_residue"], t["cassette_last_model_residue"]) == (
        "95",
        "145",
    )
    assert t["r2_key"] == "library-colabfold-tagged/2026-11-12/l1-m0444.internal.pdb"


def test_nterm_decisions_supersede_the_reviewer_package_picks(built):
    s = _sites(built["data"])["l1-p0003-nsp-34"]
    assert (s["leader"], s["insert_after_residue"], s["status"], s["decision"]) == (
        "igk",
        "34",
        "built",
        "igk_swap",
    )
    assert s["rejected_alternative"] == "native site 34"
    assert json.loads(s["rationale_json"])["refold_verdict"] == "pass"
    assert s["decided_by"].startswith("nterm session")


def test_proteoform_decision_rides_on_the_member(built):
    m = {r["member_id"]: r for r in _rows(built["data"], "members")}
    assert json.loads(m["l1-m0004"]["proteoform_json"])["decision"] == "repair"
    assert m["l1-m0003"]["proteoform_json"] == ""


def test_native_only_refold_fills_a_member_with_no_native_model(built):
    rows = _rows(built["data"], "structures")
    nat = [r for r in rows if r["kind"] == "native" and r["member_id"] == "l1-m0003"]
    assert (
        len(nat) == 1 and nat[0]["source"] == "colabfold" and nat[0]["is_chosen"] == "1"
    )
    # GENEA already has a payload model, so no refold native is added for it.
    assert not any(
        "native-refold" in r["structure_id"]
        for r in rows
        if r["member_id"] == "l1-m0001"
    )


def test_snorkel_pick_sits_after_the_native_c_terminus(built):
    s = _sites(built["data"])["l1-p0008-internal-snorkel"]
    # Built by the C-terminal builder: shown after the native C-terminus (300), not at
    # the construct position (355) that counts the added module.
    assert (s["status"], s["insert_after_residue"], s["cassette_aa"]) == (
        "built",
        "300",
        "106",
    )
    assert s["rejected_alternative"] == "internal loop 2"
    why = json.loads(s["rationale_json"])
    assert why["snorkel_construct"]["cassette_after_construct_residue"] == "355"
    assert why["snorkel_design"]["components"].startswith("linker")
    assert not any(k.startswith("l1-p0008-cterm") for k in _sites(built["data"]))


def test_cterm_decisions_attach_and_holds_show(built):
    sites = _sites(built["data"])
    c = sites["l1-p0001-cterm-760"]
    assert (c["decision"], c["rejected_alternative"]) == (
        "keep the cassette at the C-terminus",
        "stalk site 700",
    )
    assert c["decided_by"].startswith("cterm session")
    held = sites["l1-p0002-cterm-held"]
    assert (held["status"], held["insert_after_residue"], held["decision"]) == (
        "no_tag",
        "",
        "hold (not built)",
    )


def test_agent_picks_only_where_the_member_is_the_canonical(built):
    sites = _sites(built["data"])
    a = sites["l1-p0006-agent-r1"]
    assert (a["site_source"], a["status"], a["is_primary"]) == (
        "agent_proposer",
        "alternative",
        "0",
    )
    # GENEG's member has no canonical sha on record, and only the 'full' arm loads.
    assert not any(k.startswith("l1-p0008-agent") for k in sites)
    manifest = json.loads((built["data"] / "manifest.json").read_text())
    assert manifest["counts"]["agent_picks_without_identical_member"] == 1


def test_contacts_tiers_and_sources(built):
    rows = {(r["residue"], r["source"]): r for r in _rows(built["data"], "contacts")}
    assert rows[("90", "literature_agent")]["confidence_tier"] == "high"
    assert rows[("91", "literature_agent")]["confidence_tier"] == "lower"
    assert rows[("92", "literature_agent")]["confidence_tier"] == "hidden"  # ion site
    assert rows[("93", "uniprot_binding")]["confidence_tier"] == "lower"
    assert {r["member_id"] for r in rows.values()} == {"l1-m0006"}


def test_membrane_classes(built):
    cls = {r["member_id"]: r["membrane_class"] for r in _rows(built["data"], "members")}
    assert cls["l1-m0005"] == "GPCR"  # the multipass table's GPCR flag
    assert cls["l1-m0007"] == "transporter"  # SLC family, multipass
    assert cls["l1-m0003"] == "single-pass type I"
    assert cls["l1-m0001"] == "single-pass type II"
    assert cls["l1-m0004"] == "single-pass type III"


def _apply(sql: Path, db: sqlite3.Connection) -> dict[str, int]:
    db.executescript(sql.read_text())
    tables = ("l1_member_public", "l1_tag_site_design_public", "l1_structure_design_public",
              "l1_contact_site_public", "l1_design_load_public")  # fmt: skip
    return {t: db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tables}


def test_sql_is_insert_only_idempotent_and_load_row_last(built):
    text = built["sql"].read_text()
    bodies = [
        "\n".join(ln for ln in s.splitlines() if not ln.startswith("--")).strip()
        for s in text.split(";\n")
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
    assert first == {"l1_member_public": 8, "l1_tag_site_design_public": 12, "l1_structure_design_public": 5,
                     "l1_contact_site_public": 4, "l1_design_load_public": 1}  # fmt: skip
    assert _apply(built["sql"], db) == first


def test_redacted_sql_drops_the_internal_record(built):
    db = sqlite3.connect(":memory:")
    db.executescript(MIGRATION.read_text())
    _apply(built["redacted"], db)
    L = _loader()
    rows = db.execute(
        "SELECT source_pr, rationale_json, rejected_alternative, reason, source_commit, decided_by, implemented_by "
        "FROM l1_tag_site_design_public"
    ).fetchall()
    assert all(r[:4] == (None, None, None, None) for r in rows)
    assert all(v == L.REDACTED for r in rows for v in r[4:])
    match = re.search(r"l1d-[0-9a-f]{16}", built["sql"].read_text())
    assert match
    lv, raw_inputs = db.execute(
        "SELECT load_version, inputs_json FROM l1_design_load_public"
    ).fetchone()
    assert lv != match.group(0), "redacted and full loads must not share a load_version"
    assert all(
        set(v) <= {"sha256", "n"}
        for v in json.loads(raw_inputs).values()
        if isinstance(v, dict)
    )
    assert db.execute(
        "SELECT insert_after_residue FROM l1_tag_site_design_public WHERE site_id = 'l1-p0001-cterm-760'"
    ).fetchone() == (760,)


NODE_TEST = r"""
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
        async run() { db.prepare(sql).run(...args); return { success: true }; },
      };
    },
  };
};
const ctx = { waitUntil() {}, passThroughOnException() {} };
const [pub, empty, priv] = process.argv.slice(2);
const env = { DB: d1(pub), FEEDBACK_DB: d1(priv), L1_REVIEW_TOKEN: "s3cret" };
const call = async (path, { method = "GET", body, token, envOverride } = {}) => {
  const headers = { "Content-Type": "application/json" };
  if (token) headers["X-L1-Review-Token"] = token;
  const res = await worker.fetch(
    new Request(`https://api.test${path}`, { method, headers, body: body && JSON.stringify(body) }),
    envOverride ?? env, ctx);
  const type = res.headers.get("Content-Type") || "";
  return [res.status, type.includes("json") ? await res.json() : await res.text(), res];
};

let [status, body] = await call("/v1/l1-design/GENEA");
assert.equal(status, 200);
assert.match(body.load.load_version, /^l1d-[0-9a-f]{16}$/);
assert.deepEqual(body.members.map((m) => [m.member_id, m.species, m.membrane_class]),
  [["l1-m0001", "human", "single-pass type II"], ["l1-m0002", "cyno", "single-pass type II"]]);
assert.equal(body.members[0].sites[0].insert_after_residue, 760);
assert.equal(body.members[0].sites[0].status, "built");
assert.equal(body.members[0].proteoform, null);
assert.equal(body.members[0].structures[0].display_last_model_residue, 760);
const lv = body.load.load_version;

[status, body] = await call("/v1/l1-design/genee");
const e = body.members[0];
assert.deepEqual(e.sites.filter((s) => s.is_primary).map((s) => s.status).sort(), ["built", "decided_not_built"]);
const dec = e.sites.find((s) => s.site_id === "l1p".replace("l1p", "l1-p0006-internal-94"));
assert.equal(dec.rejected_alternative, "v5 rank-2 pick");
assert.equal(dec.rationale.loop_evidence.glycan_n, "100");
assert.ok(e.sites.some((s) => s.site_source === "agent_proposer" && s.status === "alternative"));
assert.deepEqual(e.contacts.map((c) => [c.residue, c.source, c.confidence_tier]),
  [[90, "literature_agent", "high"], [91, "literature_agent", "lower"], [92, "literature_agent", "hidden"],
   [93, "uniprot_binding", "lower"]]);

[status, body] = await call("/v1/l1-design");
assert.equal(status, 200);
assert.equal(body.members.length, 8);
assert.deepEqual(body.members.find((m) => m.member_id === "l1-m0006").pick_status, ["built", "decided_not_built"]);
assert.deepEqual(body.members.find((m) => m.member_id === "l1-m0008").pick_status, ["built"]);

[status] = await call(`/v1/l1-design/GENEA/${lv}`);
assert.equal(status, 200);
[status] = await call(`/v1/l1-design/GENEA/l1d-0000000000000000`);
assert.equal(status, 404);
[status] = await call(`/v1/l1-design/GENEA/not-a-load`);
assert.equal(status, 400);
[status, body] = await call("/v1/l1-design/TFRC", { envOverride: { DB: d1(empty) } });
assert.equal(status, 200);
assert.equal(body.load, null);

// --- reviews ---
const verdict = { kind: "verdict", reviewer: "Becca", member_id: "l1-m0006", design_id: "l1-p0006",
  sequence_sha256: "f".repeat(64), gene_symbol: "GENEE", verdict: "no", reason: "glycan at 100",
  load_version: lv };
[status] = await call("/v1/l1-review", { method: "POST", body: verdict });
assert.equal(status, 401);
[status] = await call("/v1/l1-review", { method: "POST", body: verdict, token: "wrong" });
assert.equal(status, 401);
[status] = await call("/v1/l1-review", { method: "POST", body: verdict, token: "s3cret",
  envOverride: { ...env, L1_REVIEW_TOKEN: undefined } });
assert.equal(status, 503);
[status] = await call("/v1/l1-review", { method: "POST", body: { ...verdict, reason: "" }, token: "s3cret" });
assert.equal(status, 400, "a 'no' needs a reason");
[status, body] = await call("/v1/l1-review", { method: "POST", body: verdict, token: "s3cret" });
assert.equal(status, 201);
const alt = { kind: "alt_tag", reviewer: "Becca", member_id: "l1-m0006", design_id: "l1-p0006",
  gene_symbol: "GENEE", insert_after_residue: 60, placement: "internal", reason: "try loop 2",
  load_version: lv };
[status] = await call("/v1/l1-review", { method: "POST", body: { ...alt, placement: "sideways" }, token: "s3cret" });
assert.equal(status, 400);
[status] = await call("/v1/l1-review", { method: "POST", body: { ...alt, insert_after_residue: null }, token: "s3cret" });
assert.equal(status, 400, "an internal placement needs a residue");
[status] = await call("/v1/l1-review", { method: "POST", body: alt, token: "s3cret" });
assert.equal(status, 201);
[status] = await call("/v1/l1-review");
assert.equal(status, 401);
[status, body] = await call("/v1/l1-review", { token: "s3cret" });
assert.equal(body.reviews.length, 1);
assert.equal(body.alt_tags[0].insert_after_residue, 60);
let res;
[status, body, res] = await call("/v1/l1-review/export.tsv", { token: "s3cret" });
assert.equal(status, 200);
assert.equal(res.headers.get("Cache-Control"), "no-store");
const lines = body.trim().split("\n");
assert.equal(lines.length, 3);
assert.match(lines[0], /^kind\tid\tcreated_at\treviewer/);
assert.ok(lines.some((l) => l.startsWith("alt_tag\t") && l.includes("\tinternal\t")));
console.log("ok");
"""


def test_worker_routes_against_sqlite(built):
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
    pub = tmp / "public.sqlite"
    db = sqlite3.connect(pub)
    db.executescript(MIGRATION.read_text())
    db.executescript(built["sql"].read_text())
    db.commit()
    db.close()
    priv = tmp / "private.sqlite"
    db = sqlite3.connect(priv)
    db.executescript(REVIEW_MIGRATION.read_text())
    db.commit()
    db.close()
    empty = tmp / "empty.sqlite"
    sqlite3.connect(empty).close()

    source = WORKER.read_text().replace(
        'import { deepDiveTier, isLowLiteratureSurface } from "../../../../viewer/lib/catalog-presets";',
        "const deepDiveTier = () => ({tier: 'no', facet: null}); const isLowLiteratureSurface = () => false;",
    )
    for js in WORKER.parent.glob("*.js"):
        if js.name != "index.js":
            shutil.copy2(js, tmp / js.name)
    (tmp / "worker.mjs").write_text(source)
    (tmp / "test.mjs").write_text(NODE_TEST)
    res = subprocess.run(
        [node, "test.mjs", str(pub), str(empty), str(priv)],
        cwd=tmp,
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, res.stdout + res.stderr
    assert "ok" in res.stdout


def test_internal_decision_is_built_only_when_built_at_that_residue():
    L = _loader()
    member = {"member_id": "l1-m0001", "design_id": "l1-p0001", "gene_symbol": "G", "species": "human",
              "candidate_set": "library_reference", "rung": "internal", "ordered_length_aa": 200,
              "sequence_sha256": "a" * 64}  # fmt: skip
    R = L.Resolver({"l1-m0001": member})
    dec = {"design_id": "l1-p0001", "gene": "G", "sequence_sha256": "a" * 64, "decision": "internal_loop",
           "insert_after_residue": "94.0", "pick_rank": "1", "rank_score": "0.8", "absolute_score": "0.7",
           "best_region_pct_of_published_regions": "0.5", "this_region_length": "19", "snorkel_candidate": "False",
           "confidence": "medium", "reason": "r", "rejected_alternative": "x", "decided_by": "ranker",
           "implemented_by": "ranker", "refold_verdict": "pending"}  # fmt: skip
    info = {"pr": 1, "pr_state": "open", "commit": "c" * 40, "path": "decisions.tsv"}
    built = {"l1-p0001": {"design_id": "l1-p0001", "cassette_after_residue": "94", "junction": "V94|S95",
                          "native_aa": "200", "protein_aa": "251", "protein_sha256": "4" * 64,
                          "refold_verdict": "pass", "built_by": "integration"}}  # fmt: skip
    (site,) = L._internal([dec], [], info, info, R, {}, loop_built=built)
    assert (site["status"], site["residue_before"], site["cassette_aa"]) == (
        "built",
        "V",
        51,
    )
    assert site["tagged_protein_sha256"] == "4" * 64
    (site,) = L._internal([dec], [], info, info, R, {}, loop_built={})
    assert site["status"] == "decided_not_built"


def test_final_refold_manifest_overrides_the_index_verdict():
    L = _loader()
    member = {"member_id": "l1-m0001", "design_id": "l1-p0001", "gene_symbol": "G", "species": "human",
              "candidate_set": "library_reference", "rung": "C-terminal", "ordered_length_aa": 200,
              "sequence_sha256": "a" * 64}  # fmt: skip
    R = L.Resolver({"l1-m0001": member})
    head = ("fold_id\tkind\trung\tdesign_id\tgene_symbol\ttagged_sha256\tnative_sha256\tcassette_start_1based\t"
            "cassette_end_1based\tinsert_after_native_residue\tmean_plddt\tverdict\tpdb_key\n")  # fmt: skip
    row = f"t.1\ttagged\tcterm\tl1-p0001\tG\t{'9' * 64}\t{'a' * 64}\t201\t251\t200\t80\tpass\tprocessed://x/t.1.pdb\n"
    manifest = ("tagged_sha256\tverdict\tverdict_reasons\tspytag003_rsa\talfa_rsa\n"
                f"{'9' * 64}\tfail\tepitope packed\t0.12\t0.40\n").encode()  # fmt: skip
    spec = {"release": "2026-11-12", "decided_by": "d", "implemented_by": "i"}
    (t,) = L._tagged_refold_v1(spec, (head + row).encode(), b"", R, {}, manifest)
    assert t["refold_verdict"] == "fail"
    assert "SpyTag003 RSA 0.12" in t["note"] and "epitope packed" in t["note"]
    (t,) = L._tagged_refold_v1(spec, (head + row).encode(), b"", R, {})
    assert t["refold_verdict"] == "pass"
