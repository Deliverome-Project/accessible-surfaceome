"""Literature (PMID/DOI-anchored) sweep over the internalization cohort -> public D1.

Augments each gene's existing SEQUENCE record with the literature track, via a
**read-back-merge** so the seq track is never clobbered:

  1. batch-read existing seq ``model_priors`` from D1 (chunked IN queries),
  2. ``annotate_literature(gene, model_priors=<seq>, web_search_mode=...)`` —
     graded BLIND to the seq prior, with per-thread ``CachedHTTP`` clients,
  3. ``publish_seq_record(merged, purge_catalog=False)`` — UPSERTs BOTH tracks,
     then purges ``/v1/catalog`` ONCE at end of sweep.

SAFETY:
  * DRY-RUN BY DEFAULT — prints cohort breakdown + cost estimate, writes nothing.
  * On ``--execute``, runs R2 backup of ``surface_internalization`` FIRST.
  * Tracks real cumulative spend against ``--max-budget-usd`` (default $3,000)
    and stops submitting new work if the cap is reached.
  * Persists a JSONL ledger per run under ``data/runs/internalization_lit/``.

Resume is prompt-sha-aware: genes already at ``has_literature=1`` under the
CURRENT ``lit_prompt_sha()`` are skipped automatically.

    uv run python scripts/internalization_lit_sweep.py --cohort canonical_and_likely
    uv run python scripts/internalization_lit_sweep.py --cohort canonical --execute
    uv run python scripts/internalization_lit_sweep.py --genes TFRC LDLR --execute
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from accessible_surfaceome.agents.internalization.literature_runner import (
    DEFAULT_LIT_MODEL,
    DEFAULT_LIT_TRIAGE_MODEL,
    DEFAULT_LIT_WEB_SCOUT_MODEL,
    annotate_literature,
    lit_prompt_sha,
)
from accessible_surfaceome.agents.internalization.models import (
    LIT_PROMPT_VERSION,
    SCHEMA_VERSION,
    InternalizationRecord,
)
from accessible_surfaceome.cloud.internalization import (
    ensure_table,
    publish_seq_record,
    purge_catalog_cache,
    purge_internalization_batch,
)
from accessible_surfaceome.env import REPO_ROOT, load_env
from accessible_surfaceome.release.catalog_presets import (
    passes_canonical,
    passes_likely,
)

logger = logging.getLogger("internalization_lit_sweep")

# Measured ballpark per-gene lit cost under adaptive Haiku-5.5 web_search +
# Sonnet-5.5 select/grade (calibrated on the 24-gene v0.2.1 benchmark: $0.286/gene
# on lit-dense targets, $0.056-$0.068/gene on sparse/empty genes -> ~$0.18-0.22/gene
# blended across the 3,213-gene L1+Canonical+Likely cohort).
PER_GENE_USD_EST = 0.20
DEFAULT_CONCURRENCY = 6
DEFAULT_MAX_BUDGET_USD = 3000.0
_D1_IN_CHUNK = 80


def load_cohort(
    d1,
    *,
    genes: list[str] | None,
    cohort: str = "l1_canonical_and_likely",
) -> tuple[list[str], dict[str, Any], list[dict[str, Any]]]:
    """Resolve the target gene list, tier breakdown, and per-gene manifest rows.

    * Explicit ``--genes`` overrides ``--cohort``.
    * ``l1_canonical_and_likely`` (default): union of the newest L1 library load
      (``l1_design_load_public`` / ``l1_member_public``) ∪ ``passes_canonical``
      ∪ ``passes_likely``. Ordered: ``L1 ∩ Canonical`` → ``L1-only`` →
      ``Canonical-only`` → ``Likely-only``.
    * ``canonical``: ``passes_canonical(filters)`` from ``surface_annotation``.
    * ``canonical_and_likely``: ``passes_likely(filters)`` (Canonical first).
    * ``all_seq``: every gene with a sequence row in ``surface_internalization``.
    """
    captured_at = datetime.now(UTC).isoformat()
    seq_rows = d1.query(
        "SELECT gene_symbol FROM surface_internalization WHERE schema_version = ?;",
        [SCHEMA_VERSION],
    )
    seq_syms = {(r["gene_symbol"] or "").upper() for r in seq_rows if r.get("gene_symbol")}

    if genes:
        deduped = sorted(dict.fromkeys(g.upper() for g in genes))
        manifest = [
            {
                "gene_symbol": g,
                "in_l1": "",
                "l1_member_count": "",
                "in_canonical": "",
                "in_likely": "",
                "has_seq_prior": int(g in seq_syms),
                "l1_load_version": "",
                "captured_at": captured_at,
            }
            for g in deduped
        ]
        return deduped, {"explicit": len(deduped)}, manifest

    if cohort == "all_seq":
        syms = sorted(seq_syms)
        manifest = [
            {
                "gene_symbol": g,
                "in_l1": "",
                "l1_member_count": "",
                "in_canonical": "",
                "in_likely": "",
                "has_seq_prior": 1,
                "l1_load_version": "",
                "captured_at": captured_at,
            }
            for g in syms
        ]
        return syms, {"all_seq": len(syms)}, manifest

    sa_rows = d1.query(
        "SELECT gene_symbol, json_extract(annotation_json, '$.filters') AS filters_json "
        "FROM surface_annotation;"
    )
    canonical_set: set[str] = set()
    likely_set: set[str] = set()
    for r in sa_rows:
        sym = (r.get("gene_symbol") or "").upper()
        if not sym:
            continue
        raw_f = r.get("filters_json")
        f = json.loads(raw_f) if raw_f else {}
        if passes_canonical(f):
            canonical_set.add(sym)
            likely_set.add(sym)
        elif passes_likely(f):
            likely_set.add(sym)

    l1_load_version = ""
    l1_member_counts: dict[str, int] = {}
    if cohort == "l1_canonical_and_likely":
        loads = d1.query(
            "SELECT load_version, n_members FROM l1_design_load_public "
            "ORDER BY created_at DESC LIMIT 1;"
        )
        if loads:
            l1_load_version = str(loads[0]["load_version"])
            m_rows = d1.query(
                "SELECT gene_symbol, COUNT(*) AS n_members FROM l1_member_public "
                "WHERE load_version = ? GROUP BY gene_symbol;",
                [l1_load_version],
            )
            for mr in m_rows:
                sym = (mr.get("gene_symbol") or "").upper()
                if sym:
                    l1_member_counts[sym] = int(mr["n_members"])

    l1_set = set(l1_member_counts)
    likely_only_set = likely_set - canonical_set

    if cohort == "canonical":
        ordered = sorted(canonical_set)
        breakdown: dict[str, Any] = {"canonical": len(canonical_set)}
    elif cohort == "canonical_and_likely":
        ordered = sorted(canonical_set) + sorted(likely_only_set)
        breakdown = {
            "canonical": len(canonical_set),
            "likely_only": len(likely_only_set),
        }
    else:
        # l1_canonical_and_likely: L1∩Canonical -> L1-rest -> Canonical-only -> Likely-only
        l1_can = sorted(l1_set & canonical_set)
        l1_other = sorted(l1_set - canonical_set)
        can_only = sorted(canonical_set - l1_set)
        lik_only = sorted(likely_only_set - l1_set)
        ordered = l1_can + l1_other + can_only + lik_only
        breakdown = {
            "l1_load_version": l1_load_version,
            "l1_members": sum(l1_member_counts.values()),
            "l1_unique_genes": len(l1_set),
            "canonical": len(canonical_set),
            "likely_only": len(likely_only_set),
            "l1_outside_can_likely": len(l1_set - likely_set),
            "union_total": len(ordered),
        }

    manifest = [
        {
            "gene_symbol": g,
            "in_l1": int(g in l1_set),
            "l1_member_count": l1_member_counts.get(g, 0),
            "in_canonical": int(g in canonical_set),
            "in_likely": int(g in likely_set),
            "has_seq_prior": int(g in seq_syms),
            "l1_load_version": l1_load_version,
            "captured_at": captured_at,
        }
        for g in ordered
    ]
    return ordered, breakdown, manifest


def write_cohort_manifest(path: Path, manifest: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "gene_symbol",
        "in_l1",
        "l1_member_count",
        "in_canonical",
        "in_likely",
        "has_seq_prior",
        "l1_load_version",
        "captured_at",
    ]
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, delimiter="\t")
        w.writeheader()
        w.writerows(manifest)


def _batch_read_seq_priors(d1, symbols: list[str]) -> dict[str, list]:
    """Batch-read existing sequence ``model_priors`` in chunks (avoids N+1 D1 calls)."""
    seq_by_gene: dict[str, list] = {}
    for i in range(0, len(symbols), _D1_IN_CHUNK):
        chunk = symbols[i : i + _D1_IN_CHUNK]
        placeholders = ", ".join(["?"] * len(chunk))
        rows = d1.query(
            f"SELECT gene_symbol, record_json FROM surface_internalization "
            f"WHERE schema_version = ? AND gene_symbol IN ({placeholders});",
            [SCHEMA_VERSION, *chunk],
        )
        for r in rows:
            sym = r["gene_symbol"]
            try:
                seq_by_gene[sym] = InternalizationRecord.model_validate_json(
                    r["record_json"]
                ).model_priors
            except Exception as exc:  # noqa: BLE001
                logger.warning("could not parse existing seq record for %s: %s", sym, exc)
                seq_by_gene[sym] = []
    return seq_by_gene


def _run_backup() -> None:
    logger.info("running R2 backup of surface_internalization before any write…")
    res = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "backup_surface_internalization_to_r2.py"),
        ],
        cwd=REPO_ROOT,
    )
    if res.returncode != 0:
        raise SystemExit(
            "backup FAILED — refusing to run the lit sweep without a fresh backup."
        )


def main(argv: list[str] | None = None) -> int:
    load_env()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--execute", action="store_true", help="Run + publish (default: dry run)."
    )
    p.add_argument(
        "--cohort",
        choices=("l1_canonical_and_likely", "canonical", "canonical_and_likely", "all_seq"),
        default="l1_canonical_and_likely",
        help="Target cohort when --genes is not given (default: l1_canonical_and_likely).",
    )
    p.add_argument(
        "--save-cohort",
        type=Path,
        default=None,
        help="Optional path to record the resolved cohort TSV manifest (also always saved in the run dir on --execute).",
    )
    p.add_argument(
        "--genes", nargs="+", default=None, help="Explicit gene list (overrides --cohort)."
    )
    p.add_argument(
        "--genes-file",
        type=Path,
        default=None,
        help="File with one gene symbol per line (overrides --cohort; e.g. missed_preprint_genes.txt).",
    )
    p.add_argument(
        "--from-r2",
        action="store_true",
        help="Seed discovered papers & Haiku triage verdicts from R2 intermediates before running.",
    )
    p.add_argument(
        "--skip-discovery",
        action="store_true",
        help="Skip fresh EuropePMC/PubTator queries (reuse R2/local seeded papers only).",
    )
    p.add_argument("--limit", type=int, default=None, help="Cap the number of genes.")
    p.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY)
    p.add_argument(
        "--web-search-mode",
        choices=("adaptive", "always", "off"),
        default="adaptive",
        help="Web-search discovery policy (default: adaptive).",
    )
    p.add_argument(
        "--model",
        default=DEFAULT_LIT_MODEL,
        help=f"Select/grade model (default: {DEFAULT_LIT_MODEL}).",
    )
    p.add_argument(
        "--triage-model",
        default=DEFAULT_LIT_TRIAGE_MODEL,
        help=f"Abstract triage model (default: {DEFAULT_LIT_TRIAGE_MODEL}).",
    )
    p.add_argument(
        "--web-scout-model",
        default=DEFAULT_LIT_WEB_SCOUT_MODEL,
        help=f"Web-search discovery scout model (default: {DEFAULT_LIT_WEB_SCOUT_MODEL}).",
    )
    p.add_argument(
        "--triage-concurrency",
        type=int,
        default=4,
        help="Per-gene Haiku triage concurrency (default: 4; total peak = concurrency * triage_concurrency).",
    )
    p.add_argument(
        "--no-upload-intermediates-r2",
        action="store_true",
        help="Skip uploading per-gene gzipped intermediates to R2 (still saved locally in the run dir).",
    )
    p.add_argument(
        "--no-per-gene-purge",
        action="store_true",
        help="Skip batched per-gene Cloudflare edge-cache purges during sweep (still purges /v1/catalog at end).",
    )
    p.add_argument(
        "--no-web-search",
        action="store_true",
        help="Legacy alias for --web-search-mode off.",
    )
    p.add_argument(
        "--max-budget-usd",
        type=float,
        default=DEFAULT_MAX_BUDGET_USD,
        help=f"Hard spend guardrail in USD (default: ${DEFAULT_MAX_BUDGET_USD:,.0f}).",
    )
    p.add_argument(
        "--force",
        action="store_true",
        help="Re-run genes already lit-annotated at the current lit-prompt sha.",
    )
    p.add_argument(
        "--no-backup",
        action="store_true",
        help="Skip the pre-run R2 backup (NOT recommended).",
    )
    p.add_argument(
        "--run-id",
        default=None,
        help="Run identifier for local JSONL ledger & archive directory.",
    )
    args = p.parse_args(argv)
    ws_mode = "off" if args.no_web_search else args.web_search_mode
    run_id = args.run_id or datetime.now(UTC).strftime("int_lit_%Y%m%d_%H%M%S")

    from accessible_surfaceome.cloud.d1_client import D1Client

    explicit_genes = list(args.genes or [])
    if args.genes_file:
        for line in args.genes_file.read_text(encoding="utf-8").splitlines():
            sym = line.strip().split("\t")[0].strip().upper()
            if sym and sym != "GENE_SYMBOL":
                explicit_genes.append(sym)

    cur_sha = lit_prompt_sha()
    with D1Client.public() as d1:
        ensure_table(d1)
        cohort, breakdown, manifest = load_cohort(
            d1, genes=explicit_genes or None, cohort=args.cohort
        )
        if args.save_cohort:
            write_cohort_manifest(args.save_cohort, manifest)
            logger.info("wrote cohort manifest (%d genes) to %s", len(manifest), args.save_cohort)

        done: set[str] = set()
        if not args.force:
            rows = d1.query(
                "SELECT gene_symbol, lit_prompt_sha FROM surface_internalization "
                "WHERE schema_version = ? AND has_literature = 1;",
                [SCHEMA_VERSION],
            )
            done = {
                r["gene_symbol"] for r in rows if r.get("lit_prompt_sha") == cur_sha
            }
        todo = [g for g in cohort if g not in done]
        if args.limit:
            todo = todo[: args.limit]

        logger.info("lit prompt: version=%s sha=%s", LIT_PROMPT_VERSION, cur_sha[:12])
        logger.info(
            "cohort=%d (%s)  already-lit@sha=%d  todo=%d  web_search_mode=%s  budget=$%.0f",
            len(cohort),
            breakdown,
            len(done),
            len(todo),
            ws_mode,
            args.max_budget_usd,
        )

        if not args.execute:
            est = len(todo) * PER_GENE_USD_EST
            print(f"\nDRY RUN — {len(todo)} genes to lit-annotate (read-back-merge)")
            print(f"  cohort: {args.cohort} ({breakdown})")
            print(f"  web_search_mode: {ws_mode}  |  concurrency: {args.concurrency}")
            print(
                f"  est spend: ~${est:,.0f} (@ ~${PER_GENE_USD_EST:.2f}/gene)  |  "
                f"budget cap: ${args.max_budget_usd:,.0f}"
            )
            print(
                f"  target: public D1 surface_internalization @ schema {SCHEMA_VERSION}, "
                f"lit-prompt {LIT_PROMPT_VERSION}"
            )
            print(f"  first {min(15, len(todo))}: {', '.join(todo[:15])}")
            print(
                "\n  → re-run with --execute (runs an R2 backup first, then writes). Nothing written."
            )
            return 0

        if not todo:
            logger.info(
                "nothing to do (all todo genes already lit-annotated at the current sha)."
            )
            return 0

        seq_by_gene = _batch_read_seq_priors(d1, todo)

        if not args.no_backup:
            _run_backup()

        run_dir = REPO_ROOT / "data" / "runs" / "internalization_lit" / run_id
        records_dir = run_dir / "records"
        intermediates_dir = run_dir / "intermediates"
        records_dir.mkdir(parents=True, exist_ok=True)
        intermediates_dir.mkdir(parents=True, exist_ok=True)
        write_cohort_manifest(run_dir / "cohort.tsv", manifest)
        ledger_path = run_dir / "ledger.jsonl"

        from accessible_surfaceome.agents._support.client import get_client
        from accessible_surfaceome.tools._shared.cache import Cache
        from accessible_surfaceome.tools._shared.http import CachedHTTP, default_cache_path
        from accessible_surfaceome.tools._shared.ratelimit import default_limiter

        shared_client = get_client()
        # Share ONE SQLite Cache (with Lock + busy_timeout=30s) and ONE per-host
        # RateLimiter across workers while giving each worker its own httpx.Client.
        shared_cache = Cache(default_cache_path())
        shared_limiter = default_limiter()
        conc = max(1, args.concurrency)
        upload_r2 = not args.no_upload_intermediates_r2
        logger.info(
            "running %d genes @ concurrency %d (triage_conc=%d, r2_intermediates=%s, ledger=%s)",
            len(todo),
            conc,
            args.triage_concurrency,
            upload_r2,
            ledger_path,
        )

        def _annotate(sym: str):
            t0 = time.monotonic()
            with CachedHTTP(shared_cache, shared_limiter) as http:
                rec = annotate_literature(
                    sym,
                    client=shared_client,
                    http=http,
                    model_priors=seq_by_gene.get(sym) or [],
                    use_web_search=(ws_mode != "off"),
                    web_search_mode=ws_mode,
                    persist=True,
                    annotations_dir=records_dir,
                    model=args.model,
                    triage_model=args.triage_model,
                    web_scout_model=args.web_scout_model,
                    triage_concurrency=args.triage_concurrency,
                    load_from_r2=args.from_r2,
                    skip_discovery=args.skip_discovery,
                    upload_to_r2=upload_r2,
                    intermediates_dir=intermediates_dir,
                    run_id=run_id,
                )
            return sym, rec, round(time.monotonic() - t0, 2)

        ok = fail = 0
        total_cost = 0.0
        idx = 0
        it = iter(todo)
        budget_hit = False
        pending_purge: list[str] = []

        with ThreadPoolExecutor(max_workers=conc) as pool, ledger_path.open(
            "a", encoding="utf-8"
        ) as ledger_fh:
            in_flight = {}
            # Seed initial wave
            for _ in range(min(conc, len(todo))):
                sym = next(it, None)
                if sym is not None:
                    in_flight[pool.submit(_annotate, sym)] = sym

            while in_flight:
                done_futs = []
                for fut in as_completed(list(in_flight)):
                    done_futs.append(fut)
                    break  # process one completion at a time so budget check gates next submit
                for fut in done_futs:
                    sym = in_flight.pop(fut)
                    idx += 1
                    try:
                        _, rec, elapsed_s = fut.result()
                        publish_seq_record(
                            rec,
                            client=d1,
                            purge_catalog=False,
                            ensure_schema=False,
                            purge_edge=False,
                        )
                        ok += 1
                        if not args.no_per_gene_purge:
                            pending_purge.append(sym)
                            if len(pending_purge) >= 30:
                                purge_internalization_batch(pending_purge, include_catalog=False)
                                pending_purge.clear()
                        lit = rec.literature
                        gene_cost = float(lit.cost_usd) if lit else 0.0
                        total_cost += gene_cost
                        n_quant_obs = (
                            sum(1 for o in lit.observations if o.quant and o.quant.rate_value is not None)
                            if lit
                            else 0
                        )
                        n_derived_kinetics = (
                            sum(1 for o in lit.observations if o.quant and o.quant.derived_t_half_min is not None)
                            if lit
                            else 0
                        )
                        entry = {
                            "gene": sym,
                            "status": "ok",
                            "overall_grade": lit.overall_grade if lit else None,
                            "overall_confidence": lit.overall_confidence if lit else None,
                            "predominant_fate": lit.predominant_fate if lit else None,
                            "n_observations": lit.n_observations if lit else 0,
                            "n_quant_obs": n_quant_obs,
                            "n_derived_kinetics": n_derived_kinetics,
                            "n_refusals": lit.n_refusals if lit else 0,
                            "n_papers_discovered": lit.n_papers_discovered if lit else 0,
                            "n_papers_fetched": lit.n_papers_fetched if lit else 0,
                            "web_search_used": bool(lit.web_search_used) if lit else False,
                            "cost_usd": round(gene_cost, 4),
                            "elapsed_s": elapsed_s,
                            "ts": datetime.now(UTC).isoformat(),
                        }
                        ledger_fh.write(json.dumps(entry) + "\n")
                        ledger_fh.flush()
                        logger.info(
                            "[%d/%d] %s -> %s (%d obs, %d quant, %d ref, ws=%s, $%.3f | total=$%.2f)",
                            idx,
                            len(todo),
                            sym,
                            lit.overall_grade if lit else "?",
                            lit.n_observations if lit else 0,
                            n_quant_obs,
                            lit.n_refusals if lit else 0,
                            lit.web_search_used if lit else False,
                            gene_cost,
                            total_cost,
                        )
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
                        logger.error(
                            "[%d/%d] %s FAILED: %s", idx, len(todo), sym, str(exc)[:200]
                        )

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
                        nxt = next(it, None)
                        if nxt is not None:
                            in_flight[pool.submit(_annotate, nxt)] = nxt

        if ok > 0:
            if pending_purge:
                purge_internalization_batch(pending_purge, include_catalog=True)
            else:
                purge_catalog_cache()
        logger.info(
            "done: %d published, %d failed, total_cost=$%.2f (mean=$%.3f/gene)%s",
            ok,
            fail,
            total_cost,
            (total_cost / ok) if ok else 0.0,
            " [STOPPED AT BUDGET CAP]" if budget_hit else "",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
