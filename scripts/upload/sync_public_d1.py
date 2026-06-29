"""Sync the public-safe subset of `surfaceome_agents` D1 → `surfaceome_public`.

One-way push. Reads from the private D1, applies a column whitelist
to strip operational data (token counts, costs, full prompt text),
and writes to the public mirror. Append-only on the public side:
`INSERT OR IGNORE` keeps prior snapshots queryable.

Tables synced:
  * compara_release       — full row (Ensembl Compara is inherently public)
  * compara_ortholog      — full row
  * benchmark_version     — full row (curated truth labels)
  * gene_identifier       → gene_identifier_public (full row; stable-ID cache)
  * triage_run → triage_run_public
        - DROP: raw_text (the full model response — only the parsed
                fields cross over)
        - KEEP: verdict, reason, confidence, key_uncertainty,
                verdict_reasoning, correct, latency, n_web_searches,
                error, plus cost_usd + token counts (cost data is now
                public so external readers can reproduce
                cost-vs-accuracy figures without private credentials)
        - JOIN: prompt_version.prompt_filename (added; prompt_version.text
                stays private)
  * surface_annotation    — NOT synced here. Deep-dive records are
                            written **direct to public D1** by the agent
                            (``cloud.surface_annotation.publish_record``),
                            so the public table is authoritative. This
                            sync used to INSERT-OR-REPLACE from local
                            ``data/annotations/*.json``, which would
                            clobber the direct-to-public writes with stale
                            on-disk copies — removed deliberately. There
                            is no on-disk fallback for deep dives anymore.

Usage::

    # Full sync (every table)
    uv run python scripts/upload/sync_public_d1.py

    # Only the triage_run table (incremental — only rows newer than last sync)
    uv run python scripts/upload/sync_public_d1.py --only triage_run --since 2026-05-01

    # Dry-run: print what would be written but don't write
    uv run python scripts/upload/sync_public_d1.py --dry-run

Requires the standard Cloudflare env vars (CLOUDFLARE_ACCOUNT_ID,
CLOUDFLARE_API_TOKEN) plus CLOUDFLARE_D1_SURFACEOME_AGENTS_ID
(source) and CLOUDFLARE_D1_SURFACEOME_PUBLIC_ID (destination). The
public mirror's UUID lives only in your `.env`; the Worker reads it
from a local `wrangler.toml` generated from
`cloudflare/workers/surfaceome_api/wrangler.toml.example`.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from dataclasses import dataclass
from typing import Any

import httpx

from accessible_surfaceome.env import load_env

logger = logging.getLogger(__name__)

# Batch size: Cloudflare D1 caps SQL parameters per statement around ~100,
# so chunk multi-row INSERTs accordingly. compara_ortholog has 11 cols → 8 rows;
# triage_run_public has 25 cols → 3 rows; benchmark has 8 cols → 12 rows.
BATCH_BY_TABLE: dict[str, int] = {
    "compara_release":         18,   # 5 cols → 90 params
    "compara_ortholog":        8,    # 11 cols → 88 params
    "benchmark_version":       9,    # 9 cols → 81 params (D1 rejected 12×9=108)
    "triage_run_public":       3,    # 27 cols → 81 params (+hgnc_id, ensembl_gene); ≤100 limit
    "gene_identifier_public":  7,    # 12 cols → 84 params
}

API_ROOT = "https://api.cloudflare.com/client/v4"


@dataclass(frozen=True)
class D1:
    account_id: str
    database_id: str
    api_token: str

    @property
    def url(self) -> str:
        return f"{API_ROOT}/accounts/{self.account_id}/d1/database/{self.database_id}/query"


def _from_env(db_uuid_env: str) -> D1:
    missing: list[str] = []
    acct = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
    token = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
    db = os.environ.get(db_uuid_env, "").strip()
    if not acct:
        missing.append("CLOUDFLARE_ACCOUNT_ID")
    if not token:
        missing.append("CLOUDFLARE_API_TOKEN")
    if not db:
        missing.append(db_uuid_env)
    if missing:
        raise SystemExit(
            "Missing env vars: " + ", ".join(missing)
            + ". Add them to your .env; see .env.example for the full list."
        )
    return D1(account_id=acct, database_id=db, api_token=token)


def _query(d1: D1, sql: str, params: list[Any] | None = None, *, client: httpx.Client) -> list[dict[str, Any]]:
    """Single D1 query with bounded retry on transient network errors.

    Large SELECTs (the 19,464-row gene_identifier pull, for instance)
    occasionally exceed the per-request timeout when the D1 edge is
    slow; on a ReadTimeout we back off and retry up to 3 times rather
    than abort the whole sync after a partial insert.
    """
    body: dict[str, Any] = {"sql": sql}
    if params:
        body["params"] = list(params)
    headers = {"Authorization": f"Bearer {d1.api_token}"}
    last_exc: Exception | None = None
    for attempt in range(3):
        try:
            resp = client.post(d1.url, json=body, headers=headers, timeout=300)
            data = resp.json()
            if not data.get("success"):
                raise RuntimeError(f"D1 error on {d1.database_id}: {data}")
            result = data.get("result")
            if isinstance(result, list) and result:
                return list(result[0].get("results") or [])
            if isinstance(result, dict):
                return list(result.get("results") or [])
            return []
        except (httpx.ReadTimeout, httpx.ConnectError, httpx.RemoteProtocolError) as exc:
            last_exc = exc
            wait = 2 ** attempt
            logger.warning("D1 query attempt %d failed (%s); retrying in %ds",
                           attempt + 1, type(exc).__name__, wait)
            time.sleep(wait)
    raise RuntimeError(f"D1 query failed after 3 attempts: {last_exc}") from last_exc


def _multi_insert(
    d1: D1, table: str, cols: list[str], rows: list[list[Any]],
    *, dry_run: bool, client: httpx.Client,
    on_conflict: str = "IGNORE",
) -> None:
    """INSERT OR <on_conflict> many rows into ``table`` via multi-value INSERTs.

    ``on_conflict`` controls how duplicates on a UNIQUE constraint are
    handled — ``IGNORE`` skips them (the historical default; safe when
    the public-side columns are a strict superset of what's already
    there), ``REPLACE`` overwrites the row (used when public columns
    have been added since the prior sync and existing rows need
    backfilling).
    """
    if not rows:
        logger.info("  %s: 0 rows (skip)", table)
        return
    batch = BATCH_BY_TABLE.get(table, 8)
    placeholders_one = "(" + ", ".join(["?"] * len(cols)) + ")"
    cols_sql = ", ".join(cols)
    total = len(rows)
    for start in range(0, total, batch):
        chunk = rows[start : start + batch]
        sql = (
            f"INSERT OR {on_conflict} INTO {table} ({cols_sql}) "
            f"VALUES {', '.join([placeholders_one] * len(chunk))}"
        )
        params = [v for row in chunk for v in row]
        if dry_run:
            logger.info("  [DRY] %s rows %d..%d  (n=%d, %d params)",
                        table, start, start + len(chunk) - 1, len(chunk), len(params))
            continue
        _query(d1, sql, params, client=client)
        logger.info("  %s rows %d..%d (n=%d)", table, start, start + len(chunk) - 1, len(chunk))
    logger.info("  %s: %d rows synced", table, total)


# ---------------------------------------------------------------------------
# Per-table sync functions
# ---------------------------------------------------------------------------


def sync_compara(*, priv: D1, pub: D1, dry_run: bool, client: httpx.Client) -> None:
    logger.info("compara_release / compara_ortholog")
    releases = _query(priv, "SELECT release_version, fetched_at, n_pairs, source_url, notes FROM compara_release", client=client)
    rel_rows = [[r["release_version"], r["fetched_at"], r["n_pairs"], r["source_url"], r["notes"]] for r in releases]
    _multi_insert(pub, "compara_release",
                  ["release_version", "fetched_at", "n_pairs", "source_url", "notes"],
                  rel_rows, dry_run=dry_run, client=client)
    orthologs = _query(priv, "SELECT * FROM compara_ortholog", client=client)
    ortho_cols = [
        "release_version", "human_ensembl_gene", "human_uniprot_acc", "human_gene_symbol",
        "species", "ortholog_ensembl_gene", "ortholog_uniprot_acc", "ortholog_gene_symbol",
        "orthology_type", "percent_identity", "is_high_confidence",
    ]
    ortho_rows = [[r.get(c) for c in ortho_cols] for r in orthologs]
    _multi_insert(pub, "compara_ortholog", ortho_cols, ortho_rows, dry_run=dry_run, client=client)


def sync_gene_identifier(*, priv: D1, pub: D1, dry_run: bool, client: httpx.Client) -> None:
    """Sync gene_identifier → gene_identifier_public.

    Full-row copy; the table is itself the column-whitelisted shape (no
    operational fields to strip). OR REPLACE so a re-resolve (after a
    resolver upgrade) propagates instead of being silently ignored.
    """
    logger.info("gene_identifier → gene_identifier_public")
    rows = _query(priv, """
        SELECT hgnc_id, hgnc_symbol, cohort_symbol, uniprot_acc, ncbi_gene_id,
               ensembl_gene, ensembl_canonical_protein, resolver_path,
               resolver_version, resolved_at, hgnc_xref_count, needs_review
        FROM gene_identifier
    """, client=client)
    cols = [
        "hgnc_id", "hgnc_symbol", "cohort_symbol", "uniprot_acc",
        "ncbi_gene_id", "ensembl_gene", "ensembl_canonical_protein",
        "resolver_path", "resolver_version", "resolved_at",
        "hgnc_xref_count", "needs_review",
    ]
    out = [[r.get(c) for c in cols] for r in rows]
    _multi_insert(pub, "gene_identifier_public", cols, out,
                  dry_run=dry_run, client=client, on_conflict="REPLACE")


def sync_benchmark(*, priv: D1, pub: D1, dry_run: bool, client: httpx.Client) -> None:
    logger.info("benchmark_version")
    rows = _query(priv, "SELECT * FROM benchmark_version", client=client)
    cols = [
        "bench_version", "gene_symbol", "uniprot_acc", "class",
        "truth_verdict", "truth_signal", "truth_reason", "rationale", "created_at",
    ]
    out = [[r.get(c) for c in cols] for r in rows]
    _multi_insert(pub, "benchmark_version", cols, out, dry_run=dry_run, client=client)


def sync_triage_runs(*, priv: D1, pub: D1, dry_run: bool, since: str | None, client: httpx.Client) -> None:
    logger.info("triage_run → triage_run_public")
    # Join prompt_filename in from prompt_version (text stays private).
    sql = (
        "SELECT tr.run_id, tr.created_at, tr.gene_symbol, tr.uniprot_acc, "
        "       tr.hgnc_id, tr.ensembl_gene, "
        "       tr.bench_version, tr.model, tr.prompt_variant, tr.prompt_sha, "
        "       pv.prompt_filename, tr.schema_version, tr.replicate, "
        "       tr.predicted_verdict, tr.predicted_reason, "
        "       tr.predicted_confidence, tr.predicted_key_uncertainty, "
        "       tr.verdict_reasoning, tr.correct, tr.latency_s, "
        "       tr.n_web_searches, tr.error, "
        "       tr.cost_usd, tr.prompt_tokens, tr.completion_tokens, "
        "       tr.cache_creation_tokens, tr.cache_read_tokens "
        "  FROM triage_run tr LEFT JOIN prompt_version pv "
        "       ON pv.prompt_sha = tr.prompt_sha"
    )
    params: list[Any] = []
    if since:
        sql += " WHERE tr.created_at >= ?"
        params.append(since)
    rows = _query(priv, sql, params or None, client=client)
    cols = [
        "run_id", "created_at", "gene_symbol", "uniprot_acc",
        "hgnc_id", "ensembl_gene", "bench_version",
        "model", "prompt_variant", "prompt_sha", "prompt_filename", "schema_version",
        "replicate", "predicted_verdict", "predicted_reason",
        "predicted_confidence", "predicted_key_uncertainty",
        "verdict_reasoning", "correct", "latency_s", "n_web_searches", "error",
        "cost_usd", "prompt_tokens", "completion_tokens",
        "cache_creation_tokens", "cache_read_tokens",
    ]
    out = [[r.get(c) for c in cols] for r in rows]
    # `triage_run_public` carries a UNIQUE INDEX on the natural key
    # (run_id, gene_symbol, model, prompt_variant, replicate, prompt_sha),
    # so use OR REPLACE rather than OR IGNORE. The historical sync
    # inserted rows without cost_usd/token columns when those were
    # stripped at sync time; OR REPLACE backfills them in place
    # without us having to manually DELETE first. id renumbering
    # doesn't matter — nothing outside this table references it.
    _multi_insert(pub, "triage_run_public", cols, out, dry_run=dry_run,
                  client=client, on_conflict="REPLACE")


# NOTE: `sync_surface_annotations` was removed deliberately (2026-05-30).
#
# Deep-dive SurfaceomeRecords are now written **direct to public D1** by the
# agent via `cloud.surface_annotation.publish_record` — the public
# `surface_annotation` table is the authoritative store. The old sync read
# local `data/annotations/*.json` and INSERT-OR-REPLACE'd into public D1,
# which would silently clobber the direct-to-public writes with whatever
# stale copies happened to be on disk (and we no longer keep on-disk
# fallbacks for deep dives at all). If you need to (re)publish a record,
# use `scripts/upload/upload_viewer_snapshots_to_d1.py` or the agent's own publish
# path — never a private→public / disk→public sync.


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


_ALL_TABLES = ["compara", "benchmark", "gene_identifier", "triage_run"]


def main() -> int:
    load_env()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--only", nargs="+", choices=_ALL_TABLES,
                    help="Limit sync to these table groups (default: all)")
    ap.add_argument("--since", help="ISO timestamp; only sync triage_run rows created at or after")
    ap.add_argument("--dry-run", action="store_true", help="Print row counts but don't write")
    args = ap.parse_args()

    priv = _from_env("CLOUDFLARE_D1_SURFACEOME_AGENTS_ID")
    pub = _from_env("CLOUDFLARE_D1_SURFACEOME_PUBLIC_ID")
    logger.info("private DB: %s", priv.database_id)
    logger.info("public  DB: %s", pub.database_id)

    targets = set(args.only) if args.only else set(_ALL_TABLES)
    with httpx.Client(timeout=60) as client:
        if "compara" in targets:
            sync_compara(priv=priv, pub=pub, dry_run=args.dry_run, client=client)
        if "benchmark" in targets:
            sync_benchmark(priv=priv, pub=pub, dry_run=args.dry_run, client=client)
        if "gene_identifier" in targets:
            sync_gene_identifier(priv=priv, pub=pub, dry_run=args.dry_run, client=client)
        if "triage_run" in targets:
            sync_triage_runs(priv=priv, pub=pub, dry_run=args.dry_run, since=args.since, client=client)
        # NOTE: surface_annotation is intentionally NOT synced here. Deep-dive
        # records are written direct to public D1 by the agent
        # (cloud.surface_annotation.publish_record); syncing from local
        # data/annotations/*.json would clobber those authoritative writes.
    return 0


if __name__ == "__main__":
    sys.exit(main())
