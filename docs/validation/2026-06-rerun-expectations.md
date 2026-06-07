# Re-run validation expectations — 2026-06

A checklist to run against re-annotated records after the prompt-corpus
2.4.0 → 2.7.0 / SurfaceomeRecord 2.6.0 → 2.9.0 cycle ships. For each
gene, the expected outcomes are paired with the **prompt change or
schema rule** that should drive them — so when a check fails, you can
trace it straight to the prompt section / validator that owns it.

Re-annotation cost is ~$2-3/gene on Sonnet 4.6. Validate the per-gene
list first, then the cross-gene structural checks, before running a
larger sweep.

## How to use this file

After each gene's re-run lands in D1, pull the fresh record and tick the
boxes:

```bash
curl -sS "https://api.deliverome.org/surfaceome/v1/genes/<SYMBOL>" \
  -o /tmp/<symbol>.json
```

Then read against the expectations below. Failures fall into three
buckets:

* **Validator caught it** — schema rejected the record; re-run will
  retry. Inspect the orchestrator log for the validator name.
* **Prompt slip** — record validates but doesn't meet expectation
  (e.g. the synth picked `state_dependence='moderate'` when `'high'`
  was clearly warranted). Tighten the prompt rule that owns the call.
* **Pipeline gap** — the rule doesn't exist anywhere yet (e.g. the
  ortholog builder still can't find cyno TACSTD2). File as a follow-up.

---

## Per-gene expectations (user-supplied)

### TROP2 / TACSTD2

| Expectation | Owns it |
|---|---|
| `filters.has_known_ligand=False` OR (`=True` AND `has_known_ligand_rationale` non-empty + names the ligand) | `Filters._require_has_known_ligand_rationale_when_true` validator (98cc312cb). Empty rationale now fails. |
| `executive_summary.state_dependence='high'` (or at minimum `'moderate'`) — 10 increases-direction modulation rows + `induction_trigger='oncogenic'` + tumor-induced upregulation across CRC/PTC/EOC/gallbladder | `SurfaceomeRecord._check_state_dependence_consistent_with_modulation` (98cc312cb). `'low'` is now refused; current TROP2 record is graded `'low'` and would re-run. |
| `executive_summary.surface_accessibility` adjusted to reflect the actual call (the user noted "accessibility is a bit off"). Re-read the prompt's surface_accessibility section after the inner-leaflet-rejection prompt landed (376588a5b) and confirm the call is appropriate. | Synthesizer prompt `surface_accessibility` section |
| At least one `accessibility_modulation` row carries `direction='increases'` for the canonical TROP2-ADC indications (lung adeno, breast adeno, colon) — NOT only the niche cases (urothelium, COPD basal cells, salivary ACC) | Anatomical accessibility builder coverage; no specific validator |

### HMGB1

HMGB1 IS surface-accessible biologically — there's a real extracellular
pool that engages PRRs after acetylation-driven lysosomal exocytosis or
necrotic release. What the new prompt corpus should fix is the
**evidence calibration**: the methods in the ledger are receptor-
binding inferences, not direct surface staining of HMGB1 itself, so
the grade should land at `supportive_but_indirect` rather than the
old `direct_multi_method`.

| Expectation | Owns it |
|---|---|
| `executive_summary.surface_accessibility` is in the YES bucket (`high` or `moderate`) — the biology is real, just state-conditional | Synthesizer; the surface_accessibility section's "best-case state" rule (lines 167-179) |
| `executive_summary.state_dependence='high'` — acetylation / necrotic-release gating is the entire mechanism | `_check_state_dependence_consistent_with_modulation` validator |
| `surface_evidence.evidence_grade='supportive_but_indirect'` — NOT `direct_multi_method` (the receptor-engagement methods don't clear the direct bar) AND NOT `weak` (the biology IS established by independent methods). The first re-run landed `weak`, which over-fits on the ligand filter — the next re-run under the 2.9.0 prompts should re-calibrate up to `supportive_but_indirect`. | Methods builder inclusion filter + evidence-grade builder grade rules |
| `surface_evidence.excluded_as_ligand_engagement` is **non-empty** — at minimum the BS3-crosslinking-HMGB1-TREM-1 claim should appear with a reason like "HMGB1 binding TREM-1 on monocytes — soluble ligand engagement, not surface anchoring of HMGB1." | Evidence-grade builder prompt (5587da60b) `excluded_as_ligand_engagement` section |
| Inner-leaflet rejection (376588a5b) likewise excludes any "HMGB1 at inner leaflet of PM" interpretations — HMGB1 isn't inner-leaflet anyway, so this should be a no-op | Methods builder inner-leaflet rejection |

### SRC

| Expectation | Owns it |
|---|---|
| `surface_evidence.evidence_grade='direct_single_method'`. Current SRC record (1.1.0) has it as `supportive_but_indirect`. The expected upgrade comes from the methods builder more carefully classifying live-cell flow / nonperm-IF rows. | Methods builder + evidence-grade methods-summary cross-check (a1cbb7c85). |
| **Caution:** SRC is canonically inner-leaflet-anchored (myristoylated N-terminus, cytoplasmic-face kinase). The inner-leaflet rejection prompt (376588a5b) should NOT block the cancer-state outer-leaflet inversion evidence — `state_dependence={moderate, high}` with the outer-leaflet methods graded directly. If `evidence_grade` re-runs to `weak` because the inner-leaflet rejection nuked the outer-leaflet evidence, the prompt rule is over-fitting and needs a state-conditional carve-out. | Methods builder inner-leaflet section + state-dependence validator. |

### GPR75

| Expectation | Owns it |
|---|---|
| `surface_evidence.evidence_grade='supportive_but_indirect'` (canonical class A GPCR with strong topology prior + indirect-only methods). Already the current call — should hold. | Evidence-grade rules (unchanged for the GPCR case). |
| `surface_evidence.grade_rationale` carries inline `(aN_evi_NN)` cite on each numbered/named claim — no more "(3) VPS35-mediated retromer recycling to the hepatocyte PM" with no chip. | `SurfaceEvidence._fail_grade_rationale_structured_claims_uncited` (5587da60b). Current record fails this rule and would re-run. |
| `filters.low_endogenous_expression=True` — `expression_level='moderate'` + `expression_breadth='restricted'` (CNS-concentrated). The extended derivation (40592f46b) catches this case. | `_derive_filters` `low_endogenous_expression` rule. |
| `filters.low_endogenous_expression_rationale` is the synth's `expression_level_rationale` verbatim — **no "Derived from expression_level=..." preamble**. | `_derive_filters` composition (40592f46b). |

### TGOLN2

| Expectation | Owns it |
|---|---|
| `executive_summary.surface_accessibility` ∈ `{low, moderate}` (at minimum) — not `no` or `uncertain`. The previous round graded it `weak` and the methods builder didn't surface any direct evidence; under the new prompts the inner-leaflet rejection should NOT block legitimate trans-Golgi-network → PM trafficking rows. | Methods builder inner-leaflet + state-dependence interaction. The user flagged this as a case to check carefully. |
| **No isoform duplication** in the viewer's IsoformsCard table OR the 3D StructureViewer tab strip. The canonical accession should NOT appear as both `Canonical` and `Isoform`. | Viewer-side fixes (`8e01ef14c` IsoformsCard, `0fced4164` StructureViewer). Upstream annotator-side fix (don't emit canonical into `isoform_topologies`) is a separate follow-up. |
| **`deterministic_features.isoform_topologies[i].full_length_pct_identity_to_canonical` is NO LONGER 100% for truncated isoforms.** The current TGOLN2 record has `O43493-4` (309/367 residues) reading `100.0`; under the new `max(len_a, len_b)` denominator (commit `aed9cdc40`) it should read ~84% (309/367). | Shared `merge/_sequence_identity.pct_identity` helper — applies to ALL isoform / paralog / ortholog identity numbers on every re-run record. |

---

## Cross-gene structural checks (apply to every re-annotated record)

These are general invariants the new prompts + validators should enforce
on every record. Sample a handful from the re-run set; if any record
ships violating one, the rule is broken.

### Schema-side (a violation would fail validation outright)

| Check | Validator |
|---|---|
| `surface_evidence.grade_rationale` either carries ≥1 `(aN_evi_NN)` inline cite OR the prose has no structured-claim markers (numbered items, named experimental methods) | `_warn_grade_rationale_missing_cite` (warn) + `_fail_grade_rationale_structured_claims_uncited` (raise) |
| If `filters.has_known_ligand=True`, `filters.has_known_ligand_rationale` is non-empty | `Filters._require_has_known_ligand_rationale_when_true` |
| `executive_summary.state_dependence` is NOT `'low'` when (`induction_trigger != 'none'`) OR (≥3 `accessibility_modulation` rows with `direction='increases'`) OR (any oncogenic-transformation row with `direction='increases'` AND `surface_accessibility != 'no'`) | `SurfaceomeRecord._check_state_dependence_consistent_with_modulation` |
| Every `claim_stances[i].claim_id` resolves to an `EvidenceClaim` in the ledger | pre-existing draft validator |

### Prompt-side (the synth should produce these, but the schema doesn't enforce them)

| Check | Owns it |
|---|---|
| `surface_evidence.methods` does NOT contain any row whose subject role is "soluble ligand binding surface receptor on another cell." Sanity-spot-check: any rows that cite RAGE / TLR / TREM / CCR / CXCR / DC-SIGN / CD14 / patient-IgG binding should NOT appear. | Methods builder inclusion criterion (5587da60b + role-in-assay refinement 98cc312cb) |
| `surface_evidence.excluded_as_ligand_engagement` is non-empty for genes where the ledger had receptor-engagement evidence (HMGB1, S100 family, cytokines, secreted DAMPs, free chemokines) | Evidence-grade builder `excluded_as_ligand_engagement` section |
| When `tm_helix_count == 0` (from `deterministic_features.canonical_topology`) AND `surface_evidence.evidence_grade ∈ {direct_*}`, at least one `MethodObservation` row's prose names an outer-leaflet anchoring mechanism | Non-canonical anchoring gate in methods builder prompt |
| `grade_rationale` prose is **concise** (≤800 chars soft target) AND does NOT include pipeline-internal references (`A1`, `A2`, `a1_evi_NN`, `verdict='`, `the synthesizer`, `triage prior`, etc.) | Existing audience-rewrite rules in the synthesizer prompt |

### Filter-derivation checks (the orchestrator computes these from blocks)

| Check | Owns it |
|---|---|
| `filters.low_endogenous_expression_rationale` is the synth's `expression_level_rationale` verbatim — no "Derived from" preamble, no enum names, no boolean status text | `_derive_filters` (40592f46b) |
| `filters.tumor_associated` is True iff at least one `biological_context.expression` row has `disease_context ∈ {tumor, tumor_adjacent}` at a non-absent level | `_derive_filters` (unchanged) |
| `filters.induction_trigger != 'none'` iff at least one `accessibility_modulation` row carries a `cell_state_trigger` mapping into a non-empty bucket | `_derive_filters` (unchanged) |
| `filters.has_live_cell_surface_evidence` is True iff at least one `MethodObservation` is `live-cell flow / nonperm IF / surface biotin / proximity labeling` with endogenous/mixed expression system | `_derive_filters` (unchanged) |

### Sequence-identity refresh (every re-run record)

The denominator switch in commit `aed9cdc40` (`min(len_a, len_b)` →
`max(len_a, len_b)`) affects every isoform / paralog / ortholog
identity number on every re-annotated record. Worth a quick scan of
each re-run record:

| Check | Owns it |
|---|---|
| Truncated isoforms (canonical length > isoform length) no longer read 100% — they should read coverage (`isoform_len / canonical_len * 100`) | `merge/_sequence_identity.pct_identity` (commit `aed9cdc40`) |
| Paralog `ecd_pct_identity` numbers refreshed; loop weights still use `min(loop_len)` for the aggregator but per-loop identity uses `max(loop_len)` | `merge/paralog_ecd_identity` |
| `filters.cyno_ortholog_ecd` / `mouse_ortholog_ecd` / `max_paralog_ecd` bands are re-banded off the refreshed identity — a paralog that used to be `high` band could drop a band when its identity reads lower under the new denominator | `_derive_filters` ECD-band mapping (unchanged), reading the refreshed inputs |

---

## Viewer / render checks (no re-run required; spot-check after deploy)

These don't depend on re-annotation — they're frontend fixes already
shipped. Worth confirming once the freshness dots show green on the
re-run cohort and the viewer rebuilds.

| Check | Fix |
|---|---|
| `accessibility_modulation` table rows show ↑/↓ glyphs (green/red), not `?`, for `direction='increases'/'decreases'` rows | `c7d4fdf1f` |
| `restricted_subdomain.rationale`, `anatomical_accessibility[i].rationale`, `co_receptor_requirements.rationale`, `epitope_masking.rationale`, `ecd_size_assessment.rationale` render inline `(aN_evi_NN)` chips | `c7d4fdf1f` |
| Expression table rows lead with `disease_context='normal'`, then `tumor_adjacent`, then `tumor`, then `other_disease`, then `mixed`, then `unknown` | `dcada4f77` |
| IsoformsCard "Sequence variants" table does NOT show a duplicate row for the canonical accession as `Isoform` | `8e01ef14c` |
| 3D StructureViewer tab strip does NOT have a phantom `Isoform 1` tab pointing at the canonical AFDB model | `0fced4164` |
| GeneJump dropdown freshness dots reflect each gene's D1 `schema_version` vs `CURRENT_RECORD_SCHEMA_VERSION` (currently `"2.9.0"` after this batch — bump the viewer constant in lock-step) | `70674aea2` + the constant bump that should land alongside the re-run |

**Action item before re-run:** update `CURRENT_RECORD_SCHEMA_VERSION` in
`viewer/lib/surfaceome.ts` from `"2.6.0"` to `"2.9.0"` so the freshness
dots correctly mark un-re-run records (still on 2.6.0 / 1.1.0) as stale
once any 2.9.0 record lands.

---

## Known gaps the re-run will NOT fix (file as PR2 / follow-ups)

These are problems we surfaced but didn't address in the current prompt-
corpus version. The re-run will NOT close them.

| Gap | Why deferred |
|---|---|
| Cyno ortholog gap for TACSTD2 (`orthologs.cynomolgus=[]`) | Annotator-side fix — needs NCBI `gene_orthologs.tsv` fallback when Compara returns empty. Different surface from the prompt corpus. |
| Anatomical accessibility row recall for major ADC targets — TROP2 missed the prototype "normal epithelium apical → tumor depolarized" rows for breast / colon / lung adeno | Prompt-side fix needed in `anatomical_accessibility_builder_system.md`; not yet drafted. |
| Annotator emits canonical accession into `isoform_topologies` for some genes (TACSTD2, TGOLN2 likely) | Annotator-side fix; viewer-side filter is in place but the upstream cleanup is cleaner. |
| Existing records on schema 1.1.0 / 2.0.0 still ship the bad calls (TROP2 + many others) until they're re-annotated | Cost: 14 genes × ~$2-3 = $30-50. Re-run is the path. |
| Python post-validator that flags existing D1 records matching the bad patterns (HMGB1-shape direct grade on non-TM, GPR75-shape uncited claims) — for an audit pass over the cohort without re-running every record | PR2 scope; deferred from PR1. |

---

## Suggested re-run order

1. **TROP2** and **HMGB1** first — they're the most-changed expectations
   and any prompt slip surfaces most loudly here. Cost: ~$5-6 total.
2. **GPR75** + **SRC** — second tier; less risky cases that validate the
   citation-discipline + direct-method-grade rules respectively.
   ~$5-6.
3. **TGOLN2** + the remaining 1.1.0 / 2.0.0 records — once the first
   two tiers look right, sweep the rest. ~$25-35.

If TROP2 or HMGB1 re-runs surface anything in the "validator caught it"
or "prompt slip" buckets above, **stop the sweep** and tighten the
rule before paying $25 on the tail.
