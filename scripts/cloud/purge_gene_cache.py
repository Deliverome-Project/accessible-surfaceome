"""Cohort-wide purge of the Worker's cached per-gene responses.

``publish_record`` already purges a gene's cached surfaces when that gene
is republished. This script covers the other case: a **Worker deploy that
changes the SHAPE of a per-gene response without touching any record**.
Nothing is republished, so nothing is purged, and every gene already
cached keeps serving the old shape for up to a day.

That is exactly what happened when the ``papers`` citation-metadata join
shipped — the endpoint started returning paper titles, but a gene cached
before the deploy kept answering without them, so the viewer fell back to
bare accessions on an arbitrary subset of genes.

Both per-gene surfaces need this, and which one depends on what the deploy
changed, so ``--surfaces`` selects:

  * ``evidence`` — ``/v1/genes/{SYMBOL}/evidence`` (the ledger + its
    serve-time ``papers`` citation join)
  * ``record``   — ``/v1/genes/{SYMBOL}`` (the record + every serve-time
    ``deterministic_features`` enrichment ``handleGene`` computes)
  * ``both``     — the default

Caching is per-POP, so a half-purged state doesn't look broken so much as
*inconsistent*: the same gene answers differently depending on which
datacenter served it. Purge the surface a deploy touched, not just the
gene you happened to spot-check.

Purges both layers the Worker reads through, using the SAME key builders
``publish_record`` uses (``_purge_urls_for`` / ``_kv_keys_for``), so the
synthetic cache-key hosts can't drift between the two paths:

  * ``caches.default`` — Cloudflare purge-by-URL (``cache.internal`` host)
  * ``RECORD_CACHE`` KV — the shared-global read-through mirror

Both soft-skip with a warning when their env var is missing
(``CLOUDFLARE_ZONE_ID`` / ``CLOUDFLARE_KV_RECORD_CACHE_ID``), matching the
publish path's posture.

Usage::

    uv run python scripts/cloud/purge_gene_cache.py            # dry-run, both
    uv run python scripts/cloud/purge_gene_cache.py --execute
    uv run python scripts/cloud/purge_gene_cache.py --surfaces record --execute
    uv run python scripts/cloud/purge_gene_cache.py --genes EGFR,CD63 --execute
"""

from __future__ import annotations

import argparse
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx

from accessible_surfaceome.cloud.d1_client import D1Client, D1Config
from accessible_surfaceome.cloud.surface_annotation import (
    _delete_kv_key,
    _kv_keys_for,
    _purge_cf_cache,
    _purge_urls_for,
)
from accessible_surfaceome.env import load_env

# Cloudflare's purge-by-URL takes at most 30 files per request on
# non-Enterprise plans.
PURGE_CHUNK = 30

# KV has no bulk-delete for arbitrary keys on this path, so deletes are
# issued one key at a time from a small pool. `httpx.Client` is thread-safe.
KV_WORKERS = 8


def _published_genes(d1: D1Client) -> list[str]:
    rows = d1.query(
        "SELECT DISTINCT gene_symbol FROM surface_annotation ORDER BY gene_symbol;",
        [],
    )
    return [r["gene_symbol"] for r in rows if r.get("gene_symbol")]


def _wanted_suffixes(sym: str, surfaces: str) -> tuple[str, ...]:
    record = f"/v1/genes/{sym}"
    evidence = f"{record}/evidence"
    if surfaces == "record":
        return (record,)
    if surfaces == "evidence":
        return (evidence,)
    return (record, evidence)


def _gene_urls(symbols: list[str], surfaces: str) -> list[str]:
    """The ``caches.default`` keys for the selected per-gene surfaces.

    ``_purge_urls_for`` returns the full publish-time purge set (record,
    evidence, catalog, gene list). The catalog + gene-list entries are
    dropped here — a Worker shape change to a per-gene handler doesn't
    invalidate them, and purging them once per gene would be 5,130 wasted
    purges on a zone shared with the main site.
    """
    out = []
    for sym in symbols:
        wanted = _wanted_suffixes(sym, surfaces)
        for url in _purge_urls_for(sym):
            if url.endswith(wanted):
                out.append(url)
    return out


def _gene_kv_keys(symbols: list[str], surfaces: str) -> list[str]:
    out = []
    for sym in symbols:
        wanted = _wanted_suffixes(sym, surfaces)
        for key in _kv_keys_for(sym):
            if key.endswith(wanted):
                out.append(key)
    return out


def _purge_edge(urls: list[str], *, client: httpx.Client) -> tuple[int, int]:
    zone = os.environ.get("CLOUDFLARE_ZONE_ID", "").strip()
    if not zone:
        print("  ! CLOUDFLARE_ZONE_ID unset — skipping edge purge "
              "(responses then refresh on their 1-day TTL)")
        return 0, 0
    token = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
    ok = fail = 0
    for start in range(0, len(urls), PURGE_CHUNK):
        chunk = urls[start : start + PURGE_CHUNK]
        try:
            if _purge_cf_cache(chunk, zone_id=zone, token=token, client=client):
                ok += len(chunk)
            else:
                fail += len(chunk)
        except Exception as exc:  # noqa: BLE001 — one bad chunk must not
            # sink the run; those genes just refresh on TTL instead.
            print(f"  ! edge purge chunk at {start} failed: {exc}")
            fail += len(chunk)
        print(f"  edge {ok + fail}/{len(urls)}", end="\r", flush=True)
    print()
    return ok, fail


def _purge_kv(keys: list[str], *, cfg: D1Config, client: httpx.Client) -> tuple[int, int]:
    ns_id = os.environ.get("CLOUDFLARE_KV_RECORD_CACHE_ID", "").strip()
    if not ns_id:
        print("  ! CLOUDFLARE_KV_RECORD_CACHE_ID unset — skipping KV purge")
        return 0, 0

    def one(key: str) -> bool:
        try:
            return _delete_kv_key(
                key,
                account_id=cfg.account_id,
                namespace_id=ns_id,
                token=cfg.api_token,
                client=client,
            )
        except Exception:  # noqa: BLE001 — a missing key 404s, which is
            # the desired end state anyway; treat as non-fatal.
            return False

    ok = fail = 0
    with ThreadPoolExecutor(max_workers=KV_WORKERS) as pool:
        futures = [pool.submit(one, k) for k in keys]
        for fut in as_completed(futures):
            if fut.result():
                ok += 1
            else:
                fail += 1
            print(f"  kv {ok + fail}/{len(keys)}", end="\r", flush=True)
    print()
    return ok, fail


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--execute", action="store_true",
                    help="Actually purge. Without this, reports what would be purged.")
    ap.add_argument("--surfaces", choices=("evidence", "record", "both"),
                    default="both",
                    help="Which per-gene surface to purge (default: both).")
    ap.add_argument("--genes", default=None,
                    help="Comma-separated symbols instead of every published gene.")
    args = ap.parse_args()

    load_env()

    if args.genes:
        symbols = [g.strip().upper() for g in args.genes.split(",") if g.strip()]
    else:
        with D1Client.public() as d1:
            symbols = _published_genes(d1)
    print(f"genes: {len(symbols)}  surfaces: {args.surfaces}")

    urls = _gene_urls(symbols, args.surfaces)
    keys = _gene_kv_keys(symbols, args.surfaces)
    print(f"  edge URLs: {len(urls)}  ({(len(urls) + PURGE_CHUNK - 1) // PURGE_CHUNK} purge calls)")
    print(f"  KV keys:   {len(keys)}")
    for u in urls[:2]:
        print(f"  e.g. {u}")

    if not args.execute:
        print("(dry-run) nothing purged — pass --execute")
        return 0

    cfg = D1Config.from_env_public()
    with httpx.Client(timeout=30.0) as client:
        edge_ok, edge_fail = _purge_edge(urls, client=client)
        kv_ok, kv_fail = _purge_kv(keys, cfg=cfg, client=client)
    print(f"edge purged: {edge_ok} ok / {edge_fail} failed")
    print(f"KV purged:   {kv_ok} ok / {kv_fail} failed")
    # A failure here is not fatal — those genes refresh on their 1-day TTL.
    return 0


if __name__ == "__main__":
    sys.exit(main())
