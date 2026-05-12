"""Upload the genome-wide triageable gene catalog to the `surfaceome_public` D1 mirror.

The triageable set is every protein-coding human gene the triage
agent could be asked about — 19,325 rows from
``data/external/ncbi_gene_info/Homo_sapiens.protein_coding.with_hgnc.triageable.tsv``.
For each, we LEFT JOIN the candidate-universe merge artifact
(``data/processed/candidate_universe/candidate_universe.tsv``) on
gene symbol to pick up the 7 per-source surface flags. Genes that
don't appear in candidate_universe get all-zero flags — those are
protein-coding genes for which no DB voted "surface".

We then compute ``n_sources_surface`` as the count over the **5
gating DBs only** (uniprot, go, surfy, cspa, hpa) — same definition
the merge module uses for the M1 universe gate
(``src/accessible_surfaceome/merge/__init__.py``). DeepTMHMM and
COMPARTMENTS are still loaded into the table (preserves the full
data), but their flags don't count toward the public-facing
``n_sources``. The Worker's ``/v1/catalog`` endpoint mirrors that
choice — it returns only the 5 gating columns to the viewer.

Resulting public table:
    candidate_universe_public(universe_version, gene_symbol, uniprot_acc)
      → 19,325 rows per release; the Worker's catalog endpoint joins
        these with triage_run_public + surface_annotation.

Idempotent on (universe_version, gene_symbol, uniprot_acc): existing
rows are skipped via ``INSERT OR IGNORE``. To re-load with corrected
data, pass a fresh ``--version`` (the Worker always picks the latest
``candidate_universe_release`` row).

Usage::

    uv run python scripts/upload_candidate_universe_to_d1.py \\
        --version "cu_$(date -u +%Y_%m_%d)"

Requires the standard Cloudflare env vars (CLOUDFLARE_ACCOUNT_ID,
CLOUDFLARE_API_TOKEN) plus ``CLOUDFLARE_D1_SURFACEOME_PUBLIC_ID``
pointing at the public mirror DB. See ``.env.example`` for the full
set and ``cloudflare/workers/surfaceome_api/wrangler.toml.example``
for where the Worker reads the same UUID from.
"""

from __future__ import annotations

import argparse
import csv
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from accessible_surfaceome.env import load_env

logger = logging.getLogger(__name__)

# Cloudflare D1 caps SQL placeholders per statement at ~100. Each row has
# 11 cols, so 8 rows per batch (88 placeholders) is the safe ceiling.
BATCH_SIZE = 8

API_ROOT = "https://api.cloudflare.com/client/v4"

COLS = [
    "universe_version",
    "gene_symbol",
    "uniprot_acc",
    "n_sources_surface",
    "uniprot_surface_flag",
    "go_surface_flag",
    "surfy_surface_flag",
    "cspa_surface_flag",
    "hpa_surface_flag",
    "deeptmhmm_surface_flag",
    "compartments_surface_flag",
]


@dataclass(frozen=True)
class D1:
    account_id: str
    database_id: str
    api_token: str

    @property
    def url(self) -> str:
        return f"{API_ROOT}/accounts/{self.account_id}/d1/database/{self.database_id}/query"


def _from_env() -> D1:
    missing: list[str] = []
    acct = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
    token = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
    db = os.environ.get("CLOUDFLARE_D1_SURFACEOME_PUBLIC_ID", "").strip()
    if not acct:
        missing.append("CLOUDFLARE_ACCOUNT_ID")
    if not token:
        missing.append("CLOUDFLARE_API_TOKEN")
    if not db:
        missing.append("CLOUDFLARE_D1_SURFACEOME_PUBLIC_ID")
    if missing:
        raise SystemExit(
            "Missing env vars: " + ", ".join(missing)
            + ". Add them to your .env; see .env.example for the full list."
        )
    return D1(account_id=acct, database_id=db, api_token=token)


def _query(d1: D1, sql: str, params: list[Any] | None = None, *, client: httpx.Client) -> Any:
    body: dict[str, Any] = {"sql": sql}
    if params is not None:
        body["params"] = list(params)
    resp = client.post(
        d1.url,
        json=body,
        headers={"Authorization": f"Bearer {d1.api_token}"},
        timeout=60,
    )
    data = resp.json()
    if not data.get("success"):
        raise RuntimeError(f"D1 error: {data}")
    return data.get("result")


def _flag(row: dict[str, Any] | None, name: str) -> int:
    """Tolerant 0/1 coercion. Empty / NA / nan / missing-key / None row → 0."""
    if row is None:
        return 0
    v = str(row.get(name) or "").strip()
    if not v or v in {"NA", "nan", "None"}:
        return 0
    try:
        return 1 if int(float(v)) else 0
    except ValueError:
        return 0


def _int(row: dict[str, Any], name: str) -> int:
    v = str(row.get(name) or "").strip()
    if not v:
        return 0
    try:
        return int(float(v))
    except ValueError:
        return 0


def _load_candidate_universe_index(tsv: Path) -> dict[str, dict[str, Any]]:
    """Index candidate_universe.tsv by gene_symbol_resolved. When a
    gene has multiple UniProt rows (paralogs / isoforms with the same
    HGNC symbol — happens for ~14/5,666 genes), keep the row with the
    highest n_sources_surface so the canonical UniProt + the strongest
    surface signal wins."""
    by_sym: dict[str, dict[str, Any]] = {}
    with tsv.open() as f:
        reader = csv.DictReader(f, delimiter="\t")
        for r in reader:
            sym = (r.get("gene_symbol_resolved") or r.get("gene_symbol") or "").strip()
            if not sym:
                continue
            n_sources = _int(r, "n_sources_surface")
            existing = by_sym.get(sym)
            if existing is None or n_sources > _int(existing, "n_sources_surface"):
                by_sym[sym] = r
    return by_sym


def _build_rows(
    triageable_tsv: Path,
    candidate_universe_tsv: Path,
    version: str,
) -> list[list[Any]]:
    """One row per triageable gene. Flags come from candidate_universe
    when the gene is in it; otherwise all-zero. n_sources_surface is
    the count over the 5 gating DBs only (uniprot, go, surfy, cspa,
    hpa) — DeepTMHMM and COMPARTMENTS are still stored but don't
    contribute to the public-facing count."""
    cu_by_sym = _load_candidate_universe_index(candidate_universe_tsv)
    logger.info(
        "indexed %d genes from %s (one row each, max-n_sources wins)",
        len(cu_by_sym),
        candidate_universe_tsv,
    )

    out: list[list[Any]] = []
    skipped = 0
    seen_syms: set[str] = set()
    with triageable_tsv.open() as f:
        reader = csv.DictReader(f, delimiter="\t")
        for r in reader:
            sym = (r.get("gene_symbol") or "").strip()
            if not sym or sym in seen_syms:
                skipped += 1
                continue
            seen_syms.add(sym)
            cu = cu_by_sym.get(sym)
            uni = ((cu or {}).get("uniprot_accession") or "").strip()
            # 7 flags. Genes absent from candidate_universe default to all-zero.
            f_uniprot     = _flag(cu, "uniprot_surface_flag")    if cu else 0
            f_go          = _flag(cu, "go_surface_flag")          if cu else 0
            f_surfy       = _flag(cu, "surfy_surface_flag")       if cu else 0
            f_cspa        = _flag(cu, "cspa_surface_flag")        if cu else 0
            f_hpa         = _flag(cu, "hpa_surface_flag")         if cu else 0
            f_deeptmhmm   = _flag(cu, "deeptmhmm_surface_flag")   if cu else 0
            f_compartmnts = _flag(cu, "compartments_surface_flag") if cu else 0
            # n_sources counts the 5 gating DBs only — matches the M1
            # universe gate in merge.__init__.gating_corroborator.
            n_sources = f_uniprot + f_go + f_surfy + f_cspa + f_hpa
            out.append([
                version, sym, uni, n_sources,
                f_uniprot, f_go, f_surfy, f_cspa, f_hpa,
                f_deeptmhmm, f_compartmnts,
            ])
    if skipped:
        logger.warning("skipped %d duplicate / empty-symbol rows", skipped)
    return out


def _intern_release(
    d1: D1, *, version: str, n_rows: int, source_path: str, dry_run: bool, client: httpx.Client,
) -> None:
    if dry_run:
        logger.info("[DRY] candidate_universe_release(version=%s, n_rows=%d)", version, n_rows)
        return
    _query(
        d1,
        """
        INSERT INTO candidate_universe_release (universe_version, n_rows, source_path, notes)
        VALUES (?, ?, ?, NULL)
        ON CONFLICT (universe_version) DO UPDATE SET
            n_rows = excluded.n_rows,
            source_path = excluded.source_path
        """,
        [version, n_rows, source_path],
        client=client,
    )


def _upload_rows(d1: D1, rows: list[list[Any]], *, dry_run: bool, client: httpx.Client) -> None:
    if not rows:
        return
    placeholders_one = "(" + ", ".join(["?"] * len(COLS)) + ")"
    cols_sql = ", ".join(COLS)
    total = len(rows)
    for start in range(0, total, BATCH_SIZE):
        chunk = rows[start : start + BATCH_SIZE]
        sql = (
            f"INSERT OR IGNORE INTO candidate_universe_public ({cols_sql}) "
            f"VALUES {', '.join([placeholders_one] * len(chunk))}"
        )
        params = [v for row in chunk for v in row]
        if dry_run:
            logger.info("[DRY] rows %d..%d (n=%d, %d params)",
                        start, start + len(chunk) - 1, len(chunk), len(params))
            continue
        _query(d1, sql, params, client=client)
        logger.info("rows %d..%d (n=%d) done", start, start + len(chunk) - 1, len(chunk))


def main() -> int:
    load_env()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--triageable-tsv",
        type=Path,
        default=Path(
            "data/external/ncbi_gene_info/"
            "Homo_sapiens.protein_coding.with_hgnc.triageable.tsv"
        ),
        help="Path to the protein-coding triageable TSV "
             "(default: data/external/ncbi_gene_info/...triageable.tsv)",
    )
    ap.add_argument(
        "--candidate-universe-tsv",
        type=Path,
        default=Path("data/processed/candidate_universe/candidate_universe.tsv"),
        help="Path to the candidate-universe TSV with the 7 *_surface_flag columns "
             "(default: data/processed/candidate_universe/candidate_universe.tsv)",
    )
    ap.add_argument(
        "--version",
        required=True,
        help="universe_version stamp, e.g. cu_2026_05_12",
    )
    ap.add_argument("--dry-run", action="store_true", help="Print rows but don't write")
    args = ap.parse_args()

    if not args.triageable_tsv.exists():
        raise SystemExit(f"Triageable TSV not found: {args.triageable_tsv}")
    if not args.candidate_universe_tsv.exists():
        raise SystemExit(f"Candidate universe TSV not found: {args.candidate_universe_tsv}")

    d1 = _from_env()
    logger.info("target DB: %s", d1.database_id)
    rows = _build_rows(args.triageable_tsv, args.candidate_universe_tsv, args.version)
    n_with_signal = sum(1 for r in rows if r[3] > 0)
    logger.info(
        "parsed %d triageable rows (%d with ≥1 gating-DB surface vote, version=%s)",
        len(rows), n_with_signal, args.version,
    )

    with httpx.Client(timeout=60) as client:
        _intern_release(
            d1,
            version=args.version,
            n_rows=len(rows),
            source_path=str(args.triageable_tsv),
            dry_run=args.dry_run,
            client=client,
        )
        _upload_rows(d1, rows, dry_run=args.dry_run, client=client)

    logger.info("done: %d rows → candidate_universe_public (version=%s)", len(rows), args.version)
    return 0


if __name__ == "__main__":
    sys.exit(main())
