"""Internalization-specific abstract triage (Haiku, 3-way: discard /
keep_abstract / worth_fetching).

The shared ``plan_trim_select.triage_abstracts`` bakes a fixed surface-evidence
prompt with no override, so this module runs its own internalization-flavored
triage and emits ``TriageOutcome`` objects — the exact shape
``plan_trim_select.apply_triage_outcomes`` consumes for body fetch.
"""

from __future__ import annotations

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from accessible_surfaceome.agents._support.api_retry import messages_create_with_backoff
from accessible_surfaceome.agents._support.model_config import model_rejects_sampling_params
from accessible_surfaceome.agents._support.payload import cached_system
from accessible_surfaceome.agents._support.pricing import (
    record_from_response,
    resolve_pricing_key,
)
from accessible_surfaceome.agents.internalization.model_prior import extract_json_object
from accessible_surfaceome.agents.plan_trim_select.abstract_triage import (
    TriageOutcome,
    paper_source_id,
)
from accessible_surfaceome.agents.plan_trim_select.schemas import AbstractTriageResponse

logger = logging.getLogger(__name__)

HAIKU_MODEL = "claude-haiku-5-5"
MAX_TOKENS_TRIAGE = 512
TRIAGE_CONCURRENCY = 10
_PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "literature_triage_system.md"
_TRIAGE_SCHEMA_JSON = json.dumps(AbstractTriageResponse.model_json_schema(), indent=2)


def load_triage_prompt() -> str:
    return _PROMPT_PATH.read_text()


def _cached_triage_system(system_prompt: str) -> str:
    """Append the static AbstractTriageResponse JSON schema to the cached system
    prompt (same pattern as plan_trim_select.abstract_triage)."""
    return f"{system_prompt}\n\n# JSON Schema\n\n```json\n{_TRIAGE_SCHEMA_JSON}\n```"


def _text_of(resp: Any) -> str:
    return "".join(
        getattr(b, "text", "")
        for b in resp.content
        if getattr(b, "type", None) == "text"
    ).strip()


def _triage_one(
    client: Any,
    *,
    paper: Any,
    gene: str,
    system_prompt: str,
    synonyms: list[str] | None = None,
    model: str = HAIKU_MODEL,
) -> TriageOutcome:
    pid = paper_source_id(paper)  # PMC:<id> > PMID:<id> > DOI:<doi>
    aka = f"Also known as: {', '.join(synonyms)}\n" if synonyms else ""
    user = (
        f"Gene: {gene}\n{aka}Source: {pid}\nTitle: {paper.title}\n\n"
        f"Abstract:\n{paper.abstract or '(no abstract)'}\n\n"
        f"Decide: discard | keep_abstract | worth_fetching. "
        f"Use paper_id={pid!r}. Return one ```json object."
    )
    t0 = time.monotonic()
    usage_rec = None
    try:
        call_kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": MAX_TOKENS_TRIAGE,
            "system": cached_system(system_prompt),
            "messages": [{"role": "user", "content": user}],
        }
        # Claude 5.x models enable adaptive thinking by default; on a 512-token
        # abstract classifier, thinking can consume all 512 tokens and emit empty
        # text (silently dropping ~10-20% of papers). Disable thinking for triage.
        if model_rejects_sampling_params(model):
            call_kwargs["thinking"] = {"type": "disabled"}
        resp = messages_create_with_backoff(client, **call_kwargs)
        raw_usage = getattr(resp, "usage", None)
        pkey = resolve_pricing_key(model)
        if raw_usage is not None and pkey is not None:
            usage_rec = record_from_response(raw_usage, pkey, response=resp)
        if getattr(resp, "stop_reason", None) == "refusal":
            logger.warning("triage refusal (%s) on %s paper %s: %.120s", model, gene, pid, paper.title or "")
            return TriageOutcome(
                paper_id=pid,
                response=None,
                usage=usage_rec,
                elapsed_s=round(time.monotonic() - t0, 3),
                error="refusal",
            )
        data = extract_json_object(_text_of(resp))
        data.setdefault("paper_id", pid)
        return TriageOutcome(
            paper_id=pid,
            response=AbstractTriageResponse.model_validate(data),
            usage=usage_rec,
            elapsed_s=round(time.monotonic() - t0, 3),
            error=None,
        )
    except Exception as err:  # noqa: BLE001 — one bad paper must not kill the batch
        return TriageOutcome(
            paper_id=pid,
            response=None,
            usage=usage_rec,
            elapsed_s=round(time.monotonic() - t0, 3),
            error=str(err),
        )


def triage_internalization_abstracts(
    client: Any,
    *,
    papers: list[Any],
    gene: str,
    synonyms: list[str] | None = None,
    system_prompt: str | None = None,
    concurrency: int = TRIAGE_CONCURRENCY,
    usage_sink: list[Any] | None = None,
    model: str = HAIKU_MODEL,
) -> list[TriageOutcome]:
    """Triage abstracts concurrently (order preserved). Each paper's Haiku call
    is independent; ``messages_create_with_backoff`` self-throttles on rate
    limits, so a pool of ~10 is safe at cohort scale."""
    if not papers:
        return []
    system_prompt = _cached_triage_system(system_prompt or load_triage_prompt())
    workers = max(1, min(concurrency, len(papers)))
    with ThreadPoolExecutor(max_workers=workers) as ex:
        outcomes = list(
            ex.map(
                lambda p: _triage_one(
                    client,
                    paper=p,
                    gene=gene,
                    system_prompt=system_prompt,
                    synonyms=synonyms,
                    model=model,
                ),
                papers,
            )
        )
    if usage_sink is not None:
        usage_sink.extend(o.usage for o in outcomes if getattr(o, "usage", None) is not None)
    return outcomes
