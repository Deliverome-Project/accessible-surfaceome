"""Messages-API runner for the Surfaceome Synthesizer (B).

B is a single-shot **no-tools** Messages-API call (with a small repair loop
for schema-validation slips). We read the system prompt from disk, inline
the A1 (and optionally A2) drafts into the task message, and loop
``messages.create`` until the model returns a fenced JSON block — which we
validate as a :class:`SynthesizerDraft`.

Why no tools: B's role is integration over the merged A1 + A2 evidence
ledger. The lack of tools is the load-bearing guarantee that every claim
traces back to a ledger entry — the model physically can't reach for an
outside fact mid-run.

The repair loop stays (max two retries on bad JSON / schema failure) because
LLMs don't count characters reliably; ``max_length`` overruns are common.

Run directly for a real test:

    uv run python -m accessible_surfaceome.agents.surfaceome_synthesizer.runner EGFR
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

from anthropic import Anthropic
from anthropic.types import TextBlock
from pydantic import ValidationError

from accessible_surfaceome.agents._support.client import get_client
from accessible_surfaceome.agents._support.payload import cached_system, cached_user_text
from accessible_surfaceome.agents._support.pricing import (
    UsageRecord,
    UsageSummary,
    record_from_response,
    summarize_usage,
)
from accessible_surfaceome.tools._shared.models import (
    BiologicalContextDraft,
    DeterministicFeatures,
    OrthologEntry,
    SurfaceEvidenceDraft,
    SynthesizerDraft,
)

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent / "prompts"
SYSTEM_PROMPT_PATH = PROMPTS_DIR / "system.md"

AGENT_MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 16000
# B has no tools, so the loop terminates on the first stop. We still bound
# the loop in case of repeated bad-JSON repairs.
MAX_ITERATIONS = 6
MAX_REPAIRS = 2

_FENCED_JSON_RE = re.compile(r"```(?:json)?\s*(\{.*\})\s*```", re.DOTALL)


@dataclass
class BResult:
    """Outcome of one B run — valid draft, invalid JSON, or no JSON at all."""

    gene: str
    draft: SynthesizerDraft | None
    raw_json: dict[str, Any] | None
    final_text: str
    validation_error: str | None
    n_tool_calls: int  # always 0 by design — kept for API symmetry with A1
    n_repair_attempts: int = 0
    messages: list[dict[str, Any]] = field(default_factory=list)
    usage: UsageSummary = field(
        default_factory=lambda: UsageSummary(model=AGENT_MODEL)
    )


def _extract_json(text: str) -> dict[str, Any] | None:
    """Last fenced JSON block wins — the model may show intermediate examples."""
    matches = _FENCED_JSON_RE.findall(text)
    if not matches:
        return None
    try:
        return json.loads(matches[-1])
    except json.JSONDecodeError:
        return None


def _load_json(path: Path) -> dict[str, Any]:
    return cast("dict[str, Any]", json.loads(path.read_text()))


def _summarize_deterministic_for_synthesizer(
    features: DeterministicFeatures,
    *,
    hgnc_gene_groups: list[str] | None = None,
    uniprot_family: str | None = None,
) -> str:
    """Compact JSON summary of the deterministic block handed to B.

    Richer than ``_summarize_deterministic_for_planner`` (plan-trim-select's
    summarizer) because B's decisions weight more deterministic axes:

    * Threshold calls against ``canonical_topology.ecd_length_residues`` for
      the ``ecd_accessibility_class`` filter (``system.md`` L165-166).
    * Paralog cross-reactivity discussion in the methods evidence-grade
      section needs the close-paralog cluster (top by ECD identity).
    * SURFACE-Bind sites + scores anchor the structure-quality and
      binder-tractability prose B emits in ``executive_summary``.
    * AFDB pLDDT + experimental-structure availability gate the confidence
      modifiers B applies in ``confidence_reasoning``.
    * Mouse + cyno ortholog identity drives the cross-species translatability
      hint B can offer on ``key_uncertainty``.

    Curator-assigned family tags (``hgnc_gene_groups``, ``uniprot_family``)
    are NOT in ``DeterministicFeatures`` — they live on the resolved
    :class:`IdentifierBundle`. ``_attach_deterministic_families`` overwrites
    these on B's output AFTER synthesis, so showing them to B at decision
    time lets it cross-check its own ``llm_family`` call against curator
    ground truth rather than discover the mismatch only at post-pass.
    Optional kwargs so callers without a bundle (CLI re-runs from disk) can
    omit them.
    """
    canon = features.canonical_topology
    # Sort: numeric identity first (high → low), Nones last (sentinel -1
    # below any valid 0-100 identity).
    top_paralogs = sorted(
        features.paralogs,
        key=lambda p: (
            p.ecd_pct_identity if p.ecd_pct_identity is not None else -1.0
        ),
        reverse=True,
    )[:5]

    def _canonical(entries: list[OrthologEntry]) -> OrthologEntry | None:
        for entry in entries:
            if entry.is_canonical:
                return entry
        return entries[0] if entries else None

    mouse = _canonical(list(features.orthologs.mouse))
    cyno = _canonical(list(features.orthologs.cynomolgus))
    structure = features.structure
    surface_bind = features.surface_bind

    payload: dict[str, Any] = {
        "canonical_topology": {
            "tm_helix_count": canon.tm_helix_count,
            "n_terminal_orientation": canon.n_terminal_orientation,
            "c_terminal_orientation": canon.c_terminal_orientation,
            "ecd_length_residues": canon.ecd_length_residues,
            "icd_length_residues": canon.icd_length_residues,
            "signal_peptide_length": canon.signal_peptide_length,
        },
        "isoform_topologies": {
            "count": len(features.isoform_topologies),
            "checked": features.isoform_topologies_checked,
        },
        "paralogs": {
            "count": len(features.paralogs),
            "checked": features.paralogs_checked,
            "top_by_ecd_identity": [
                {
                    "symbol": p.paralog_symbol,
                    "ecd_pct_identity": p.ecd_pct_identity,
                    "tm_helix_count": p.tm_helix_count,
                    "ecd_length_residues": p.ecd_length_residues,
                }
                for p in top_paralogs
            ],
        },
        "orthologs": {
            "mouse": {
                "count": len(features.orthologs.mouse),
                "canonical_symbol": mouse.ortholog_symbol if mouse else None,
                "ecd_pct_identity_to_human": (
                    mouse.ecd_pct_identity_to_human_canonical if mouse else None
                ),
            },
            "cynomolgus": {
                "count": len(features.orthologs.cynomolgus),
                "canonical_symbol": cyno.ortholog_symbol if cyno else None,
                "ecd_pct_identity_to_human": (
                    cyno.ecd_pct_identity_to_human_canonical if cyno else None
                ),
            },
        },
        "structure": {
            "afdb_id": structure.afdb_id,
            "ecd_mean_plddt": structure.ecd_mean_plddt,
            "ecd_disordered_fraction": structure.ecd_disordered_fraction,
            "has_afdb_model_urls": structure.model_cif_url is not None,
        },
        "surface_bind": {
            "has_data": surface_bind.has_data,
            "n_sites": surface_bind.n_sites,
            "n_seeds_total": surface_bind.n_seeds_total,
            "n_seeds_alpha": surface_bind.n_seeds_alpha,
            "n_seeds_beta": surface_bind.n_seeds_beta,
            "representative_pdb_id": (
                surface_bind.representative_structure.pdb_id
                if surface_bind.representative_structure
                else None
            ),
        },
        # Curator-assigned ground truth from the resolved IdentifierBundle.
        # NOT model output — shown to B so it can cross-check its own
        # ``llm_family`` call against curator labels rather than learning of
        # the mismatch only after ``_attach_deterministic_families`` runs.
        "curator_family_tags": {
            "hgnc_gene_groups": hgnc_gene_groups or [],
            "uniprot_family": uniprot_family,
        },
    }
    return json.dumps(payload, indent=2)


def _build_task(
    gene: str,
    *,
    a1_draft: dict[str, Any],
    a2_draft: dict[str, Any] | None,
    triage_summary_json: str | None = None,
    deterministic_summary_json: str | None = None,
) -> str:
    schema = json.dumps(SynthesizerDraft.model_json_schema(), indent=2)
    a1_json = json.dumps(a1_draft, indent=2)
    a2_section: str
    if a2_draft is None:
        a2_section = (
            "## A2 (Biology Compiler) output\n\n"
            "(A2 is not yet built in this branch — ignore this section, use "
            "schema defaults / `present=false` for biology-driven risks, and "
            "do NOT cite any `a2_evi_*` ids.)\n"
        )
    else:
        a2_section = (
            "## A2 (Biology Compiler) output\n\n"
            "Full `BiologicalContextDraft` (including its evidence ledger slice):\n\n"
            f"```json\n{json.dumps(a2_draft, indent=2)}\n```\n"
        )
    triage_section = ""
    if triage_summary_json:
        triage_section = (
            "## Triage prior\n\n"
            "The genome-wide Haiku `surface_triage` agent's verdict on this "
            "gene — a first-pass decision made before any deep literature "
            "work. Carries `verdict` / `reason` / `verdict_reasoning` (prose) "
            "/ `key_uncertainty` / `confidence`. The "
            "`_check_triage_signal_consistency` model_validator on "
            "`SurfaceomeRecord` requires you to explain in "
            "`confidence_reasoning` when the triage verdict strongly "
            "conflicts with what the A1+A2 evidence shows; the triage "
            "prose in `verdict_reasoning` is often the first place to "
            "look for what went wrong — quote it if useful.\n\n"
            f"```json\n{triage_summary_json}\n```\n\n"
        )
    deterministic_section = ""
    if deterministic_summary_json:
        deterministic_section = (
            "## Deterministic features (read-only)\n\n"
            "Prefetched tool output the orchestrator computed for you — "
            "NOT something you're allowed to modify or cite as evidence. "
            "Use these as numeric thresholds and structural priors when "
            "your system prompt asks you to:\n\n"
            "* `canonical_topology.ecd_length_residues` → "
            "`filters.ecd_accessibility_class` thresholds (see system "
            "prompt §ECD accessibility).\n"
            "* `paralogs.top_by_ecd_identity` → antibody cross-reactivity "
            "discussion in the methods grade rationale + paralog-decoy "
            "headline risk.\n"
            "* `surface_bind.n_sites` / `n_seeds_total` → structure "
            "tractability prose in `executive_summary.one_paragraph`.\n"
            "* `structure.ecd_mean_plddt` → confidence modifier when "
            "antibody-finding rests on AFDB epitope geometry.\n"
            "* `orthologs.{mouse,cynomolgus}` ECD identity → "
            "`key_uncertainty` notes on cross-species translatability.\n"
            "* `curator_family_tags.{hgnc_gene_groups,uniprot_family}` → "
            "cross-check your `executive_summary.llm_family` call. These "
            "are curator ground truth (not model output); a strong "
            "disagreement should land in `confidence_reasoning`.\n\n"
            f"```json\n{deterministic_summary_json}\n```\n\n"
        )
    return (
        f"Synthesize the deep-dive top-line for the human gene **{gene}**.\n\n"
        "You receive the A1 (surface_evidence) and A2 (biological_context) "
        "outputs below. Integrate them into a `SynthesizerDraft`. Cite only "
        "from the merged evidence ledger (`a1_evi_*` plus `a2_evi_*` when "
        "A2 is present). Emit exactly one fenced ```json block as your final "
        "message — no prose around it — matching the schema at the end.\n\n"
        f"{triage_section}"
        f"{deterministic_section}"
        "## A1 (Surface Evidence Compiler) output\n\n"
        "Full `SurfaceEvidenceDraft` (including its evidence ledger slice):\n\n"
        f"```json\n{a1_json}\n```\n\n"
        f"{a2_section}\n"
        "## SynthesizerDraft JSON schema\n\n"
        f"```json\n{schema}\n```\n"
    )


def run_synthesizer(
    gene: str,
    *,
    a1_path: Path,
    a2_path: Path | None = None,
    client: Anthropic | None = None,
    triage_summary_json: str | None = None,
    deterministic_summary_json: str | None = None,
) -> BResult:
    """Run B against one gene's A1 (+ optional A2) draft from disk.

    ``triage_summary_json`` is the compact triage prior the v2
    orchestrator builds via
    :func:`accessible_surfaceome.agents.plan_trim_select.runner._summarize_triage_for_planner`.
    When present, it lands as a "Triage prior" section at the top of B's
    task message — see PR #23 design doc §1110-1116.

    ``deterministic_summary_json`` is the prefetched-tool-output summary the
    orchestrator builds via :func:`_summarize_deterministic_for_synthesizer`
    (topology + paralog/ortholog + structure + SURFACE-Bind + curator family
    tags). When present, it lands as a "Deterministic features (read-only)"
    section — grounding the numeric thresholds + paralog-cross-reactivity
    discussion the system prompt asks for.
    """
    client = client or get_client()
    a1_draft = _load_json(a1_path)
    a2_draft = _load_json(a2_path) if a2_path is not None else None
    return _run(
        client,
        gene,
        a1_draft=a1_draft,
        a2_draft=a2_draft,
        triage_summary_json=triage_summary_json,
        deterministic_summary_json=deterministic_summary_json,
    )


def run_synthesizer_with_drafts(
    gene: str,
    *,
    a1_draft: SurfaceEvidenceDraft,
    a2_draft: BiologicalContextDraft | None = None,
    client: Anthropic | None = None,
    triage_summary_json: str | None = None,
    deterministic_summary_json: str | None = None,
) -> BResult:
    """In-memory peer of :func:`run_synthesizer` — for orchestrator usage.

    Accepts Pydantic drafts directly so the orchestrator doesn't have to
    round-trip A1 / A2 outputs through disk just to feed them into B.
    ``triage_summary_json`` + ``deterministic_summary_json`` semantics match
    :func:`run_synthesizer`.
    """
    client = client or get_client()
    a1_dict = a1_draft.model_dump(mode="json")
    a2_dict = a2_draft.model_dump(mode="json") if a2_draft is not None else None
    return _run(
        client,
        gene,
        a1_draft=a1_dict,
        a2_draft=a2_dict,
        triage_summary_json=triage_summary_json,
        deterministic_summary_json=deterministic_summary_json,
    )


def _run(
    client: Anthropic,
    gene: str,
    *,
    a1_draft: dict[str, Any],
    a2_draft: dict[str, Any] | None,
    triage_summary_json: str | None = None,
    deterministic_summary_json: str | None = None,
) -> BResult:
    system_prompt = SYSTEM_PROMPT_PATH.read_text()
    cached_system_blocks = cached_system(system_prompt)
    # The initial user task message embeds both ledgers + the SynthesizerDraft
    # JSON schema — large, static across repair iterations. Cache it once so
    # repairs only pay full price for the new error-feedback turn.
    messages: list[dict[str, Any]] = [
        cached_user_text(
            _build_task(
                gene,
                a1_draft=a1_draft,
                a2_draft=a2_draft,
                triage_summary_json=triage_summary_json,
                deterministic_summary_json=deterministic_summary_json,
            )
        )
    ]
    n_repair_attempts = 0
    usage_records: list[UsageRecord] = []
    final_text = ""
    raw_json: dict[str, Any] | None = None
    validation_error: str | None = None

    for _ in range(MAX_ITERATIONS):
        resp = client.messages.create(
            model=AGENT_MODEL,
            max_tokens=MAX_TOKENS,
            system=cast("Any", cached_system_blocks),
            # No tools by design — see module docstring.
            messages=cast("Any", messages),
        )
        usage_records.append(record_from_response(resp.usage, AGENT_MODEL))
        messages.append({"role": "assistant", "content": resp.content})

        # Defensive: B should never trigger tool_use (no tools were offered),
        # but if a future change adds host-side tools we surface the misuse.
        if resp.stop_reason == "tool_use":
            logger.warning(
                "B emitted tool_use despite no tools registered — aborting run"
            )
            break

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
                        "SynthesizerDraft, with no prose around it."
                    ),
                }
            )
            continue

        try:
            draft = SynthesizerDraft.model_validate(raw_json)
        except ValidationError as exc:
            validation_error = str(exc)
            if n_repair_attempts >= MAX_REPAIRS:
                break
            n_repair_attempts += 1
            logger.info(
                "B repair %d/%d for %s — %d validation error(s)",
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
                        "Emit a corrected SynthesizerDraft as one fenced ```json "
                        "block. Respect every maxLength in the schema and use the "
                        "closed-enum values exactly as listed."
                    ),
                }
            )
            continue

        return BResult(
            gene=gene,
            draft=draft,
            raw_json=raw_json,
            final_text=final_text,
            validation_error=None,
            n_tool_calls=0,
            n_repair_attempts=n_repair_attempts,
            messages=messages,
            usage=summarize_usage(usage_records, AGENT_MODEL),
        )
    else:
        logger.warning("B hit MAX_ITERATIONS=%d for %s", MAX_ITERATIONS, gene)

    return BResult(
        gene=gene,
        draft=None,
        raw_json=raw_json,
        final_text=final_text,
        validation_error=validation_error,
        n_tool_calls=0,
        n_repair_attempts=n_repair_attempts,
        messages=messages,
        usage=summarize_usage(usage_records, AGENT_MODEL),
    )


def _main(argv: list[str] | None = None) -> int:
    import sys

    from accessible_surfaceome.env import load_env

    # python -m ... bypasses the CLI entry point that normally loads .env;
    # load it here so ANTHROPIC_API_KEY resolves.
    load_env()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )
    args = argv if argv is not None else sys.argv[1:]
    gene = args[0] if args else "EGFR"

    run_dir = Path(".runs")
    a1_path = run_dir / f"a1_{gene}.json"
    a2_path = run_dir / f"a2_{gene}.json"
    if not a1_path.exists():
        print(f"missing A1 input: {a1_path}", file=sys.stderr)
        print(
            "Run the A1 runner first: "
            "`uv run python -m accessible_surfaceome.agents.surface_evidence_compiler.runner "
            f"{gene}`",
            file=sys.stderr,
        )
        return 2
    a2_arg = a2_path if a2_path.exists() else None
    if a2_arg is None:
        logger.info(
            "no %s found — running B with the A2-absent placeholder", a2_path
        )

    result = run_synthesizer(gene, a1_path=a1_path, a2_path=a2_arg)

    print(f"\n=== B result for {gene} ===")
    print(
        f"tool calls: {result.n_tool_calls}  "
        f"repair attempts: {result.n_repair_attempts}"
    )
    print(
        f"tokens: in={result.usage.input_tokens} out={result.usage.output_tokens} "
        f"cache_w={result.usage.cache_creation_input_tokens} "
        f"cache_r={result.usage.cache_read_input_tokens}  "
        f"cost: ${result.usage.cost_usd:.4f}"
    )

    run_dir.mkdir(exist_ok=True)

    meta = {
        "gene": gene,
        "a1_input": str(a1_path),
        "a2_input": str(a2_arg) if a2_arg is not None else None,
        "n_tool_calls": result.n_tool_calls,
        "n_repair_attempts": result.n_repair_attempts,
        "validation_error": result.validation_error,
        "usage": result.usage.as_dict(),
    }
    meta_out = run_dir / f"b_{gene}.meta.json"
    meta_out.write_text(json.dumps(meta, indent=2))

    if result.draft is not None:
        es = result.draft.executive_summary
        ar = result.draft.accessibility_risks
        print(
            f"VALID  surface_accessibility={es.surface_accessibility}  "
            f"evidence_grade_summary={es.evidence_grade_summary}  "
            f"confidence={result.draft.confidence}  "
            f"headline_risks={list(es.headline_risks)}"
        )
        print(
            "  accessibility_risks present: "
            f"shed_form={ar.shed_form.present}  "
            f"secreted_form={ar.secreted_form.present}  "
            f"restricted_subdomain={ar.restricted_subdomain.present}  "
            f"co_receptor={ar.co_receptor_requirements.surface_expression_dependency}"
        )
        out = run_dir / f"b_{gene}.json"
        out.write_text(result.draft.model_dump_json(indent=2))
        print(f"written: {out}, {meta_out}")
        return 0
    if result.raw_json is not None:
        print(f"INVALID — emitted JSON failed validation:\n{result.validation_error}")
        out = run_dir / f"b_{gene}.invalid.json"
        out.write_text(json.dumps(result.raw_json, indent=2))
        print(f"written: {out}")
        return 1
    print("NO JSON emitted. Final text (first 2000 chars):")
    print(result.final_text[:2000])
    return 1


if __name__ == "__main__":
    raise SystemExit(_main())
