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
from typing import Any, Literal, cast

from anthropic import Anthropic

from pydantic import ValidationError

from accessible_surfaceome.paths import DATA_DIR, DATA_SOURCES_DIR, REPO_ROOT
from accessible_surfaceome.tools._shared import retraction_watch as _retraction_watch
from accessible_surfaceome.tools._shared.http import CachedHTTP, open_default_client
from accessible_surfaceome.tools._shared.models import (
    Evidence,
    ProteinFeatures,
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
from .audit import (
    EntailmentAuditCallable,
    apply_entailment_audit,
    make_sonnet_entailment_audit,
)
from .deep_dive_pack import DeepDivePackLoader, render_markdown as _render_deep_dive
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
    audit: bool = False,
) -> AnnotateResult:
    client = client or _client_module.get_client()
    own_http = http is None
    http_client = http or open_default_client()
    try:
        return _annotate_one(client, http_client, gene, audit=audit)
    finally:
        if own_http:
            http_client.close()


def _annotate_one(
    client: Anthropic, http: CachedHTTP, gene: str, *, audit: bool = False
) -> AnnotateResult:
    reg = _registry.load()
    if _agent.AGENT_NAME not in reg.agents or _environment.ENVIRONMENT_NAME not in reg.environments:
        raise RuntimeError(
            "agent or environment missing from registry — run `accessible-surfaceome agents sync` first"
        )
    agent_entry = reg.agents[_agent.AGENT_NAME]
    env_entry = reg.environments[_environment.ENVIRONMENT_NAME]

    source_store = SourceTextStore()
    retraction_index = _retraction_watch.from_http(http)
    logger.info(
        "Retraction Watch index: %d PMIDs / %d DOIs (checked_at=%s)",
        len(retraction_index.pmids),
        len(retraction_index.dois),
        retraction_index.checked_at.isoformat(),
    )
    handlers = tool_registry.build_handlers(
        http, source_store=source_store, retraction_index=retraction_index
    )

    try:
        pack = DeepDivePackLoader().for_gene(hgnc_symbol=gene)
        deep_dive_block = _render_deep_dive(pack)
    except Exception as exc:  # noqa: BLE001
        # Pack is best-effort context; never fail the run on a missing TSV.
        logger.warning("deep_dive_pack render failed for %s: %s", gene, exc)
        deep_dive_block = ""

    # Pre-inject SURFY snapshot features so the agent doesn't burn tool
    # calls on basic structural facts (TM count, signal peptide, Almen
    # class, UniProt keywords). Empty block when the gene isn't in the
    # snapshot — the agent falls back to its own gene_lookup cascade.
    try:
        protein_features = _load_surfy_features(gene)
        protein_features_block = _render_protein_features_block(protein_features)
    except Exception as exc:  # noqa: BLE001
        logger.warning("SURFY feature load failed for %s: %s", gene, exc)
        protein_features_block = ""

    # If the triage agent already ran on this gene, inject its
    # ``key_uncertainty`` as a focal directive for the deep-dive. Empty
    # block when no triage record exists.
    try:
        triage_uncertainty = _load_triage_key_uncertainty(gene)
        triage_uncertainty_block = _render_triage_uncertainty_block(triage_uncertainty)
    except Exception as exc:  # noqa: BLE001
        logger.warning("triage key_uncertainty load failed for %s: %s", gene, exc)
        triage_uncertainty_block = ""

    task_text = _render_task(
        gene,
        deep_dive_block=deep_dive_block,
        protein_features_block=protein_features_block,
        triage_uncertainty_block=triage_uncertainty_block,
    )

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

    audit_callable: EntailmentAuditCallable | None = (
        make_sonnet_entailment_audit(client) if audit else None
    )
    annotation_path, invalid_path, validation_status, validation_errors = _persist_annotation(
        gene=gene,
        annotation_json=annotation_json,
        run_dir=run_dir,
        source_store=source_store,
        audit_callable=audit_callable,
        protein_features_override=protein_features,
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


def _load_triage_key_uncertainty(gene: str) -> str | None:
    """If a triage record exists for this gene at
    ``data/triage/{gene}.json``, return its ``key_uncertainty`` text;
    otherwise return None.

    The triage agent emits a one-sentence ``key_uncertainty`` per gene
    pointing at whatever ambiguity it couldn't resolve. The deep-dive
    consumes that as a focal point for its own investigation.
    """
    triage_path = DATA_DIR / "triage" / f"{gene}.json"
    if not triage_path.exists():
        return None
    try:
        record = json.loads(triage_path.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning(
            "triage record at %s failed to parse: %s — skipping key_uncertainty injection",
            triage_path, exc,
        )
        return None
    text = record.get("key_uncertainty") or record.get("predicted_key_uncertainty")
    if isinstance(text, str) and text.strip():
        return text.strip()
    return None


def _render_triage_uncertainty_block(text: str | None) -> str:
    if not text:
        return ""
    return (
        "## Triage flag\n\n"
        f"The triage agent flagged the following key uncertainty for this gene: "
        f"*{text}*\n\n"
        "Treat this as the focal question for your investigation. Your "
        "`confidence_reasoning` should explicitly address whether your record "
        "resolves or sustains this uncertainty.\n"
    )


_SURFY_SNAPSHOT_PATH = DATA_DIR / "processed" / "surfy" / "surfy_human_snapshot.tsv"


def _load_surfy_features(gene_symbol: str) -> ProteinFeatures:
    """Look up a gene in the SURFY snapshot and return a populated
    :class:`ProteinFeatures`. Returns an empty (default) instance if
    the snapshot file is missing or the gene isn't present.

    The orchestrator calls this once per ``annotate_gene`` invocation
    and injects the rendered block into the task prompt before the
    LLM runs. The agent does not modify these fields.

    Provenance: stamped with ``provenance="surfy_snapshot"`` so we can
    distinguish snapshot-fed records from records built from direct
    primary sources later (see plan: protein-features-provenance audit).
    """
    if not _SURFY_SNAPSHOT_PATH.exists():
        logger.warning(
            "SURFY snapshot not found at %s; protein_features will be empty",
            _SURFY_SNAPSHOT_PATH,
        )
        return ProteinFeatures()

    def _opt(row: dict[str, str], key: str) -> str | None:
        v = (row.get(key) or "").strip()
        return v or None

    def _int(row: dict[str, str], key: str) -> int | None:
        v = _opt(row, key)
        try:
            return int(float(v)) if v is not None else None
        except ValueError:
            return None

    def _float(row: dict[str, str], key: str) -> float | None:
        v = _opt(row, key)
        try:
            return float(v) if v is not None else None
        except ValueError:
            return None

    def _bool(row: dict[str, str], key: str) -> bool | None:
        v = _opt(row, key)
        if v is None:
            return None
        return v.lower() in {"1", "true", "yes", "y", "t"}

    def _list(row: dict[str, str], key: str) -> list[str]:
        v = _opt(row, key)
        if v is None:
            return []
        # SURFY uses ';' as the in-cell list separator for keywords / xrefs
        return [tok.strip() for tok in v.split(";") if tok.strip()]

    import csv as _csv  # local alias; csv is imported at module top
    target = gene_symbol.strip().upper()
    with _SURFY_SNAPSHOT_PATH.open() as fh:
        for row in _csv.DictReader(fh, delimiter="\t"):
            if (row.get("gene_symbol") or "").strip().upper() == target:
                # Cast SURFY's surface-call flag into the topology_source slot
                # only when SURFY explicitly cites one (most rows leave it blank).
                raw_source = _opt(row, "topology_source") or "unknown"
                if raw_source not in (
                    "uniprot", "phobius", "deeptmhmm", "literature", "unknown",
                ):
                    raw_source = "unknown"
                topology_source = cast(
                    Literal["uniprot", "phobius", "deeptmhmm", "literature", "unknown"],
                    raw_source,
                )
                return ProteinFeatures(
                    protein_length_aa=_int(row, "protein_length"),
                    tm_domain_count=_int(row, "tm_domain_count"),
                    signal_peptide=_bool(row, "signal_peptide"),
                    topology_string=_opt(row, "topology_string"),
                    topology_source=topology_source,
                    almen_main_class=_opt(row, "almen_main_class"),
                    almen_sub_class=_opt(row, "almen_sub_class"),
                    cd_designation=_opt(row, "cd_number"),
                    uniprot_keywords=_list(row, "uniprot_keywords"),
                    pdb_ids=[],  # not in SURFY snapshot; left empty
                    cspa_peptide_count=_int(row, "cspa_peptide_count"),
                    hpa_antibody_available=_bool(row, "hpa_antibody"),
                    drugbank_ids=_list(row, "drugbank_ids"),
                    surfy_ml_score=_float(row, "surfy_ml_score"),
                    surfy_label_source=_opt(row, "surfy_label_source"),
                    provenance="surfy_snapshot",
                )
    logger.info("gene %s not present in SURFY snapshot; protein_features empty", gene_symbol)
    return ProteinFeatures()


def _render_protein_features_block(features: ProteinFeatures) -> str:
    """Render the pre-loaded ProteinFeatures bucket as the markdown block
    injected into the task prompt. Returns empty when no field is populated."""
    if features == ProteinFeatures():
        return ""
    lines: list[str] = ["## Pre-loaded protein features (SURFY snapshot + UniProt)\n"]
    # Compact key:value lines for the populated fields only.
    def _line(label: str, value: object) -> None:
        if value is None or value == "" or value == []:
            return
        lines.append(f"- **{label}:** {value}")

    _line("Protein length (aa)", features.protein_length_aa)
    _line("TM domain count", features.tm_domain_count)
    _line("Signal peptide", features.signal_peptide)
    _line("Topology string", features.topology_string)
    if features.topology_source not in {"unknown", None}:
        _line("Topology source", features.topology_source)
    _line("Almen main class", features.almen_main_class)
    _line("Almen sub class", features.almen_sub_class)
    _line("CD designation", features.cd_designation)
    if features.uniprot_keywords:
        _line("UniProt keywords", ", ".join(features.uniprot_keywords))
    if features.pdb_ids:
        _line("PDB ids", ", ".join(features.pdb_ids))
    _line("CSPA peptide count", features.cspa_peptide_count)
    _line("HPA antibody available", features.hpa_antibody_available)
    if features.drugbank_ids:
        _line("DrugBank ids", ", ".join(features.drugbank_ids))
    if features.surfy_ml_score is not None:
        _line("SURFY ML surface score", f"{features.surfy_ml_score:.3f}")
    _line("SURFY label source", features.surfy_label_source)
    lines.append(
        "\nThese fields are pre-loaded; quote them when load-bearing. The "
        "orchestrator stamped `provenance` on this bucket; do not overwrite it.\n"
    )
    return "\n".join(lines)


def _render_task(
    gene: str,
    *,
    deep_dive_block: str = "",
    protein_features_block: str = "",
    triage_uncertainty_block: str = "",
) -> str:
    template = (Path(__file__).parent / "prompts" / "task_template.md").read_text()
    return (
        template.replace("{gene}", gene)
        .replace("{deep_dive_block}", deep_dive_block)
        .replace("{protein_features_block}", protein_features_block)
        .replace("{triage_key_uncertainty_block}", triage_uncertainty_block)
    )


_FENCED_JSON_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def _persist_annotation(
    *,
    gene: str,
    annotation_json: dict[str, Any] | None,
    run_dir: Path,
    source_store: SourceTextStore,
    audit_callable: EntailmentAuditCallable | None = None,
    protein_features_override: ProteinFeatures | None = None,
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

    # Inject the orchestrator-loaded ProteinFeatures into the draft
    # BEFORE Pydantic validation. The agent may emit a partial / wrong
    # `protein_features` (e.g. legacy field names from prior schema),
    # but those fields are authoritative on the orchestrator side, not
    # agent-emitted. Stripping the agent's version + dumping the
    # orchestrator's override prevents extra-field rejections.
    if protein_features_override is not None:
        annotation_json["protein_features"] = protein_features_override.model_dump()

    try:
        draft = SurfaceomeRecordDraft.model_validate(annotation_json)
    except ValidationError as exc:
        invalid_path = _write_invalid(annotation_json, gene=gene, run_dir=run_dir)
        return None, invalid_path, "invalid", [{**e} for e in exc.errors()]

    evidence: list[Evidence] = [
        promote_claim(claim, store=source_store) for claim in draft.evidence_claims
    ]

    if audit_callable is not None:
        apply_entailment_audit(evidence, audit=audit_callable)

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
            protein_features=draft.protein_features,
            targetability=draft.targetability,
            surface_biology=draft.surface_biology,
            surface_engagement_validation=draft.surface_engagement_validation,
            risk_flags=draft.risk_flags,
            isoform_accessibility=draft.isoform_accessibility,
            coreceptor_requirements=draft.coreceptor_requirements,
            orthology=draft.orthology,
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
            triage_signal=draft.triage_signal,
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
