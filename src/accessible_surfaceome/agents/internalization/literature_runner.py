"""Literature-track internalization pass: resolve gene -> discover papers ->
triage -> fetch bodies + real source store -> select clips -> promote to
span-verified Evidence -> grade by mode -> assemble + validate + persist."""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from anthropic import Anthropic

from accessible_surfaceome.agents._support.client import get_client
from accessible_surfaceome.agents._support.web_literature import web_discover_papers
from accessible_surfaceome.agents.internalization.ids import resolve_hgnc_id
from accessible_surfaceome.agents.internalization.literature_discovery import (
    discover_internalization_papers,
)
from accessible_surfaceome.agents.internalization.literature_grade import (
    grade_from_evidence,
    rollup_species_scope,
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
    LIT_PROMPT_VERSION,
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


def lit_prompt_sha() -> str:
    """sha256 of the literature prompt corpus, so a stale lit record is detectable
    and the sweep re-runs on any prompt edit. Covers the three judgment prompts
    (triage + select + grade) AND the shared web-discovery system prompt — the web
    prompt materially shapes WHICH papers enter the record, so a change to it (e.g.
    the envelope-tolerance fix) must invalidate prior records the same way a grading
    change does."""
    from accessible_surfaceome.agents._support.web_literature import _SYSTEM as web_system
    from accessible_surfaceome.agents.internalization.literature_grade import (
        load_grade_prompt,
    )
    from accessible_surfaceome.agents.internalization.literature_select import (
        load_select_prompt,
    )
    from accessible_surfaceome.agents.internalization.literature_triage import (
        load_triage_prompt,
    )

    corpus = "\0".join(
        (load_triage_prompt(), load_select_prompt(), load_grade_prompt(), web_system)
    )
    return hashlib.sha256(corpus.encode("utf-8")).hexdigest()
# Topic phrase for the shared web_search discovery complement (kept gene-agnostic
# — the gene's own names are passed separately).
_WEB_INTENT = (
    "internalization / endocytosis / receptor-mediated uptake of this cell-surface "
    "protein — rate, kinetics, mechanism, or trafficking measurements"
)
_DEFAULT_ANNOTATIONS_DIR = REPO_ROOT / "data" / "annotations" / "internalization"


def annotate_literature(
    gene: str,
    *,
    client: object | None = None,
    http: CachedHTTP | None = None,
    persist: bool = True,
    annotations_dir: Path | None = None,
    model_priors: list[ModelPriorTrack] | None = None,
    use_web_search: bool = False,
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
    if use_web_search:
        # Shared web_search complement — surfaces recent preprints + vocabulary-
        # mismatch papers the abstract index misses (e.g. a methods preprint that
        # studies this protein as one example cargo). Hydrated to real Papers, so
        # they flow through the SAME triage / full-text-fetch / span-verify path;
        # a no-op if web_search isn't enabled on the account.
        web_names = [
            n
            for n in (
                bundle.hgnc_symbol,
                bundle.approved_name,  # str | None
                *bundle.aliases,
                *bundle.alias_names,
                *bundle.previous_symbols,
            )
            if n
        ]
        for paper in web_discover_papers(
            cast(Anthropic, client),
            intent=_WEB_INTENT,
            gene_names=web_names,
            http=http,
            retraction_index=retraction,
        ):
            discovered.setdefault(paper_source_id(paper), paper)
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

    # Deterministic backstop for the modulator DIRECTION rule (modulator -> the
    # target): drop any modulator_observation whose `modulator` field NAMES THE
    # TARGET itself. Both reversals the grader occasionally emits put the target's
    # own name in the modulator slot — a target-self perturbation, or a "target
    # modulates ANOTHER gene" clip — so this one check catches both. A genuine
    # third-party modulator is never named by the target's own symbol / name.
    _target_syms = {bundle.hgnc_symbol.upper()} | {
        a.upper()
        for a in (*bundle.aliases, *bundle.previous_symbols)
        if len(a) >= 4  # skip ultra-short ambiguous aliases (TR / T9 / p90)
    }
    _target_name = (bundle.approved_name or "").upper()

    def _names_target(modulator: str) -> bool:
        up = modulator.upper()
        if _target_name and _target_name in up:
            return True
        return bool(set(re.findall(r"[A-Z0-9]+", up)) & _target_syms)

    modulators = [
        m for m in llm.modulator_observations if not _names_target(m.modulator)
    ]

    # Defense-in-depth against an off-target clip that SELECT let into the ledger
    # but GRADE attributed to NOTHING: prune any span-verified source cited by no
    # target observation, no per-mode grade, AND no (kept) modulator observation
    # (the separate cross-gene table — its clips are kept, not dropped). Guarded on
    # the grader having attributed at least one source somewhere: if it emitted no
    # citations at all we keep the full ledger rather than strip genuine evidence.
    cited_ids: set[str] = {
        sid for o in llm.observations for sid in o.cited_source_ids
    }
    cited_ids.update(sid for m in modulators for sid in m.cited_source_ids)
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
    # Likewise derive species_scope from the per-observation species — the LLM
    # schema (extra="forbid") has no species_scope field, so the grader's summary
    # was dropped at parse time and every record defaulted to "unspecified".
    species_scope = rollup_species_scope(llm.observations)

    track = LiteratureTrack(
        grades_by_mode=llm.grades_by_mode,
        overall_grade=llm.overall_grade,
        overall_confidence=llm.overall_confidence,
        rationale=llm.rationale,
        cross_condition_note=llm.cross_condition_note,
        trafficking_summary=llm.trafficking_summary,
        species_scope=species_scope,
        species_inferred=species_scope != "unspecified",
        has_primary_or_invivo_evidence=has_primary_or_invivo,
        observations=llm.observations,
        modulator_observations=modulators,
        sources=evidence,
        n_observations=len(llm.observations),
        n_modulator_observations=len(modulators),
        n_papers_discovered=len(discovered),
        n_papers_fetched=sum(1 for v in fetched_by_id.values() if v),
        prompt_sha=lit_prompt_sha(),
        prompt_version=LIT_PROMPT_VERSION,
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
