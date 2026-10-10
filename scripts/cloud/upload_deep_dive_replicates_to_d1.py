"""Load the deep-dive reproducibility replicates into public D1 ``deep_dive_replicate``.

Source is the frozen bundle ``data/processed/deep_dive_concordance_v1/`` — the
same bytes Supplementary Figure 15 is built from and the Zenodo data record
deposits — so the API, the figure and the deposit cannot disagree. Three record
sets per gene (50 genes): the published snapshot the study compared against, the
full re-run, and the fixed-evidence replay.

These rows are replicates, NOT published records: this script never touches
``surface_annotation``, so ``/v1/genes/{SYMBOL}`` is unaffected. The Worker
serves the table API-only under ``/v1/replicates`` and
``/v1/genes/{SYMBOL}/replicates``.

Every record is validated against ``SurfaceomeRecord`` before any write (the
serve-time ``deep_dive_tier`` / ``deep_dive_facet`` and the split-out
``evidence`` are set aside for validation only; the stored JSON is the record
exactly as frozen). Idempotent ``INSERT OR REPLACE`` on
``(study_id, replicate_kind, gene_symbol)``; creates the table if missing.

Run from the repo root::

    uv run python scripts/cloud/upload_deep_dive_replicates_to_d1.py            # dry-run
    uv run python scripts/cloud/upload_deep_dive_replicates_to_d1.py --execute  # write
"""

from __future__ import annotations

import argparse
import gzip
import json
import re
from typing import Any

from accessible_surfaceome.cloud.d1_client import D1Client, D1Config
from accessible_surfaceome.env import load_env
from accessible_surfaceome.paths import REPO_ROOT
from accessible_surfaceome.tools._shared.models import SurfaceomeRecord

BUNDLE = REPO_ROOT / "data/processed/deep_dive_concordance_v1"
SCHEMA = REPO_ROOT / "cloudflare/d1_public_schema.sql"
STUDY_ID = "deep_dive_concordance_v1"
PUBLISHED_RUN = "cu_v3_sonnet_2026_06"
# bundle file → (replicate_kind, run_id that produced the record)
KINDS = {
    "published.jsonl.gz": ("published_snapshot", PUBLISHED_RUN),
    "full_rerun.jsonl.gz": ("full_rerun", STUDY_ID),
    "fixed_evidence_replay.jsonl.gz": ("fixed_evidence_replay", f"{PUBLISHED_RUN}+replay"),
}
# Serve-time additions on the published snapshot; not SurfaceomeRecord fields.
_SERVE_TIME_KEYS = ("deep_dive_tier", "deep_dive_facet", "evidence")
_COLUMNS = (
    "study_id", "replicate_kind", "gene_symbol", "hgnc_id", "uniprot_acc", "sample_batch",
    "run_id", "compared_against_run_id", "schema_version", "prompt_corpus_version",
    "record_generated_at", "annotation_json",
)


def _ddl() -> list[str]:
    """The deep_dive_replicate CREATE TABLE / INDEX statements from the schema file."""
    src = SCHEMA.read_text()
    stmts = re.findall(
        r"CREATE (?:TABLE|INDEX) IF NOT EXISTS (?:deep_dive_replicate|idx_deep_dive_replicate_\w+)\b.*?;",
        src, re.DOTALL,
    )
    assert len(stmts) == 2, f"expected 2 deep_dive_replicate DDL statements, found {len(stmts)}"
    return [re.sub(r"--[^\n]*", "", s) for s in stmts]


def _validate(record: dict[str, Any]) -> None:
    core = {k: v for k, v in record.items() if k not in _SERVE_TIME_KEYS}
    SurfaceomeRecord.model_validate(core)


def build_rows() -> list[dict[str, Any]]:
    rows = []
    for fname, (kind, run_id) in KINDS.items():
        with gzip.open(BUNDLE / fname, "rt") as fh:
            entries = [json.loads(line) for line in fh]
        for e in entries:
            rec = e["record"]
            _validate(rec)
            gene = rec["gene"]
            rows.append({
                "study_id": STUDY_ID, "replicate_kind": kind,
                "gene_symbol": e["hgnc_symbol"], "hgnc_id": gene.get("hgnc_id"),
                "uniprot_acc": gene.get("uniprot_acc"), "sample_batch": e["sample_batch"],
                "run_id": run_id, "compared_against_run_id": PUBLISHED_RUN,
                "schema_version": rec.get("schema_version"),
                "prompt_corpus_version": rec.get("prompt_corpus_version"),
                "record_generated_at": rec.get("record_generated_at"),
                "annotation_json": json.dumps(rec, ensure_ascii=False, separators=(",", ":")),
            })
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--execute", action="store_true", help="write to public D1 (default: dry-run)")
    args = ap.parse_args()

    rows = build_rows()
    by_kind: dict[str, int] = {}
    for r in rows:
        by_kind[r["replicate_kind"]] = by_kind.get(r["replicate_kind"], 0) + 1
    biggest = max(len(r["annotation_json"]) for r in rows)
    print(f"validated {len(rows)} records {by_kind}; largest annotation_json {biggest / 1024:.0f} KB")
    if not args.execute:
        print("dry-run — pass --execute to create the table and write the rows")
        return 0

    load_env()
    placeholders = ", ".join("?" for _ in _COLUMNS)
    sql = (f"INSERT OR REPLACE INTO deep_dive_replicate ({', '.join(_COLUMNS)}) "
           f"VALUES ({placeholders});")
    with D1Client(config=D1Config.from_env_public()) as d1:
        for stmt in _ddl():
            d1.query(stmt, [])
        for i, r in enumerate(rows, 1):
            d1.query(sql, [r[c] for c in _COLUMNS])
            if i % 25 == 0:
                print(f"  wrote {i}/{len(rows)}")
        n = d1.query(
            "SELECT replicate_kind, COUNT(*) AS n FROM deep_dive_replicate "
            "WHERE study_id = ? GROUP BY replicate_kind;", [STUDY_ID])
    print(f"public D1 now holds: {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
