# Tag-site disulfide-clearance floor — calibration against published sites

Measured from the position-pinned internal literature tag-site corpus in `tag_site_public`. Every distance is junction residue -> nearest **model-bonded** cysteine. Bonds are read off the model as any Cys pair with SG-SG < 2.5 A, never from UniProt `DISULFID`.

## The four conventions, and which one the gate consumes

These differ by 1-4 A, so a floor fitted on one does **not** transfer to a gate applying another. Every number below names its convention.

| name in these outputs | measured from | measured to | used by |
|---|---|---|---|
| `ca_ca` (CA-CA) | junction CA | cysteine CA | **`features.py`'s 10 A floor** |
| `ca_sg` (CA-SG) | junction CA | cysteine SG | the ordering session's measurements |
| `heavy_sg` (heavy-SG) | nearest junction heavy atom | cysteine SG | the predictors session; the `features.py` P35 numbers |
| `heavy` (heavy-heavy) | nearest junction heavy atom | nearest cysteine heavy atom | the ordering session's "heavy" column |

`features.py` consumes **CA-CA**, so that is the row a change to the constant alone would move. Changing the convention is a separate decision from changing the number, and this study deliberately does not make it.

## Two limits on what this can be used for

**There is no negative set.** Every site here worked and got published, so a floor rejecting 0% of them is shown only to be *not too strict*. Nothing in this study speaks to a floor being too permissive, because failed insertions are not published. It bounds the floor from above and cannot confirm one from below.

**Insert length is absent from the corpus** — `tag_length_aa` is NULL on all 185 rows. The size class below is derived from the `tag_type` free text, not measured. So this describes where mostly-small epitope tags sit, which licenses a floor for an 8-11 aa tag and **does not** license one for the 51-aa cassette.

**The arms this informs carry the full 51-aa cassette.** A proposal circulated that the 51-aa SpyTag003+ALFA tandem is terminal-only — SpyTag003 being a beta-strand that must complete SpyCatcher's sheet and arguably cannot while tethered at both ends — and that loops should take 19-aa ALFA or 23-aa DogTag instead. **That proposal was withdrawn by the session that made it**, on in-house evidence of internal SpyTag working at TFRC V291 (reagent P-0007, built and received), and all six internal arms were confirmed to contain the complete 51-aa cassette, each tagged protein being native + 51. So the 19-23 aa figure describes a proposal, not the constructs, and the limit above is the binding one exactly as written: **nothing measured here licenses a floor for a 51-aa internal insert.**

The nearest evidence this corpus holds is therefore the **>=100 aa fusion-domain band**, which brackets 51 aa from *above* only — those inserts are 2-6x larger than the cassette, so a site that took one is evidence a cassette-sized insert is tolerable there, while a site that did not take one says nothing. The 31-99 aa band, which would bracket 51 aa from below, is near-empty. The 12-30 aa band is reported because it is well-defined, not because it is the operative cargo here.

### Scope: internal sites only

This corpus is the **internal** literature tag sites — the ones where a cassette is threaded into a loop and a nearby disulfide is a hazard to thread past. `tag_site_public` also holds 722 position-pinned `terminal_n` and 83 `terminal_c` literature sites, and they are not measured here. If `features.py` applies the same clearance veto to terminal candidates, then a floor calibrated on this corpus is being transferred to a case it was not fitted on — a free chain end is not a threaded loop. Worth confirming which site kinds the veto actually runs on before the number is adopted for all of them.

## Cohort

- sites resolved and measured: **130**
- sites whose protein has **no model disulfide**: **54** (reported separately, never as infinity — they carry no information about the floor)
- sites excluded before measurement: **1**
- proteins measured: **95**; distinct genes: **95**

Exclusions, by reason:

- 1 x model sequence != UniProt sequence for Q9NS40 (model 732 aa vs UniProt 1196 aa, first difference at residue 298)

### Bond classification is not a knife edge

- 592 bonded pairs, widest SG-SG **2.08 A**
- nearest *unbonded* Cys-Cys pair anywhere in the cohort: **3.13 A**
So the 2.5 A cut separates two well-separated populations; no pair sits near it.

## Minimum observed distance — the number that bounds the floor

A floor cannot exceed the tightest working site without rejecting a known success. Each convention is minimised independently, so the binding site can differ between conventions.

| convention | minimum observed | gene | site | nearest bonded Cys | bond | annotated in UniProt |
|---|---:|---|---|---|---|---|
| CA-CA | **3.81 A** | ITGB7 | Q427 (after-427) | C428 | C412-C428 | yes |
| CA-SG | **4.94 A** | SMO | P153 (after-153) | C154 | C118-C154 | yes |
| heavy-SG | **3.54 A** | ITGB7 | Q427 (after-427) | C412 | C412-C428 | yes |
| heavy-heavy | **1.33 A** | ITGB7 | Q427 (after-427) | C428 | C412-C428 | yes |

### How much did the nearest cysteine win by

A per-site minimum reported as "the nearest bonded cysteine" can be a near-tie between two cysteines, which the single number hides. Every (site, bonded cysteine) pair is in `per_site_per_cysteine.tsv`.

| convention | median gap to runner-up | sites within 1 A of a tie | sites with only one bonded Cys |
|---|---:|---:|---:|
| CA-CA | 2.26 A | 33 | 0 |
| CA-SG | 1.02 A | 65 | 0 |
| heavy-SG | 1.03 A | 62 | 0 |
| heavy-heavy | 2.23 A | 30 | 0 |

The minimum is taken over **every** bonded cysteine, never the nearest by sequence: the binding cysteine under heavy-heavy sits a median **53** residues away in sequence, up to **1190**, so a sequence-distance test measures a different axis entirely.

## The tightest sites are sequence-adjacent, where distance is not clearance

**9 of 130 measured sites sit within 2 residues of their nearest bonded cysteine in sequence.** At a separation of 1 the numbers are geometric constants, not measurements: heavy-heavy lands at 1.33-1.35 A, which is the peptide C-N bond, and CA-CA at 3.81-3.86 A, which is the Ca-Ca virtual bond. A distance-based floor cannot say anything useful about those sites because every one of them returns the same number for the same reason.

This is not a nuisance to discard. These are **published working sites inserted immediately beside a bonded cysteine**, and that is a stronger statement against a large clearance floor than any distance would be:

| gene | site | Cys | sep | CA-CA | CA-SG | heavy-SG | heavy-heavy | tier | position | cargo band |
|---|---|---:|---:|---:|---:|---:|---:|---|---|---|
| ITGB7 | Q427 | C428 | 1 | 3.81 | 4.99 | 3.54 | 1.33 | surface_only | inferred | c_12_to_30aa |
| ADCYAP1R1 | D24 | C25 | 1 | 3.84 | 5.39 | 4.35 | 1.34 | surface_and_function | validated | b_epitope_to_11aa |
| SMO | P153 | C154 | 1 | 3.86 | 4.94 | 3.94 | 1.34 | detected_only | validated | c_12_to_30aa |
| TRPV3 | P613 | C612 | 1 | 3.84 | 6.13 | 4.87 | 1.35 | surface_only | inferred | e_unknown |
| CRB2 | D1096 | C1098 | 2 | 5.37 | 6.68 | 4.16 | 2.85 | surface_and_function | validated | d_domain_100aa_plus |
| KCNH2 | T443 | C445 | 2 | 5.98 | 7.61 | 5.48 | 2.94 | surface_and_function | validated | b_epitope_to_11aa |
| SLC12A3 | G414 | C416 | 2 | 5.83 | 7.44 | 6.07 | 3.13 | surface_only | validated | b_epitope_to_11aa |
| ADGRG6 | D550 | C548 | 2 | 5.63 | 7.06 | 6.42 | 3.29 | surface_and_function | validated | a_single_ncAA |
| TSPAN2 | K154 | C152 | 2 | 5.89 | 6.37 | 5.76 | 4.33 | surface_only | validated | e_unknown |

The load-bearing row is **ADCYAP1R1 D24** — `surface_and_function`, position `validated`, inserted 1 residue(s) from bonded C25 at 3.84 A CA-CA. A floor anywhere at or above 4 A CA-CA rejects it, and it is a site whose tagged protein was shown both to reach the surface and to still work.

Everything below is therefore reported **twice**: over all measured sites, and over the 121 sites whose junction is more than 2 residues from the cysteine, where the distance really is a spatial clearance. Read the second table when you want to know where a floor bites geometrically, and the first when you want to know what it would reject in practice.

| convention | min, all sites | min, spatial only (sep > 2) |
|---|---:|---:|
| CA-CA | 3.81 A | 5.29 A |
| CA-SG | 4.94 A | 5.04 A |
| heavy-SG | 3.54 A | 4.13 A |
| heavy-heavy | 1.33 A | 2.80 A |

## Retrospective rejections by floor and convention

All 130 measured sites.

| floor | CA-CA rejected | CA-SG rejected | heavy-SG rejected | heavy-heavy rejected |
|---|---:|---:|---:|---:|
| 4 A | 4 (3.1%) | 0 (0.0%) | 2 (1.5%) | 14 (10.8%) |
| 5 A | 4 (3.1%) | 2 (1.5%) | 7 (5.4%) | 18 (13.9%) |
| 6 A | 14 (10.8%) | 5 (3.9%) | 15 (11.5%) | 18 (13.9%) |
| 7 A | 17 (13.1%) | 10 (7.7%) | 20 (15.4%) | 21 (16.2%) |
| 8 A | 18 (13.9%) | 18 (13.9%) | 22 (16.9%) | 26 (20.0%) |
| 9 A | 18 (13.9%) | 20 (15.4%) | 23 (17.7%) | 28 (21.5%) |
| 10 A | 22 (16.9%) | 22 (16.9%) | 28 (21.5%) | 33 (25.4%) |
| 11 A | 28 (21.5%) | 25 (19.2%) | 30 (23.1%) | 37 (28.5%) |
| 12 A | 31 (23.8%) | 28 (21.5%) | 33 (25.4%) | 41 (31.5%) |
| 13 A | 32 (24.6%) | 31 (23.8%) | 41 (31.5%) | 51 (39.2%) |
| 14 A | 37 (28.5%) | 39 (30.0%) | 45 (34.6%) | 57 (43.9%) |
| 15 A | 49 (37.7%) | 43 (33.1%) | 49 (37.7%) | 61 (46.9%) |
| 16 A | 51 (39.2%) | 47 (36.1%) | 54 (41.5%) | 64 (49.2%) |

Spatial subset only — the 121 sites more than 2 residues from their cysteine:

| floor | CA-CA rejected | CA-SG rejected | heavy-SG rejected | heavy-heavy rejected |
|---|---:|---:|---:|---:|
| 4 A | 0 (0.0%) | 0 (0.0%) | 0 (0.0%) | 6 (5.0%) |
| 5 A | 0 (0.0%) | 0 (0.0%) | 2 (1.7%) | 9 (7.4%) |
| 6 A | 5 (4.1%) | 2 (1.7%) | 8 (6.6%) | 9 (7.4%) |
| 7 A | 8 (6.6%) | 4 (3.3%) | 11 (9.1%) | 12 (9.9%) |
| 8 A | 9 (7.4%) | 9 (7.4%) | 13 (10.7%) | 17 (14.1%) |
| 9 A | 9 (7.4%) | 11 (9.1%) | 14 (11.6%) | 19 (15.7%) |
| 10 A | 13 (10.7%) | 13 (10.7%) | 19 (15.7%) | 24 (19.8%) |
| 11 A | 19 (15.7%) | 16 (13.2%) | 21 (17.4%) | 28 (23.1%) |
| 12 A | 22 (18.2%) | 19 (15.7%) | 24 (19.8%) | 32 (26.5%) |
| 13 A | 23 (19.0%) | 22 (18.2%) | 32 (26.5%) | 42 (34.7%) |
| 14 A | 28 (23.1%) | 30 (24.8%) | 36 (29.8%) | 48 (39.7%) |
| 15 A | 40 (33.1%) | 34 (28.1%) | 40 (33.1%) | 52 (43.0%) |
| 16 A | 42 (34.7%) | 38 (31.4%) | 45 (37.2%) | 55 (45.5%) |

## Stratified by validation tier

A floor calibrated on "displayed" and one on "displayed AND functional" are different floors, so they are reported separately rather than averaged. 62% of the 1,093 literature sites in the corpus carry no functional validation at all.

| tier | n measured | n no-disulfide |
|---|---:|---:|
| surface_and_function | 49 | 17 |
| surface_only | 60 | 32 |
| detected_only | 19 | 1 |
| function_only | 1 | 2 |
| not_measured | 0 | 1 |
| function_perturbed | 1 | 1 |

### surface_and_function (n=49)

Minimum observed: CA-CA **3.84 A** (ADCYAP1R1 D24), CA-SG **5.06 A** (NPC1L1 S986), heavy-SG **4.13 A** (NPC1L1 S986), heavy-heavy **1.34 A** (ADCYAP1R1 D24)

| floor | CA-CA rejected | CA-SG rejected | heavy-SG rejected | heavy-heavy rejected |
|---|---:|---:|---:|---:|
| 4 A | 1 (2.0%) | 0 (0.0%) | 0 (0.0%) | 7 (14.3%) |
| 5 A | 1 (2.0%) | 0 (0.0%) | 3 (6.1%) | 10 (20.4%) |
| 6 A | 8 (16.3%) | 2 (4.1%) | 8 (16.3%) | 10 (20.4%) |
| 7 A | 9 (18.4%) | 4 (8.2%) | 10 (20.4%) | 10 (20.4%) |
| 8 A | 10 (20.4%) | 10 (20.4%) | 11 (22.4%) | 11 (22.4%) |
| 9 A | 10 (20.4%) | 10 (20.4%) | 11 (22.4%) | 11 (22.4%) |
| 10 A | 11 (22.4%) | 11 (22.4%) | 12 (24.5%) | 15 (30.6%) |
| 11 A | 11 (22.4%) | 12 (24.5%) | 13 (26.5%) | 15 (30.6%) |
| 12 A | 12 (24.5%) | 12 (24.5%) | 13 (26.5%) | 15 (30.6%) |
| 13 A | 13 (26.5%) | 12 (24.5%) | 16 (32.6%) | 19 (38.8%) |
| 14 A | 15 (30.6%) | 15 (30.6%) | 17 (34.7%) | 21 (42.9%) |
| 15 A | 19 (38.8%) | 16 (32.6%) | 18 (36.7%) | 22 (44.9%) |
| 16 A | 19 (38.8%) | 17 (34.7%) | 20 (40.8%) | 23 (46.9%) |

### surface_only (n=60)

Minimum observed: CA-CA **3.81 A** (ITGB7 Q427), CA-SG **4.99 A** (ITGB7 Q427), heavy-SG **3.54 A** (ITGB7 Q427), heavy-heavy **1.33 A** (ITGB7 Q427)

| floor | CA-CA rejected | CA-SG rejected | heavy-SG rejected | heavy-heavy rejected |
|---|---:|---:|---:|---:|
| 4 A | 2 (3.3%) | 0 (0.0%) | 1 (1.7%) | 6 (10.0%) |
| 5 A | 2 (3.3%) | 1 (1.7%) | 3 (5.0%) | 7 (11.7%) |
| 6 A | 5 (8.3%) | 2 (3.3%) | 6 (10.0%) | 7 (11.7%) |
| 7 A | 7 (11.7%) | 5 (8.3%) | 8 (13.3%) | 9 (15.0%) |
| 8 A | 7 (11.7%) | 7 (11.7%) | 8 (13.3%) | 11 (18.3%) |
| 9 A | 7 (11.7%) | 8 (13.3%) | 9 (15.0%) | 12 (20.0%) |
| 10 A | 9 (15.0%) | 8 (13.3%) | 11 (18.3%) | 12 (20.0%) |
| 11 A | 12 (20.0%) | 10 (16.7%) | 12 (20.0%) | 16 (26.7%) |
| 12 A | 13 (21.7%) | 11 (18.3%) | 14 (23.3%) | 19 (31.7%) |
| 13 A | 13 (21.7%) | 14 (23.3%) | 17 (28.3%) | 23 (38.3%) |
| 14 A | 15 (25.0%) | 16 (26.7%) | 20 (33.3%) | 26 (43.3%) |
| 15 A | 22 (36.7%) | 19 (31.7%) | 23 (38.3%) | 29 (48.3%) |
| 16 A | 24 (40.0%) | 22 (36.7%) | 26 (43.3%) | 30 (50.0%) |

### detected_only (n=19)

Minimum observed: CA-CA **3.86 A** (SMO P153), CA-SG **4.94 A** (SMO P153), heavy-SG **3.94 A** (SMO P153), heavy-heavy **1.34 A** (SMO P153)

| floor | CA-CA rejected | CA-SG rejected | heavy-SG rejected | heavy-heavy rejected |
|---|---:|---:|---:|---:|
| 4 A | 1 (5.3%) | 0 (0.0%) | 1 (5.3%) | 1 (5.3%) |
| 5 A | 1 (5.3%) | 1 (5.3%) | 1 (5.3%) | 1 (5.3%) |
| 6 A | 1 (5.3%) | 1 (5.3%) | 1 (5.3%) | 1 (5.3%) |
| 7 A | 1 (5.3%) | 1 (5.3%) | 2 (10.5%) | 2 (10.5%) |
| 8 A | 1 (5.3%) | 1 (5.3%) | 3 (15.8%) | 4 (21.1%) |
| 9 A | 1 (5.3%) | 2 (10.5%) | 3 (15.8%) | 4 (21.1%) |
| 10 A | 2 (10.5%) | 3 (15.8%) | 5 (26.3%) | 5 (26.3%) |
| 11 A | 4 (21.1%) | 3 (15.8%) | 5 (26.3%) | 5 (26.3%) |
| 12 A | 5 (26.3%) | 5 (26.3%) | 6 (31.6%) | 6 (31.6%) |
| 13 A | 5 (26.3%) | 5 (26.3%) | 7 (36.8%) | 8 (42.1%) |
| 14 A | 6 (31.6%) | 7 (36.8%) | 7 (36.8%) | 9 (47.4%) |
| 15 A | 7 (36.8%) | 7 (36.8%) | 7 (36.8%) | 9 (47.4%) |
| 16 A | 7 (36.8%) | 7 (36.8%) | 7 (36.8%) | 10 (52.6%) |

## Unannotated bonds

Share of measured sites whose *nearest* bonded cysteine belongs to a bond UniProt does not annotate:

| convention | sites | share |
|---|---:|---:|
| CA-CA | 42 | 32.3% |
| CA-SG | 41 | 31.5% |
| heavy-SG | 41 | 31.5% |
| heavy-heavy | 42 | 32.3% |

### How wrong is a gate keyed on UniProt — cohort level

This sizes the annotation blind spot independently of which sites happen to sit near a bond, so it transfers to anything built on `DISULFID` rather than on model geometry.

- **177** of **592** bonds formed in the models (29.9%) are **not** annotated in UniProt
- they are spread over **53** of **133** proteins (39.8%)
- the converse — UniProt asserts a bond the model does not form — is **17** bonds over **13** proteins. That direction over-vetoes rather than under-vetoes, so it is the safer error of the two.

Of the sites inside 10 A nearest-heavy-atom, **12** are constrained by an unannotated bond — i.e. a gate keyed on UniProt `DISULFID` would not even see the hazard.

## Insert size — derived from `tag_type`, not a corpus length field

| size class | n | heavy min | CA-CA min | CA-SG min |
|---|---:|---:|---:|---:|
| large_domain | 17 | 2.85 | 5.37 | 6.68 |
| ncAA_single | 16 | 2.80 | 5.29 | 6.38 |
| small_epitope | 89 | 1.33 | 3.81 | 4.94 |
| unknown | 8 | 1.35 | 3.84 | 6.13 |

A numeric length could be recovered for **89** of 130 measured sites (median **9 aa**, max **30 aa**). `ncAA_single` sites are a single unnatural amino acid put in by amber suppression — a *substitution*, not an insertion — so they are the weakest evidence here, not the strongest.

### By cargo size band

Bands rather than a single class, so a floor is not fitted on one cargo size and applied to another. **The internal arms this informs carry the full 51-aa cassette**, so the band that brackets them from above is `>=100 aa` and the band that would bracket them from below (31-99 aa) is empty — no site in this corpus carries an insert between 31 and 99 aa. The 12-30 aa band is reported because it is well-defined, not because it is the operative cargo.

**Every length here is read off a label, not measured off a peptide.** That is the weaker of the two methods and it is the one this corpus forces: `tag_length_aa` is NULL throughout, so a band assignment is only as good as the `tag_type` string. The tag-sites side derives its 19 aa as `len(LOOP_TAG_AA)` — the actual peptide — which is immune to the whole class of bug that label parsing invites, and two such bugs did surface while these bands were being built (an explicit "35 aa" losing to a canonical-table 15, and `+` treated as `/` so that a joined cassette would be filed as its smaller half). Both are fixed and unit-pinned, but the right rule is theirs: take length from the peptide, never from a label. Where a measured length exists, prefer it over anything in this table.

| band | n | CA-CA min | CA-SG min | heavy-SG min | heavy-heavy min |
|---|---:|---:|---:|---:|---:|
| single ncAA (~1 aa, a substitution) | 16 | 5.29 | 6.38 | 5.48 | 2.80 |
| epitope tag <=11 aa | 70 | 3.84 | 5.04 | 4.24 | 1.34 |
| 12-30 aa (ALFA 15, DogTag 23, 3xHA 27) | 19 | 3.81 | 4.94 | 3.54 | 1.33 |
| fusion domain >=100 aa | 17 | 5.37 | 6.68 | 4.16 | 2.85 |
| unknown | 8 | 3.84 | 6.13 | 4.87 | 1.35 |

**The 12-30 aa band is a lower bound, not a census.** It is built from `tag_site_public.tag_type`, and D1's literature rows are incomplete for ALFA — which is the cargo the internal arms actually carry. Checked against the 25 curated internal positive controls in the tag-sites worktree's `data/tag_sites/positive_controls.tsv`: of five EndoNB ALFA entries, three (ITGB5 102, TFRC 290, AXL 184) have no D1 literature row at all, one (ITGB1 101) has a row whose `tag_type` omits ALFA, and only TMEM123 appears cleanly. Both VANGL1 HA sites are missing too, so the gap is not ALFA-specific. Treat the band's n as what D1 happens to record, and the curated table as the better source for this band.

The gap is confined to the **literature** lane. The deterministic rows are well populated for the same genes (TFRC 15 sites, ITGB1 11, ITGB5 10), so this is not a statement about `tag_site_public` as a whole and should not be generalised into one — a worklist audit reading deterministic rows is, on this evidence, unaffected. The claim is narrower and sharper than "D1 is incomplete": for literature provenance, absence from D1 is not evidence of absence. Reproduced independently against the live `/v1/tag-sites/{symbol}` API by the session recalibrating `MIN_LOOP_LEN`, which agreed on all five genes.

**And its ALFA half is survivorship-filtered at source.** The curators' own note: EndoNB "reports no failures; they screened 2-3 gRNAs per gene and published only the winner, so its 5/5 success rate is survivorship-filtered." That is a *stronger* objection than the corpus-wide one at the top of this report. Cohort-wide, failures were never measured; here they were measured and withheld, so 5/5 is a selected maximum over a known-larger denominator rather than a rate.

The 12-30 aa band has **n=19** over 16 genes. It is not the cargo the arms carry, but it is the best-defined band in the table, so its sweep is given for reference:

| floor | CA-CA rejected | CA-SG rejected | heavy-SG rejected | heavy-heavy rejected |
|---|---:|---:|---:|---:|
| 4 A | 2 (10.5%) | 0 (0.0%) | 2 (10.5%) | 4 (21.1%) |
| 5 A | 2 (10.5%) | 2 (10.5%) | 3 (15.8%) | 4 (21.1%) |
| 6 A | 3 (15.8%) | 3 (15.8%) | 4 (21.1%) | 4 (21.1%) |
| 7 A | 4 (21.1%) | 3 (15.8%) | 4 (21.1%) | 4 (21.1%) |
| 8 A | 4 (21.1%) | 4 (21.1%) | 4 (21.1%) | 4 (21.1%) |
| 9 A | 4 (21.1%) | 4 (21.1%) | 4 (21.1%) | 4 (21.1%) |
| 10 A | 4 (21.1%) | 4 (21.1%) | 5 (26.3%) | 5 (26.3%) |
| 11 A | 5 (26.3%) | 4 (21.1%) | 5 (26.3%) | 6 (31.6%) |
| 12 A | 5 (26.3%) | 5 (26.3%) | 5 (26.3%) | 6 (31.6%) |
| 13 A | 5 (26.3%) | 5 (26.3%) | 6 (31.6%) | 9 (47.4%) |
| 14 A | 5 (26.3%) | 5 (26.3%) | 8 (42.1%) | 10 (52.6%) |
| 15 A | 8 (42.1%) | 8 (42.1%) | 9 (47.4%) | 10 (52.6%) |
| 16 A | 8 (42.1%) | 8 (42.1%) | 9 (47.4%) | 11 (57.9%) |

### What the corpus does and does not license

**17** measured sites took a fusion domain of ~100 aa or more (GFP/pHluorin ~238 aa, HaloTag ~297 aa, SNAP-tag ~182 aa, GLuc ~185 aa). These are the only sites in the corpus that bear on an insert larger than the 51-aa cassette at all, and every one of them is *bigger* than the cassette, so they are the right comparison if any exists.

| convention | minimum over large-domain sites | gene | site | seq sep to that Cys |
|---|---:|---|---|---:|
| CA-CA | **5.37 A** | CRB2 | D1096 | 2 |
| CA-SG | **6.68 A** | CRB2 | D1096 | 2 |
| heavy-SG | **4.16 A** | CRB2 | D1096 | 2 |
| heavy-heavy | **2.85 A** | CRB2 | D1096 | 2 |

The minimum in every convention is the same site, and it is **sequence-adjacent** — so read it as "a GFP/SNAP/HaloTag-class insert went in two residues from a bonded cysteine and the protein still reached the surface and still worked", not as a distance. Over the 16 large-domain sites that are more than 2 residues away, the minima are CA-CA 7.37 A, CA-SG 7.65 A, heavy-SG 5.38 A, heavy-heavy 4.15 A.

At n=17 this is thin — it is 17 sites over 14 genes, with no negative set, so it cannot fix a cassette floor. It does mean the cassette question is not completely unaddressed by this corpus, and it bounds a large-insert floor from above the same way the whole cohort bounds the small-tag one.

## Position evidence

`inferred` positions are not read off the paper, so a minimum computed over them is less trustworthy than the number itself suggests.

| position_evidence | n | heavy min | CA-CA min | CA-SG min |
|---|---:|---:|---:|---:|
| inferred | 38 | 1.33 | 3.81 | 4.99 |
| topology_derived | 2 | 6.07 | 9.18 | 8.25 |
| validated | 90 | 1.34 | 3.84 | 4.94 |

