"""Tag-site-specific abstract triage (Haiku 5.5, 3-way: discard /
keep_abstract / worth_fetching).

Replaces the generic surface-accessibility triage in ``plan_trim_select`` for
the tag-site agent: uses a tag-insertion-specific prompt, passes gene synonyms,
supports internal-loop-only scoping (discarding cytoplasmic N-/C-terminal
GFP/FLAG fusions on multipass proteins with no extracellular terminus),
disables adaptive thinking on Claude 5.x Haiku (so 512 output tokens are never
exhausted before JSON emission), and emits ``TriageOutcome`` objects directly
consumed by ``plan_trim_select.apply_triage_outcomes``.
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
from accessible_surfaceome.agents._support.structured_call import extract_json_object
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

_INTERNAL_SCOPE_LINE = (
    "SCOPE: internal extracellular loops ONLY — this protein has NO "
    "extracellular terminus (both N- and C-termini are intracellular). "
    "Discard papers that only report N-terminal or C-terminal fusions; keep "
    "extracellular loop insertions, unspecified-position ecto-tags detected "
    "on intact cells, insertion screens, and snorkel tags.\n"
)


def load_triage_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def _cached_triage_system(system_prompt: str) -> str:
    """Append the static AbstractTriageResponse JSON schema to the cached system
    prompt so Anthropic ephemeral prompt caching covers both rules and schema."""
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
    internal_only: bool = False,
    model: str = HAIKU_MODEL,
) -> TriageOutcome:
    pid = paper_source_id(paper)  # PMC:<id> > PMID:<id> > DOI:<doi>
    clean_syns = [s.strip() for s in (synonyms or []) if s and s.strip() and s.strip().upper() != gene.upper()]
    aka = f"Also known as: {', '.join(dict.fromkeys(clean_syns))}\n" if clean_syns else ""
    scope = _INTERNAL_SCOPE_LINE if internal_only else ""
    user = (
        f"Gene: {gene}\n{aka}{scope}Source: {pid}\n"
        f"Title: {getattr(paper, 'title', None) or '(no title)'}\n\n"
        f"Abstract:\n{(getattr(paper, 'abstract', None) or '').strip() or '(no abstract)'}\n\n"
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
        # abstract classifier, thinking can consume the entire budget and emit
        # empty text. Disable thinking for triage.
        if model_rejects_sampling_params(model):
            call_kwargs["thinking"] = {"type": "disabled"}
        resp = messages_create_with_backoff(client, **call_kwargs)
        raw_usage = getattr(resp, "usage", None)
        pkey = resolve_pricing_key(model)
        if raw_usage is not None and pkey is not None:
            usage_rec = record_from_response(raw_usage, pkey, response=resp)
        if getattr(resp, "stop_reason", None) == "refusal":
            logger.warning(
                "tag_site triage refusal (%s) on %s paper %s: %.120s",
                model,
                gene,
                pid,
                getattr(paper, "title", None) or "",
            )
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


def triage_tag_site_abstracts(
    client: Any,
    *,
    papers: list[Any],
    gene: str,
    synonyms: list[str] | None = None,
    internal_only: bool = False,
    system_prompt: str | None = None,
    concurrency: int = TRIAGE_CONCURRENCY,
    usage_sink: list[Any] | None = None,
    model: str = HAIKU_MODEL,
) -> list[TriageOutcome]:
    """Triage abstracts concurrently (order preserved) for tag-site relevance.

    Each paper's Haiku call is independent and shares the cached system prompt;
    ``messages_create_with_backoff`` self-throttles on rate limits.
    """
    if not papers:
        return []
    full_system = _cached_triage_system(system_prompt or load_triage_prompt())
    workers = max(1, min(concurrency, len(papers)))
    with ThreadPoolExecutor(max_workers=workers) as ex:
        outcomes = list(
            ex.map(
                lambda p: _triage_one(
                    client,
                    paper=p,
                    gene=gene,
                    system_prompt=full_system,
                    synonyms=synonyms,
                    internal_only=internal_only,
                    model=model,
                ),
                papers,
            )
        )
    if usage_sink is not None:
        usage_sink.extend(o.usage for o in outcomes if getattr(o, "usage", None) is not None)
    return outcomes
