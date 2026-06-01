"""Messages-API runner for the Biology Compiler (A2).

A2 is a single-shot tool-use loop, mirroring A1. We read the system prompt
from disk, expose the three custom tools (``gene_lookup``,
``gene_literature``, ``evidence_retrieval``), and loop ``messages.create``
until the model stops with a final fenced JSON block — which we validate as
a :class:`BiologicalContextDraft`.

Same Managed-Agents reasoning as A1: A2 writes no files, runs no bash, and
the orchestrator owns persistence + ledger merging. The tool handlers are
shared via ``agents._support.tool_registry`` — no duplication.

Run directly for a real test:

    uv run python -m accessible_surfaceome.agents.biology_compiler.runner EGFR
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

from anthropic import Anthropic
from anthropic.types import TextBlock, ToolUseBlock
from pydantic import BaseModel, ValidationError

from accessible_surfaceome.agents._support.client import get_client
from accessible_surfaceome.agents._support import tool_registry
from accessible_surfaceome.agents._support.payload import (
    cached_system,
    compact_for_agent_transport,
    mark_latest_tool_result_for_cache,
)
from accessible_surfaceome.agents._support.pricing import (
    UsageRecord,
    UsageSummary,
    record_from_response,
    summarize_usage,
)
from accessible_surfaceome.tools._shared import retraction_watch as _retraction_watch
from accessible_surfaceome.tools._shared.http import CachedHTTP, open_default_client
from accessible_surfaceome.tools._shared.models import BiologicalContextDraft
from accessible_surfaceome.tools._shared.retraction_watch import RetractionIndex
from accessible_surfaceome.tools._shared.source_text import SourceTextStore

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent / "prompts"
SYSTEM_PROMPT_PATH = PROMPTS_DIR / "system.md"

AGENT_MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 16000
MAX_ITERATIONS = 30
# When the emitted JSON fails Pydantic validation (or no JSON is found), feed
# the errors back and let the model correct itself. The category-conditional
# sub-enum validators on AccessibilityModulationObservation are the common
# trip-up here.
MAX_REPAIRS = 2

# Server tools Anthropic executes host-side. Left empty for now — same as A1.
_SERVER_TOOLS: list[dict[str, Any]] = []

_FENCED_JSON_RE = re.compile(r"```(?:json)?\s*(\{.*\})\s*```", re.DOTALL)


@dataclass
class ToolCall:
    """One custom-tool invocation — name, salient input, ok/error."""

    name: str
    input_summary: str
    is_error: bool


@dataclass
class A2Result:
    """Outcome of one A2 run — valid draft, invalid JSON, or no JSON at all."""

    gene: str
    draft: BiologicalContextDraft | None
    raw_json: dict[str, Any] | None
    final_text: str
    validation_error: str | None
    n_tool_calls: int
    n_repair_attempts: int = 0
    tool_calls: list[ToolCall] = field(default_factory=list)
    messages: list[dict[str, Any]] = field(default_factory=list)
    usage: UsageSummary = field(
        default_factory=lambda: UsageSummary(model=AGENT_MODEL)
    )


def _summarize_tool_input(name: str, payload: dict[str, Any]) -> str:
    """Compact one-line summary of the tool input, for the call log."""
    if name == "gene_lookup":
        return f"{payload.get('mode', '?')}({payload.get('symbol_or_acc', '?')})"
    if name == "gene_literature":
        mode = payload.get("mode", "?")
        extras: list[str] = []
        if "uniprot_acc" in payload:
            extras.append(payload["uniprot_acc"])
        if "topic_anchors" in payload:
            extras.append("+".join(payload["topic_anchors"]))
        if "pmcid" in payload:
            extras.append(payload["pmcid"])
        if "pmid" in payload:
            extras.append(str(payload["pmid"]))
        return f"{mode}({', '.join(extras) or '-'})"
    if name == "evidence_retrieval":
        return f"{payload.get('category', '?')}({payload.get('uniprot_acc', '?')})"
    keys = ",".join(sorted(payload.keys()))
    return f"({keys})"


def _custom_tool_defs() -> list[dict[str, Any]]:
    """Messages-API custom-tool defs from the shared registry.

    ``tool_registry.custom_tool_definitions()`` emits the Managed-Agents
    ``{"type": "custom", ...}`` shape; the Messages API wants a bare
    ``{name, description, input_schema}``.
    """
    return [
        {
            "name": spec.name,
            "description": spec.description,
            "input_schema": spec.input_schema,
        }
        for spec in tool_registry.SPECS
    ]


def _serialize_tool_result(result: Any) -> str:
    if isinstance(result, str):
        return result
    if isinstance(result, BaseModel):
        return result.model_dump_json()
    return json.dumps(result, default=str)


def _extract_json(text: str) -> dict[str, Any] | None:
    """Last fenced JSON block wins — the model may show intermediate examples."""
    matches = _FENCED_JSON_RE.findall(text)
    if not matches:
        return None
    try:
        return json.loads(matches[-1])
    except json.JSONDecodeError:
        return None


def _build_task(gene: str) -> str:
    schema = json.dumps(BiologicalContextDraft.model_json_schema(), indent=2)
    return (
        f"Compile the `biological_context` block for the human gene **{gene}**.\n\n"
        "Resolve the gene with `gene_lookup` first, then gather "
        "tissue / cell-type / cell-state / anatomical / modulation evidence "
        "with `evidence_retrieval`. Honor the category-conditional sub-enum "
        "pairings on `accessibility_modulation`. When done, emit exactly one "
        "fenced ```json block as your final message — no prose around it — "
        "matching this `BiologicalContextDraft` JSON schema:\n\n"
        f"```json\n{schema}\n```\n"
    )


def run_biology_compiler(
    gene: str,
    *,
    client: Anthropic | None = None,
    http: CachedHTTP | None = None,
    source_store: SourceTextStore | None = None,
    retraction_index: RetractionIndex | None = None,
) -> A2Result:
    """Run A2 against one gene and return the validated draft (or the failure).

    ``source_store`` and ``retraction_index`` are accepted so the orchestrator
    can share a single store + index across A1 / A2 in a parallel dispatch.
    """
    client = client or get_client()
    own_http = http is None
    http = http or open_default_client()
    try:
        return _run(
            client, http, gene,
            source_store=source_store, retraction_index=retraction_index,
        )
    finally:
        if own_http:
            http.close()


def _run(
    client: Anthropic,
    http: CachedHTTP,
    gene: str,
    *,
    source_store: SourceTextStore | None = None,
    retraction_index: RetractionIndex | None = None,
) -> A2Result:
    system_prompt = SYSTEM_PROMPT_PATH.read_text()
    if source_store is None:
        source_store = SourceTextStore()
    if retraction_index is None:
        retraction_index = _retraction_watch.from_http(http)
    handlers = tool_registry.build_handlers(
        http, source_store=source_store, retraction_index=retraction_index
    )
    tools = _custom_tool_defs() + _SERVER_TOOLS

    messages: list[dict[str, Any]] = [{"role": "user", "content": _build_task(gene)}]
    n_tool_calls = 0
    n_repair_attempts = 0
    tool_calls: list[ToolCall] = []
    usage_records: list[UsageRecord] = []
    final_text = ""
    raw_json: dict[str, Any] | None = None
    validation_error: str | None = None

    cached_system_blocks = cached_system(system_prompt)
    for _ in range(MAX_ITERATIONS):
        # Rotate the rolling cache breakpoint onto the most recent tool_result
        # (no-op on iteration 1; from iteration 2 on, ~95% of input is a
        # cache hit at 0.1× the base rate).
        mark_latest_tool_result_for_cache(messages)
        # cast: tool / message dicts are SDK-shaped at runtime, but the SDK's
        # TypedDict params don't accept a bare list[dict[str, Any]].
        resp = client.messages.create(
            model=AGENT_MODEL,
            max_tokens=MAX_TOKENS,
            system=cast("Any", cached_system_blocks),
            tools=cast("Any", tools),
            messages=cast("Any", messages),
        )
        usage_records.append(record_from_response(resp.usage, AGENT_MODEL))
        messages.append({"role": "assistant", "content": resp.content})

        # --- tool-use turn: dispatch handlers, feed results back ---
        if resp.stop_reason == "tool_use":
            tool_results: list[dict[str, Any]] = []
            for block in resp.content:
                if not isinstance(block, ToolUseBlock):
                    continue  # text / server_tool_use — handled host-side
                handler = handlers.get(block.name)
                if handler is None:
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(
                                {"error": f"no handler for tool {block.name!r}"}
                            ),
                            "is_error": True,
                        }
                    )
                    continue
                n_tool_calls += 1
                payload = dict(block.input)
                input_summary = _summarize_tool_input(block.name, payload)
                try:
                    result = handler(payload)
                    # Handler already registered the unstripped body into
                    # SourceTextStore; compact for transport drops the heavy
                    # paper.sections fields the agent doesn't need.
                    content = _serialize_tool_result(compact_for_agent_transport(result))
                    is_error = False
                except Exception as exc:  # noqa: BLE001
                    logger.warning("A2 tool %s failed: %s", block.name, exc)
                    content = json.dumps({"error": str(exc)})
                    is_error = True
                logger.info(
                    "A2 tool %s %s %s",
                    block.name,
                    input_summary,
                    "ERR" if is_error else "ok",
                )
                tool_calls.append(
                    ToolCall(name=block.name, input_summary=input_summary, is_error=is_error)
                )
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": content,
                        "is_error": is_error,
                    }
                )
            if not tool_results:
                break
            messages.append({"role": "user", "content": tool_results})
            continue

        # --- the model thinks it's done: extract + validate ---
        final_text = "".join(b.text for b in resp.content if isinstance(b, TextBlock))
        raw_json = _extract_json(final_text)

        if raw_json is None:
            if n_repair_attempts >= MAX_REPAIRS:
                break
            n_repair_attempts += 1
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "I could not find a fenced ```json block in your reply. "
                        "Emit exactly one fenced ```json block containing the "
                        "BiologicalContextDraft, with no prose around it."
                    ),
                }
            )
            continue

        try:
            draft = BiologicalContextDraft.model_validate(raw_json)
        except ValidationError as exc:
            validation_error = str(exc)
            if n_repair_attempts >= MAX_REPAIRS:
                break
            n_repair_attempts += 1
            logger.info(
                "A2 repair %d/%d for %s — %d validation error(s)",
                n_repair_attempts,
                MAX_REPAIRS,
                gene,
                exc.error_count(),
            )
            messages.append(
                {
                    "role": "user",
                    "content": (
                        f"Your JSON failed schema validation with "
                        f"{exc.error_count()} error(s):\n\n{validation_error[:2000]}\n\n"
                        "Emit a corrected BiologicalContextDraft as one fenced ```json "
                        "block. Respect every maxLength in the schema — quotes must "
                        "stay ≤200 chars and verbatim; trim prose fields to fit. "
                        "Honor the AccessibilityModulationObservation sub-enum pairings: "
                        "cell_state_trigger only with state-induced categories, "
                        "restricted_lineage only with tissue_restricted_surface, "
                        "dual_loc_partner_compartment only with dual_localization, "
                        "category_other_label only when category=='other'."
                    ),
                }
            )
            continue

        return A2Result(
            gene=gene,
            draft=draft,
            raw_json=raw_json,
            final_text=final_text,
            validation_error=None,
            n_tool_calls=n_tool_calls,
            n_repair_attempts=n_repair_attempts,
            tool_calls=tool_calls,
            messages=messages,
            usage=summarize_usage(usage_records, AGENT_MODEL),
        )
    else:
        logger.warning("A2 hit MAX_ITERATIONS=%d for %s", MAX_ITERATIONS, gene)

    return A2Result(
        gene=gene,
        draft=None,
        raw_json=raw_json,
        final_text=final_text,
        validation_error=validation_error,
        n_tool_calls=n_tool_calls,
        n_repair_attempts=n_repair_attempts,
        tool_calls=tool_calls,
        messages=messages,
        usage=summarize_usage(usage_records, AGENT_MODEL),
    )


def _main(argv: list[str] | None = None) -> int:
    import sys

    from accessible_surfaceome.env import load_env

    # python -m ... bypasses the CLI entry point that normally loads .env;
    # load it here so ANTHROPIC_API_KEY / NCBI_API_KEY resolve.
    load_env()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )
    args = argv if argv is not None else sys.argv[1:]
    gene = args[0] if args else "EGFR"

    result = run_biology_compiler(gene)

    print(f"\n=== A2 result for {gene} ===")
    print(f"tool calls: {result.n_tool_calls}  repair attempts: {result.n_repair_attempts}")
    print(
        f"tokens: in={result.usage.input_tokens} out={result.usage.output_tokens} "
        f"cache_w={result.usage.cache_creation_input_tokens} "
        f"cache_r={result.usage.cache_read_input_tokens}  "
        f"cost: ${result.usage.cost_usd:.4f}"
    )

    # Per-tool breakdown
    from collections import Counter

    by_tool = Counter(tc.name for tc in result.tool_calls)
    err_by_tool = Counter(tc.name for tc in result.tool_calls if tc.is_error)
    for tool_name in sorted(by_tool):
        total = by_tool[tool_name]
        errs = err_by_tool.get(tool_name, 0)
        err_note = f" ({errs} err)" if errs else ""
        print(f"  {tool_name}: {total}{err_note}")

    run_dir = Path(".runs")
    run_dir.mkdir(exist_ok=True)

    # Always persist the tool-call trace + counters for diagnosability,
    # regardless of validation outcome.
    meta = {
        "gene": gene,
        "n_tool_calls": result.n_tool_calls,
        "n_repair_attempts": result.n_repair_attempts,
        "tool_calls": [
            {"name": tc.name, "input": tc.input_summary, "error": tc.is_error}
            for tc in result.tool_calls
        ],
        "validation_error": result.validation_error,
        "usage": result.usage.as_dict(),
    }
    meta_out = run_dir / f"a2_{gene}.meta.json"
    meta_out.write_text(json.dumps(meta, indent=2))

    if result.draft is not None:
        bc = result.draft.biological_context
        print(
            f"VALID  expression={len(bc.expression)}  "
            f"cell_states={len(bc.cell_states)}  "
            f"anatomical={len(bc.anatomical_accessibility)}  "
            f"modulation={len(bc.accessibility_modulation)}  "
            f"claims={len(result.draft.evidence_claims)}"
        )
        out = run_dir / f"a2_{gene}.json"
        out.write_text(result.draft.model_dump_json(indent=2))
        print(f"written: {out}, {meta_out}")
        return 0
    if result.raw_json is not None:
        print(f"INVALID — emitted JSON failed validation:\n{result.validation_error}")
        out = run_dir / f"a2_{gene}.invalid.json"
        out.write_text(json.dumps(result.raw_json, indent=2))
        print(f"written: {out}")
        return 1
    print("NO JSON emitted. Final text (first 2000 chars):")
    print(result.final_text[:2000])
    return 1


if __name__ == "__main__":
    raise SystemExit(_main())
