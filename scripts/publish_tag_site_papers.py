"""Publish the gene-to-paper graph + triage verdicts to public D1.

The discovery and triage caches exist only on one laptop. They are 350 MB of
derived data that cost real money and a day of wall-clock to build, they are in
no backup, and they are what makes a rescue analysis free — `build_pool` is
deterministic over them, so the exact clip pool a run saw can be rebuilt without
a single model call. Losing them means re-paying for every answer.

What goes PUBLIC is only what may: the gene-to-paper link, each paper's
accession and bibliography, and the triage verdict with its one-line reason.

What does NOT go public is the 180 MB of `abstract`, `sections` and
`target_mention_excerpts` in the same files. That is publisher full text, and
shipping it in bulk is redistribution — the repo already treats it that way
(`blob_cache/` is gitignored as "copyrighted PDFs; never commit", and the
pipeline ships only short substring-anchored snippets under fair use). The
bodies stay local, or go to a PRIVATE store; they are re-fetchable from the
caches that produced them, and the accession here is what makes that possible.

    uv run python scripts/publish_tag_site_papers.py            # dry run
    uv run python scripts/publish_tag_site_papers.py --execute
"""

from __future__ import annotations

import argparse
import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from accessible_surfaceome.env import load_env

load_env()

from accessible_surfaceome.cloud.d1_client import D1Client  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DISCOVERY = ROOT / "data/external/tag_site_discovery"
TRIAGE = ROOT / "data/external/tag_site_triage"
log = logging.getLogger("publish_papers")

DDL = """
CREATE TABLE IF NOT EXISTS tag_site_paper_public (
    gene_symbol      TEXT NOT NULL,
    source_id        TEXT NOT NULL,
    pmid             TEXT,
    pmc_id           TEXT,
    doi              TEXT,
    title            TEXT,
    journal          TEXT,
    year             TEXT,
    is_preprint      INTEGER,
    is_review        INTEGER,
    is_retracted     INTEGER,
    triage_decision  TEXT,
    triage_reason    TEXT,
    PRIMARY KEY (gene_symbol, source_id)
);
"""
INDEXES = (
    "CREATE INDEX IF NOT EXISTS idx_tspp_gene ON tag_site_paper_public (gene_symbol);",
    "CREATE INDEX IF NOT EXISTS idx_tspp_pmid ON tag_site_paper_public (pmid);",
    "CREATE INDEX IF NOT EXISTS idx_tspp_decision ON tag_site_paper_public (triage_decision);",
)
_COLS = (
    "gene_symbol",
    "source_id",
    "pmid",
    "pmc_id",
    "doi",
    "title",
    "journal",
    "year",
    "is_preprint",
    "is_review",
    "is_retracted",
    "triage_decision",
    "triage_reason",
)
#: D1 caps bound parameters at 100 per statement.
_ROWS_PER_CALL = 100 // len(_COLS)


def _flag(v: object) -> int | None:
    return None if v is None else (1 if v else 0)


def rows_for_gene(gene: str) -> list[dict]:
    try:
        papers = json.loads((DISCOVERY / f"{gene}.json").read_text())
    except Exception:  # noqa: BLE001
        return []
    try:
        verdicts = json.loads((TRIAGE / f"{gene}.json").read_text())
    except Exception:  # noqa: BLE001
        verdicts = {}
    out = []
    for source_id, p in papers.items():
        v = verdicts.get(source_id) or {}
        out.append(
            {
                "gene_symbol": gene,
                "source_id": source_id,
                "pmid": str(p.get("pmid")) if p.get("pmid") else None,
                "pmc_id": p.get("pmc_id"),
                "doi": p.get("doi"),
                "title": p.get("title"),
                "journal": p.get("journal"),
                "year": str(p.get("year")) if p.get("year") else None,
                "is_preprint": _flag(p.get("is_preprint")),
                "is_review": _flag(p.get("is_review")),
                "is_retracted": _flag(p.get("is_retracted")),
                "triage_decision": v.get("decision"),
                "triage_reason": v.get("reason"),
            }
        )
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--parallel", type=int, default=8)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    genes = sorted(p.stem for p in DISCOVERY.glob("*.json"))
    all_rows: list[dict] = []
    for g in genes:
        all_rows.extend(rows_for_gene(g))
    triaged = sum(1 for r in all_rows if r["triage_decision"])
    log.info(
        "genes %d | (gene,paper) rows %d | with a triage verdict %d",
        len(genes),
        len(all_rows),
        triaged,
    )
    log.info(
        "payload ~%.0f MB of bibliography + verdicts (NO abstracts or body text)",
        sum(len(json.dumps(r)) for r in all_rows) / 1e6,
    )
    if not args.execute:
        log.info("dry run — nothing written (pass --execute)")
        return 0

    with D1Client() as _probe:  # noqa: F841 - fail fast on bad env before the sweep
        pass
    client = D1Client.public()
    try:
        client.query(DDL, [])
        for idx in INDEXES:
            client.query(idx, [])

        batches = [
            all_rows[i : i + _ROWS_PER_CALL]
            for i in range(0, len(all_rows), _ROWS_PER_CALL)
        ]
        cols = ", ".join(_COLS)
        log.info("writing %d batches of <=%d rows", len(batches), _ROWS_PER_CALL)

        def write(batch: list[dict]) -> int:
            marks = ", ".join(["(" + ", ".join(["?"] * len(_COLS)) + ")"] * len(batch))
            params = [r[c] for r in batch for c in _COLS]
            # Idempotent on the PK, which is what makes the retry in D1Client
            # safe to run from a pool.
            client.query(
                f"INSERT OR REPLACE INTO tag_site_paper_public ({cols}) VALUES {marks};",
                params,
            )
            return len(batch)

        done = 0
        with ThreadPoolExecutor(max_workers=args.parallel) as pool:
            futs = [pool.submit(write, b) for b in batches]
            for i, f in enumerate(as_completed(futs), 1):
                try:
                    done += f.result()
                except Exception as exc:  # noqa: BLE001
                    log.warning("batch failed: %s", str(exc)[:120])
                if i % 200 == 0:
                    log.info("  %d/%d batches, %d rows", i, len(batches), done)
        log.info("wrote %d rows -> tag_site_paper_public", done)
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
