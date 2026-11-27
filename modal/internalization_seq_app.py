"""Modal app — internalization sequence-prior sweep (5,333-gene deep_dive ∪ L1).

Runs the BLIND canonical-isoform sequence + DeepTMHMM E/C topology model-prior
on Modal and UPSERTs each ``InternalizationRecord`` into public D1's
``surface_internalization`` via a **fresh per-gene read-back-merge** that
preserves any existing ``literature`` track (and all 11 projected ``lit_*``
columns).

$0 preflight (verifies secrets, R2 write access, HGNC TSV, DeepTMHMM index, and
the 5,333-gene cohort manifest):

    uv run --extra modal modal run modal/internalization_seq_app.py::check_secret

Cloud-detached sweep (recommended — entire wave loop runs inside Modal so the
sweep survives laptop sleep / internet loss; model + prompt-SHA resume picks up
automatically from any prior local or cloud run):

    uv run --extra modal modal run --detach modal/internalization_seq_app.py::driver
    uv run --extra modal modal run --detach modal/internalization_seq_app.py::driver --execute

Architecture notes:
  * **Concurrent-safe with the literature sweep:** ``annotate_one`` reads back
    ``$.literature`` from D1 immediately before publishing (raising loudly if
    ``has_literature=1`` cannot be parsed), and ``driver`` defaults to
    ``reverse=True`` (Z→A) while ``internalization_lit_app::driver`` traverses
    A→Z so the two sweeps do not race on the same gene row.
  * **Hard spend guardrail:** tracks real API spend from ``usage_sink`` across
    waves (plus optional ``--prior-spent-usd``) and stops cleanly before any
    wave once ``max_budget_usd`` (default ``$500``) is reached.
  * **Durability:** every gene publishes directly to public D1; the driver
    commits ``ledger.jsonl`` and ``summary.json`` to Modal Volume
    ``surfaceome-internalization-seq`` after every wave.
"""

from __future__ import annotations

import csv
import json
import os
import sys
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import modal

from accessible_surfaceome.tools._shared.ratelimit import reserve_slot

GATE_MAX_WAIT_S = 120.0
# Default concurrency: 12 containers × 2 inputs/container = 24 genes in flight.
MAX_CONTAINERS = int(os.environ.get("INT_SEQ_MAX_CONTAINERS", "12"))
MAX_INPUTS = int(os.environ.get("INT_SEQ_MAX_INPUTS", "2"))
GENE_TIMEOUT_S = int(os.environ.get("INT_SEQ_GENE_TIMEOUT_S", str(10 * 60)))
DEFAULT_SEQ_MODEL = "claude-opus-5-5"
DEFAULT_COHORT_TSV = "data/processed/internalization/cohort_deep_dive_and_l1_2026-11-27.tsv"

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
            ".env",
            ".env.*",
            "**/wrangler.toml",
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
            # Exclude bulky local caches under data/external EXCEPT the
            # reference TSVs and DeepTMHMM 3line files needed by sequence priors:
            #   1. data/external/ncbi_gene_info/Homo_sapiens.protein_coding.with_hgnc.tsv
            #   2. data/external/hgnc/hgnc_complete_set.tsv
            #   3. data/external/deeptmhmm_surfaceome_predictions/human_canonical_non_hla/predicted_topologies.3line
            #   4. data/external/deeptmhmm_surfaceome_predictions/human_isoforms_from_afdb_non_hla/predicted_topologies.3line
            "data/external/**",
            "!data/external/hgnc",
            "!data/external/hgnc/**",
            "!data/external/ncbi_gene_info",
            "!data/external/ncbi_gene_info/Homo_sapiens.protein_coding.with_hgnc.tsv",
            "!data/external/deeptmhmm_surfaceome_predictions",
            "!data/external/deeptmhmm_surfaceome_predictions/human_canonical_non_hla",
            "!data/external/deeptmhmm_surfaceome_predictions/human_canonical_non_hla/predicted_topologies.3line",
            "!data/external/deeptmhmm_surfaceome_predictions/human_isoforms_from_afdb_non_hla",
            "!data/external/deeptmhmm_surfaceome_predictions/human_isoforms_from_afdb_non_hla/predicted_topologies.3line",
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
        "paths = ["
        "Path('/repo/data/external/ncbi_gene_info/Homo_sapiens.protein_coding.with_hgnc.tsv'), "
        "Path('/repo/data/external/deeptmhmm_surfaceome_predictions/human_canonical_non_hla/predicted_topologies.3line')"
        "]; "
        "bad = [f'{p} (size={p.stat().st_size if p.exists() else 0})' "
        "for p in paths if not p.exists() or p.stat().st_size < 1_000_000]; "
        "sys.exit(0) if not bad else sys.exit('Missing or pointer reference files: ' + ', '.join(bad))\""
    )
    .env(_IMAGE_ENV)
)
if modal.is_local():
    from accessible_surfaceome.trust_store import harden

    image = harden(image)

app = modal.App("surfaceome-internalization-seq")
volume = modal.Volume.from_name("surfaceome-internalization-seq", create_if_missing=True)
secret = modal.Secret.from_name("surfaceome-env")

VOL_MOUNT = "/internalization_seq"

_RATE_LIMIT_LAST_CALL: dict[str, float] = {}
_RATE_LIMIT_LOCK = threading.Lock()

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
    """Central non-blocking reservation gate for UniProt/HGNC/NCBI calls."""
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
    memory=512,
    timeout=60,
    secrets=[secret],
)
def secret_presence_check() -> dict[str, Any]:
    """$0 worker-side preflight: verifies secrets, R2 write, HGNC, DeepTMHMM, and cohort TSV."""
    sys.path.insert(0, "/repo/src")
    from accessible_surfaceome.agents.internalization.deeptmhmm_topology import load_index
    from accessible_surfaceome.agents.internalization.ids import resolve_hgnc_id
    from accessible_surfaceome.cloud import r2_client
    from accessible_surfaceome.env import load_env

    load_env()
    present = {k: bool((os.environ.get(k) or "").strip()) for k in _REQUIRED_SECRET_KEYS}
    pool = (os.environ.get("NCBI_API_KEYS") or "").replace(";", ",").replace(" ", ",")

    try:
        r2_write_ok = r2_client.put_object(
            key="_preflight/check_internalization_seq_r2_probe.txt",
            body=b"ok",
            content_type="text/plain",
        )
    except Exception:  # noqa: BLE001
        r2_write_ok = False

    try:
        hgnc_ok = resolve_hgnc_id("TFRC") == "HGNC:11763"
    except Exception:  # noqa: BLE001
        hgnc_ok = False

    try:
        idx = load_index()
        deeptmhmm_count = len(idx)
        deeptmhmm_tfrc_ok = "P02786" in idx
    except Exception:  # noqa: BLE001
        deeptmhmm_count = 0
        deeptmhmm_tfrc_ok = False

    cohort_tsv = Path("/repo") / DEFAULT_COHORT_TSV
    return {
        "present": present,
        "ncbi_pool_size": len([x for x in pool.split(",") if x.strip()]),
        "r2_write_ok": bool(r2_write_ok),
        "hgnc_resolve_ok": hgnc_ok,
        "deeptmhmm_count": deeptmhmm_count,
        "deeptmhmm_tfrc_ok": deeptmhmm_tfrc_ok,
        "cohort_tsv_exists": cohort_tsv.exists(),
        "cohort_tsv_bytes": cohort_tsv.stat().st_size if cohort_tsv.exists() else 0,
    }


def _get_container_runtime() -> tuple[Any, Any, Any]:
    """Lazily initialize one Anthropic client, SQLite Cache, RateLimiter, and DeepTMHMM index."""
    with _CONTAINER_INIT_LOCK:
        if "client" not in _CONTAINER_STATE:
            sys.path.insert(0, "/repo/src")
            from accessible_surfaceome.agents._support.client import get_client
            from accessible_surfaceome.agents.internalization.deeptmhmm_topology import load_index
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
            load_index()
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
    memory=1536,
    timeout=GENE_TIMEOUT_S,
    retries=modal.Retries(max_retries=2, backoff_coefficient=2.0, initial_delay=5.0),
    secrets=[secret],
    max_containers=MAX_CONTAINERS,
)
@modal.concurrent(max_inputs=MAX_INPUTS)
def annotate_one(payload: dict[str, Any]) -> dict[str, Any]:
    """Run blind canonical-isoform sequence-prior annotation for one gene in Modal
    and UPSERT into public D1 with per-gene literature read-back-merge."""
    t0 = time.monotonic()
    gene: str = payload["gene"]
    models: list[str] = list(payload.get("models") or [DEFAULT_SEQ_MODEL])
    publish_d1: bool = bool(payload.get("publish_d1", True))

    try:
        client, shared_cache, shared_limiter = _get_container_runtime()
        from accessible_surfaceome.agents._support.pricing import UsageRecord
        from accessible_surfaceome.agents.internalization.runner import annotate_model_prior
        from accessible_surfaceome.cloud.d1_client import D1Client
        from accessible_surfaceome.cloud.internalization import (
            publish_seq_record,
            read_existing_literature,
        )
        from accessible_surfaceome.tools._shared.http import CachedHTTP

        usage: list[UsageRecord] = []
        with CachedHTTP(shared_cache, shared_limiter) as http:
            rec = annotate_model_prior(
                gene,
                models=tuple(models),
                client=client,
                http=http,
                persist=False,
                canonical_only=True,
                usage_sink=usage,
            )
        cost = sum(float(getattr(u, "cost_usd", 0.0) or 0.0) for u in usage)
        preserved_lit = False

        if publish_d1:
            with D1Client.public() as d1:
                # Fresh per-gene read-back-merge right before publish so we NEVER
                # clobber curated literature (fails loud if has_literature=1 is null).
                existing_lit = read_existing_literature(d1, rec.gene_symbol)
                if existing_lit is not None:
                    rec = rec.model_copy(update={"literature": existing_lit})
                    preserved_lit = True
                publish_seq_record(
                    rec,
                    client=d1,
                    purge_catalog=False,
                    ensure_schema=False,
                    purge_edge=False,
                    max_retries=3,
                )

        grade = rec.model_priors[0].overall_grade if rec.model_priors else "?"
        return {
            "gene": rec.gene_symbol,
            "status": "ok",
            "model": models[0],
            "grade": grade,
            "preserved_lit": preserved_lit,
            "cost_usd": round(cost, 5),
            "elapsed_s": round(time.monotonic() - t0, 2),
            "published_d1": publish_d1,
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


def _load_genes_from_tsv(tsv_path: Path) -> list[str]:
    genes: list[str] = []
    with tsv_path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            sym = (row.get("gene_symbol") or row.get("symbol") or "").strip().upper()
            if sym:
                genes.append(sym)
    return list(dict.fromkeys(genes))


@app.function(
    image=image,
    cpu=0.5,
    memory=1024,
    timeout=24 * 3600,
    volumes={VOL_MOUNT: volume},
    secrets=[secret],
)
def driver(
    cohort_tsv: str = DEFAULT_COHORT_TSV,
    model: str = DEFAULT_SEQ_MODEL,
    run_id: str = "",
    max_budget_usd: float = 500.0,
    prior_spent_usd: float = 0.0,
    wave_size: int = 150,
    limit: int = 0,
    force: bool = False,
    no_backup: bool = False,
    reverse: bool = True,
    execute: bool = False,
) -> dict[str, Any]:
    """Cloud-resident wave orchestrator for the sequence-prior sweep (invoke with
    ``modal run --detach``).

    Model + prompt-SHA-aware resume skips any gene already published at ``model``
    + current prompt SHA, so this picks up seamlessly from a partial local or
    cloud run. Defaults to ``reverse=True`` (Z→A) so it can run alongside the
    A→Z literature sweep without racing on the same gene row.

    DRY-RUN by default — pass ``--execute`` to back up D1 to R2 and publish.
    """
    sys.path.insert(0, "/repo/src")
    from accessible_surfaceome.agents.internalization.model_prior import prompt_sha
    from accessible_surfaceome.agents.internalization.models import (
        MODEL_PRIOR_PROMPT_VERSION,
        SCHEMA_VERSION,
    )
    from accessible_surfaceome.agents.internalization.runner import load_prompt
    from accessible_surfaceome.cloud.d1_client import D1Client
    from accessible_surfaceome.cloud.internalization import (
        backup_table_to_r2,
        ensure_table,
        purge_catalog_cache,
        purge_internalization_batch,
    )
    from accessible_surfaceome.env import REPO_ROOT, load_env

    load_env()
    tsv_path = Path(cohort_tsv)
    if not tsv_path.is_absolute():
        tsv_path = REPO_ROOT / tsv_path
    cohort = _load_genes_from_tsv(tsv_path)
    cur_sha = prompt_sha(load_prompt())
    rid = run_id or datetime.now(UTC).strftime("int_seq_cloud_%Y%m%d_%H%M%S")
    per_gene_est = 0.042 if model == "claude-opus-5-5" else 0.055

    with D1Client.public() as d1:
        ensure_table(d1)
        existing_rows = d1.query(
            "SELECT gene_symbol, seq_model, seq_prompt_sha, has_literature "
            "FROM surface_internalization WHERE schema_version = ?;",
            [SCHEMA_VERSION],
        )
        done: set[str] = set()
        if not force:
            done = {
                str(r["gene_symbol"]).upper()
                for r in existing_rows
                if r.get("seq_prompt_sha") == cur_sha and r.get("seq_model") == model
            }
        n_with_lit = sum(1 for r in existing_rows if r.get("has_literature"))

        todo = [g for g in cohort if g not in done]
        if reverse:
            todo = list(reversed(todo))
        if limit > 0:
            todo = todo[:limit]

        est = len(todo) * per_gene_est
        remaining_budget = max(0.0, max_budget_usd - prior_spent_usd)
        print(f"Modal CLOUD internalization seq-prior driver (run_id={rid})", flush=True)
        print(f"  cohort TSV      : {tsv_path} ({len(cohort)} genes)", flush=True)
        print(f"  model / prompt  : {model}  |  v{MODEL_PRIOR_PROMPT_VERSION} sha={cur_sha[:12]}", flush=True)
        print(
            f"  already @ model : {len(done)}  |  todo: {len(todo)}  |  "
            f"existing_lit={n_with_lit} (read-back-merged)  |  reverse={reverse}",
            flush=True,
        )
        print(
            f"  concurrency     : {MAX_CONTAINERS} containers x {MAX_INPUTS} inputs = "
            f"{MAX_CONTAINERS * MAX_INPUTS} genes in flight",
            flush=True,
        )
        print(
            f"  est spend       : ~${est:,.1f} (@ ~${per_gene_est:.3f}/gene)  |  "
            f"budget cap: ${max_budget_usd:,.0f} (prior=${prior_spent_usd:.2f}, "
            f"remaining=${remaining_budget:.2f})",
            flush=True,
        )

        if not execute:
            print(
                "\nDRY RUN — pass --execute to run R2 backup + cloud sweep. Nothing written.",
                flush=True,
            )
            return {
                "run_id": rid,
                "dry_run": True,
                "cohort": len(cohort),
                "already_done": len(done),
                "todo": len(todo),
                "est_usd": round(est, 2),
                "remaining_budget_usd": round(remaining_budget, 2),
            }

        if not todo:
            print(
                f"Nothing to do — all {len(cohort)} cohort genes already at {model} @ {cur_sha[:12]}.",
                flush=True,
            )
            return {"run_id": rid, "published": 0, "failed": 0, "todo": 0, "total_cost_usd": 0.0}

        if not no_backup:
            print("Running pre-sweep R2 backup of public D1 surface_internalization…", flush=True)
            key = backup_table_to_r2(d1, label=f"pre-seq-{rid}")
            print(f"  backup complete -> r2://{key}", flush=True)

    run_dir = Path(VOL_MOUNT) / rid
    run_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = run_dir / "ledger.jsonl"

    ok = fail = 0
    total_cost = float(prior_spent_usd)
    run_cost = 0.0
    budget_hit = False

    for start in range(0, len(todo), max(1, wave_size)):
        if total_cost >= max_budget_usd:
            budget_hit = True
            print(
                f"BUDGET CAP REACHED (${total_cost:.2f} >= ${max_budget_usd:.2f}) "
                f"— stopping before wave {start}.",
                flush=True,
            )
            break
        wave = todo[start : start + max(1, wave_size)]
        payloads = [
            {
                "gene": g,
                "models": [model],
                "publish_d1": True,
            }
            for g in wave
        ]
        print(
            f"\n--- Wave {start + 1}..{start + len(wave)} / {len(todo)} "
            f"(run_cost=${run_cost:.2f}, cum_cost=${total_cost:.2f}) ---",
            flush=True,
        )
        wave_ok_genes: list[str] = []
        wave_entries: list[dict[str, Any]] = []
        for g, res in zip(wave, annotate_one.map(payloads, return_exceptions=True), strict=True):
            if isinstance(res, BaseException):
                fail += 1
                entry: dict[str, Any] = {
                    "gene": g,
                    "status": "error",
                    "error": f"Modal exception: {res}"[:400],
                    "ts": datetime.now(UTC).isoformat(),
                }
                wave_entries.append(entry)
                print(f"  FAIL {g}: {res}", flush=True)
                continue
            wave_entries.append(res)
            if res.get("status") == "ok":
                ok += 1
                wave_ok_genes.append(str(res.get("gene") or g))
                c = float(res.get("cost_usd", 0.0) or 0.0)
                run_cost += c
                total_cost += c
            else:
                fail += 1
                print(f"  FAIL {g}: {res.get('error')}", flush=True)

        with ledger_path.open("a", encoding="utf-8") as ledger_fh:
            for entry in wave_entries:
                ledger_fh.write(json.dumps(entry) + "\n")
        volume.commit()

        if wave_ok_genes:
            purge_internalization_batch(wave_ok_genes, include_catalog=False)
        print(
            f"Wave summary: ok={ok} fail={fail} run_cost=${run_cost:.2f} "
            f"cum_cost=${total_cost:.2f} (mean=${(run_cost / ok) if ok else 0.0:.4f}/gene)",
            flush=True,
        )

    if ok > 0:
        purge_catalog_cache()
    summary = {
        "run_id": rid,
        "model": model,
        "published": ok,
        "failed": fail,
        "run_cost_usd": round(run_cost, 4),
        "total_cost_usd": round(total_cost, 4),
        "mean_cost_usd": round((run_cost / ok) if ok else 0.0, 4),
        "budget_hit": budget_hit,
        "volume_ledger": f"/{rid}/ledger.jsonl",
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    volume.commit()
    print(
        f"\nDONE: published={ok}, failed={fail}, run_cost=${run_cost:.2f}, "
        f"cum_cost=${total_cost:.2f} (mean=${(run_cost / ok) if ok else 0.0:.4f}/gene)"
        f"{' [STOPPED AT BUDGET CAP]' if budget_hit else ''}",
        flush=True,
    )
    return summary


@app.local_entrypoint()
def check_secret():
    """$0 preflight: verify surfaceome-env secret, R2 write, HGNC, DeepTMHMM, and cohort TSV."""
    result = secret_presence_check.remote()
    print(json.dumps(result, indent=2))
    missing = [k for k, ok in result["present"].items() if not ok]
    if missing:
        raise RuntimeError(f"surfaceome-env secret missing keys: {missing}")
    if not result.get("r2_write_ok"):
        raise RuntimeError("R2 write probe failed — check CLOUDFLARE_API_TOKEN R2:Edit scope.")
    if not result.get("hgnc_resolve_ok"):
        raise RuntimeError("HGNC TSV resolution failed inside Modal container.")
    if not result.get("deeptmhmm_tfrc_ok") or int(result.get("deeptmhmm_count") or 0) < 1000:
        raise RuntimeError(f"DeepTMHMM index incomplete inside Modal container: {result}")
    if not result.get("cohort_tsv_exists"):
        raise RuntimeError(f"Cohort TSV missing inside Modal container: {DEFAULT_COHORT_TSV}")
    print("\n✓ Modal seq-prior preflight passed (secrets + R2 + HGNC + DeepTMHMM + cohort TSV).")
