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
from accessible_surfaceome.tools._shared.models import SynthesizerDraft

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


def _build_task(
    gene: str,
    *,
    a1_draft: dict[str, Any],
    a2_draft: dict[str, Any] | None,
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
    return (
        f"Synthesize the deep-dive top-line for the human gene **{gene}**.\n\n"
        "You receive the A1 (surface_evidence) and A2 (biological_context) "
        "outputs below. Integrate them into a `SynthesizerDraft`. Cite only "
        "from the merged evidence ledger (`a1_evi_*` plus `a2_evi_*` when "
        "A2 is present). Emit exactly one fenced ```json block as your final "
        "message — no prose around it — matching the schema at the end.\n\n"
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
) -> BResult:
    """Run B against one gene's A1 (+ optional A2) draft and return the result."""
    client = client or get_client()
    a1_draft = _load_json(a1_path)
    a2_draft = _load_json(a2_path) if a2_path is not None else None
    return _run(client, gene, a1_draft=a1_draft, a2_draft=a2_draft)


def _run(
    client: Anthropic,
    gene: str,
    *,
    a1_draft: dict[str, Any],
    a2_draft: dict[str, Any] | None,
) -> BResult:
    system_prompt = SYSTEM_PROMPT_PATH.read_text()
    messages: list[dict[str, Any]] = [
        {
            "role": "user",
            "content": _build_task(gene, a1_draft=a1_draft, a2_draft=a2_draft),
        }
    ]
    n_repair_attempts = 0
    final_text = ""
    raw_json: dict[str, Any] | None = None
    validation_error: str | None = None

    for _ in range(MAX_ITERATIONS):
        resp = client.messages.create(
            model=AGENT_MODEL,
            max_tokens=MAX_TOKENS,
            system=system_prompt,
            # No tools by design — see module docstring.
            messages=cast("Any", messages),
        )
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

    run_dir.mkdir(exist_ok=True)

    meta = {
        "gene": gene,
        "a1_input": str(a1_path),
        "a2_input": str(a2_arg) if a2_arg is not None else None,
        "n_tool_calls": result.n_tool_calls,
        "n_repair_attempts": result.n_repair_attempts,
        "validation_error": result.validation_error,
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
