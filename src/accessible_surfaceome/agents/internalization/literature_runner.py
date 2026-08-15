"""Literature-track internalization pass: resolve gene -> discover papers ->
triage -> fetch bodies + real source store -> select clips -> promote to
span-verified Evidence -> grade by mode -> assemble + validate + persist."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from accessible_surfaceome.agents._support.client import get_client
from accessible_surfaceome.agents.internalization.ids import resolve_hgnc_id
from accessible_surfaceome.agents.internalization.literature_discovery import (
    discover_internalization_papers,
)
from accessible_surfaceome.agents.internalization.literature_grade import (
    grade_from_evidence,
)
from accessible_surfaceome.agents.internalization.literature_pool import (
    build_pool,
    build_source_store,
)
from accessible_surfaceome.agents.internalization.literature_select import (
    promote,
    select_clips,
)
from accessible_surfaceome.agents.internalization.literature_triage import (
    triage_internalization_abstracts,
)
from accessible_surfaceome.agents.internalization.models import (
    SCHEMA_VERSION,
    InternalizationRecord,
    LiteratureTrack,
    ModelPriorTrack,
)
from accessible_surfaceome.agents.plan_trim_select.abstract_triage import paper_source_id
from accessible_surfaceome.env import REPO_ROOT
from accessible_surfaceome.tools._shared.http import CachedHTTP, open_default_client
from accessible_surfaceome.tools._shared.retraction_watch import empty as empty_retraction
from accessible_surfaceome.tools.gene_lookup import resolve_by_hgnc_id

LIT_RUNNER_VERSION = "internalization-literature/0.1.0"
_DEFAULT_ANNOTATIONS_DIR = REPO_ROOT / "data" / "annotations" / "internalization"


def annotate_literature(
    gene: str,
    *,
    client: object | None = None,
    http: CachedHTTP | None = None,
    persist: bool = True,
    annotations_dir: Path | None = None,
    model_priors: list[ModelPriorTrack] | None = None,
) -> InternalizationRecord:
    client = client or get_client()
    http = http or open_default_client()
    retraction = empty_retraction()

    bundle = resolve_by_hgnc_id(resolve_hgnc_id(gene), http=http)
    # Alternate names so the LLM stages recognize the protein under aliases /
    # deprecated symbols — deduped, primary symbol excluded.
    synonyms = [
        s
        for s in dict.fromkeys([*bundle.aliases, *bundle.previous_symbols])
        if s and s != bundle.hgnc_symbol
    ]

    discovered = discover_internalization_papers(
        bundle, http=http, retraction_index=retraction
    )
    papers_by_id = {paper_source_id(p): p for p in discovered.values()}

    outcomes = triage_internalization_abstracts(
        client,
        papers=list(discovered.values()),
        gene=bundle.hgnc_symbol,
        synonyms=synonyms,
    )
    pool, actions = build_pool(
        outcomes, papers_by_id, http=http, retraction_index=retraction
    )

    fetched_by_id = {a.paper_id: bool(getattr(a, "fetched_body", False)) for a in actions}
    papers_by_source_id = {
        pid: (paper, fetched_by_id.get(pid, False))
        for pid, paper in papers_by_id.items()
    }
    store = build_source_store(
        pool, papers_by_source_id=papers_by_source_id, http=http, retraction_index=retraction
    )

    selection = select_clips(
        client, pool=pool, gene=bundle.hgnc_symbol, synonyms=synonyms
    )
    # Only span-verified claims (real char offset into the fetched body) inform
    # the grade and ship as cited sources — drop store/substring misses.
    evidence = [
        e for e in promote(selection, pool=pool, store=store) if e.entailment_verified
    ]
    llm = grade_from_evidence(
        client, gene=bundle.hgnc_symbol, evidence=evidence, synonyms=synonyms
    )

    # Defense-in-depth against a third-party-modulator / off-target clip that
    # SELECT let into the ledger but GRADE (correctly) built no observation from:
    # prune any span-verified source the grader attributed to NOTHING — no
    # observation and no per-mode grade cites it. Guarded on the grader having
    # attributed at least one source somewhere: if it emitted no citations at all
    # we keep the full ledger rather than risk stripping genuine evidence.
    cited_ids: set[str] = {
        sid for o in llm.observations for sid in o.cited_source_ids
    }
    for mode in (
        llm.grades_by_mode.basal,
        llm.grades_by_mode.native_ligand,
        llm.grades_by_mode.therapeutic,
    ):
        cited_ids.update(mode.cited_source_ids)
    if cited_ids:
        evidence = [e for e in evidence if e.evidence_id in cited_ids]

    # Derived in code (not trusted to the LLM): does any graded observation rest
    # on primary tissue or in-vivo data rather than only cell lines?
    has_primary_or_invivo = any(
        o.cell_context in ("primary", "in_vivo") for o in llm.observations
    )

    track = LiteratureTrack(
        grades_by_mode=llm.grades_by_mode,
        overall_grade=llm.overall_grade,
        overall_confidence=llm.overall_confidence,
        rationale=llm.rationale,
        cross_condition_note=llm.cross_condition_note,
        trafficking_summary=llm.trafficking_summary,
        has_primary_or_invivo_evidence=has_primary_or_invivo,
        observations=llm.observations,
        sources=evidence,
        n_observations=len(llm.observations),
        n_papers_discovered=len(discovered),
        n_papers_fetched=sum(1 for v in fetched_by_id.values() if v),
    )

    record = InternalizationRecord(
        schema_version=SCHEMA_VERSION,
        gene_symbol=bundle.hgnc_symbol,
        hgnc_id=bundle.hgnc_id,
        uniprot_acc=bundle.uniprot_acc,
        model_priors=model_priors or [],
        literature=track,
        generated_at=datetime.now(UTC),
        runner_version=LIT_RUNNER_VERSION,
    )

    if persist:
        out_dir = annotations_dir or _DEFAULT_ANNOTATIONS_DIR
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / f"{record.gene_symbol}.json").write_text(
            record.model_dump_json(indent=2)
        )

    return record
