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
import time
from pathlib import Path

import modal

# ---------------------------------------------------------------------------
# image + volume + secret
# ---------------------------------------------------------------------------

# Build the image from the repo source. uv sync installs everything in
# pyproject.toml's main dependency block (we don't need the modal extra
# inside the container — modal itself runs on the driver).
image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("git", "ca-certificates")
    .pip_install("uv>=0.5")
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
            ".runs",
            "data/raw",
            # Exclude all of data/external EXCEPT the HGNC gazetteer
            # — the competing-gene snippet filter in evidence_retrieval.py
            # needs full HGNC symbol/alias membership at query time;
            # there is no per-gene subset that suffices.
            "data/external/**",
            "!data/external/hgnc",
            "!data/external/hgnc/**",
            "data/processed",
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
    max_containers=200,  # cap fan-out so external APIs don't drown
)
@modal.concurrent(max_inputs=4)
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

    # Driver passes the file via Modal Secret; load_env still wires
    # NCBI_API_KEY etc. into the resolver.
    load_env()

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
    }


# ---------------------------------------------------------------------------
# driver entrypoints (canary + full_sweep)
# ---------------------------------------------------------------------------


def _load_and_filter(
    gene_list: str, run_id: str, no_d1: bool
) -> tuple[list[dict], int]:
    """Driver-side helper: load the TSV, filter out genes already in D1
    under this run_id. Returns (remaining_rows_as_payloads, total_loaded).
    """
    from scripts.deep_dive_sweep import load_gene_list
    rows = load_gene_list(Path(gene_list))
    total = len(rows)
    if not no_d1:
        from accessible_surfaceome.cloud.deep_dive_upload import D1DeepDiveSink
        sink = D1DeepDiveSink(run_id=run_id)
        try:
            rows = [r for r in rows if not sink.already_done(r.hgnc_symbol)]
        finally:
            sink.close()
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
):
    """Run a stratified canary and print the projected full-sweep cost."""
    from accessible_surfaceome.env import load_env
    load_env()  # driver-side: needed for D1 resume query
    from scripts.deep_dive_sweep import (
        print_canary_report, select_canary, summarize_canary, GeneRow,
    )

    payloads, total = _load_and_filter(gene_list, run_id, no_d1=False)
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
        )
        for r in results
    ]
    summary = summarize_canary(generesults, total_genes=len(rows))
    summary["wall_clock_s"] = round(elapsed, 1)
    print_canary_report(summary)


@app.local_entrypoint()
def full_sweep(
    gene_list: str,
    run_id: str,
    max_cost_per_gene_usd: float = 10.0,
    max_total_cost_usd: float = 18000.0,
):
    """Launch the full sweep over genes not yet in D1 under run_id."""
    from accessible_surfaceome.env import load_env
    load_env()

    payloads, total = _load_and_filter(gene_list, run_id, no_d1=False)
    print(
        f"full sweep: {len(payloads)}/{total} genes remaining "
        f"(resumed from D1 run_id={run_id})",
        flush=True,
    )
    for p in payloads:
        p["max_cost_per_gene_usd"] = max_cost_per_gene_usd

    running_cost = 0.0
    completed = 0
    failed = 0
    d1_failed = 0
    t0 = time.monotonic()
    for result in annotate_one.map(payloads):
        completed += 1
        running_cost += float(result.get("cost_usd") or 0.0)
        if not result.get("record_valid"):
            failed += 1
        elif not result.get("d1_mirror_ok", True):
            d1_failed += 1
        if completed % 50 == 0 or completed == len(payloads):
            elapsed = time.monotonic() - t0
            print(
                f"[{completed:4d}/{len(payloads)}] running_cost=${running_cost:.2f} "
                f"failed={failed} d1_failed={d1_failed} elapsed={elapsed:.0f}s",
                flush=True,
            )
        if running_cost > max_total_cost_usd:
            print(
                f"!! aborting: running cost ${running_cost:.2f} "
                f"> --max-total-cost-usd ${max_total_cost_usd:.2f}",
                flush=True,
            )
            break
    if d1_failed:
        print(
            f"!! d1 mirror failures: {d1_failed}/{completed - failed} "
            "(JSON files landed on the Volume; D1 rows did NOT — "
            "backfill from JSON before resuming or those genes will re-spend)",
            flush=True,
        )
    print(json.dumps({
        "completed": completed,
        "failed": failed,
        "d1_failed": d1_failed,
        "running_cost_usd": round(running_cost, 2),
        "wall_clock_s": round(time.monotonic() - t0, 1),
    }, indent=2))
