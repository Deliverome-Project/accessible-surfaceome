"""Generic SSE event-stream loop with custom-tool dispatch.

Encodes the load-bearing patterns from
``shared/managed-agents-client-patterns.md``:

* **Stream-first ordering** — open the stream *before* sending the kickoff
  message, otherwise early events arrive buffered and steering can't react in
  real time.
* **Idle-break gate** — break on ``session.status_terminated`` or
  ``session.status_idle`` only when ``stop_reason.type != "requires_action"``;
  ``requires_action`` is transient (waiting for a tool confirmation or a
  custom-tool result), not terminal.
* **Custom-tool round-trip** — on ``agent.custom_tool_use`` look up the
  handler in the registry, JSON-stringify the Pydantic return, and POST
  ``user.custom_tool_result`` keyed by the original event ID.

This module intentionally does *not* cover lossless reconnect or
``processed_at`` queued/processed gating — those land when we add a
production-grade orchestrator.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Callable, Iterator

from anthropic import Anthropic

logger = logging.getLogger(__name__)


# A handler takes the parsed input dict and returns either a Pydantic model
# (with ``model_dump_json``) or a string. The orchestrator owns the registry.
ToolHandler = Callable[[dict[str, Any]], Any]
ToolRegistry = dict[str, ToolHandler]


def send_user_message(client: Anthropic, *, session_id: str, text: str) -> None:
    client.beta.sessions.events.send(
        session_id,
        events=[{"type": "user.message", "content": [{"type": "text", "text": text}]}],
    )


def send_custom_tool_result(
    client: Anthropic, *, session_id: str, tool_use_id: str, result_text: str, is_error: bool = False
) -> None:
    client.beta.sessions.events.send(
        session_id,
        events=[
            {
                "type": "user.custom_tool_result",
                "custom_tool_use_id": tool_use_id,
                "content": [{"type": "text", "text": result_text}],
                "is_error": is_error,
            }
        ],
    )


def stream_until_done(
    client: Anthropic,
    *,
    session_id: str,
    handlers: ToolRegistry,
    on_event: Callable[[Any], None] | None = None,
) -> Iterator[Any]:
    """Iterate the session event stream, dispatch custom tools, yield raw events.

    Yields each event as it arrives so the caller can render progress / collect
    final messages. Returns when the session is terminated or idle for a
    terminal reason.
    """

    with client.beta.sessions.events.stream(session_id) as stream:
        for event in stream:
            if on_event is not None:
                on_event(event)
            yield event

            evtype = getattr(event, "type", None)

            if evtype == "agent.custom_tool_use":
                _dispatch_custom_tool(client, session_id=session_id, event=event, handlers=handlers)
                continue

            if evtype == "session.status_terminated":
                return

            if evtype == "session.status_idle":
                stop_reason = getattr(event, "stop_reason", None)
                stop_type = getattr(stop_reason, "type", None) if stop_reason is not None else None
                if stop_type == "requires_action":
                    # Waiting on us — handlers above already responded, or
                    # we're paused for a tool_confirmation we don't support yet.
                    continue
                return


def _dispatch_custom_tool(
    client: Anthropic,
    *,
    session_id: str,
    event: Any,
    handlers: ToolRegistry,
) -> None:
    name = getattr(event, "name", None)
    tool_use_id = getattr(event, "id", None)
    raw_input = getattr(event, "input", None) or {}
    if not name or not tool_use_id:
        logger.warning("custom_tool_use event missing name or id: %r", event)
        return
    handler = handlers.get(name)
    if handler is None:
        send_custom_tool_result(
            client,
            session_id=session_id,
            tool_use_id=tool_use_id,
            result_text=json.dumps({"error": f"no handler registered for tool {name!r}"}),
            is_error=True,
        )
        return

    started = time.monotonic()
    try:
        result = handler(raw_input)
    except Exception as exc:
        elapsed = time.monotonic() - started
        logger.exception("custom-tool handler %s raised after %.2fs", name, elapsed)
        send_custom_tool_result(
            client,
            session_id=session_id,
            tool_use_id=tool_use_id,
            result_text=json.dumps({"error": f"{type(exc).__name__}: {exc}"}),
            is_error=True,
        )
        return

    elapsed = time.monotonic() - started
    logger.info("custom-tool %s returned in %.2fs", name, elapsed)

    if hasattr(result, "model_dump_json"):
        text = result.model_dump_json(indent=2)
    elif isinstance(result, str):
        text = result
    else:
        text = json.dumps(result, default=str, indent=2)

    send_custom_tool_result(
        client,
        session_id=session_id,
        tool_use_id=tool_use_id,
        result_text=text,
    )


def collect_text(events: Iterator[Any]) -> str:
    """Drain ``stream_until_done`` and return the agent's concatenated text output."""

    parts: list[str] = []
    for event in events:
        if getattr(event, "type", None) != "agent.message":
            continue
        for block in getattr(event, "content", None) or []:
            if getattr(block, "type", None) == "text":
                parts.append(block.text)
    return "".join(parts)
