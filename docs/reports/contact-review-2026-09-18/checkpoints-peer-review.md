> Review history: this is an initial proposal or independent critique, not the final accepted rule set. See the consolidated report for accepted corrections and final counts.

# Independent peer review of checkpoint partner rules

Reviewed 2026-09-18 against `checkpoints-records.json`, all 75 proposed rules, the report, cached primary PDB entry/polymer-entity metadata, and public primary PDB/paper records. **No source files, rules, observations or production resources were edited.** Indices below are **zero-based JSON array indices**; the parent report numbers rules one higher.

## Verdict

The frozen snapshot has no demonstrated wrong engineered-Ipi or 5C8 assignment. All 75 rules match at least one observation. Independent replay of the production normalization/matching semantics found 225 of 232 observations matched, with only three overlaps: two 7SU0 observations hit `[61, 62]`, and one 7SU1 observation hits `[61, 63]`. In the supplied order the narrower correct identities win. No other overlapping rules or accidental numeric-IEDB-ID matches were found.

**Recommendation:** the full set is acceptable for a review artifact pinned to this exact snapshot and order. Before making it a reusable production rule set, narrow six rules—indices **25, 26, 49, 50, 53, 61**—as described below. The other **69 rules** are a conservative safe subset for consolidation. This is a scope-hardening recommendation, not an assertion that those six currently misclassify observations. Do not invent a present error to justify withholding the correct variant corrections.

## Material scope and integration findings

### 1. Rule 61 is order-dependent against known engineered constructs

- Index **61** (report rule 62): all-PDB `Ipilimumab`, `Ipilimumab Fab`, `ipilimumab Fv` → parent Ipilimumab.
- Indices **62/63** (report 63/64): 7SU0 → Ipi.105; 7SU1 → Ipi.106.
- Current output is correct only because the scoped variants follow the global rule. Sorting rules alphabetically, prepending the variants, or allowing a later parent rule during consolidation reintroduces the known incorrect therapeutic-parent assignment for three observations.
- Concrete improvement: replace index 61 with parent rules scoped to observed 5TRU, 5XJ3, 6RP8 and 7ELX, retaining the arm-projection caveat at 7ELX. Keep indices 62/63 unchanged. Alternatively preserve ordering explicitly and add a focused validation assertion covering these three observations. A future unseen variant called `Ipilimumab Fab` should not silently inherit parent identity.
- Primary evidence: [7SU0](https://www.rcsb.org/structure/7SU0), [7SU1](https://www.rcsb.org/structure/7SU1), [Lee et al., acidic-pH variants](https://doi.org/10.1080/19420862.2021.2024642).

### 2. Generic OX40 Ab1/Ab2 aliases should not apply to every deposition

- Index **25** includes `Ab1` globally in the vonlerolizumab/1A7 alias group.
- Index **26** includes `Ab2` globally in the 3C8 group.
- The current four IEDB Ab1/Ab2 observations are correctly assigned. I independently checked cached polymer sequences: 6OGX entities 1/2 equal 6OKN 1A7 heavy/light; 6OGX entities 4/5 equal 6OKM 3C8 heavy/light. This supports the local source shorthand, not the globally reusable names “Ab1” and “Ab2.” A different OX40 paper can reuse those labels.
- Concrete improvement: split generic `Ab1` rules to **6OGX and 6OKN** and generic `Ab2` rules to **6OGX and 6OKM**. Keep specific names `Vonlerolizumab`, `RG7888`, `1A7`, `3C8` and PDB-embedded `6OGX_1/_2` in their appropriate stable alias groups. Narrowing the whole existing rules to their supported PDBs is also safe, though less flexible.
- Primary evidence: [6OGX](https://www.rcsb.org/structure/6OGX), [6OKN](https://www.rcsb.org/structure/6OKN), [6OKM](https://www.rcsb.org/structure/6OKM), [dual-antibody OX40 study](https://doi.org/10.1080/19420862.2019.1625662).

### 3. Unprefixed BTLA clone labels need the structural scope used in their rationale

- Index **49** globally converts `22B3` to **h22B3**; index **50** globally converts `25F7` to **h25F7**.
- Current IEDB entries are respectively 8F6O and 8F6L, so the intended humanized structural interpretation is supported. The reason text itself says “refer here … in 8F6O/8F6L.” The all-PDB matcher does not encode that limitation. Dropping the `h` prefix can also identify a parental/nonhuman clone outside these structures.
- Concrete improvement: scope the `22B3` source shorthand to **8F6O** and `25F7` to **8F6L**. Explicit `h22B3`/`h25F7` names may remain family aliases, or simply scope both complete rules to the sole supported deposition each.
- Keep index **48** Venanprubart separate, as proposed. The cached evidence really does contain an `exact_VH_VL` match for venanprubart, arm 0, antibody A/B, antigen C, 8F6O. This establishes a catalogue arm projection, not whole-construct equivalence or reconciliation of the clinical occupancy-reagent terminology. No evidence reviewed here justifies merging the drug and structural clone names.
- Primary evidence: [8F6O](https://www.rcsb.org/structure/8F6O), [8F6L](https://www.rcsb.org/structure/8F6L), [BTLA structural study](https://doi.org/10.1016/j.str.2023.05.011). The linked clinical PMC page in the original report returned a browser challenge during this peer review, so its detailed clone wording was not independently reverified and is not used as decisive evidence here.

### 4. Rule 53 still contains a generic parent label despite careful 5C8 variants

- Index **53** globally maps `humanized 5c8` to Ruplizumab, while indices **64/65** appropriately scope raw `5C8 Fab`/`5c8 Fab` to 1I9R versus 6W9G.
- Current `humanized 5c8` observation is only 1I9R and is consistent. However 6W9G's own primary title also calls its modified construct “humanized 5c8 antibody,” so the generic phrase is not intrinsically an unmodified-parent identity. If a future source drops the asterisk and uses that label in 6W9G, index 53 would assign Ruplizumab, and index 65 would **not** rescue it because its names do not match `humanized 5c8`.
- Concrete improvement: keep explicit `Ruplizumab` global if desired, but scope `humanized 5c8` to **1I9R**. Keep indices 56, 57, 64, 65 and 74 intact.
- Primary evidence: [parent 1I9R](https://www.rcsb.org/structure/1I9R), [fluorescent 6W9G](https://www.rcsb.org/structure/6W9G), [fluorescent 5c8 study](https://doi.org/10.1021/acs.biochem.0c00474).

## Explicit engineered-variant checks: passed

| Indices | Proposed distinction | Independent check |
|---|---|---|
| 62 / 63 | Ipi.105 / Ipi.106 | 7SU0 and 7SU1 titles explicitly identify the respective acidic-pH-selective variants. The parent study confirms engineered altered-pH affinity. Keep separate from parent and mipi.4. |
| 12 / 67 | mipi.4 and its anonymous SAbDab record | Specific 9DQ3 construct; no collapse into parent Ipilimumab. |
| 64 | 1I9R parent 5C8 → Ruplizumab binding-domain alias | Narrow 1I9R scope prevents a casefolded generic 5C8 name from overriding the fluorescent deposits. |
| 56 / 65 / 74 | 6W9G 5c8* | PDB explicitly reports fluorescent noncanonical L-(7-hydroxycoumarin-4-yl)ethylglycine. It is not the unmodified parent. AACDB, IEDB and SAbDab observations converge within this PDB. |
| 57 | 7SGM 5c8* WH47L | Cached entity 2 explicitly has heavy-chain mutation W47L; its sequence differs from the 6W9G heavy chain at that position. The fluorescent construct remains separate from both parent 5C8 and unmutated 5c8*. |

The production normalization does **not** strip the asterisk or WH47L string; these variants remain distinguishable. It does strip case and terminal Fab/Fv/VHH, which is why 1I9R versus 6W9G needs explicit PDB scopes. [7SGM](https://www.rcsb.org/structure/7SGM) and its [primary photophysics study](https://doi.org/10.1016/j.jmb.2022.167455) support the W47L distinction.

## Other high-risk distinctions checked and retained

- **8SZY TIGIT, indices 36/40:** cached entity author chains A/C + B/D are CHA.9.543; H/I + L/M are BMS-986207. Distinct sequence entities support the proposed nonblocking-tool versus renvistobart identities. No chain conflation found. The target entity is TIGIT **C69S**, worth retaining as receptor-construct provenance; it does not create a different ligand. [8SZY](https://www.rcsb.org/structure/8SZY).
- **8VTE, index 37:** entity descriptions identify tiragolumab despite an inconsistent entry title. Sequence/entity evidence is the appropriate basis; do not change it to vibostolimab based on title alone. [8VTE entity 1](https://data.rcsb.org/rest/v1/core/polymer_entity/8vte/1), [entity 2](https://data.rcsb.org/rest/v1/core/polymer_entity/8vte/2).
- **CD40 IEDB ID 197330:** used for ABBV-323 and FAB516, but rules 19 and 22 correctly match distinct descriptive labels and never use this raw numeric ID. No collision.
- **CD27 indices 46/47:** M2191 and humanized H2191 remain separate. Their [5TLJ](https://www.rcsb.org/structure/5TLJ) and [5TLK](https://www.rcsb.org/structure/5TLK) contexts support that decision.
- **CD40LG index 60:** 6BRB entity 2 is an engineered Tn3-like scaffold, not natural TNC. `VIB4920-related Tn3 binding domain` is deliberately qualified and is acceptable; do not shorten it to either “TNC” or “VIB4920” without the binding-domain qualifier. [6BRB](https://www.rcsb.org/structure/6BRB), [primary development study](https://doi.org/10.1126/scitranslmed.aar6584).
- **Indices 32/33:** 1618 and HZ-L-Yr-16 remain named binding-domain constructs rather than being renamed to the complete bispecific drugs. Their therapeutic-development category is defensible with that wording and is not a regulatory-approval assertion. [7YXU](https://www.rcsb.org/structure/7YXU), [7D4B](https://www.rcsb.org/structure/7D4B).
- **Shared drug arms, indices 0–4, 17–18, 48, 54–55:** distinct catalogue drug names remain distinct; no full-drug crystallization assertion is made. Exact arm matching must remain visible on source observations. These rules should not be interpreted as counts of separately crystallized drug molecules.
- **Unresolved 7ELX, index 8:** keeping the deposited anonymous Fab unclassified while retaining separate exact-arm catalogue projections is cautious and internally consistent.
- **Generic 6Y8K peptide, index 34:** correct PDB scope; no global peptide identity inference. **LKJ index 59** is a specific CCD ligand identity rather than an ambiguous amino-acid sequence label.

## Consolidation recommendation

Retain all source labels, residue arrays and identity-match records. Start from the 69-rule safe subset excluding indices 25, 26, 49, 50, 53, 61, then add the narrow replacements above. Preserve all variant corrections and explicitly test 7SU0, 7SU1, 1I9R, 6W9G and 7SGM after merging rule sets. Recompute counts from individual observations after rules, not summary representatives. No new quarantine/exclusion is warranted by this peer review, and no original observation should be removed.
