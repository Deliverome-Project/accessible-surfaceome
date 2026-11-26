"""Durable R2 + local intermediates store for the internalization literature track.

Persists every expensive per-gene artifact (discovered papers, Haiku triage
verdicts, full-text fetch actions, extracted clip pool, span-verified evidence
ledger, web-search status, and per-call usage) as a single gzipped JSON blob:

    r2://{bucket}/internalization_lit_intermediates/{GENE}/latest.json.gz
    r2://{bucket}/internalization_lit_intermediates/{GENE}/{run_id}.json.gz

Why this exists:
  1. **Incremental paper addition over time:** reload ``latest.json.gz`` from
     any machine/worktree, merge in newly published or manually supplied
     PMIDs/PMCIDs/DOIs, triage and fetch *only* the delta papers, and re-run
     just the select/grade step (~$0.05-0.08/gene instead of re-discovering
     and re-triaging 100+ historical papers).
  2. **Forensic auditability:** mirrors ``cloud.intermediates`` for surface
     annotations without risking D1's 1 MB row limit (typical blob is
     ~20-80 KB gzipped; ~150 MB total across 3,213 genes).
  3. **Zero new secrets:** reuses :mod:`accessible_surfaceome.cloud.r2_client`
     (``CLOUDFLARE_ACCOUNT_ID`` + ``CLOUDFLARE_API_TOKEN`` →
     ``deliverome-d1-backups``).
"""

from __future__ import annotations

import gzip
import json
import logging
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from accessible_surfaceome.agents.plan_trim_select.abstract_triage import (
    TriageOutcome,
    paper_source_id,
)
from accessible_surfaceome.agents.plan_trim_select.schemas import AbstractTriageResponse
from accessible_surfaceome.cloud.r2_client import R2Config, get_object, put_object
from accessible_surfaceome.tools._shared.europepmc import (
    europepmc_bulk_by_pmid,
    europepmc_search,
    paper_from_europepmc,
)
from accessible_surfaceome.tools._shared.http import CachedHTTP
from accessible_surfaceome.tools._shared.models import EvidenceClaimDraft, Paper
from accessible_surfaceome.tools._shared.preprint import paper_from_preprint_doi
from accessible_surfaceome.tools._shared.retraction_watch import RetractionIndex

logger = logging.getLogger(__name__)

INTERMEDIATES_VERSION = "1.0"
_R2_PREFIX = "internalization_lit_intermediates"

_PMID_RE = re.compile(r"^(?:pmid[:\s]*)?(\d{5,9})$", re.IGNORECASE)
_PMCID_RE = re.compile(r"^(?:pmc[:\s]*)?(PMC\d+)$", re.IGNORECASE)
_DOI_PREFIX_RE = re.compile(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", re.IGNORECASE)


def r2_latest_key(gene_symbol: str) -> str:
    return f"{_R2_PREFIX}/{gene_symbol.upper()}/latest.json.gz"


def r2_run_key(gene_symbol: str, run_id: str) -> str:
    safe_run = re.sub(r"[^A-Za-z0-9._-]+", "_", run_id).strip("_") or "run"
    return f"{_R2_PREFIX}/{gene_symbol.upper()}/{safe_run}.json.gz"


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


def _serialize_triage_verdicts(
    outcomes: list[Any],
    *,
    prompt_sha: str,
    input_shas: dict[str, str],
    model: str,
) -> dict[str, dict[str, Any]]:
    verdicts: dict[str, dict[str, Any]] = {}
    for o in outcomes:
        pid = getattr(o, "paper_id", None)
        if not pid:
            continue
        resp = getattr(o, "response", None)
        err = getattr(o, "error", None)
        verdicts[pid] = {
            "decision": getattr(resp, "decision", None) if resp is not None else None,
            "reason": getattr(resp, "reason", None) if resp is not None else None,
            "prompt_sha": prompt_sha,
            "input_sha": input_shas.get(pid),
            "model": model,
            "error": err,
        }
    return verdicts


def _serialize_actions(actions: list[Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for a in actions:
        if hasattr(a, "model_dump"):
            out.append(a.model_dump(mode="json"))
        elif isinstance(a, dict):
            out.append(dict(a))
        else:
            out.append(
                {
                    "paper_id": getattr(a, "paper_id", None),
                    "decision": getattr(a, "decision", None),
                    "fetched_body": bool(getattr(a, "fetched_body", False)),
                    "body_source": getattr(a, "body_source", None),
                    "n_drafts": getattr(a, "n_drafts", None),
                    "error": getattr(a, "error", None),
                }
            )
    return out


def build_intermediates_payload(
    *,
    gene_symbol: str,
    hgnc_id: str | None,
    uniprot_acc: str | None,
    run_id: str | None,
    schema_version: str,
    lit_prompt_version: str,
    lit_prompt_sha: str,
    triage_prompt_sha: str,
    model: str,
    triage_model: str,
    web_scout_model: str,
    web_search_mode: str,
    web_search_used: bool,
    web_search_reason: str | None,
    web_search_paper_ids: list[str],
    extra_paper_ids: list[str],
    discovered: dict[str, Paper],
    outcomes: list[Any],
    triage_input_shas: dict[str, str],
    actions: list[Any],
    pool: dict[str, EvidenceClaimDraft],
    evidence_pre_cap: list[Any],
    evidence_graded: list[Any],
    usage: list[Any],
    summary: dict[str, Any],
) -> dict[str, Any]:
    """Assemble the canonical JSON-serializable intermediates bundle for one gene."""
    return {
        "intermediates_version": INTERMEDIATES_VERSION,
        "gene_symbol": gene_symbol.upper(),
        "hgnc_id": hgnc_id,
        "uniprot_acc": uniprot_acc,
        "run_id": run_id,
        "created_at": datetime.now(UTC).isoformat(),
        "schema_version": schema_version,
        "lit_prompt_version": lit_prompt_version,
        "lit_prompt_sha": lit_prompt_sha,
        "model": model,
        "triage_model": triage_model,
        "web_scout_model": web_scout_model,
        "web_search_mode": web_search_mode,
        "web_search_used": web_search_used,
        "web_search_reason": web_search_reason,
        "web_search_paper_ids": sorted(set(web_search_paper_ids)),
        "extra_paper_ids": list(extra_paper_ids),
        "discovered_papers": {
            sid: p.model_dump(mode="json") for sid, p in discovered.items()
        },
        "triage_verdicts": _serialize_triage_verdicts(
            outcomes,
            prompt_sha=triage_prompt_sha,
            input_shas=triage_input_shas,
            model=triage_model,
        ),
        "fetch_actions": _serialize_actions(actions),
        "pool_clips": {
            cid: d.model_dump(mode="json") for cid, d in pool.items()
        },
        "selected_evidence_all": [
            e.model_dump(mode="json") for e in evidence_pre_cap
        ],
        "selected_evidence_graded": [
            e.model_dump(mode="json") for e in evidence_graded
        ],
        "usage": _serialize_usage(usage),
        "summary": summary,
    }


def compress_intermediates(payload: dict[str, Any]) -> bytes:
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return gzip.compress(raw, compresslevel=6)


def decompress_intermediates(data: bytes) -> dict[str, Any]:
    if data[:2] == b"\x1f\x8b":
        raw = gzip.decompress(data)
    else:
        raw = data
    obj = json.loads(raw.decode("utf-8"))
    if not isinstance(obj, dict):
        raise ValueError("intermediates payload is not a JSON object")
    return obj


def save_intermediates_local(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == ".gz":
        path.write_bytes(compress_intermediates(payload))
    else:
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def upload_intermediates_r2(
    payload: dict[str, Any],
    *,
    gene_symbol: str,
    run_id: str | None = None,
    cfg: R2Config | None = None,
) -> tuple[bool, str]:
    """Upload gzipped intermediates to R2 (``latest.json.gz`` + optional ``{run_id}.json.gz``).

    Best-effort: returns ``(ok, latest_key)`` and never raises so an R2 blip
    never aborts a sweep or discards a completed gene.
    """
    gz_bytes = compress_intermediates(payload)
    latest_key = r2_latest_key(gene_symbol)
    ok_latest = put_object(
        key=latest_key,
        body=gz_bytes,
        content_type="application/gzip",
        cfg=cfg,
    )
    ok_run = True
    if run_id:
        run_key = r2_run_key(gene_symbol, run_id)
        ok_run = put_object(
            key=run_key,
            body=gz_bytes,
            content_type="application/gzip",
            cfg=cfg,
        )
    return (ok_latest and ok_run), latest_key


def load_intermediates_r2(
    gene_symbol: str,
    *,
    run_id: str | None = None,
    cfg: R2Config | None = None,
) -> dict[str, Any] | None:
    """Download and decode a gene's saved intermediates bundle from R2.

    Returns ``None`` on 404 or when R2 credentials are not configured.
    """
    key = r2_run_key(gene_symbol, run_id) if run_id else r2_latest_key(gene_symbol)
    try:
        raw = get_object(key=key, cfg=cfg)
    except Exception as exc:  # noqa: BLE001
        logger.warning("R2 intermediates load failed for %s (%s): %s", gene_symbol, key, exc)
        return None
    if raw is None:
        return None
    try:
        return decompress_intermediates(raw)
    except Exception as exc:  # noqa: BLE001
        logger.warning("R2 intermediates corrupt for %s (%s): %s", gene_symbol, key, exc)
        return None


def seed_from_intermediates(
    blob: dict[str, Any],
) -> tuple[dict[str, Paper], dict[str, dict[str, Any]], bool]:
    """Extract reusable ``(discovered_papers, triage_cache, web_search_ran)``
    from a previously saved R2/local intermediates bundle."""
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


def force_worth_fetching_outcomes(
    papers: dict[str, Paper],
    *,
    reason: str = "User-supplied paper via --add-papers",
) -> list[TriageOutcome]:
    """Promote explicitly user-supplied papers straight to ``worth_fetching`` so
    incremental additions are always fetched and span-verified without risking
    an accidental Haiku discard."""
    out: list[TriageOutcome] = []
    for sid in papers:
        out.append(
            TriageOutcome(
                paper_id=sid,
                response=AbstractTriageResponse(
                    paper_id=sid,
                    decision="worth_fetching",
                    reason=reason,
                ),
                usage=None,
                elapsed_s=0.0,
                error=None,
            )
        )
    return out


def hydrate_paper_ids(
    identifiers: list[str],
    *,
    http: CachedHTTP,
    retraction_index: RetractionIndex,
) -> dict[str, Paper]:
    """Hydrate user-supplied PMIDs, PMCIDs, or DOIs into real ``Paper`` objects
    via EuropePMC with bioRxiv/medRxiv preprint DOI fallback."""
    out: dict[str, Paper] = {}
    pmids: list[int] = []
    pmcids: list[str] = []
    dois: list[str] = []

    for raw in identifiers:
        token = raw.strip()
        if not token:
            continue
        m_pmc = _PMCID_RE.match(token)
        if m_pmc:
            pmcids.append(m_pmc.group(1).upper())
            continue
        m_pmid = _PMID_RE.match(token)
        if m_pmid:
            pmids.append(int(m_pmid.group(1)))
            continue
        doi = _DOI_PREFIX_RE.sub("", token).strip().lower()
        if "/" in doi:
            dois.append(doi)
        else:
            logger.warning("unrecognized paper identifier %r — skipping", raw)

    if pmids:
        for paper in europepmc_bulk_by_pmid(
            http=http, pmids=pmids, retraction_index=retraction_index
        ):
            if not getattr(paper, "is_retracted", False):
                out.setdefault(paper_source_id(paper), paper)

    for pmcid in pmcids:
        try:
            payload = europepmc_search(http=http, query=f'PMCID:"{pmcid}"', page_size=1)
            for rec in payload.get("resultList", {}).get("result", []):
                paper = paper_from_europepmc(
                    rec, retraction_index=retraction_index, include_preprints=True
                )
                if not getattr(paper, "is_retracted", False):
                    out.setdefault(paper_source_id(paper), paper)
                    break
        except Exception as exc:  # noqa: BLE001
            logger.warning("could not hydrate PMCID %s: %s", pmcid, exc)

    for doi in dois:
        hydrated: Paper | None = None
        try:
            payload = europepmc_search(http=http, query=f'DOI:"{doi}"', page_size=1)
            for rec in payload.get("resultList", {}).get("result", []):
                try:
                    hydrated = paper_from_europepmc(
                        rec, retraction_index=retraction_index, include_preprints=True
                    )
                    break
                except LookupError:
                    continue
        except Exception as exc:  # noqa: BLE001
            logger.warning("EuropePMC DOI lookup failed for %s: %s", doi, exc)
        if hydrated is None:
            try:
                hydrated = paper_from_preprint_doi(
                    doi, http=http, retraction_index=retraction_index
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("preprint DOI lookup failed for %s: %s", doi, exc)
        if hydrated is not None and not getattr(hydrated, "is_retracted", False):
            out.setdefault(paper_source_id(hydrated), hydrated)
        elif hydrated is None:
            logger.warning("could not hydrate DOI %s from EuropePMC or bioRxiv/medRxiv", doi)

    return out
