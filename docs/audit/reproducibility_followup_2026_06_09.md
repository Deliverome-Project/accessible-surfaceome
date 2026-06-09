# Tier 3 reproducibility — integration follow-up (post-flight wiring)

Date: 2026-06-08. Companion to
[`r2_and_reproducibility_2026_06_08.md`](r2_and_reproducibility_2026_06_08.md).

## TL;DR

Tier 3 lands in two waves:

1. **Wave 1 (committed today)** — new files, no edits to in-flight files:
   [`run_metadata.py`](../../src/accessible_surfaceome/agents/_support/run_metadata.py)
   + [`failure_modes.py`](../../src/accessible_surfaceome/tools/_shared/failure_modes.py)
   + [`test_run_metadata.py`](../../tests/test_run_metadata.py).
2. **Wave 2 (this doc)** — 8 integration sites in files that Agents
   #17 / #18 / #19 are mid-flight on. Each item names the in-flight
   commit that unblocks it.

## Wave 2 integration list

### 1. `code_sha` into the published intermediates dict

**Field**: `code_sha` — git rev at runtime. Bug-fix between two
same-`prompt_corpus_version` runs is invisible without this.

**File**: [`src/accessible_surfaceome/cloud/intermediates.py`](../../src/accessible_surfaceome/cloud/intermediates.py)
line ~240, just before the `if n_bytes > _MAX_INTERMEDIATES_BYTES`
slim-fallback block in `publish_intermediates`.

```python
from accessible_surfaceome.agents._support.run_metadata import code_sha
intermediates = {**intermediates, "code_sha": code_sha()}
blob = json.dumps(intermediates, separators=(",", ":"))
n_bytes = len(blob.encode("utf-8"))
```

Re-serialize `blob` + recompute `n_bytes` because we added a key
before the size check. `{**intermediates, ...}` keeps the caller's
dict immutable — same pattern `_slim_intermediates_for_d1` uses.

**Unblocks**: Agent #19's `publish_intermediates` plumbing has already
landed at HEAD `f80a50be5`. Land this with items 2 + 7 + 8 (same
function).

---

### 2. `model_id` into the published intermediates dict

**Field**: `model_id` — the bare-alias model id (`"claude-sonnet-4-6"`).
The resolved dated alias (`"claude-sonnet-4-6-20251022"`) is captured
per-call by item 3.

**File**: same as item 1; extend the dict-build:

```python
from accessible_surfaceome.agents._support.run_metadata import code_sha
from accessible_surfaceome.agents.surfaceome_v2.orchestrator import AGENT_MODEL
intermediates = {
    **intermediates,
    "code_sha": code_sha(),
    "model_id": AGENT_MODEL,
}
```

**Unblocks**: Agent #19's intermediates wave.

---

### 3. `api_response_id` + `api_model` + `api_stop_reason` per call

**Field**: Anthropic `response.id`, resolved model snapshot
(`response.model`), and `stop_reason`. Captured via Wave 1's
`run_metadata.api_response_metadata(response)`.

**File**: [`src/accessible_surfaceome/agents/_support/api_retry.py`](../../src/accessible_surfaceome/agents/_support/api_retry.py).
Extend `messages_create_with_backoff` with an optional sink kwarg:

```python
def messages_create_with_backoff(
    client: anthropic.Anthropic,
    *,
    api_metadata_sink: list[dict[str, Any]] | None = None,
    **kwargs: Any,
) -> Message:
    # ... existing body ...
    resp = _call()
    if api_metadata_sink is not None:
        from accessible_surfaceome.agents._support.run_metadata import (
            api_response_metadata,
        )
        api_metadata_sink.append(api_response_metadata(resp))
    return resp
```

Each call site that wants the metadata constructs a list, passes it
as `api_metadata_sink=`, and folds the dict into its `UsageRecord`
(at [`pricing.py:75`](../../src/accessible_surfaceome/agents/_support/pricing.py)).

**Unblocks**: Agent #18's tenacity wave. Defer the `UsageRecord`
shape change (3 new fields) to the same commit — adding fields to
that dataclass *now* would collide.

---

### 4. Explicit `temperature` on every `messages.create`

**Field**: `temperature` — currently SDK default 1.0. Wave 1's
`cohort_temperature()` returns 0.2 (overridable via `COHORT_TEMPERATURE`).

**File**: same as item 3. Inside `messages_create_with_backoff`:

```python
def messages_create_with_backoff(client, **kwargs):
    if "temperature" not in kwargs:
        from accessible_surfaceome.agents._support.run_metadata import (
            cohort_temperature,
        )
        kwargs["temperature"] = cohort_temperature()
    # ... existing body ...
```

Low-risk: every call site that already passes `temperature=` keeps
its explicit value; the rest get 0.2.

**Unblocks**: Agent #18 (same file).

---

### 5. Per-builder `n_repair_attempts`

**Field**: `n_repair_attempts` per builder. Already counted in
`call_builder`'s `attempt` loop variable, silently discarded at return.

**File**: [`src/accessible_surfaceome/agents/surfaceome_v2/builders/_common.py`](../../src/accessible_surfaceome/agents/surfaceome_v2/builders/_common.py).
Wrap `call_builder`'s return in a small dataclass:

```python
@dataclass
class _BuilderCallResult:
    parsed: Any  # T | list[BaseModel] | None
    n_repair_attempts: int = 0
    validation_error: str | None = None
```

`return parsed` at lines 246 / 249 becomes
`return _BuilderCallResult(parsed=parsed, n_repair_attempts=attempt)`;
line 278's loop-bottom becomes
`return _BuilderCallResult(parsed=None, n_repair_attempts=MAX_REPAIRS, validation_error=validation_error)`.
Every caller unwraps with `.parsed` and pushes the count into
`builder_usage[name]`.

**Unblocks**: Agent #18 has open edits in `_common.py`. The 9-caller
rewrite needs their tenacity edits to settle first.

---

### 6. Structured `failure_mode` on `AnnotateResultV2`

**Field**: `failure_mode: FailureMode = "ok"` — structured companion
to free-text `error`. Enum:
[`tools/_shared/failure_modes.py`](../../src/accessible_surfaceome/tools/_shared/failure_modes.py).

**File**: [`src/accessible_surfaceome/agents/surfaceome_v2/orchestrator.py`](../../src/accessible_surfaceome/agents/surfaceome_v2/orchestrator.py).
Add the field to `AnnotateResultV2` (line ~780, between `error` and
`timing`):

```python
from accessible_surfaceome.tools._shared.failure_modes import FailureMode

@dataclass
class AnnotateResultV2:
    # ... existing fields ...
    error: str | None = None
    failure_mode: FailureMode = "ok"
    timing: list[StepTiming] = field(default_factory=list)
```

Populate at each error path:

| Line | Existing `error=` | Add `failure_mode=` |
|---|---|---|
| ~877 | `"skipped: fresh record already in public D1"` | `"ok"` |
| ~977 | `"plan-trim-select did not resolve a gene bundle"` | `"pts_failure"` |
| ~1047 | PTS $5 cost-ceiling (Agent #19) | `"cost_ceiling_pts"` |
| ~1306 | `"SurfaceEvidenceDraft validation failed: ..."` | `"validation_failed"` |
| ~1323 | `"BiologicalContextDraft validation failed: ..."` | `"validation_failed"` |
| ~1540 | `"per-gene cost ceiling exceeded"` ($7 cap) | `"cost_ceiling_total"` |
| ~1556 | `"synthesizer returned no valid draft"` | `"synth_draft_missing"` |
| ~2067 | final record assembly failure | `"schema_drift"` |

**Unblocks**: Agent #19's PTS $5 cap commit. Land in their follow-up
so the new abort path is born with its tag.

---

### 7. Triage `run_id` link into intermediates

**Field**: `triage_run_id` — the `triage_run_public.run_id` the synth
consumed as prior. `_load_triage_record(symbol)` (line 1444) returns
a `TriageRecord` whose `provenance.run_id` carries the link.

**File**: orchestrator.py, after line 1503
(`intermediates["triage_summary_json"] = ...`):

```python
prov = triage_record.provenance if triage_record is not None else None
intermediates["triage_run_id"] = prov.run_id if prov is not None else None
intermediates["triage_model"] = prov.model if prov is not None else None
intermediates["triage_prompt_variant"] = (
    prov.prompt_variant if prov is not None else None
)
```

Three independent fields on purpose — "all v2 runs whose triage came
from `mainbench_canonical_v2` ncbi" is the first cohort-analytics query.

**Unblocks**: Agent #19 (synth block at ~1494).

---

### 8. Per-step `timing` mirrored into D1 blob

**Field**: full `timing` list — today written only to
`.runs/surfaceome_v2_{gene}.meta.json`, lost on Modal container
shutdown.

**File**: orchestrator.py, after the `cost_per_pipeline` block
(~line 1517, before the cost-ceiling check at ~1525):

```python
intermediates["timing"] = [t.as_dict() for t in list(timing.entries)]
```

`StepTiming.as_dict()` already exists; `list(...)` is defensive
against a future thread-safe wrapper around `timing.entries`.

Re-mirror on every error-path early return that populates
`intermediates=intermediates`. Grep `intermediates=intermediates` to
verify each branch.

**Unblocks**: Agent #19 (same `_annotate` flow).

---

## Wave 2 landing order

1. **Item 6** (`failure_mode`) — depends only on Wave 1. Wire field +
   import; populate `"ok"` on every success path, `"unknown"` on every
   error path as baseline.
2. **Items 1 + 2 + 7 + 8** — all in the `publish_intermediates` ↔
   orchestrator handoff Agent #19 is editing. Single chore commit.
3. **Items 3 + 4** — both edit `messages_create_with_backoff`. Wait
   for Agent #18's wave to settle.
4. **Item 5** — highest friction (9 caller updates). Save for last.

After all 8 land, confirm each new field is present + populated on a
heavy-gene replay.

## Files referenced

* `src/accessible_surfaceome/agents/_support/run_metadata.py` — Wave 1.
* `src/accessible_surfaceome/tools/_shared/failure_modes.py` — Wave 1.
* `tests/test_run_metadata.py` — Wave 1 tests.
* `src/accessible_surfaceome/cloud/intermediates.py` — items 1, 2.
* `src/accessible_surfaceome/agents/_support/api_retry.py` — 3, 4.
* `src/accessible_surfaceome/agents/surfaceome_v2/builders/_common.py` — 5.
* `src/accessible_surfaceome/agents/surfaceome_v2/orchestrator.py` — 6, 7, 8.
* `docs/audit/r2_and_reproducibility_2026_06_08.md` — parent audit.
