"""Shared scaffolding for v2 block-builders.

Each block-builder is a focused Sonnet call that turns an ``EvidenceClaim``
ledger slice + the target schema into a structured block. The pattern is
identical across all nine builders, so it lives here:

1. Read a per-builder system prompt from disk.
2. Format the user prompt as: gene context + claim ledger (JSON) + target
   JSON schema.
3. Call Sonnet with a repair loop (max 2 retries) until the JSON parses
   and validates.
4. Record token usage via :func:`record_from_response`.

Designed for code reuse only — there's no behavioural opinion here.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, TypeVar, cast

from anthropic import Anthropic
from anthropic.types import TextBlock
from pydantic import BaseModel, ValidationError

from accessible_surfaceome.agents._support.api_retry import (
    messages_create_with_backoff,
)
from accessible_surfaceome.agents._support.model_config import deep_dive_model
from accessible_surfaceome.agents._support.payload import cached_system
from accessible_surfaceome.agents._support.pricing import (
    UsageRecord,
    record_from_response,
)
from accessible_surfaceome.tools._shared.models import EvidenceClaim

logger = logging.getLogger(__name__)

SONNET_MODEL = deep_dive_model()  # SURFACEOME_DEEP_DIVE_MODEL override
# Default per-builder output cap. Raised from 8k → 16k on 2026-05-16 after
# the EGFR end-to-end run hit ``stop_reason="max_tokens"`` on
# ``methods_builder`` (55 A1 claims → 19 MethodObservation rows with
# antibody + expression_observations sub-structures). The repair loop
# recovered but burned a second Sonnet call (~$0.40 vs ~$0.20 expected).
# Heavy builders override via ``MAX_TOKENS_HEAVY`` so a 55+ claim ledger
# completes in one round-trip.
MAX_TOKENS_BLOCK = 16_000
# Cap for known-heavy builders that emit dense lists of nested objects
# (methods, tissues, accessibility_modulation, evidence_grade). Each
# row in these blocks carries multiple sub-records (antibodies,
# expression_observations, non_surface_expression, etc.), so per-row
# token cost can be 200-400. At 30 rows that's 6-12k tokens before
# prose padding — 32k gives comfortable headroom.
MAX_TOKENS_HEAVY = 32_000
MAX_REPAIRS = 2

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"

_FENCED_JSON_RE = re.compile(r"```(?:json)?\s*([\[\{].*?[\]\}])\s*```", re.DOTALL)

T = TypeVar("T", bound=BaseModel)


class _ArrayShapeError(Exception):
    """Internal flag for "top-level JSON wasn't an array" in the repair loop."""


def load_prompt(name: str) -> str:
    """Read a system prompt from the v2 prompts dir.

    Raises ``FileNotFoundError`` (loudly) on missing prompt — a typo on
    the builder side should fail fast before any model call.
    """
    path = PROMPTS_DIR / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"v2 block-builder prompt not found: {path}")
    return path.read_text()


def claims_to_jsonable(claims: list[EvidenceClaim]) -> list[dict[str, Any]]:
    """Compact dict form of each claim for ledger rendering."""
    return [c.model_dump(mode="json") for c in claims]


def format_ledger_block(claims: list[EvidenceClaim], *, header: str = "ledger") -> str:
    """Render the claim ledger as a fenced JSON block the model can read.

    Each entry retains the verbatim ``quote`` + ``assay_context`` +
    ``source_id`` + classification so the builder has everything it
    needs to extract the structured block.
    """
    payload = claims_to_jsonable(claims)
    return f"## {header} ({len(claims)} claims)\n\n```json\n{json.dumps(payload, indent=2, sort_keys=True)}\n```\n"


def format_schema_block(schema: dict[str, Any], *, name: str) -> str:
    """Render the target Pydantic JSON schema."""
    return (
        f"## Target schema — `{name}`\n\n"
        f"```json\n{json.dumps(schema, indent=2, sort_keys=True)}\n```\n"
    )


def _extract_json(text: str, *, expect_array: bool) -> Any | None:
    """Last fenced block wins. Defensive against the model echoing examples."""
    matches = _FENCED_JSON_RE.findall(text)
    if not matches:
        # The model sometimes omits fences entirely on tiny outputs (e.g. an
        # empty list ``[]``). Try a permissive trim.
        stripped = text.strip()
        if (expect_array and stripped.startswith("[")) or (
            not expect_array and stripped.startswith("{")
        ):
            try:
                return json.loads(stripped)
            except json.JSONDecodeError:
                return None
        return None
    try:
        return json.loads(matches[-1])
    except json.JSONDecodeError:
        return None


def call_builder(
    client: Anthropic,
    *,
    system_prompt: str,
    user_prompt: str,
    schema: type[T],
    usage_sink: list[UsageRecord],
    label: str,
    expect_array: bool = False,
    array_item_model: type[BaseModel] | None = None,
    max_tokens: int = MAX_TOKENS_BLOCK,
    tools: list[dict[str, Any]] | None = None,
    meta_sink: dict[str, Any] | None = None,
) -> T | list[BaseModel] | None:
    """Call Sonnet with a repair loop until the emitted JSON validates.

    Returns:
      * Parsed ``schema`` instance when ``expect_array=False``.
      * ``list[array_item_model]`` when ``expect_array=True`` (and
        ``array_item_model`` is provided).
      * ``None`` after ``MAX_REPAIRS`` consecutive failures.

    All four token-bucket counts go into ``usage_sink`` via
    :func:`record_from_response`.

    When ``meta_sink`` is supplied (a caller-owned dict — same pattern
    the existing ``usage_sink`` follows), the helper writes:

      * ``n_repair_attempts`` — count of repair-loop iterations actually
        used (0 when the first emission validated; up to ``MAX_REPAIRS``
        on validation-loop exhaustion).
      * ``validation_error`` — the last validation error message when
        the loop didn't succeed; ``None`` on success.

    Per-call Anthropic identifiers (``api_response_id`` / ``api_model``
    / ``api_stop_reason``) are stamped directly onto each ``UsageRecord``
    via the SDK ``response`` object, so the per-call provenance is on
    ``usage_sink`` already — ``meta_sink`` carries the per-INVOCATION
    repair-loop summary only.
    """
    if expect_array and array_item_model is None:
        raise ValueError("expect_array=True requires array_item_model")

    messages: list[dict[str, Any]] = [{"role": "user", "content": user_prompt}]
    validation_error: str | None = None
    parsed: Any = None
    raw_json: Any = None
    n_repair_attempts: int = 0

    # Cache the (static, per-builder) system prompt — mirrors the synthesizer's
    # cached_system pattern. Cuts cost on repair-loop retries and across genes
    # in a sweep; byte-identical output (cache_control is a transport/billing
    # directive, not a generation change).
    cached_sys = cached_system(system_prompt)

    # When ``tools`` is supplied (today: Anthropic's server-side
    # ``web_search`` for the methods builder's antibody-metadata
    # enrichment), pass it through. The server tool resolves within a
    # single ``create`` call — its extra ``server_tool_use`` /
    # ``web_search_tool_result`` content blocks are non-``TextBlock`` and
    # are ignored by the JSON extraction below, so no tool-loop is needed.
    extra_kwargs: dict[str, Any] = {}
    if tools:
        extra_kwargs["tools"] = tools

    for attempt in range(MAX_REPAIRS + 1):
        try:
            resp = messages_create_with_backoff(
                client,
                model=SONNET_MODEL,
                max_tokens=max_tokens,
                system=cast("Any", cached_sys),
                messages=cast("Any", messages),
                **cast("Any", extra_kwargs),
            )
        except Exception as exc:  # noqa: BLE001 - degrade, never crash the run
            if not extra_kwargs:
                raise
            # The server tool (web_search) errored or isn't enabled on the
            # account. The antibody-metadata enrichment is best-effort, so
            # degrade to the cite-only call rather than hard-failing every
            # deep-dive run.
            logger.warning(
                "%s: web-search-enabled call failed (%s); retrying cite-only",
                label,
                exc,
            )
            extra_kwargs = {}
            resp = messages_create_with_backoff(
                client,
                model=SONNET_MODEL,
                max_tokens=max_tokens,
                system=cast("Any", cached_sys),
                messages=cast("Any", messages),
            )
        usage_sink.append(
            record_from_response(resp.usage, SONNET_MODEL, response=resp)
        )
        final_text = "\n".join(
            b.text for b in resp.content if isinstance(b, TextBlock)
        ).strip()
        # Detect ``max_tokens`` cutoff *before* JSON extraction so the
        # repair-loop log says "output truncated, bump max_tokens" rather
        # than the generic "no fenced JSON block" — the symptom is the
        # same (unclosed fenced block) but the fix is different. Sonnet's
        # ``stop_reason`` is one of: ``end_turn``, ``max_tokens``,
        # ``stop_sequence``, ``tool_use``.
        if getattr(resp, "stop_reason", None) == "max_tokens":
            logger.warning(
                "%s hit max_tokens cutoff at %d (output_tokens=%d). "
                "Bump max_tokens for this builder.",
                label,
                max_tokens,
                resp.usage.output_tokens,
            )
        raw_json = _extract_json(final_text, expect_array=expect_array)
        if raw_json is None:
            if getattr(resp, "stop_reason", None) == "max_tokens":
                validation_error = (
                    f"output truncated at max_tokens={max_tokens} "
                    f"(wrote {resp.usage.output_tokens} tokens, "
                    "fenced JSON block was not closed). Retry will "
                    "re-emit from scratch; persistent failures indicate "
                    "max_tokens needs to be raised for this builder."
                )
            else:
                validation_error = "no fenced JSON block in model output"
        else:
            try:
                if expect_array:
                    if not isinstance(raw_json, list):
                        validation_error = (
                            "expected a JSON array at top level, "
                            f"got {type(raw_json).__name__}"
                        )
                        raise _ArrayShapeError(validation_error)
                    assert array_item_model is not None  # for ty
                    parsed = [array_item_model.model_validate(it) for it in raw_json]
                    if meta_sink is not None:
                        meta_sink["n_repair_attempts"] = n_repair_attempts
                        meta_sink["validation_error"] = None
                    return parsed
                else:
                    parsed = schema.model_validate(raw_json)
                    if meta_sink is not None:
                        meta_sink["n_repair_attempts"] = n_repair_attempts
                        meta_sink["validation_error"] = None
                    return parsed
            except ValidationError as exc:
                validation_error = str(exc)
            except _ArrayShapeError:
                # validation_error already set above
                pass
        # The current attempt failed (no fenced JSON or schema-invalid);
        # bump the repair counter before logging so the printed
        # "repair N/MAX" matches the next call's iteration count.
        n_repair_attempts += 1
        logger.info(
            "%s repair %d/%d — %s",
            label,
            attempt + 1,
            MAX_REPAIRS,
            (validation_error or "")[:200],
        )
        messages.append({"role": "assistant", "content": final_text})
        messages.append(
            {
                "role": "user",
                "content": (
                    "Your JSON failed schema validation:\n\n"
                    f"{(validation_error or '')[:2000]}\n\n"
                    "Emit a corrected JSON "
                    + ("array" if expect_array else "object")
                    + " as ONE fenced ```json block — no prose around it. "
                    "Respect the schema exactly: every enum value verbatim, no extra "
                    "fields, all required fields present."
                ),
            }
        )
    logger.warning("%s validation failed after %d repairs", label, MAX_REPAIRS)
    if meta_sink is not None:
        meta_sink["n_repair_attempts"] = n_repair_attempts
        meta_sink["validation_error"] = validation_error
    return None


def filter_by_evidence_type(
    claims: list[EvidenceClaim], allowed: set[str]
) -> list[EvidenceClaim]:
    return [c for c in claims if c.evidence_type in allowed]


def filter_by_claim_type(
    claims: list[EvidenceClaim], allowed: set[str]
) -> list[EvidenceClaim]:
    return [c for c in claims if c.claim_type in allowed]


__all__ = [
    "MAX_REPAIRS",
    "MAX_TOKENS_BLOCK",
    "MAX_TOKENS_HEAVY",
    "PROMPTS_DIR",
    "SONNET_MODEL",
    "call_builder",
    "claims_to_jsonable",
    "filter_by_claim_type",
    "filter_by_evidence_type",
    "format_ledger_block",
    "format_schema_block",
    "load_prompt",
]
