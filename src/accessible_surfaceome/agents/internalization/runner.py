"""Model-prior internalization pass: resolve gene -> fetch isoform context ->
grade with each model -> assemble + validate + (optionally) persist."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from accessible_surfaceome.agents._support.client import get_client
from accessible_surfaceome.agents.internalization.ids import resolve_hgnc_id
from accessible_surfaceome.agents.internalization.model_prior import (
    grade_isoforms_with_model,
)
from accessible_surfaceome.agents.internalization.models import (
    RUNNER_VERSION,
    SCHEMA_VERSION,
    InternalizationRecord,
)
from accessible_surfaceome.agents.internalization.uniprot_isoforms import (
    fetch_isoform_context,
)
from accessible_surfaceome.env import REPO_ROOT
from accessible_surfaceome.tools._shared.http import CachedHTTP, open_default_client
from accessible_surfaceome.tools.gene_lookup import resolve_by_hgnc_id

DEFAULT_MODELS: tuple[str, ...] = ("claude-opus-4-8", "claude-sonnet-4-6")
_PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "model_prior_system.md"
_DEFAULT_ANNOTATIONS_DIR = REPO_ROOT / "data" / "annotations" / "internalization"


def load_prompt() -> str:
    return _PROMPT_PATH.read_text()


def annotate_model_prior(
    gene: str,
    *,
    models: tuple[str, ...] = DEFAULT_MODELS,
    client: object | None = None,
    http: CachedHTTP | None = None,
    persist: bool = True,
    annotations_dir: Path | None = None,
    canonical_only: bool = True,
) -> InternalizationRecord:
    client = client or get_client()
    http = http or open_default_client()

    hgnc_id = resolve_hgnc_id(gene)
    bundle = resolve_by_hgnc_id(hgnc_id, http=http)
    isoforms = fetch_isoform_context(
        bundle.uniprot_acc, http=http, canonical_only=canonical_only
    )
    system_prompt = load_prompt()

    priors = [
        grade_isoforms_with_model(
            client,
            model=model,
            system_prompt=system_prompt,
            gene_symbol=bundle.hgnc_symbol,
            isoforms=isoforms,
        )
        for model in models
    ]

    record = InternalizationRecord(
        schema_version=SCHEMA_VERSION,
        gene_symbol=bundle.hgnc_symbol,
        hgnc_id=bundle.hgnc_id,
        uniprot_acc=bundle.uniprot_acc,
        model_priors=priors,
        generated_at=datetime.now(UTC),
        runner_version=RUNNER_VERSION,
    )

    if persist:
        out_dir = annotations_dir or _DEFAULT_ANNOTATIONS_DIR
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / f"{record.gene_symbol}.json").write_text(
            record.model_dump_json(indent=2)
        )

    return record
