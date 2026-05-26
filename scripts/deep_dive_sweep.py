"""Sweep the surfaceome_v2 deep-dive annotator across a gene list.

Two phases, gated by CLI flags:

1. **Canary** (``--canary N``): annotate N genes stratified by triage
   verdict, report cost + latency histogram + projected full-sweep total,
   exit without launching the full sweep. Use this to decide whether the
   full sweep is affordable before paying for it.

2. **Full sweep** (``--confirm-full-sweep``): resume-aware sweep over the
   entire input list. Skips genes already in D1 under this ``--run-id``;
   aborts if the canary projection exceeds ``--max-total-cost-usd`` or if
   the running cost accrued so far does.

Local execution (this script): in-process ThreadPoolExecutor. Use it for
smoke tests and small (<200 gene) runs. For the full 5,680-gene sweep
use the Modal app at ``modal/deep_dive_app.py``, which imports the
helpers from this module.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

from accessible_surfaceome.agents.surfaceome_v2 import annotate
from accessible_surfaceome.cloud.deep_dive_upload import D1DeepDiveSink
from accessible_surfaceome.env import load_env
from accessible_surfaceome.paths import DATA_DIR
from accessible_surfaceome.tools._shared.http import open_default_client
from accessible_surfaceome.tools.gene_lookup import resolve_by_hgnc_id

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# gene list loading + canary selection
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GeneRow:
    hgnc_id: str
    hgnc_symbol: str
    sonnet_verdict: str  # "yes" | "borderline" | "no" | "unresolved" | "" (unlabeled)


def load_gene_list(tsv: Path) -> list[GeneRow]:
    with tsv.open() as f:
        reader = csv.DictReader(f, delimiter="\t")
        out: list[GeneRow] = []
        for r in reader:
            hgnc_id = (r.get("hgnc_id") or "").strip()
            symbol = (r.get("hgnc_symbol") or r.get("gene_symbol") or "").strip()
            if not hgnc_id or not symbol:
                continue
            out.append(GeneRow(
                hgnc_id=hgnc_id,
                hgnc_symbol=symbol,
                sonnet_verdict=(r.get("sonnet_verdict") or "").strip(),
            ))
    return out


def select_canary(rows: list[GeneRow], n: int, seed: int = 0) -> list[GeneRow]:
    """Stratified sample by sonnet_verdict so we exercise the cost
    distribution, not just the easy genes.
    """
    import random
    rng = random.Random(seed)
    buckets: dict[str, list[GeneRow]] = {}
    for r in rows:
        buckets.setdefault(r.sonnet_verdict or "unlabeled", []).append(r)
    # Take proportional slice per bucket, then top up from the largest
    # bucket if rounding leaves us short.
    per_bucket: dict[str, int] = {}
    total = len(rows)
    for k, v in buckets.items():
        per_bucket[k] = max(1, round(n * len(v) / total)) if v else 0
    while sum(per_bucket.values()) > n:
        k = max(per_bucket, key=lambda x: per_bucket[x])
        per_bucket[k] -= 1
    while sum(per_bucket.values()) < n:
        k = max(buckets, key=lambda x: len(buckets[x]))
        per_bucket[k] += 1
    out: list[GeneRow] = []
    for k, take in per_bucket.items():
        pool = buckets.get(k, [])
        rng.shuffle(pool)
        out.extend(pool[:take])
    return out


# ---------------------------------------------------------------------------
# one-gene worker (used by local executor; mirrored by Modal Function)
# ---------------------------------------------------------------------------


@dataclass
class GeneResult:
    hgnc_id: str
    hgnc_symbol: str
    cost_usd: float
    latency_s: float
    blocks_used: dict[str, int]
    error: str | None
    record_valid: bool
    # True iff the D1 sink reported a successful insert (or was skipped
    # because --no-d1). False only when sink.insert() returned False —
    # i.e. JSON wrote but the D1 mirror failed. Default True so worker
    # exceptions don't double-count as D1 failures.
    d1_mirror_ok: bool = True
    # Number of SearchEntry rows on the record's search_log. Used by the
    # canary gate to fail fast on a regression where every record ships
    # with an empty search_log (the silent-provenance-loss bug fixed in
    # the same PR as this field was introduced).
    search_log_count: int = 0


def annotate_one(
    row: GeneRow,
    *,
    run_id: str,
    sink: D1DeepDiveSink | None,
    annotations_dir: Path,
    max_cost_per_gene_usd: float,
) -> GeneResult:
    """Annotate one gene end-to-end. Used by both the local sweep loop and
    (importable) the Modal Function. Writes per-gene JSON to
    ``annotations_dir`` and best-effort streams to D1 via ``sink``.
    """
    http = open_default_client()
    t0 = time.monotonic()
    try:
        try:
            bundle = resolve_by_hgnc_id(row.hgnc_id, http=http)
        except Exception as exc:  # noqa: BLE001
            return GeneResult(
                hgnc_id=row.hgnc_id, hgnc_symbol=row.hgnc_symbol,
                cost_usd=0.0, latency_s=time.monotonic() - t0,
                blocks_used={}, error=f"resolve failed: {exc}", record_valid=False,
            )

        result = annotate(bundle.hgnc_symbol, http=http, persist=False)
        cost = float(result.total_cost_usd)
        latency = time.monotonic() - t0

        if cost > max_cost_per_gene_usd:
            return GeneResult(
                hgnc_id=row.hgnc_id, hgnc_symbol=row.hgnc_symbol,
                cost_usd=cost, latency_s=latency,
                blocks_used=result.blocks_used,
                error=f"cost_cap_exceeded ({cost:.2f} > {max_cost_per_gene_usd:.2f})",
                record_valid=False,
            )

        if result.record is None:
            return GeneResult(
                hgnc_id=row.hgnc_id, hgnc_symbol=row.hgnc_symbol,
                cost_usd=cost, latency_s=latency,
                blocks_used=result.blocks_used, error=result.error,
                record_valid=False,
            )

        # Canonical artifact: data/annotations/<symbol>.json
        annotations_dir.mkdir(parents=True, exist_ok=True)
        out = annotations_dir / f"{bundle.hgnc_symbol}.json"
        out.write_text(result.record.model_dump_json(indent=2))

        # Best-effort D1 mirror. Capture the return so silent D1 failures
        # bubble up into the sweep summary instead of dying as log
        # warnings.
        d1_mirror_ok = True
        if sink is not None:
            d1_mirror_ok = sink.insert(
                result.record,
                cost_usd=cost,
                latency_s=latency,
                n_tool_calls=len(result.timing),
            )

        return GeneResult(
            hgnc_id=row.hgnc_id, hgnc_symbol=row.hgnc_symbol,
            cost_usd=cost, latency_s=latency,
            blocks_used=result.blocks_used, error=None, record_valid=True,
            d1_mirror_ok=d1_mirror_ok,
            search_log_count=len(result.record.search_log),
        )
    finally:
        http.close()


# ---------------------------------------------------------------------------
# local executor
# ---------------------------------------------------------------------------


def run_local(
    rows: list[GeneRow],
    *,
    run_id: str,
    sink: D1DeepDiveSink | None,
    annotations_dir: Path,
    concurrency: int,
    max_cost_per_gene_usd: float,
    max_total_cost_usd: float | None,
) -> list[GeneResult]:
    results: list[GeneResult] = []
    total_cost = 0.0
    with ThreadPoolExecutor(max_workers=concurrency) as ex:
        futures = {
            ex.submit(
                annotate_one,
                r,
                run_id=run_id,
                sink=sink,
                annotations_dir=annotations_dir,
                max_cost_per_gene_usd=max_cost_per_gene_usd,
            ): r
            for r in rows
        }
        for fut in as_completed(futures):
            r = futures[fut]
            try:
                res = fut.result()
            except Exception as exc:  # noqa: BLE001
                res = GeneResult(
                    hgnc_id=r.hgnc_id, hgnc_symbol=r.hgnc_symbol,
                    cost_usd=0.0, latency_s=0.0, blocks_used={},
                    error=f"worker raised: {exc}", record_valid=False,
                )
            results.append(res)
            total_cost += res.cost_usd
            if not res.record_valid:
                status = f"FAIL ({res.error})"
            elif not res.d1_mirror_ok:
                status = "OK (D1 MIRROR FAILED)"
            else:
                status = "OK"
            print(
                f"[{len(results):4d}/{len(rows)}] {res.hgnc_symbol:12s} "
                f"${res.cost_usd:6.3f}  {res.latency_s:6.1f}s  {status}",
                flush=True,
            )
            if max_total_cost_usd is not None and total_cost > max_total_cost_usd:
                print(
                    f"!! aborting: running cost ${total_cost:.2f} > "
                    f"--max-total-cost-usd ${max_total_cost_usd:.2f}",
                    flush=True,
                )
                for f2 in futures:
                    f2.cancel()
                break
    return results


# ---------------------------------------------------------------------------
# canary summary + full-sweep gate
# ---------------------------------------------------------------------------


def summarize_canary(results: list[GeneResult], total_genes: int) -> dict:
    costs = [r.cost_usd for r in results if r.record_valid]
    latencies = [r.latency_s for r in results if r.record_valid]
    if not costs:
        return {"valid": 0, "failed": len(results), "projection": None}

    def pct(xs: list[float], q: float) -> float:
        xs = sorted(xs)
        i = max(0, min(len(xs) - 1, int(round(q * (len(xs) - 1)))))
        return xs[i]

    median = statistics.median(costs)
    p95 = pct(costs, 0.95)
    mx = max(costs)
    summary = {
        "valid": len(costs),
        "failed": len(results) - len(costs),
        "cost_median_usd": median,
        "cost_p95_usd": p95,
        "cost_max_usd": mx,
        "latency_median_s": statistics.median(latencies),
        "latency_p95_s": pct(latencies, 0.95),
        "projection": {
            "total_genes": total_genes,
            "projected_total_usd_median_extrap": median * total_genes,
            "projected_total_usd_p95_extrap": p95 * total_genes,
        },
    }
    return summary


def check_search_log_populated(results: list[GeneResult]) -> str | None:
    """Return an error message if every valid record in the canary has an
    empty ``search_log``, else None.

    The v2 orchestrator builds ``record.search_log`` from
    ``DualPlanTrimSelectResult.{a1,a2}.search_log``. A regression that
    leaves the field empty silently loses per-gene provenance — a class
    of bug expensive to detect after the full sweep finishes. Fail the
    canary loudly instead.
    """
    valid = [r for r in results if r.record_valid]
    if not valid:
        return None
    if max(r.search_log_count for r in valid) == 0:
        return (
            f"canary aborted: {len(valid)} valid records but every one has "
            "search_log=[]. The v2 orchestrator's search-log translation is "
            "broken — re-running the full sweep would silently lose "
            "per-gene provenance for every gene. Fix the regression in "
            "src/accessible_surfaceome/agents/surfaceome_v2/orchestrator.py "
            "before launching."
        )
    return None


def print_canary_report(summary: dict) -> None:
    print()
    print("=== canary report ===")
    print(json.dumps(summary, indent=2))
    print()
    proj = summary.get("projection")
    if proj:
        print(
            "Projected full-sweep cost (extrapolated from canary):\n"
            f"  median × {proj['total_genes']} = ${proj['projected_total_usd_median_extrap']:.2f}\n"
            f"  p95    × {proj['total_genes']} = ${proj['projected_total_usd_p95_extrap']:.2f}",
            flush=True,
        )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    load_env()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--gene-list", required=True, type=Path,
                   help="TSV with hgnc_id + hgnc_symbol columns (e.g. candidate_universe.tsv)")
    p.add_argument("--run-id", required=True, help="Sweep tag (used as deep_dive_run.run_id)")
    p.add_argument("--canary", type=int, default=0,
                   help="If >0, run a stratified N-gene canary and exit without launching full sweep")
    p.add_argument("--confirm-full-sweep", action="store_true",
                   help="Required to launch the full sweep after canary review")
    p.add_argument("--concurrency", type=int, default=4,
                   help="Local ThreadPoolExecutor size (Modal app uses its own concurrency knobs)")
    p.add_argument("--max-cost-per-gene-usd", type=float, default=10.0,
                   help="Per-gene cost cap; aborts the gene if exceeded")
    p.add_argument("--max-total-cost-usd", type=float, default=18000.0,
                   help="Sweep-wide cost cap; aborts the sweep when running cost crosses this")
    p.add_argument("--annotations-dir", type=Path,
                   default=DATA_DIR / "annotations",
                   help="Where per-gene JSON lands (canonical artifact)")
    p.add_argument("--no-d1", action="store_true",
                   help="Skip the D1 sink (JSON only); useful for offline smoke tests")
    p.add_argument("--limit", type=int, default=None,
                   help="Truncate the gene list to N rows after resume filtering (debug only)")
    args = p.parse_args(argv)

    if args.canary and args.confirm_full_sweep:
        print("error: pass either --canary OR --confirm-full-sweep, not both", file=sys.stderr)
        return 2
    if not args.canary and not args.confirm_full_sweep:
        print(
            "error: pass --canary N for the first pass, or --confirm-full-sweep "
            "to launch the full sweep after canary review",
            file=sys.stderr,
        )
        return 2

    all_rows = load_gene_list(args.gene_list)
    print(f"loaded {len(all_rows)} genes from {args.gene_list}", flush=True)

    sink: D1DeepDiveSink | None = None
    if not args.no_d1:
        sink = D1DeepDiveSink(run_id=args.run_id)
        before = len(all_rows)
        all_rows = [r for r in all_rows if not sink.already_done(r.hgnc_symbol)]
        print(
            f"resume: {before - len(all_rows)} genes already in D1 under "
            f"run_id={args.run_id}; {len(all_rows)} remaining",
            flush=True,
        )

    if args.canary:
        canary_rows = select_canary(all_rows, args.canary)
        print(f"canary: {len(canary_rows)} genes stratified by sonnet_verdict", flush=True)
        results = run_local(
            canary_rows,
            run_id=args.run_id,
            sink=sink,
            annotations_dir=args.annotations_dir,
            concurrency=args.concurrency,
            max_cost_per_gene_usd=args.max_cost_per_gene_usd,
            max_total_cost_usd=None,  # canary has its own implicit budget (N × cap)
        )
        summary = summarize_canary(results, total_genes=len(all_rows))
        print_canary_report(summary)
        err = check_search_log_populated(results)
        if err is not None:
            print(f"\n!! {err}", file=sys.stderr, flush=True)
            if sink is not None:
                sink.close()
            return 3
        if sink is not None:
            sink.close()
        return 0

    # full sweep
    rows = all_rows[: args.limit] if args.limit else all_rows
    print(f"full sweep: launching {len(rows)} genes with concurrency={args.concurrency}", flush=True)
    results = run_local(
        rows,
        run_id=args.run_id,
        sink=sink,
        annotations_dir=args.annotations_dir,
        concurrency=args.concurrency,
        max_cost_per_gene_usd=args.max_cost_per_gene_usd,
        max_total_cost_usd=args.max_total_cost_usd,
    )
    summary = summarize_canary(results, total_genes=len(rows))
    print_canary_report(summary)
    failed = [r for r in results if not r.record_valid]
    d1_failed = [r for r in results if r.record_valid and not r.d1_mirror_ok]
    print(f"\ntotals: valid={len(results) - len(failed)}  failed={len(failed)}", flush=True)
    if d1_failed:
        print(
            f"!! d1 mirror failures: {len(d1_failed)}/{len(results) - len(failed)} "
            "(JSON files landed; D1 rows did NOT — backfill from JSON before re-running "
            "or the next resume will re-spend on these genes)",
            flush=True,
        )
    if sink is not None:
        sink.close()
    return 0 if not failed and not d1_failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
