# Internalization — Literature Track (Plan 2 of N) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the PMID-anchored **literature track** to the internalization record: discover internalization papers for a gene, triage abstracts, fetch full text, extract span-verified quotes, and have a model grade internalization **by mode** (basal / native-ligand / therapeutic) with per-condition observations (assay, cell line, primary-vs-line, ±ligand, quantitative rate) — every claim cited to a PMID with a real char-offset span.

**Architecture:** A second track in the existing standalone `agents/internalization/` package, reusing the `plan_trim_select` machinery (discovery, abstract triage, body fetch, evidence promotion) rather than reinventing it. Unlike the deep-dive orchestrator's *synthetic* source store (char-offsets into a quote-blob), this pass builds a **real** `SourceTextStore` from fetched body text so `promote_claim` yields genuine offsets into the actual paper. Bumps the record `schema_version` `0.1.0 → 0.2.0` and adds a `literature: LiteratureTrack | None` field alongside the shipped `model_priors`.

**Tech Stack:** Python 3.11/3.12, Pydantic v2, Anthropic SDK (Haiku for triage, Sonnet for select + grade) via `messages_create_with_backoff`, `uv`/`pytest`. Reuses `europepmc_search`/`pubtator_search`/`fetch_fulltext`, `apply_triage_outcomes`, `promote_claim`, `SourceTextStore`.

**Design spec:** [docs/superpowers/specs/2026-08-04-internalization-evidence-design.md](../specs/2026-08-04-internalization-evidence-design.md) §4.2.

**Plan 1 recap (shipped):** `agents/internalization/` has `models.py` (schema 0.1.0), `runner.py::annotate_model_prior`, `model_prior.py`, `uniprot_isoforms.py`, `deeptmhmm_topology.py`, `ids.py`, `topology.py`, `prompts/model_prior_system.md`, `scripts/internalization_annotate.py`.

---

## Verified reuse signatures (quote-accurate; do not re-derive)

- `europepmc_search(*, http: CachedHTTP, query: str, page_size: int = 25) -> dict` — raw JSON; hits at `payload["resultList"]["result"]`. `tools/_shared/europepmc.py:64`.
- `paper_from_europepmc(record: dict, *, retraction_index, topic_tagger=None) -> Paper` — per-record coercion. `europepmc.py:487`.
- `europepmc_bulk_by_pmid(*, http, pmids: Sequence[int|str], retraction_index, topic_tagger=None) -> list[Paper]`. `europepmc.py:83`.
- `fetch_fulltext(*, http, pmcid: str, retraction_index, topic_tagger=None) -> Paper` — returns a `Paper` with `.sections: list[PaperSection]`, `.fulltext_fetch_source`. `europepmc.py:182`.
- `pubtator_search(*, http, query: str, page: int = 1, sort="score desc") -> PubTatorSearchResult` (`.hits: list[PubTatorHit]`, each `.pmid:int`). `pubtator.py:55`. `build_gene_entity_query(symbol, free_text_terms="") -> str`. `pubtator.py:33`.
- `triage_abstracts(client, *, papers: list[Paper], gene: str, bundle=None, concurrency=10) -> list[TriageOutcome]` — **uses a FIXED surface-evidence prompt, no template param.** `abstract_triage.py:264`. We write our own internalization triage instead (Task 3).
- `apply_triage_outcomes(outcomes, papers_by_id, *, pool, by_source, http, retraction_index, add_to_pool_fn, fetch_concurrency=5) -> list[TriageAction]`. `abstract_triage.py:1207`.
- `TriageOutcome{paper_id, response: AbstractTriageResponse|None, usage, elapsed_s, error}`; `AbstractTriageResponse{paper_id:str, decision: Literal["discard","keep_abstract","worth_fetching"], reason:str}` (`schemas.py:209`).
- `SourceTextStore.put(source: SourceText, *, replace=False)` / `.get(source_id) -> SourceText | None` / `.has(...)`. Key format `"PMID:<int>"`. `source_text.py:84`. `SourceText` frozen dataclass fields: `source_id, source_type, url, title, raw_text, normalized_text, content_sha256, normalized_source_sha256, retrieved_at, publication_type, is_retracted, retraction_checked_at, license="unknown", authors=(), year=None, journal=None` (`source_text.py:52`).
- `promote_claim(claim: EvidenceClaim, *, store: SourceTextStore) -> Evidence` — store-miss/substring-miss → `Evidence(spans=[], entailment_verified=False, validation_warnings=[...])`; success → real `EvidenceSpan(char_offset, quote_sha256, ...)`. `agents/_support/evidence_promotion.py:50`.
- `normalize_for_quote_matching(text) -> str`. `tools/_shared/normalize.py:60`.
- `Selection` / `SelectionResponse` (`schemas.py:164/187`) — `Selection{clip_id, claim, claim_type, evidence_type, evidence_tier, direction, confidence, assay_context}` (NO quote). `SelectionResponse{selections: list[Selection], notes: str}`.
- `EvidenceClaim` (`models.py:909`) / `EvidenceClaimDraft{suggested_evidence_id, quote, source_id, section, figure_or_table_id, context_excerpt, hallmark_phrase, score}` (`models.py:540`).
- `resolve_by_hgnc_id(hgnc_id, *, http) -> IdentifierBundle`; `open_default_client() -> CachedHTTP`; `messages_create_with_backoff`; `cached_system`; `get_client` — as used in Plan 1.
- Retraction index: `from accessible_surfaceome.tools._shared.retraction_watch import empty as empty_retraction`.

`_add_to_pool` (`runner.py:1070`) and `_promote_selections` (`runner.py:1461`) are module-private; **copy them verbatim** into a shared-within-package helper (reproduced in Tasks 4/5) rather than importing privates.

---

## File Structure

**Modify:**
- `src/accessible_surfaceome/agents/internalization/models.py` — literature-track models; bump `SCHEMA_VERSION = "0.2.0"`; add `literature` field.
- `scripts/internalization_annotate.py` — `--track {model_prior,literature,both}`.

**Create:**
- `agents/internalization/literature_discovery.py` — `discover_internalization_papers`.
- `agents/internalization/literature_triage.py` — internalization abstract triage → `list[TriageOutcome]`.
- `agents/internalization/literature_pool.py` — `_add_to_pool` copy + `build_pool` (wraps `apply_triage_outcomes`) + `build_source_store`.
- `agents/internalization/literature_select.py` — Sonnet selector + `_promote_selections` copy + promotion to `list[Evidence]`.
- `agents/internalization/literature_grade.py` — Sonnet mode-grader → `LiteratureLLMOut`.
- `agents/internalization/literature_runner.py` — `annotate_literature(gene, ...) -> InternalizationRecord`.
- `agents/internalization/prompts/literature_triage_system.md`, `literature_select_system.md`, `literature_grade_system.md`.
- `scripts/probe_internalization_discovery.py` — `$0` discovery/triage probe (no model calls beyond Haiku triage; add `--no-triage` for a pure-$0 discovery check).
- Tests: `tests/test_internalization_lit_models.py`, `_lit_discovery.py`, `_lit_triage.py`, `_lit_pool.py`, `_lit_select.py`, `_lit_grade.py`, `_lit_runner.py`.

---

## Task 1: Literature-track models + schema bump

**Files:** Modify `src/accessible_surfaceome/agents/internalization/models.py`; Test `tests/test_internalization_lit_models.py`.

- [ ] **Step 1: Write the failing test**

```python
import pytest
from pydantic import ValidationError

from accessible_surfaceome.agents.internalization.models import (
    SCHEMA_VERSION,
    GradesByMode,
    InternalizationObservation,
    InternalizationRecord,
    LiteratureLLMOut,
    LiteratureTrack,
    ModeGrade,
)


def test_schema_version_bumped_to_0_2_0():
    assert SCHEMA_VERSION == "0.2.0"


def test_observation_requires_other_label_when_other():
    with pytest.raises(ValidationError):
        InternalizationObservation(assay_type="other")  # missing other_label
    ok = InternalizationObservation(assay_type="other", assay_type_other_label="split-GFP uptake")
    assert ok.assay_type_other_label == "split-GFP uptake"


def test_observation_defaults_are_safe():
    o = InternalizationObservation(assay_type="antibody_uptake")
    assert o.internalization_mode == "unknown"
    assert o.magnitude == "unknown"
    assert o.quant.quant_summary == ""
    assert o.cited_source_ids == []


def test_llm_out_excludes_sources_field():
    # The grader model must not fabricate the promoted-evidence ledger.
    assert "sources" not in set(LiteratureLLMOut.model_fields)
    assert {"grades_by_mode", "overall_grade", "overall_confidence",
            "rationale", "cross_condition_note", "observations"} <= set(LiteratureLLMOut.model_fields)


def test_record_accepts_optional_literature_track():
    from datetime import UTC, datetime
    rec = InternalizationRecord(
        schema_version=SCHEMA_VERSION,
        gene_symbol="TFRC", hgnc_id="HGNC:11763", uniprot_acc="P02786",
        model_priors=[],
        literature=LiteratureTrack(
            grades_by_mode=GradesByMode(therapeutic=ModeGrade(grade="high", confidence="moderate")),
            overall_grade="high", overall_confidence="moderate",
            observations=[InternalizationObservation(assay_type="antibody_uptake")],
            n_observations=1,
        ),
        generated_at=datetime.now(UTC), runner_version="x",
    )
    assert rec.literature.grades_by_mode.therapeutic.grade == "high"
    # literature is optional (model-prior-only records still validate)
    assert InternalizationRecord.model_validate({**rec.model_dump(), "literature": None}).literature is None
```

- [ ] **Step 2: Run to verify it fails** — `uv run pytest tests/test_internalization_lit_models.py -q` → FAIL (`ImportError` for the new names; `SCHEMA_VERSION` still `0.1.0`).

- [ ] **Step 3: Implement** — append to `models.py` (after the existing model-prior models), and change `SCHEMA_VERSION = "0.1.0"` → `SCHEMA_VERSION = "0.2.0"`, and add the `literature` field to `InternalizationRecord`.

Add imports at the top of `models.py` (merge with existing): add `model_validator` to the pydantic import, and:
```python
from accessible_surfaceome.tools._shared.models import Evidence
```

New models to append:
```python
InternalizationMode = Literal["basal", "native_ligand", "therapeutic", "unknown"]
AssayType = Literal[
    "antibody_uptake", "ligand_uptake", "adc_internalization",
    "radioligand_immunopet", "ph_sensitive_dye", "acid_strip_flow",
    "surface_biotinylation", "live_imaging", "receptor_recycling",
    "endocytosis_inhibitor", "other", "unknown",
]
CellContext = Literal[
    "primary", "cell_line", "tumor_cell_line", "ipsc_or_stem",
    "in_vivo", "other", "unknown",
]
Mechanism = Literal[
    "clathrin", "caveolin", "macropinocytosis", "clathrin_independent",
    "receptor_mediated_unspecified", "other", "unknown",
]
Magnitude = Literal["high", "moderate", "low", "none", "unknown"]
RateMetric = Literal["ke_h_inv", "percent_internalized", "half_life", "fold_change", "other"]


class ModeGrade(BaseModel):
    model_config = ConfigDict(extra="forbid")
    grade: Grade = "unknown"
    confidence: GradeConfidence = "low"
    rationale: str = ""
    cited_source_ids: list[str] = Field(default_factory=list)


class GradesByMode(BaseModel):
    model_config = ConfigDict(extra="forbid")
    basal: ModeGrade = Field(default_factory=ModeGrade)
    native_ligand: ModeGrade = Field(default_factory=ModeGrade)
    therapeutic: ModeGrade = Field(default_factory=ModeGrade)


class InternalizationQuant(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rate_metric: RateMetric | None = None
    rate_value: float | None = None
    rate_unit: str | None = None
    time_point: str | None = None
    quant_summary: str = ""


class InternalizationObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    assay_type: AssayType
    assay_type_other_label: str | None = None
    cell_line: str | None = None
    cell_context: CellContext = "unknown"
    internalization_mode: InternalizationMode = "unknown"
    ligand_name: str | None = None
    mechanism: Mechanism | None = None
    magnitude: Magnitude = "unknown"
    quant: InternalizationQuant = Field(default_factory=InternalizationQuant)
    controls_note: str | None = None
    condition_note: str = ""
    cited_source_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_other_label(self) -> "InternalizationObservation":
        if self.assay_type == "other" and not self.assay_type_other_label:
            raise ValueError("assay_type='other' requires assay_type_other_label")
        if self.assay_type != "other" and self.assay_type_other_label is not None:
            raise ValueError("assay_type_other_label must be None unless assay_type=='other'")
        return self


class LiteratureLLMOut(BaseModel):
    """Exact shape the grader model emits — no `sources` (code attaches the
    promoted, span-verified evidence ledger)."""
    model_config = ConfigDict(extra="forbid")
    grades_by_mode: GradesByMode = Field(default_factory=GradesByMode)
    overall_grade: Grade = "unknown"
    overall_confidence: GradeConfidence = "low"
    rationale: str = ""
    cross_condition_note: str = ""
    observations: list[InternalizationObservation] = Field(default_factory=list)


class LiteratureTrack(BaseModel):
    model_config = ConfigDict(extra="forbid")
    grades_by_mode: GradesByMode = Field(default_factory=GradesByMode)
    overall_grade: Grade = "unknown"
    overall_confidence: GradeConfidence = "low"
    rationale: str = ""
    cross_condition_note: str = ""
    species_scope: str = "unspecified"
    species_inferred: bool = False
    observations: list[InternalizationObservation] = Field(default_factory=list)
    sources: list[Evidence] = Field(default_factory=list)
    n_observations: int = 0
    n_papers_discovered: int = 0
    n_papers_fetched: int = 0
```

Change `InternalizationRecord`: add `literature: LiteratureTrack | None = None` (after `model_priors`), and bump `SCHEMA_VERSION`.

- [ ] **Step 4: Run to verify it passes** — `uv run pytest tests/test_internalization_lit_models.py tests/test_internalization_models.py -q` → all pass. (The Plan-1 `test_internalization_models.py::test_record_round_trips` used `schema_version=SCHEMA_VERSION`, so it tracks the bump automatically.)

- [ ] **Step 5: `uv run --frozen ty check src/accessible_surfaceome/agents/internalization` → clean; then commit**
```bash
git add src/accessible_surfaceome/agents/internalization/models.py tests/test_internalization_lit_models.py
git commit -m "feat(agents): internalization literature-track models (schema 0.2.0)"
```

---

## Task 2: Discovery — union EuropePMC + PubTator

**Files:** Create `agents/internalization/literature_discovery.py`; Test `tests/test_internalization_lit_discovery.py`.

Discovery bypasses the closed `TopicAnchor` enum (no `internalization` member) and queries EuropePMC + PubTator directly with internalization terms, merging by PMID.

- [ ] **Step 1: Write the failing test**
```python
from types import SimpleNamespace
from typing import Any, cast

from accessible_surfaceome.agents.internalization import literature_discovery as mod
from accessible_surfaceome.agents.internalization.literature_discovery import (
    build_internalization_query,
    discover_internalization_papers,
)


def test_query_ors_aliases_and_ands_internalization_terms():
    q = build_internalization_query(["TFRC", "CD71", "TFR1"])
    assert "TFRC" in q and "CD71" in q
    assert "internali" in q.lower()
    assert "endocytos" in q.lower()


def _paper(pmid):
    return SimpleNamespace(pmid=pmid)


def test_discovery_unions_and_dedupes_by_pmid(monkeypatch):
    # europepmc_search returns raw hits; paper_from_europepmc coerces each.
    monkeypatch.setattr(mod, "europepmc_search",
                        lambda *, http, query, page_size=25: {"resultList": {"result": [{"pmid": "1"}, {"pmid": "2"}]}})
    monkeypatch.setattr(mod, "paper_from_europepmc",
                        lambda rec, *, retraction_index, topic_tagger=None: _paper(int(rec["pmid"])))
    monkeypatch.setattr(mod, "pubtator_search",
                        lambda *, http, query, page=1, sort="score desc": SimpleNamespace(hits=[SimpleNamespace(pmid=2), SimpleNamespace(pmid=3)]))
    monkeypatch.setattr(mod, "europepmc_bulk_by_pmid",
                        lambda *, http, pmids, retraction_index, topic_tagger=None: [_paper(p) for p in pmids])

    bundle = SimpleNamespace(hgnc_symbol="TFRC", aliases=["CD71"], previous_symbols=[])
    out = discover_internalization_papers(bundle, http=cast(Any, object()), retraction_index=cast(Any, object()))
    assert set(out) == {1, 2, 3}  # dict keyed by pmid, deduped (2 came from both)
```

- [ ] **Step 2: Run → FAIL** (`ModuleNotFoundError`).

- [ ] **Step 3: Implement** `agents/internalization/literature_discovery.py`:
```python
"""Discover internalization papers: union EuropePMC free-text + PubTator
entity search, merged by PMID. Bypasses the closed TopicAnchor enum."""

from __future__ import annotations

from typing import Any

from accessible_surfaceome.tools._shared.europepmc import (
    europepmc_bulk_by_pmid,
    europepmc_search,
    paper_from_europepmc,
)
from accessible_surfaceome.tools._shared.http import CachedHTTP
from accessible_surfaceome.tools._shared.models import IdentifierBundle, Paper
from accessible_surfaceome.tools._shared.pubtator import (
    build_gene_entity_query,
    pubtator_search,
)

_INTERNALIZATION_TERMS = (
    "internali* OR endocytos* OR \"receptor-mediated uptake\" OR "
    "\"antibody internalization\" OR \"ADC internalization\" OR "
    "\"receptor recycling\" OR \"clathrin-mediated\""
)
_MAX_PER_SOURCE = 40


def build_internalization_query(aliases: list[str]) -> str:
    alias_or = " OR ".join(sorted({a for a in aliases if a}))
    return f"({alias_or}) AND ({_INTERNALIZATION_TERMS})"


def discover_internalization_papers(
    bundle: IdentifierBundle,
    *,
    http: CachedHTTP,
    retraction_index: Any,
) -> dict[int, Paper]:
    aliases = [bundle.hgnc_symbol, *bundle.aliases, *bundle.previous_symbols]
    discovered: dict[int, Paper] = {}

    # EuropePMC free-text
    payload = europepmc_search(
        http=http, query=build_internalization_query(aliases), page_size=_MAX_PER_SOURCE
    )
    for rec in payload.get("resultList", {}).get("result", []):
        paper = paper_from_europepmc(rec, retraction_index=retraction_index)
        if paper.pmid:
            discovered.setdefault(paper.pmid, paper)

    # PubTator entity search, hydrated via EuropePMC
    hits = pubtator_search(
        http=http,
        query=build_gene_entity_query(bundle.hgnc_symbol, "internalization endocytosis"),
        sort="date desc",
    ).hits
    pmids = [h.pmid for h in hits if h.pmid and h.pmid not in discovered][:_MAX_PER_SOURCE]
    for paper in europepmc_bulk_by_pmid(http=http, pmids=pmids, retraction_index=retraction_index):
        if paper.pmid:
            discovered.setdefault(paper.pmid, paper)

    return discovered
```

- [ ] **Step 4: Run → PASS.** ty check clean.
- [ ] **Step 5: Commit** — `feat(agents): internalization literature discovery (EuropePMC + PubTator union)`.

---

## Task 3: Internalization abstract triage

**Files:** Create `agents/internalization/literature_triage.py` + `prompts/literature_triage_system.md`; Test `tests/test_internalization_lit_triage.py`.

`plan_trim_select.triage_abstracts` bakes a fixed surface-evidence prompt, so we write a focused internalization triage that emits `TriageOutcome`s (the shape `apply_triage_outcomes` consumes).

- [ ] **Step 1: Write the failing test** (fake Haiku client, reuse the `_FakeClient` pattern from `tests/test_internalization_model_prior.py`):
```python
import json
from types import SimpleNamespace

from accessible_surfaceome.agents.internalization import literature_triage as mod
from accessible_surfaceome.agents.internalization.literature_triage import triage_internalization_abstracts


class _FakeMessages:
    def __init__(self, texts): self._t = list(texts); self.calls = 0
    def create(self, **kw):
        self.calls += 1
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=self._t.pop(0))],
                               usage=SimpleNamespace(input_tokens=1, output_tokens=1), stop_reason="end_turn")


class _FakeClient:
    def __init__(self, texts): self.messages = _FakeMessages(texts)


def _paper(pmid, abstract="cells internalized the antibody"):
    return SimpleNamespace(pmid=pmid, title="t", abstract=abstract)


def test_triage_maps_decisions_per_paper():
    payloads = [
        json.dumps({"paper_id": "PMID:1", "decision": "worth_fetching", "reason": "uptake kinetics"}),
        json.dumps({"paper_id": "PMID:2", "decision": "discard", "reason": "unrelated"}),
    ]
    client = _FakeClient(["```json\n" + p + "\n```" for p in payloads])
    outcomes = mod._make_paper_source_id  # ensure helper exists
    out = triage_internalization_abstracts(client, papers=[_paper(1), _paper(2)], gene="TFRC", system_prompt="SYS")
    assert [o.response.decision for o in out] == ["worth_fetching", "discard"]
    assert out[0].paper_id == "PMID:1"
```

- [ ] **Step 2: Run → FAIL.**

- [ ] **Step 3: Implement** `literature_triage.py`. Reuse `extract_json_object` from `model_prior.py`. Produce `TriageOutcome` + `AbstractTriageResponse` (import both from `plan_trim_select`).
```python
"""Internalization-specific abstract triage (Haiku, 3-way: discard /
keep_abstract / worth_fetching). Emits TriageOutcome objects consumable by
plan_trim_select.apply_triage_outcomes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from accessible_surfaceome.agents._support.api_retry import messages_create_with_backoff
from accessible_surfaceome.agents._support.payload import cached_system
from accessible_surfaceome.agents.internalization.model_prior import extract_json_object
from accessible_surfaceome.agents.plan_trim_select.abstract_triage import TriageOutcome
from accessible_surfaceome.agents.plan_trim_select.schemas import AbstractTriageResponse

HAIKU_MODEL = "claude-haiku-4-5-20251001"
MAX_TOKENS_TRIAGE = 512
_PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "literature_triage_system.md"


def load_triage_prompt() -> str:
    return _PROMPT_PATH.read_text()


def _make_paper_source_id(paper: Any) -> str:
    return f"PMID:{paper.pmid}"


def _text_of(resp: Any) -> str:
    return "".join(getattr(b, "text", "") for b in resp.content
                   if getattr(b, "type", None) == "text").strip()


def triage_internalization_abstracts(
    client: Any, *, papers: list[Any], gene: str, system_prompt: str | None = None,
) -> list[TriageOutcome]:
    system_prompt = system_prompt or load_triage_prompt()
    outcomes: list[TriageOutcome] = []
    for paper in papers:
        pid = _make_paper_source_id(paper)
        user = (f"Gene: {gene}\nPMID: {paper.pmid}\nTitle: {paper.title}\n\n"
                f"Abstract:\n{paper.abstract or '(no abstract)'}\n\n"
                f"Decide: discard | keep_abstract | worth_fetching. "
                f"Use paper_id={pid!r}. Return one ```json object.")
        try:
            resp = messages_create_with_backoff(
                client, model=HAIKU_MODEL, max_tokens=MAX_TOKENS_TRIAGE,
                system=cached_system(system_prompt), messages=[{"role": "user", "content": user}],
            )
            data = extract_json_object(_text_of(resp))
            data.setdefault("paper_id", pid)
            outcomes.append(TriageOutcome(paper_id=pid, response=AbstractTriageResponse.model_validate(data),
                                          usage=None, elapsed_s=0.0, error=None))
        except Exception as err:  # noqa: BLE001 — one bad paper must not kill the batch
            outcomes.append(TriageOutcome(paper_id=pid, response=None, usage=None, elapsed_s=0.0, error=str(err)))
    return outcomes
```
**Confirm `TriageOutcome`'s constructor kwargs** (`abstract_triage.py:137`) match (`paper_id, response, usage, elapsed_s, error`); adjust if the dataclass differs. Fix the test's stray `mod._make_paper_source_id` line into a real assertion (`assert mod._make_paper_source_id(_paper(1)) == "PMID:1"`).

Create `prompts/literature_triage_system.md` — gene-agnostic; keep out specific gene/protein names (leak tests auto-scan). Instruct: keep papers with direct internalization/endocytosis/uptake **measurements** (antibody/ligand/ADC uptake, acid-strip flow, pH-dye, live imaging, k_e/half-life, recycling); `worth_fetching` when the abstract implies quantitative or condition-stratified uptake worth the full text; `keep_abstract` when the abstract itself states an internalization result; `discard` for expression-only / signaling-only / non-endocytic. Uses `{schema}`? No — keep it literal.

- [ ] **Step 4: Run → PASS.** ty clean.
- [ ] **Step 5: Run prompt-leak tests** `uv run pytest tests/test_prompts_no_gene_names.py tests/test_prompt_no_specific_proteins.py -q` → PASS. Commit — `feat(agents): internalization abstract triage + prompt`.

---

## Task 4: Pool + body fetch + real source store

**Files:** Create `agents/internalization/literature_pool.py`; Test `tests/test_internalization_lit_pool.py`.

- [ ] **Step 1: confirm SourceText enum literals** (needed for the constructor — do NOT guess):
```bash
uv run python -c "from accessible_surfaceome.tools._shared.source_text import SourceText; import inspect; print([f.name for f in __import__('dataclasses').fields(SourceText)])"
uv run python -c "from accessible_surfaceome.tools._shared import models as m; import typing; print('SourceType', typing.get_args(m.SourceType)); print('PublicationType', typing.get_args(m.PublicationType)); print('License', typing.get_args(m.License))"
```
Use the printed literal values (e.g. the `SourceType` member for a PubMed paper, a neutral `PublicationType`, and `license="unknown"`) in the constructor below; replace the `<...>` markers accordingly. This is a real confirm-then-fill step, not a placeholder.

- [ ] **Step 2: Write the failing test** — `build_pool` wraps `apply_triage_outcomes`; `build_source_store` registers a real `SourceText` per pooled source_id (full body if fetched, else abstract). Mock `apply_triage_outcomes`, `fetch_fulltext`, and inject fake papers + pool.
```python
from types import SimpleNamespace
from typing import Any, cast

from accessible_surfaceome.agents.internalization import literature_pool as mod
from accessible_surfaceome.agents.internalization.literature_pool import build_source_store


def _draft(sid, quote): return SimpleNamespace(source_id=sid, quote=quote)


def test_source_store_registers_real_body_for_fetched(monkeypatch):
    # one pooled source from a fetched paper -> store body is the full text
    pool = {"c1": _draft("PMID:1", "the receptor internalized rapidly")}
    paper = SimpleNamespace(pmid=1, title="t", abstract="abs", doi=None, pmc_id="PMC9",
                            publication_type=None, is_retracted=False, year=2020, journal="J", authors=[])
    monkeypatch.setattr(mod, "fetch_fulltext",
                        lambda *, http, pmcid, retraction_index, topic_tagger=None:
                        SimpleNamespace(sections=[SimpleNamespace(name="results", text="the receptor internalized rapidly in SKBR3")]))
    store = build_source_store(pool, papers_by_source_id={"PMID:1": (paper, True)},
                               http=cast(Any, object()), retraction_index=cast(Any, object()))
    st = store.get("PMID:1")
    assert st is not None
    assert "internalized rapidly" in st.raw_text
    assert st.normalized_text  # normalized present
```

- [ ] **Step 3: Implement** `literature_pool.py`: copy `_add_to_pool` **verbatim** from `runner.py:1070` (reproduced here), plus `build_pool` and `build_source_store`:
```python
"""Pool construction (body fetch via apply_triage_outcomes) + a REAL
SourceTextStore built from fetched body text, so promote_claim yields genuine
char offsets into the actual paper (NOT the orchestrator's synthetic store)."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from accessible_surfaceome.tools._shared.europepmc import fetch_fulltext
from accessible_surfaceome.tools._shared.http import CachedHTTP
from accessible_surfaceome.tools._shared.models import EvidenceClaimDraft, Paper
from accessible_surfaceome.tools._shared.normalize import normalize_for_quote_matching
from accessible_surfaceome.tools._shared.source_text import SourceText, SourceTextStore
from accessible_surfaceome.agents.plan_trim_select.abstract_triage import (
    TriageAction, apply_triage_outcomes,
)


def _add_to_pool(draft, pool, by_source):  # verbatim copy of runner._add_to_pool
    normalized = normalize_for_quote_matching(draft.quote)
    for existing in by_source.get(draft.source_id, []):
        if normalize_for_quote_matching(existing.quote) == normalized:
            return
    clip_id = draft.suggested_evidence_id
    if clip_id in pool:
        k = 2
        while f"{clip_id}_{k}" in pool:
            k += 1
        clip_id = f"{clip_id}_{k}"
    redrafted = draft.model_copy(update={"suggested_evidence_id": clip_id})
    pool[clip_id] = redrafted
    by_source[redrafted.source_id].append(redrafted)


def build_pool(outcomes, papers_by_id, *, http: CachedHTTP, retraction_index: Any):
    pool: dict[str, EvidenceClaimDraft] = {}
    by_source: dict[str, list[EvidenceClaimDraft]] = defaultdict(list)
    actions = apply_triage_outcomes(
        outcomes, papers_by_id, pool=pool, by_source=by_source,
        http=http, retraction_index=retraction_index, add_to_pool_fn=_add_to_pool,
    )
    return pool, actions


def _body_text(paper: Paper, *, fetched: bool, http: CachedHTTP, retraction_index: Any) -> str:
    if fetched and paper.pmc_id:
        full = fetch_fulltext(http=http, pmcid=paper.pmc_id, retraction_index=retraction_index)
        secs = getattr(full, "sections", None) or []
        joined = "\n\n".join(s.text for s in secs if getattr(s, "text", None))
        if joined:
            return joined
    return paper.abstract or ""


def build_source_store(
    pool: dict[str, EvidenceClaimDraft],
    *,
    papers_by_source_id: dict[str, tuple[Paper, bool]],  # source_id -> (paper, was_fetched)
    http: CachedHTTP,
    retraction_index: Any,
) -> SourceTextStore:
    store = SourceTextStore()
    for source_id in {d.source_id for d in pool.values()}:
        entry = papers_by_source_id.get(source_id)
        if entry is None:
            continue
        paper, fetched = entry
        raw = _body_text(paper, fetched=fetched, http=http, retraction_index=retraction_index)
        if not raw:
            continue
        norm = normalize_for_quote_matching(raw)
        now = datetime.now(UTC)
        store.put(SourceText(
            source_id=source_id,
            source_type=<SOURCE_TYPE_PUBMED>,        # from Step 1
            url=f"https://pubmed.ncbi.nlm.nih.gov/{source_id.split(':', 1)[1]}/",
            title=paper.title,
            raw_text=raw,
            normalized_text=norm,
            content_sha256=hashlib.sha256(raw.encode("utf-8")).hexdigest(),
            normalized_source_sha256=hashlib.sha256(norm.encode("utf-8")).hexdigest(),
            retrieved_at=now,
            publication_type=<PUBLICATION_TYPE_DEFAULT>,   # from Step 1
            is_retracted=bool(getattr(paper, "is_retracted", False)),
            retraction_checked_at=now,
            license="unknown",
            year=getattr(paper, "year", None),
            journal=getattr(paper, "journal", None),
        ))
    return store
```
Replace `<SOURCE_TYPE_PUBMED>` / `<PUBLICATION_TYPE_DEFAULT>` with the literals confirmed in Step 1.

- [ ] **Step 4: Run → PASS.** ty clean. Commit — `feat(agents): internalization pool + real source-text store`.

---

## Task 5: Selection + promotion (real spans)

**Files:** Create `agents/internalization/literature_select.py` + `prompts/literature_select_system.md`; Test `tests/test_internalization_lit_select.py`.

- [ ] **Step 1: Write the failing test** — Sonnet selector returns `SelectionResponse`; `_promote_selections` (copied) maps clip_ids → `EvidenceClaim` with verbatim pool quotes; `promote_claim` against the real store yields `Evidence` with a span when the quote substring-matches. Use a real `SourceTextStore` seeded with a body containing the quote.

- [ ] **Step 2: Run → FAIL.**

- [ ] **Step 3: Implement** `literature_select.py`: copy `_promote_selections` **verbatim** from `runner.py:1461` (with `evidence_id_prefix="int_evi_"`), add `select_clips(client, *, pool, gene, system_prompt) -> SelectionResponse` (Sonnet call over a rendered clip menu, structured-output against `SelectionResponse`, reuse `call_model_structured`-style repair from `model_prior.py`), and `promote(selection, *, pool, store) -> list[Evidence]` = `[promote_claim(c, store=store) for c in _promote_selections(selection, pool=pool, evidence_id_prefix="int_evi_")[0]]`. Prompt `literature_select_system.md`: gene-agnostic, "pick the clips that are direct internalization measurements; do not paraphrase; classify each."

- [ ] **Step 4: Run → PASS.** Commit — `feat(agents): internalization clip selection + span-verified promotion`.

---

## Task 6: Mode-grading

**Files:** Create `agents/internalization/literature_grade.py` + `prompts/literature_grade_system.md`; Test `tests/test_internalization_lit_grade.py`.

- [ ] **Step 1: Write the failing test** — fake Sonnet returns a `LiteratureLLMOut` JSON (grades_by_mode + observations); `grade_from_evidence(client, *, gene, evidence, system_prompt) -> LiteratureLLMOut` validates + returns it. Assert an `assay_type='other'`-without-label payload triggers the repair loop.

- [ ] **Step 2: Run → FAIL.**

- [ ] **Step 3: Implement** `literature_grade.py`: `grade_from_evidence(...)` renders the promoted `Evidence` ledger (evidence_id + quote + source_id + section) into a user prompt and calls Sonnet with structured output against `LiteratureLLMOut` (reuse the repair loop from `model_prior.call_model_structured`, parameterized on schema). Prompt `literature_grade_system.md`: gene-agnostic; grade **per mode** (basal / native-ligand / therapeutic), each `high|low|no|unknown` + confidence + cited_source_ids; emit observations with assay/cell-context/mode/quant; overall_grade; cross_condition_note summarizing differences across conditions/cells; **cite only source_ids present in the provided ledger** (post-filter in code against the promoted evidence_ids, dropping unknown cites like Plan 1's model-prior scrub).

- [ ] **Step 4: Run → PASS.** Leak tests PASS. Commit — `feat(agents): internalization mode-grader + prompt`.

---

## Task 7: Literature runner

**Files:** Create `agents/internalization/literature_runner.py`; Test `tests/test_internalization_lit_runner.py`.

- [ ] **Step 1: Write the failing test** — monkeypatch every sub-step (`resolve_hgnc_id`, `resolve_by_hgnc_id`, `discover_internalization_papers`, `triage_internalization_abstracts`, `build_pool`, `build_source_store`, `select_clips`, `promote`, `grade_from_evidence`); assert `annotate_literature("TFRC", client=..., http=...)` returns an `InternalizationRecord` (schema 0.2.0) whose `.literature` is a populated `LiteratureTrack` with `sources` = the promoted evidence and `n_papers_discovered`/`n_observations` set; persists to `data/annotations/internalization/{SYMBOL}.json` when `persist=True`.

- [ ] **Step 2: Run → FAIL.**

- [ ] **Step 3: Implement** `literature_runner.py::annotate_literature(gene, *, client=None, http=None, persist=True, annotations_dir=None) -> InternalizationRecord`: resolve → `discover` → `triage` → `build_pool` → build `papers_by_source_id` (from discovered papers + which were fetched, read off the `TriageAction.decision=="worth_fetching"` + `fetched_body`) → `build_source_store` → `select_clips` → `promote` → `grade_from_evidence` → assemble `LiteratureTrack(**llm_out, sources=promoted, n_observations=len(llm_out.observations), n_papers_discovered=len(discovered), n_papers_fetched=<count>)` → `InternalizationRecord(schema_version=SCHEMA_VERSION, ..., model_priors=[], literature=track, ...)`. **Validate before persist.**

- [ ] **Step 4: Run → PASS.** ty + ruff clean. Commit — `feat(agents): internalization literature runner`.

---

## Task 8: CLI `--track`

**Files:** Modify `scripts/internalization_annotate.py`.

- [ ] **Step 1:** add `--track {model_prior,literature,both}` (default `both`). For `model_prior`/`both` call `annotate_model_prior`; for `literature`/`both` call `annotate_literature`. When `both`, merge: run model-prior, then literature, and write ONE record carrying both `model_priors` and `literature` (the literature runner should accept an optional `model_priors=` to fold in, or the CLI assembles the merged record). Simplest: `annotate_literature` takes `model_priors: list[ModelPriorTrack] | None = None` and includes them; `both` runs model-prior first and passes its `.model_priors` in.
- [ ] **Step 2:** `uv run python scripts/internalization_annotate.py --help` parses; exit 0.
- [ ] **Step 3: real smoke** (needs `.env` + hydrated data): `uv run python scripts/internalization_annotate.py TFRC --track literature` → prints grades_by_mode + n observations + n sources; `data/annotations/internalization/TFRC.json` validates at schema 0.2.0 with a populated `literature`. Spot-check a therapeutic-ADC control (e.g. ERBB2) shows a `therapeutic` mode grade with ≥1 PMID-cited observation.
- [ ] **Step 4:** `bash scripts/check-py.sh` (green except the pre-existing TGOLN2 flake — confirm no NEW failures; run `check_viewer_types_sync.py` separately as in Plan 1). Commit — `feat(agents): CLI --track for internalization literature pass`.

---

## Task 9: `$0` discovery probe

**Files:** Create `scripts/probe_internalization_discovery.py`.

- [ ] **Step 1:** a script that runs `discover_internalization_papers` for a gene and prints PMID count + titles (no model calls with `--no-triage`; optional Haiku triage summary otherwise) — the analog of `scripts/probe_triage_fetch.py`, for validating retrieval before spending Sonnet.
- [ ] **Step 2:** run over the 6 controls; confirm each returns a non-trivial corpus (TFRC/EGFR large; ENPP3 smaller). Commit — `feat(agents): $0 internalization discovery probe`.

---

## Definition of done (Plan 2)
- `scripts/internalization_annotate.py TFRC --track literature` produces a schema-0.2.0 `InternalizationRecord` with a populated `literature` track: grades-by-mode, observations (assay/cell-context/mode/quant), and a `sources` ledger of span-verified `Evidence` each carrying a real `char_offset` + PMID.
- Span verification is genuine (real `SourceTextStore` from fetched bodies — NOT the synthetic-quote-blob shortcut). Spot-check: every `sources[*].spans[0].char_offset` indexes the real body.
- The 6 controls grade sensibly by mode (therapeutic present for the ADC targets; TFRC basal+native high; CD20 low across modes).
- `bash scripts/check-py.sh` green except the pre-existing TGOLN2 flake; prompt-leak tests green.

## Self-review notes (checked while writing)
- Schema bump is additive + optional (`literature: … | None`), so Plan-1 model-prior-only records still validate. ✓
- `LiteratureLLMOut` excludes `sources` (code attaches promoted evidence), mirroring Plan 1's `ModelPriorLLMOut` boundary. ✓
- Real source store (Task 4) is the one genuine integration risk; Step-1 confirm-then-fill for the `SourceText` enum literals avoids guessing. ✓
- `_add_to_pool` / `_promote_selections` copied verbatim (private, no coupling) rather than imported. ✓
- Triage is a purpose-built internalization module (the shared `triage_abstracts` bakes a surface-evidence prompt with no override). ✓

## Follow-on plans
- **Plan 3 — D1 + Worker:** `internalization_annotation` tables (both tracks), publisher, Worker LEFT JOIN, edge purge.
- **Plan 4 — Viewer card + markdown + tooltips** (incl. the "model estimate — not citation-backed" badge on the model-prior track, and mode-stratified literature grades).
- **Plan 5 — Controls report + `--canonical` sweep.**
