# JensenLab COMPARTMENTS (and HPA) integration — channel methods, pool filters, and the rule we chose

**Date:** 2026-04-17 · **Status:** Implemented.
**Files touched:** [`build_jensenlab_compartments.py`](../../src/surface_proteome/candidates/build_jensenlab_compartments.py), [`build_hpa.py`](../../src/surface_proteome/candidates/build_hpa.py), [`build_candidate_universe.py`](../../src/surface_proteome/candidates/merge.py), [`download_jensenlab_compartments.py`](../../src/surface_proteome/candidates/download_jensenlab_compartments.py).

## Why this write-up exists

We added JensenLab COMPARTMENTS as one of two new sources in the M1 candidate-universe merge (alongside HPA). Unlike the other sources, COMPARTMENTS is itself a **meta-database** that integrates four independent evidence streams — knowledge, experiments, text-mining, and predictions — across GO cellular-component terms. Treating "COMPARTMENTS" as a single vote in the merge collapses that structure into one bit, and depending on which channels you include the vote can mean very different things. This doc records what each channel actually contains, what we found when we wired it in naively, and the final rule we chose.

Reference: Binder et al., *Database* (Oxford), 2014, [DOI: 10.1093/database/bau012](https://doi.org/10.1093/database/bau012). License: CC-BY-4.0.

## The four COMPARTMENTS channels — what each one actually is

All four channels emit per-ENSP rows keyed on GO cellular-component terms, with a star-rated confidence score on the same 0–5 scale. They differ in how that confidence is computed.

### 1. Knowledge channel

**Source.** Manually curated database annotations from UniProtKB, MGI, SGD, FlyBase, and WormBase.

**Stars are assigned by GO evidence code:**

| Stars | GO evidence codes |
|---|---|
| 4 (then +1 → **5** for UniProt / model-org DBs) | CURATED, IDA, TAS, NAS |
| 3 | PROBABLE, EXP, IPI, IMP, IGI, IEP, ISS, ISO, ISA, ISM, IBA, IBD, IKR, IMR, IRD, IC |
| 2 | POTENTIAL, IGC, IEA |
| 1 | BY SIMILARITY, RCA, NR |

**What it overlaps with in our merge.** The knowledge channel *is* GO + UniProt-SubCell, re-packaged with a star rating. Our merge already ingests GO GAF and the UniProt surface-candidate query as first-class sources. Using knowledge as a third vote would **triple-count exactly the same evidence**.

### 2. Experiments channel (human-only)

**Source.** Human Protein Atlas (HPA) immunofluorescence, and a small number of other high-throughput datasets not available for non-human organisms.

**Star mapping for HPA reliability tiers** (reliability → stars): high → 4, medium → 3, low → 2, very low → 1. Single-antibody IF validations map supportive → 3, uncertain → 1, non-supportive → excluded.

**What it overlaps with.** The experiments rows are almost entirely HPA IF (visible inline in the raw TSV as `source == "HPA"`). We already ingest HPA's `subcellular_location.tsv` as a first-class source. Same double-counting trap as knowledge — just at the HPA layer.

### 3. Text-mining channel

**Source.** Automated named-entity recognition over all of Medline + PMC full-text (the same JensenLab tagger pipeline used by STRING, TISSUES, and DISEASES).

**Method.**

- **Dictionaries.** Protein dictionary = STRING 9.1's. Location dictionary = names of GO cellular-component terms.
- **Entity recognition.** Dictionary-based NER, matched case-sensitively against Medline abstracts and PMC full-text.
- **Co-occurrence scoring.** For each (protein, localization) pair, count co-mentions weighted by proximity:
  - same-sentence co-mention contributes weight `w_s`
  - different-sentence-same-abstract co-mention contributes `w_a = 0.6`
- **Background normalization.** Raw scores are z-scored to correct for overall corpus growth and per-entity frequency. The observed score distribution is modeled as a mixture of random (low-score) and biologically meaningful (high-score) pairs; the random background's mean is taken as the 40th-percentile mode and its variance from the 20th–40th-percentile gap.
- **Star assignment.** `stars = z-score / 2`, capped at 4.

**What it is, orthogonally.** The only COMPARTMENTS channel that brings genuinely new evidence not already ingested elsewhere in our merge — literature signal that isn't GO-curated, HPA-stained, or sequence-predicted. This is the load-bearing value-add.

### 4. Predictions channel

**Source.** Two sequence-based subcellular-localization predictors, applied to whole proteomes:

- **WoLF PSORT.** k-nearest-neighbor classifier over a feature set combining sorting signals, amino-acid composition, and biological rules. Stars derived from k-NN vote count, **max 3 stars**.
- **YLoc-HighRes.** Probabilistic SVM-based classifier over curated sequence features. Stars derived from posterior probability, **max 3 stars**.

**What it overlaps with.** Sequence-based localization prediction is exactly what **SURFY** (ML surfaceome classifier) and **DeepTMHMM** (TM topology predictor) do — both first-class sources in our merge. Adding predictions-channel as a COMPARTMENTS vote gives the sequence-predictor family a third vote on top of those two.

### Integrated channel (carried as provenance only)

The `compartments_integrated_stars_max` column we emit is the per-GO-term integrated score that COMPARTMENTS publishes. It's the max across the four channels above, computed per GO-term per entity; the paper describes it as "when multiple lines of evidence point to the same localization, always select the strongest." Useful as a quick "what does JensenLab think overall?" provenance indicator, but not a fifth independent channel — **by construction it's a function of the other four**.

## What we found when we included all three non-knowledge channels

Initial `compartments_surface_flag` rule: `max(experiments [source != HPA], textmining, predictions) >= 3` over the surface GO terms {GO:0005886 plasma membrane, GO:0009986 cell surface, GO:0031225 anchored component, GO:0005887 integral component of PM}.

Result: **1,217 proteins flagged.** Channel decomposition of those 1,217:

| Channel | Hits @ stars ≥ 3 | Notes |
|---|---:|---|
| experiments (`source != HPA`) | **0** | Every experiments row for surface terms came from HPA, which we drop upstream |
| textmining | 340 | Spread across GO:0005886 (304), GO:0009986 (183), GO:0005887 (89); some overlap |
| predictions | **889 (73% of flag)** | **100% PSORT**, **100% against GO:0005886 only** |

In other words, 73% of the flag was a PSORT-on-plasma-membrane re-vote — evidence the SURFY and DeepTMHMM sequence predictors already provide.

**Cross-source overlap diagnostic** (of the 1,217):

- 945 also flagged by UniProt
- 816 also flagged by SURFY
- 567 also flagged by DeepTMHMM
- Only **154** were COMPARTMENTS-only (all seven sources turned off except this one)

Of those 154 COMPARTMENTS-only hits, most were textmining rows, not predictions — which is a second way of saying the predictions channel wasn't contributing unique signal, just inflating overlap with SURFY/DeepTMHMM.

## The rule we chose

```
compartments_surface_flag = 1 iff
  max(compartments_experiments_stars_max [HPA rows dropped upstream],
      compartments_textmining_stars_max) >= 3
  AND compartments_split_mapping_ambiguous == 0
```

Three of the four channels are carried as provenance columns but do **not** set the flag:

1. `compartments_knowledge_stars_max` — knowledge re-ingests GO + UniProt-SubCell; already first-class in the merge.
2. `compartments_predictions_stars_max` — PSORT + YLoc are sequence-based ML predictors; SURFY + DeepTMHMM already cover that family.
3. Experiments rows with `source == "HPA"` are dropped in [`build_jensenlab_compartments.py`](../../src/surface_proteome/candidates/build_jensenlab_compartments.py) before the per-ENSP aggregation; HPA IF is already first-class.

**Effect.** `compartments_surface_flag` becomes **textmining-driven** — the one channel that brings genuinely orthogonal evidence.

| Metric | Before (all three channels) | After (textmining + HPA-stripped experiments only) |
|---|---:|---:|
| `compartments_surface_flag == 1` | 1,217 | **340** |
| 7/7-source agreement | 67 | 50 |
| All 6 DB-source agreement | 71 | 54 |

We chose a flag threshold of **stars ≥ 3**, which is JensenLab's own "moderate confidence" default on their web UI. It corresponds to `z-score = 6` on the text-mining scale (since `stars = z/2` capped at 4), i.e. a pair of (protein, localization) that co-occurs in the literature substantially above background.

## Spot-check: what this means for known candidates

| Accession | Gene | experiments | textmining | predictions | flag | n_sources |
|---|---|---:|---:|---:|---:|---:|
| P00533 | EGFR | 0.0 | 3.672 | 2.0 | 1 | 7/7 |
| P04439 | HLA-A | 0.0 | 3.327 | 1.0 | 1 | 6/7 |
| P11836 | MS4A1 (CD20) | 0.0 | 2.298 | 2.0 | **0** | 6/7 |
| P15391 | CD19 | 0.0 | 3.747 | 2.0 | 1 | 6/7 |
| P01889 | HLA-B | 0.0 | 3.088 | 2.0 | 1 | 5/7 |
| P10321 | HLA-C | 0.0 | 3.023 | 2.0 | 1 | 5/7 |
| P01871 | IGHM | — | — | — | 0 (no COMPARTMENTS row) | 4/7 |
| P01909 | HLA-DQA1 | 0.0 | 2.411 | 1.0 | **0** | 4/7 |
| P01911 | HLA-DRB1 | 0.0 | 2.650 | 1.0 | **0** | 4/7 |

CD20 (MS4A1), HLA-DQA1, and HLA-DRB1 lose their COMPARTMENTS flag under the new rule because their textmining stars are below 3. CD20 is already supported by six other sources (UniProt, GO, SURFY, CSPA, DeepTMHMM, HPA) — so the overall candidate-universe picture is unchanged where it matters.

## How this reads in the pipeline

- [`build_jensenlab_compartments.py`](../../src/surface_proteome/candidates/build_jensenlab_compartments.py) emits the per-UniProt-primary snapshot, computes the flag at stars ≥ 3 over `max(experiments, textmining)`, carries `compartments_predictions_stars_max` and `compartments_knowledge_stars_max` as provenance, and documents the exclusion under `excluded_evidence` in [`jensenlab_compartments_build_traceability.json`](../../data/processed/jensenlab_compartments/jensenlab_compartments_build_traceability.json).
- [`build_candidate_universe.py`](../../src/surface_proteome/candidates/merge.py) re-derives `compartments_surface_flag` from the raw evidence columns in its pre-publish drift assertion, so a future loader change cannot silently desync from the `flag_rules` block in the manifest.
- [`download_jensenlab_compartments.py`](../../src/surface_proteome/candidates/download_jensenlab_compartments.py) filters the 850 MB textmining TSV at download time to rows whose `go_id` is in the configured surface-term set (reduces to ~5 MB).

## Correctness iteration — pool filter + corroboration gate

Two successive corrections were applied to converge on the committed design. Both were motivated by adversarial review (Codex) and validated numerically against the raw files.

### Iteration 1 — pool filter (fixes the "universe too big" bug)

The first implementation brought the full upstream coverage of HPA + COMPARTMENTS into the merge without filtering to a "surface-candidate pool", unlike the other five sources. That inflated the universe from the M0 plan's intended ~8–10k to **18,548 rows**:

- HPA's `subcellular_location.tsv` covers ~13.6k genes with *any* subcellular annotation. Only the surface-adjacent rows belong in the M1 candidate universe; pure-nuclear / pure-cytosolic / pure-mitochondrial annotations do not.
- COMPARTMENTS restricts to surface-GO-term rows at the build step but had no floor on stars, so ENSPs supported only by a single casual abstract co-mention (noise-tier `stars = 1` textmining) entered the merge.

**Fix.**

1. **HPA pool** — keep rows where PM or Cell Junctions evidence exists at any tier, OR a secretion prediction is present. Secreted-only rows stay for provenance but do not flag. Full per-tier gating semantics documented in [`2026-04-17-hpa-therapeutic-delivery-refinement.md`](2026-04-17-hpa-therapeutic-delivery-refinement.md).
2. **COMPARTMENTS pool** — keep ENSPs where `max(compartments_experiments_stars_max, compartments_textmining_stars_max) >= POOL_STARS_THRESHOLD` (default **2**, JensenLab's "low-but-meaningful" floor; stars=1 is a single casual co-mention, below background). Knowledge and predictions channels (both provenance-only) don't gate pool membership. Flag threshold of **stars ≥ 3** still applies within the pool.

### Iteration 2 — corroboration gate (fixes the "textmining-only false positives" bug)

After iteration 1, 94 proteins still had `sources_present = "compartments"` — a COMPARTMENTS flag with no support from any other source. Inspection revealed 66 of the 94 were flagged purely on text-mining noise:

- **Nuclear transcription factors**: TP53, MYC, FOS, JUN, NFE2L2
- **Secreted cytokines / chemokines / growth factors / hormones**: IFNG, IFNB1, IL1B, IL3, IL4, IL5, IL1A, NGF, FGF4, FGF8, INS, GCG
- **Secreted serum / acute-phase proteins**: ALB, AGT, REN, CCK, APOE, CRP
- **Apoptosis regulators / ER enzymes / mitochondrial proteins**: BCL2, HMGCR, SOD2
- **Secreted matrix / signaling effectors**: MPO, EDN1, MMP2, CSF2

The JensenLab tagger's dictionary-based NER over Medline correctly detects literature co-occurrences between these proteins and "plasma membrane" — but co-occurrence doesn't imply extracellular accessibility on intact cells. TP53 has known PM-localized fractions in signaling abstracts; ALB is abundantly discussed in membrane-dynamics contexts; cytokines are discussed as secreted *toward* PM receptors. None are therapeutic-delivery targets.

**Fix.** `compartments_surface_flag` gated on another source's own *surface flag* (not pool membership, not broader evidence columns):

```
compartments_surface_flag = 1 iff
  max(experiments, textmining) >= 3
  AND compartments_split_mapping_ambiguous == 0
  AND compartments_corroborated == 1

compartments_corroborated = 1 iff any of:
  uniprot_surface_flag == 1
  go_surface_flag == 1       (requires non-IEA evidence — see go_low_confidence_only)
  surfy_surface_flag == 1
  cspa_surface_flag == 1     (high-confidence OR putative; non-specific detections excluded)
  deeptmhmm_surface_flag == 1 (TM/SP+TM/BETA; GLOB/SP-only excluded)
  hpa_surface_flag == 1      (PM/junctional at Enhanced/Supported/Approved; secreted-only excluded)
```

Each source's own `surface_flag` rule already encodes that source's "this protein is membrane-accessible" predicate. Requiring another source to have passed its own bar is the tightest, most principled corroboration signal for a therapeutic-delivery candidate universe. Looser predicates were tried and rejected:

- **Raw pool membership** (initial fix): admits HPA secreted-only rows (ALB, IL1A, APOE, CRP, CSF2 etc. got corroborated via HPA presence) and CSPA non-specific detections.
- **`go_n_go_ids > 0`**: admits pure-IEA GO annotations, which `go_surface_flag` itself rejects. Caught 6 lone-COMPARTMENTS FPs (FGF8, IL13, IL17A, NFE2L2, CXCL10, CALM3) in a final Codex pass.
- **HPA at any tier including Uncertain**: admits weak single-antibody IF that wouldn't set `hpa_surface_flag` on its own.

**Consequence for COMPARTMENTS's role in the merge**: COMPARTMENTS becomes a **confidence booster** that confirms surface calls already made by another source — it cannot add a protein to the universe on its own. Given the tagger's false-positive profile (heavy co-occurrence calls on cytokines, transcription factors, secreted proteins), this is the correct posture for a therapeutic-delivery pipeline. The knowledge and predictions channels, also provenance-only, reinforce the pattern.

**Effect on the committed universe**:

| Metric | Iter 1 only | Iter 1 + 2 (naive corroboration) | Iter 1 + 2 + tightened (committed) |
|---|---:|---:|---:|
| Rows in `candidate_universe.tsv` | 8,680 | 8,770 | **8,770** |
| `0_of_7` bucket | 1,486 | 2,117 | 2,125 |
| `compartments_surface_flag == 1` | 340 | 254 | **246** |
| Lone-COMPARTMENTS flags (`sources_present = "compartments"`) | 94 | 8 | **0** |
| `n_with_all_7_sources` | 50 | 50 | 50 |
| `n_with_all_6_db_sources` | 54 | 54 | 54 |

With the tightened gate, **every `compartments_surface_flag == 1` row has at least one other source's surface flag equal to 1**. All 33 known-textmining-FP proteins in the test panel (TP53, MYC, ALB, INS, IFNG, IL1B, IL3-5, IL13, IL17A, NFE2L2, FGF8, FGF4, CXCL10, CALM3, NGF, BCL2, APOE, CRP, CSF2, MPO, EDN1, MMP2, AGT, REN, CCK, HMGCR, FOS, JUN, SOD2, IFNB1, GCG, IL1A) are correctly unflagged.

**Invariants verified** (all 0 violations):
- `compartments_surface_flag == 1` always has `compartments_corroborated == 1`
- `compartments_surface_flag == 1` always has at least one other `<source>_surface_flag == 1`
- `compartments_surface_flag == 1` always has `max(experiments, textmining) >= 3`
- `compartments_surface_flag == 1` always has `compartments_split_mapping_ambiguous == 0`
- Pre-publish drift assertion re-derives all 4 gated flags (go, cspa, hpa, compartments) and raises on any mismatch with the emitted column

## Follow-ups worth considering

- **Sensitivity sweep.** Re-run with threshold ≥ 2 and ≥ 4 as a downstream analysis; emit a small TSV of how each choice shifts the agreement distribution. Doesn't change the canonical flag.
- **Narrow surface-term set.** JensenLab's own web UI exposes a single "Plasma membrane" top-level bucket (GO:0005886). Restricting our working set to just GO:0005886 would match their canonical aggregation; we keep the four-term set for now because legitimate cell-surface textmining hits (GO:0009986) are lost otherwise — CD markers in particular tend to annotate there.
- **Co-textmining with TISSUES / DISEASES.** The same JensenLab tagger pipeline powers the TISSUES and DISEASES databases. Cross-referencing COMPARTMENTS textmining against TISSUES tissue-distribution textmining would let us flag "reported surface in literature but only in cancer contexts" edge cases without running the full Claude agent pipeline.
- **Re-adopt predictions once DeepTMHMM is extended.** Plan M1's DeepTMHMM run is restricted to 2,360 accessions. Once that's extended to the full reviewed proteome, the PSORT-predictions redundancy argument weakens somewhat — PSORT still overlaps with SURFY, but the "we already have ML predictions on every protein" premise would be stronger. Not urgent.
