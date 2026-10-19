# Internalization — Model-Prior Track (Plan 1 of N) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a standalone pass that, for one gene, fetches its canonical + isoform sequences and topology, asks **both Opus and Sonnet** to grade the protein's *intrinsic endocytic (internalization) propensity* per isoform from parametric knowledge, and writes a validated `InternalizationRecord` (model-prior track only) to `data/annotations/internalization/{SYMBOL}.json`.

**Architecture:** New self-contained package `src/accessible_surfaceome/agents/internalization/`. No cloud/D1 dependency, no literature discovery — that's later plans. The record schema starts at `0.1.0` carrying only `model_priors`; Plan 2 (literature track) will bump it and add the `literature` field. This is the smallest end-to-end vertical slice that exercises the data model and delivers the novel model-prior feature, fully testable offline (all network + model calls mocked in unit tests; one manual real smoke run).

**Tech Stack:** Python 3.12, Pydantic v2, the Anthropic SDK via the repo's `messages_create_with_backoff` wrapper, `uv`/`pytest`. Reuses `resolve_by_hgnc_id`, `uniprot_summary`, `fetch_uniprot_fasta`, `open_default_client`, `get_client`, `load_env`, `cached_system`.

**Design spec:** [docs/superpowers/specs/2026-08-04-internalization-evidence-design.md](../specs/2026-08-04-internalization-evidence-design.md)

**Key reused signatures (verified against the tree):**
- `SONNET_MODEL = "claude-sonnet-4-6"` (`agents/surfaceome_v2/builders/_common.py:41`). **No Opus constant exists** — hard-code `"claude-opus-4-8"` (matches the pricing table so cost lookups won't `KeyError`).
- `call_builder` is **hard-locked to Sonnet internally**, so it cannot make the Opus call — this plan writes its own model-parameterized structured-output helper over `messages_create_with_backoff(client, *, api_metadata_sink=None, **kwargs) -> Message` (`agents/_support/api_retry.py:129`), which injects `temperature` (default 0.2) and retries on rate-limit/5xx.
- `get_client() -> Anthropic` (`agents/_support/client.py:30`) — reads `ANTHROPIC_API_KEY` from env, never passed explicitly.
- `cached_system(system_text) -> list[dict]` (`agents/_support/payload.py:96`).
- `resolve_by_hgnc_id(hgnc_id, *, http: CachedHTTP) -> IdentifierBundle` (`tools/gene_lookup.py:667`); bundle has `uniprot_acc`, `hgnc_symbol`, `hgnc_id`, `ensembl_canonical_protein`, `isoform_count`, `length_aa`.
- `open_default_client() -> CachedHTTP` (`tools/_shared/http.py:338`).
- `uniprot_summary(uniprot_acc, *, http) -> UniProtSummary` (`tools/gene_lookup.py:464`) → `.topology_features: list[TopologyFeature]` (fields `feature_type, description, start, end`) + `.isoforms: list[IsoformRecord]` (fields `isoform_id, name, is_canonical, length_aa` — **no sequence**).
- `fetch_uniprot_fasta(accession, *, timeout, retry_max_attempts, min_request_interval_ms) -> FastaRecord` (`sources/deeptmhmm.py:761`); `FastaRecord` has `.header, .sequence`. Feeding an isoform accession like `P12345-2` returns that isoform's sequence.
- `IsoformRecord`, `TopologyFeature`, `UniProtSummary` live in `tools/_shared/models.py`.
- `REPO_ROOT` + `load_env` importable from `accessible_surfaceome.env`.
- Prompt-leak tests (`tests/test_prompts_no_gene_names.py`, `tests/test_prompt_no_specific_proteins.py`) `rglob("*.md")` over `src/accessible_surfaceome/agents/` — a new prompt under `agents/internalization/prompts/` is **auto-covered, no test wiring needed**.

---

## File Structure

**Create:**
- `src/accessible_surfaceome/agents/internalization/__init__.py` — package marker (docstring only; submodules imported by full path — must stay import-free).
- `src/accessible_surfaceome/agents/internalization/models.py` — Pydantic models + `SCHEMA_VERSION`, `RUNNER_VERSION`.
- `src/accessible_surfaceome/agents/internalization/topology.py` — `summarize_topology(features)`.
- `src/accessible_surfaceome/agents/internalization/uniprot_isoforms.py` — `IsoformContext`, `fetch_isoform_context(uniprot_acc, *, http)`.
- `src/accessible_surfaceome/agents/internalization/model_prior.py` — `extract_json_object`, `call_model_structured`, `grade_isoforms_with_model`, model-id constants.
- `src/accessible_surfaceome/agents/internalization/ids.py` — `resolve_hgnc_id(symbol_or_hgnc, *, cohort_tsv=None)`.
- `src/accessible_surfaceome/agents/internalization/runner.py` — `annotate_model_prior(gene, ...)`, `DEFAULT_MODELS`.
- `src/accessible_surfaceome/agents/internalization/prompts/model_prior_system.md` — gene-agnostic system prompt.
- `scripts/internalization_annotate.py` — CLI driver.
- `tests/test_internalization_models.py`, `tests/test_internalization_topology.py`, `tests/test_internalization_uniprot_isoforms.py`, `tests/test_internalization_model_prior.py`, `tests/test_internalization_ids.py`, `tests/test_internalization_runner.py` (flat in `tests/`, per repo convention — 107 existing test files are flat with unique basenames and no `__init__.py`).

---

## Task 1: Package scaffold + Pydantic models

**Files:**
- Create: `src/accessible_surfaceome/agents/internalization/__init__.py`
- Create: `src/accessible_surfaceome/agents/internalization/models.py`
- Test: `tests/test_internalization_models.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_internalization_models.py`:

```python
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from accessible_surfaceome.agents.internalization.models import (
    SCHEMA_VERSION,
    InternalizationRecord,
    IsoformPrior,
    ModelPriorLLMOut,
    ModelPriorTrack,
)


def _isoform_prior(**over):
    base = dict(
        isoform_id="P00533-1",
        is_canonical=True,
        length_aa=1210,
        topology_summary="1 TM; N-term extracellular; cytoplasmic tail present",
        endocytic_motifs_noted="dileucine in cytoplasmic tail",
        grade="high",
        confidence="moderate",
        rationale="Cytoplasmic tail carries a canonical endocytic sorting motif.",
    )
    base.update(over)
    return IsoformPrior(**base)


def test_isoform_prior_rejects_bad_grade():
    with pytest.raises(ValidationError):
        _isoform_prior(grade="very_high")


def test_model_prior_track_defaults_scope_and_keeps_model():
    track = ModelPriorTrack(
        model="claude-opus-4-8",
        overall_grade="high",
        overall_confidence="moderate",
        model_reasoning="reasons",
        per_isoform=[_isoform_prior()],
    )
    assert track.scope == "intrinsic_propensity"
    assert track.model == "claude-opus-4-8"


def test_llm_out_has_no_model_or_scope_fields():
    # The LLM output schema must NOT carry model/scope (code sets those).
    fields = set(ModelPriorLLMOut.model_fields)
    assert "model" not in fields
    assert "scope" not in fields
    assert fields == {
        "overall_grade",
        "overall_confidence",
        "model_reasoning",
        "per_isoform",
    }


def test_record_round_trips_and_forbids_extra():
    rec = InternalizationRecord(
        schema_version=SCHEMA_VERSION,
        gene_symbol="EGFR",
        hgnc_id="HGNC:3236",
        uniprot_acc="P00533",
        model_priors=[
            ModelPriorTrack(
                model="claude-sonnet-4-6",
                overall_grade="low",
                overall_confidence="low",
                model_reasoning="reasons",
                per_isoform=[_isoform_prior()],
            )
        ],
        generated_at=datetime.now(UTC),
        runner_version="x",
    )
    dumped = rec.model_dump_json()
    again = InternalizationRecord.model_validate_json(dumped)
    assert again.model_priors[0].per_isoform[0].isoform_id == "P00533-1"
    with pytest.raises(ValidationError):
        InternalizationRecord.model_validate({**again.model_dump(), "junk": 1})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_internalization_models.py -q`
Expected: FAIL — `ModuleNotFoundError: accessible_surfaceome.agents.internalization`.

- [ ] **Step 3: Write the models**

Create `src/accessible_surfaceome/agents/internalization/__init__.py`:

```python
"""Standalone protein-internalization pass (separate from the v2 deep-dive).

Package marker only. Import submodules by full path (e.g.
``accessible_surfaceome.agents.internalization.runner``). This ``__init__`` must
stay import-free so importing any submodule works even in partially-built states
(e.g. before ``runner`` exists in Task 7).
"""
```

Create `src/accessible_surfaceome/agents/internalization/models.py`:

```python
"""Pydantic models for the internalization record.

Schema 0.1.0 carries ONLY the model-prior track. Plan 2 (literature track)
bumps the version and adds a ``literature`` field. This record is a separate
artifact from ``SurfaceomeRecord`` with its own schema version.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = "0.1.0"
RUNNER_VERSION = "internalization-model-prior/0.1.0"

Grade = Literal["high", "low", "no", "unknown"]
GradeConfidence = Literal["high", "moderate", "low"]


class IsoformPrior(BaseModel):
    """Model's per-isoform intrinsic-endocytic-propensity grade."""

    model_config = ConfigDict(extra="forbid")

    isoform_id: str
    is_canonical: bool
    length_aa: int | None = None
    topology_summary: str
    endocytic_motifs_noted: str | None = None
    grade: Grade
    confidence: GradeConfidence
    rationale: str = Field(..., description="Why this isoform got this grade.")


class ModelPriorLLMOut(BaseModel):
    """Exact shape the model must emit. No model/scope fields — code sets those."""

    model_config = ConfigDict(extra="forbid")

    overall_grade: Grade
    overall_confidence: GradeConfidence
    model_reasoning: str
    per_isoform: list[IsoformPrior]


class ModelPriorTrack(BaseModel):
    """One model's grade (e.g. Opus or Sonnet). ``scope`` is fixed: a model
    cannot know therapeutic/antibody-induced internalization from sequence, so
    this track speaks only to intrinsic/basal endocytic propensity."""

    model_config = ConfigDict(extra="forbid")

    model: str
    scope: Literal["intrinsic_propensity"] = "intrinsic_propensity"
    overall_grade: Grade
    overall_confidence: GradeConfidence
    model_reasoning: str
    per_isoform: list[IsoformPrior]


class InternalizationRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str
    gene_symbol: str
    hgnc_id: str
    uniprot_acc: str
    model_priors: list[ModelPriorTrack]
    generated_at: datetime
    runner_version: str
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_internalization_models.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add src/accessible_surfaceome/agents/internalization/__init__.py src/accessible_surfaceome/agents/internalization/models.py tests/test_internalization_models.py
git commit -m "feat(agents): internalization record models (model-prior track, schema 0.1.0)"
```

Note: `__init__.py` is intentionally import-free, so importing any submodule (`...internalization.models`) works even before later submodules (`runner`) exist. Never add a top-level `from .runner import ...` to `__init__.py` — it would break submodule imports mid-build.

---

## Task 2: Topology summarizer

**Files:**
- Create: `src/accessible_surfaceome/agents/internalization/topology.py`
- Test: `tests/test_internalization_topology.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_internalization_topology.py`:

```python
from accessible_surfaceome.agents.internalization.topology import summarize_topology
from accessible_surfaceome.tools._shared.models import TopologyFeature


def _f(feature_type, description, start, end):
    return TopologyFeature(
        feature_type=feature_type, description=description, start=start, end=end
    )


def test_summarize_counts_tm_and_notes_sides():
    feats = [
        _f("signal_peptide", "", 1, 24),
        _f("transmembrane", "Helical", 646, 668),
        _f("topological_domain", "Extracellular", 25, 645),
        _f("topological_domain", "Cytoplasmic", 669, 1210),
    ]
    out = summarize_topology(feats)
    assert "1 transmembrane" in out
    assert "signal peptide" in out
    assert "extracellular" in out.lower()
    assert "cytoplasmic" in out.lower()


def test_summarize_empty_is_explicit():
    assert summarize_topology([]) == "No UniProt topology features annotated."
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_internalization_topology.py -q`
Expected: FAIL — `ModuleNotFoundError` for `...internalization.topology`.

- [ ] **Step 3: Implement**

Create `src/accessible_surfaceome/agents/internalization/topology.py`:

```python
"""Render UniProt topology features into a compact prose summary for the
model-prior prompt. Topology features are annotated on the canonical isoform;
the summary is shared across isoforms and the prompt says so."""

from __future__ import annotations

from collections import Counter

from accessible_surfaceome.tools._shared.models import TopologyFeature


def summarize_topology(features: list[TopologyFeature]) -> str:
    if not features:
        return "No UniProt topology features annotated."

    counts: Counter[str] = Counter(f.feature_type for f in features)
    parts: list[str] = []

    if counts.get("signal_peptide"):
        parts.append(f"{counts['signal_peptide']} signal peptide")
    if counts.get("transmembrane"):
        parts.append(f"{counts['transmembrane']} transmembrane segment(s)")
    if counts.get("gpi_anchor"):
        parts.append("GPI-anchored")
    if counts.get("intramembrane"):
        parts.append(f"{counts['intramembrane']} intramembrane segment(s)")

    sides = {
        (f.description or "").strip().lower()
        for f in features
        if f.feature_type == "topological_domain"
    }
    if "extracellular" in sides:
        parts.append("extracellular domain(s) present")
    if "cytoplasmic" in sides:
        parts.append("cytoplasmic domain(s) present")

    if not parts:
        kinds = ", ".join(sorted(counts))
        return f"Topology features present ({kinds}) but no TM/sidedness resolved."
    return "; ".join(parts) + "."
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_internalization_topology.py -q`
Expected: PASS (2 passed).

If `TopologyFeature(...)` rejects any kwarg, run `uv run python -c "from accessible_surfaceome.tools._shared.models import TopologyFeature; print(TopologyFeature.model_fields.keys())"` and adjust the test's `_f` helper + summarizer field names to match — the summarizer logic (count by `feature_type`, read `description` for sidedness) stays the same.

- [ ] **Step 5: Commit**

```bash
git add src/accessible_surfaceome/agents/internalization/topology.py tests/test_internalization_topology.py
git commit -m "feat(agents): topology summarizer for internalization model-prior prompt"
```

---

## Task 3: Isoform context fetch

**Files:**
- Create: `src/accessible_surfaceome/agents/internalization/uniprot_isoforms.py`
- Test: `tests/test_internalization_uniprot_isoforms.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_internalization_uniprot_isoforms.py`:

```python
from types import SimpleNamespace

from accessible_surfaceome.agents.internalization import uniprot_isoforms as mod
from accessible_surfaceome.agents.internalization.uniprot_isoforms import (
    IsoformContext,
    fetch_isoform_context,
)
from accessible_surfaceome.tools._shared.models import IsoformRecord


def test_fetch_maps_each_isoform_to_a_sequence(monkeypatch):
    summary = SimpleNamespace(
        topology_features=[],
        isoforms=[
            IsoformRecord(isoform_id="P00533-1", is_canonical=True, length_aa=1210),
            IsoformRecord(isoform_id="P00533-2", is_canonical=False, length_aa=405),
        ],
    )
    monkeypatch.setattr(mod, "uniprot_summary", lambda acc, *, http: summary)
    monkeypatch.setattr(mod, "summarize_topology", lambda feats: "TOPO")

    seqs = {"P00533-1": "MRPSGTAG" * 10, "P00533-2": "MRPSGTAG" * 3}
    monkeypatch.setattr(
        mod,
        "fetch_uniprot_fasta",
        lambda acc, **kw: SimpleNamespace(header=">x", sequence=seqs[acc]),
    )

    out = fetch_isoform_context("P00533", http=object())
    assert [c.isoform_id for c in out] == ["P00533-1", "P00533-2"]
    assert out[0].is_canonical is True
    assert out[0].sequence == seqs["P00533-1"]
    assert out[0].topology_summary == "TOPO"
    assert all(isinstance(c, IsoformContext) for c in out)


def test_fetch_falls_back_to_acc_when_no_isoforms(monkeypatch):
    summary = SimpleNamespace(topology_features=[], isoforms=[])
    monkeypatch.setattr(mod, "uniprot_summary", lambda acc, *, http: summary)
    monkeypatch.setattr(mod, "summarize_topology", lambda feats: "TOPO")
    monkeypatch.setattr(
        mod,
        "fetch_uniprot_fasta",
        lambda acc, **kw: SimpleNamespace(header=">x", sequence="MSEQ" * 5),
    )

    out = fetch_isoform_context("Q9UBP8", http=object())
    assert len(out) == 1
    assert out[0].isoform_id == "Q9UBP8"
    assert out[0].is_canonical is True
    assert out[0].length_aa == len("MSEQ" * 5)
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_internalization_uniprot_isoforms.py -q`
Expected: FAIL — `ModuleNotFoundError` for `...internalization.uniprot_isoforms`.

- [ ] **Step 3: Implement**

Create `src/accessible_surfaceome/agents/internalization/uniprot_isoforms.py`:

```python
"""Fetch per-isoform amino-acid sequences + a canonical-topology summary.

No repo helper returns per-isoform sequences, so we combine:
  * ``uniprot_summary`` — topology features + isoform metadata (ids, canonical flag)
  * ``fetch_uniprot_fasta(isoform_id)`` — the isoform's sequence (the FASTA
    endpoint accepts isoform-suffixed accessions like ``P00533-2``)
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from accessible_surfaceome.agents.internalization.topology import summarize_topology
from accessible_surfaceome.sources.deeptmhmm import fetch_uniprot_fasta
from accessible_surfaceome.tools._shared.http import CachedHTTP
from accessible_surfaceome.tools._shared.models import IsoformRecord
from accessible_surfaceome.tools.gene_lookup import uniprot_summary

_FASTA_TIMEOUT = 30
_FASTA_RETRIES = 3
_FASTA_INTERVAL_MS = 350


class IsoformContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    isoform_id: str
    is_canonical: bool
    length_aa: int | None
    sequence: str
    topology_summary: str


def fetch_isoform_context(uniprot_acc: str, *, http: CachedHTTP) -> list[IsoformContext]:
    summary = uniprot_summary(uniprot_acc, http=http)
    topo = summarize_topology(summary.topology_features)

    records: list[IsoformRecord] = list(summary.isoforms) or [
        IsoformRecord(isoform_id=uniprot_acc, is_canonical=True, length_aa=None)
    ]

    out: list[IsoformContext] = []
    for iso in records:
        fasta = fetch_uniprot_fasta(
            iso.isoform_id,
            timeout=_FASTA_TIMEOUT,
            retry_max_attempts=_FASTA_RETRIES,
            min_request_interval_ms=_FASTA_INTERVAL_MS,
        )
        out.append(
            IsoformContext(
                isoform_id=iso.isoform_id,
                is_canonical=iso.is_canonical,
                length_aa=iso.length_aa or len(fasta.sequence),
                sequence=fasta.sequence,
                topology_summary=topo,
            )
        )
    return out
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_internalization_uniprot_isoforms.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add src/accessible_surfaceome/agents/internalization/uniprot_isoforms.py tests/test_internalization_uniprot_isoforms.py
git commit -m "feat(agents): per-isoform sequence + topology fetch for internalization"
```

---

## Task 4: Structured model call + per-model grader

**Files:**
- Create: `src/accessible_surfaceome/agents/internalization/model_prior.py`
- Test: `tests/test_internalization_model_prior.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_internalization_model_prior.py`:

```python
import json
from types import SimpleNamespace

import pytest

from accessible_surfaceome.agents.internalization.model_prior import (
    extract_json_object,
    grade_isoforms_with_model,
)
from accessible_surfaceome.agents.internalization.models import ModelPriorTrack
from accessible_surfaceome.agents.internalization.uniprot_isoforms import IsoformContext


def test_extract_json_object_prefers_fenced_block():
    text = "prose\n```json\n{\"a\": 1}\n```\ntail"
    assert extract_json_object(text) == {"a": 1}


def test_extract_json_object_bare_fallback():
    assert extract_json_object('  {"a": 2}  ') == {"a": 2}


def _llm_payload():
    return {
        "overall_grade": "high",
        "overall_confidence": "moderate",
        "model_reasoning": "Rapidly recycling receptor family.",
        "per_isoform": [
            {
                "isoform_id": "P02786-1",
                "is_canonical": True,
                "length_aa": 760,
                "topology_summary": "TOPO",
                "endocytic_motifs_noted": "YXXphi in cytoplasmic tail",
                "grade": "high",
                "confidence": "moderate",
                "rationale": "Cytoplasmic internalization motif present.",
            }
        ],
    }


class _FakeMessages:
    def __init__(self, texts):
        self._texts = list(texts)
        self.calls = 0

    def create(self, **kwargs):
        self.calls += 1
        text = self._texts.pop(0)
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=text)],
            usage=SimpleNamespace(input_tokens=10, output_tokens=20),
            stop_reason="end_turn",
        )


class _FakeClient:
    def __init__(self, texts):
        self.messages = _FakeMessages(texts)


def _isoforms():
    return [
        IsoformContext(
            isoform_id="P02786-1",
            is_canonical=True,
            length_aa=760,
            sequence="MSEQ" * 20,
            topology_summary="TOPO",
        )
    ]


def test_grade_wraps_llm_output_and_stamps_model():
    client = _FakeClient(["```json\n" + json.dumps(_llm_payload()) + "\n```"])
    track = grade_isoforms_with_model(
        client,
        model="claude-opus-4-8",
        system_prompt="SYS",
        gene_symbol="TFRC",
        isoforms=_isoforms(),
    )
    assert isinstance(track, ModelPriorTrack)
    assert track.model == "claude-opus-4-8"
    assert track.scope == "intrinsic_propensity"
    assert track.overall_grade == "high"
    assert track.per_isoform[0].isoform_id == "P02786-1"


def test_grade_repairs_once_on_bad_json():
    good = "```json\n" + json.dumps(_llm_payload()) + "\n```"
    client = _FakeClient(["not json at all", good])
    track = grade_isoforms_with_model(
        client,
        model="claude-sonnet-4-6",
        system_prompt="SYS",
        gene_symbol="TFRC",
        isoforms=_isoforms(),
    )
    assert client.messages.calls == 2
    assert track.overall_grade == "high"


def test_grade_raises_after_exhausting_repairs():
    client = _FakeClient(["nope", "still nope"])
    with pytest.raises(ValueError):
        grade_isoforms_with_model(
            client,
            model="claude-sonnet-4-6",
            system_prompt="SYS",
            gene_symbol="TFRC",
            isoforms=_isoforms(),
        )
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_internalization_model_prior.py -q`
Expected: FAIL — `ModuleNotFoundError` for `...internalization.model_prior`.

- [ ] **Step 3: Implement**

Create `src/accessible_surfaceome/agents/internalization/model_prior.py`:

```python
"""Ask one model (Opus or Sonnet) to grade intrinsic endocytic propensity from
sequence + topology. Model-parameterized because ``call_builder`` is Sonnet-locked."""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import ValidationError

from accessible_surfaceome.agents._support.api_retry import messages_create_with_backoff
from accessible_surfaceome.agents._support.payload import cached_system
from accessible_surfaceome.agents.internalization.models import (
    ModelPriorLLMOut,
    ModelPriorTrack,
)
from accessible_surfaceome.agents.internalization.uniprot_isoforms import IsoformContext

OPUS_MODEL = "claude-opus-4-8"
SONNET_MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 16_000
MAX_REPAIRS = 1

_FENCED_JSON_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def extract_json_object(text: str) -> dict[str, Any]:
    """Pull a JSON object from a model response: last fenced ```json block, else
    the outermost bare {...}. Raises ValueError when neither parses."""
    matches = _FENCED_JSON_RE.findall(text)
    if matches:
        return json.loads(matches[-1])
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        return json.loads(text[start : end + 1])
    raise ValueError("no JSON object found in model response")


def _text_of(resp: Any) -> str:
    return "".join(
        getattr(b, "text", "")
        for b in resp.content
        if getattr(b, "type", None) == "text"
    ).strip()


def _build_user_prompt(gene_symbol: str, isoforms: list[IsoformContext]) -> str:
    lines = [
        f"Gene symbol: {gene_symbol}",
        "",
        "Grade this protein's INTRINSIC / BASAL endocytic (internalization) "
        "propensity per isoform, using your knowledge of this protein plus the "
        "sequences and canonical topology below. Topology is annotated on the "
        "canonical isoform and shared across rows; reason about isoform-specific "
        "sequence differences yourself.",
        "",
    ]
    for i, iso in enumerate(isoforms, 1):
        lines += [
            f"### Isoform {i}: {iso.isoform_id}"
            + (" (canonical)" if iso.is_canonical else ""),
            f"Length: {iso.length_aa} aa",
            f"Canonical topology: {iso.topology_summary}",
            "Sequence:",
            iso.sequence,
            "",
        ]
    lines.append(
        "Return a single ```json fenced object matching the required schema."
    )
    return "\n".join(lines)


def call_model_structured(
    client: Any,
    *,
    model: str,
    system_prompt: str,
    user_prompt: str,
    schema: type[ModelPriorLLMOut],
    usage_sink: list[Any] | None = None,
    max_tokens: int = MAX_TOKENS,
    max_repairs: int = MAX_REPAIRS,
) -> ModelPriorLLMOut:
    messages: list[dict[str, Any]] = [{"role": "user", "content": user_prompt}]
    last_err = ""
    for _ in range(max_repairs + 1):
        resp = messages_create_with_backoff(
            client,
            model=model,
            max_tokens=max_tokens,
            system=cached_system(system_prompt),
            messages=messages,
        )
        if usage_sink is not None:
            usage_sink.append(resp.usage)
        text = _text_of(resp)
        try:
            return schema.model_validate(extract_json_object(text))
        except (ValueError, ValidationError) as err:
            last_err = str(err)[:800]
            messages.append({"role": "assistant", "content": text})
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "That was not valid per the schema. Return ONE ```json "
                        f"fenced object only. Error:\n{last_err}"
                    ),
                }
            )
    raise ValueError(f"model {model} failed schema validation after repairs: {last_err}")


def grade_isoforms_with_model(
    client: Any,
    *,
    model: str,
    system_prompt: str,
    gene_symbol: str,
    isoforms: list[IsoformContext],
    usage_sink: list[Any] | None = None,
) -> ModelPriorTrack:
    out = call_model_structured(
        client,
        model=model,
        system_prompt=system_prompt,
        user_prompt=_build_user_prompt(gene_symbol, isoforms),
        schema=ModelPriorLLMOut,
        usage_sink=usage_sink,
    )
    return ModelPriorTrack(
        model=model,
        overall_grade=out.overall_grade,
        overall_confidence=out.overall_confidence,
        model_reasoning=out.model_reasoning,
        per_isoform=out.per_isoform,
    )
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_internalization_model_prior.py -q`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add src/accessible_surfaceome/agents/internalization/model_prior.py tests/test_internalization_model_prior.py
git commit -m "feat(agents): model-parameterized structured grader for internalization prior"
```

---

## Task 5: Gene-agnostic system prompt

**Files:**
- Create: `src/accessible_surfaceome/agents/internalization/prompts/model_prior_system.md`

- [ ] **Step 1: Write the prompt**

Create `src/accessible_surfaceome/agents/internalization/prompts/model_prior_system.md`:

```markdown
# Role

You are an expert in membrane-protein cell biology, receptor trafficking, and
endocytosis. You grade a human cell-surface protein's **intrinsic / basal
endocytic (internalization) propensity** — how readily the protein is taken
from the plasma membrane into the cell under normal conditions, including
constitutive turnover and endogenous-ligand-driven uptake.

# Scope (read carefully)

- Grade ONLY intrinsic/basal propensity (constitutive ± native-ligand).
- Do NOT grade therapeutic internalization (antibody-, ADC-, or engineered-
  binder-induced uptake). That depends on an external binder you were not given
  and cannot be inferred from sequence.
- This is a **parametric-knowledge estimate**, not a literature review. Do NOT
  fabricate citations, PMIDs, DOIs, k_e values, or specific experiments. If you
  are uncertain, say so and lower the confidence.

# Inputs

You receive a gene symbol, and for the canonical isoform and each alternative
isoform: length, the canonical-isoform topology summary, and the amino-acid
sequence. Use both your knowledge of the protein and sequence-level reasoning.

# What to reason about

- Presence of cytoplasmic endocytic sorting motifs in cytoplasmic regions:
  tyrosine-based YXX[hydrophobic], NPXY, and dileucine [DE]XXXL[LI].
- Topology: a cytoplasmic tail is required to host most endocytic motifs; a
  GPI-anchored or tail-less protein internalizes mainly via bulk/lipid-raft
  routes.
- Isoform differences: an isoform that truncates or replaces the cytoplasmic
  tail may lose internalization competence even with an identical ectodomain —
  grade each isoform on its own sequence.
- The known trafficking behavior of the protein family, when you recognize it.

# Grades

- `high` — robust constitutive and/or native-ligand-driven internalization.
- `low` — slow / limited internalization; predominantly surface-resident.
- `no` — non-internalizing / predominantly non-endocytic.
- `unknown` — you cannot make a defensible call.

# Confidence

- `high` — strong, specific knowledge and/or clear sequence signals.
- `moderate` — reasonable basis, some uncertainty.
- `low` — sparse or conflicting basis.

# Output

Return exactly one ```json fenced object with keys:
`overall_grade`, `overall_confidence`, `model_reasoning`, and `per_isoform`
(a list; each item has `isoform_id`, `is_canonical`, `length_aa`,
`topology_summary`, `endocytic_motifs_noted` (or null), `grade`, `confidence`,
`rationale`). No prose outside the fenced block.
```

Do NOT name any specific human gene or protein anywhere in this file — the
prompt-leak tests scan it. Motif names (YXXΦ, NPXY, dileucine) are fine.

- [ ] **Step 2: Run the prompt-leak tests (they auto-scan the new file)**

Run: `uv run pytest -q tests/test_prompts_no_gene_names.py tests/test_prompt_no_specific_proteins.py`
Expected: PASS. If a token trips the blocklist, rephrase the prompt to remove the gene/protein name (do NOT add to `ALLOWED_TOKENS` unless it is a non-gene technical term).

- [ ] **Step 3: Commit**

```bash
git add src/accessible_surfaceome/agents/internalization/prompts/model_prior_system.md
git commit -m "feat(agents): gene-agnostic system prompt for internalization model-prior"
```

---

## Task 6: Symbol → HGNC-ID resolution

**Files:**
- Create: `src/accessible_surfaceome/agents/internalization/ids.py`
- Test: `tests/test_internalization_ids.py`

Rationale: the stable-ID rule (CLAUDE.md) requires entering resolution through
`hgnc_id`, never a bare symbol. The controls are given as symbols, so map
symbol → hgnc_id via the cohort TSV, then hand the id to `resolve_by_hgnc_id`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_internalization_ids.py`:

```python
import pytest

from accessible_surfaceome.agents.internalization.ids import resolve_hgnc_id


def _write_cohort(tmp_path):
    p = tmp_path / "cohort.tsv"
    p.write_text(
        "symbol\thgnc_id\tother\n"
        "TFRC\tHGNC:11763\tx\n"
        "EGFR\tHGNC:3236\ty\n"
    )
    return p


def test_passthrough_when_already_hgnc_id(tmp_path):
    assert resolve_hgnc_id("HGNC:11763", cohort_tsv=_write_cohort(tmp_path)) == "HGNC:11763"


def test_maps_symbol_case_insensitively(tmp_path):
    cohort = _write_cohort(tmp_path)
    assert resolve_hgnc_id("tfrc", cohort_tsv=cohort) == "HGNC:11763"
    assert resolve_hgnc_id("EGFR", cohort_tsv=cohort) == "HGNC:3236"


def test_unknown_symbol_raises(tmp_path):
    with pytest.raises(LookupError):
        resolve_hgnc_id("NOTAGENE", cohort_tsv=_write_cohort(tmp_path))
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_internalization_ids.py -q`
Expected: FAIL — `ModuleNotFoundError` for `...internalization.ids`.

- [ ] **Step 3: Implement**

Create `src/accessible_surfaceome/agents/internalization/ids.py`:

```python
"""Resolve a gene symbol (or passthrough HGNC id) to a stable HGNC id via the
cohort TSV, honoring the CLAUDE.md stable-identifier rule."""

from __future__ import annotations

import csv
import re
from pathlib import Path

from accessible_surfaceome.env import REPO_ROOT

_HGNC_RE = re.compile(r"^HGNC:\d+$")
_DEFAULT_COHORT = (
    REPO_ROOT
    / "data"
    / "external"
    / "ncbi_gene_info"
    / "Homo_sapiens.protein_coding.with_hgnc.tsv"
)


def resolve_hgnc_id(symbol_or_hgnc: str, *, cohort_tsv: Path | None = None) -> str:
    token = symbol_or_hgnc.strip()
    if _HGNC_RE.match(token):
        return token

    path = cohort_tsv or _DEFAULT_COHORT
    if not path.exists():
        raise LookupError(
            f"cohort TSV not found at {path}; run scripts/bootstrap-worktree.sh candidate"
        )
    wanted = token.upper()
    with path.open(newline="") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            if (row.get("symbol") or "").strip().upper() == wanted:
                hid = (row.get("hgnc_id") or "").strip()
                if hid:
                    return hid
    raise LookupError(f"no hgnc_id for symbol {symbol_or_hgnc!r} in {path}")
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_internalization_ids.py -q`
Expected: PASS (3 passed).

If the real cohort TSV's symbol column is not literally `symbol`, confirm with
`head -1 data/external/ncbi_gene_info/Homo_sapiens.protein_coding.with_hgnc.tsv`
and adjust the `row.get("symbol")` key (the test fixture header must match too).

- [ ] **Step 5: Commit**

```bash
git add src/accessible_surfaceome/agents/internalization/ids.py tests/test_internalization_ids.py
git commit -m "feat(agents): symbol->hgnc_id resolution for internalization pass"
```

---

## Task 7: Runner — assemble the record

**Files:**
- Create: `src/accessible_surfaceome/agents/internalization/runner.py`
- Test: `tests/test_internalization_runner.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_internalization_runner.py`:

```python
import json
from types import SimpleNamespace

from accessible_surfaceome.agents.internalization import runner as mod
from accessible_surfaceome.agents.internalization.models import (
    InternalizationRecord,
    ModelPriorTrack,
)
from accessible_surfaceome.agents.internalization.uniprot_isoforms import IsoformContext


def _prior(model):
    return ModelPriorTrack(
        model=model,
        overall_grade="high",
        overall_confidence="moderate",
        model_reasoning="r",
        per_isoform=[],
    )


def test_annotate_assembles_record_and_persists(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "resolve_hgnc_id", lambda g, **kw: "HGNC:11763")
    monkeypatch.setattr(
        mod,
        "resolve_by_hgnc_id",
        lambda hid, *, http: SimpleNamespace(
            hgnc_symbol="TFRC", hgnc_id=hid, uniprot_acc="P02786"
        ),
    )
    monkeypatch.setattr(
        mod,
        "fetch_isoform_context",
        lambda acc, *, http: [
            IsoformContext(
                isoform_id="P02786-1",
                is_canonical=True,
                length_aa=760,
                sequence="MSEQ" * 10,
                topology_summary="TOPO",
            )
        ],
    )
    monkeypatch.setattr(mod, "load_prompt", lambda: "SYS")

    seen = []
    monkeypatch.setattr(
        mod,
        "grade_isoforms_with_model",
        lambda client, *, model, **kw: seen.append(model) or _prior(model),
    )

    rec = mod.annotate_model_prior(
        "TFRC",
        client=object(),
        http=object(),
        models=("claude-opus-4-8", "claude-sonnet-4-6"),
        annotations_dir=tmp_path,
    )
    assert isinstance(rec, InternalizationRecord)
    assert rec.gene_symbol == "TFRC"
    assert rec.uniprot_acc == "P02786"
    assert [t.model for t in rec.model_priors] == [
        "claude-opus-4-8",
        "claude-sonnet-4-6",
    ]
    assert seen == ["claude-opus-4-8", "claude-sonnet-4-6"]

    written = json.loads((tmp_path / "TFRC.json").read_text())
    assert written["schema_version"] == rec.schema_version
    assert len(written["model_priors"]) == 2


def test_annotate_can_skip_persist(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "resolve_hgnc_id", lambda g, **kw: "HGNC:11763")
    monkeypatch.setattr(
        mod,
        "resolve_by_hgnc_id",
        lambda hid, *, http: SimpleNamespace(
            hgnc_symbol="TFRC", hgnc_id=hid, uniprot_acc="P02786"
        ),
    )
    monkeypatch.setattr(
        mod, "fetch_isoform_context", lambda acc, *, http: []
    )
    monkeypatch.setattr(mod, "load_prompt", lambda: "SYS")
    monkeypatch.setattr(
        mod, "grade_isoforms_with_model", lambda client, *, model, **kw: _prior(model)
    )

    mod.annotate_model_prior(
        "TFRC", client=object(), http=object(), persist=False, annotations_dir=tmp_path
    )
    assert list(tmp_path.iterdir()) == []
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_internalization_runner.py -q`
Expected: FAIL — `ModuleNotFoundError` for `...internalization.runner`.

- [ ] **Step 3: Implement**

Create `src/accessible_surfaceome/agents/internalization/runner.py`:

```python
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
) -> InternalizationRecord:
    client = client or get_client()
    http = http or open_default_client()

    hgnc_id = resolve_hgnc_id(gene)
    bundle = resolve_by_hgnc_id(hgnc_id, http=http)
    isoforms = fetch_isoform_context(bundle.uniprot_acc, http=http)
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
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_internalization_runner.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Run the full internalization test module + type check**

Run: `uv run pytest tests/test_internalization_*.py -q && uv run ty check src/accessible_surfaceome/agents/internalization`
Expected: all PASS; ty reports no errors. Fix any type issues (e.g. add `-> str` returns) before committing.

- [ ] **Step 6: Commit**

```bash
git add src/accessible_surfaceome/agents/internalization/runner.py tests/test_internalization_runner.py
git commit -m "feat(agents): internalization model-prior runner (Opus + Sonnet, per-isoform)"
```

---

## Task 8: CLI driver + real smoke run

**Files:**
- Create: `scripts/internalization_annotate.py`

- [ ] **Step 1: Write the CLI**

Create `scripts/internalization_annotate.py`:

```python
"""Annotate one gene's internalization model-prior track (Opus + Sonnet).

Usage:
    uv run python scripts/internalization_annotate.py TFRC
    uv run python scripts/internalization_annotate.py HGNC:3236 --no-persist
    uv run python scripts/internalization_annotate.py CD20 --models claude-sonnet-4-6
"""

from __future__ import annotations

import argparse
import logging
import sys

from accessible_surfaceome.agents.internalization.runner import (
    DEFAULT_MODELS,
    annotate_model_prior,
)
from accessible_surfaceome.env import load_env


def main(argv: list[str] | None = None) -> int:
    load_env()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("gene", help="Gene symbol or HGNC:id")
    parser.add_argument(
        "--persist",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Write data/annotations/internalization/{SYMBOL}.json (default: on)",
    )
    parser.add_argument(
        "--models",
        nargs="+",
        default=list(DEFAULT_MODELS),
        help=f"Model ids to grade with (default: {' '.join(DEFAULT_MODELS)})",
    )
    args = parser.parse_args(argv)

    record = annotate_model_prior(
        args.gene, models=tuple(args.models), persist=args.persist
    )

    print(f"\n{record.gene_symbol}  ({record.uniprot_acc}, {record.hgnc_id})")
    for track in record.model_priors:
        print(
            f"  [{track.model}] overall={track.overall_grade} "
            f"({track.overall_confidence})"
        )
        for iso in track.per_isoform:
            flag = "canonical" if iso.is_canonical else "isoform"
            print(
                f"      {iso.isoform_id} ({flag}): {iso.grade} "
                f"({iso.confidence}) — {iso.rationale[:90]}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
```

- [ ] **Step 2: Verify the CLI parses without a model call**

Run: `uv run python scripts/internalization_annotate.py --help`
Expected: argparse help text prints the `gene`, `--persist/--no-persist`, `--models` options; exit 0.

- [ ] **Step 3: Real smoke run (needs `.env` with `ANTHROPIC_API_KEY` + hydrated cohort TSV)**

Ensure data + env are present:

```bash
bash scripts/bootstrap-worktree.sh candidate
ls -l .env  # symlinked per CLAUDE.md
```

Run one control that internalizes and one that does not, verifying the grades diverge sensibly:

```bash
uv run python scripts/internalization_annotate.py TFRC
uv run python scripts/internalization_annotate.py MS4A1
```

Expected: TFRC prints a `high` overall from both models; MS4A1 prints `low`/`no`. Each writes `data/annotations/internalization/{TFRC,MS4A1}.json`. If a model emits invalid JSON twice, the run raises `ValueError` (by design) — re-run; if it recurs, tighten the prompt's output instruction.

Confirm the artifact validates:

```bash
uv run python -c "import json; from accessible_surfaceome.agents.internalization.models import InternalizationRecord; InternalizationRecord.model_validate_json(open('data/annotations/internalization/TFRC.json').read()); print('valid')"
```

Expected: `valid`.

- [ ] **Step 4: Full quality gate**

Run: `bash scripts/check-py.sh`
Expected: ruff + ty + compile + pytest all green (includes the new `tests/test_internalization_*.py` files and the prompt-leak tests).

- [ ] **Step 5: Commit**

```bash
git add scripts/internalization_annotate.py
git commit -m "feat(agents): CLI driver for internalization model-prior pass"
```

Do NOT commit anything under `data/annotations/internalization/` — those are
run artifacts (verify they're gitignored or leave them unstaged).

---

## Definition of done (Plan 1)

- `uv run python scripts/internalization_annotate.py TFRC` produces a validated
  `InternalizationRecord` (schema 0.1.0) with two `model_priors` (Opus + Sonnet),
  per-isoform grades, written to `data/annotations/internalization/TFRC.json`.
- The 6 controls grade sensibly (TFRC/EGFR high, HER2/FOLR1/ENPP3 medium-ish,
  CD20 low) — spot-checked manually; automated controls report is a later plan.
- `bash scripts/check-py.sh` green; prompt-leak tests green.

## Follow-on plans (not this plan)

- **Plan 2 — Literature track (Track 1):** discovery/triage/PDF reuse from
  `plan_trim_select`, observation rows + grades-by-mode, PMID span verification;
  bumps `schema_version` and adds the `literature` field to `InternalizationRecord`.
- **Plan 3 — D1 + Worker:** `internalization_annotation` tables, `publish_record`
  mirror, Worker LEFT JOIN, edge purge.
- **Plan 4 — Viewer:** `InternalizationCard`, `surfaceome-types.ts`, markdown
  export, tooltips (incl. the "model estimate — not citation-backed" badge).
- **Plan 5 — Controls report + `--canonical` cohort sweep + `gen_prompt_review`
  wiring.**
