"""Internalization-specific abstract triage (Haiku, 3-way: discard /
keep_abstract / worth_fetching).

The shared ``plan_trim_select.triage_abstracts`` bakes a fixed surface-evidence
prompt with no override, so this module runs its own internalization-flavored
triage and emits ``TriageOutcome`` objects — the exact shape
``plan_trim_select.apply_triage_outcomes`` consumes for body fetch.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from accessible_surfaceome.agents._support.api_retry import messages_create_with_backoff
from accessible_surfaceome.agents._support.payload import cached_system
from accessible_surfaceome.agents.internalization.model_prior import extract_json_object
from accessible_surfaceome.agents.plan_trim_select.abstract_triage import TriageOutcome
from accessible_surfaceome.agents.plan_trim_select.schemas import AbstractTriageResponse

HAIKU_MODEL = "claude-haiku-4-5-20251001"
MAX_TOKENS_TRIAGE = 512
_PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "literature_triage_system.md"


def load_triage_prompt() -> str:
    return _PROMPT_PATH.read_text()


def _make_paper_source_id(paper: Any) -> str:
    return f"PMID:{paper.pmid}"


def _text_of(resp: Any) -> str:
    return "".join(
        getattr(b, "text", "")
        for b in resp.content
        if getattr(b, "type", None) == "text"
    ).strip()


def triage_internalization_abstracts(
    client: Any,
    *,
    papers: list[Any],
    gene: str,
    system_prompt: str | None = None,
) -> list[TriageOutcome]:
    system_prompt = system_prompt or load_triage_prompt()
    outcomes: list[TriageOutcome] = []
    for paper in papers:
        pid = _make_paper_source_id(paper)
        user = (
            f"Gene: {gene}\nPMID: {paper.pmid}\nTitle: {paper.title}\n\n"
            f"Abstract:\n{paper.abstract or '(no abstract)'}\n\n"
            f"Decide: discard | keep_abstract | worth_fetching. "
            f"Use paper_id={pid!r}. Return one ```json object."
        )
        try:
            resp = messages_create_with_backoff(
                client,
                model=HAIKU_MODEL,
                max_tokens=MAX_TOKENS_TRIAGE,
                system=cached_system(system_prompt),
                messages=[{"role": "user", "content": user}],
            )
            data = extract_json_object(_text_of(resp))
            data.setdefault("paper_id", pid)
            outcomes.append(
                TriageOutcome(
                    paper_id=pid,
                    response=AbstractTriageResponse.model_validate(data),
                    usage=None,
                    elapsed_s=0.0,
                    error=None,
                )
            )
        except Exception as err:  # noqa: BLE001 — one bad paper must not kill the batch
            outcomes.append(
                TriageOutcome(
                    paper_id=pid, response=None, usage=None, elapsed_s=0.0, error=str(err)
                )
            )
    return outcomes
