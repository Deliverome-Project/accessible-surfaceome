# `subcellular_localization` rationale audit

**Date:** 2026-06-08
**Cohort:** TACSTD2, C3, CD63, PVRIG, HMGB1, GPR75, ABCB9, LYN, TGOLN2, SRC, BAX (11 v2 reruns @ `prompt_corpus_version='2.35.0'`)
**Block under audit:** `subcellular_localization` (built by `subloc_anatomical_combined`)
**Comparison blocks:** `evidence_grade.grade_rationale`, `risks_builder.*.rationale`, `anatomical_accessibility.rationale`

---

## Headline

**The schema has no rationale fields at all.** Every other LLM-authored block carries one or more `rationale: str = Field(...)` slots with `_PROSE_TARGETS` validators; `SubcellularLocalization`, `DualLocalization`, and `MembraneSubdomain` do not. The only prose-shaped field is `DualLocalization.condition` — explicitly speced as a "short qualifier" in the prompt — and `MembraneSubdomain` carries no free text whatsoever.

Distribution across the 11 reruns (chars):

| Block | n | min | median | mean | max | Target |
|---|---|---|---|---|---|---|
| `subcellular_localization.dual_localization.condition` (free text) | 25 emitted + 6 null | 0 | 70 | 64 | 109 | none |
| `subcellular_localization.membrane_subdomains.*` (any prose) | 13 | — | — | — | — | **no prose field exists** |
| `evidence_grade.grade_rationale` | 11 | 871 | 1187 | 1241 | 1592 | ≤800 (soft) |
| `risks_builder.*.rationale` (4 chips × 11 genes) | 44 | 75 | 360 | 361 | 703 | ≤300 / ≤400 (soft) |
| `anatomical_accessibility.rationale` | 2 | 221 | 247 | 247 | 274 | ≤300 (soft) |

`evidence_grade` produces **~20× more rationale prose per gene** than the subcellular block. Six dual-loc rows (19% of all rows, including all four CD63 non-PM compartments and both LYN compartments) have `condition=null` — zero explanation of why CD63 was placed in `multivesicular body` or LYN in `cytosol`.

This is a schema + prompt design gap, not a model failure. Output token count (TGOLN2: 277) is the *expected consequence* of asking the LLM to emit a JSON object with no rationale fields, not a `max_tokens` truncation (`MAX_TOKENS_BLOCK=16_000`).

---

## Per-gene examples

**Worst (null):** CD63 has four non-PM compartments (endosome, multivesicular body, secretory granule, extracellular vesicle) all with `condition=null`. LYN's two rows (inner leaflet of PM, cytosol) are also both null. The reader sees "dual-localized to inner leaflet of PM and cytosol" with no indication why — cited evidence ids are there (`a2_evi_04/05/06`) but the block itself is silent.

**Best (~85 chars):** ABCB9's longest row:
```
{compartment: "plasma_membrane",
 condition: "only when TMD0 is absent (core-TAPL truncation) or N-terminal region M1-S275 is deleted"}
```
Even this — the longest condition in the cohort at 87 chars — names no assay, no perm status, no cell type. Compare TGOLN2's `evidence_grade.grade_rationale` at 1058 chars: named methods, cited per-claim, perm status flagged.

---

## Root cause

**Hypothesis 1 holds: the prompt does not ask for rationale at the level other blocks do.** The 80-line prompt is entirely about *taxonomy* (which compartment goes where, what counts as a microdomain, where the cell-intrinsic / tissue-level boundary sits vs. anatomical_accessibility). There is no instruction to name methods that placed the protein in a compartment, carry inline `(a2_evi_NN)` cites, or explain why the primary compartment was chosen over alternatives. `evidence_grade_builder_system.md` spends lines 241–319 (~80 lines — the entire size of the subcellular prompt) on rationale discipline alone.

**Hypothesis 2 also holds: the schema gives the LLM no opportunity.** Code at `models.py:2331-2464`:

```python
class DualLocalization(BaseModel):
    compartment: str               # validator: ≤40 chars, no parentheticals
    fraction_estimate: float | None = None
    condition: str | None = None   # the only free-text slot
    cited_evidence_ids: list[str] = Field(default_factory=list)

class MembraneSubdomain(BaseModel):
    subdomain: MembraneSubdomainName    # closed enum
    cited_evidence_ids: list[str] = Field(default_factory=list)
    # NO rationale field

class SubcellularLocalization(BaseModel):
    primary_compartment: PrimaryCompartment   # closed enum
    dual_localization: list[DualLocalization] = Field(default_factory=list)
    membrane_subdomains: list[MembraneSubdomain] = Field(default_factory=list)
    # NO rationale field on the parent either
```

`risks_builder` siblings all have `rationale: str = Field(..., description="…Soft target ≤NNN chars…")` + `_PROSE_TARGETS` + a `@model_validator` that warns on overshoot. `AnatomicalAccessibilityObservation` — the *other* output of the same combined Sonnet call — carries a 300-char rationale field. The model is being asked to write rationale for half the block it emits and not the other half.

**Hypothesis 3 not supported.** A2 ledger range is 10–34 claims / gene, 4–16 subcellular-relevant. Even BAX (10 total / 6 relevant) yields 871-char `grade_rationale` on the same ledger.

**Hypothesis 4 not supported.** `MAX_TOKENS_BLOCK = 16_000` (`_common.py:46`). TGOLN2's `output=277` is the combined-call total; for a schema with no rationale fields plus an empty anatomical array, 277 is expected, not truncation. No `stop_reason="max_tokens"` in logs.

---

## Recommended edits

### 1. Schema — add `rationale: str` to all three subcellular block types
**File:** `src/accessible_surfaceome/tools/_shared/models.py`

Pattern to mirror exactly from `CoReceptorRequirements` (lines 3124–3147) and `AnatomicalAccessibilityObservation` (lines 2467–2487):

```python
# DualLocalization (around line 2336)
class DualLocalization(BaseModel):
    model_config = ConfigDict(extra="forbid")
    compartment: str
    fraction_estimate: float | None = None
    condition: str | None = None
    rationale: str = Field(                       # NEW
        ...,
        description="Why this compartment (assay + cell type + perm status, "
                    "inline (a2_evi_NN) cite per claim). Soft target ≤300 chars.",
    )
    cited_evidence_ids: list[str] = Field(default_factory=list)
    _PROSE_TARGETS: ClassVar[dict[str, int]] = {"rationale": 300}  # NEW
    @model_validator(mode="after")
    def _warn_soft_target_overshoot(self) -> "DualLocalization":
        _warn_prose_overshoot(self, type(self)._PROSE_TARGETS)
        return self
```

Same pattern on `MembraneSubdomain` (line 2436) with soft target ≤200 (subdomain is shorter scope), and a top-level `primary_compartment_rationale: str` on `SubcellularLocalization` itself (line 2457) with soft target ≤400. **Make the top-level one required (`...`), the per-row ones optional with a non-empty default — the LLM needs to write SOMETHING when it picks a compartment, but per-row prose can stay terse for genes with many rows.**

For backward-compat with existing D1 records, use `str = ""` default rather than `...` — soft-target validators emit warnings, not raises, so old records still load; subsequent reruns fill them in.

### 2. Prompt — add a "Rationale discipline" section
**File:** `subcellular_localization_builder_system.md`

Insert between line 56 (end of `membrane_subdomains` description) and line 57 (the boundary section). Copy the structural pattern from `evidence_grade_builder_system.md:241-319`, condensed:

```markdown
## Rationale discipline

Every block you emit carries a `rationale` field. Treat it the same way
evidence_grade does — name the assay readout, cell type, and (where
relevant) the perm status, and inline-cite the supporting `(a2_evi_NN)`
id immediately after each specific claim.

- `primary_compartment_rationale` — one paragraph (≤400 chars). State
  the dominant pool and the methods that pinned it (IF / fractionation /
  IHC / Atlas annotation / nonperm flow). Inline cite per claim.
- `dual_localization[*].rationale` — one short paragraph per row
  (≤300 chars). Why is this compartment a *non-primary* pool? What
  assay observed it? Cell type / state?
- `membrane_subdomains[*].rationale` — one line per row (≤200 chars).
  Which evidence assigned this microdomain (raft purification, cilium
  IF, polarized epithelium IHC)?

A specific claim is anything that names a method, mechanism, cell type,
or condition. Loose framing ("predominantly intracellular") doesn't
need a per-sentence cite; specific claims do.

A good rationale:
> "Permeabilized IF in HeLa shows TGN co-staining with TGN46
> and golgin-97 markers (a2_evi_06); GFP-fusion vCLEM in HEK293T
> confirms Golgi-stack localization (a2_evi_07)."

A vague rationale that fails the discipline:
> "Predominantly Golgi by literature."
```

### 3. Prompt — explicit length targets, mirroring evidence_grade
**File:** `subcellular_localization_builder_system.md` line 22 (`primary_compartment` description)

Change:
```
- `primary_compartment` — closed enum: `plasma_membrane`, …
```
to:
```
- `primary_compartment` — closed enum: `plasma_membrane`, …
- `primary_compartment_rationale` — prose (soft target ≤400 chars) explaining
  WHY this compartment, citing the specific methods + cell types that pinned it.
  Inline `(a2_evi_NN)` cites required for every method named.
```

### 4. Prompt — promote `condition` to a sub-rationale, not a "qualifier"
**File:** `subcellular_localization_builder_system.md` lines 31–32

Current:
```
- `condition` — free-text qualifier (e.g. `under stress`,
  `in polarized cells`) or null.
```

Replace with:
```
- `condition` — short trigger / context phrase (≤80 chars). The detailed
  WHY (assay, cell type, perm status, source) goes in `rationale`, not here.
```

This unblocks the LLM from cramming explanation into `condition` (which is the only writeable prose slot today) and pushes it into the new `rationale` field where the soft target + validator can govern its quality.

### 5. No code change in `subloc_anatomical_combined.py`

The combined builder stitches both system prompts together (line 106). Once the subcellular prompt has its rationale section, the stitched prompt covers both blocks symmetrically — code unchanged. After the prompt edit, run `scripts/gen_prompt_review.py` and the gene-leak tests (`tests/test_prompts_no_gene_names.py`, `tests/test_prompt_no_specific_proteins.py`) — the worked example in edit #2 names assay reagents (TGN46 / golgin-97) which are markers, not the audited gene, so should pass; check anyway.

---

## Expected impact

After all five edits: rationale per gene should land in the 600–1200 char range, matching `risks_builder`'s 4-chip pattern (~360 chars × 3 rationale slots per gene ≈ 1080 chars). Output token count for the combined builder rises from ~277 to ~600-800. Cost delta is negligible (~$0.005/gene at Sonnet pricing) relative to the ~$0.20/gene baseline; the gain is that a reader looking at the gene page sees `Localization: Golgi (primary). Permeabilized IF in HeLa shows TGN co-staining with TGN46 and golgin-97 (a2_evi_06)…` instead of `Localization: Golgi.`

---

## References

- Prompt: [`src/accessible_surfaceome/agents/surfaceome_v2/prompts/subcellular_localization_builder_system.md`](../../src/accessible_surfaceome/agents/surfaceome_v2/prompts/subcellular_localization_builder_system.md) (80 lines)
- Comparison prompt: [`src/accessible_surfaceome/agents/surfaceome_v2/prompts/evidence_grade_builder_system.md`](../../src/accessible_surfaceome/agents/surfaceome_v2/prompts/evidence_grade_builder_system.md) (395 lines; rationale discipline at lines 241–319)
- Schema: [`src/accessible_surfaceome/tools/_shared/models.py`](../../src/accessible_surfaceome/tools/_shared/models.py) lines 2331–2464 (gap), 3124–3294 (reference pattern in risks_builder), 2467–2487 (reference pattern in anatomical_accessibility)
- Builder: [`src/accessible_surfaceome/agents/surfaceome_v2/builders/subloc_anatomical_combined.py`](../../src/accessible_surfaceome/agents/surfaceome_v2/builders/subloc_anatomical_combined.py)
- Common (token cap): [`src/accessible_surfaceome/agents/surfaceome_v2/builders/_common.py`](../../src/accessible_surfaceome/agents/surfaceome_v2/builders/_common.py) line 46 (`MAX_TOKENS_BLOCK = 16_000` — not the bottleneck)
