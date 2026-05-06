"""Session lifecycle for the surface annotator.

Two entry points:

* :func:`sync_agent_and_environment` — create-or-update the remote agent and
  environment, persist IDs + drift-detection hashes to the registry. Idempotent.
  Run after editing the system prompt or any other agent field.

* :func:`annotate_gene` — open one session for one gene, run the agent through
  the ``gene_lookup`` cascade, persist the resulting :class:`GeneAnnotation`
  JSON to ``data/annotations/{symbol}.json``, and write a run log under
  ``.runs/<timestamp>-<symbol>-<session_id>/``.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from anthropic import Anthropic

from pydantic import ValidationError

from accessible_surfaceome.paths import DATA_DIR, DATA_SOURCES_DIR, REPO_ROOT
from accessible_surfaceome.tools._shared.http import CachedHTTP, open_default_client
from accessible_surfaceome.tools._shared.models import (
    Evidence,
    SurfaceomeRecord,
    SurfaceomeRecordDraft,
)
from accessible_surfaceome.tools._shared.source_text import SourceTextStore

from .._support import client as _client_module
from .._support import registry as _registry
from .._support.events import (
    collect_text,
    send_user_message,
    stream_until_done,
)
from . import agent as _agent
from . import environment as _environment
from . import tool_registry
from .evidence_promotion import build_search_log, promote_claim

logger = logging.getLogger(__name__)


@dataclass
class SyncResult:
    agent_id: str
    agent_version: int | None
    environment_id: str
    agent_changed: bool
    environment_changed: bool


def sync_agent_and_environment(client: Anthropic | None = None) -> SyncResult:
    client = client or _client_module.get_client()
    reg = _registry.load()

    env_entry = reg.environments.get(_environment.ENVIRONMENT_NAME)
    env_blob_sha = _registry.sha256(_environment.environment_config_blob())
    env_changed = env_entry is None or env_entry.config_sha256 != env_blob_sha
    if env_changed:
        env = _environment.upsert_environment(
            client,
            current_id=env_entry.id if env_entry else None,
        )
        env_id = env.id
        reg.environments[_environment.ENVIRONMENT_NAME] = _registry.EnvironmentEntry(
            id=env_id, config_sha256=env_blob_sha
        )
    else:
        env_id = env_entry.id  # type: ignore[union-attr]

    agent_entry = reg.agents.get(_agent.AGENT_NAME)
    system_sha = _registry.sha256(_agent.read_system_prompt())
    # Naive drift check: the system prompt sha is the dominant source of change.
    # Tool list / model are version-controlled and changes there will also bump
    # the agent's remote version, but we don't independently sha them — the
    # registry entry just tracks "did we last sync this prompt".
    agent_changed = agent_entry is None or agent_entry.system_prompt_sha256 != system_sha
    if agent_changed:
        agent = _agent.upsert_agent(
            client,
            current_id=agent_entry.id if agent_entry else None,
            current_version=agent_entry.version if agent_entry else None,
        )
        reg.agents[_agent.AGENT_NAME] = _registry.AgentEntry(
            id=agent.id,
            version=getattr(agent, "version", None),
            system_prompt_sha256=system_sha,
        )

    _registry.save(reg)
    final = reg.agents[_agent.AGENT_NAME]
    return SyncResult(
        agent_id=final.id,
        agent_version=final.version,
        environment_id=env_id,
        agent_changed=agent_changed,
        environment_changed=env_changed,
    )


# ---------------------------------------------------------------------------
# Per-gene run
# ---------------------------------------------------------------------------


@dataclass
class AnnotateResult:
    session_id: str
    annotation_path: Path | None
    invalid_path: Path | None
    run_dir: Path
    final_text: str
    annotation_json: dict[str, Any] | None
    n_tool_calls: int
    validation_status: Literal["valid", "invalid", "missing"]
    validation_errors: list[dict[str, Any]] | None


def annotate_gene(
    gene: str,
    *,
    client: Anthropic | None = None,
    http: CachedHTTP | None = None,
) -> AnnotateResult:
    client = client or _client_module.get_client()
    own_http = http is None
    http_client = http or open_default_client()
    try:
        return _annotate_one(client, http_client, gene)
    finally:
        if own_http:
            http_client.close()


def _annotate_one(client: Anthropic, http: CachedHTTP, gene: str) -> AnnotateResult:
    reg = _registry.load()
    if _agent.AGENT_NAME not in reg.agents or _environment.ENVIRONMENT_NAME not in reg.environments:
        raise RuntimeError(
            "agent or environment missing from registry — run `accessible-surfaceome agents sync` first"
        )
    agent_entry = reg.agents[_agent.AGENT_NAME]
    env_entry = reg.environments[_environment.ENVIRONMENT_NAME]

    source_store = SourceTextStore()
    handlers = tool_registry.build_handlers(http, source_store=source_store)
    task_text = _render_task(gene)

    session = client.beta.sessions.create(
        agent={"type": "agent", "id": agent_entry.id, "version": agent_entry.version}
        if agent_entry.version
        else agent_entry.id,
        environment_id=env_entry.id,
        title=f"annotate {gene}",
    )
    logger.info("created session %s for %s", session.id, gene)

    timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%S")
    run_dir = REPO_ROOT / ".runs" / f"{timestamp}-{gene}-{session.id}"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "task.md").write_text(task_text)

    events_path = run_dir / "events.jsonl"
    n_tool_calls = 0

    def _log_event(event: Any) -> None:
        nonlocal n_tool_calls
        if getattr(event, "type", None) == "agent.custom_tool_use":
            n_tool_calls += 1
        with events_path.open("a") as f:
            f.write(_event_to_json_line(event))
            f.write("\n")

    # Stream-first: open the stream BEFORE sending the kickoff message,
    # otherwise early events arrive buffered and we lose live ordering.
    stream = stream_until_done(client, session_id=session.id, handlers=handlers, on_event=_log_event)
    send_user_message(client, session_id=session.id, text=task_text)
    final_text = collect_text(stream)

    (run_dir / "final.md").write_text(final_text)
    annotation_json = _extract_annotation_json(final_text)

    annotation_path, invalid_path, validation_status, validation_errors = _persist_annotation(
        gene=gene,
        annotation_json=annotation_json,
        run_dir=run_dir,
        source_store=source_store,
    )
    if validation_status == "invalid":
        logger.warning(
            "annotation for %s failed Pydantic validation; persisted to %s for review",
            gene,
            invalid_path,
        )

    # Persist the source corpus so any future UI / re-validation can render
    # quote-in-context and verify hashes without re-fetching upstream. Run
    # regardless of annotation validation status — the sources are still
    # canonical even when the agent's record didn't validate.
    sources_written = source_store.persist_to_disk(DATA_SOURCES_DIR)
    logger.info(
        "persisted %d source bodies to %s",
        len(sources_written),
        DATA_SOURCES_DIR,
    )

    summary = {
        "gene": gene,
        "session_id": session.id,
        "agent_id": agent_entry.id,
        "agent_version": agent_entry.version,
        "environment_id": env_entry.id,
        "n_custom_tool_calls": n_tool_calls,
        "annotation_path": str(annotation_path) if annotation_path else None,
        "invalid_path": str(invalid_path) if invalid_path else None,
        "validation_status": validation_status,
        "validation_errors": validation_errors,
        "annotation_json": annotation_json,
        "final_text_chars": len(final_text),
        "sources_persisted": {sid: str(p) for sid, p in sources_written.items()},
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")

    return AnnotateResult(
        session_id=session.id,
        annotation_path=annotation_path,
        invalid_path=invalid_path,
        run_dir=run_dir,
        final_text=final_text,
        annotation_json=annotation_json,
        n_tool_calls=n_tool_calls,
        validation_status=validation_status,
        validation_errors=validation_errors,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _render_task(gene: str) -> str:
    template = (Path(__file__).parent / "prompts" / "task_template.md").read_text()
    return template.replace("{gene}", gene)


_FENCED_JSON_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def _persist_annotation(
    *,
    gene: str,
    annotation_json: dict[str, Any] | None,
    run_dir: Path,
    source_store: SourceTextStore,
) -> tuple[Path | None, Path | None, Literal["valid", "invalid", "missing"], list[dict[str, Any]] | None]:
    """Promote the agent's ``SurfaceomeRecordDraft`` and persist as ``SurfaceomeRecord``.

    Pipeline:

    1. Parse the agent's JSON as a :class:`SurfaceomeRecordDraft` (which
       carries ``evidence_claims: list[EvidenceClaim]``).
    2. Promote each claim to an :class:`Evidence` via
       :func:`promote_claim` — substring-anchor against the cached
       ``SourceTextStore``, fail soft with ``entailment_verified=False``
       and a warning when the quote doesn't match.
    3. Build the ``search_log`` from ``run_dir/events.jsonl``, populating
       ``contributed_evidence_ids`` from each Evidence's cited source_ids.
    4. Construct the canonical :class:`SurfaceomeRecord` and write it.

    Returns ``(annotation_path, invalid_path, validation_status, validation_errors)``:

    - ``valid`` — draft parsed, promoted, and the resulting record validated.
      Persisted to ``data/annotations/{gene}.json``.
    - ``invalid`` — JSON parsed but the draft (or the constructed record)
      failed Pydantic validation. The agent's raw payload is persisted to
      ``run_dir/{gene}.invalid.json`` for review.
    - ``missing`` — agent didn't emit a JSON block at all.

    Why we don't crash on validation failure: the agent's tool calls, final
    text, and run log are still useful for debugging. The summary.json
    documents what went wrong without losing the rest of the run.
    """

    if annotation_json is None:
        return None, None, "missing", None

    try:
        draft = SurfaceomeRecordDraft.model_validate(annotation_json)
    except ValidationError as exc:
        invalid_path = _write_invalid(annotation_json, gene=gene, run_dir=run_dir)
        return None, invalid_path, "invalid", [{**e} for e in exc.errors()]

    evidence: list[Evidence] = [
        promote_claim(claim, store=source_store) for claim in draft.evidence_claims
    ]

    contributed_by: dict[str, list[str]] = {}
    for evi in evidence:
        for span in evi.spans:
            contributed_by.setdefault(span.source.source_id, []).append(evi.evidence_id)

    search_log = build_search_log(run_dir / "events.jsonl", contributed_by=contributed_by)

    primary = sum(1 for e in evidence if e.evidence_tier == "primary")
    secondary = sum(1 for e in evidence if e.evidence_tier == "secondary")

    try:
        record = SurfaceomeRecord(
            schema_version=draft.schema_version,
            gene=draft.gene,
            canonical_isoform=draft.canonical_isoform,
            isoform_flattened=draft.isoform_flattened,
            targetability=draft.targetability,
            surface_biology=draft.surface_biology,
            expression=draft.expression,
            adc_properties=draft.adc_properties,
            therapeutic_landscape=draft.therapeutic_landscape,
            risk_flags=draft.risk_flags,
            evidence=evidence,
            primary_evidence_count=primary,
            secondary_evidence_count=secondary,
            evidence_count=len(evidence),
            search_log=search_log,
            confidence=draft.confidence,
            confidence_reasoning=draft.confidence_reasoning,
            contradiction_flag=draft.contradiction_flag,
            rationale=draft.rationale,
            model_path=draft.model_path,
        )
    except ValidationError as exc:
        invalid_path = _write_invalid(annotation_json, gene=gene, run_dir=run_dir)
        return None, invalid_path, "invalid", [{**e} for e in exc.errors()]

    annotation_dir = DATA_DIR / "annotations"
    annotation_dir.mkdir(parents=True, exist_ok=True)
    annotation_path = annotation_dir / f"{gene}.json"
    annotation_path.write_text(record.model_dump_json(indent=2) + "\n")
    return annotation_path, None, "valid", None


def _write_invalid(
    annotation_json: dict[str, Any], *, gene: str, run_dir: Path
) -> Path:
    invalid_path = run_dir / f"{gene}.invalid.json"
    invalid_path.write_text(json.dumps(annotation_json, indent=2, sort_keys=True) + "\n")
    return invalid_path


def _extract_annotation_json(text: str) -> dict[str, Any] | None:
    """Find and parse the agent's final ``SurfaceomeRecord`` JSON block.

    The system prompt asks the agent to emit a single fenced JSON block as its
    final response. We pick the *last* ``json``-fenced block that parses and
    looks record-shaped — has ``gene`` and either ``surface_biology`` (current
    schema) or ``surface_status`` (legacy proof-of-concept shape).
    """

    candidates = _FENCED_JSON_RE.findall(text)
    for raw in reversed(candidates):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(data, dict) or "gene" not in data:
            continue
        if "surface_biology" in data or "surface_status" in data:
            return data
    return None


def _event_to_json_line(event: Any) -> str:
    """Best-effort serialization of an SDK event for the run log."""

    if hasattr(event, "model_dump_json"):
        try:
            return event.model_dump_json()
        except Exception:
            pass
    if hasattr(event, "model_dump"):
        try:
            return json.dumps(event.model_dump(), default=str)
        except Exception:
            pass
    return json.dumps({"type": getattr(event, "type", "unknown"), "repr": repr(event)})
