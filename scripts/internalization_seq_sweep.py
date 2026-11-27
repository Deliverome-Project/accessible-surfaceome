"""Sequence (model-prior) sweep over the internalization cohort → public D1.

Runs the BLIND sequence + DeepTMHMM E/C topology model-prior on the CANONICAL
isoform only and UPSERTs each ``InternalizationRecord`` into public D1's
``surface_internalization`` via a **read-back-merge** that preserves any
existing ``literature`` track (and all projected ``lit_*`` columns).

Cohorts (``--cohort``):
  * ``deep_dive_and_l1`` (default): UNION of every gene with a deep-dive record
    in public D1 ``surface_annotation`` (~5,332 genes) and every L1 library
    gene (from the frozen cohort manifest, ~2,395 genes → ~5,333 unique genes).
  * ``canonical_likely_low_lit``: legacy catalog-tier cohort
    (``deep_dive_tier`` in {canonical, likely} ∪ ``low_lit_uniprot``).

SAFETY:
  * DRY-RUN BY DEFAULT — prints cohort breakdown + cost estimate, writes nothing.
  * Pass ``--execute`` to run an R2 backup of ``surface_internalization`` first,
    then annotate + publish with per-gene literature read-back-merge.
  * Hard spend guardrail via ``--max-budget-usd`` (default $500): stops
    submitting new genes the instant cumulative cost reaches the cap.
  * Model + prompt-SHA-aware resume: skips a gene only if its stored
    ``seq_model`` AND ``seq_prompt_sha`` match the target run (unless ``--force``).

    uv run python scripts/internalization_seq_sweep.py                         # dry run
    uv run python scripts/internalization_seq_sweep.py --limit 5 --execute     # 5-gene canary
    uv run python scripts/internalization_seq_sweep.py --max-budget-usd 500 --execute
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
import threading
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from accessible_surfaceome.agents._support.pricing import UsageRecord
from accessible_surfaceome.agents.internalization.model_prior import prompt_sha
from accessible_surfaceome.agents.internalization.models import (
    MODEL_PRIOR_PROMPT_VERSION,
    SCHEMA_VERSION,
)
from accessible_surfaceome.agents.internalization.runner import (
    annotate_model_prior,
    load_prompt,
)
from accessible_surfaceome.cloud.d1_client import D1Client
from accessible_surfaceome.cloud.internalization import (
    backup_table_to_r2,
    ensure_table,
    publish_seq_record,
    purge_catalog_cache,
    purge_internalization_batch,
    read_existing_literature,
)
from accessible_surfaceome.env import REPO_ROOT, load_env

logger = logging.getLogger("internalization_seq_sweep")

CATALOG_URL = "https://api.deliverome.org/surfaceome/v1/catalog"
DEFAULT_L1_COHORT_TSV = (
    REPO_ROOT / "data" / "processed" / "internalization" / "cohort_deep_dive_and_l1_2026-11-27.tsv"
)
OPUS_MODEL = "claude-opus-5-5"
DEFAULT_CONCURRENCY = 12
DEFAULT_MAX_BUDGET_USD = 500.0
# Measured on claude-opus-5-5 ($4/$20/$0.20 MTok, canonical isoform only):
# ~650–2,000 input + ~2.2k cached-system read + ~900–1,400 output tok/gene
# ≈ $0.021–$0.045/gene (mean ~$0.036/gene → 5,333 genes ≈ ~$192).
PER_GENE_USD_BY_MODEL: dict[str, float] = {
    "claude-opus-5-5": 0.055,
    "claude-opus-5": 0.088,
    "claude-fable-5-2": 0.072,
    "claude-sonnet-5-5": 0.018,
}
COHORT_TIERS = ("canonical", "likely")
_PURGE_BATCH_SIZE = 50


def _estimate_per_gene_usd(models: list[str]) -> float:
    return sum(PER_GENE_USD_BY_MODEL.get(m, 0.05) for m in models)


def load_l1_genes(tsv_path: Path = DEFAULT_L1_COHORT_TSV) -> set[str]:
    """Read all L1-library gene symbols from the frozen internalization cohort TSV."""
    if not tsv_path.is_file():
        raise FileNotFoundError(f"L1 cohort manifest not found: {tsv_path}")
    out: set[str] = set()
    with tsv_path.open("r", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            if str(row.get("in_l1", "")).strip().lower() in {"1", "true", "yes"}:
                sym = (row.get("gene_symbol") or "").strip().upper()
                if sym:
                    out.add(sym)
    return out


def load_deep_dive_and_l1_cohort(
    d1: D1Client, *, l1_tsv: Path = DEFAULT_L1_COHORT_TSV
) -> tuple[list[str], dict[str, int]]:
    """Return sorted UNION of all deep-dive genes in D1 ``surface_annotation``
    and all L1 library genes."""
    dd_rows = d1.query("SELECT DISTINCT gene_symbol FROM surface_annotation;", [])
    dd = {str(r["gene_symbol"]).strip().upper() for r in dd_rows if r.get("gene_symbol")}
    l1 = load_l1_genes(l1_tsv)
    union = sorted(dd | l1)
    breakdown = {
        "deep_dive": len(dd),
        "l1": len(l1),
        "l1_only": len(l1 - dd),
        "union": len(union),
    }
    return union, breakdown


def load_catalog_tier_cohort(
    *, catalog_url: str = CATALOG_URL, include_low_lit: bool = True
) -> tuple[list[str], dict[str, int]]:
    """Legacy cohort from /v1/catalog baked deep_dive_tier tags."""
    payload = httpx.get(catalog_url, timeout=120).json()
    rows = payload["rows"]
    tier: set[str] = set()
    lowlit: set[str] = set()
    for r in rows:
        sym = (r.get("symbol") or "").strip().upper()
        if not sym:
            continue
        if r.get("deep_dive_tier") in COHORT_TIERS:
            tier.add(sym)
        if include_low_lit and r.get("low_lit_uniprot"):
            lowlit.add(sym)
    union = sorted(tier | lowlit)
    return union, {
        "tier": len(tier),
        "low_lit_uniprot": len(lowlit),
        "low_lit_only": len(lowlit - tier),
        "union": len(union),
    }


def _run_d1_backup(d1: D1Client) -> None:
    logger.info("Running pre-sweep D1 -> R2 backup…")
    key = backup_table_to_r2(d1, label="pre-seq-sweep")
    logger.info("Backup complete: r2://%s", key)


def main(argv: list[str] | None = None) -> int:
    load_env()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--execute", action="store_true", help="Run + publish (default: dry run).")
    p.add_argument(
        "--cohort",
        choices=("deep_dive_and_l1", "canonical_likely_low_lit"),
        default="deep_dive_and_l1",
        help="Target cohort (default: deep_dive_and_l1 = all surface_annotation ∪ L1).",
    )
    p.add_argument("--genes", nargs="+", default=None, help="Explicit gene list (overrides --cohort).")
    p.add_argument("--genes-file", type=Path, default=None, help="One gene symbol per line.")
    p.add_argument("--limit", type=int, default=None, help="Cap the number of genes.")
    p.add_argument("--models", nargs="+", default=[OPUS_MODEL], help="Model-prior model ids.")
    p.add_argument(
        "--no-low-lit",
        action="store_true",
        help="For canonical_likely_low_lit only: exclude low_lit_uniprot.",
    )
    p.add_argument("--catalog-url", default=CATALOG_URL)
    p.add_argument("--l1-tsv", type=Path, default=DEFAULT_L1_COHORT_TSV)
    p.add_argument(
        "--force",
        action="store_true",
        help="Re-run genes already present in D1 at the target model + prompt SHA.",
    )
    p.add_argument(
        "--max-budget-usd",
        type=float,
        default=DEFAULT_MAX_BUDGET_USD,
        help=f"Hard spend guardrail in USD (default ${DEFAULT_MAX_BUDGET_USD:.0f}).",
    )
    p.add_argument("--no-backup", action="store_true", help="Skip pre-run R2 backup.")
    p.add_argument("--run-id", default="", help="Optional run id for ledger directory.")
    p.add_argument(
        "--concurrency",
        type=int,
        default=DEFAULT_CONCURRENCY,
        help=f"Concurrent gene annotations (default {DEFAULT_CONCURRENCY}).",
    )
    args = p.parse_args(argv)

    primary_model = args.models[0]
    current_sha = prompt_sha(load_prompt())
    per_gene_est = _estimate_per_gene_usd(args.models)

    with D1Client.public() as d1:
        if args.genes:
            cohort = sorted({g.strip().upper() for g in args.genes if g.strip()})
            breakdown = {"explicit": len(cohort)}
        elif args.genes_file:
            cohort = sorted(
                {
                    ln.strip().upper()
                    for ln in args.genes_file.read_text(encoding="utf-8").splitlines()
                    if ln.strip() and not ln.lstrip().startswith("#")
                }
            )
            breakdown = {"genes_file": len(cohort)}
        elif args.cohort == "deep_dive_and_l1":
            cohort, breakdown = load_deep_dive_and_l1_cohort(d1, l1_tsv=args.l1_tsv)
        else:
            cohort, breakdown = load_catalog_tier_cohort(
                catalog_url=args.catalog_url, include_low_lit=not args.no_low_lit
            )

        existing_rows = d1.query(
            "SELECT gene_symbol, seq_model, seq_prompt_sha, has_literature "
            "FROM surface_internalization WHERE schema_version = ?;",
            [SCHEMA_VERSION],
        )
        done: set[str] = set()
        if not args.force:
            done = {
                str(r["gene_symbol"]).upper()
                for r in existing_rows
                if r.get("seq_prompt_sha") == current_sha and r.get("seq_model") == primary_model
            }
        n_with_lit = sum(1 for r in existing_rows if r.get("has_literature"))
        todo = [g for g in cohort if g not in done]
        if args.limit:
            todo = todo[: args.limit]

        est = len(todo) * per_gene_est
        conc = max(1, args.concurrency)
        eta_min = len(todo) * 0.35 / conc  # ~20s/gene on opus-5-5

        if not args.execute:
            print(f"\nDRY RUN — cohort {len(cohort)} genes ({breakdown})")
            print(f"  models          : {', '.join(args.models)} (canonical isoform only)")
            print(f"  prompt          : v{MODEL_PRIOR_PROMPT_VERSION}, sha {current_sha[:12]}")
            print(f"  already @ model : {len(done)} (skipping)  |  todo: {len(todo)}")
            print(f"  existing lit    : {n_with_lit} genes (preserved via per-gene read-back-merge)")
            print(f"  est. cost       : ~${est:,.1f} (@ ~${per_gene_est:.3f}/gene)  |  budget cap: ${args.max_budget_usd:,.0f}")
            print(f"  concurrency     : {conc}  (~{eta_min:,.0f} min ≈ {eta_min / 60:,.1f} h)")
            print(f"  first 15 todo   : {', '.join(todo[:15])}")
            print("\n  → re-run with --execute to run + publish. Nothing was written.")
            return 0

        if not todo:
            logger.info("Nothing to do — all %d cohort genes already at %s @ %s.", len(cohort), primary_model, current_sha[:12])
            return 0

        ensure_table(d1)
        if not args.no_backup:
            _run_d1_backup(d1)

        rid = args.run_id or datetime.now(UTC).strftime("int_seq_%Y%m%d_%H%M%S")
        run_dir = REPO_ROOT / "data" / "runs" / "internalization_seq" / rid
        run_dir.mkdir(parents=True, exist_ok=True)
        ledger_path = run_dir / "ledger.jsonl"
        (run_dir / "cohort.txt").write_text("\n".join(todo) + "\n", encoding="utf-8")

        from accessible_surfaceome.agents._support.client import get_client
        from accessible_surfaceome.agents.internalization.deeptmhmm_topology import load_index
        from accessible_surfaceome.tools._shared.http import open_default_client

        load_index()
        shared_client = get_client()
        tls = threading.local()

        def _thread_http():
            h = getattr(tls, "http", None)
            if h is None:
                h = open_default_client()
                tls.http = h
            return h

        def _annotate(sym: str) -> tuple[str, Any, float]:
            usage: list[UsageRecord] = []
            rec = annotate_model_prior(
                sym,
                models=tuple(args.models),
                client=shared_client,
                http=_thread_http(),
                persist=False,
                canonical_only=True,
                usage_sink=usage,
            )
            cost = sum(float(getattr(u, "cost_usd", 0.0) or 0.0) for u in usage)
            return sym, rec, cost

        logger.info(
            "running %d genes @ concurrency=%d model=%s budget=$%.2f ledger=%s",
            len(todo), conc, primary_model, args.max_budget_usd, ledger_path,
        )

        ok = fail = 0
        total_cost = 0.0
        budget_hit = False
        pending_purges: list[str] = []
        todo_iter = iter(todo)
        in_flight: dict[Future[tuple[str, Any, float]], str] = {}

        with ledger_path.open("a", encoding="utf-8") as ledger_fh, ThreadPoolExecutor(
            max_workers=conc
        ) as pool:
            # Fill initial window
            for _ in range(conc):
                sym = next(todo_iter, None)
                if sym is None:
                    break
                in_flight[pool.submit(_annotate, sym)] = sym

            while in_flight:
                done_futs, _ = wait(in_flight.keys(), return_when=FIRST_COMPLETED)
                for fut in done_futs:
                    sym = in_flight.pop(fut)
                    try:
                        _, rec, cost = fut.result()
                        total_cost += cost
                        # Read-back-merge existing literature so we NEVER clobber it!
                        existing_lit = read_existing_literature(d1, rec.gene_symbol)
                        if existing_lit is not None:
                            rec = rec.model_copy(update={"literature": existing_lit})
                        publish_seq_record(
                            rec,
                            client=d1,
                            ensure_schema=False,
                            purge_edge=False,
                        )
                        ok += 1
                        pending_purges.append(rec.gene_symbol)
                        grade = rec.model_priors[0].overall_grade if rec.model_priors else "?"
                        entry = {
                            "gene": rec.gene_symbol,
                            "status": "ok",
                            "model": primary_model,
                            "grade": grade,
                            "preserved_lit": existing_lit is not None,
                            "cost_usd": round(cost, 5),
                            "cum_cost_usd": round(total_cost, 4),
                            "ts": datetime.now(UTC).isoformat(),
                        }
                        ledger_fh.write(json.dumps(entry) + "\n")
                        ledger_fh.flush()
                        logger.info(
                            "[%d/%d] %s -> %s (lit=%s, $%.4f | total=$%.2f)",
                            ok + fail,
                            len(todo),
                            rec.gene_symbol,
                            grade,
                            "kept" if existing_lit is not None else "none",
                            cost,
                            total_cost,
                        )
                        if len(pending_purges) >= _PURGE_BATCH_SIZE:
                            purge_internalization_batch(pending_purges, include_catalog=False)
                            pending_purges.clear()
                    except Exception as exc:  # noqa: BLE001
                        fail += 1
                        entry = {
                            "gene": sym,
                            "status": "error",
                            "error": str(exc)[:300],
                            "ts": datetime.now(UTC).isoformat(),
                        }
                        ledger_fh.write(json.dumps(entry) + "\n")
                        ledger_fh.flush()
                        logger.error("[%d/%d] %s FAILED: %s", ok + fail, len(todo), sym, str(exc)[:200])

                    if total_cost >= args.max_budget_usd:
                        if not budget_hit:
                            budget_hit = True
                            logger.warning(
                                "BUDGET CAP REACHED ($%.2f >= $%.2f) — draining %d in-flight gene(s) and stopping.",
                                total_cost,
                                args.max_budget_usd,
                                len(in_flight),
                            )
                    else:
                        nxt = next(todo_iter, None)
                        if nxt is not None:
                            in_flight[pool.submit(_annotate, nxt)] = nxt

        if pending_purges:
            purge_internalization_batch(pending_purges, include_catalog=True)
        elif ok > 0:
            purge_catalog_cache()

        logger.info(
            "done: %d published, %d failed, total_cost=$%.2f (mean=$%.4f/gene)%s",
            ok,
            fail,
            total_cost,
            (total_cost / ok) if ok else 0.0,
            " [BUDGET CAP]" if budget_hit else "",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
