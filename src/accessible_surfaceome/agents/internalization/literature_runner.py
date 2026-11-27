"""Literature-track internalization pass: resolve gene -> discover papers ->
triage (cached) -> fetch bodies with relevance scoring -> adaptive/always web
search -> boost & batched clip select -> promote to span-verified Evidence ->
grade by mode with deterministic hygiene guards -> assemble + validate + persist."""

from __future__ import annotations

import hashlib
import logging
import re
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast

from anthropic import Anthropic

from accessible_surfaceome.agents._support.client import get_client
from accessible_surfaceome.agents._support.web_literature import web_discover_papers
from accessible_surfaceome.agents.internalization.ids import resolve_hgnc_id
from accessible_surfaceome.agents.internalization.intermediates import (
    build_intermediates_payload,
    force_worth_fetching_outcomes,
    hydrate_paper_ids,
    load_intermediates_r2,
    save_intermediates_local,
    seed_from_intermediates,
    upload_intermediates_r2,
)
from accessible_surfaceome.agents.internalization.literature_discovery import (
    boost_internalization_clips,
    count_high_signal_papers,
    discover_internalization_papers,
    internalization_relevance,
    load_discovery_cache,
    load_web_search_cache,
    save_discovery_cache,
    save_web_search_cache,
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
    HAIKU_MODEL,
    triage_internalization_abstracts,
)
from accessible_surfaceome.agents.internalization.models import (
    LIT_PROMPT_VERSION,
    SCHEMA_VERSION,
    InternalizationRecord,
    LiteratureTrack,
    ModelPriorTrack,
)
from accessible_surfaceome.agents.internalization.triage_cache import (
    input_sha as triage_input_sha,
    load as load_triage_cache,
    save as save_triage_cache,
    split as split_triage,
    triage_prompt_sha,
)
from accessible_surfaceome.agents.plan_trim_select.abstract_triage import paper_source_id
from accessible_surfaceome.env import REPO_ROOT
from accessible_surfaceome.tools._shared.http import CachedHTTP, open_default_client
from accessible_surfaceome.tools._shared.retraction_watch import (
    empty as empty_retraction,
    from_http as retraction_from_http,
)
from accessible_surfaceome.tools.gene_lookup import resolve_by_hgnc_id

logger = logging.getLogger(__name__)

LIT_RUNNER_VERSION = "internalization-literature/0.2.1"
DEFAULT_LIT_MODEL = "claude-sonnet-5-5"
DEFAULT_LIT_TRIAGE_MODEL = "claude-haiku-5-5"
DEFAULT_LIT_WEB_SCOUT_MODEL = "claude-haiku-5-5"

WebSearchMode = Literal["always", "adaptive", "off"]

# Adaptive web_search thresholds: if deterministic EuropePMC + PubTator already
# delivered at least this many fetched full-text papers, distinct papers with
# quantitative internalization clips, and pool clips, skip the ~$0.15-0.25 web
# scout call. Otherwise run web_search to recover recent preprints (e.g. EndoNB)
# and vocabulary-mismatch methods screens.
_ADAPTIVE_MIN_FETCHED = 3
_ADAPTIVE_MIN_QUANT_PAPERS = 2
_ADAPTIVE_MIN_CLIPS = 30
_WEB_SEARCH_MAX_USES = 6
_SELECT_MAX_BATCHES = 2
# Bound full-text body fetches per gene so well-studied genes (50-60+
# worth_fetching abstracts) don't stall for minutes downloading redundant PDFs.
# Excess worth_fetching outcomes are downgraded to keep_abstract (still in pool).
_MAX_WORTH_FETCHING = 25
# Bound & diversify the span-verified evidence ledger handed to Sonnet's grader:
# keeps output safely under _MAX_TOKENS_GRADE (avoiding JSON truncation on
# clip-dense genes) while preserving up to 3 clips per distinct paper and
# prioritizing quantitative kinetics + direct-assay clips.
_MAX_GRADE_EVIDENCE = 45
_MAX_CLIPS_PER_PAPER_FOR_GRADE = 3


def lit_prompt_sha() -> str:
    """sha256 of the literature prompt corpus, so a stale lit record is detectable
    and the sweep re-runs on any prompt edit. Covers the three judgment prompts
    (triage + select + grade) AND the shared web-discovery system prompt."""
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
    "protein — quantitative rate constants (k_e, half-life t1/2, % internalized), "
    "constitutive vs ligand- or antibody-induced uptake, or non-internalizing control assays"
)
_DEFAULT_ANNOTATIONS_DIR = REPO_ROOT / "data" / "annotations" / "internalization"


_RETRACTION_LOCK = threading.Lock()
_RETRACTION_CACHE: Any | None = None


def _open_retraction_index(http: Any) -> Any:
    """Load the Retraction Watch index ONCE per process when running against a
    real CachedHTTP, degrading cleanly to an empty index in unit tests."""
    global _RETRACTION_CACHE
    if not isinstance(http, CachedHTTP):
        return empty_retraction()
    with _RETRACTION_LOCK:
        if _RETRACTION_CACHE is not None:
            return _RETRACTION_CACHE
        try:
            _RETRACTION_CACHE = retraction_from_http(http)
            return _RETRACTION_CACHE
        except Exception as exc:  # noqa: BLE001
            logger.warning("retraction watch load failed (%s) — continuing with empty index", exc)
            return empty_retraction()


def _triage_with_cache(
    client: Any,
    *,
    papers_by_id: dict[str, Any],
    gene: str,
    synonyms: list[str],
    usage_sink: list[Any],
    use_caches: bool,
    triage_model: str = HAIKU_MODEL,
    triage_concurrency: int | None = None,
    seed_triage_cache: dict[str, dict[str, Any]] | None = None,
) -> list[Any]:
    if not papers_by_id:
        return []
    if not use_caches and not seed_triage_cache:
        kwargs: dict[str, Any] = {
            "papers": list(papers_by_id.values()),
            "gene": gene,
            "synonyms": synonyms,
        }
        if triage_model != HAIKU_MODEL:
            kwargs["model"] = triage_model
        if triage_concurrency is not None:
            kwargs["concurrency"] = triage_concurrency
        outcomes = triage_internalization_abstracts(client, **kwargs)
        usage_sink.extend(o.usage for o in outcomes if getattr(o, "usage", None) is not None)
        return outcomes
    tsha = triage_prompt_sha()
    cached: dict[str, dict[str, Any]] = dict(seed_triage_cache or {})
    if use_caches:
        cached.update(load_triage_cache(gene))
    to_triage, reused = split_triage(papers_by_id, cached, prompt_sha=tsha, model=triage_model)
    if reused:
        logger.info("%s: reusing %d cached triage verdict(s) [%s]; %d to run", gene, len(reused), triage_model, len(to_triage))
    triage_kwargs: dict[str, Any] = {
        "papers": to_triage,
        "gene": gene,
        "synonyms": synonyms,
        "model": triage_model,
    }
    if triage_concurrency is not None:
        triage_kwargs["concurrency"] = triage_concurrency
    fresh = (
        triage_internalization_abstracts(client, **triage_kwargs)
        if to_triage
        else []
    )
    usage_sink.extend(o.usage for o in fresh if getattr(o, "usage", None) is not None)
    if fresh and use_caches:
        save_triage_cache(
            gene,
            fresh,
            prompt_sha=tsha,
            inputs={sid: triage_input_sha(p) for sid, p in papers_by_id.items()},
            model=triage_model,
        )
    return reused + fresh


def _cap_worth_fetching(
    outcomes: list[Any],
    papers_by_id: dict[str, Any],
    *,
    gene_names: list[str],
    max_fetch: int = _MAX_WORTH_FETCHING,
    pinned_ids: set[str] | None = None,
    citation_counts: dict[str, int] | None = None,
) -> list[Any]:
    """Keep at most ``max_fetch`` highest-value ``worth_fetching`` outcomes,
    downgrading lower-priority excess ones to ``keep_abstract`` so their
    abstracts remain in the pool without stalling on 50+ full-text downloads.
    Explicitly user-pinned paper IDs are never downgraded."""
    pinned = pinned_ids or set()
    cites = citation_counts or {}
    wf_indices = [
        i
        for i, o in enumerate(outcomes)
        if getattr(getattr(o, "response", None), "decision", None) == "worth_fetching"
    ]
    if len(wf_indices) <= max_fetch:
        return outcomes
    scorer = internalization_relevance(gene_names)

    def _priority(idx: int) -> tuple[int, float, int, int]:
        o = outcomes[idx]
        p = papers_by_id.get(o.paper_id)
        is_pinned = 1 if o.paper_id in pinned else 0
        abstract = (getattr(p, "abstract", "") or "") if p is not None else ""
        title = (getattr(p, "title", "") or "") if p is not None else ""
        cited = int(cites.get(o.paper_id, 0) or 0)
        has_pmc = 1 if (p is not None and getattr(p, "pmc_id", None)) else 0
        # Relevance score first, then citation count (so foundational pre-PMC
        # kinetics papers beat low-cited OA papers), then PMC availability.
        return (is_pinned, scorer(f"{title}. {abstract}"), cited, has_pmc)

    ranked = sorted(wf_indices, key=_priority, reverse=True)
    keep_set = set(ranked[: max(max_fetch, len(pinned))])
    out = list(outcomes)
    downgraded = 0
    for idx in wf_indices:
        if idx not in keep_set:
            o = out[idx]
            resp = o.response
            out[idx] = type(o)(
                paper_id=o.paper_id,
                response=resp.model_copy(update={"decision": "keep_abstract"}),
                usage=o.usage,
                elapsed_s=o.elapsed_s,
                error=o.error,
            )
            downgraded += 1
    if downgraded:
        logger.info(
            "capped worth_fetching at %d (downgraded %d excess to keep_abstract)",
            max_fetch,
            downgraded,
        )
    return out


def _select_evidence_for_grading(
    evidence: list[Any],
    *,
    gene_names: list[str],
    max_clips: int = _MAX_GRADE_EVIDENCE,
    max_per_paper: int = _MAX_CLIPS_PER_PAPER_FOR_GRADE,
) -> list[Any]:
    """Bound and diversify the span-verified evidence ledger before grading.

    Prioritizes clips carrying quantitative kinetic terms and direct assays,
    capped at ``max_per_paper`` clips per distinct source so one verbose paper
    never crowds out independent corroborating papers or triggers JSON output
    truncation in the grader.
    """
    if len(evidence) <= max_clips:
        return evidence
    scorer = internalization_relevance(gene_names)
    conf_rank = {"strong": 2, "moderate": 1, "weak": 0}

    def _rank_key(e: Any) -> tuple[float, int, int]:
        span = e.spans[0] if getattr(e, "spans", None) else None
        quote = (span.quote if span else "") or ""
        claim = getattr(e, "claim", "") or ""
        is_primary = 1 if getattr(e, "evidence_tier", "") == "primary" else 0
        c_rank = conf_rank.get(str(getattr(e, "confidence", "")), 0)
        return (scorer(f"{quote} {claim}"), is_primary, c_rank)

    ranked = sorted(evidence, key=_rank_key, reverse=True)
    chosen: list[Any] = []
    per_source: dict[str, int] = {}
    overflow: list[Any] = []
    for e in ranked:
        span = e.spans[0] if getattr(e, "spans", None) else None
        sid = span.source.source_id if span else e.evidence_id
        if per_source.get(sid, 0) < max_per_paper:
            chosen.append(e)
            per_source[sid] = per_source.get(sid, 0) + 1
            if len(chosen) >= max_clips:
                break
        else:
            overflow.append(e)
    if len(chosen) < max_clips and overflow:
        chosen.extend(overflow[: max_clips - len(chosen)])
    logger.info(
        "capped grader evidence ledger %d -> %d clips across %d distinct sources",
        len(evidence),
        len(chosen),
        len(per_source),
    )
    return chosen


def _needs_adaptive_web_search(
    *,
    pool: dict[str, Any],
    actions: list[Any],
    gene_names: list[str],
) -> tuple[bool, str]:
    n_fetched = sum(1 for a in actions if bool(getattr(a, "fetched_body", False)))
    _n_assay_papers, n_quant_papers = count_high_signal_papers(pool, gene_names=gene_names)
    if n_fetched < _ADAPTIVE_MIN_FETCHED:
        return True, f"fetched={n_fetched}<{_ADAPTIVE_MIN_FETCHED}"
    if n_quant_papers < _ADAPTIVE_MIN_QUANT_PAPERS:
        return True, f"quant_papers={n_quant_papers}<{_ADAPTIVE_MIN_QUANT_PAPERS}"
    if len(pool) < _ADAPTIVE_MIN_CLIPS:
        return True, f"clips={len(pool)}<{_ADAPTIVE_MIN_CLIPS}"
    return False, f"sufficient (fetched={n_fetched}, quant_papers={n_quant_papers}, clips={len(pool)})"


def annotate_literature(
    gene: str,
    *,
    client: object | None = None,
    http: CachedHTTP | None = None,
    persist: bool = True,
    annotations_dir: Path | None = None,
    model_priors: list[ModelPriorTrack] | None = None,
    use_web_search: bool = False,
    web_search_mode: WebSearchMode | None = None,
    use_caches: bool = True,
    max_select_batches: int = _SELECT_MAX_BATCHES,
    model: str = DEFAULT_LIT_MODEL,
    triage_model: str = DEFAULT_LIT_TRIAGE_MODEL,
    web_scout_model: str | None = None,
    triage_concurrency: int | None = None,
    extra_paper_ids: list[str] | None = None,
    skip_discovery: bool = False,
    load_from_r2: bool = False,
    upload_to_r2: bool = False,
    intermediates_dir: Path | None = None,
    run_id: str | None = None,
    r2_cfg: Any | None = None,
) -> InternalizationRecord:
    owns_http = http is None
    client = client or get_client()
    http_client: Any = http if http is not None else open_default_client()
    # Disable local file caches automatically when a unit test injects a stub http.
    caches_active = use_caches and isinstance(http_client, CachedHTTP)
    effective_web_scout_model = web_scout_model or DEFAULT_LIT_WEB_SCOUT_MODEL

    # Resolve web_search_mode while staying 100% backward-compatible with
    # legacy callers passing ``use_web_search=True/False``.
    if web_search_mode is not None:
        ws_mode: WebSearchMode = "off" if (not use_web_search and web_search_mode != "off") else web_search_mode
    else:
        ws_mode = "always" if use_web_search else "off"

    usage: list[Any] = []
    web_search_used = False
    web_search_reason: str | None = None
    web_search_paper_ids: list[str] = []

    try:
        retraction = _open_retraction_index(http_client)
        bundle = resolve_by_hgnc_id(resolve_hgnc_id(gene), http=http_client)
        synonyms = [
            s
            for s in dict.fromkeys([*bundle.aliases, *bundle.previous_symbols])
            if s and s != bundle.hgnc_symbol
        ]
        all_names = [
            n
            for n in (
                bundle.hgnc_symbol,
                getattr(bundle, "approved_name", None),
                *(getattr(bundle, "aliases", ()) or ()),
                *(getattr(bundle, "alias_names", ()) or ()),
                *(getattr(bundle, "previous_symbols", ()) or ()),
            )
            if n
        ]

        r2_seed_papers: dict[str, Any] = {}
        r2_seed_triage: dict[str, dict[str, Any]] = {}
        r2_web_search_ran = False
        if load_from_r2:
            r2_blob = load_intermediates_r2(bundle.hgnc_symbol, cfg=r2_cfg)
            if r2_blob:
                r2_seed_papers, r2_seed_triage, r2_web_search_ran = seed_from_intermediates(r2_blob)
                logger.info(
                    "%s: seeded %d paper(s) & %d triage verdict(s) from R2 intermediates (web_search_ran=%s)",
                    bundle.hgnc_symbol,
                    len(r2_seed_papers),
                    len(r2_seed_triage),
                    r2_web_search_ran,
                )

        cached_papers: dict[str, Any] = dict(r2_seed_papers)
        if caches_active:
            cached_papers.update(load_discovery_cache(bundle.hgnc_symbol))

        citation_counts: dict[str, int] = {}
        if skip_discovery and cached_papers:
            discovered = dict(cached_papers)
            logger.info("%s: skip_discovery=True — using %d seeded paper(s)", bundle.hgnc_symbol, len(discovered))
        elif cached_papers:
            discovered = discover_internalization_papers(
                bundle,
                http=http_client,
                retraction_index=retraction,
                cached=cached_papers,
                citation_counts_out=citation_counts,
            )
        elif isinstance(http_client, CachedHTTP):
            discovered = discover_internalization_papers(
                bundle,
                http=http_client,
                retraction_index=retraction,
                citation_counts_out=citation_counts,
            )
        else:
            discovered = discover_internalization_papers(
                bundle, http=http_client, retraction_index=retraction
            )

        # User-supplied incremental papers (PMID/PMCID/DOI): hydrate and force-promote
        # to worth_fetching so they are always fetched & span-verified.
        pinned_extra_papers: dict[str, Any] = {}
        if extra_paper_ids and isinstance(http_client, CachedHTTP):
            pinned_extra_papers = hydrate_paper_ids(
                extra_paper_ids, http=http_client, retraction_index=retraction
            )
            for sid, paper in pinned_extra_papers.items():
                discovered[sid] = paper
            if pinned_extra_papers:
                logger.info(
                    "%s: hydrated %d user-supplied extra paper(s): %s",
                    bundle.hgnc_symbol,
                    len(pinned_extra_papers),
                    sorted(pinned_extra_papers),
                )

        def _run_web_scout() -> list[Any]:
            nonlocal web_search_used, web_search_paper_ids
            if caches_active:
                cached_ws_ids = load_web_search_cache(
                    bundle.hgnc_symbol,
                    model=effective_web_scout_model,
                    max_uses=_WEB_SEARCH_MAX_USES,
                )
                if cached_ws_ids is not None:
                    web_search_used = True
                    web_search_paper_ids = list(cached_ws_ids)
                    logger.info(
                        "%s: reusing cached web_search result (%d hit(s), model=%s)",
                        bundle.hgnc_symbol,
                        len(cached_ws_ids),
                        effective_web_scout_model,
                    )
                    return []
            if r2_web_search_ran and skip_discovery:
                web_search_used = True
                logger.info("%s: skipping web_search (already ran in R2 seed)", bundle.hgnc_symbol)
                return []
            web_search_used = True
            hits = web_discover_papers(
                cast(Anthropic, client),
                intent=_WEB_INTENT,
                gene_names=all_names,
                http=http_client,
                retraction_index=retraction,
                usage_sink=usage,
                max_uses=_WEB_SEARCH_MAX_USES,
                model=effective_web_scout_model,
            )
            hit_ids = [paper_source_id(p) for p in hits]
            web_search_paper_ids = hit_ids
            if caches_active:
                save_web_search_cache(
                    bundle.hgnc_symbol,
                    hit_ids,
                    model=effective_web_scout_model,
                    max_uses=_WEB_SEARCH_MAX_USES,
                )
            return hits

        if ws_mode == "always":
            web_search_reason = "mode=always"
            for paper in _run_web_scout():
                discovered.setdefault(paper_source_id(paper), paper)

        if caches_active and discovered:
            save_discovery_cache(bundle.hgnc_symbol, discovered)

        papers_by_id = {paper_source_id(p): p for p in discovered.values()}
        pinned_ids = set(pinned_extra_papers)
        papers_to_triage = {
            sid: p for sid, p in papers_by_id.items() if sid not in pinned_ids
        }
        outcomes = _triage_with_cache(
            client,
            papers_by_id=papers_to_triage,
            gene=bundle.hgnc_symbol,
            synonyms=synonyms,
            usage_sink=usage,
            use_caches=caches_active,
            triage_model=triage_model,
            triage_concurrency=triage_concurrency,
            seed_triage_cache=r2_seed_triage or None,
        )
        if pinned_extra_papers:
            outcomes.extend(force_worth_fetching_outcomes(pinned_extra_papers))
        outcomes = _cap_worth_fetching(
            outcomes,
            papers_by_id,
            gene_names=all_names,
            pinned_ids=pinned_ids,
            citation_counts=citation_counts,
        )
        rel_fn = internalization_relevance(all_names)
        pool, actions = build_pool(
            outcomes,
            papers_by_id,
            http=http_client,
            retraction_index=retraction,
            relevance=rel_fn,
        )

        # Adaptive web_search: only pay for the web scout when deterministic
        # discovery left thin full-text or quantitative coverage.
        if ws_mode == "adaptive":
            need_ws, ws_reason = _needs_adaptive_web_search(
                pool=pool, actions=actions, gene_names=all_names
            )
            web_search_reason = ws_reason
            logger.info("%s: adaptive web_search=%s (%s)", bundle.hgnc_symbol, need_ws, ws_reason)
            if need_ws:
                new_web_papers: dict[str, Any] = {}
                for paper in _run_web_scout():
                    sid = paper_source_id(paper)
                    if sid not in papers_by_id:
                        discovered[sid] = paper
                        papers_by_id[sid] = paper
                        new_web_papers[sid] = paper
                if new_web_papers:
                    if caches_active:
                        save_discovery_cache(bundle.hgnc_symbol, new_web_papers)
                    web_outcomes = _triage_with_cache(
                        client,
                        papers_by_id=new_web_papers,
                        gene=bundle.hgnc_symbol,
                        synonyms=synonyms,
                        usage_sink=usage,
                        use_caches=caches_active,
                        triage_model=triage_model,
                        triage_concurrency=triage_concurrency,
                        seed_triage_cache=r2_seed_triage or None,
                    )
                    outcomes.extend(web_outcomes)
                    web_pool, web_actions = build_pool(
                        web_outcomes,
                        new_web_papers,
                        http=http_client,
                        retraction_index=retraction,
                        relevance=rel_fn,
                    )
                    for cid, draft in web_pool.items():
                        key = cid
                        k = 2
                        while key in pool:
                            key = f"{cid}_{k}"
                            k += 1
                        pool[key] = draft.model_copy(update={"suggested_evidence_id": key})
                    actions.extend(web_actions)

        boost_internalization_clips(pool, gene_names=all_names)

        fetched_by_id = {a.paper_id: bool(getattr(a, "fetched_body", False)) for a in actions}
        papers_by_source_id = {
            pid: (paper, fetched_by_id.get(pid, False))
            for pid, paper in papers_by_id.items()
        }
        store = build_source_store(
            pool,
            papers_by_source_id=papers_by_source_id,
            http=http_client,
            retraction_index=retraction,
        )

        selection = select_clips(
            client,
            pool=pool,
            gene=bundle.hgnc_symbol,
            synonyms=synonyms,
            usage_sink=usage,
            max_batches=max_select_batches,
            model=model,
        )
        # Only span-verified claims (real char offset into the fetched body) inform
        # the grade and ship as cited sources — drop store/substring misses.
        evidence_pre_cap = [
            e for e in promote(selection, pool=pool, store=store) if e.entailment_verified
        ]
        evidence = _select_evidence_for_grading(evidence_pre_cap, gene_names=all_names)
        evidence_graded = list(evidence)
        llm = grade_from_evidence(
            client,
            gene=bundle.hgnc_symbol,
            evidence=evidence,
            synonyms=synonyms,
            usage_sink=usage,
            model=model,
        )

        # Deterministic backstop for the modulator DIRECTION rule (modulator -> target):
        # drop any modulator_observation whose `modulator` field names the target itself.
        _target_syms = {bundle.hgnc_symbol.upper()} | {
            a.upper()
            for a in (*bundle.aliases, *bundle.previous_symbols)
            if len(a) >= 4
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

        # Defense-in-depth: prune any span-verified source cited by no observation,
        # no per-mode grade (including pathogen_entry!), and no kept modulator.
        cited_ids: set[str] = {
            sid for o in llm.observations for sid in o.cited_source_ids
        }
        cited_ids.update(sid for m in modulators for sid in m.cited_source_ids)
        for mode in (
            llm.grades_by_mode.basal,
            llm.grades_by_mode.native_ligand,
            llm.grades_by_mode.therapeutic,
            llm.grades_by_mode.pathogen_entry,
        ):
            cited_ids.update(mode.cited_source_ids)
        if cited_ids:
            evidence = [e for e in evidence if e.evidence_id in cited_ids]

        has_primary_or_invivo = any(
            o.cell_context in ("primary", "in_vivo") for o in llm.observations
        )
        species_scope = rollup_species_scope(llm.observations)

        n_refusals = sum(
            1 for u in usage if getattr(u, "api_stop_reason", None) == "refusal"
        )
        cache_read_tok = sum(int(getattr(u, "cache_read_input_tokens", 0) or 0) for u in usage)
        cache_write_tok = sum(int(getattr(u, "cache_creation_input_tokens", 0) or 0) for u in usage)
        if cache_read_tok or cache_write_tok:
            logger.info(
                "%s: prompt cache read=%d write=%d tokens",
                bundle.hgnc_symbol,
                cache_read_tok,
                cache_write_tok,
            )
        track = LiteratureTrack(
            grades_by_mode=llm.grades_by_mode,
            overall_grade=llm.overall_grade,
            overall_confidence=llm.overall_confidence,
            rationale=llm.rationale,
            cross_condition_note=llm.cross_condition_note,
            trafficking_summary=llm.trafficking_summary,
            predominant_fate=llm.predominant_fate,
            epitope_or_valency_dependence_note=llm.epitope_or_valency_dependence_note,
            ligand_dependence_summary=llm.ligand_dependence_summary,
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
            model=model,
            triage_model=triage_model,
            cost_usd=round(sum(getattr(u, "cost_usd", 0.0) or 0.0 for u in usage), 4),
            n_model_calls=len(usage),
            n_refusals=n_refusals,
            web_search_used=web_search_used,
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
                record.model_dump_json(indent=2), encoding="utf-8"
            )

        if intermediates_dir is not None or upload_to_r2:
            n_quant_obs = sum(
                1 for o in llm.observations if o.quant and o.quant.rate_value is not None
            )
            n_derived_kinetics = sum(
                1
                for o in llm.observations
                if o.quant and o.quant.derived_t_half_min is not None
            )
            inter_payload = build_intermediates_payload(
                gene_symbol=bundle.hgnc_symbol,
                hgnc_id=bundle.hgnc_id,
                uniprot_acc=bundle.uniprot_acc,
                run_id=run_id,
                schema_version=SCHEMA_VERSION,
                lit_prompt_version=LIT_PROMPT_VERSION,
                lit_prompt_sha=track.prompt_sha or lit_prompt_sha(),
                triage_prompt_sha=triage_prompt_sha(),
                model=model,
                triage_model=triage_model,
                web_scout_model=effective_web_scout_model,
                web_search_mode=ws_mode,
                web_search_used=web_search_used,
                web_search_reason=web_search_reason,
                web_search_paper_ids=web_search_paper_ids,
                extra_paper_ids=list(extra_paper_ids or ()),
                discovered=discovered,
                outcomes=outcomes,
                triage_input_shas={
                    sid: triage_input_sha(p) for sid, p in papers_by_id.items()
                },
                actions=actions,
                pool=pool,
                evidence_pre_cap=evidence_pre_cap,
                evidence_graded=evidence_graded,
                usage=usage,
                summary={
                    "overall_grade": track.overall_grade,
                    "overall_confidence": track.overall_confidence,
                    "n_observations": track.n_observations,
                    "n_quant_obs": n_quant_obs,
                    "n_derived_kinetics": n_derived_kinetics,
                    "n_refusals": track.n_refusals,
                    "predominant_fate": track.predominant_fate,
                    "cost_usd": track.cost_usd,
                    "cache_read_tokens": cache_read_tok,
                    "cache_write_tokens": cache_write_tok,
                },
            )
            if intermediates_dir is not None:
                save_intermediates_local(
                    intermediates_dir / f"{record.gene_symbol}.json.gz",
                    inter_payload,
                )
            if upload_to_r2:
                ok_r2, r2_key = upload_intermediates_r2(
                    inter_payload,
                    gene_symbol=record.gene_symbol,
                    run_id=run_id,
                    cfg=r2_cfg,
                )
                if not ok_r2:
                    logger.warning(
                        "%s: R2 intermediates upload failed (%s) — continuing",
                        record.gene_symbol,
                        r2_key,
                    )

        return record
    finally:
        if owns_http and hasattr(http_client, "close"):
            http_client.close()
