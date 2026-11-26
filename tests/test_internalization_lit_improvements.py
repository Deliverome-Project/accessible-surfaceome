"""Unit tests for the internalization literature v0.2.0 improvements:
- benchmark loader & deterministic scorer (bogus quant, mode violations, abstention)
- internalization_relevance & boost_internalization_clips
- PubTator minimal-query + PMC-aware PMID deduplication
- triage_cache prompt_sha + input_sha invalidation
- grade sanitization (bogus quant, ADC-in-basal, cell-line species, pathogen_entry)
- end-to-end priced UsageRecord cost accounting (including web_search_requests)
- adaptive web_search gating and pathogen_entry citation retention
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast

from accessible_surfaceome.agents._support.pricing import (
    record_from_response,
    resolve_pricing_key,
)
from accessible_surfaceome.agents._support.structured_call import call_model_structured
from accessible_surfaceome.agents.internalization import (
    literature_discovery as disc_mod,
    literature_runner as run_mod,
    triage_cache,
)
from accessible_surfaceome.agents.internalization.benchmark import (
    BenchmarkSummary,
    check_observation_mode_issue,
    check_observation_quant_issue,
    format_report,
    load_benchmark,
    score_record,
)
from accessible_surfaceome.agents.internalization.literature_discovery import (
    boost_internalization_clips,
    clean_query_aliases,
    internalization_relevance,
)
from accessible_surfaceome.agents.internalization.literature_grade import (
    _sanitize_grade_output,
    _scrub_unknown_cites,
    derive_universal_kinetics,
    rollup_species_scope,
)
from accessible_surfaceome.agents.internalization.models import (
    GradesByMode,
    InternalizationObservation,
    InternalizationQuant,
    InternalizationRecord,
    LiteratureLLMOut,
    LiteratureTrack,
    ModeGrade,
    ModulatorObservation,
)
from accessible_surfaceome.agents.plan_trim_select.abstract_triage import TriageOutcome
from accessible_surfaceome.agents.plan_trim_select.schemas import AbstractTriageResponse
from accessible_surfaceome.tools._shared.models import EvidenceClaimDraft


def test_benchmark_tsv_loads_all_categories():
    rows = load_benchmark()
    assert len(rows) >= 20
    cats = {r.category for r in rows}
    assert {"fast_constitutive", "ligand_switch", "therapeutic_anchor", "low_or_negative", "abstention"} <= cats


def test_quant_and_mode_hygiene_checks_catch_v019_failure_modes():
    # Bare time point stuffed into rate_value (NECTIN4 / TNFRSF17 v0.1.9 bug)
    obs_time = InternalizationObservation(
        assay_type="adc_internalization",
        internalization_mode="basal",
        ligand_name="J6M0-MMAF (anti-BCMA ADC)",
        quant=InternalizationQuant(
            rate_metric="other", rate_value=1.0, rate_unit="h", time_point="1 h", quant_summary="internalized within 1 h"
        ),
    )
    assert check_observation_quant_issue(obs_time) is not None
    assert check_observation_mode_issue(obs_time) is not None

    # cAMP signaling readout stuffed into rate_value (AVPR2 v0.1.9 bug)
    obs_camp = InternalizationObservation(
        assay_type="live_imaging",
        internalization_mode="native_ligand",
        quant=InternalizationQuant(
            rate_metric="other", rate_value=32.0, rate_unit="fold cAMP increase", quant_summary="32-fold cAMP increase"
        ),
    )
    assert check_observation_quant_issue(obs_camp) is not None

    # Legitimate half-life passes cleanly
    obs_ok = InternalizationObservation(
        assay_type="ligand_uptake",
        internalization_mode="basal",
        rate_class="gross_entry",
        quant=InternalizationQuant(
            rate_metric="half_life", rate_value=3.5, rate_unit="min", quant_summary="t1/2 = 3.5 min"
        ),
    )
    assert check_observation_quant_issue(obs_ok) is None
    assert check_observation_mode_issue(obs_ok) is None


def test_sanitize_grade_output_fixes_quant_mode_species_and_overall():
    out = LiteratureLLMOut(
        grades_by_mode=GradesByMode(
            pathogen_entry=ModeGrade(grade="high", confidence="moderate", cited_source_ids=["int_evi_01", "BOGUS"])
        ),
        overall_grade="high",  # should NOT be driven by pathogen_entry alone
        overall_confidence="moderate",
        observations=[
            InternalizationObservation(
                assay_type="adc_internalization",
                cell_line="LNCaP",
                species=None,
                internalization_mode="basal",  # misfiled!
                ligand_name="J591-ADC",
                quant=InternalizationQuant(
                    rate_metric="other", rate_value=30.0, rate_unit="min", quant_summary="internalized within 30 min"
                ),
                cited_source_ids=["int_evi_01", "NOPE"],
            )
        ],
        modulator_observations=[
            ModulatorObservation(modulator="AP2M1", cited_source_ids=["int_evi_01", "NOPE"])
        ],
    )
    scrubbed = _scrub_unknown_cites(out, known={"int_evi_01"})
    assert scrubbed.grades_by_mode.pathogen_entry.cited_source_ids == ["int_evi_01"]
    assert scrubbed.modulator_observations[0].cited_source_ids == ["int_evi_01"]

    clean = _sanitize_grade_output(scrubbed)
    assert clean.overall_grade == "unknown"  # pathogen_entry cannot drive overall_grade
    o = clean.observations[0]
    assert o.species == "human"  # inferred from LNCaP
    assert o.internalization_mode == "therapeutic"  # ADC moved out of basal
    assert o.quant.rate_value is None  # bare 30 min scrubbed
    assert o.quant.time_point == "30 min"
    assert o.rate_class == "qualitative_only"
    assert rollup_species_scope(clean.observations) == "human"


def test_internalization_relevance_ranks_kinetics_above_preamble():
    score = internalization_relevance(["TFRC", "transferrin receptor"])
    preamble = "Transferrin receptor is well known to be a promising target for drug delivery."
    kinetic = (
        "In HepG2 cells, surface-labeled transferrin receptor internalized constitutively "
        "by acid-strip assay with a half-time of 3.5 min (k_e = 0.20 per min)."
    )
    assert score(kinetic) > score(preamble) + 5.0

    pool = {
        "c1": EvidenceClaimDraft(
            suggested_evidence_id="c1",
            quote=preamble,
            source_id="PMID:1",
            section="introduction",
            hallmark_phrase="paper_level",
            score=1.9,
        ),
        "c2": EvidenceClaimDraft(
            suggested_evidence_id="c2",
            quote=kinetic,
            source_id="PMID:1",
            section="results",
            hallmark_phrase="paper_level",
            score=1.2,
        ),
    }
    n = boost_internalization_clips(pool, gene_names=["TFRC", "transferrin receptor"])
    assert n == 1
    assert (pool["c2"].score or 0.0) > (pool["c1"].score or 0.0)


def test_pubtator_uses_minimal_queries_and_dedupes_against_pmc_keyed_papers(monkeypatch):
    pt_queries: list[str] = []
    bulk_pmids: list[list[int]] = []

    p1 = SimpleNamespace(pmid=111, pmc_id="PMC111", doi=None, is_retracted=False)
    p2 = SimpleNamespace(pmid=222, pmc_id=None, doi=None, is_retracted=False)

    monkeypatch.setattr(
        disc_mod,
        "europepmc_search",
        lambda *, http, query, page_size=25, sort=None: {"resultList": {"result": [{"pmid": "111"}]}},
    )
    monkeypatch.setattr(disc_mod, "paper_from_europepmc", lambda rec, **kw: p1)
    monkeypatch.setattr(
        disc_mod,
        "pubtator_search",
        lambda *, http, query, page=1, sort="score desc": (
            pt_queries.append(query),
            SimpleNamespace(hits=[SimpleNamespace(pmid=111), SimpleNamespace(pmid=222)]),
        )[1],
    )
    monkeypatch.setattr(
        disc_mod,
        "europepmc_bulk_by_pmid",
        lambda *, http, pmids, retraction_index, **kw: (bulk_pmids.append(list(pmids)), [p2])[1],
    )

    bundle = SimpleNamespace(
        hgnc_symbol="ERBB2",
        aliases=["HER2", "T9"],
        previous_symbols=[],
        approved_name="erb-b2 receptor tyrosine kinase 2",
        alias_names=[],
    )
    out = disc_mod.discover_internalization_papers(
        cast(Any, bundle), http=cast(Any, object()), retraction_index=cast(Any, object())
    )
    # Two minimal single-term PubTator queries instead of 4 ANDed words
    assert len(pt_queries) == 2
    assert any("internalization" in q and "endocytosis" not in q for q in pt_queries)
    assert any("endocytosis" in q and "internalization" not in q for q in pt_queries)
    # PMID 111 was already present under PMC:PMC111 -> NOT re-requested from bulk
    assert bulk_pmids == [[222]]
    assert set(out) == {"PMC:PMC111", "PMID:222"}
    assert "T9" not in clean_query_aliases(cast(Any, bundle))


def test_triage_cache_roundtrip_and_invalidation(tmp_path):
    p1 = SimpleNamespace(pmid=1, pmc_id=None, doi=None, title="T1", abstract="A1")
    p2 = SimpleNamespace(pmid=2, pmc_id=None, doi=None, title="T2", abstract="A2")
    outcomes = [
        TriageOutcome(
            paper_id="PMID:1",
            response=AbstractTriageResponse(paper_id="PMID:1", decision="worth_fetching", reason="quant"),
            usage=None,
            elapsed_s=0.1,
            error=None,
        ),
        TriageOutcome(paper_id="PMID:2", response=None, usage=None, elapsed_s=0.1, error="timeout"),
    ]
    n = triage_cache.save(
        "TFRC",
        outcomes,
        prompt_sha="sha_v1",
        inputs={"PMID:1": triage_cache.input_sha(p1), "PMID:2": triage_cache.input_sha(p2)},
        cache_dir=tmp_path,
    )
    assert n == 1  # error outcome never cached

    cached = triage_cache.load("TFRC", cache_dir=tmp_path)
    todo, reused = triage_cache.split({"PMID:1": p1, "PMID:2": p2}, cached, prompt_sha="sha_v1")
    assert [p.pmid for p in todo] == [2]
    assert [o.paper_id for o in reused] == ["PMID:1"]

    # Prompt sha change invalidates cached verdict
    todo2, reused2 = triage_cache.split({"PMID:1": p1}, cached, prompt_sha="sha_v2")
    assert len(todo2) == 1 and len(reused2) == 0


def test_pricing_resolves_dated_models_and_counts_web_search_requests():
    assert resolve_pricing_key("claude-haiku-4-5-20251001") == "claude-haiku-4-5"
    raw = SimpleNamespace(
        input_tokens=1000,
        output_tokens=500,
        cache_creation_input_tokens=0,
        cache_read_input_tokens=0,
        server_tool_use=SimpleNamespace(web_search_requests=5),
    )
    rec = record_from_response(raw, "claude-sonnet-4-6")
    # tokens: (1000*3 + 500*15)/1e6 = 0.0105; web_search: 5 * 0.01 = 0.05 -> 0.0605
    assert abs(rec.cost_usd - 0.0605) < 1e-6


def test_call_model_structured_records_priced_usage_record():
    usage_obj = SimpleNamespace(
        input_tokens=2000,
        output_tokens=1000,
        cache_creation_input_tokens=0,
        cache_read_input_tokens=0,
    )
    fake_resp = SimpleNamespace(
        content=[SimpleNamespace(type="text", text='```json\n{"overall_grade": "unknown"}\n```')],
        usage=usage_obj,
        id="msg_1",
        model="claude-sonnet-4-6",
        stop_reason="end_turn",
    )
    client = SimpleNamespace(
        messages=SimpleNamespace(create=lambda **kw: fake_resp)
    )
    sink: list[Any] = []
    call_model_structured(
        client,
        model="claude-sonnet-4-6",
        system_prompt="SYS",
        user_prompt="USR",
        schema=LiteratureLLMOut,
        usage_sink=sink,
    )
    assert len(sink) == 1
    assert sink[0].cost_usd > 0


def test_runner_retains_pathogen_entry_sources_and_reports_abstention_cleanly(tmp_path, monkeypatch):
    from accessible_surfaceome.tools._shared.models import (
        AssayContext,
        Evidence,
        EvidenceSpan,
        SourceRef,
    )

    now = datetime(2026, 1, 1, tzinfo=UTC)
    src = SourceRef(
        source_type="pubmed",
        source_id="PMID:1",
        url="https://pubmed.ncbi.nlm.nih.gov/1/",
        title="t",
        retrieved_at=now,
        content_sha256="a" * 64,
        publication_type="primary_research",
        is_retracted=False,
        retraction_checked_at=now,
    )
    ev1 = Evidence(
        evidence_id="int_evi_01",
        claim="viral entry via receptor",
        claim_type="methodological",
        direction="supports",
        evidence_type="functional_assay",
        evidence_tier="primary",
        confidence="moderate",
        assay_context=AssayContext(species="human"),
        spans=[
            EvidenceSpan(
                source=src,
                section="results",
                quote="virus entered cells via receptor",
                quote_sha256="a" * 64,
                char_offset=0,
                normalized_source_sha256="b" * 64,
            )
        ],
        entailment_verified=True,
    )
    llm = LiteratureLLMOut(
        grades_by_mode=GradesByMode(
            pathogen_entry=ModeGrade(grade="moderate", confidence="moderate", cited_source_ids=["int_evi_01"])
        ),
        overall_grade="unknown",
        overall_confidence="low",
    )
    monkeypatch.setattr(run_mod, "resolve_hgnc_id", lambda g, **kw: "HGNC:11763")
    monkeypatch.setattr(
        run_mod,
        "resolve_by_hgnc_id",
        lambda hid, *, http: SimpleNamespace(
            hgnc_symbol="TFRC",
            hgnc_id=hid,
            uniprot_acc="P02786",
            approved_name="transferrin receptor",
            aliases=[],
            previous_symbols=[],
        ),
    )
    monkeypatch.setattr(
        run_mod,
        "discover_internalization_papers",
        lambda b, *, http, retraction_index, **kw: {"PMID:1": SimpleNamespace(pmid=1)},
    )
    monkeypatch.setattr(run_mod, "paper_source_id", lambda p: f"PMID:{p.pmid}")
    monkeypatch.setattr(run_mod, "triage_internalization_abstracts", lambda *a, **kw: [])
    monkeypatch.setattr(run_mod, "build_pool", lambda *a, **kw: ({}, []))
    monkeypatch.setattr(run_mod, "build_source_store", lambda *a, **kw: object())
    monkeypatch.setattr(run_mod, "select_clips", lambda *a, **kw: SimpleNamespace())
    monkeypatch.setattr(run_mod, "promote", lambda *a, **kw: [ev1])
    monkeypatch.setattr(run_mod, "grade_from_evidence", lambda *a, **kw: llm)

    rec = run_mod.annotate_literature(
        "TFRC", client=object(), http=cast(Any, object()), persist=False, annotations_dir=tmp_path
    )
    assert rec.literature is not None
    # pathogen_entry-only cited source must NOT be pruned
    assert [s.evidence_id for s in rec.literature.sources] == ["int_evi_01"]

    # Score an abstention gene cleanly
    bench = {r.gene_symbol: r for r in load_benchmark()}
    ab_rec = InternalizationRecord(
        schema_version="0.3.0",
        gene_symbol="OR10A3",
        hgnc_id="HGNC:1",
        uniprot_acc="Q8NGE3",
        model_priors=[],
        literature=LiteratureTrack(overall_grade="unknown", overall_confidence="low", cost_usd=0.05),
        generated_at=datetime(2026, 11, 25, tzinfo=UTC),
        runner_version="test",
    )
    sc = score_record(ab_rec, bench["OR10A3"])
    assert sc.overall_ok and sc.abstention_ok
    report = format_report(BenchmarkSummary(scores=[sc]))
    assert "OR10A3" in report and "Abstention accuracy" in report


def test_basal_mode_resets_when_only_adc_observation_is_reclassified():
    out = LiteratureLLMOut(
        grades_by_mode=GradesByMode(
            basal=ModeGrade(grade="high", confidence="moderate", cited_source_ids=["int_evi_01"]),
            therapeutic=ModeGrade(grade="high", confidence="high", cited_source_ids=["int_evi_01"]),
        ),
        overall_grade="high",
        overall_confidence="high",
        observations=[
            InternalizationObservation(
                assay_type="adc_internalization",
                internalization_mode="basal",
                ligand_name="J6M0-MMAF (anti-BCMA ADC)",
                cited_source_ids=["int_evi_01"],
            )
        ],
    )
    clean = _sanitize_grade_output(out)
    assert clean.observations[0].internalization_mode == "therapeutic"
    assert clean.grades_by_mode.basal.grade == "unknown"
    assert clean.grades_by_mode.basal.cited_source_ids == []
    assert clean.overall_grade == "high"


def test_cap_worth_fetching_and_grade_evidence_ledger_cap():
    # Cap worth_fetching prefers quantitative abstract over generic abstract
    papers = {
        "PMID:1": SimpleNamespace(title="Generic", abstract="Protein expressed on cells.", pmc_id=None, cited_by_count=5),
        "PMID:2": SimpleNamespace(title="Kinetics", abstract="Internalization half-time t1/2 = 3.5 min by acid strip.", pmc_id="PMC2", cited_by_count=50),
    }
    outcomes = [
        TriageOutcome(
            paper_id="PMID:1",
            response=AbstractTriageResponse(paper_id="PMID:1", decision="worth_fetching", reason="r"),
            usage=None,
            elapsed_s=0.0,
            error=None,
        ),
        TriageOutcome(
            paper_id="PMID:2",
            response=AbstractTriageResponse(paper_id="PMID:2", decision="worth_fetching", reason="r"),
            usage=None,
            elapsed_s=0.0,
            error=None,
        ),
    ]
    capped = run_mod._cap_worth_fetching(outcomes, papers, gene_names=["TFRC"], max_fetch=1)
    by_id = {o.paper_id: o.response.decision for o in capped}
    assert by_id["PMID:2"] == "worth_fetching"
    assert by_id["PMID:1"] == "keep_abstract"

    # Grade evidence cap enforces per-paper diversity + quant prioritization
    def _mk_ev(i: int, sid: str, quote: str):
        return SimpleNamespace(
            evidence_id=f"int_evi_{i:02d}",
            claim=quote,
            evidence_tier="primary",
            confidence="moderate",
            spans=[SimpleNamespace(quote=quote, source=SimpleNamespace(source_id=sid))],
        )

    evs = [
        *[_mk_ev(i, "PMID:1", f"Generic sentence {i}") for i in range(5)],
        _mk_ev(99, "PMID:2", "Rate constant k_e = 0.015 per min in SKBr3 cells."),
    ]
    chosen = run_mod._select_evidence_for_grading(evs, gene_names=["ERBB2"], max_clips=3, max_per_paper=2)
    assert len(chosen) == 3
    assert chosen[0].evidence_id == "int_evi_99"
    assert sum(1 for e in chosen if e.spans[0].source.source_id == "PMID:1") == 2


def test_derive_universal_kinetics_converts_valid_rates_and_skips_endpoints():
    # 1. CCR5 basal 13.7 %/h -> t1/2 ~ 282 min (~4.7 h)
    q_ccr5_basal = derive_universal_kinetics(
        InternalizationQuant(rate_metric="other", rate_value=13.7, rate_unit="%/h"),
        rate_class="gross_entry",
    )
    assert q_ccr5_basal.rate_metric == "percent_per_hour"
    assert q_ccr5_basal.derived_t_half_min is not None
    assert 275.0 <= q_ccr5_basal.derived_t_half_min <= 290.0

    # 2. CCR5 + CCL5 9.3 %/min -> t1/2 ~ 7.1 min
    q_ccr5_ccl5 = derive_universal_kinetics(
        InternalizationQuant(rate_metric="other", rate_value=9.3, rate_unit="%/min"),
        rate_class="gross_entry",
    )
    assert q_ccr5_ccl5.rate_metric == "percent_per_min"
    assert q_ccr5_ccl5.derived_t_half_min is not None
    assert 6.5 <= q_ccr5_ccl5.derived_t_half_min <= 7.8

    # 3. ERBB2 gross 0.015 /min -> t1/2 = 46.21 min
    q_her2 = derive_universal_kinetics(
        InternalizationQuant(rate_metric="rate_per_min", rate_value=0.015, rate_unit="min^-1"),
        rate_class="gross_entry",
    )
    assert q_her2.derived_t_half_min == 46.21
    assert q_her2.derived_ke_min_inv == 0.015

    # 4. Half-life in hours (7.5 h) -> 450 min
    q_hl = derive_universal_kinetics(
        InternalizationQuant(rate_metric="half_life", rate_value=7.5, rate_unit="h"),
        rate_class="net_accumulation",
    )
    assert q_hl.derived_t_half_min == 450.0

    # 5. Endpoint fraction (60% at 12 h) MUST NOT be converted to a rate constant
    q_ep = derive_universal_kinetics(
        InternalizationQuant(
            rate_metric="percent_internalized",
            rate_value=60.0,
            rate_unit="%",
            time_point="12 h",
            derived_t_half_min=99.0,  # LLM guess must be wiped
        ),
        rate_class="endpoint_fraction",
    )
    assert q_ep.derived_t_half_min is None
    assert q_ep.derived_ke_min_inv is None



def test_intermediates_gzip_roundtrip_and_seed(tmp_path):
    from accessible_surfaceome.agents.internalization.intermediates import (
        build_intermediates_payload,
        compress_intermediates,
        decompress_intermediates,
        force_worth_fetching_outcomes,
        r2_latest_key,
        r2_run_key,
        save_intermediates_local,
        seed_from_intermediates,
    )
    from accessible_surfaceome.agents.plan_trim_select.abstract_triage import TriageOutcome
    from accessible_surfaceome.agents.plan_trim_select.schemas import AbstractTriageResponse
    from accessible_surfaceome.tools._shared.models import Paper

    p = Paper(
        pmid=12345678,
        title="Quantitative endocytosis of TFRC",
        abstract="TFRC internalizes rapidly.",
        year=2024,
        journal="J Cell Biol",
    )
    outcomes = [
        TriageOutcome(
            paper_id="PMID:12345678",
            response=AbstractTriageResponse(
                paper_id="PMID:12345678",
                decision="worth_fetching",
                reason="Direct kinetic measurement",
            ),
            usage=None,
            elapsed_s=0.1,
            error=None,
        )
    ]
    payload = build_intermediates_payload(
        gene_symbol="tfrc",
        hgnc_id="HGNC:11763",
        uniprot_acc="P02786",
        run_id="int_lit_test_1",
        schema_version="0.3.0",
        lit_prompt_version="0.2.1",
        lit_prompt_sha="abc123",
        triage_prompt_sha="def456",
        model="claude-sonnet-5-5",
        triage_model="claude-haiku-5-5",
        web_scout_model="claude-haiku-5-5",
        web_search_mode="adaptive",
        web_search_used=True,
        web_search_reason="quant_papers=0<2",
        web_search_paper_ids=["PMID:12345678"],
        extra_paper_ids=[],
        discovered={"PMID:12345678": p},
        outcomes=outcomes,
        triage_input_shas={"PMID:12345678": "sha_in_1"},
        actions=[],
        pool={},
        evidence_pre_cap=[],
        evidence_graded=[],
        usage=[],
        summary={"overall_grade": "high"},
    )
    gz = compress_intermediates(payload)
    decoded = decompress_intermediates(gz)
    assert decoded["gene_symbol"] == "TFRC"
    assert decoded["web_search_used"] is True

    saved = save_intermediates_local(tmp_path / "TFRC.json.gz", payload)
    assert decompress_intermediates(saved.read_bytes())["run_id"] == "int_lit_test_1"

    papers, triage_cache, ws_ran = seed_from_intermediates(decoded)
    assert "PMID:12345678" in papers
    assert triage_cache["PMID:12345678"]["decision"] == "worth_fetching"
    assert ws_ran is True

    forced = force_worth_fetching_outcomes(papers)
    assert len(forced) == 1
    assert forced[0].response is not None and forced[0].response.decision == "worth_fetching"

    assert r2_latest_key("tfrc") == "internalization_lit_intermediates/TFRC/latest.json.gz"
    assert r2_run_key("tfrc", "run 1/a") == "internalization_lit_intermediates/TFRC/run_1_a.json.gz"


def test_web_search_disk_cache_positive_and_negative(tmp_path):
    from accessible_surfaceome.agents.internalization.literature_discovery import (
        load_web_search_cache,
        save_web_search_cache,
    )

    assert load_web_search_cache("OR1N1", model="claude-haiku-5-5", max_uses=6, cache_dir=tmp_path) is None
    # Negative cache (0 hits) must still return [] (not None!) so we don't re-pay
    save_web_search_cache("OR1N1", [], model="claude-haiku-5-5", max_uses=6, cache_dir=tmp_path)
    assert load_web_search_cache("OR1N1", model="claude-haiku-5-5", max_uses=6, cache_dir=tmp_path) == []
    # Different model invalidates cache
    assert load_web_search_cache("OR1N1", model="claude-sonnet-5-5", max_uses=6, cache_dir=tmp_path) is None
    # Positive hit roundtrips sorted & deduped
    save_web_search_cache("TMEM123", ["DOI:10.1101/b", "DOI:10.1101/a", "DOI:10.1101/a"], model="claude-haiku-5-5", max_uses=6, cache_dir=tmp_path)
    assert load_web_search_cache("TMEM123", model="claude-haiku-5-5", max_uses=6, cache_dir=tmp_path) == ["DOI:10.1101/a", "DOI:10.1101/b"]


def test_cap_worth_fetching_preserves_pinned_extra_papers():
    from accessible_surfaceome.agents.internalization.literature_runner import _cap_worth_fetching
    from accessible_surfaceome.agents.plan_trim_select.abstract_triage import TriageOutcome
    from accessible_surfaceome.agents.plan_trim_select.schemas import AbstractTriageResponse
    from accessible_surfaceome.tools._shared.models import Paper

    papers = {
        f"PMID:{i}": Paper(
            pmid=i,
            title="TFRC rapid internalization kinetics t1/2=4 min",
            abstract="Endocytosis rate constant ke=0.17/min.",
            year=2020,
        )
        for i in range(1, 6)
    }
    papers["DOI:10.1101/pinned"] = Paper(
        doi="10.1101/pinned",
        title="Unusual title without keywords",
        abstract="Short preprint.",
        year=2026,
    )
    outcomes = [
        TriageOutcome(
            paper_id=pid,
            response=AbstractTriageResponse(paper_id=pid, decision="worth_fetching", reason="ok"),
            usage=None,
            elapsed_s=0.0,
            error=None,
        )
        for pid in papers
    ]
    capped = _cap_worth_fetching(
        outcomes,
        papers,
        gene_names=["TFRC"],
        max_fetch=2,
        pinned_ids={"DOI:10.1101/pinned"},
    )
    wf_ids = {o.paper_id for o in capped if o.response and o.response.decision == "worth_fetching"}
    assert "DOI:10.1101/pinned" in wf_ids
    assert len(wf_ids) == 2


def test_publish_seq_record_retries_and_skips_ddl_when_requested():
    from datetime import UTC, datetime

    from accessible_surfaceome.agents.internalization.models import InternalizationRecord
    from accessible_surfaceome.cloud.internalization import publish_seq_record

    class _FlakyD1:
        def __init__(self) -> None:
            self.calls: list[str] = []
            self.failed_once = False

        def query(self, sql: str, params: list | None = None):
            self.calls.append(sql.strip())
            if sql.strip().startswith("INSERT OR REPLACE") and not self.failed_once:
                self.failed_once = True
                raise RuntimeError("transient 502")
            return []

        def close(self) -> None:
            pass

    d1 = _FlakyD1()
    rec = InternalizationRecord(
        schema_version="0.3.0",
        gene_symbol="TFRC",
        hgnc_id="HGNC:11763",
        uniprot_acc="P02786",
        model_priors=[],
        literature=None,
        generated_at=datetime.now(UTC),
        runner_version="test",
    )
    from typing import Any, cast

    publish_seq_record(
        rec,
        client=cast(Any, d1),
        ensure_schema=False,
        purge_edge=False,
        max_retries=2,
    )
    assert not any("CREATE TABLE" in c for c in d1.calls)
    assert sum(1 for c in d1.calls if c.startswith("INSERT OR REPLACE")) == 2
