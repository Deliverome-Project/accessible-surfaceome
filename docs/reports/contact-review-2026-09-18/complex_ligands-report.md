> Review history: this is an initial proposal or independent critique, not the final accepted rule set. See the consolidated report for accepted corrections and final counts.

# Eight-target complex-ligand contact review

Review date: 2026-09-18. Input release: `contacts-ba6680878403e6980464`. This is a proposed curation, not a production change. All original residue positions and labels remain untouched. The companion JSON contains conservative rules using the existing matcher schema. No D1 writes, deployments, repository edits, or model calls were performed.

## Coverage and count interpretation

All 2,189 observations were inventoried across the eight targets, including unnamed accession-level evidence; the detailed named-partner review covers every row in the supplied extracellular lists. Public PDBe summary and entity metadata were retrieved for 247 selected deposits (all named-partner deposits except repeated bulk assembly-subunit contacts; representative assembly deposits are included). PDB 2DTG is obsolete; 4ZXB is its authoritative replacement. Cache files are in `complex_ligands/`. This is not an atom-by-atom validation of every interface or exhaustive naming of the unnamed TCR/viral peptide accessions.

“Cleaned” below means estimated distinct displayed labels from **named, explicitly extracellular observations** after proposed rules, retaining unresolved labels. It is not a count of unique molecular species or native extracellular ligands. HLA peptide families remain unresolved, so these counts must not be marketed as clean biological denominators. Correctly splitting engineered constructs can increase counts.

| Target stable ID | Original all labels | Original EC labels | Observations | Estimated labels after rules |
|---|---:|---:|---:|---:|
| APP P05067 | 33 | 30 | 159 | 27 |
| HLA-DRA P01903 | 23 | 23 | 312 | 23 |
| HLA-A P04439 | 19 | 19 | 792 | 16 |
| HLA-DRB1 P01911 | 13 | 13 | 227 | 13 |
| HLA-B P01889 | 8 | 8 | 447 | 8 |
| BACE1 P56817 | 16 | 16 | 24 | 15 |
| INSR P06213 | 10 | 8 | 143 | 14 |
| ITGAV P06756 | 11 | 11 | 85 | 14 |

## Decisions requiring richer schema

1. **HLA needs target allele + deposited target entity/chain + peptide sequence + chemical modifications + peptide register + TCR clonotype.** A stable UniProt accession alone cannot distinguish these. Many “protein partners” are 9–20-residue peptides, and the same source protein contributes different peptides. Canonical sequence strings normalize modified amino acids; retain PDBe `pdb_sequence`/CCD modifications. Do not assign all peptides `endogenous_small` just because the source accession is human. Synthetic substitutions, citrullination, phosphorylation, tumor mutations and tethering matter. Current proposed rules intentionally leave these source-protein families unclassified rather than falsely resolving them.
2. **Target fragment versus intact surface protein is essential.** APP residues in amyloid-beta, APP Kunitz inhibitor, C99 and whole APP have different physical settings. HLA-A peptide presentation by HLA-DR creates reciprocal “HLA-DRA binds HLA-A” records despite the target entity being only an HLA-A-derived peptide. The precise reciprocal 1AQD/4OV5 observations are excluded from the intact-HLA-A overview, not discarded.
3. **Topology is not physiological compartment.** CALR/PDIA3 in 7QPD are ER peptide-loading machinery. The HLA domain later becomes extracellular, but this experiment is intracellular/lumenal. Those exact observations are excluded from the native surface overview. CALR in 2CLR is instead a presented signal peptide and remains in evidence.
4. **Antibody lineage versus construct identity is separate from category.** Murine m266 is not humanized solanezumab; chimeric aducanumab is not the complete therapeutic. 3D6/bapineuzumab is an unresolved compound label with mixed constructs, not a safe alias merge. Arm-matching cannot establish that a full bispecific drug was deposited.
5. **A ligand accession may represent only one chain.** INSR insulin A/B chains can map to different accessions/species. Chemical conjugates can have native-looking amino-acid sequences. A source-family label must not erase deposited analogue names. Rules narrowly split unequivocal named analogue deposits; species/processing ambiguities remain unclassified.
6. **Role and category are orthogonal.** Integrin beta chains are heterodimer partners; latent TGF-beta contact is with LAP/proregion; enzymes may bind an APP-derived substrate. `receptor_partner` is the best available broad category for receptor assemblies but cannot encode co-receptor versus assembly subunit versus chaperone.

## APP: fragment biology and therapeutic arms

Aducanumab, crenezumab, gantenerumab, solanezumab and bapineuzumab labels refer to anti-amyloid-beta recognition, not demonstrated access to intact cell-surface APP. APP770 Aβ1 maps to residue 672. The extracellular gate excludes ponezumab’s membrane-spanning precursor footprint, even though released Aβ40 is soluble. This illustrates why precursor topology alone cannot answer fragment accessibility. Preserve both coordinate systems.

The primary study [Arndt et al.](https://pmc.ncbi.nlm.nih.gov/articles/PMC5913127/) distinguishes chimeric mouse constant-region reagents and parental murine m266/3D6 variable regions. Consequently `(ch)aducanumab` and its semicolon variant merge with each other only; `(ch)gantenerumab` remains separate from gantenerumab. `m266, solanezumab` gets a murine-precursor label. **Do not use raw IEDB ID 1173 in that rule**: it is also used by the distinct solanezumab structural record. No all-PDB “3D6 = bapineuzumab” rule is justified: [4HIX](https://www.rcsb.org/structure/4HIX) explicitly contains humanized 3D6, while other IEDB records are murine-parent experiments. The source compound label stays uncertain.

The local `therapeutic_aacdb_evidence.tsv.gz` verifies exact VH/VL arm matches: aducanumab 6CO3 H/L; crenezumab 5VZY H/L; gantenerumab **and trontinemab** both match 5CSZ A/B and H/L; ponezumab 3U0T B/A and D/C. [5CSZ](https://www.rcsb.org/structure/5CSZ) is a gantenerumab Fab–Aβ complex. Trontinemab must remain a therapeutic catalogue/arm link; do not say the complete trontinemab bispecific was crystallized, and do not merge the therapeutic names merely because their matching arms coincide.

[5NX1](https://www.rcsb.org/structure/5NX1) and [5NX3](https://www.rcsb.org/structure/5NX3) contain engineered APP Kunitz inhibitor constructs, including split 25-/56-residue and intact 81-residue entities. Generic `peptide` in 5NX1 is not an independently identified ligand: narrowly excluded as same-target construct evidence. KLK6 contacts remain visible with engineered-APPI qualification and unclassified physiological status. [6HGA](https://www.rcsb.org/structure/6HGA) is IL17RC bearing an APP tag with 6E10-A5 Fab: excluded from the native APP overview, retained as tag-binding evidence. ACE/IDE act on Aβ fragments; MMP2 [3AYU](https://www.rcsb.org/structure/3AYU) uses an active-site mutant and APP-derived decapeptide inhibitor. These do not establish intact precursor binding.

HLA-DRA [31VO](https://www.rcsb.org/structure/31VO) presents Aβ1–15, with the peptide tethered to DR beta. NCSTN 6IYC/8X52/8X54 is gamma-secretase processing context; PSEN1 and FPR2 remain in membrane-spanning evidence rather than named EC counts. No blanket physiological claim or receptor-partner relabel is proposed for these.

## HLA-DRA and HLA-DRB1

HLA-DRB1, DRB3 and DRB5 remain separate assembly partners; their alleles must also remain available. CD4 deposits 3S4S/3S5L use mutant CD4; category is co-receptor context, not proof of wild-type affinity. HLA-DM (4FQX) is peptide exchange machinery, while LAG3 (9BF9) is a receptor partner.

All APP, CAMP, CD74, EEF1A1, ENO1, FGB, HLA-A, insulin, ITGB3, MBP, PMEL, RO60, TNC, TPBG and VIM source labels in these named lists refer to presented peptide or tethered-peptide contexts, not full-length soluble protein ligands. In particular CD74 is CLIP, and insulin 4Y19 is a proinsulin C-peptide-region sequence, despite the deposited entity name “Insulin A chain.” Preserve sequence rather than trusting the entity name. No whole-protein alias is proposed. The generic 5NI9 `peptide` is safely identified as ENO1 `KRIAKAVNEKSCNCL` and merged only with the ENO1 observation in that PDB; other ENO1 sequences remain separate unresolved family evidence. The unchanged HLA-DRA count reflects one duplicate removed and the 5NI9 sequence distinguished from other ENO1 peptides.

CAMP, FGB, TNC, VIM and ENO1 include citrullinated material. For example [6BIX](https://www.rcsb.org/structure/6BIX), [6ATZ](https://www.rcsb.org/structure/6ATZ), [9NIH](https://www.rcsb.org/structure/9NIH) and [8TRL](https://www.rcsb.org/structure/8TRL) expressly name such contexts. Human origin does not justify an unconditional endogenous category. All modifications require retained chemical identity. [1AQD](https://www.rcsb.org/structure/1AQD) and [4OV5](https://www.rcsb.org/structure/4OV5) have different HLA-A peptide sequences; these must never merge as one “HLA-A ligand.”

## HLA-A and HLA-B

B2M is an assembly partner, not a soluble ligand. CD8A, KIR2DS2, LILRB1 and KIR3DL1 are receptor/co-receptor partners with allele/peptide constraints. [V2 7STF](https://www.rcsb.org/structure/7STF) recognizes KRAS G12V/HLA-A*03:01; [2Q1 6UJ9](https://www.rcsb.org/structure/6UJ9) recognizes IDH2 R140Q/HLA-B*07:02. They are research peptide-HLA antibodies, not pan-HLA drugs.

HLA-A named ALK, ARHGAP45, CTNNB1, DCT, ERBB2, insulin, PLP1, PMEL, SLCO2A1 and TYR are peptide-source families. CALR mixes a peptide in 2CLR and whole chaperone in 7QPD. HLA-B ALK, CACNA1D, CTSA, GCGR and VIPR1 are peptide-source families. CTNNB1 includes phosphopeptides; TYR 7RK7 is N371D; insulin 3UTQ is signal peptide `ALWGPDPAAA`, not mature insulin. No family-wide physiological category or cross-sequence alias is assigned.

Unnamed observations include many TCR constant/germline accessions, viral antigens and peptide-source accessions. **Do not rename all P01848/P01850-type chains “TCR” and collapse them**: the paired variable sequence/clonotype and peptide-HLA restriction are the relevant identities. This review inventories but does not resolve those additional unnamed clonotypes.

## BACE1

YW412.8.31 and the IEDB `anti-BACE1 (Yw412.8.31), Yw412.8.31` label describe the same research antibody; merge as `tool` with [3R1G](https://www.rcsb.org/structure/3R1G) provenance. QKA is a CCD chemical, [compound 32 in 6UWP](https://www.rcsb.org/structure/6UWP), not a peptide sequence. Every other named EC ligand is a synthetic inhibitor, with CCD identity preserved. PDB verifies concise aliases LY2886721 (3YS), LY2811376 (4B2), CNP520 (BUH), and AM-6494 (P6J). The first three are investigated therapeutic candidates, **not an approval statement**; other molecules are conservatively tools, without inventing drug names. [CNP520 primary study](https://doi.org/10.15252/emmm.201809316) establishes clinical investigation. No synthetic inhibitor is endogenous. BACE1 is an ectodomain/lumenal protease: these structures do not by themselves demonstrate surface exposure in vivo.

## INSR

Separate native insulin from [D-Pro-B26]-DTI-NH2 (3W12/3W13), SCI-b (7KD6), venom-hybrid insulin (7MQO/7MQR/7MQS), IRPA-3 and IRPA-9 (7MD4/7MD5), and Ins-AC-S2 (9PUW/9PVO). The last two classes have chemical/linked construct identity not recoverable from a “human insulin” accession alone. PDB-specific tool labels are proposed, without merging their different identities. [7U6E](https://www.rcsb.org/structure/7U6E) includes both native insulin chains and a separate non-insulin agonist IM462; its title alone is **not** grounds to rename the insulin observations IM462.

6CE7/6CE9/6CEB deposit a human-mapped A chain plus a B chain ending Ala30, mapped to Ovis aries P01318. A-chain matches cannot establish a native human hormone; these are separated as an unclassified Ala-B30 insulin context. 7BW7/7BW8/7BWA deposit a 74-residue “insulin fusion” with precursor-like sequence. Processing state cannot be inferred safely from the accession and paper title; separate it with an uncertainty label. 8YYS deposits a 110-residue precursor sequence, another warning that deposited sequence metadata does not prove an uncleaved precursor was the bound species; no automatic proinsulin relabel is made.

F8WCM5 `INS-IGF2` in 7YQ3/4/5 and 8GUY is deposited as a 25-residue B-chain sequence `NQHLCGSHLVEALYLVCGERGFFYT` alongside insulin A chain. This is not evidence that a distinct INS-IGF2 readthrough hormone was present. PDB-specific insulin alias rules remove that false distinct ligand while retaining the source mapping and sequence uncertainty.

83-14 and 83-7 remain separate tools. Alias merging of 83-14 exposes a source inconsistency: AACDB 4ZXB positions ~238–309 versus some IEDB 83-14-labelled contacts ~501–733, near the broader 83-7 footprint. This could be source chain/name assignment, assay-specific mapping, or another construct issue. **No residue reassignment or clone swap is justified here.** IGF1R is a hybrid receptor partner; IGF-I/IGF-II are separate endogenous protein ligands. IRS1 and Irfin-1 are cytoplasmic and remain outside EC counts.

## ITGAV

ITGB1, ITGB3, ITGB6 and ITGB8 are four distinct integrin beta assembly partners. They are not soluble ligands. 17E6, C6D4 and the engineered C6-RGD3 remain separate research Fabs. [A1A6H](https://www.rcsb.org/ligand/A1A6H) is compound 30, a nonpolymer small molecule in 9CZD; the same structure also contains 17E6, which must not be confused with this ligand code.

FN1 cannot be blanket-classified as native fibronectin. 4MMX has isolated 10FN3, 4MMY and 4MMZ different engineered loops, and 6NAJ the Hr10 variant. Four construct labels preserve the differences; 4MMX is conservatively unclassified because an isolated deposited fragment is not a demonstration of intact native fibronectin binding. TGFB1/TGFB3 contacts concern LAP/latent-proprotein regions, including peptide 4UM9 and large latent assemblies 8VS6/8VSD. Mature active TGF-beta must not be substituted as the partner identity. No beta-subunit or TGF-beta isoform merges are proposed.

## Matcher validation and integration cautions

The current matcher strips terminal Fab/Fv/VHH and one terminal parenthetical, then matches either raw partner or partner_label, with optional PDB restriction. There is no source/assay/entity/chain discriminator, and later rules overwrite earlier fields. The proposed 99 rules have no multiple-rule collisions across the supplied observations. They deliberately avoid raw numeric IEDB IDs for shared therapeutic/precursor cases. `exclude_from_overview` is sticky in the current code: false rules do not reset a previous exclusion. Do not rely on ordering to undo quarantine.

Most rules only categorize or add context. They cannot fix the missing allele, peptide or target-fragment schema. Canonical labels must not replace source identifiers. Apply rules to individual observations before aggregation; otherwise a single representative PDB can incorrectly reclassify an entire mixed family. HLA peptide rows left unclassified below are **reviewed and intentionally unresolved**, not skipped.

## Complete named extracellular row checklist

Each original EC row is listed, even if its source label is deliberately left uncertain. A representative PDB is a locator, not a claim that all observations have that construct. Per-PDB variants are detailed above and below.


### APP — P05067

| Original label | Raw key | Representative evidence | Proposed disposition |
|---|---|---|---|
| Aducanumab | Aducanumab | [6CO3](https://www.rcsb.org/structure/6CO3) | Retain therapeutic/arm provenance; Aβ epitope does not prove intact APP accessibility. |
| bapineuzumab | 598 | [assay](https://www.iedb.org/assay/2113220) | Retain therapeutic/arm provenance; Aβ epitope does not prove intact APP accessibility. |
| Crenezumab | Crenezumab | [5VZY](https://www.rcsb.org/structure/5VZY) | Retain therapeutic/arm provenance; Aβ epitope does not prove intact APP accessibility. |
| gantenerumab | 326 | [assay](https://www.iedb.org/assay/2482115) | Retain therapeutic/arm provenance; Aβ epitope does not prove intact APP accessibility. |
| solanezumab | 1173 | [4XXD](https://www.rcsb.org/structure/4XXD) | Retain therapeutic/arm provenance; Aβ epitope does not prove intact APP accessibility. |
| Trontinemab | Trontinemab | [5CSZ](https://www.rcsb.org/structure/5CSZ) | Retain therapeutic/arm provenance; Aβ epitope does not prove intact APP accessibility. |
| (ch)aducanumab | 207358 | [assay](https://www.iedb.org/assay/3925244) | Chimeric aducanumab; tool |
| (ch)aducanumab;chaducanumab | 207358 | [6CO3](https://www.rcsb.org/structure/6CO3) | Chimeric aducanumab; tool |
| (ch)gantenerumab | 326 | [assay](https://www.iedb.org/assay/3925268) | Chimeric gantenerumab; tool |
| 10D5 | 918 | [3IFO](https://www.rcsb.org/structure/3IFO) | 10D5; tool |
| 12A11 | 923 | [3IFL](https://www.rcsb.org/structure/3IFL) | 12A11; tool |
| 12B4 | 1068 | [3IFP](https://www.rcsb.org/structure/3IFP) | 12B4; tool |
| 3D6, bapineuzumab | 425 | [assay](https://www.iedb.org/assay/1973826) | Mixed murine/humanized source label unresolved; no alias merge. |
| 6E10-A5 | 197682 | [6HGA](https://www.rcsb.org/structure/6HGA) | Quarantine this PDB from overview; 6E10-A5 — APP-tag Fab; tool |
| ACE | P12821 | [5AM8](https://www.rcsb.org/structure/5AM8) | ACE; endogenous_large |
| c#17 | 18374 | [5MY4](https://www.rcsb.org/structure/5MY4) | c#17; tool |
| c#6 | 18373 | [5MYO](https://www.rcsb.org/structure/5MYO) | c#6; tool |
| C706 | 297 | [assay](https://www.iedb.org/assay/1844808) | C706; tool |
| HLA-DRA | P01903 | [31VO](https://www.rcsb.org/structure/31VO) | Retain unclassified: presented Aβ or gamma-secretase fragment context, not intact-APP ligand evidence. |
| IC16, scFv-IC16 | 254 | [assay](https://www.iedb.org/assay/1975857) | IC16, scFv-IC16; tool |
| IDE | P14735 | [2G47](https://www.rcsb.org/structure/2G47) | IDE; endogenous_large |
| KLK6 | Q92876 | [5NX1](https://www.rcsb.org/structure/5NX1) | KLK6 — engineered APPI complex; unclassified |
| KW1 | 395 | [assay](https://www.iedb.org/assay/1959865) | KW1; tool |
| m266, solanezumab | 1173 | [assay](https://www.iedb.org/assay/3925287) | m266 — murine solanezumab precursor; tool |
| MMP2 | P08253 | [3AYU](https://www.rcsb.org/structure/3AYU) | MMP2; endogenous_large |
| NCSTN | Q92542 | [6IYC](https://www.rcsb.org/structure/6IYC) | Retain unclassified: presented Aβ or gamma-secretase fragment context, not intact-APP ligand evidence. |
| peptide | peptide | [5NX1](https://www.rcsb.org/structure/5NX1) | Quarantine this PDB from overview; Engineered APPI fragment — same-target construct contact; unclassified |
| PFA1 | 970 | [2IPU](https://www.rcsb.org/structure/2IPU) | PFA1; tool |
| PFA2 | 921 | [2R0W](https://www.rcsb.org/structure/2R0W) | PFA2; tool |
| WO2 | 440 | [assay](https://www.iedb.org/assay/1979576) | WO2; tool |

### HLA-DRA — P01903

| Original label | Raw key | Representative evidence | Proposed disposition |
|---|---|---|---|
| APP | P05067 | [31VO](https://www.rcsb.org/structure/31VO) | Presented-peptide/source-family identity remains unclassified; retain sequence, modifications and allele. See entity appendix. |
| CAMP | P49913 | [6BIX](https://www.rcsb.org/structure/6BIX) | Presented-peptide/source-family identity remains unclassified; retain sequence, modifications and allele. See entity appendix. |
| CD4 | P01730 | [3S5L](https://www.rcsb.org/structure/3S5L) | CD4; receptor_partner |
| CD74 | P04233 | [4AH2](https://www.rcsb.org/structure/4AH2) | Presented-peptide/source-family identity remains unclassified; retain sequence, modifications and allele. See entity appendix. |
| EEF1A1 | P68104 | [3C5J](https://www.rcsb.org/structure/3C5J) | Presented-peptide/source-family identity remains unclassified; retain sequence, modifications and allele. See entity appendix. |
| ENO1 | P06733 | [5NI9](https://www.rcsb.org/structure/5NI9) | ENO1 peptide KRIAKAVNEKSCNCL — 5NI9; unclassified |
| FGB | P02675 | [6ATZ](https://www.rcsb.org/structure/6ATZ) | Presented-peptide/source-family identity remains unclassified; retain sequence, modifications and allele. See entity appendix. |
| HLA-A | P04439 | [1AQD](https://www.rcsb.org/structure/1AQD) | Presented-peptide/source-family identity remains unclassified; retain sequence, modifications and allele. See entity appendix. |
| HLA-DMA | P28067 | [4FQX](https://www.rcsb.org/structure/4FQX) | HLA-DMA; receptor_partner |
| HLA-DMB | P28068 | [4FQX](https://www.rcsb.org/structure/4FQX) | HLA-DMB; receptor_partner |
| HLA-DRB1 | P01911 | [1DLH](https://www.rcsb.org/structure/1DLH) | HLA-DRB1; receptor_partner |
| HLA-DRB3 | P79483 | [2Q6W](https://www.rcsb.org/structure/2Q6W) | HLA-DRB3; receptor_partner |
| HLA-DRB5 | Q30154 | [1FV1](https://www.rcsb.org/structure/1FV1) | HLA-DRB5; receptor_partner |
| insulin | P01308 | [4Y19](https://www.rcsb.org/structure/4Y19) | Presented-peptide/source-family identity remains unclassified; retain sequence, modifications and allele. See entity appendix. |
| ITGB3 | P05106 | [2Q6W](https://www.rcsb.org/structure/2Q6W) | Presented-peptide/source-family identity remains unclassified; retain sequence, modifications and allele. See entity appendix. |
| LAG3 | P18627 | [9BF9](https://www.rcsb.org/structure/9BF9) | LAG3; receptor_partner |
| MBP | P02686 | [1FV1](https://www.rcsb.org/structure/1FV1) | Presented-peptide/source-family identity remains unclassified; retain sequence, modifications and allele. See entity appendix. |
| peptide | peptide | [5NI9](https://www.rcsb.org/structure/5NI9) | ENO1 peptide KRIAKAVNEKSCNCL — 5NI9; unclassified |
| PMEL | P40967 | [4IS6](https://www.rcsb.org/structure/4IS6) | Presented-peptide/source-family identity remains unclassified; retain sequence, modifications and allele. See entity appendix. |
| RO60 | P10155 | [9YZ3](https://www.rcsb.org/structure/9YZ3) | Presented-peptide/source-family identity remains unclassified; retain sequence, modifications and allele. See entity appendix. |
| TNC | P24821 | [9NIH](https://www.rcsb.org/structure/9NIH) | Presented-peptide/source-family identity remains unclassified; retain sequence, modifications and allele. See entity appendix. |
| TPBG | Q13641 | [6HBY](https://www.rcsb.org/structure/6HBY) | Presented-peptide/source-family identity remains unclassified; retain sequence, modifications and allele. See entity appendix. |
| VIM | P08670 | [6ATF](https://www.rcsb.org/structure/6ATF) | Presented-peptide/source-family identity remains unclassified; retain sequence, modifications and allele. See entity appendix. |

### HLA-A — P04439

| Original label | Raw key | Representative evidence | Proposed disposition |
|---|---|---|---|
| ALK | Q9UM73 | [6AT9](https://www.rcsb.org/structure/6AT9) | Presented-peptide/source-family identity remains unclassified; retain sequence, modifications and allele. See entity appendix. |
| ARHGAP45 | Q92619 | [3D25](https://www.rcsb.org/structure/3D25) | Presented-peptide/source-family identity remains unclassified; retain sequence, modifications and allele. See entity appendix. |
| B2M | P61769 | [1LP9](https://www.rcsb.org/structure/1LP9) | B2M; receptor_partner |
| CALR | P27797 | [2CLR](https://www.rcsb.org/structure/2CLR) | Presented-peptide/source-family identity remains unclassified; retain sequence, modifications and allele. See entity appendix. |
| CD8A | P01732 | [1AKJ](https://www.rcsb.org/structure/1AKJ) | CD8A; receptor_partner |
| CTNNB1 | P35222 | [3FQN](https://www.rcsb.org/structure/3FQN) | Presented-peptide/source-family identity remains unclassified; retain sequence, modifications and allele. See entity appendix. |
| DCT | P40126 | [4HX1](https://www.rcsb.org/structure/4HX1) | Presented-peptide/source-family identity remains unclassified; retain sequence, modifications and allele. See entity appendix. |
| ERBB2 | P04626 | [1QR1](https://www.rcsb.org/structure/1QR1) | Presented-peptide/source-family identity remains unclassified; retain sequence, modifications and allele. See entity appendix. |
| HLA-DRA | P01903 | [4OV5](https://www.rcsb.org/structure/4OV5) | Quarantine this PDB from overview; HLA-DRA — HLA-A-derived peptide presentation; unclassified |
| HLA-DRB1 | P01911 | [1AQD](https://www.rcsb.org/structure/1AQD) | Quarantine this PDB from overview; HLA-DRB1 — HLA-A-derived peptide presentation; unclassified |
| insulin | P01308 | [3UTQ](https://www.rcsb.org/structure/3UTQ) | Presented-peptide/source-family identity remains unclassified; retain sequence, modifications and allele. See entity appendix. |
| KIR2DS2 | P43631 | [4N8V](https://www.rcsb.org/structure/4N8V) | KIR2DS2; receptor_partner |
| LILRB1 | Q8NHL6 | [6EWC](https://www.rcsb.org/structure/6EWC) | LILRB1; receptor_partner |
| PDIA3 | P30101 | [7QPD](https://www.rcsb.org/structure/7QPD) | Quarantine this PDB from overview; PDIA3 — ER peptide-loading complex; receptor_partner |
| PLP1 | P60201 | [2XPG](https://www.rcsb.org/structure/2XPG) | Presented-peptide/source-family identity remains unclassified; retain sequence, modifications and allele. See entity appendix. |
| PMEL | P40967 | [7PHR](https://www.rcsb.org/structure/7PHR) | Presented-peptide/source-family identity remains unclassified; retain sequence, modifications and allele. See entity appendix. |
| SLCO2A1 | Q92959 | [3MRR](https://www.rcsb.org/structure/3MRR) | Presented-peptide/source-family identity remains unclassified; retain sequence, modifications and allele. See entity appendix. |
| TYR | P14679 | [7RK7](https://www.rcsb.org/structure/7RK7) | Presented-peptide/source-family identity remains unclassified; retain sequence, modifications and allele. See entity appendix. |
| V2 IgG | V2 IgG Fab | [7STF](https://www.rcsb.org/structure/7STF) | V2 IgG; tool |

### HLA-DRB1 — P01911

| Original label | Raw key | Representative evidence | Proposed disposition |
|---|---|---|---|
| CAMP | P49913 | [6BIX](https://www.rcsb.org/structure/6BIX) | Presented-peptide/source-family identity remains unclassified; retain sequence, modifications and allele. See entity appendix. |
| CD4 | P01730 | [3S4S](https://www.rcsb.org/structure/3S4S) | CD4; receptor_partner |
| CD74 | P04233 | [1A6A](https://www.rcsb.org/structure/1A6A) | Presented-peptide/source-family identity remains unclassified; retain sequence, modifications and allele. See entity appendix. |
| ENO1 | P06733 | [8TRL](https://www.rcsb.org/structure/8TRL) | Presented-peptide/source-family identity remains unclassified; retain sequence, modifications and allele. See entity appendix. |
| FGB | P02675 | [6BIL](https://www.rcsb.org/structure/6BIL) | Presented-peptide/source-family identity remains unclassified; retain sequence, modifications and allele. See entity appendix. |
| HLA-A | P04439 | [1AQD](https://www.rcsb.org/structure/1AQD) | Presented-peptide/source-family identity remains unclassified; retain sequence, modifications and allele. See entity appendix. |
| HLA-DMB | P28068 | [4FQX](https://www.rcsb.org/structure/4FQX) | HLA-DMB; receptor_partner |
| HLA-DRA | P01903 | [1DLH](https://www.rcsb.org/structure/1DLH) | HLA-DRA; receptor_partner |
| insulin | P01308 | [4Y19](https://www.rcsb.org/structure/4Y19) | Presented-peptide/source-family identity remains unclassified; retain sequence, modifications and allele. See entity appendix. |
| MBP | P02686 | [1YMM](https://www.rcsb.org/structure/1YMM) | Presented-peptide/source-family identity remains unclassified; retain sequence, modifications and allele. See entity appendix. |
| PMEL | P40967 | [4IS6](https://www.rcsb.org/structure/4IS6) | Presented-peptide/source-family identity remains unclassified; retain sequence, modifications and allele. See entity appendix. |
| TPBG | Q13641 | [6HBY](https://www.rcsb.org/structure/6HBY) | Presented-peptide/source-family identity remains unclassified; retain sequence, modifications and allele. See entity appendix. |
| VIM | P08670 | [4MDJ](https://www.rcsb.org/structure/4MDJ) | Presented-peptide/source-family identity remains unclassified; retain sequence, modifications and allele. See entity appendix. |

### HLA-B — P01889

| Original label | Raw key | Representative evidence | Proposed disposition |
|---|---|---|---|
| 2Q1 | 2Q1 Fab | [6UJ9](https://www.rcsb.org/structure/6UJ9) | 2Q1; tool |
| ALK | Q9UM73 | [5VZ5](https://www.rcsb.org/structure/5VZ5) | Presented-peptide/source-family identity remains unclassified; retain sequence, modifications and allele. See entity appendix. |
| B2M | P61769 | [3FFC](https://www.rcsb.org/structure/3FFC) | B2M; receptor_partner |
| CACNA1D | Q01668 | [3LV3](https://www.rcsb.org/structure/3LV3) | Presented-peptide/source-family identity remains unclassified; retain sequence, modifications and allele. See entity appendix. |
| CTSA | P10619 | [3BP4](https://www.rcsb.org/structure/3BP4) | Presented-peptide/source-family identity remains unclassified; retain sequence, modifications and allele. See entity appendix. |
| GCGR | P47871 | [3CZF](https://www.rcsb.org/structure/3CZF) | Presented-peptide/source-family identity remains unclassified; retain sequence, modifications and allele. See entity appendix. |
| KIR3DL1 | P43629 | [3VH8](https://www.rcsb.org/structure/3VH8) | KIR3DL1; receptor_partner |
| VIPR1 | P32241 | [5DEF](https://www.rcsb.org/structure/5DEF) | Presented-peptide/source-family identity remains unclassified; retain sequence, modifications and allele. See entity appendix. |

### BACE1 — P56817

| Original label | Raw key | Representative evidence | Proposed disposition |
|---|---|---|---|
| (1R,3S,4S,5R)-3-(4-amino-3-fluoro-5-{[(2R)-1,1,1-trifluoro-3-methoxypropan-2-yl]oxy}benzyl)-5-[(3-tert-butylbenzyl)amino]tetrahydro-2H-thiopyran-4-ol 1-oxide | CCD:1YT | [4LXK](https://www.rcsb.org/structure/4LXK) | BACE1 inhibitor — CCD 1YT; tool |
| (2E,4aR,7aS)-7a-(2,4-difluorophenyl)-6-(5-fluoro-4-methoxy-6-methylpyrimidin-2-yl)-2-imino-3-methyloctahydro-4H-pyrrolo[3,4-d]pyrimidin-4-one | CCD:60X | [5HE7](https://www.rcsb.org/structure/5HE7) | BACE1 inhibitor — CCD 60X; tool |
| (2R)-N-{(2S,3R)-4-{[(4'S)-6'-(2,2-dimethylpropyl)-3',4'-dihydrospiro[cyclobutane-1,2'-pyrano[2,3-b]pyridin]-4'-yl]amino}-3-hydroxy-1-[3-(1,3-thiazol-2-yl)phenyl]butan-2-yl}-2-methoxypropanamide | CCD:0K9 | [4DI2](https://www.rcsb.org/structure/4DI2) | BACE1 inhibitor — CCD 0K9; tool |
| (2Z,6S)-6-{3-chloro-5-[5-(prop-1-yn-1-yl)pyridin-3-yl]thiophen-2-yl}-2-imino-3,6-dimethyltetrahydropyrimidin-4(1H)-one | CCD:0V6 | [4FRS](https://www.rcsb.org/structure/4FRS) | BACE1 inhibitor — CCD 0V6; tool |
| (4S)-4-[2,4-difluoro-5-(pyrimidin-5-yl)phenyl]-4-methyl-5,6-dihydro-4H-1,3-thiazin-2-amine | CCD:4B2 | [4YBI](https://www.rcsb.org/structure/4YBI) | LY2811376; therapeutic |
| (5S)-7-(2-fluoropyridin-3-yl)-3-[(3-methyloxetan-3-yl)ethynyl]spiro[chromeno[2,3-b]pyridine-5,4'-[1,3]oxazol]-2'-amine | CCD:3LL | [4RCD](https://www.rcsb.org/structure/4RCD) | BACE1 inhibitor — CCD 3LL; tool |
| ~{N}-[6-[(3~{R},6~{R})-5-azanyl-3,6-dimethyl-6-(trifluoromethyl)-2~{H}-1,4-oxazin-3-yl]-5-fluoranyl-pyridin-2-yl]-3-chloranyl-5-(trifluoromethyl)pyridine-2-carboxamide | CCD:BUH | [6EQM](https://www.rcsb.org/structure/6EQM) | CNP520; therapeutic |
| anti-BACE1 (Yw412.8.31), Yw412.8.31 | 283 | [assay](https://www.iedb.org/assay/1845942) | YW412.8.31; tool |
| N-[(1S,2R)-1-BENZYL-3-(CYCLOPROPYLAMINO)-2-HYDROXYPROPYL]-5-[METHYL(METHYLSULFONYL)AMINO]-N'-[(1R)-1-PHENYLETHYL]ISOPHTHALAMIDE | CCD:5HA | [2B8L](https://www.rcsb.org/structure/2B8L) | BACE1 inhibitor — CCD 5HA; tool |
| N-[3-[(4S)-2-azanyl-4-methyl-5,6-dihydro-1,3-thiazin-4-yl]-4-fluoranyl-phenyl]-5-chloranyl-pyridine-2-carboxamide | CCD:C6U | [6JSG](https://www.rcsb.org/structure/6JSG) | BACE1 inhibitor — CCD C6U; tool |
| N-{3-[(1S,5S,6S)-3-amino-1-(methoxymethyl)-5-methyl-2-thia-4-azabicyclo[4.1.0]hept-3-en-5-yl]-4,5-difluorophenyl}-5-[(prop-2-yn-1-yl)oxy]pyrazine-2-carboxamide | CCD:P6J | [6PZ4](https://www.rcsb.org/structure/6PZ4) | AM-6494; tool |
| N-{3-[(4aS,7aS)-2-amino-4a,5-dihydro-4H-furo[3,4-d][1,3]thiazin-7a(7H)-yl]-4-fluorophenyl}-5-fluoropyridine-2-carboxamide | CCD:3YS | [4X7I](https://www.rcsb.org/structure/4X7I) | LY2886721; therapeutic |
| N-{3-[(4S,6S)-2-amino-4-methyl-6-(trifluoromethyl)-5,6-dihydro-4H-1,3-oxazin-4-yl]-4-fluorophenyl}-5-cyanopyridine-2-carboxamide | CCD:1HL | [4J1F](https://www.rcsb.org/structure/4J1F) | BACE1 inhibitor — CCD 1HL; tool |
| N-{3-[(5R)-3-amino-2,5-dimethyl-1,1-dioxido-5,6-dihydro-2H-1,2,4-thiadiazin-5-yl]-4-fluorophenyl}-5-fluoropyridine-2-carboxamide | CCD:66F | [5HU1](https://www.rcsb.org/structure/5HU1) | BACE1 inhibitor — CCD 66F; tool |
| QKA | QKA | [6UWP](https://www.rcsb.org/structure/6UWP) | BACE1 compound 32 — CCD QKA; tool |
| YW412.8.31 | YW412.8.31 Fab | [3R1G](https://www.rcsb.org/structure/3R1G) | YW412.8.31; tool |

### INSR — P06213

| Original label | Raw key | Representative evidence | Proposed disposition |
|---|---|---|---|
| insulin | GTOPDB:5012 | [7PG0](https://www.rcsb.org/structure/7PG0) | Split multiple engineered/uncertain constructs by PDB; do not blanket-merge as native insulin. |
| insulin-like growth factor 1 | GTOPDB:4971 | [8XKM](https://www.rcsb.org/structure/8XKM) | Retain endogenous IGF-I; hybrid-receptor/construct context remains attached. |
| 83-14 | 83-14 Fab | [4ZXB](https://www.rcsb.org/structure/4ZXB) | 83-14; tool |
| 83-14, anti-insulin receptor monoclonal antibody 83-14 | 496 | [assay](https://www.iedb.org/assay/2006831) | 83-14; tool |
| 83-7 | 83-7 Fab | [4ZXB](https://www.rcsb.org/structure/4ZXB) | 83-7; tool |
| IGF1R | P08069 | [7S8V](https://www.rcsb.org/structure/7S8V) | IGF1R; receptor_partner |
| INS-IGF2 | F8WCM5 | [8GUY](https://www.rcsb.org/structure/8GUY) | insulin; endogenous_large |
| insulin-like growth factor 2 | P01344 | [8U4C](https://www.rcsb.org/structure/8U4C) | insulin-like growth factor 2; endogenous_large |

### ITGAV — P06756

| Original label | Raw key | Representative evidence | Proposed disposition |
|---|---|---|---|
| 17E6 | 17E6 Fab | [4O02](https://www.rcsb.org/structure/4O02) | 17E6; tool |
| A1A6H | A1A6H | [9CZD](https://www.rcsb.org/structure/9CZD) | Integrin compound 30 — CCD A1A6H; tool |
| C6-RGD3 | C6-RGD3 Fab | [6UJC](https://www.rcsb.org/structure/6UJC) | C6-RGD3; tool |
| C6D4 | C6D4 Fab | [6UJB](https://www.rcsb.org/structure/6UJB) | C6D4; tool |
| FN1 | P02751 | [4MMX](https://www.rcsb.org/structure/4MMX) | Fibronectin 10FN3 fragment; unclassified |
| ITGB1 | P05556 | [8W30](https://www.rcsb.org/structure/8W30) | ITGB1; receptor_partner |
| ITGB3 | P05106 | [4G1E](https://www.rcsb.org/structure/4G1E) | ITGB3; receptor_partner |
| ITGB6 | P18564 | [9CZ7](https://www.rcsb.org/structure/9CZ7) | ITGB6; receptor_partner |
| ITGB8 | P26012 | [8TCF](https://www.rcsb.org/structure/8TCF) | ITGB8; receptor_partner |
| TGFB1 | P01137 | [5FFO](https://www.rcsb.org/structure/5FFO) | TGFB1 latency-associated region; endogenous_large |
| TGFβ3 | P10600 | [8VS6](https://www.rcsb.org/structure/8VS6) | TGFβ3 latency-associated region; endogenous_large |

## HLA peptide deposit appendix

These are deposited short entity sequences in the relevant named-partner structures, not aliases to be collapsed by source protein. Some deposits have multiple entities or tethered peptides. `pdb_sequence` retains nonstandard residue codes. Allele information remains in the linked entry. Long fused entities are described above; no short entity does not mean no peptide.

| Target | Named source key | PDB | Short entity and deposited chemical sequence |
|---|---|---|---|
| HLA-DRA | peptide | [5NI9](https://www.rcsb.org/structure/5NI9) | entity 3 Alpha-enolase: `KRIAKAVNEKSCNCL` |
| HLA-DRA | insulin | [4Y19](https://www.rcsb.org/structure/4Y19) | entity 3 Insulin A chain: `GSLQPLALEGSLQKRG` |
| HLA-DRA | insulin | [4Y1A](https://www.rcsb.org/structure/4Y1A) | entity 3 Insulin A chain: `GSLQPLALEGSLQKRG` |
| HLA-DRA | FGB | [6ATZ](https://www.rcsb.org/structure/6ATZ) | entity 3 Fibrinogen beta chain: `GGYRA(CIR)PAKAAT` |
| HLA-DRA | FGB | [6BIJ](https://www.rcsb.org/structure/6BIJ) | entity 3 Fibrinogen beta chain: `GGY(CIR)A(CIR)PAKAAAT` |
| HLA-DRA | FGB | [6BIL](https://www.rcsb.org/structure/6BIL) | entity 3 Fibrinogen beta chain: `GGYRA(CIR)PAKAAAT` |
| HLA-DRA | FGB | [6V0Y](https://www.rcsb.org/structure/6V0Y) | entity 3 Fibrinogen beta chain: `GGY(CIR)A(CIR)PAKAAAT` |
| HLA-DRA | FGB | [6V13](https://www.rcsb.org/structure/6V13) | entity 3 Fibrinogen beta chain: `GGYRA(CIR)PAKAAAT` |
| HLA-DRA | FGB | [6V15](https://www.rcsb.org/structure/6V15) | entity 3 Fibrinogen beta chain: `GGY(CIR)A(CIR)PAKAAAT` |
| HLA-DRA | FGB | [6V18](https://www.rcsb.org/structure/6V18) | entity 3 Fibrinogen beta chain: `GGYRA(CIR)PAKAAAT` |
| HLA-DRA | FGB | [6V19](https://www.rcsb.org/structure/6V19) | entity 3 Fibrinogen beta chain: `GGY(CIR)A(CIR)PAKAAAT` |
| HLA-DRA | FGB | [6V1A](https://www.rcsb.org/structure/6V1A) | entity 3 Fibrinogen beta chain: `GGYRA(CIR)PAKAAAT` |
| HLA-DRA | MBP | [1BX2](https://www.rcsb.org/structure/1BX2) | entity 3 Myelin basic protein: `ENPVVHFFKNIVTPR` |
| HLA-DRA | MBP | [1FV1](https://www.rcsb.org/structure/1FV1) | entity 3 Myelin basic protein: `NPVVHFFKNIVTPRTPPPSQ` |
| HLA-DRA | MBP | [1HQR](https://www.rcsb.org/structure/1HQR) | entity 3 Myelin basic protein: `VHFFKNIVTPRTP` |
| HLA-DRA | MBP | [1YMM](https://www.rcsb.org/structure/1YMM) | entity 3 Myelin basic protein: `ENPVVHFFKNIVTPRGGSGGGGG` |
| HLA-DRA | MBP | [1ZGL](https://www.rcsb.org/structure/1ZGL) | entity 3 Myelin basic protein: `VHFFKNIVTPRTPGG` |
| HLA-DRA | CD74 | [1A6A](https://www.rcsb.org/structure/1A6A) | entity 3 Class-II-associated invariant chain peptide: `PVSKMRMATPLLMQA` |
| HLA-DRA | CD74 | [3PDO](https://www.rcsb.org/structure/3PDO) | entity 3 Class-II-associated invariant chain peptide: `KPVSKMRMATPLLMQALPM` |
| HLA-DRA | CD74 | [3PGC](https://www.rcsb.org/structure/3PGC) | entity 3 Class-II-associated invariant chain peptide: `KMRMATPLLMQALPM` |
| HLA-DRA | CD74 | [3PGD](https://www.rcsb.org/structure/3PGD) | entity 3 Class-II-associated invariant chain peptide: `KMRMATPLLMQALPM` |
| HLA-DRA | CD74 | [3QXA](https://www.rcsb.org/structure/3QXA) | entity 3 Class-II-associated invariant chain peptide: `PVSKMRMATPLLMQA` |
| HLA-DRA | CD74 | [3QXD](https://www.rcsb.org/structure/3QXD) | entity 3 Class-II-associated invariant chain peptide: `PVSKMRMATPLLMQA` |
| HLA-DRA | CD74 | [4AEN](https://www.rcsb.org/structure/4AEN) | entity 3 Class-II-associated invariant chain peptide: `MKMRMATPLLMQALPM` |
| HLA-DRA | CD74 | [4AH2](https://www.rcsb.org/structure/4AH2) | Long/fused entities; inspect deposited construct (no inferred peptide sequence). |
| HLA-DRA | CD74 | [4X5W](https://www.rcsb.org/structure/4X5W) | entity 3 Class-II-associated invariant chain peptide: `KPVSKWRMATPLLMQALPM` |
| HLA-DRA | CD74 | [7YX9](https://www.rcsb.org/structure/7YX9) | entity 3 Class-II-associated invariant chain peptide: `PVSKMRMATPLLMQA` |
| HLA-DRA | CD74 | [7YXB](https://www.rcsb.org/structure/7YXB) | entity 3 Class-II-associated invariant chain peptide: `AFAPVSKMRMATPLLMQAGN` |
| HLA-DRA | CD74 | [7Z0Q](https://www.rcsb.org/structure/7Z0Q) | entity 3 Class-II-associated invariant chain peptide: `PVSKMRMATPLLMQAGN` |
| HLA-DRA | CD74 | [8VRW](https://www.rcsb.org/structure/8VRW) | Long/fused entities; inspect deposited construct (no inferred peptide sequence). |
| HLA-DRA | HLA-A | [1AQD](https://www.rcsb.org/structure/1AQD) | entity 3 HLA class I histocompatibility antigen, A alpha chain: `VGSDWRFLRGYHQYA` |
| HLA-DRA | HLA-A | [4OV5](https://www.rcsb.org/structure/4OV5) | entity 3 HLA class I histocompatibility antigen, A alpha chain: `GSDARFLRGYHLYA` |
| HLA-DRA | APP | [31VO](https://www.rcsb.org/structure/31VO) | Long/fused entities; inspect deposited construct (no inferred peptide sequence). |
| HLA-DRA | ITGB3 | [2Q6W](https://www.rcsb.org/structure/2Q6W) | entity 3 Integrin beta-3: `AWRSDEALPLGS` |
| HLA-DRA | ENO1 | [5JLZ](https://www.rcsb.org/structure/5JLZ) | entity 3 Alpha-enolase: `TSKGLF(CIR)AAVPSGAS` |
| HLA-DRA | ENO1 | [5LAX](https://www.rcsb.org/structure/5LAX) | entity 3 Alpha-enolase: `TSKGLFRAAVPSGAS` |
| HLA-DRA | ENO1 | [5NI9](https://www.rcsb.org/structure/5NI9) | entity 3 Alpha-enolase: `KRIAKAVNEKSCNCL` |
| HLA-DRA | ENO1 | [5NIG](https://www.rcsb.org/structure/5NIG) | entity 3 Alpha-enolase: `K(CIR)IAKAVNEKSCNCL` |
| HLA-DRA | ENO1 | [8TRL](https://www.rcsb.org/structure/8TRL) | entity 3 Alpha-enolase: `EIFDS(CIR)GNPTGEV` |
| HLA-DRA | VIM | [4MCY](https://www.rcsb.org/structure/4MCY) | entity 3 Vimentin: `SAVRL(CIR)SSVPGVR` |
| HLA-DRA | VIM | [4MCZ](https://www.rcsb.org/structure/4MCZ) | entity 3 Vimentin: `GVYAT(CIR)SSAVRLR` |
| HLA-DRA | VIM | [4MD0](https://www.rcsb.org/structure/4MD0) | entity 3 Vimentin: `GVYAT(CIR)SSAV(CIR)L(CIR)` |
| HLA-DRA | VIM | [4MD5](https://www.rcsb.org/structure/4MD5) | entity 3 Vimentin: `SAVRL(CIR)SSVPGVR` |
| HLA-DRA | VIM | [4MDI](https://www.rcsb.org/structure/4MDI) | entity 3 Vimentin: `SAVRL(CIR)SSVPGVR` |
| HLA-DRA | VIM | [4MDJ](https://www.rcsb.org/structure/4MDJ) | entity 3 Vimentin: `SAVRLRSSVPGVR` |
| HLA-DRA | VIM | [6ATF](https://www.rcsb.org/structure/6ATF) | entity 3 Vimentin: `GVYATRSSAVRLR` |
| HLA-DRA | VIM | [6ATI](https://www.rcsb.org/structure/6ATI) | entity 3 Vimentin: `GVYAT(CIR)SSAVRLR` |
| HLA-DRA | VIM | [6BIR](https://www.rcsb.org/structure/6BIR) | entity 3 Vimentin: `SSLNL(CIR)ETNLDSL` |
| HLA-DRA | VIM | [8TRQ](https://www.rcsb.org/structure/8TRQ) | entity 3 Vimentin: `GVYAT(CIR)SSAVRLR` |
| HLA-DRA | VIM | [8TRR](https://www.rcsb.org/structure/8TRR) | entity 3 Vimentin: `GVYAT(CIR)SSAVRLR` |
| HLA-DRA | RO60 | [9YZ3](https://www.rcsb.org/structure/9YZ3) | entity 3 RNA-binding protein RO60: `KRFLLAVDVSASM` |
| HLA-DRA | TNC | [9NIG](https://www.rcsb.org/structure/9NIG) | entity 5 Tenascin: `D(CIR)Y(CIR)LNYSLPTGKK` |
| HLA-DRA | TNC | [9NIH](https://www.rcsb.org/structure/9NIH) | entity 3 Tenascin: `D(CIR)Y(CIR)LNYSLPTGKK` |
| HLA-DRA | PMEL | [4IS6](https://www.rcsb.org/structure/4IS6) | entity 3 M-alpha: `WNRQLYPEWTEAQRLD` |
| HLA-DRA | CAMP | [6BIV](https://www.rcsb.org/structure/6BIV) | entity 3 Cathelicidin antimicrobial peptide: `ETVCP(CIR)TTQQSPE` |
| HLA-DRA | CAMP | [6BIX](https://www.rcsb.org/structure/6BIX) | entity 3 Cathelicidin antimicrobial peptide: `ETVCP(CIR)TTQQSPE` |
| HLA-DRA | EEF1A1 | [3C5J](https://www.rcsb.org/structure/3C5J) | entity 3 Elongation factor 1-alpha 1: `QVIILNHPGQISA` |
| HLA-DRA | TPBG | [6HBY](https://www.rcsb.org/structure/6HBY) | entity 3 Trophoblast glycoprotein: `ARRPPLAELAALNLSGSRL` |
| HLA-A | V2 IgG Fab | [7STF](https://www.rcsb.org/structure/7STF) | entity 2 GTPase KRas, N-terminally processed: `VVVGAVGVGK` |
| HLA-A | insulin | [3UTQ](https://www.rcsb.org/structure/3UTQ) | entity 3 Insulin: `ALWGPDPAAA` |
| HLA-A | insulin | [3UTS](https://www.rcsb.org/structure/3UTS) | entity 3 Insulin: `ALWGPDPAAA` |
| HLA-A | insulin | [3UTT](https://www.rcsb.org/structure/3UTT) | entity 3 Insulin: `ALWGPDPAAA` |
| HLA-A | insulin | [5C0D](https://www.rcsb.org/structure/5C0D) | entity 3 Insulin: `AQWGPDPAAA` |
| HLA-A | insulin | [5HYJ](https://www.rcsb.org/structure/5HYJ) | entity 3 Insulin: `AQWGPDPAAA` |
| HLA-A | ERBB2 | [1QR1](https://www.rcsb.org/structure/1QR1) | entity 3 Receptor tyrosine-protein kinase erbB-2: `IISAVVGIL` |
| HLA-A | TYR | [7RK7](https://www.rcsb.org/structure/7RK7) | entity 3 Tyrosinase: `YMDGTMSQV` |
| HLA-A | CALR | [2CLR](https://www.rcsb.org/structure/2CLR) | entity 3 Calreticulin: `MLLSVPLLLG` |
| HLA-A | CALR | [7QPD](https://www.rcsb.org/structure/7QPD) | Long/fused entities; inspect deposited construct (no inferred peptide sequence). |
| HLA-A | CTNNB1 | [3FQN](https://www.rcsb.org/structure/3FQN) | entity 3 Catenin beta-1: `YLDSGIHSGA` |
| HLA-A | CTNNB1 | [3FQR](https://www.rcsb.org/structure/3FQR) | entity 3 Catenin beta-1: `YLD(SEP)GIHSGA` |
| HLA-A | CTNNB1 | [6O9B](https://www.rcsb.org/structure/6O9B) | entity 3 Catenin beta-1: `TTAPSLSGK` |
| HLA-A | CTNNB1 | [6O9C](https://www.rcsb.org/structure/6O9C) | entity 3 Catenin beta-1: `TTAPFLSGK` |
| HLA-A | DCT | [4HX1](https://www.rcsb.org/structure/4HX1) | entity 3 L-dopachrome tautomerase: `SVYDFFVWL` |
| HLA-A | PMEL | [1TVB](https://www.rcsb.org/structure/1TVB) | entity 3 M-alpha: `ITDQVPFSV` |
| HLA-A | PMEL | [1TVH](https://www.rcsb.org/structure/1TVH) | entity 3 M-alpha: `IMDQVPFSV` |
| HLA-A | PMEL | [5EU3](https://www.rcsb.org/structure/5EU3) | entity 3 M-alpha: `YLEPGPVTA` |
| HLA-A | PMEL | [5EU4](https://www.rcsb.org/structure/5EU4) | entity 3 M-alpha: `YLAPGPVTA` |
| HLA-A | PMEL | [5EU5](https://www.rcsb.org/structure/5EU5) | entity 3 M-alpha: `YLEPAPVTA` |
| HLA-A | PMEL | [5EU6](https://www.rcsb.org/structure/5EU6) | entity 3 M-alpha: `YLEPGPVTV` |
| HLA-A | PMEL | [7PHR](https://www.rcsb.org/structure/7PHR) | entity 8 M-alpha: `YLEPGPVTV`; entity 9 T-cell surface glycoprotein CD3 zeta chain: `QSFGLLDPKLCYLLDGILFIYGVILTALFLRVKFSR` |
| HLA-A | PLP1 | [2XPG](https://www.rcsb.org/structure/2XPG) | entity 3 Myelin proteolipid protein: `KLIETYFSK` |
| HLA-A | ARHGAP45 | [3D25](https://www.rcsb.org/structure/3D25) | entity 3 Minor histocompatibility antigen HA-1: `VLHDDLLEA` |
| HLA-A | ARHGAP45 | [3FT3](https://www.rcsb.org/structure/3FT3) | entity 3 Minor histocompatibility antigen HA-1: `VLHDDLLEA` |
| HLA-A | SLCO2A1 | [3MRR](https://www.rcsb.org/structure/3MRR) | entity 3 Solute carrier organic anion transporter family member 2A1: `LLAGIGTVPI` |
| HLA-A | ALK | [6AT9](https://www.rcsb.org/structure/6AT9) | entity 3 ALK tyrosine kinase receptor: `AQDIYRASYY` |
| HLA-DRB1 | insulin | [4Y19](https://www.rcsb.org/structure/4Y19) | entity 3 Insulin A chain: `GSLQPLALEGSLQKRG` |
| HLA-DRB1 | insulin | [4Y1A](https://www.rcsb.org/structure/4Y1A) | entity 3 Insulin A chain: `GSLQPLALEGSLQKRG` |
| HLA-DRB1 | FGB | [6BIJ](https://www.rcsb.org/structure/6BIJ) | entity 3 Fibrinogen beta chain: `GGY(CIR)A(CIR)PAKAAAT` |
| HLA-DRB1 | FGB | [6BIL](https://www.rcsb.org/structure/6BIL) | entity 3 Fibrinogen beta chain: `GGYRA(CIR)PAKAAAT` |
| HLA-DRB1 | FGB | [6V0Y](https://www.rcsb.org/structure/6V0Y) | entity 3 Fibrinogen beta chain: `GGY(CIR)A(CIR)PAKAAAT` |
| HLA-DRB1 | FGB | [6V13](https://www.rcsb.org/structure/6V13) | entity 3 Fibrinogen beta chain: `GGYRA(CIR)PAKAAAT` |
| HLA-DRB1 | FGB | [6V15](https://www.rcsb.org/structure/6V15) | entity 3 Fibrinogen beta chain: `GGY(CIR)A(CIR)PAKAAAT` |
| HLA-DRB1 | FGB | [6V18](https://www.rcsb.org/structure/6V18) | entity 3 Fibrinogen beta chain: `GGYRA(CIR)PAKAAAT` |
| HLA-DRB1 | FGB | [6V19](https://www.rcsb.org/structure/6V19) | entity 3 Fibrinogen beta chain: `GGY(CIR)A(CIR)PAKAAAT` |
| HLA-DRB1 | FGB | [6V1A](https://www.rcsb.org/structure/6V1A) | entity 3 Fibrinogen beta chain: `GGYRA(CIR)PAKAAAT` |
| HLA-DRB1 | MBP | [1BX2](https://www.rcsb.org/structure/1BX2) | entity 3 Myelin basic protein: `ENPVVHFFKNIVTPR` |
| HLA-DRB1 | MBP | [1YMM](https://www.rcsb.org/structure/1YMM) | entity 3 Myelin basic protein: `ENPVVHFFKNIVTPRGGSGGGGG` |
| HLA-DRB1 | CD74 | [1A6A](https://www.rcsb.org/structure/1A6A) | entity 3 Class-II-associated invariant chain peptide: `PVSKMRMATPLLMQA` |
| HLA-DRB1 | CD74 | [3PDO](https://www.rcsb.org/structure/3PDO) | entity 3 Class-II-associated invariant chain peptide: `KPVSKMRMATPLLMQALPM` |
| HLA-DRB1 | CD74 | [3PGC](https://www.rcsb.org/structure/3PGC) | entity 3 Class-II-associated invariant chain peptide: `KMRMATPLLMQALPM` |
| HLA-DRB1 | CD74 | [3PGD](https://www.rcsb.org/structure/3PGD) | entity 3 Class-II-associated invariant chain peptide: `KMRMATPLLMQALPM` |
| HLA-DRB1 | CD74 | [3QXA](https://www.rcsb.org/structure/3QXA) | entity 3 Class-II-associated invariant chain peptide: `PVSKMRMATPLLMQA` |
| HLA-DRB1 | CD74 | [3QXD](https://www.rcsb.org/structure/3QXD) | entity 3 Class-II-associated invariant chain peptide: `PVSKMRMATPLLMQA` |
| HLA-DRB1 | CD74 | [4AEN](https://www.rcsb.org/structure/4AEN) | entity 3 Class-II-associated invariant chain peptide: `MKMRMATPLLMQALPM` |
| HLA-DRB1 | CD74 | [4X5W](https://www.rcsb.org/structure/4X5W) | entity 3 Class-II-associated invariant chain peptide: `KPVSKWRMATPLLMQALPM` |
| HLA-DRB1 | CD74 | [8VRW](https://www.rcsb.org/structure/8VRW) | Long/fused entities; inspect deposited construct (no inferred peptide sequence). |
| HLA-DRB1 | HLA-A | [1AQD](https://www.rcsb.org/structure/1AQD) | entity 3 HLA class I histocompatibility antigen, A alpha chain: `VGSDWRFLRGYHQYA` |
| HLA-DRB1 | HLA-A | [4OV5](https://www.rcsb.org/structure/4OV5) | entity 3 HLA class I histocompatibility antigen, A alpha chain: `GSDARFLRGYHLYA` |
| HLA-DRB1 | ENO1 | [5JLZ](https://www.rcsb.org/structure/5JLZ) | entity 3 Alpha-enolase: `TSKGLF(CIR)AAVPSGAS` |
| HLA-DRB1 | ENO1 | [5LAX](https://www.rcsb.org/structure/5LAX) | entity 3 Alpha-enolase: `TSKGLFRAAVPSGAS` |
| HLA-DRB1 | ENO1 | [5NI9](https://www.rcsb.org/structure/5NI9) | entity 3 Alpha-enolase: `KRIAKAVNEKSCNCL` |
| HLA-DRB1 | ENO1 | [5NIG](https://www.rcsb.org/structure/5NIG) | entity 3 Alpha-enolase: `K(CIR)IAKAVNEKSCNCL` |
| HLA-DRB1 | ENO1 | [8TRL](https://www.rcsb.org/structure/8TRL) | entity 3 Alpha-enolase: `EIFDS(CIR)GNPTGEV` |
| HLA-DRB1 | VIM | [4MCY](https://www.rcsb.org/structure/4MCY) | entity 3 Vimentin: `SAVRL(CIR)SSVPGVR` |
| HLA-DRB1 | VIM | [4MCZ](https://www.rcsb.org/structure/4MCZ) | entity 3 Vimentin: `GVYAT(CIR)SSAVRLR` |
| HLA-DRB1 | VIM | [4MD0](https://www.rcsb.org/structure/4MD0) | entity 3 Vimentin: `GVYAT(CIR)SSAV(CIR)L(CIR)` |
| HLA-DRB1 | VIM | [4MD5](https://www.rcsb.org/structure/4MD5) | entity 3 Vimentin: `SAVRL(CIR)SSVPGVR` |
| HLA-DRB1 | VIM | [4MDI](https://www.rcsb.org/structure/4MDI) | entity 3 Vimentin: `SAVRL(CIR)SSVPGVR` |
| HLA-DRB1 | VIM | [4MDJ](https://www.rcsb.org/structure/4MDJ) | entity 3 Vimentin: `SAVRLRSSVPGVR` |
| HLA-DRB1 | VIM | [6BIR](https://www.rcsb.org/structure/6BIR) | entity 3 Vimentin: `SSLNL(CIR)ETNLDSL` |
| HLA-DRB1 | VIM | [8TRQ](https://www.rcsb.org/structure/8TRQ) | entity 3 Vimentin: `GVYAT(CIR)SSAVRLR` |
| HLA-DRB1 | VIM | [8TRR](https://www.rcsb.org/structure/8TRR) | entity 3 Vimentin: `GVYAT(CIR)SSAVRLR` |
| HLA-DRB1 | PMEL | [4IS6](https://www.rcsb.org/structure/4IS6) | entity 3 M-alpha: `WNRQLYPEWTEAQRLD` |
| HLA-DRB1 | CAMP | [6BIV](https://www.rcsb.org/structure/6BIV) | entity 3 Cathelicidin antimicrobial peptide: `ETVCP(CIR)TTQQSPE` |
| HLA-DRB1 | CAMP | [6BIX](https://www.rcsb.org/structure/6BIX) | entity 3 Cathelicidin antimicrobial peptide: `ETVCP(CIR)TTQQSPE` |
| HLA-DRB1 | TPBG | [6HBY](https://www.rcsb.org/structure/6HBY) | entity 3 Trophoblast glycoprotein: `ARRPPLAELAALNLSGSRL` |
| HLA-B | 2Q1 Fab | [6UJ9](https://www.rcsb.org/structure/6UJ9) | entity 3 Isocitrate dehydrogenase [NADP], mitochondrial: `SPNGTIQNIL` |
| HLA-B | CTSA | [3BP4](https://www.rcsb.org/structure/3BP4) | entity 3 Lysosomal protective protein: `IRAAPPPLF` |
| HLA-B | CTSA | [3BP7](https://www.rcsb.org/structure/3BP7) | entity 3 Lysosomal protective protein: `IRAAPPPLF` |
| HLA-B | VIPR1 | [1OF2](https://www.rcsb.org/structure/1OF2) | entity 3 Vasoactive intestinal polypeptide receptor 1: `RRKWRRWHL` |
| HLA-B | VIPR1 | [1OGT](https://www.rcsb.org/structure/1OGT) | entity 3 Vasoactive intestinal polypeptide receptor 1: `RRKWRRWHL` |
| HLA-B | VIPR1 | [3B3I](https://www.rcsb.org/structure/3B3I) | entity 3 Vasoactive intestinal polypeptide receptor 1: `RRKW(CIR)RWHL` |
| HLA-B | VIPR1 | [3B6S](https://www.rcsb.org/structure/3B6S) | entity 3 Vasoactive intestinal polypeptide receptor 1: `RRKW(CIR)RWHL` |
| HLA-B | VIPR1 | [3DTX](https://www.rcsb.org/structure/3DTX) | entity 3 Vasoactive intestinal polypeptide receptor 1: `RRKW(CIR)(CIR)WHL` |
| HLA-B | VIPR1 | [3HCV](https://www.rcsb.org/structure/3HCV) | entity 3 Vasoactive intestinal polypeptide receptor 1: `RRKW(CIR)(CIR)WHL` |
| HLA-B | VIPR1 | [5DEF](https://www.rcsb.org/structure/5DEF) | entity 3 Vasoactive intestinal polypeptide receptor 1: `RRKWRRWHL` |
| HLA-B | VIPR1 | [5DEG](https://www.rcsb.org/structure/5DEG) | entity 3 Vasoactive intestinal polypeptide receptor 1: `RRKWRRWHL` |
| HLA-B | VIPR1 | [5IB1](https://www.rcsb.org/structure/5IB1) | entity 3 Vasoactive intestinal polypeptide receptor 1: `RRKWRRWHL` |
| HLA-B | VIPR1 | [5IB2](https://www.rcsb.org/structure/5IB2) | entity 3 Vasoactive intestinal polypeptide receptor 1: `RRKWRRWHL` |
| HLA-B | VIPR1 | [5IB3](https://www.rcsb.org/structure/5IB3) | entity 3 Vasoactive intestinal polypeptide receptor 1: `RRKWRRWHL` |
| HLA-B | VIPR1 | [5IB4](https://www.rcsb.org/structure/5IB4) | entity 3 Vasoactive intestinal polypeptide receptor 1: `RRKWRRWHL` |
| HLA-B | VIPR1 | [5IB5](https://www.rcsb.org/structure/5IB5) | entity 3 Vasoactive intestinal polypeptide receptor 1: `RRKWRRWHL` |
| HLA-B | GCGR | [2A83](https://www.rcsb.org/structure/2A83) | entity 3 Glucagon receptor: `RRRWHRWRL` |
| HLA-B | GCGR | [3CZF](https://www.rcsb.org/structure/3CZF) | entity 3 Glucagon receptor: `RRRWHRWRL` |
| HLA-B | CACNA1D | [3LV3](https://www.rcsb.org/structure/3LV3) | entity 3 Voltage-dependent L-type calcium channel subunit alpha-1D: `SRRWRRWNR` |
| HLA-B | ALK | [5VZ5](https://www.rcsb.org/structure/5VZ5) | entity 3 ALK tyrosine kinase receptor: `AQDIYRASYY` |
