"""Local triage verdict cache for the internalization literature track.

Mirrors ``agents/tag_site/triage_cache.py``: caches Haiku per-paper verdicts
under ``data/external/internalization_triage/{GENE}.json`` keyed on
``(source_id, prompt_sha, input_sha)``, so tuning the select or grade prompts
never re-pays 100+ Haiku triage calls per gene. Error outcomes are never cached.
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

from accessible_surfaceome.agents.internalization.literature_triage import (
    load_triage_prompt,
)
from accessible_surfaceome.agents.plan_trim_select.abstract_triage import TriageOutcome
from accessible_surfaceome.agents.plan_trim_select.schemas import AbstractTriageResponse
from accessible_surfaceome.env import REPO_ROOT

log = logging.getLogger(__name__)

TRIAGE_CACHE_DIR = REPO_ROOT / "data" / "external" / "internalization_triage"


def triage_prompt_sha(system_prompt: str | None = None) -> str:
    text = system_prompt if system_prompt is not None else load_triage_prompt()
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def input_sha(paper: Any) -> str:
    title = (getattr(paper, "title", "") or "").strip()
    abstract = (getattr(paper, "abstract", "") or "").strip()
    return hashlib.sha256(f"{title}\n{abstract}".encode("utf-8")).hexdigest()


def _path(gene_symbol: str, *, cache_dir: Path | None = None) -> Path:
    return Path(cache_dir or TRIAGE_CACHE_DIR) / f"{gene_symbol.upper()}.json"


def load(gene_symbol: str, *, cache_dir: Path | None = None) -> dict[str, dict[str, Any]]:
    try:
        raw = json.loads(_path(gene_symbol, cache_dir=cache_dir).read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 — absent or corrupt cache must never fail a run
        return {}
    return raw if isinstance(raw, dict) else {}


def save(
    gene_symbol: str,
    outcomes: list[Any],
    *,
    prompt_sha: str,
    inputs: dict[str, str] | None = None,
    model: str | None = None,
    cache_dir: Path | None = None,
) -> int:
    cached = load(gene_symbol, cache_dir=cache_dir)
    n = 0
    for o in outcomes:
        resp = getattr(o, "response", None)
        if resp is None or getattr(o, "error", None):
            continue
        cached[o.paper_id] = {
            "decision": getattr(resp, "decision", None),
            "reason": getattr(resp, "reason", None),
            "prompt_sha": prompt_sha,
            "input_sha": (inputs or {}).get(o.paper_id),
            "model": model,
        }
        n += 1
    path = _path(gene_symbol, cache_dir=cache_dir)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(cached, indent=2, sort_keys=True), encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        log.warning("could not write internalization triage cache for %s: %s", gene_symbol, exc)
        return 0
    return n


def split(
    papers: dict[str, Any],
    cached: dict[str, dict[str, Any]],
    *,
    prompt_sha: str,
    model: str | None = None,
) -> tuple[list[Any], list[TriageOutcome]]:
    """Return ``(to_triage, reusable_outcomes)``."""
    to_triage: list[Any] = []
    reusable: list[TriageOutcome] = []
    for source_id, paper in papers.items():
        hit = cached.get(source_id)
        if (
            not hit
            or hit.get("prompt_sha") != prompt_sha
            or hit.get("input_sha") != input_sha(paper)
            or (model is not None and hit.get("model") != model)
        ):
            to_triage.append(paper)
            continue
        try:
            response = AbstractTriageResponse(
                paper_id=source_id,
                decision=hit["decision"],
                reason=hit.get("reason") or "",
            )
        except Exception:  # noqa: BLE001
            to_triage.append(paper)
            continue
        reusable.append(
            TriageOutcome(
                paper_id=source_id, response=response, usage=None, elapsed_s=0.0, error=None
            )
        )
    return to_triage, reusable
