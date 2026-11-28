"""Modal app — L1 internal tag-site literature enrichment sweep (607 members).

Mirrors ``modal/internalization_lit_app.py``:
  * Central ``rate_limit_gate`` (``max_containers=1``) coordinating EuropePMC,
    PubTator, NCBI, UniProt, Unpaywall, and DataCite across workers.
  * Org-global Anthropic ephemeral prompt caching across parallel containers.
  * 3-way durability & resume:
      1. Public D1 ``tag_site_public`` + ``tag_site_gene_public`` (additive
         ``literature_enriched`` provenance + prompt-SHA-aware member resume).
      2. Cloudflare R2 ``tag_site_lit_intermediates/{CANDIDATE_ID}/latest.json.gz``
         + ``{run_id}.json.gz`` for incremental ``--add-papers`` and local
         bioRxiv 429 rescue.
      3. Modal Volume ``surfaceome-tag-site-lit`` (per-member gzipped bundle).

$0 preflight:
    uv run --extra modal modal run modal/tag_site_lit_app.py::check_secret

5-member canary (writes to Modal Volume + R2 only unless ``--publish-d1``):
    uv run --extra modal modal run modal/tag_site_lit_app.py::canary

Full 607-member sweep (DRY-RUN by default; pass ``--execute`` to write):
    uv run --extra modal modal run modal/tag_site_lit_app.py::full_sweep
    uv run --extra modal modal run modal/tag_site_lit_app.py::full_sweep --execute
"""

from __future__ import annotations

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
# 10 containers × 2 inputs/container = 20 members in flight; keeps Cloudflare D1
# free of 429 bursts while rate_limit_gate enforces the global 350 ms EBI cap.
MAX_CONTAINERS = int(os.environ.get("TAG_SITE_LIT_MAX_CONTAINERS", "10"))
MAX_INPUTS = int(os.environ.get("TAG_SITE_LIT_MAX_INPUTS", "2"))
MEMBER_TIMEOUT_S = int(os.environ.get("TAG_SITE_LIT_MEMBER_TIMEOUT_S", str(20 * 60)))
PER_MEMBER_USD_EST = 0.15

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
            "data/external/**",
            "!data/external/hgnc",
            "!data/external/hgnc/**",
            "!data/external/ncbi_gene_info",
            "!data/external/ncbi_gene_info/Homo_sapiens.protein_coding.with_hgnc.tsv",
            "data/processed/**",
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
        "tsv = Path('/repo/data/tag_sites/l1_internal_members.tsv'); "
        "sys.exit(0) if tsv.exists() and tsv.stat().st_size > 50_000 "
        "else sys.exit(f'Missing l1_internal_members.tsv at {tsv}')\""
    )
    .env(_IMAGE_ENV)
)
if modal.is_local():
    from accessible_surfaceome.trust_store import harden

    image = harden(image)

app = modal.App("surfaceome-tag-site-lit")
volume = modal.Volume.from_name("surfaceome-tag-site-lit", create_if_missing=True)
secret = modal.Secret.from_name("surfaceome-env")

VOL_MOUNT = "/tag_site_lit"

_RATE_LIMIT_LAST_CALL: dict[str, float] = {}
_RATE_LIMIT_LOCK = threading.Lock()
_CONTAINER_INIT_LOCK = threading.Lock()
_CONTAINER_STATE: dict[str, Any] = {}

_REQUIRED_SECRET_KEYS = (
    "ANTHROPIC_API_KEY",
    "CLOUDFLARE_ACCOUNT_ID",
    "CLOUDFLARE_API_TOKEN",
    "CLOUDFLARE_D1_SURFACEOME_AGENTS_ID",
    "CLOUDFLARE_D1_SURFACEOME_PUBLIC_ID",
    "NCBI_API_KEYS",
)


def _is_retryable_modal_error(exc: BaseException) -> bool:
    """True for transient upstream failures Modal should retry with backoff."""
    msg = str(exc)
    if "EuropePMC discovery degraded" in msg:
        return True
    name = type(exc).__name__
    if name in {"D1Error", "ReadTimeout", "ConnectTimeout", "RemoteProtocolError", "ConnectError"}:
        return True
    if "500" in msg or "502" in msg or "503" in msg or "504" in msg or "Connection reset" in msg:
        return True
    return False


@app.function(
    image=image,
    cpu=0.25,
    memory=256,
    timeout=30,
    max_containers=1,
)
@modal.concurrent(max_inputs=200)
def rate_limit_gate(state_key: str, interval_s: float) -> float:
    """Central non-blocking reservation gate for EuropePMC/PubTator/NCBI/UniProt."""
    with _RATE_LIMIT_LOCK:
        return reserve_slot(
            _RATE_LIMIT_LAST_CALL,
            state_key,
            float(interval_s),
            now=time.monotonic(),
            max_wait_s=GATE_MAX_WAIT_S,
        )


@app.function(
    image=image,
    cpu=0.25,
    memory=256,
    timeout=60,
    secrets=[secret],
)
def secret_presence_check(
    members_tsv: str = "data/tag_sites/l1_internal_members.tsv",
) -> dict[str, Any]:
    """$0 preflight: verify secret keys, R2 write access, and member TSV resolution."""
    sys.path.insert(0, "/repo/src")
    from accessible_surfaceome.agents.tag_site.member_frames import load_members
    from accessible_surfaceome.cloud import r2_client
    from accessible_surfaceome.env import load_env

    load_env()
    present = {k: bool((os.environ.get(k) or "").strip()) for k in _REQUIRED_SECRET_KEYS}
    try:
        r2_write_ok = r2_client.put_object(
            key="_preflight/check_tag_site_r2_probe.txt",
            body=b"ok",
            content_type="text/plain",
        )
    except Exception:  # noqa: BLE001
        r2_write_ok = False
    tsv_path = Path("/repo") / members_tsv
    members = load_members(tsv_path)
    sys.path.insert(0, "/repo/scripts")
    import enrich_tag_site_lit as enrich  # type: ignore[import-not-found]
    from accessible_surfaceome.cloud.d1_client import D1Client

    with D1Client.public() as pub:
        accs = enrich.canonical_accessions(members, pub=pub)
        frames, _, unresolved = enrich.resolve_frames(members, pub=pub, accessions=accs)
    return {
        "present": present,
        "r2_write_ok": bool(r2_write_ok),
        "members_tsv": members_tsv,
        "n_members": len(members),
        "n_topology_resolved": len(frames),
        "n_topology_unresolved": len(unresolved),
        "unresolved_sample": [m.candidate_id for m in unresolved[:10]],
    }


def _get_container_runtime() -> tuple[Any, Any, Any]:
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
    timeout=MEMBER_TIMEOUT_S,
    retries=modal.Retries(max_retries=2, backoff_coefficient=2.0, initial_delay=10.0),
    volumes={VOL_MOUNT: volume},
    secrets=[secret],
    max_containers=MAX_CONTAINERS,
)
@modal.concurrent(max_inputs=MAX_INPUTS)
def enrich_one(payload: dict[str, Any]) -> dict[str, Any]:
    """Run tag-site literature enrichment for one L1 internal member on Modal."""
    t0 = time.monotonic()
    candidate_id: str = payload["candidate_id"]
    gene_symbol: str = payload["gene_symbol"]
    run_id: str = payload["run_id"]
    run_series: str = payload.get("run_series", "literature_enriched_v2")
    publish_d1: bool = bool(payload.get("publish_d1", False))
    upload_r2: bool = bool(payload.get("upload_r2", True))
    ws_mode: str = payload.get("web_search_mode", "adaptive")
    model: str = payload["model"]
    triage_model: str = payload["triage_model"]
    web_scout_model: str = payload["web_scout_model"]

    try:
        client, shared_cache, shared_limiter = _get_container_runtime()
        sys.path.insert(0, "/repo/scripts")
        import enrich_tag_site_lit as enrich  # type: ignore[import-not-found]
        from accessible_surfaceome.agents.tag_site.intermediates import (
            build_intermediates_payload,
            has_missed_preprint_body,
            save_intermediates_local,
            upload_intermediates_r2,
        )
        from accessible_surfaceome.agents.tag_site.member_frames import (
            load_members,
            loop_inventory,
        )
        from accessible_surfaceome.agents.tag_site.ortholog_frames import (
            build_aliases,
            fetch_rodent_ortholog_frames,
            fetch_uniprot_names_cached,
        )
        from accessible_surfaceome.agents.tag_site.runner import (
            run_tag_site_agent,
            to_viewer_sites,
        )
        from accessible_surfaceome.cloud.d1_client import D1Client
        from accessible_surfaceome.cloud.tag_site_genes import publish_gene_rows
        from accessible_surfaceome.cloud.tag_sites import publish_tag_sites
        from accessible_surfaceome.tools._shared.http import CachedHTTP

        members_tsv = payload.get("members_tsv", "data/tag_sites/l1_internal_members.tsv")
        members = [
            m
            for m in load_members(Path("/repo") / members_tsv)
            if m.candidate_id == candidate_id
        ]
        if not members:
            return {"candidate_id": candidate_id, "gene_symbol": gene_symbol, "status": "error", "error": "member not found"}
        m = members[0]

        independent: bool = bool(payload.get("independent", True))
        with D1Client.public() as pub:
            accs = enrich.canonical_accessions([m], pub=pub)
            frames, alternates, unresolved = enrich.resolve_frames([m], pub=pub, accessions=accs)
            if unresolved or m.candidate_id not in frames or m.candidate_id not in accs:
                return {
                    "candidate_id": candidate_id,
                    "gene_symbol": gene_symbol,
                    "status": "skipped",
                    "error": "unresolved topology_public sha256",
                }
            fr = frames[m.candidate_id]
            base_acc = accs[m.candidate_id]
            if independent:
                # Independent fresh evaluation: confirms/refutes existing
                # literature sites and avoids dropping clips near prior sites.
                clips, seen, covered = [], set(), set()
            else:
                with D1Client() as pri:
                    clips, seen, covered = enrich.prior_state(m.gene_symbol, pri=pri, pub=pub)

            with CachedHTTP(shared_cache, shared_limiter) as http:
                name, cands, sp_end = fetch_uniprot_names_cached(base_acc, http=http)
                aliases = build_aliases("", name, cands)
                alts = list(alternates[m.candidate_id])
                existing_seqs = {f.sequence for f in alts if f.sequence}
                alts.extend(
                    fetch_rodent_ortholog_frames(
                        m.gene_symbol, http=http, exclude_sequences=existing_seqs
                    )
                )
                inv = loop_inventory(m, fr.topology)
                usage: list[Any] = []
                inter: dict[str, Any] = {}
                result = run_tag_site_agent(
                    client=client,
                    http=http,
                    usage_sink=usage,
                    intermediates=inter,
                    gene_symbol=m.gene_symbol,
                    protein_name=name,
                    uniprot_accession=base_acc,
                    aliases=aliases,
                    sequence=fr.sequence,
                    topology=fr.topology,
                    sp_end=sp_end,
                    mode="production",
                    loop_inventory=inv,
                    prior_clips=clips,
                    seen_keys=seen,
                    covered_junctions=covered,
                    numbered_against=fr.numbered_against,
                    alternate_frames=alts,
                    frame_label="member",
                    select_max_batches=4,
                    faceted_discovery=True,
                    web_search_mode=ws_mode,  # type: ignore[arg-type]
                    model=model,
                    triage_model=triage_model,
                    web_scout_model=web_scout_model,
                    triage_concurrency=4,
                    follow_construct_refs=True,
                )

            sites = to_viewer_sites(
                result,
                uniprot_acc=base_acc,
                provenance=enrich.ENRICHED_PROVENANCE,
                candidate_id=m.candidate_id,
                library=m.library,
                numbered_against=fr.numbered_against,
                topology=fr.topology,
            )
            bundle = build_intermediates_payload(
                member_key=m.candidate_id,
                gene_symbol=m.gene_symbol,
                candidate_id=m.candidate_id,
                uniprot_acc=base_acc,
                run_id=run_id,
                run_series=run_series,
                prompt_version=getattr(result, "prompt_version", "") or "",
                prompt_sha=getattr(result, "prompt_sha", "") or "",
                runner_intermediates=inter,
                viewer_sites=sites,
                usage=usage,
                result_dump=result.model_dump(mode="json"),
            )
            save_intermediates_local(
                Path(VOL_MOUNT) / run_id / "intermediates" / f"{m.candidate_id}.json.gz",
                bundle,
            )
            r2_ok = False
            if upload_r2:
                r2_ok, _ = upload_intermediates_r2(
                    bundle, member_key=m.candidate_id, run_id=run_id
                )
            if publish_d1:
                publish_tag_sites(
                    {
                        "has_data": bool(sites),
                        "gene_symbol": m.gene_symbol,
                        "uniprot_acc": base_acc,
                        "sites": sites,
                    },
                    tag_sites_version=run_series,
                    client=pub,
                    provenances=[enrich.ENRICHED_PROVENANCE],
                    candidate_id=m.candidate_id,
                )
                srow = enrich.searched_row(
                    m,
                    result,
                    sites,
                    base_acc=base_acc,
                    run_series=run_series,
                    n_papers=inter.get("n_papers"),
                )
                if srow is not None:
                    publish_gene_rows([srow], client=pub)

        volume.commit()
        ec_pinned = [
            s
            for s in sites
            if s.get("insert_after_residue") is not None
            and s.get("site_kind") == "internal"
            and bool(s.get("extracellular"))
        ]
        pinned = sorted({int(s["insert_after_residue"]) for s in ec_pinned})
        validated_pinned = sorted(
            {
                int(s["insert_after_residue"])
                for s in ec_pinned
                if s.get("position_evidence") == "validated"
            }
        )
        return {
            "candidate_id": candidate_id,
            "gene_symbol": gene_symbol,
            "status": "ok",
            "outcome": inter.get("outcome"),
            "n_papers": inter.get("n_papers", 0),
            "n_papers_fetched": inter.get("n_papers_fetched", 0),
            "n_clips": inter.get("n_clips", 0),
            "n_sites": len(sites),
            "pinned_residues": pinned,
            "validated_pinned_residues": validated_pinned,
            "n_refusals": inter.get("n_refusals", 0),
            "web_search_used": bool(inter.get("web_search_used", False)),
            "missed_preprint_body": has_missed_preprint_body(bundle),
            "cost_usd": bundle["summary"]["cost_usd"],
            "uploaded_r2": r2_ok,
            "published_d1": publish_d1,
            "elapsed_s": round(time.monotonic() - t0, 2),
            "ts": datetime.now(UTC).isoformat(),
        }
    except Exception as exc:  # noqa: BLE001
        if _is_retryable_modal_error(exc):
            # Re-raise so Modal's configured Retries(max_retries=2) handles
            # transient EuropePMC / D1 blips before full_sweep records a miss.
            raise
        return {
            "candidate_id": candidate_id,
            "gene_symbol": gene_symbol,
            "status": "error",
            "error": str(exc)[:400],
            "elapsed_s": round(time.monotonic() - t0, 2),
            "ts": datetime.now(UTC).isoformat(),
        }


@app.function(
    image=image,
    secrets=[secret],
    volumes={VOL_MOUNT: volume},
    timeout=12 * 3600,
    max_containers=1,
)
def sweep_driver(
    members_tsv: str = "data/tag_sites/expanded_multipass_members.tsv",
    run_id: str = "",
    run_series: str = "literature_enriched_v2",
    web_search_mode: str = "adaptive",
    max_budget_usd: float = 350.0,
    wave_size: int = 100,
    limit: int = 0,
    force: bool = False,
    upload_r2: bool = True,
    retry_errors: bool = True,
) -> dict[str, Any]:
    """Detached cloud orchestrator: runs the remaining sweep entirely on Modal.

    Survives laptop sleep / offline travel when launched via ``modal deploy`` +
    ``.spawn()`` or ``modal run --detach modal/tag_site_lit_app.py::sweep_driver``.
    """
    from accessible_surfaceome.agents.tag_site.member_frames import load_members
    from accessible_surfaceome.agents.tag_site.prompt import (
        TAG_SITE_PROMPT_VERSION,
        prompt_sha,
    )
    from accessible_surfaceome.agents.tag_site.runner import (
        DEFAULT_TAG_SITE_MODEL,
        DEFAULT_TAG_SITE_TRIAGE_MODEL,
        DEFAULT_TAG_SITE_WEB_SCOUT_MODEL,
    )
    from accessible_surfaceome.cloud.d1_client import D1Client
    from accessible_surfaceome.cloud.tag_site_genes import searched_members

    rel_tsv = members_tsv.lstrip("/")
    tsv_path = Path("/repo") / rel_tsv
    members = load_members(tsv_path)
    cur_sha = prompt_sha()
    rid = run_id or datetime.now(UTC).strftime("tag_site_l1_modal_%Y%m%d_%H%M%S")

    done: set[tuple[str, str]] = set()
    if not force:
        with D1Client.public() as pub:
            done = searched_members(pub, run_series=run_series, prompt_sha=cur_sha)

    todo = [m for m in members if (m.gene_symbol, m.candidate_id) not in done]
    if limit > 0:
        todo = todo[:limit]

    print(f"Detached Modal tag-site sweep (run_id={rid})", flush=True)
    print(f"  members TSV     : {rel_tsv} ({len(members)} members)", flush=True)
    print(f"  prompt          : v{TAG_SITE_PROMPT_VERSION} sha={cur_sha[:12]}  series={run_series}", flush=True)
    print(f"  already@sha     : {len(done)}  |  todo: {len(todo)}", flush=True)
    print(f"  models          : synth/select={DEFAULT_TAG_SITE_MODEL}, triage/scout={DEFAULT_TAG_SITE_TRIAGE_MODEL}", flush=True)
    print(f"  budget cap      : ${max_budget_usd:,.2f}", flush=True)

    vol_run_dir = Path(VOL_MOUNT) / rid
    vol_run_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = vol_run_dir / "driver_ledger.jsonl"

    ok = fail = skipped = 0
    total_cost = 0.0
    missed_preprint_members: list[str] = []
    failed_members: list[Any] = []

    def _run_wave(batch: list[Any], label: str) -> list[Any]:
        nonlocal ok, fail, skipped, total_cost
        payloads = [
            {
                "candidate_id": m.candidate_id,
                "gene_symbol": m.gene_symbol,
                "members_tsv": rel_tsv,
                "run_id": rid,
                "run_series": run_series,
                "web_search_mode": web_search_mode,
                "model": DEFAULT_TAG_SITE_MODEL,
                "triage_model": DEFAULT_TAG_SITE_TRIAGE_MODEL,
                "web_scout_model": DEFAULT_TAG_SITE_WEB_SCOUT_MODEL,
                "publish_d1": True,
                "upload_r2": upload_r2,
            }
            for m in batch
        ]
        wave_failed: list[Any] = []
        with ledger_path.open("a", encoding="utf-8") as fh:
            for m, res in zip(batch, enrich_one.map(payloads, return_exceptions=True), strict=True):
                if isinstance(res, BaseException):
                    fail += 1
                    wave_failed.append(m)
                    fh.write(
                        json.dumps(
                            {
                                "candidate_id": m.candidate_id,
                                "gene_symbol": m.gene_symbol,
                                "status": "error",
                                "error": str(res)[:400],
                                "ts": datetime.now(UTC).isoformat(),
                            }
                        )
                        + "\n"
                    )
                    fh.flush()
                    continue
                fh.write(json.dumps(res) + "\n")
                fh.flush()
                st = res.get("status")
                if st == "ok":
                    ok += 1
                    total_cost += float(res.get("cost_usd", 0.0) or 0.0)
                    if res.get("missed_preprint_body"):
                        missed_preprint_members.append(m.candidate_id)
                elif st == "skipped":
                    skipped += 1
                else:
                    fail += 1
                    wave_failed.append(m)
        volume.commit()
        print(
            f"{label}: ok={ok} skipped={skipped} fail={fail} "
            f"missed_biorxiv={len(set(missed_preprint_members))} cost=${total_cost:.2f}",
            flush=True,
        )
        return wave_failed

    for start in range(0, len(todo), max(1, wave_size)):
        if total_cost >= max_budget_usd:
            print(
                f"BUDGET CAP REACHED (${total_cost:.2f} >= ${max_budget_usd:.2f}) — stopping.",
                flush=True,
            )
            break
        wave = todo[start : start + max(1, wave_size)]
        failed_members.extend(_run_wave(wave, f"Wave {start + 1}..{start + len(wave)}"))

    if retry_errors and failed_members and total_cost < max_budget_usd:
        print(f"Retrying {len(failed_members)} failed member(s)...", flush=True)
        # Reset fail count to reflect only unresolved failures after cleanup pass.
        prior_fail = fail
        fail = 0
        still_failed = _run_wave(failed_members, f"Retry ({len(failed_members)})")
        print(
            f"Retry pass complete: recovered={prior_fail - len(still_failed)} still_failed={len(still_failed)}",
            flush=True,
        )

    if missed_preprint_members:
        rescue = vol_run_dir / "missed_preprint_members.txt"
        rescue.write_text("\n".join(sorted(set(missed_preprint_members))) + "\n", encoding="utf-8")
        volume.commit()

    summary = {
        "run_id": rid,
        "members_tsv": rel_tsv,
        "already_done_before_driver": len(done),
        "todo_dispatched": len(todo),
        "ok": ok,
        "skipped": skipped,
        "fail": fail,
        "missed_biorxiv": len(set(missed_preprint_members)),
        "driver_cost_usd": round(total_cost, 4),
        "finished_at": datetime.now(UTC).isoformat(),
    }
    (vol_run_dir / "driver_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    volume.commit()
    print(f"DETACHED SWEEP COMPLETE: {json.dumps(summary)}", flush=True)
    return summary


@app.local_entrypoint()
def check_secret(
    members_tsv: str = "data/tag_sites/expanded_multipass_members.tsv",
) -> None:
    """$0 preflight check."""
    res = secret_presence_check.remote(members_tsv)
    print(json.dumps(res, indent=2))
    missing = [k for k, ok in res["present"].items() if not ok]
    if missing:
        raise RuntimeError(f"surfaceome-env secret missing keys: {missing}")
    if not res.get("r2_write_ok"):
        raise RuntimeError("R2 write probe failed")
    if res.get("n_topology_unresolved", 0) > 0:
        raise RuntimeError(
            f"{res['n_topology_unresolved']} member(s) unresolved in topology_public: "
            f"{res.get('unresolved_sample')}"
        )
    print(
        f"\n✓ Tag-site Modal preflight passed "
        f"({res['n_topology_resolved']}/{res['n_members']} members resolved from {members_tsv})."
    )


@app.local_entrypoint()
def canary(
    genes: str = "KCNN3,TSPAN4,AQP4,KCND2,SLC12A5",
    members_tsv: str = "data/tag_sites/expanded_multipass_members.tsv",
    run_id: str = "",
    web_search_mode: str = "adaptive",
    publish_d1: bool = False,
    upload_r2: bool = True,
) -> None:
    """Run a Modal canary (never writes D1 unless --publish-d1)."""
    from accessible_surfaceome.agents.tag_site.member_frames import load_members
    from accessible_surfaceome.agents.tag_site.runner import (
        DEFAULT_TAG_SITE_MODEL,
        DEFAULT_TAG_SITE_TRIAGE_MODEL,
        DEFAULT_TAG_SITE_WEB_SCOUT_MODEL,
    )
    from accessible_surfaceome.env import REPO_ROOT, load_env

    load_env()
    want = [g.strip().upper() for g in genes.split(",") if g.strip()]
    all_members = load_members(REPO_ROOT / members_tsv)
    selected = []
    for g in want:
        cands = [m for m in all_members if m.gene_symbol.upper() == g]
        if cands:
            human = [m for m in cands if m.species == "human"]
            selected.append((human or cands)[0])

    rid = run_id or datetime.now(UTC).strftime("tag_site_canary_%Y%m%d_%H%M%S")
    payloads = [
        {
            "candidate_id": m.candidate_id,
            "gene_symbol": m.gene_symbol,
            "members_tsv": members_tsv,
            "run_id": rid,
            "run_series": "literature_enriched_v2",
            "web_search_mode": web_search_mode,
            "model": DEFAULT_TAG_SITE_MODEL,
            "triage_model": DEFAULT_TAG_SITE_TRIAGE_MODEL,
            "web_scout_model": DEFAULT_TAG_SITE_WEB_SCOUT_MODEL,
            "publish_d1": publish_d1,
            "upload_r2": upload_r2,
        }
        for m in selected
    ]
    total_cost = 0.0
    for res in enrich_one.map(payloads, return_exceptions=True):
        if isinstance(res, BaseException):
            print(f"  EXCEPTION: {res}", flush=True)
            continue
        total_cost += float(res.get("cost_usd", 0.0) or 0.0)
        print(f"  {json.dumps(res)}", flush=True)
    print(f"\nCanary done: total=${total_cost:.4f} (mean=${total_cost / max(1, len(selected)):.4f}/member)")


@app.local_entrypoint()
def full_sweep(
    members_tsv: str = "data/tag_sites/l1_internal_members.tsv",
    run_id: str = "",
    run_series: str = "literature_enriched_v2",
    web_search_mode: str = "adaptive",
    max_budget_usd: float = 400.0,
    wave_size: int = 100,
    limit: int = 0,
    force: bool = False,
    upload_r2: bool = True,
    execute: bool = False,
) -> None:
    """Run the 607-member L1 internal tag-site enrichment sweep on Modal.

    DRY-RUN by default — pass ``--execute`` to publish to D1 + R2.
    """
    from accessible_surfaceome.agents.tag_site.member_frames import load_members
    from accessible_surfaceome.agents.tag_site.prompt import (
        TAG_SITE_PROMPT_VERSION,
        prompt_sha,
    )
    from accessible_surfaceome.agents.tag_site.runner import (
        DEFAULT_TAG_SITE_MODEL,
        DEFAULT_TAG_SITE_TRIAGE_MODEL,
        DEFAULT_TAG_SITE_WEB_SCOUT_MODEL,
    )
    from accessible_surfaceome.cloud.d1_client import D1Client
    from accessible_surfaceome.cloud.tag_site_genes import searched_members
    from accessible_surfaceome.env import REPO_ROOT, load_env

    load_env()
    tsv_path = Path(members_tsv)
    if not tsv_path.is_absolute():
        rel_tsv = members_tsv
        tsv_path = REPO_ROOT / tsv_path
    else:
        rel_tsv = str(tsv_path.relative_to(REPO_ROOT))
    members = load_members(tsv_path)
    cur_sha = prompt_sha()
    rid = run_id or datetime.now(UTC).strftime("tag_site_l1_modal_%Y%m%d_%H%M%S")

    done: set[tuple[str, str]] = set()
    if not force:
        with D1Client.public() as pub:
            done = searched_members(pub, run_series=run_series, prompt_sha=cur_sha)

    todo = [m for m in members if (m.gene_symbol, m.candidate_id) not in done]
    if limit > 0:
        todo = todo[:limit]

    print(f"Modal tag-site L1 enrichment sweep (run_id={rid})")
    print(f"  members TSV     : {tsv_path} ({len(members)} members)")
    print(f"  prompt          : v{TAG_SITE_PROMPT_VERSION} sha={cur_sha[:12]}  series={run_series}")
    print(f"  already@sha     : {len(done)}  |  todo: {len(todo)}")
    print(f"  models          : synth/select={DEFAULT_TAG_SITE_MODEL}, triage/scout={DEFAULT_TAG_SITE_TRIAGE_MODEL}")
    print(f"  est spend       : ~${len(todo) * PER_MEMBER_USD_EST:,.0f}  |  budget cap: ${max_budget_usd:,.0f}")
    if not execute:
        print("\nDRY RUN — pass --execute to run the Modal sweep. Nothing written.")
        return

    local_run_dir = REPO_ROOT / "data" / "runs" / "tag_site_lit" / rid
    local_run_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = local_run_dir / "ledger.jsonl"

    ok = fail = skipped = 0
    total_cost = 0.0
    missed_preprint_members: list[str] = []

    with ledger_path.open("a", encoding="utf-8") as fh:
        for start in range(0, len(todo), max(1, wave_size)):
            if total_cost >= max_budget_usd:
                print(f"BUDGET CAP REACHED (${total_cost:.2f} >= ${max_budget_usd:.2f}) — stopping.", flush=True)
                break
            wave = todo[start : start + max(1, wave_size)]
            payloads = [
                {
                    "candidate_id": m.candidate_id,
                    "gene_symbol": m.gene_symbol,
                    "members_tsv": rel_tsv,
                    "run_id": rid,
                    "run_series": run_series,
                    "web_search_mode": web_search_mode,
                    "model": DEFAULT_TAG_SITE_MODEL,
                    "triage_model": DEFAULT_TAG_SITE_TRIAGE_MODEL,
                    "web_scout_model": DEFAULT_TAG_SITE_WEB_SCOUT_MODEL,
                    "publish_d1": True,
                    "upload_r2": upload_r2,
                }
                for m in wave
            ]
            for m, res in zip(wave, enrich_one.map(payloads, return_exceptions=True), strict=True):
                if isinstance(res, BaseException):
                    fail += 1
                    fh.write(json.dumps({"candidate_id": m.candidate_id, "status": "error", "error": str(res)[:400]}) + "\n")
                    fh.flush()
                    continue
                fh.write(json.dumps(res) + "\n")
                fh.flush()
                st = res.get("status")
                if st == "ok":
                    ok += 1
                    total_cost += float(res.get("cost_usd", 0.0) or 0.0)
                    if res.get("missed_preprint_body"):
                        missed_preprint_members.append(m.candidate_id)
                elif st == "skipped":
                    skipped += 1
                else:
                    fail += 1
            print(
                f"Wave {start + 1}..{start + len(wave)}: ok={ok} skipped={skipped} fail={fail} "
                f"missed_biorxiv={len(missed_preprint_members)} cost=${total_cost:.2f}",
                flush=True,
            )

    if missed_preprint_members:
        rescue = local_run_dir / "missed_preprint_members.txt"
        rescue.write_text("\n".join(sorted(set(missed_preprint_members))) + "\n", encoding="utf-8")
        print(
            f"\n{len(set(missed_preprint_members))} member(s) had a worth_fetching bioRxiv/medRxiv "
            f"preprint blocked on Modal cloud IPs -> {rescue}\n"
            f"Rescue locally via: uv run python scripts/enrich_tag_site_lit.py "
            f"--candidate-id <ID> --from-r2 --skip-discovery --upload-r2"
        )
