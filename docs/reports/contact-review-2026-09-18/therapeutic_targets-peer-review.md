> Review history: this is an initial proposal or independent critique, not the final accepted rule set. See the consolidated report for accepted corrections and final counts.

# Independent peer review: therapeutic-target contact proposals

Reviewed all 75 proposed rules against the 247-observation snapshot, the original report, cached antibody-arm matches, the production matcher and viewer counting semantics, and focused primary-source checks. Rule indices below are **one-based positions in `therapeutic_targets-rules.json["rules"]`**. This is a proposal review, not a published data change; original files and observations remain unchanged.

**Recommendation: accept 62 rules provisionally and correct or replace 13 before consolidation.** Withhold indices **18, 21, 22, 30, 31, 32, 49, 60, 61, 62, 63, 72, 74**. Most corrections restore legitimate evidence rather than dispute the recorded contact residues. No reason was found to merge distinct drugs solely because they share a parent antibody arm.

## High: nine exclusions incorrectly hide valid therapeutic-arm evidence

Rules **18, 30, 31, 49, 60, 61, 62, 72, 74** set `exclude_from_overview: true` because the intact therapeutic was not crystallized. That is inconsistent with the accepted review policy: sequence-matched therapeutic arms remain named therapeutic evidence, with their inference provenance explicit. It is also inconsistent within this proposal: rule 3 retains erzotabart even though the Fab structure does not contain the therapeutic Fc engineering.

Set exclusion to **false** for all nine. Keep each therapeutic identity separate from its experimental template construct and from other drugs with the same arm. Revise reasons to state the exact evidence tier and observed construct; do not claim that a complete bispecific, ADC, fusion, or Fc-engineered IgG was observed.

| Rule | Target | Named therapeutic | Actual structural template/evidence |
|---:|---|---|---|
| 18 | ERBB3 P21860 | Zenocutuzumab | MF3178 Fab, 5O4O/5O7P; therapeutic-arm match |
| 30 | CD47 Q08722 | Safimestomig | 6MW3211 CD47-binding Fab, 7XJF; cached exact VH/VL match |
| 31 | CD47 Q08722 | Zeripatamig | K2 Fab, 8RP8; cache tier is `Thera_100pct_structure_chain`, not verified full paired VH/VL |
| 49 | BCMA Q02223 | Pamlectabart | J22.9-ISY Fab, 8QYB; cached exact VH/VL match |
| 60 | MS4A1 P11836 | Eramkafusp | Rituximab-derived template arm, 2OSL/6VJA/6Y90/8VGN |
| 61 | MS4A1 P11836 | Ripertamab | Rituximab variable-region template, same PDB set |
| 62 | MS4A1 P11836 | Glofitamab | GA101/obinutuzumab Fab, 3PP4 |
| 72 | DR5 O14763 | Benufutamab | IgG1-hDR5-01 Fab in 6T3J; cached pairs A/B and F/G |
| 74 | DR5 O14763 | Tilogotamab | IgG1-hDR5-05 Fab in 6T3J; cached pairs C/D and H/I |

The deposited constructs are directly documented by [5O4O](https://www.rcsb.org/structure/5O4O), [7XJF](https://www.rcsb.org/structure/7XJF), [8RP8](https://www.rcsb.org/structure/8RP8), [8QYB](https://www.rcsb.org/structure/8QYB), [6Y90](https://www.rcsb.org/structure/6Y90), [3PP4](https://www.rcsb.org/structure/3PP4), and [6T3J](https://www.rcsb.org/structure/6T3J). The arm association itself comes from the unchanged cached match evidence, not from an inference that a PDB title names the complete drug. Preserve the weaker evidence tier for Zeripatamig.

Two particularly useful primary checks support keeping construct distinctions explicit:

- The [ripertamab comparison study](https://pmc.ncbi.nlm.nih.gov/articles/PMC9829503/) describes the shared variable sequence but a constant-region difference from rituximab. Shared Fab-variable identity is neither grounds for hiding ripertamab nor for merging the complete antibodies.
- The [WHO proposed-INN document](https://iris.who.int/bitstream/handle/10665/339768/9789240004511-eng.pdf) describes benufutamab as an Fc-engineered anti-DR5 antibody. The separate -01 and -05 Fab chains remain separate observations. Do not substitute a combined two-antibody therapeutic label for either one.

## Medium: rule 49 additionally uses the wrong payload rationale

Rule **49**, BCMA/Pamlectabart, invokes the absence of an ADC payload. **Pamlectabart and pamlectabart tismanitin are distinct names.** The [FDA substance record for pamlectabart](https://precision.fda.gov/ginas/app/ui/substances/64959883-5ab3-4aeb-905e-ba4ca27ad25d) identifies the antibody and code J22.9-ISY-D265C, including its constant-region substitution. The bare antibody name does not assert the tismanitin conjugate.

Remove the payload rationale. Retain Pamlectabart as a separately named sequence-matched therapeutic, explicitly preserving the experimental J22.9-ISY Fab versus therapeutic constant-region variant distinction. Do not merge J22.9-ISY with J22.9-H, J22.9-FNY, or J22.9-xi; rules 43–46 appropriately keep those variants separate.

## High: rules 21 and 22 remove legitimate all-contact evidence

Rules **21** (ERBB3 P21860, `P00533`/`EGFR`) and **22** (`DB8`/Bosutinib) justify global exclusion using intracellular localization. However, `exclude_from_overview` removes a partner from **both EC and all-contact overviews**. The existing compartment filter already prevents the supplied intracellular observations from contributing to the EC overview.

Set exclusions to **false**, preserve the kinase-domain context, and scope structure-dependent reasons to their actual structures if appropriate. [4RIY](https://www.rcsb.org/structure/4RIY) documents an EGFR/HER3 kinase-domain complex; [6OP9](https://www.rcsb.org/structure/6OP9) documents bosutinib in the HER3 pseudokinase domain. Neither is a spurious molecular interaction just because it is intracellular. EGFR remains `receptor_partner`; Bosutinib remains `therapeutic`. This correction restores two all-contact identities and adds zero EC identities.

## Medium: rule 32 unnecessarily combines native SIRPA and engineered IMM01-domain evidence

Rule **32** (CD47 Q08722, names `P78324`, `SIRPA`) globally relabels known native and engineered constructs as a mixed, unclassified partner. Its reason says a PDB-scoped repair is required; such rules are already supported and authorized, so this deferral is unnecessary.

Replace with a native SIRPA `receptor_partner` rule for the supported native complexes **2JJS/2JJT/4CMM**, plus a separate **7YGG** override whose canonical name explicitly identifies **engineered SIRPα D1 N80A / IMM01 binding domain**. Do not label the deposited domain as a complete Fc-fusion drug. Preserve the raw accession and observation. A narrowly described therapeutic-domain category is defensible with the IMM01 primary-paper provenance; if that convention is not adopted, keep only this engineered construct unclassified while restoring the native receptor category.

[7YGG](https://www.rcsb.org/structure/7YGG) names SIRPa.D1(N80A); its [primary study](https://doi.org/10.3390/molecules27175574) describes the IMM01 program. The native complexes are separately inspectable at [2JJS](https://www.rcsb.org/structure/2JJS), [2JJT](https://www.rcsb.org/structure/2JJT), and [4CMM](https://www.rcsb.org/structure/4CMM). This is genuine variant differentiation, not a clone equivalence inferred from a common footprint.

A PDB-specific rule is sufficient here. For 6T3J in the DR5 rules, two distinct antibodies coexist in the same PDB, so a generic whole-PDB identity rename would not be sufficient: retain the distinct source names and cached chain pairs.

## Medium: retain the rule 63 exclusion only as a narrowly scoped unresolved identity conflict

Rule **63**, MS4A1/Ibritumomab, is unlike the valid arm-only cases above. Its cached exact VH/VL match points at **3BKY**, whose deposited antibody is **chimeric C2H7**. The [3BKY deposition and primary study](https://www.rcsb.org/structure/3BKY) specifically describe C2H7 and its binding differences from rituximab. The [FDA chemistry review](https://www.accessdata.fda.gov/drugsatfda_docs/nda/2002/125019_0000_Zevalin_ChemR.pdf) identifies ibritumomab as **IDEC-2B8**, not C2H7. The [FDA medical review](https://www.accessdata.fda.gov/drugsatfda_docs/nda/2002/125019_0000_Zevalin_MedR.pdf) separately identifies rituximab as the chimeric C2B8 antibody.

Keep this association out of the named overview pending reconciliation, but change `pdb` to **3bky** and rewrite the reason as an **unresolved source/sequence identity conflict**. Do not certify the cached row as an established ibritumomab structural arm merely because the cache says exact match. A conservative association-level category is `unclassified`; the therapeutic nature of authentic ibritumomab does not validate this particular linked structure. The raw label must remain Ibritumomab. A future independently verified ibritumomab structure should not inherit an all-PDB exclusion.

## Matcher effects and estimated counts

The matcher casefolds names and strips trailing Fab/Fv/VHH and parenthetical qualifiers. It uses exact normalized identities, not substring matching. The supplied labels are compatible with these rules; no current cross-clone collision was identified in this bounded snapshot. All-PDB rules on short numeric SIRPA labels such as `3`, `119`, `136`, and `218` remain limited to target accession but are less future-proof than structure-scoped rules; scope them on a later hardening pass if broader source coverage is imported. This is not evidence of a current collision.

Exclusion is sticky: a later `exclude_from_overview: false` rule does not undo an earlier true value. **Edit or remove the original exclusion rules before rebuilding; do not append apparent undo rules.** Narrow variant overrides should follow broad native defaults where used.

Independent reproduction of the viewer's named-partner and scope predicates over all 247 raw observations produced these estimates. The corrected column only reverses exclusions in rules 18/21/22/30/31/49/60/61/62/72/74; it still retains the narrow unresolved Ibritumomab and synthetic Y01 exclusions. It does not yet split rule 32.

| Target | Proposed all / EC | Corrected all / EC |
|---|---:|---:|
| CD38 P28907 | 11 / 11 | 11 / 11 |
| ERBB3 P21860 | 8 / 8 | 11 / 9 |
| CD47 Q08722 | 8 / 8 | 10 / 10 |
| SIRPA P78324 | 9 / 9 | 9 / 9 |
| BCMA Q02223 | 8 / 8 | 9 / 9 |
| MSLN Q13421 | 5 / 5 | 5 / 5 |
| MS4A1 P11836 | 5 / 4 | 8 / 7 |
| DR5 O14763 | 8 / 8 | 10 / 10 |

Splitting native SIRPA and its engineered 7YGG construct should raise CD47 from 10 to **11 EC names**, provided the currently named observation labels are retained. A canonical label alone does not promote a bare accession under the viewer predicate. These are snapshot estimates, not a rebuilt release or a count of independent full-drug structures.

## Safe subset and residual uncertainties

The **62-rule provisional safe subset** is every index from 1 through 75 except **18, 21, 22, 30, 31, 32, 49, 60, 61, 62, 63, 72, 74**. This is a bounded review finding, not a promise about future observations introduced under broad aliases.

Keep the conservative unresolved treatment of **rules 39/40** (Fab 25/hAB21 versus AB21 source label), **54** (MSLN 3F2 versus inconsistent paper accession text), and **75** (GA101/B-Ly1/H299 source aggregate). Their uncertainty should not be removed merely because related antibodies share epitopes. Rule **64**, synthetic cholesterol hemisuccinate Y01, is an assay-additive exclusion rather than an intracellular-localization exclusion and need not be reverted with 21/22. Ofatumumab's current all-versus-EC difference comes from topology filtering, not an identity repair.

The original report's statement that every PDB field must be empty is stale: nonempty PDB scopes are supported and were explicitly approved. Its count table and narrative describing therapeutic-arm records as overview duplicates must be updated with the corrected policy. Primary source checks establish construct provenance and named-drug distinctions; cached sequence-match claims were reviewed as cached evidence, not recomputed from complete drug sequences in this peer-review pass.
