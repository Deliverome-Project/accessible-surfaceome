"""Ask one model (Opus or Sonnet) to grade intrinsic endocytic propensity from
sequence + topology. Model-parameterized because ``call_builder`` is Sonnet-locked."""

from __future__ import annotations

import json
import re
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)

from accessible_surfaceome.agents._support.api_retry import messages_create_with_backoff
from accessible_surfaceome.agents._support.payload import cached_system
from accessible_surfaceome.agents.internalization.models import (
    ModelPriorLLMOut,
    ModelPriorTrack,
)
from accessible_surfaceome.agents.internalization.uniprot_isoforms import IsoformContext

OPUS_MODEL = "claude-opus-4-8"
SONNET_MODEL = "claude-sonnet-4-6"
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


def _build_user_prompt(gene_symbol: str, isoforms: list[IsoformContext]) -> str:
    lines = [
        f"Gene symbol: {gene_symbol}",
        "",
        "Grade this protein's INTRINSIC / BASAL endocytic (internalization) "
        "propensity per isoform, using your knowledge of this protein plus the "
        "sequences and topology below. Topology gives the extracellular vs "
        "cytoplasmic (inside/outside) sidedness — endocytic sorting motifs only "
        "function in CYTOPLASMIC regions, so weigh motifs against it. Source is "
        "DeepTMHMM (per-residue inside/outside prediction) where available, else "
        "UniProt topology features (annotated on the canonical isoform).",
        "",
    ]
    for i, iso in enumerate(isoforms, 1):
        lines += [
            f"### Isoform {i}: {iso.isoform_id}"
            + (" (canonical)" if iso.is_canonical else ""),
            f"Length: {iso.length_aa} aa",
            f"Topology ({iso.topology_source}): {iso.topology_summary}",
            "Sequence:",
            iso.sequence,
            "",
        ]
    lines.append(
        "Return a single ```json fenced object matching the required schema."
    )
    return "\n".join(lines)


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


def grade_isoforms_with_model(
    client: Any,
    *,
    model: str,
    system_prompt: str,
    gene_symbol: str,
    isoforms: list[IsoformContext],
    usage_sink: list[Any] | None = None,
) -> ModelPriorTrack:
    out = call_model_structured(
        client,
        model=model,
        system_prompt=system_prompt,
        user_prompt=_build_user_prompt(gene_symbol, isoforms),
        schema=ModelPriorLLMOut,
        usage_sink=usage_sink,
    )
    return ModelPriorTrack(
        model=model,
        overall_grade=out.overall_grade,
        overall_confidence=out.overall_confidence,
        model_reasoning=out.model_reasoning,
        per_isoform=out.per_isoform,
    )
