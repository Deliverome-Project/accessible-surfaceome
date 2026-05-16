"""A1 → ``TherapeuticEngagementContext | None``.

Single-row builder. Emits None when the ledger documents no therapeutic
engaging the protein at the cell surface.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, cast

from anthropic import Anthropic
from anthropic.types import TextBlock
from pydantic import ValidationError

from accessible_surfaceome.agents._support.pricing import (
    UsageRecord,
    record_from_response,
)
from accessible_surfaceome.agents.surfaceome_v2.builders._common import (
    MAX_REPAIRS,
    MAX_TOKENS_BLOCK,
    SONNET_MODEL,
    format_ledger_block,
    format_schema_block,
    load_prompt,
)
from accessible_surfaceome.tools._shared.models import (
    EvidenceClaim,
    TherapeuticEngagementContext,
)

logger = logging.getLogger(__name__)

_FENCED_JSON_RE = re.compile(r"```(?:json)?\s*(\{.*?\}|null)\s*```", re.DOTALL)


def build_therapeutic_engagement(
    claims: list[EvidenceClaim],
    *,
    client: Anthropic,
    usage_sink: list[UsageRecord],
    context: dict[str, Any] | None = None,
) -> TherapeuticEngagementContext | None:
    """Extract the therapeutic-engagement block from an A1 ledger.

    Returns ``None`` when no qualifying claims exist or the model emits
    ``null``.
    """
    context = context or {}
    if not claims:
        return None
    gene = context.get("gene", "<unknown>")
    system_prompt = load_prompt("therapeutic_engagement_builder_system")
    user_prompt = (
        f"# Gene: {gene}\n\n"
        f"{format_ledger_block(claims, header='A1 ledger (full)')}\n"
        f"{format_schema_block(TherapeuticEngagementContext.model_json_schema(), name='TherapeuticEngagementContext')}\n"
        "Emit ONE fenced ```json block. EITHER a JSON object matching the "
        "schema OR the literal `null`. No prose around it.\n"
    )

    known_ids = {c.evidence_id for c in claims}
    messages: list[dict[str, Any]] = [{"role": "user", "content": user_prompt}]
    validation_error: str | None = None

    for attempt in range(MAX_REPAIRS + 1):
        resp = client.messages.create(
            model=SONNET_MODEL,
            max_tokens=MAX_TOKENS_BLOCK,
            system=system_prompt,
            messages=cast("Any", messages),
        )
        usage_sink.append(record_from_response(resp.usage, SONNET_MODEL))
        text = "\n".join(
            b.text for b in resp.content if isinstance(b, TextBlock)
        ).strip()
        raw = _extract_object_or_null(text)
        if raw is _SENTINEL:
            validation_error = "no fenced JSON block (object or null) in output"
        elif raw is None:
            return None
        else:
            try:
                parsed = TherapeuticEngagementContext.model_validate(raw)
            except ValidationError as exc:
                validation_error = str(exc)
            else:
                scrubbed = parsed.model_copy(
                    update={
                        "cited_evidence_ids": [
                            i for i in parsed.cited_evidence_ids if i in known_ids
                        ]
                    }
                )
                return scrubbed
        logger.info(
            "therapeutic_engagement_builder repair %d/%d — %s",
            attempt + 1,
            MAX_REPAIRS,
            (validation_error or "")[:200],
        )
        messages.append({"role": "assistant", "content": text})
        messages.append(
            {
                "role": "user",
                "content": (
                    "Your JSON failed schema validation:\n\n"
                    f"{(validation_error or '')[:1500]}\n\n"
                    "Emit a corrected JSON object (or `null`) in ONE fenced "
                    "```json block."
                ),
            }
        )
    logger.warning(
        "therapeutic_engagement_builder validation failed after %d repairs", MAX_REPAIRS
    )
    return None


_SENTINEL = object()


def _extract_object_or_null(text: str) -> Any:
    """Return ``None`` (literal null), a dict, or the sentinel on no match."""
    matches = _FENCED_JSON_RE.findall(text)
    if not matches:
        stripped = text.strip()
        if stripped == "null":
            return None
        if stripped.startswith("{"):
            try:
                return json.loads(stripped)
            except json.JSONDecodeError:
                return _SENTINEL
        return _SENTINEL
    payload = matches[-1].strip()
    if payload == "null":
        return None
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return _SENTINEL


__all__ = ["build_therapeutic_engagement"]
