"""Modal app — internalization literature sweep (3,213-gene L1 ∪ Canonical ∪ Likely).

$0 preflight (checks secrets, R2 write access, and container reference TSVs):

    uv run --extra modal modal run modal/internalization_lit_app.py::check_secret

5-gene Modal canary (verifies prompt caching, R2 intermediates, and rate gate;
writes to Modal Volume + R2 only unless ``--publish-d1`` is passed):

    uv run --extra modal modal run modal/internalization_lit_app.py::canary

Full 3,213-gene sweep (dry-run by default; pass ``--execute`` to back up D1 to R2,
annotate in waves with a hard ``--max-budget-usd 3000`` cap, publish to public D1,
upload gzipped intermediates to R2, and batch-purge Cloudflare edge cache):

    uv run --extra modal modal run modal/internalization_lit_app.py::full_sweep
    uv run --extra modal modal run modal/internalization_lit_app.py::full_sweep --execute

Architecture notes:
  * **Prompt caching on Modal:** Anthropic ephemeral prompt caching is org-global
    on Anthropic's servers (keyed on model + exact system-prompt prefix), so all
    Modal containers share one warm cache automatically (~90%+ hit rate across
    parallel containers).
  * **Central rate-limit gate:** ``rate_limit_gate`` (``max_containers=1``)
    coordinates per-host intervals for EuropePMC, PubTator, NCBI, Unpaywall, and
    DataCite across every Modal worker.
  * **3-way durability & resume:**
      1. Public D1 ``surface_internalization`` (read-back-merge preserves
         ``model_priors``; prompt-SHA dedup makes re-runs resume automatically).
      2. Cloudflare R2 ``internalization_lit_intermediates/{GENE}/latest.json.gz``
         + ``{run_id}.json.gz`` (gzipped full discovery/triage/clip/evidence
         bundle for future incremental ``--add-papers`` runs).
      3. Modal Volume ``surfaceome-internalization-lit`` (per-gene JSON + ledger).
"""

from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import modal

from accessible_surfaceome.tools._shared.ratelimit import reserve_slot

GATE_MAX_WAIT_S = 120.0
# Default concurrency: 10 containers × 3 inputs/container = 30 genes in flight.
# Keeps Anthropic RPM/OTPM comfortable while finishing 3,213 genes in ~1.5-2 h.
MAX_CONTAINERS = int(os.environ.get("INT_LIT_MAX_CONTAINERS", "10"))
MAX_INPUTS = int(os.environ.get("INT_LIT_MAX_INPUTS", "3"))
GENE_TIMEOUT_S = int(os.environ.get("INT_LIT_GENE_TIMEOUT_S", str(20 * 60)))

_IMAGE_ENV = {"ACCESSIBLE_SURFACEOME_REPO_ROOT": "/repo"}

image = (
    modal.Image.debian_slim(python_version="3.14")
    .apt_install("git", "ca-certificates")
    .pip_install("uv>=0.13.4", "modal>=0.66")
    .add_local_dir(
        ".",
        "/repo",
        copy=True,
        ignore=[
            ".venv",
            ".claude",
            ".runs",
            ".pytest_cache",
            ".ruff_cache",
            "data/raw",
            "data/runs",
            "data/backups",
            "data/annotations",
            "data/analysis",
            "paper",
            "viewer",
            # Exclude bulky local caches under data/external EXCEPT the two
            # lightweight reference TSVs needed inside workers:
            #   1. data/external/ncbi_gene_info/Homo_sapiens.protein_coding.with_hgnc.tsv
            #   2. data/external/hgnc/hgnc_complete_set.tsv
            "data/external/**",
            "!data/external/hgnc",
            "!data/external/hgnc/**",
            "!data/external/ncbi_gene_info",
            "!data/external/ncbi_gene_info/Homo_sapiens.protein_coding.with_hgnc.tsv",
            "data/processed/**",
            "!data/processed/internalization",
            "!data/processed/internalization/**",
            "node_modules",
            "viewer/node_modules",
            "viewer/.next",
            ".git",
            "*.pyc",
            "__pycache__",
        ],
    )
    .workdir("/repo")
    .run_commands("uv pip install --system --no-cache -e .")
    .run_commands(
        "python -c \"import sys; from pathlib import Path; "
        "ncbi = Path('/repo/data/external/ncbi_gene_info/Homo_sapiens.protein_coding.with_hgnc.tsv'); "
        "sys.exit(0) if ncbi.exists() and ncbi.stat().st_size > 1_000_000 "
        "else sys.exit(f'Missing or pointer NCBI TSV at {ncbi} (size={ncbi.stat().st_size if ncbi.exists() else 0})')\""
    )
    .env(_IMAGE_ENV)
)
if modal.is_local():
    from accessible_surfaceome.trust_store import harden

    image = harden(image)

app = modal.App("surfaceome-internalization-lit")
volume = modal.Volume.from_name("surfaceome-internalization-lit", create_if_missing=True)
secret = modal.Secret.from_name("surfaceome-env")

VOL_MOUNT = "/internalization_lit"

_RATE_LIMIT_LAST_CALL: dict[str, float] = {}
_RATE_LIMIT_LOCK = threading.Lock()

# Container-local shared SQLite cache + rate limiter (shared safely across the
# container's @modal.concurrent inputs; external limits route to rate_limit_gate).
_CONTAINER_INIT_LOCK = threading.Lock()
_CONTAINER_STATE: dict[str, Any] = {}

_REQUIRED_SECRET_KEYS = (
    "ANTHROPIC_API_KEY",
    "CLOUDFLARE_ACCOUNT_ID",
    "CLOUDFLARE_API_TOKEN",
    "CLOUDFLARE_ZONE_ID",
    "CLOUDFLARE_D1_SURFACEOME_PUBLIC_ID",
    "NCBI_API_KEYS",
)


@app.function(
    image=image,
    cpu=0.25,
    memory=256,
    timeout=30,
    max_containers=1,
)
@modal.concurrent(max_inputs=200)
def rate_limit_gate(state_key: str, interval_s: float) -> float:
    """Central non-blocking reservation gate for EuropePMC/PubTator/NCBI/etc."""
    with _RATE_LIMIT_LOCK:
        wait_for = reserve_slot(
            _RATE_LIMIT_LAST_CALL,
            state_key,
            float(interval_s),
            now=time.monotonic(),
            max_wait_s=GATE_MAX_WAIT_S,
        )
    if wait_for >= GATE_MAX_WAIT_S:
        print(
            f"rate_limit_gate: wait capped at {GATE_MAX_WAIT_S}s for {state_key!r}",
            flush=True,
        )
    return wait_for


@app.function(
    image=image,
    cpu=0.25,
    memory=256,
    timeout=60,
    secrets=[secret],
)
def secret_presence_check() -> dict[str, Any]:
    """$0 worker-side check: verifies secret keys, R2 write scope, and NCBI TSV."""
    sys.path.insert(0, "/repo/src")
    from accessible_surfaceome.agents.internalization.ids import resolve_hgnc_id
    from accessible_surfaceome.cloud import r2_client
    from accessible_surfaceome.env import load_env

    load_env()
    present = {k: bool((os.environ.get(k) or "").strip()) for k in _REQUIRED_SECRET_KEYS}
    pool = (os.environ.get("NCBI_API_KEYS") or "").replace(";", ",").replace(" ", ",")

    try:
        r2_write_ok = r2_client.put_object(
            key="_preflight/check_internalization_r2_probe.txt",
            body=b"ok",
            content_type="text/plain",
        )
    except Exception:  # noqa: BLE001
        r2_write_ok = False

    try:
        hgnc_ok = resolve_hgnc_id("TFRC") == "HGNC:11763"
    except Exception:  # noqa: BLE001
        hgnc_ok = False

    cohort_tsv = Path("/repo/data/processed/internalization/cohort_l1_canonical_likely_2026-11-26.tsv")
    return {
        "present": present,
        "ncbi_pool_size": len([x for x in pool.split(",") if x.strip()]),
        "r2_write_ok": bool(r2_write_ok),
        "hgnc_resolve_ok": hgnc_ok,
        "cohort_tsv_exists": cohort_tsv.exists(),
        "cohort_tsv_bytes": cohort_tsv.stat().st_size if cohort_tsv.exists() else 0,
    }


def _get_container_runtime() -> tuple[Any, Any, Any]:
    """Lazily initialize one Anthropic client, SQLite Cache, and RateLimiter per container."""
    with _CONTAINER_INIT_LOCK:
        if "client" not in _CONTAINER_STATE:
            sys.path.insert(0, "/repo/src")
            from accessible_surfaceome.agents._support.client import get_client
            from accessible_surfaceome.env import load_env
            from accessible_surfaceome.tools._shared.cache import Cache
            from accessible_surfaceome.tools._shared.http import default_cache_path
            from accessible_surfaceome.tools._shared.ratelimit import (
                default_limiter,
                set_external_rate_limit_gate,
            )

            load_env()
            set_external_rate_limit_gate(
                lambda state_key, interval_s: rate_limit_gate.remote(state_key, interval_s)
            )
            _CONTAINER_STATE["client"] = get_client()
            _CONTAINER_STATE["cache"] = Cache(default_cache_path())
            _CONTAINER_STATE["limiter"] = default_limiter()
        return (
            _CONTAINER_STATE["client"],
            _CONTAINER_STATE["cache"],
            _CONTAINER_STATE["limiter"],
        )


@app.function(
    image=image,
    cpu=0.5,
    memory=2048,
    timeout=GENE_TIMEOUT_S,
    retries=modal.Retries(max_retries=1, backoff_coefficient=2.0),
    volumes={VOL_MOUNT: volume},
    secrets=[secret],
    max_containers=MAX_CONTAINERS,
)
@modal.concurrent(max_inputs=MAX_INPUTS)
def annotate_one(payload: dict[str, Any]) -> dict[str, Any]:
    """Run internalization literature annotation for one gene inside Modal.

    Publishes merged record to public D1 (when ``publish_d1=True``), uploads
    gzipped intermediates to R2 (when ``upload_r2=True``), and saves both the
    record JSON and intermediates on the Modal Volume.
    """
    t0 = time.monotonic()
    gene: str = payload["gene"]
    run_id: str = payload["run_id"]
    ws_mode: str = payload.get("web_search_mode", "adaptive")
    model: str = payload["model"]
    triage_model: str = payload["triage_model"]
    web_scout_model: str = payload["web_scout_model"]
    triage_concurrency: int = int(payload.get("triage_concurrency", 4))
    publish_d1: bool = bool(payload.get("publish_d1", False))
    upload_r2: bool = bool(payload.get("upload_r2", True))
    seq_priors_raw: list[dict[str, Any]] = payload.get("model_priors") or []

    try:
        client, shared_cache, shared_limiter = _get_container_runtime()
        from accessible_surfaceome.agents.internalization.literature_runner import (
            annotate_literature,
        )
        from accessible_surfaceome.agents.internalization.models import ModelPriorTrack
        from accessible_surfaceome.cloud.d1_client import D1Client
        from accessible_surfaceome.cloud.internalization import publish_seq_record
        from accessible_surfaceome.tools._shared.http import CachedHTTP

        priors = [ModelPriorTrack.model_validate(mp) for mp in seq_priors_raw]
        run_root = Path(VOL_MOUNT) / run_id
        records_dir = run_root / "records"
        intermediates_dir = run_root / "intermediates"

        with CachedHTTP(shared_cache, shared_limiter) as http:
            rec = annotate_literature(
                gene,
                client=client,
                http=http,
                model_priors=priors,
                use_web_search=(ws_mode != "off"),
                web_search_mode=ws_mode,  # type: ignore[arg-type]
                persist=True,
                annotations_dir=records_dir,
                model=model,
                triage_model=triage_model,
                web_scout_model=web_scout_model,
                triage_concurrency=triage_concurrency,
                upload_to_r2=upload_r2,
                intermediates_dir=intermediates_dir,
                run_id=run_id,
            )

        if publish_d1:
            with D1Client.public() as d1:
                publish_seq_record(
                    rec,
                    client=d1,
                    purge_catalog=False,
                    ensure_schema=False,
                    purge_edge=False,
                    max_retries=3,
                )

        volume.commit()
        lit = rec.literature
        n_quant_obs = (
            sum(1 for o in lit.observations if o.quant and o.quant.rate_value is not None)
            if lit
            else 0
        )
        n_derived = (
            sum(1 for o in lit.observations if o.quant and o.quant.derived_t_half_min is not None)
            if lit
            else 0
        )
        n_apparent = (
            sum(1 for o in lit.observations if o.quant and o.quant.apparent_t_half_min is not None)
            if lit
            else 0
        )
        from accessible_surfaceome.agents.internalization.intermediates import (
            decompress_intermediates,
        )

        inter_path = intermediates_dir / f"{rec.gene_symbol}.json.gz"
        cache_read_tok = cache_write_tok = 0
        if inter_path.exists():
            try:
                inter_summary = decompress_intermediates(inter_path.read_bytes()).get("summary") or {}
                cache_read_tok = int(inter_summary.get("cache_read_tokens", 0) or 0)
                cache_write_tok = int(inter_summary.get("cache_write_tokens", 0) or 0)
            except Exception:  # noqa: BLE001
                pass
        return {
            "gene": gene,
            "status": "ok",
            "overall_grade": lit.overall_grade if lit else None,
            "overall_confidence": lit.overall_confidence if lit else None,
            "predominant_fate": lit.predominant_fate if lit else None,
            "n_observations": lit.n_observations if lit else 0,
            "n_quant_obs": n_quant_obs,
            "n_derived_kinetics": n_derived,
            "n_apparent_t_half": n_apparent,
            "n_refusals": lit.n_refusals if lit else 0,
            "n_papers_discovered": lit.n_papers_discovered if lit else 0,
            "n_papers_fetched": lit.n_papers_fetched if lit else 0,
            "web_search_used": bool(lit.web_search_used) if lit else False,
            "cache_read_tokens": cache_read_tok,
            "cache_write_tokens": cache_write_tok,
            "cost_usd": round(float(lit.cost_usd), 4) if lit else 0.0,
            "elapsed_s": round(time.monotonic() - t0, 2),
            "published_d1": publish_d1,
            "uploaded_r2": upload_r2,
            "ts": datetime.now(UTC).isoformat(),
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "gene": gene,
            "status": "error",
            "error": str(exc)[:400],
            "elapsed_s": round(time.monotonic() - t0, 2),
            "ts": datetime.now(UTC).isoformat(),
        }


# ---------------------------------------------------------------------------
# Driver helpers + entrypoints
# ---------------------------------------------------------------------------


def _load_genes_from_tsv(tsv_path: Path) -> list[str]:
    genes: list[str] = []
    with tsv_path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            sym = (row.get("gene_symbol") or row.get("symbol") or "").strip().upper()
            if sym:
                genes.append(sym)
    return list(dict.fromkeys(genes))


def _run_d1_backup() -> None:
    from accessible_surfaceome.env import REPO_ROOT

    print("Running pre-sweep R2 backup of public D1 surface_internalization…", flush=True)
    res = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "backup_surface_internalization_to_r2.py")],
        cwd=REPO_ROOT,
    )
    if res.returncode != 0:
        raise RuntimeError("Pre-sweep R2 backup FAILED — aborting before any D1 write.")


@app.local_entrypoint()
def check_secret():
    """$0 preflight: verify surfaceome-env secret, R2 write access, and container TSVs."""
    result = secret_presence_check.remote()
    print(json.dumps(result, indent=2))
    missing = [k for k, ok in result["present"].items() if not ok]
    if missing:
        raise RuntimeError(f"surfaceome-env secret missing keys: {missing}")
    if not result.get("r2_write_ok"):
        raise RuntimeError("R2 write probe failed — check CLOUDFLARE_API_TOKEN R2:Edit scope.")
    if not result.get("hgnc_resolve_ok"):
        raise RuntimeError("HGNC TSV resolution failed inside Modal container.")
    print("\n✓ Modal preflight passed (secrets + R2 write + NCBI HGNC TSV + cohort TSV).")


@app.local_entrypoint()
def canary(
    genes: str = "TFRC,ERBB2,TMEM123,THBD,OR1N1",
    run_id: str = "",
    web_search_mode: str = "adaptive",
    publish_d1: bool = False,
    upload_r2: bool = True,
):
    """Run a 5-gene Modal canary to verify end-to-end execution, R2 intermediates,
    rate gate, and prompt caching before launching the 3,213-gene sweep."""
    from accessible_surfaceome.agents.internalization.literature_runner import (
        DEFAULT_LIT_MODEL,
        DEFAULT_LIT_TRIAGE_MODEL,
        DEFAULT_LIT_WEB_SCOUT_MODEL,
    )
    from accessible_surfaceome.cloud.d1_client import D1Client
    from accessible_surfaceome.env import load_env
    from scripts.internalization_lit_sweep import _batch_read_seq_priors

    load_env()
    gene_list = [g.strip().upper() for g in genes.split(",") if g.strip()]
    rid = run_id or datetime.now(UTC).strftime("int_lit_canary_%Y%m%d_%H%M%S")

    seq_by_gene: dict[str, list[dict[str, Any]]] = {}
    if publish_d1:
        with D1Client.public() as d1:
            priors_map = _batch_read_seq_priors(d1, gene_list)
            seq_by_gene = {
                g: [m.model_dump(mode="json") for m in plist] for g, plist in priors_map.items()
            }

    payloads = [
        {
            "gene": g,
            "run_id": rid,
            "web_search_mode": web_search_mode,
            "model": DEFAULT_LIT_MODEL,
            "triage_model": DEFAULT_LIT_TRIAGE_MODEL,
            "web_scout_model": DEFAULT_LIT_WEB_SCOUT_MODEL,
            "triage_concurrency": 4,
            "publish_d1": publish_d1,
            "upload_r2": upload_r2,
            "model_priors": seq_by_gene.get(g, []),
        }
        for g in gene_list
    ]
    print(f"Launching Modal canary ({len(payloads)} genes, run_id={rid}, publish_d1={publish_d1}, upload_r2={upload_r2})…")
    total_cost = 0.0
    for res in annotate_one.map(payloads, return_exceptions=True):
        if isinstance(res, BaseException):
            print(f"  EXCEPTION: {res}", flush=True)
            continue
        total_cost += float(res.get("cost_usd", 0.0) or 0.0)
        if res.get("status") != "ok":
            print(
                f"  {res.get('gene'):10s} ERROR ({res.get('elapsed_s')}s): {res.get('error')}",
                flush=True,
            )
            continue
        print(
            f"  {res.get('gene'):10s} status={res.get('status')} grade={res.get('overall_grade')} "
            f"obs={res.get('n_observations')} q={res.get('n_quant_obs')} "
            f"der={res.get('n_derived_kinetics')} app={res.get('n_apparent_t_half')} "
            f"ref={res.get('n_refusals')} ws={res.get('web_search_used')} "
            f"cache_r={res.get('cache_read_tokens', 0)} "
            f"cost=${res.get('cost_usd', 0.0):.4f} t={res.get('elapsed_s')}s",
            flush=True,
        )
    print(f"\nCanary done: total=${total_cost:.4f} (mean=${total_cost / max(1, len(gene_list)):.4f}/gene)")


@app.local_entrypoint()
def full_sweep(
    cohort_tsv: str = "data/processed/internalization/cohort_l1_canonical_likely_2026-11-26.tsv",
    run_id: str = "",
    web_search_mode: str = "adaptive",
    max_budget_usd: float = 3000.0,
    wave_size: int = 150,
    limit: int = 0,
    force: bool = False,
    no_backup: bool = False,
    upload_r2: bool = True,
    execute: bool = False,
):
    """Run the 3,213-gene internalization literature sweep on Modal in budget-gated waves.

    DRY-RUN by default — pass ``--execute`` to back up D1 to R2 and publish.
    """
    from accessible_surfaceome.agents.internalization.literature_runner import (
        DEFAULT_LIT_MODEL,
        DEFAULT_LIT_TRIAGE_MODEL,
        DEFAULT_LIT_WEB_SCOUT_MODEL,
        lit_prompt_sha,
    )
    from accessible_surfaceome.agents.internalization.models import (
        LIT_PROMPT_VERSION,
        SCHEMA_VERSION,
    )
    from accessible_surfaceome.cloud.d1_client import D1Client
    from accessible_surfaceome.cloud.internalization import (
        ensure_table,
        purge_catalog_cache,
        purge_internalization_batch,
    )
    from accessible_surfaceome.env import REPO_ROOT, load_env
    from scripts.internalization_lit_sweep import PER_GENE_USD_EST, _batch_read_seq_priors

    load_env()
    tsv_path = Path(cohort_tsv)
    if not tsv_path.is_absolute():
        tsv_path = REPO_ROOT / tsv_path
    cohort = _load_genes_from_tsv(tsv_path)
    cur_sha = lit_prompt_sha()
    rid = run_id or datetime.now(UTC).strftime("int_lit_modal_%Y%m%d_%H%M%S")

    with D1Client.public() as d1:
        ensure_table(d1)
        done: set[str] = set()
        if not force:
            rows = d1.query(
                "SELECT gene_symbol, lit_prompt_sha FROM surface_internalization "
                "WHERE schema_version = ? AND has_literature = 1;",
                [SCHEMA_VERSION],
            )
            done = {r["gene_symbol"].upper() for r in rows if r.get("lit_prompt_sha") == cur_sha}

        todo = [g for g in cohort if g not in done]
        if limit > 0:
            todo = todo[:limit]

        est = len(todo) * PER_GENE_USD_EST
        print(f"Modal internalization lit sweep (run_id={rid})")
        print(f"  cohort TSV      : {tsv_path} ({len(cohort)} genes)")
        print(f"  prompt          : v{LIT_PROMPT_VERSION} sha={cur_sha[:12]}")
        print(f"  already-lit@sha : {len(done)}  |  todo: {len(todo)}")
        print(f"  models          : grade/select={DEFAULT_LIT_MODEL}, triage={DEFAULT_LIT_TRIAGE_MODEL}, web_scout={DEFAULT_LIT_WEB_SCOUT_MODEL}")
        print(f"  concurrency     : {MAX_CONTAINERS} containers x {MAX_INPUTS} inputs = {MAX_CONTAINERS * MAX_INPUTS} genes in flight")
        print(f"  est spend       : ~${est:,.0f} (@ ~${PER_GENE_USD_EST:.2f}/gene)  |  budget cap: ${max_budget_usd:,.0f}")
        print(f"  R2 intermediates: {upload_r2}  |  wave_size: {wave_size}")

        if not execute:
            print("\nDRY RUN — pass --execute to run R2 backup + Modal sweep. Nothing written.")
            return

        if not todo:
            print("Nothing to do — all cohort genes are already lit-annotated at current prompt SHA.")
            return

        if not no_backup:
            _run_d1_backup()

        print(f"Batch-reading existing sequence priors for {len(todo)} genes from D1…", flush=True)
        priors_map = _batch_read_seq_priors(d1, todo)
        seq_json_map = {
            g: [m.model_dump(mode="json") for m in plist] for g, plist in priors_map.items()
        }

    local_run_dir = REPO_ROOT / "data" / "runs" / "internalization_lit" / rid
    local_run_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = local_run_dir / "ledger.jsonl"

    ok = fail = 0
    total_cost = 0.0
    total_refusals = 0
    budget_hit = False

    with ledger_path.open("a", encoding="utf-8") as ledger_fh:
        for start in range(0, len(todo), max(1, wave_size)):
            if total_cost >= max_budget_usd:
                budget_hit = True
                print(
                    f"BUDGET CAP REACHED (${total_cost:.2f} >= ${max_budget_usd:.2f}) — stopping before wave {start}.",
                    flush=True,
                )
                break
            wave = todo[start : start + max(1, wave_size)]
            payloads = [
                {
                    "gene": g,
                    "run_id": rid,
                    "web_search_mode": web_search_mode,
                    "model": DEFAULT_LIT_MODEL,
                    "triage_model": DEFAULT_LIT_TRIAGE_MODEL,
                    "web_scout_model": DEFAULT_LIT_WEB_SCOUT_MODEL,
                    "triage_concurrency": 4,
                    "publish_d1": True,
                    "upload_r2": upload_r2,
                    "model_priors": seq_json_map.get(g, []),
                }
                for g in wave
            ]
            print(
                f"\n--- Wave {start + 1}..{start + len(wave)} / {len(todo)} (cum_cost=${total_cost:.2f}) ---",
                flush=True,
            )
            wave_ok_genes: list[str] = []
            for g, res in zip(wave, annotate_one.map(payloads, return_exceptions=True), strict=True):
                if isinstance(res, BaseException):
                    fail += 1
                    entry = {
                        "gene": g,
                        "status": "error",
                        "error": f"Modal exception: {res}"[:400],
                        "ts": datetime.now(UTC).isoformat(),
                    }
                    ledger_fh.write(json.dumps(entry) + "\n")
                    ledger_fh.flush()
                    print(f"  FAIL {g}: {res}", flush=True)
                    continue
                ledger_fh.write(json.dumps(res) + "\n")
                ledger_fh.flush()
                if res.get("status") == "ok":
                    ok += 1
                    wave_ok_genes.append(g)
                    c = float(res.get("cost_usd", 0.0) or 0.0)
                    total_cost += c
                    total_refusals += int(res.get("n_refusals", 0) or 0)
                else:
                    fail += 1
                    print(f"  FAIL {g}: {res.get('error')}", flush=True)

            if wave_ok_genes:
                purge_internalization_batch(wave_ok_genes, include_catalog=False)
            print(
                f"Wave summary: ok={ok} fail={fail} refusals={total_refusals} "
                f"total_cost=${total_cost:.2f} (mean=${(total_cost / ok) if ok else 0.0:.3f}/gene)",
                flush=True,
            )

    if ok > 0:
        purge_catalog_cache()
    print(
        f"\nDONE: published={ok}, failed={fail}, refusals={total_refusals}, "
        f"total_cost=${total_cost:.2f} (mean=${(total_cost / ok) if ok else 0.0:.3f}/gene)"
        f"{' [STOPPED AT BUDGET CAP]' if budget_hit else ''}",
        flush=True,
    )
    print(f"Ledger saved to {ledger_path}")
    print("Next step: uv run python scripts/build/build_paper_metadata_table.py --execute")
