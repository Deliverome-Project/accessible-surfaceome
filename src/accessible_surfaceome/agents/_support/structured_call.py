"""Shared structured-output model call: fenced-JSON extraction + a schema-repair
loop. Agent-agnostic — extracted from internalization.model_prior so the
internalization and tag-site literature pipelines share ONE implementation.
"""

from __future__ import annotations

import json
import re
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from accessible_surfaceome.agents._support.api_retry import messages_create_with_backoff
from accessible_surfaceome.agents._support.payload import cached_system

T = TypeVar("T", bound=BaseModel)

SONNET_MODEL = "claude-sonnet-4-6"  # literature-track grader/selector
MAX_TOKENS = 16_000
MAX_REPAIRS = 1

_FENCED_JSON_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def extract_json_object(text: str) -> dict[str, Any]:
    """Pull a JSON object from a model response: last fenced ```json block, else
    the outermost bare {...}. Raises ValueError when neither parses."""
    matches = _FENCED_JSON_RE.findall(text)
    if matches:
        return json.loads(matches[-1])
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        return json.loads(text[start : end + 1])
    raise ValueError("no JSON object found in model response")


def _text_of(resp: Any) -> str:
    return "".join(
        getattr(b, "text", "")
        for b in resp.content
        if getattr(b, "type", None) == "text"
    ).strip()


def call_model_structured(
    client: Any,
    *,
    model: str,
    system_prompt: str,
    user_prompt: str,
    schema: type[T],
    usage_sink: list[Any] | None = None,
    max_tokens: int = MAX_TOKENS,
    max_repairs: int = MAX_REPAIRS,
) -> T:
    messages: list[dict[str, Any]] = [{"role": "user", "content": user_prompt}]
    last_err = ""
    for _ in range(max_repairs + 1):
        resp = messages_create_with_backoff(
            client,
            model=model,
            max_tokens=max_tokens,
            system=cached_system(system_prompt),
            messages=messages,
        )
        if usage_sink is not None:
            usage_sink.append(resp.usage)
        text = _text_of(resp)
        try:
            return schema.model_validate(extract_json_object(text))
        except (ValueError, ValidationError) as err:
            last_err = str(err)[:800]
            messages.append({"role": "assistant", "content": text})
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "That was not valid per the schema. Return ONE ```json "
                        f"fenced object only. Error:\n{last_err}"
                    ),
                }
            )
    raise ValueError(f"model {model} failed schema validation after repairs: {last_err}")
