"""Session lifecycle for the surface triage agent.

Two entry points:

* :func:`sync_agent_and_environment` — create-or-update the remote agent and
  environment, persist IDs + drift-detection hashes to the registry. Idempotent.

* :func:`triage_gene` — open one session for one gene, run the agent, persist
  the resulting :class:`TriageRecord` JSON to ``data/triage/{symbol}.json``,
  and write a run log under ``.runs/<timestamp>-<symbol>-<session_id>/``.

The triage agent is pure-model: no custom tools, no built-in toolset, no
web search, no evidence quotes. The orchestrator resolves the input gene
symbol to a canonical :class:`GeneIdentifier` (via the same UniProt /
HGNC resolution helpers the deep-dive uses) before opening the session,
so the model only sees the symbol in its prompt and emits a minimal JSON
payload.
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

from accessible_surfaceome.paths import DATA_DIR, REPO_ROOT
from accessible_surfaceome.tools._shared.http import CachedHTTP, open_default_client
from accessible_surfaceome.tools._shared.models import (
    GeneIdentifier,
    IdentifierBundle,
    TRIAGE_SCHEMA_VERSION,
    TriageModelPath,
    TriageRecord,
    TriageRecordDraft,
)
from accessible_surfaceome.tools.gene_lookup import gene_lookup

from accessible_surfaceome.agents.surface_annotator.evidence_promotion import (
    build_search_log,
)

from .._support import client as _client_module
from .._support import registry as _registry
from .._support.events import (
    collect_text,
    send_user_message,
    stream_until_done,
)
from . import agent as _agent
from . import environment as _environment

logger = logging.getLogger(__name__)


# Map the agent's configured Anthropic model id to the schema's
# TriageModelPath literal. Adding new models is one-line.
_MODEL_PATH_BY_ID: dict[str, TriageModelPath] = {
    "claude-haiku-4-5": "haiku_only",
    "claude-sonnet-4-6": "sonnet_only",
    "claude-opus-4-7": "opus_only",
}


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
class TriageResult:
    session_id: str
    triage_path: Path | None
    invalid_path: Path | None
    run_dir: Path
    final_text: str
    triage_json: dict[str, Any] | None
    validation_status: Literal["valid", "invalid", "missing"]
    validation_errors: list[dict[str, Any]] | None


def triage_gene(
    gene: str,
    *,
    client: Anthropic | None = None,
    http: CachedHTTP | None = None,
) -> TriageResult:
    client = client or _client_module.get_client()
    own_http = http is None
    http_client = http or open_default_client()
    try:
        return _triage_one(client, http_client, gene)
    finally:
        if own_http:
            http_client.close()


def _triage_one(client: Anthropic, http: CachedHTTP, gene: str) -> TriageResult:
    reg = _registry.load()
    if (
        _agent.AGENT_NAME not in reg.agents
        or _environment.ENVIRONMENT_NAME not in reg.environments
    ):
        raise RuntimeError(
            "triage agent or environment missing from registry — run "
            "`accessible-surfaceome triage sync` first"
        )
    agent_entry = reg.agents[_agent.AGENT_NAME]
    env_entry = reg.environments[_environment.ENVIRONMENT_NAME]

    # Resolve gene identifiers locally — the agent has no tools. Passing the
    # resolved IdentifierBundle into the task prompt is intentionally the
    # ONLY enrichment we do: the model gets canonical HGNC / UniProt / NCBI
    # IDs + the NCBI gene summary, then reasons from its trained knowledge.
    # We deliberately don't inject UniProt's subcellular_locations or
    # function_text — those are biased toward a single dominant
    # localization and would push the model to over-defer to UniProt's
    # subcellular call (which has its own ~70% accuracy on the benchmark,
    # not 100%).
    bundle = gene_lookup(mode="resolve", symbol_or_acc=gene, http=http)
    if not isinstance(bundle, IdentifierBundle):
        raise RuntimeError(
            f"gene_lookup(resolve) did not return IdentifierBundle for {gene!r}"
        )
    gene_id = GeneIdentifier(
        hgnc_symbol=bundle.hgnc_symbol,
        hgnc_id=bundle.hgnc_id,
        uniprot_acc=bundle.uniprot_acc,
        ncbi_gene_id=bundle.ncbi_gene_id,
        ensembl_gene=bundle.ensembl_gene,
    )

    task_text = _render_task(bundle)

    session = client.beta.sessions.create(
        agent={"type": "agent", "id": agent_entry.id, "version": agent_entry.version}
        if agent_entry.version
        else agent_entry.id,
        environment_id=env_entry.id,
        title=f"triage {bundle.hgnc_symbol}",
    )
    logger.info("created triage session %s for %s", session.id, bundle.hgnc_symbol)

    timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%S")
    run_dir = REPO_ROOT / ".runs" / f"{timestamp}-triage-{bundle.hgnc_symbol}-{session.id}"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "task.md").write_text(task_text)

    events_path = run_dir / "events.jsonl"

    def _log_event(event: Any) -> None:
        with events_path.open("a") as f:
            f.write(_event_to_json_line(event))
            f.write("\n")

    # No tools registered — the agent should never make custom_tool_use events,
    # but we still pass an empty handler dict in case of any unexpected calls.
    stream = stream_until_done(
        client, session_id=session.id, handlers={}, on_event=_log_event
    )
    send_user_message(client, session_id=session.id, text=task_text)
    final_text = collect_text(stream)

    (run_dir / "final.md").write_text(final_text)
    triage_json = _extract_triage_json(final_text)

    triage_path, invalid_path, validation_status, validation_errors = _persist_triage(
        gene_id=gene_id,
        triage_json=triage_json,
        run_dir=run_dir,
        model_id=_agent.AGENT_MODEL,
    )
    if validation_status == "invalid":
        logger.warning(
            "triage record for %s failed Pydantic validation; persisted to %s for review",
            bundle.hgnc_symbol,
            invalid_path,
        )

    summary = {
        "gene": bundle.hgnc_symbol,
        "uniprot_acc": bundle.uniprot_acc,
        "session_id": session.id,
        "agent_id": agent_entry.id,
        "agent_version": agent_entry.version,
        "environment_id": env_entry.id,
        "model_id": _agent.AGENT_MODEL,
        "triage_path": str(triage_path) if triage_path else None,
        "invalid_path": str(invalid_path) if invalid_path else None,
        "validation_status": validation_status,
        "validation_errors": validation_errors,
        "triage_json": triage_json,
        "final_text_chars": len(final_text),
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")

    return TriageResult(
        session_id=session.id,
        triage_path=triage_path,
        invalid_path=invalid_path,
        run_dir=run_dir,
        final_text=final_text,
        triage_json=triage_json,
        validation_status=validation_status,
        validation_errors=validation_errors,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _render_task(bundle: IdentifierBundle) -> str:
    """Populate the task template with canonical identifiers + NCBI summary.

    The agent has no tools, so the orchestrator pre-cooks the canonical-
    identity context here. We deliberately do NOT inject UniProt's
    subcellular_locations or function_text — that would prime the agent to
    over-defer to UniProt's localization call (which has its own ~70%
    accuracy on the benchmark). Identifiers + NCBI gene summary are
    enough to prevent gross alias hallucinations without contaminating
    the model's independent reasoning.
    """

    template = (Path(__file__).parent / "prompts" / "task_template.md").read_text()
    aliases = ", ".join(bundle.aliases) if bundle.aliases else "(none)"
    previous = ", ".join(bundle.previous_symbols) if bundle.previous_symbols else "(none)"
    summary = bundle.ncbi_summary.strip() if bundle.ncbi_summary else "(no NCBI summary available)"
    return (
        template
        .replace("{gene}", bundle.hgnc_symbol)
        .replace("{hgnc_symbol}", bundle.hgnc_symbol)
        .replace("{approved_name}", bundle.approved_name or "(unknown)")
        .replace("{uniprot_acc}", bundle.uniprot_acc)
        .replace("{aliases}", aliases)
        .replace("{previous_symbols}", previous)
        .replace("{ncbi_summary}", summary)
    )


# Permissive JSON extraction: accept a bare JSON object response, OR
# a fenced ```json``` block. The prompt asks for bare JSON, but real
# model output sometimes wraps it in a fence anyway.
_FENCED_JSON_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)
_BARE_JSON_RE = re.compile(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", re.DOTALL)


def _model_path_for(model_id: str) -> TriageModelPath:
    if model_id not in _MODEL_PATH_BY_ID:
        raise ValueError(
            f"no TriageModelPath mapping for model {model_id!r}; update _MODEL_PATH_BY_ID"
        )
    return _MODEL_PATH_BY_ID[model_id]


def _persist_triage(
    *,
    gene_id: GeneIdentifier,
    triage_json: dict[str, Any] | None,
    run_dir: Path,
    model_id: str,
) -> tuple[
    Path | None, Path | None, Literal["valid", "invalid", "missing"], list[dict[str, Any]] | None
]:
    """Validate the agent's JSON against TriageRecordDraft and persist as TriageRecord.

    No evidence promotion: the triage agent is pure-model and emits no
    Evidence quotes. Search log is still attached (typically empty since
    no tools are configured).
    """

    if triage_json is None:
        return None, None, "missing", None

    # Inject orchestrator-owned fields the agent does not emit.
    payload = dict(triage_json)
    payload.setdefault("schema_version", TRIAGE_SCHEMA_VERSION)
    payload.setdefault("model_path", _model_path_for(model_id))
    payload["gene"] = gene_id.model_dump()

    try:
        draft = TriageRecordDraft.model_validate(payload)
    except ValidationError as exc:
        invalid_path = _write_invalid(triage_json, gene=gene_id.hgnc_symbol, run_dir=run_dir)
        return None, invalid_path, "invalid", [{**e} for e in exc.errors()]

    search_log = build_search_log(run_dir / "events.jsonl", contributed_by={})

    try:
        record = TriageRecord(
            schema_version=draft.schema_version,
            gene=draft.gene,
            verdict=draft.verdict,
            verdict_reasoning=draft.verdict_reasoning,
            reason=draft.reason,
            search_log=search_log,
            model_path=draft.model_path,
        )
    except ValidationError as exc:
        invalid_path = _write_invalid(triage_json, gene=gene_id.hgnc_symbol, run_dir=run_dir)
        return None, invalid_path, "invalid", [{**e} for e in exc.errors()]

    triage_dir = DATA_DIR / "triage"
    triage_dir.mkdir(parents=True, exist_ok=True)
    triage_path = triage_dir / f"{gene_id.hgnc_symbol}.json"
    triage_path.write_text(record.model_dump_json(indent=2) + "\n")
    return triage_path, None, "valid", None


def _write_invalid(triage_json: dict[str, Any], *, gene: str, run_dir: Path) -> Path:
    invalid_path = run_dir / f"{gene}.invalid.json"
    invalid_path.write_text(json.dumps(triage_json, indent=2, sort_keys=True) + "\n")
    return invalid_path


def _extract_triage_json(text: str) -> dict[str, Any] | None:
    """Find and parse the agent's triage JSON.

    Prefers a fenced ```json``` block (back-compat with fenced output),
    falls back to a bare JSON object. Accepts the first parseable
    candidate that has a ``verdict`` field.
    """

    candidates: list[str] = list(_FENCED_JSON_RE.findall(text))
    if not candidates:
        candidates = list(_BARE_JSON_RE.findall(text))
    for raw in candidates:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and "verdict" in data:
            return data
    return None


def _event_to_json_line(event: Any) -> str:
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
