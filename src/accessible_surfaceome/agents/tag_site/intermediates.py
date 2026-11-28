"""Durable R2 + local intermediates store for the tag-site literature pipeline.

Mirrors ``agents/internalization/intermediates.py``: persists per-member
intermediates (discovered papers, Haiku triage verdicts, fetch actions, clip
pool index, span-verified ledger, emitted viewer sites, usage, and summary) as
a gzipped JSON blob in Cloudflare R2:

    r2://{bucket}/tag_site_lit_intermediates/{MEMBER_KEY}/latest.json.gz
    r2://{bucket}/tag_site_lit_intermediates/{MEMBER_KEY}/{run_id}.json.gz

Enables:
  1. Incremental ``--add-papers`` / ``--from-r2 --skip-discovery`` runs without
     re-discovering or re-triaging historical papers.
  2. Local rescue of bioRxiv/medRxiv preprints blocked (HTTP 429) on Modal
     cloud IPs while reusing Modal's discovery + triage verdicts.
  3. Full forensic auditability without hitting D1's 1 MB row limit.
"""

from __future__ import annotations

import gzip
import json
import logging
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from accessible_surfaceome.cloud.r2_client import R2Config, get_object, put_object
from accessible_surfaceome.tools._shared.models import Paper

logger = logging.getLogger(__name__)

INTERMEDIATES_VERSION = "1.0"
_R2_PREFIX = "tag_site_lit_intermediates"


def _safe_key(token: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", token.strip()).strip("_") or "unknown"


def r2_latest_key(member_key: str) -> str:
    return f"{_R2_PREFIX}/{_safe_key(member_key)}/latest.json.gz"


def r2_run_key(member_key: str, run_id: str) -> str:
    return f"{_R2_PREFIX}/{_safe_key(member_key)}/{_safe_key(run_id)}.json.gz"


def _serialize_usage(usage: list[Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for u in usage:
        if hasattr(u, "model_dump"):
            out.append(u.model_dump(mode="json"))
        elif isinstance(u, dict):
            out.append(dict(u))
        else:
            out.append(
                {
                    "model": getattr(u, "model", None),
                    "input_tokens": getattr(u, "input_tokens", None),
                    "output_tokens": getattr(u, "output_tokens", None),
                    "cache_read_input_tokens": getattr(u, "cache_read_input_tokens", None),
                    "cache_creation_input_tokens": getattr(u, "cache_creation_input_tokens", None),
                    "web_search_requests": getattr(u, "web_search_requests", None),
                    "cost_usd": getattr(u, "cost_usd", None),
                    "api_stop_reason": getattr(u, "api_stop_reason", None),
                }
            )
    return out


def build_intermediates_payload(
    *,
    member_key: str,
    gene_symbol: str,
    candidate_id: str | None,
    uniprot_acc: str,
    run_id: str | None,
    run_series: str | None,
    prompt_version: str,
    prompt_sha: str,
    runner_intermediates: dict[str, Any],
    viewer_sites: list[dict[str, Any]],
    usage: list[Any],
    result_dump: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble a self-contained JSON-serializable intermediates + result bundle."""
    return {
        "intermediates_version": INTERMEDIATES_VERSION,
        "member_key": member_key,
        "gene_symbol": gene_symbol.upper(),
        "candidate_id": candidate_id,
        "uniprot_acc": uniprot_acc,
        "run_id": run_id,
        "run_series": run_series,
        "created_at": datetime.now(UTC).isoformat(),
        "prompt_version": prompt_version,
        "prompt_sha": prompt_sha,
        "model": runner_intermediates.get("model"),
        "triage_model": runner_intermediates.get("triage_model"),
        "web_scout_model": runner_intermediates.get("web_scout_model"),
        "web_search_mode": runner_intermediates.get("web_search_mode"),
        "web_search_used": bool(runner_intermediates.get("web_search_used", False)),
        "web_search_reason": runner_intermediates.get("web_search_reason"),
        "web_search_paper_ids": list(runner_intermediates.get("web_search_paper_ids") or []),
        "followup_ref_ids": list(runner_intermediates.get("followup_ref_ids") or []),
        "extra_paper_ids": list(runner_intermediates.get("extra_paper_ids") or []),
        "numbered_against": runner_intermediates.get("numbered_against"),
        "outcome": runner_intermediates.get("outcome"),
        "discovered_papers": dict(runner_intermediates.get("discovered_papers") or {}),
        "triage_verdicts": dict(runner_intermediates.get("triage_verdicts") or {}),
        "fetch_actions": list(runner_intermediates.get("fetch_actions") or []),
        "pool": list(runner_intermediates.get("pool") or []),
        "ledger": list(runner_intermediates.get("ledger") or []),
        "rejected": list(runner_intermediates.get("rejected") or []),
        "other_positions": list(runner_intermediates.get("other_positions") or []),
        "viewer_sites": list(viewer_sites),
        "usage": _serialize_usage(usage),
        "summary": {
            "n_papers": runner_intermediates.get("n_papers", 0),
            "n_papers_fetched": runner_intermediates.get("n_papers_fetched", 0),
            "n_clips": runner_intermediates.get("n_clips", 0),
            "n_boosted": runner_intermediates.get("n_boosted", 0),
            "n_sites": len(viewer_sites),
            "n_refusals": runner_intermediates.get("n_refusals", 0),
            "cache_read_tokens": runner_intermediates.get("cache_read_tokens", 0),
            "cache_write_tokens": runner_intermediates.get("cache_write_tokens", 0),
            "cost_usd": round(sum(getattr(u, "cost_usd", 0.0) or 0.0 for u in usage), 4),
        },
        "result": result_dump,
    }


def has_missed_preprint_body(payload: dict[str, Any]) -> bool:
    """True when any ``worth_fetching`` bioRxiv/medRxiv preprint failed to fetch
    its body (typically HTTP 429 from cloud/Modal IPs -> flag for local rescue)."""
    disc_map = payload.get("discovered_papers") or {}
    for a in payload.get("fetch_actions") or []:
        if a.get("decision") != "worth_fetching" or a.get("fetched_body"):
            continue
        pid = str(a.get("paper_id") or "")
        if (
            "10.1101/" in pid
            or "10.64898/" in pid
            or bool((disc_map.get(pid) or {}).get("is_preprint"))
        ):
            return True
    return False


def compress_intermediates(payload: dict[str, Any]) -> bytes:
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True, default=str).encode("utf-8")
    return gzip.compress(raw, compresslevel=6)


def decompress_intermediates(data: bytes) -> dict[str, Any]:
    raw = gzip.decompress(data) if data[:2] == b"\x1f\x8b" else data
    obj = json.loads(raw.decode("utf-8"))
    if not isinstance(obj, dict):
        raise ValueError("intermediates payload is not a JSON object")
    return obj


def save_intermediates_local(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == ".gz":
        path.write_bytes(compress_intermediates(payload))
    else:
        path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    return path


def _put_with_retry(
    *,
    key: str,
    body: bytes,
    content_type: str,
    cfg: R2Config | None,
    max_retries: int = 3,
) -> bool:
    attempts = max(1, max_retries)
    for attempt in range(1, attempts + 1):
        if put_object(key=key, body=body, content_type=content_type, cfg=cfg):
            return True
        if attempt < attempts:
            wait_s = float(2 ** (attempt - 1))
            logger.warning(
                "R2 upload failed for %s (attempt %d/%d, retrying in %.0fs)",
                key,
                attempt,
                attempts,
                wait_s,
            )
            time.sleep(wait_s)
    return False


def upload_intermediates_r2(
    payload: dict[str, Any],
    *,
    member_key: str,
    run_id: str | None = None,
    cfg: R2Config | None = None,
    max_retries: int = 3,
) -> tuple[bool, str]:
    """Upload gzipped intermediates + result to R2 with exponential backoff.
    Best-effort: never raises so an R2 blip never discards a completed member."""
    gz_bytes = compress_intermediates(payload)
    latest_key = r2_latest_key(member_key)
    ok_latest = _put_with_retry(
        key=latest_key,
        body=gz_bytes,
        content_type="application/gzip",
        cfg=cfg,
        max_retries=max_retries,
    )
    ok_run = True
    if run_id:
        ok_run = _put_with_retry(
            key=r2_run_key(member_key, run_id),
            body=gz_bytes,
            content_type="application/gzip",
            cfg=cfg,
            max_retries=max_retries,
        )
    return (ok_latest and ok_run), latest_key


def load_intermediates_r2(
    member_key: str,
    *,
    run_id: str | None = None,
    cfg: R2Config | None = None,
) -> dict[str, Any] | None:
    key = r2_run_key(member_key, run_id) if run_id else r2_latest_key(member_key)
    try:
        raw = get_object(key=key, cfg=cfg)
    except Exception as exc:  # noqa: BLE001
        logger.warning("R2 tag-site intermediates load failed for %s (%s): %s", member_key, key, exc)
        return None
    if raw is None:
        return None
    try:
        return decompress_intermediates(raw)
    except Exception as exc:  # noqa: BLE001
        logger.warning("R2 tag-site intermediates corrupt for %s (%s): %s", member_key, key, exc)
        return None


def seed_from_intermediates(
    blob: dict[str, Any],
) -> tuple[dict[str, Paper], dict[str, dict[str, Any]], bool]:
    """Extract reusable ``(discovered_papers, triage_cache, web_search_ran)``
    from a saved R2/local intermediates bundle."""
    papers: dict[str, Paper] = {}
    for sid, raw_p in (blob.get("discovered_papers") or {}).items():
        if not isinstance(raw_p, dict):
            continue
        try:
            papers[sid] = Paper.model_validate(raw_p)
        except Exception:  # noqa: BLE001
            continue

    triage_cache: dict[str, dict[str, Any]] = {}
    for sid, hit in (blob.get("triage_verdicts") or {}).items():
        if isinstance(hit, dict) and hit.get("decision") and not hit.get("error"):
            triage_cache[sid] = dict(hit)

    web_search_ran = bool(blob.get("web_search_used", False))
    return papers, triage_cache, web_search_ran
