"""Modal app — surfaceome_v2 deep-dive across the candidate universe.

Run a canary (50 genes, exits with a cost projection):

    modal run modal/deep_dive_app.py::canary \\
        --gene-list data/processed/candidate_universe/candidate_universe.tsv \\
        --run-id candidate_universe_v1_sonnet_2026_05 \\
        --n 50

Launch the full sweep (only after canary review):

    modal run modal/deep_dive_app.py::full_sweep \\
        --gene-list data/processed/candidate_universe/candidate_universe.tsv \\
        --run-id candidate_universe_v1_sonnet_2026_05 \\
        --max-total-cost-usd 18000

Both entrypoints stream per-gene JSON to a Modal Volume and
best-effort-mirror to the ``surfaceome_agents`` D1 database. Run
``modal volume ls surfaceome-annotations`` after the sweep and pull files
back with ``modal volume get`` to commit them to the repo.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import modal

from accessible_surfaceome.agents._support.concurrency import (
    SONNET_OTPM_LIMIT,
    per_gene_otpm,
    resolve_gene_concurrency,
)
from accessible_surfaceome.tools._shared.ratelimit import reserve_slot

# Cap any single courtesy wait the gate hands back. Under extreme contention on
# a slow (~1 qps) host — many queued reservations plus phantom slots from
# crashed/retried workers — an uncapped reservation queue could push a worker's
# wait past the 20-minute gene timeout. Capping degrades to a brief over-rate
# instead. 120s is far above any healthy steady-state wait.
GATE_MAX_WAIT_S = 120.0

# Resolved on the driver at import time (env-tunable) and baked into the
# ``annotate_one`` Function config Modal ships to the workers. Total concurrent
# genes = MAX_CONTAINERS × MAX_INPUTS; the default is sized to keep expected
# Anthropic OTPM under the 2M/min ceiling — see the concurrency module.
MAX_CONTAINERS, MAX_INPUTS = resolve_gene_concurrency()

# ---------------------------------------------------------------------------
# image + volume + secret
# ---------------------------------------------------------------------------

# Build the image from the repo source. uv sync installs everything in
# pyproject.toml's main dependency block (we don't need the modal extra
# inside the container — modal itself runs on the driver).
image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("git", "ca-certificates")
    .pip_install("uv>=0.5", "modal==1.4.2")
    # copy=True bakes the source into the image layer (instead of
    # runtime-mounting), which lets subsequent `run_commands` see the
    # files. Required because `uv sync --frozen` needs pyproject.toml +
    # src/ on disk to build the local package.
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
            # Exclude all of data/external EXCEPT the HGNC gazetteer
            # — the competing-gene snippet filter in evidence_retrieval.py
            # needs full HGNC symbol/alias membership at query time;
            # there is no per-gene subset that suffices.
            "data/external/**",
            "!data/external/hgnc",
            "!data/external/hgnc/**",
            "data/processed",
            "node_modules",
            "viewer/node_modules",
            "viewer/.next",
            ".git",
            "*.pyc",
            "__pycache__",
        ],
    )
    .workdir("/repo")
    # Install into the system Python (NOT a venv) so Modal's function
    # runtime can import accessible_surfaceome + its deps directly.
    # `uv sync --frozen` would create /repo/.venv which Modal won't use.
    .run_commands("uv pip install --system --no-cache -e .")
    # Guard: hgnc_complete_set.tsv is LFS-tracked. If the source worktree
    # didn't hydrate LFS, add_local_dir(copy=True) silently copies the
    # ~130-byte pointer file and the competing-gene filter silently
    # degrades. Fail the build instead — the real TSV is >1 MB and starts
    # with `hgnc_id\tsymbol\tname\t...`.
    .run_commands(
        "python -c \"import sys; "
        "from pathlib import Path; "
        "p = Path('/repo/data/external/hgnc/hgnc_complete_set.tsv'); "
        "size = p.stat().st_size; "
        "head = p.read_bytes()[:32]; "
        "sys.exit(0) if size > 1_000_000 and head.startswith(b'hgnc_id\\t') "
        "else sys.exit(f'HGNC gazetteer looks like LFS pointer (size={size}, "
        "head={head!r}). Hydrate LFS in the source worktree before building.')\""
    )
    .env({"ACCESSIBLE_SURFACEOME_REPO_ROOT": "/repo"})
)

app = modal.App("surfaceome-deep-dive")
volume = modal.Volume.from_name("surfaceome-annotations", create_if_missing=True)
# Secret bundle must contain: ANTHROPIC_API_KEY, CLOUDFLARE_API_TOKEN,
# CLOUDFLARE_ACCOUNT_ID, D1 DB UUIDs (whatever D1Client reads), NCBI_API_KEY.
# Create once with `modal secret create surfaceome-env ...`.
secret = modal.Secret.from_name("surfaceome-env")

ANNOTATIONS_MOUNT = "/annotations"

# state_key -> monotonic time the most recently granted slot is scheduled to
# fire. The next slot for a key must be >= that + interval. One authoritative
# table, so the gate runs in exactly one container (max_containers=1).
_RATE_LIMIT_LAST_CALL: dict[str, float] = {}
_RATE_LIMIT_LOCK = threading.Lock()


@app.function(
    image=image,
    cpu=0.25,
    memory=256,
    timeout=30,
    max_containers=1,
)
@modal.concurrent(max_inputs=200)
def rate_limit_gate(state_key: str, interval_s: float) -> float:
    """Reservation gate for external-API courtesy limits under Modal fan-out.

    Every worker has its own process-local HTTP limiter, which is not enough
    when 100s of containers each independently obey a polite local limit while
    collectively overwhelming an upstream. This gate is the one cross-process
    coordination point. ``state_key`` is built by the shared RateLimiter and
    hashes sensitive buckets (e.g. NCBI API keys) before they leave a worker.

    It **reserves the next slot and returns the wait — it never sleeps** (via the
    shared :func:`reserve_slot`, so the algorithm can't drift from the in-process
    ``RateLimiter``). The caller (``RateLimiter.wait``) sleeps in its own worker
    process. That is the whole point of the redesign: the previous version slept
    *inside* this single ``max_inputs=1`` container, so one host's 350ms wait
    blocked every other host's and key's gate call (head-of-line blocking) and
    the gate became a hard throughput ceiling. Now each call is microseconds of
    locked dict math, every ``state_key`` is an independent schedule line, and a
    slow key never blocks a fast one. ``max_containers=1`` is still required
    (single authoritative table); ``max_inputs`` is raised so concurrent
    reservations are processed under the lock without serializing on input
    dispatch.

    The table lives only in container memory: a gate restart (deploy, crash,
    cold replacement) forgets all reservations, after which the first call per
    key gets a no-wait slot and spacing resumes. For courtesy limits this
    self-healing reset is an accepted trade-off vs. the per-call latency of a
    durable store.
    """
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
            f"rate_limit_gate: wait capped at {GATE_MAX_WAIT_S}s for "
            f"{state_key!r} — heavy contention, host is being over-rated",
            flush=True,
        )
    return wait_for


@app.function(
    image=image,
    cpu=0.25,
    memory=256,
    timeout=120,
    max_containers=2,
)
def rate_limit_worker_smoke(n: int = 3, interval_s: float = 0.2) -> dict:
    """Verify remote workers can call the central rate gate."""
    import sys

    sys.path.insert(0, "/repo/src")
    from accessible_surfaceome.tools._shared.ratelimit import (
        RateLimiter,
        set_external_rate_limit_gate,
    )

    set_external_rate_limit_gate(
        lambda state_key, interval_s: rate_limit_gate.remote(state_key, interval_s)
    )
    limiter = RateLimiter({"example.org": interval_s * 1000.0})
    t0 = time.monotonic()
    for _ in range(n):
        limiter.wait("https://example.org/resource")
    return {"n": n, "interval_s": interval_s, "elapsed_s": time.monotonic() - t0}


# Keys the full annotate + publish path reads. Missing ANTHROPIC_API_KEY is a
# hard fail; missing public-D1 UUID / ZONE_ID silently skips the public publish
# + cache purge (viewer goes stale); missing NCBI keys throttles discovery.
_REQUIRED_SECRET_KEYS = (
    "ANTHROPIC_API_KEY",
    "CLOUDFLARE_ACCOUNT_ID",
    "CLOUDFLARE_API_TOKEN",
    "CLOUDFLARE_ZONE_ID",
    "CLOUDFLARE_D1_SURFACEOME_AGENTS_ID",
    "CLOUDFLARE_D1_SURFACEOME_PUBLIC_ID",
    "NCBI_API_KEYS",
)


@app.function(
    image=image,
    cpu=0.25,
    memory=256,
    timeout=60,
    secrets=[secret],
)
def secret_presence_check() -> dict:
    """Report PRESENCE (never values) of the required keys inside a worker that
    has the ``surfaceome-env`` secret mounted — validates the actual secret, not
    the driver's local ``.env``. Returns a {key: bool} map plus the NCBI pool
    size, so a $0 run can confirm the secret before a paid canary spends."""
    import os
    import sys

    sys.path.insert(0, "/repo/src")
    from accessible_surfaceome.env import load_env

    load_env()  # the secret is injected as env vars; load_env is a harmless no-op here
    present = {k: bool((os.environ.get(k) or "").strip()) for k in _REQUIRED_SECRET_KEYS}
    pool = (os.environ.get("NCBI_API_KEYS") or "").replace(";", ",").replace(" ", ",")

    # Actually exercise R2 WRITE access — not just key presence. The token can
    # carry CLOUDFLARE_API_TOKEN yet lack the "Workers R2 Storage: Edit" scope,
    # which only surfaces as a 403 mid-run that silently drops heavy genes' full
    # audit blob (the slim D1 record still publishes). A fixed probe key,
    # overwritten each run, needs no cleanup.
    try:
        from accessible_surfaceome.cloud import r2_client

        r2_write_ok = r2_client.put_object(
            key="_preflight/check_secret_probe.txt",
            body=b"ok",
            content_type="text/plain",
        )
    except Exception:  # noqa: BLE001 — a preflight probe must never raise
        r2_write_ok = False

    return {
        "present": present,
        "ncbi_pool_size": len([x for x in pool.split(",") if x.strip()]),
        "r2_write_ok": bool(r2_write_ok),
    }


@app.local_entrypoint()
def check_secret():
    """$0 preflight: confirm the surfaceome-env secret carries every key the
    annotate+publish path needs, before launching a paid canary."""
    result = secret_presence_check.remote()
    print(json.dumps(result, indent=2))
    missing = [k for k, ok in result["present"].items() if not ok]
    if missing:
        print(f"\n!! MISSING from the surfaceome-env secret: {', '.join(missing)}")
        raise RuntimeError(f"secret incomplete — missing {missing}")
    print("\n✓ all required keys present in the surfaceome-env secret")
    if result.get("r2_write_ok"):
        print("✓ R2 write OK (heavy-gene audit-blob spillover will land)")
    else:
        # Non-fatal: genes still succeed, but oversized intermediates can't spill
        # to R2 → the full audit blob is lost for heavy genes.
        print(
            "!! R2 write FAILED — CLOUDFLARE_API_TOKEN likely lacks the "
            "'Workers R2 Storage: Edit' scope (or the bucket is missing). "
            "Non-blocking, but fix before a long run or heavy genes silently "
            "drop their full audit blob."
        )


# ---------------------------------------------------------------------------
# per-gene worker
# ---------------------------------------------------------------------------


@app.function(
    image=image,
    cpu=0.5,
    memory=2048,
    timeout=20 * 60,
    retries=modal.Retries(max_retries=2, backoff_coefficient=2.0),
    volumes={ANNOTATIONS_MOUNT: volume},
    secrets=[secret],
    # Sized to keep expected Anthropic OTPM under the 2M/min ceiling, not to
    # max out raw fan-out (env-tunable; see concurrency module). Total
    # concurrent genes = MAX_CONTAINERS × MAX_INPUTS.
    max_containers=MAX_CONTAINERS,
)
@modal.concurrent(max_inputs=MAX_INPUTS)
def annotate_one(payload: dict) -> dict:
    """Annotate one gene. ``payload`` carries the GeneRow fields plus
    ``run_id`` and ``max_cost_per_gene_usd``. Always returns a dict so
    Modal can collect results even when annotation fails.
    """
    # Imports inside the function so cold-start cost is per-container,
    # not per-invocation when @modal.concurrent reuses a warm worker.
    import sys
    sys.path.insert(0, "/repo/src")
    from accessible_surfaceome.cloud.d1_client import D1Client
    from accessible_surfaceome.cloud.deep_dive_upload import D1DeepDiveSink
    from accessible_surfaceome.env import load_env
    from accessible_surfaceome.tools._shared.ratelimit import (
        set_external_rate_limit_gate,
    )

    # Driver passes the file via Modal Secret; load_env still wires
    # NCBI_API_KEY etc. into the resolver.
    load_env()
    set_external_rate_limit_gate(
        lambda state_key, interval_s: rate_limit_gate.remote(state_key, interval_s)
    )

    run_id: str = payload["run_id"]
    max_cost = float(payload.get("max_cost_per_gene_usd", 10.0))

    # Re-import the shared helper. We deliberately keep a fresh D1Client
    # + sink per container so connection state doesn't outlive the run.
    from scripts.deep_dive_sweep import GeneRow, annotate_one as run_one

    row = GeneRow(
        hgnc_id=payload["hgnc_id"],
        hgnc_symbol=payload["hgnc_symbol"],
        sonnet_verdict=payload.get("sonnet_verdict", ""),
    )
    with D1Client() as d1, D1DeepDiveSink(run_id=run_id, client=d1) as sink:
        result = run_one(
            row,
            run_id=run_id,
            sink=sink,
            annotations_dir=Path(ANNOTATIONS_MOUNT),
            max_cost_per_gene_usd=max_cost,
        )
    # Always commit the Volume so the JSON file is visible to other
    # containers (and to subsequent `modal volume get`).
    volume.commit()
    return {
        "hgnc_id": result.hgnc_id,
        "hgnc_symbol": result.hgnc_symbol,
        "cost_usd": result.cost_usd,
        "latency_s": result.latency_s,
        "blocks_used": result.blocks_used,
        "error": result.error,
        "record_valid": result.record_valid,
        "d1_mirror_ok": result.d1_mirror_ok,
        "search_log_count": result.search_log_count,
        "cost_capped": result.cost_capped,
    }


# ---------------------------------------------------------------------------
# driver entrypoints (canary + full_sweep)
# ---------------------------------------------------------------------------


def _log_concurrency_plan() -> None:
    """Print the resolved fan-out + projected Anthropic OTPM vs the ceiling.

    Observability for the binding constraint: if projected OTPM is near 100%,
    expect the backoff loop to engage; dial ``SURFACEOME_MAX_CONTAINERS`` down
    (or refine ``SURFACEOME_PER_GENE_OTPM``) before a long run.
    """
    concurrency = MAX_CONTAINERS * MAX_INPUTS
    projected = concurrency * per_gene_otpm()
    print(
        f"concurrency: {concurrency} genes in flight "
        f"({MAX_CONTAINERS} containers × {MAX_INPUTS} inputs/container); "
        f"projected OTPM ≈ {projected / 1e6:.2f}M / {SONNET_OTPM_LIMIT / 1e6:.0f}M "
        f"({100 * projected / SONNET_OTPM_LIMIT:.0f}% — backoff absorbs bursts)",
        flush=True,
    )


def _load_and_filter(
    gene_list: str,
    run_id: str,
    no_d1: bool,
    include_quarantined: bool = False,
    force: bool = False,
) -> tuple[list[dict], int]:
    """Driver-side helper: load the TSV, then (unless ``force``) drop genes
    already completed **at the current schema_version in any run_id** plus genes
    quarantined for manual review (over-cap aborts).

    The schema-aware *global* dedup is what makes the incremental rollout safe:
    re-launching with any batch tag never re-spends on a successful current-
    schema gene, and a schema bump re-opens stale genes. ``force`` bypasses the
    dedup. Returns (remaining_rows_as_payloads, total_loaded).
    """
    from scripts.deep_dive_sweep import load_gene_list
    rows = load_gene_list(Path(gene_list))
    total = len(rows)
    if not no_d1:
        from accessible_surfaceome.cloud.d1_client import D1Client
        from accessible_surfaceome.cloud.deep_dive_upload import genes_done_at_schema
        from accessible_surfaceome.cloud.intermediates import fetch_quarantined_genes
        from accessible_surfaceome.tools._shared.models import SurfaceomeRecord

        schema = SurfaceomeRecord.model_fields["schema_version"].default
        with D1Client() as d1:
            if force:
                print(
                    "--force: skipping schema-aware dedup — already-complete "
                    "genes WILL be re-run (and re-spend).",
                    flush=True,
                )
            else:
                done = genes_done_at_schema(d1, schema)
                before = len(rows)
                rows = [r for r in rows if r.hgnc_symbol not in done]
                print(
                    f"resume: {before - len(rows)} gene(s) already complete at "
                    f"schema {schema} (any run_id) — skipping; {len(rows)} remain",
                    flush=True,
                )
            if not include_quarantined:
                # Over-cap genes already burned their budget; never auto-resume.
                # Surfaced for manual review (raise the ceiling deliberately,
                # then re-run with --include-quarantined).
                try:
                    quarantined = fetch_quarantined_genes(d1, cohort_run_id=run_id)
                except Exception as exc:  # noqa: BLE001 — never block dispatch
                    print(
                        f"warning: quarantine lookup failed ({exc}); proceeding "
                        "without quarantine filter",
                        flush=True,
                    )
                    quarantined = set()
                if quarantined:
                    before = len(rows)
                    rows = [r for r in rows if r.hgnc_symbol not in quarantined]
                    preview = ", ".join(sorted(quarantined)[:20])
                    more = " …" if len(quarantined) > 20 else ""
                    print(
                        f"quarantine: skipping {before - len(rows)} over-cap "
                        f"gene(s) flagged for MANUAL REVIEW: {preview}{more}",
                        flush=True,
                    )
    payloads = [
        {
            "hgnc_id": r.hgnc_id,
            "hgnc_symbol": r.hgnc_symbol,
            "sonnet_verdict": r.sonnet_verdict,
            "run_id": run_id,
        }
        for r in rows
    ]
    return payloads, total


@app.local_entrypoint()
def canary(
    gene_list: str,
    run_id: str,
    n: int = 50,
    max_cost_per_gene_usd: float = 10.0,
    force: bool = False,
):
    """Run a stratified canary and print the projected full-sweep cost.

    ``force`` bypasses the schema-aware global dedup (re-runs already-complete
    genes — re-spends).
    """
    from accessible_surfaceome.env import load_env
    load_env()  # driver-side: needed for D1 resume query
    _log_concurrency_plan()
    from scripts.deep_dive_sweep import (
        check_search_log_populated,
        print_canary_report,
        select_canary,
        summarize_canary,
        GeneRow,
    )

    payloads, total = _load_and_filter(gene_list, run_id, no_d1=False, force=force)
    rows = [
        GeneRow(hgnc_id=p["hgnc_id"], hgnc_symbol=p["hgnc_symbol"],
                sonnet_verdict=p.get("sonnet_verdict", ""))
        for p in payloads
    ]
    canary_rows = select_canary(rows, n)
    print(f"canary: {len(canary_rows)}/{len(rows)} genes "
          f"(stratified by sonnet_verdict)", flush=True)
    canary_payloads = [
        {**{k: getattr(r, k) for k in ("hgnc_id", "hgnc_symbol", "sonnet_verdict")},
         "run_id": run_id, "max_cost_per_gene_usd": max_cost_per_gene_usd}
        for r in canary_rows
    ]
    t0 = time.monotonic()
    results = list(annotate_one.map(canary_payloads))
    elapsed = time.monotonic() - t0
    # Reuse local summarizer (operates on GeneResult-shaped dicts here).
    from scripts.deep_dive_sweep import GeneResult
    generesults = [
        GeneResult(
            hgnc_id=r["hgnc_id"], hgnc_symbol=r["hgnc_symbol"],
            cost_usd=r["cost_usd"], latency_s=r["latency_s"],
            blocks_used=r["blocks_used"], error=r["error"],
            record_valid=r["record_valid"],
            d1_mirror_ok=r.get("d1_mirror_ok", True),
            search_log_count=r.get("search_log_count", 0),
            cost_capped=r.get("cost_capped", False),
        )
        for r in results
    ]
    summary = summarize_canary(generesults, total_genes=len(rows))
    summary["wall_clock_s"] = round(elapsed, 1)
    print_canary_report(summary)
    err = check_search_log_populated(generesults)
    if err is not None:
        # Raising rather than sys.exit so Modal surfaces this in the run UI.
        raise RuntimeError(err)


@app.local_entrypoint()
def rate_limit_smoke(n: int = 5, interval_s: float = 0.2, worker: bool = True):
    """Exercise the centralized Modal rate gate without running annotations."""
    if worker:
        result = rate_limit_worker_smoke.remote(n, interval_s)
    else:
        waits = [rate_limit_gate.remote("smoke", interval_s) for _ in range(n)]
        result = {"n": n, "interval_s": interval_s, "waits": waits}
    print(json.dumps(result, indent=2))


@app.local_entrypoint()
def full_sweep(
    gene_list: str,
    run_id: str,
    max_cost_per_gene_usd: float = 10.0,
    max_total_cost_usd: float = 18000.0,
    chunk_size: int = 200,
    include_quarantined: bool = False,
    limit: int = 0,
    force: bool = False,
):
    """Launch the sweep over genes not yet complete at the current schema.

    Genes are dispatched in chunks of ``chunk_size`` (default 200, which
    comfortably covers the in-flight concurrency of
    ``MAX_CONTAINERS × MAX_INPUTS``). Each chunk is
    drained fully before the next is submitted, with a running-cost
    check between chunks. This makes ``--max-total-cost-usd`` a real
    cap with bounded overshoot — at most ``chunk_size ×
    max_cost_per_gene_usd`` over the cap. ``annotate_one.map()`` on the
    full payload list would otherwise spawn every Modal Function
    eagerly, and breaking out of the iterator wouldn't cancel
    in-flight containers; the chunked path makes the cap actually stop
    new work from being launched.

    ``--limit N`` processes at most N of the remaining genes this launch —
    the batch-size knob for an incremental rollout (``--limit 25`` today,
    ``--limit 100`` tonight, ``--limit 1000`` tomorrow, then no limit). The
    schema-aware global dedup means each launch automatically picks up where
    the last left off, so you just bump ``--limit`` and keep the same run_id.
    ``--force`` bypasses the dedup (re-runs already-complete genes).
    """
    from accessible_surfaceome.env import load_env
    load_env()
    _log_concurrency_plan()

    payloads, total = _load_and_filter(
        gene_list,
        run_id,
        no_d1=False,
        include_quarantined=include_quarantined,
        force=force,
    )
    if limit and limit > 0 and len(payloads) > limit:
        print(
            f"--limit {limit}: dispatching the first {limit} of {len(payloads)} "
            "remaining genes this launch (re-run to continue the rollout).",
            flush=True,
        )
        payloads = payloads[:limit]
    print(
        f"full sweep: {len(payloads)}/{total} genes this launch "
        f"(resumed from D1 run_id={run_id}); chunk_size={chunk_size}",
        flush=True,
    )
    for p in payloads:
        p["max_cost_per_gene_usd"] = max_cost_per_gene_usd

    running_cost = 0.0
    completed = 0
    failed = 0
    d1_failed = 0
    cost_capped_count = 0
    aborted = False
    t0 = time.monotonic()
    for chunk_start in range(0, len(payloads), chunk_size):
        chunk = payloads[chunk_start : chunk_start + chunk_size]
        for result in annotate_one.map(chunk):
            completed += 1
            running_cost += float(result.get("cost_usd") or 0.0)
            if not result.get("record_valid"):
                failed += 1
            else:
                if not result.get("d1_mirror_ok", True):
                    d1_failed += 1
                if result.get("cost_capped"):
                    cost_capped_count += 1
            if completed % 50 == 0 or completed == len(payloads):
                elapsed = time.monotonic() - t0
                print(
                    f"[{completed:4d}/{len(payloads)}] running_cost=${running_cost:.2f} "
                    f"failed={failed} d1_failed={d1_failed} "
                    f"cost_capped={cost_capped_count} elapsed={elapsed:.0f}s",
                    flush=True,
                )
        if running_cost > max_total_cost_usd:
            remaining = len(payloads) - completed
            print(
                f"!! aborting between chunks: running cost ${running_cost:.2f} "
                f"> --max-total-cost-usd ${max_total_cost_usd:.2f}; "
                f"{remaining} genes NOT launched (safe — no spend).",
                flush=True,
            )
            aborted = True
            break
    if d1_failed:
        print(
            f"!! d1 mirror failures: {d1_failed}/{completed - failed} "
            "(JSON files landed on the Volume; D1 rows did NOT — "
            "backfill from JSON before resuming or those genes will re-spend)",
            flush=True,
        )
    if cost_capped_count:
        print(
            f"!! cost cap hit on {cost_capped_count} genes — records "
            "retained on the Volume + in D1; review before resuming.",
            flush=True,
        )
    print(json.dumps({
        "completed": completed,
        "failed": failed,
        "d1_failed": d1_failed,
        "cost_capped": cost_capped_count,
        "running_cost_usd": round(running_cost, 2),
        "wall_clock_s": round(time.monotonic() - t0, 1),
        "aborted_by_cost_cap": aborted,
    }, indent=2))
