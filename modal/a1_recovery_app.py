"""Modal app — A1 evidence-ledger recovery sweep.

Re-tags mis-routed direct-surface methods from A2 into A1 and replays
builders+synth for each gene, at Modal fan-out. This is a *replay* (no
plan-trim-select), so ~$0.7/gene and a few minutes each — far cheaper than a
full re-annotate. Core logic:
``accessible_surfaceome.agents.surfaceome_v2.a1_recovery.recover_one``.

Reuses the deep-dive container image + ``surfaceome-env`` secret (the D1
database UUIDs are resolved from the account at runtime via
``ensure_d1_env``, so the secret only needs ANTHROPIC_API_KEY,
CLOUDFLARE_API_TOKEN, CLOUDFLARE_ACCOUNT_ID, NCBI_API_KEY).

Usage:
    # $0 preflight — confirm the secret + D1 resolution work
    modal run modal/a1_recovery_app.py::check

    # compute-only canary (NOT published) — a few genes from the manifest
    modal run modal/a1_recovery_app.py::run --manifest data/analysis/a1_recovery/manifest.json --limit 5

    # full sweep, publishing corrected records to D1
    modal run modal/a1_recovery_app.py::run --manifest data/analysis/a1_recovery/manifest.json --publish
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import modal

# Reuse the deep-dive image + secret + concurrency sizing (same container
# contract: uv-installed package, HGNC gazetteer, Anthropic OTPM sizing).
sys.path.insert(0, os.path.dirname(__file__))
from deep_dive_app import (  # noqa: E402
    MAX_CONTAINERS,
    MAX_INPUTS,
    GENE_TIMEOUT_S,
    image,
    secret,
)

_RECOVERABLE_GRADES = ("weak", "supportive_but_indirect")

app = modal.App("surfaceome-a1-recovery")
volume = modal.Volume.from_name("surfaceome-a1-recovery", create_if_missing=True)
RESULTS_MOUNT = "/results"


@app.function(image=image, secret=secret, timeout=60)
def check_secret() -> dict:
    """$0 preflight — verify the secret carries the keys we need AND that the
    D1 database UUIDs resolve from the account (ensure_d1_env)."""
    from accessible_surfaceome.env import load_env

    load_env()
    need = ["ANTHROPIC_API_KEY", "CLOUDFLARE_API_TOKEN", "CLOUDFLARE_ACCOUNT_ID"]
    missing = [k for k in need if not os.environ.get(k)]
    resolved = False
    if not missing:
        from accessible_surfaceome.agents.surfaceome_v2.a1_recovery import ensure_d1_env

        ensure_d1_env()
        resolved = bool(os.environ.get("CLOUDFLARE_D1_SURFACEOME_AGENTS_ID"))
    return {"missing": missing, "d1_resolved": resolved}


@app.function(
    image=image,
    secrets=[secret],
    volumes={RESULTS_MOUNT: volume},
    timeout=GENE_TIMEOUT_S,
    retries=modal.Retries(max_retries=2, backoff_coefficient=2.0),
    max_containers=MAX_CONTAINERS,
)
@modal.concurrent(max_inputs=MAX_INPUTS)
def recover_gene(payload: dict) -> dict:
    """Recover one gene: re-tag A2 direct-surface claims into A1, replay
    builders+synth, optionally publish. Streams the result JSON to the volume
    so a crashed driver still leaves a durable per-gene record."""
    from accessible_surfaceome.env import load_env

    load_env()
    from accessible_surfaceome.agents.surfaceome_v2.a1_recovery import recover_one

    gene = payload["gene"]
    res = recover_one(gene, publish=payload.get("publish", False))
    Path(RESULTS_MOUNT, f"{gene}.json").write_text(json.dumps(res, indent=1))
    volume.commit()
    return res


@app.local_entrypoint()
def check():
    """$0 preflight."""
    r = check_secret.remote()
    print(json.dumps(r, indent=1))
    if r["missing"]:
        raise RuntimeError(f"secret missing keys: {r['missing']}")
    if not r["d1_resolved"]:
        raise RuntimeError("D1 UUID did not resolve — check CLOUDFLARE_ACCOUNT_ID/API_TOKEN scope")
    print("OK — secret + D1 resolution good.")


@app.local_entrypoint()
def run(manifest: str, publish: bool = False, limit: int = 0, include_direct: bool = False):
    """Map the recovery over the manifest's genes.

    Defaults to the SAFE set — genes whose current grade is weak/supportive
    (re-grade can only improve). ``--include-direct`` widens to genes already
    graded direct_* (NOT recommended: the strict perm rule can downgrade them).
    ``--publish`` persists corrected records to D1; omit for a compute-only run.
    """
    m = json.loads(Path(manifest).read_text())
    targets = [
        e["gene"]
        for e in m["class1"]
        if include_direct or e["cur_grade"] in _RECOVERABLE_GRADES
    ]
    if limit:
        targets = targets[:limit]
    payloads = [{"gene": g, "publish": publish} for g in targets]
    print(f"A1 recovery sweep: {len(payloads)} genes  publish={publish}  "
          f"concurrency={MAX_CONTAINERS}x{MAX_INPUTS}")

    ok, total_cost, results = 0, 0.0, []
    # return_exceptions=True: a container timeout/OOM/preempt surfaces as one
    # failed result, not a crashed sweep.
    for r in recover_gene.map(payloads, return_exceptions=True):
        if isinstance(r, Exception):
            print(f"  ERR: {r}", flush=True)
            continue
        results.append(r)
        if r.get("status") == "ok":
            ok += 1
            total_cost += r.get("cost_usd", 0.0)
        print(f"  {r.get('gene')}: {r.get('status')} "
              f"{r.get('evidence_grade', '')} ${r.get('cost_usd', '')}", flush=True)
    print(f"\ndone: {ok}/{len(payloads)} ok  total ${total_cost:.2f}  "
          f"(published={publish})")
