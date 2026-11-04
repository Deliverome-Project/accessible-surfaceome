> Review history: this is an initial proposal or independent critique, not the final accepted rule set. See the consolidated report for accepted corrections and final counts.

# Checkpoint contact review — proposed, not deployed

Input release: `contacts-ba6680878403e6980464`. Reviewed 8 stable UniProt targets and all original observations, using public PDB entry/entity metadata, primary papers, NCI/USAN and source-database identity evidence. No raw observations, production assets or databases were modified. The JSON contains explicit display/category rules, with narrow PDB scopes wherever a raw label is ambiguous.

## Counts and limits

Counts below reproduce the current viewer named-ligand predicate over the original observations after applying the proposed rules in order. These are estimated browsing identities, **not exhaustive partner coverage** and not a count of distinct directly crystallized therapeutics. All observation counts remain unchanged.

| Target | UniProt | Original all named | Original EC named | Proposed EC named | Original observations | EC observations | Non-EC observations |
|---|---|---:|---:|---:|---:|---:|---:|
| CTLA4 | P16410 | 19 | 18 | 18 | 80 | 78 | 2 |
| CD40 | P25942 | 14 | 14 | 9 | 35 | 31 | 4 |
| TNFRSF4 | P43489 | 10 | 10 | 4 | 21 | 20 | 1 |
| TNFRSF9 | Q07011 | 8 | 8 | 7 | 36 | 36 | 0 |
| TIGIT | Q495A1 | 8 | 8 | 8 | 19 | 19 | 0 |
| CD27 | P26842 | 8 | 8 | 5 | 18 | 18 | 0 |
| BTLA | Q7Z6A9 | 7 | 7 | 5 | 8 | 8 | 0 |
| CD40LG | P29965 | 10 | 10 | 8 | 15 | 15 | 0 |

The principal reductions are source aliases, not removal of valid binders. CTLA4 gains distinct Ipi.105/Ipi.106 constructs while losing two duplicate aliases. TIGIT retains all eight identities because the two Fabs in 8SZY are different binders. BTLA deliberately retains venanprubart separately from the h22B3 structural construct. No rule excludes an observation from the overview.

## High-priority identity corrections

1. **CTLA4 engineered variants:** AACDB calls the contacts at 7SU0 and 7SU1 `Ipilimumab Fab`, but the deposited structures identify **Ipi.105** and **Ipi.106**. The proposed structure-scoped rules separate both from parent ipilimumab and from mipi.4. The latter is explicitly engineered for species reactivity in 9DQ3. [7SU0](https://www.rcsb.org/structure/7SU0), [7SU1](https://www.rcsb.org/structure/7SU1), [primary acidic-pH paper](https://doi.org/10.1080/19420862.2021.2024642), [mipi.4 paper](https://doi.org/10.1080/19420862.2025.2451296).

2. **CD40LG parent versus fluorescent constructs:** `5C8 Fab` (1I9R) and `5c8 Fab` (6W9G) normalize identically. PDB-scoped rules connect the former to the parent humanized 5C8/ruplizumab binding domain and the latter to **5c8\***, containing a fluorescent noncanonical amino acid. **5c8\* WH47L** (7SGM) remains a third, distinct construct. [1I9R](https://www.rcsb.org/structure/1I9R), [6W9G](https://www.rcsb.org/structure/6W9G), [7SGM](https://www.rcsb.org/structure/7SGM), [fluorescent-variant paper](https://doi.org/10.1021/acs.biochem.0c00474), [WH47L paper](https://doi.org/10.1016/j.jmb.2022.167455).

3. **TIGIT two-antibody complex:** CHA.9.543 is the nonblocking Fab on the opposite TIGIT face from BMS-986207/renvistobart. PDB author chains AB/CD belong to CHA.9.543; HL/IM belong to BMS-986207. Keep CHA.9.543 as a research tool and renvistobart as therapeutic. [PDB 8SZY](https://www.rcsb.org/structure/8SZY), [primary paper](https://doi.org/10.1080/19420862.2023.2253788), [NCI renvistobart](https://www.cancer.gov/publications/dictionaries/cancer-drug/def/renvistobart).

4. **CD40LG TNC is engineered:** the 6BRB partner maps to scaffold parent P24821/TNC, but the entity is an engineered **Tn3-like domain** in the VIB4920 development study. The proposed name is `VIB4920-related Tn3 binding domain`, therapeutic category. This does not establish natural tenascin-C as a CD40L ligand or crystallization of full VIB4920. [PDB 6BRB](https://www.rcsb.org/structure/6BRB), [primary paper](https://doi.org/10.1126/scitranslmed.aar6584).

5. **Synthetic ligands:** 4-1BB generic `peptide` is **BCY10916** (6Y8K), a synthetic cyclic discovery binder. CD40LG `LKJ` is **BIO8898** (3LKJ), the synthetic subunit-fracture inhibitor. Both are research tools, not endogenous small molecules. [6Y8K](https://www.rcsb.org/structure/6Y8K), [BCY10916 primary study](https://doi.org/10.1136/jitc-2020-001762), [3LKJ](https://www.rcsb.org/structure/3LKJ), [BIO8898 primary study](https://doi.org/10.1021/cb2000346).

## Template-arm evidence and unresolved findings

- CTLA4 Danvilostomig/Sovipostobart/Tazlestobart share the ipilimumab variable domain; Volrustomig links to tremelimumab; Erfonrilimab links to KN044. Preserve these separate drug names and explicitly describe their evidence as matched arms. Thera-SAbDab independently records the common ipilimumab sequence and distinguishes 7SU0/7SU1 as only 95–98% matches. [Danvilostomig source record](https://opig.stats.ox.ac.uk/webapps/sabdab-sabpred/therasabdab/therasummary/?INN=Danvilostomig).

- CD40 Cifurtilimab has the same Fv sequence as Dacetuzumab, but 8YX9 is deposited as Dacetuzumab. They remain separate therapeutics with the same contact template. [Thera-SAbDab](https://opig.stats.ox.ac.uk/webapps/sabdab-sabpred/therasabdab/therasummary/?INN=Cifurtilimab), [8YX9](https://www.rcsb.org/structure/8YX9).

- CD40LG Tegoprubart and Velaprumig share the humanized 5C8 template contacts with Ruplizumab; sequence matching is not full-molecule equivalence. No collapse of these three drugs is proposed. [Tegoprubart source record](https://opig.stats.ox.ac.uk/webapps/sabdab-sabpred/therasabdab/therasummary/?INN=Tegoprubart), [Velaprumig source record](https://opig.stats.ox.ac.uk/webapps/sabdab-sabpred/therasabdab/therasummary/?INN=Velaprumig).

- BTLA h22B3 has an exact cached VH/VL match to Venanprubart. However the clinical paper describes 22B3 as a non-competing receptor-occupancy reagent. The clinical reagent wording is not sufficient to reconcile full construct identity; **keep h22B3 and venanprubart separate** while merging the IEDB/AACDB 22B3 structural labels at 8F6O. [BTLA structure paper](https://doi.org/10.1016/j.str.2023.05.011), [clinical paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC12813646/).

- CTLA4 7ELX is deposited only as an unspecified Fab, with its paper still listed as to be published. Cached matching links its variable domain to ipilimumab and related drugs, but the proposal retains **Unresolved Fab 7ELX**, unclassified, rather than inventing a full antibody identity. [7ELX](https://www.rcsb.org/structure/7ELX).

- TIGIT 8VTE has an inconsistent entry title that says Vibostolimab. Its deposited entity names explicitly say Tiragolumab (light variable entity 1 and heavy variable entity 2), and the cached exact-VH/VL match is Tiragolumab. Retain Tiragolumab and flag the title error; never relabel from the title alone. [8VTE](https://www.rcsb.org/structure/8VTE), [entity 1](https://data.rcsb.org/rest/v1/core/polymer_entity/8vte/1), [entity 2](https://data.rcsb.org/rest/v1/core/polymer_entity/8vte/2).

- OX40 P43488 at 2HEY is **murine** OX40L bound to human OX40; keep distinct from human P23510 at 2HEV. A proposed scoped tool classification names the experimental xenolog, but the current viewer `namedLigand` predicate still excludes a bare accession without `partner_label`, even if `canonical_partner_label` exists. Thus it does **not** increase the named count until that separate display issue is addressed. [2HEY](https://www.rcsb.org/structure/2HEY).

- 4-1BB 6CU0 uses a **C121S receptor** construct; this is not a new ligand. Keep that engineering in observation provenance rather than merging away the structural context. [6CU0](https://www.rcsb.org/structure/6CU0).

## Matcher validation and scope

Every proposed `names` entry occurs exactly in the supplied raw or summary labels. No bare IEDB numeric IDs are used: notably `197330` represents both ABBV-323 and FAB516 and would be unsafe as a matcher. The production matcher strips Fab/Fv/VHH, removes trailing parentheticals, then casefolds; rule order is last-match-wins. The global ipilimumab rule and the two narrow Ipi.105/Ipi.106 rules intentionally overlap. 5C8 corrections are independently scoped to 1I9R and 6W9G. Generic `peptide`, scaffold-parent TNC/P24821, xenolog accession and anonymous SAbDab IDs are PDB-scoped. H2191 is independently confirmed as a humanized, affinity-matured derivative of M2191 in [IEDB assay 3110168](https://www.iedb.org/details_v3.php?id=3110168&type=assay); the two remain separate. No chain-specific identity rewrite is needed for the proposed rules; 8SZY keeps existing distinct chain-derived source names.

Anonymous SAbDab observations have scoped duplicate-identity rules for 9DQ3, 8YX1, 6OKM, 6A3W, 8VTD, 5TL5, 8F60 and 6W9G, each a single named antibody complex. These do not merge distinct antibodies solely by footprint. The raw observations and residue arrays remain unchanged.

## OX40 chain-level check

Downloaded RCSB polymer-entity sequences were compared exactly. 6OGX entity 1 / author C equals 6OKN entity 1 / 1A7 heavy (225 residues); 6OGX entity 2 / D equals 6OKN entity 2 / 1A7 light (214). 6OGX entity 4 / H equals 6OKM entity 1 / 3C8 heavy (222); 6OGX entity 5 / L equals 6OKM entity 2 / 3C8 light (214). Hence 6OGX_1/Ab1/1A7 and 6OGX_2/Ab2/3C8 are legitimate source-alias groups, and remain distinct from each other. [6OGX](https://www.rcsb.org/structure/6OGX), [primary study](https://doi.org/10.1080/19420862.2019.1625662), [RG7888/vonlerolizumab source](https://www.guidetopharmacology.org/GRAC/LigandDisplayForward?ligandId=9245&tab=clinical).

## Complete named-partner disposition

Each original summary label is listed below, followed by its proposed disposition. Where the original summary already combined different constructs, inspect the listed structure-scoped split and the rule JSON rather than treating one summary representative as the whole group.

### CTLA4 — P16410

| Original named label | Original category | Representative PDB | Proposed identity/category |
|---|---|---|---|
| Danvilostomig | therapeutic | 6rp8 | Danvilostomig / therapeutic |
| Erfonrilimab | therapeutic | 6rqm | Erfonrilimab / therapeutic |
| Gotistobart | therapeutic | 6xy2 | Gotistobart / therapeutic |
| Ipilimumab | therapeutic | 7su0 | Ipi.105 / tool; parent / Ipi.105 / Ipi.106 split by PDB |
| Porustobart | therapeutic | 7dv4 | Porustobart / therapeutic |
| Sovipostobart | therapeutic | 6rp8 | Sovipostobart / therapeutic |
| Tazlestobart | therapeutic | 6rp8 | Tazlestobart / therapeutic |
| tremelimumab | therapeutic | 5ggv | Tremelimumab / therapeutic |
| Volrustomig | therapeutic | 5ggv | Volrustomig / therapeutic |
| 7ELX | unclassified | 7elx | Unresolved Fab 7ELX / unclassified |
| AP2M1 | unclassified | 1h6e | AP2M1 / unclassified |
| blocking-KN044 Nanobody | unclassified | 6rqm | KN044 nanobody / tool |
| CD80 | unclassified | 1i8l | CD80 / endogenous_large |
| CD86 | unclassified | 1i85 | CD86 / endogenous_large |
| HL32 | unclassified | 6xy2 | Gotistobart / therapeutic |
| JS007 | unclassified | 8hit | JS007 / therapeutic |
| mipi.4 | unclassified | 9dq3 | mipi.4 / tool |
| non-blocking-CTLA-4 Nanobody | unclassified | 6rpj | non-blocking-CTLA-4 Nanobody / tool |
| tremelimumab, CP-675, CP-675206, ticilimumab | unclassified | assay-only | Tremelimumab / therapeutic |

Applied rule rationale and citation:

- Rule 1: **Danvilostomig** (therapeutic; all observed PDBs). Thera-SAbDab exact variable-domain/arm match to the deposited ipilimumab construct; retained as a separate therapeutic identity. This is template-arm contact evidence, not crystallization of the complete named therapeutic. [Evidence](https://www.rcsb.org/structure/6RP8).
- Rule 2: **Sovipostobart** (therapeutic; all observed PDBs). Thera-SAbDab exact variable-domain/arm match to the deposited ipilimumab construct; retained as a separate therapeutic identity. This is template-arm contact evidence, not crystallization of the complete named therapeutic. [Evidence](https://www.rcsb.org/structure/6RP8).
- Rule 3: **Tazlestobart** (therapeutic; all observed PDBs). Thera-SAbDab exact variable-domain/arm match to the deposited ipilimumab construct; retained as a separate therapeutic identity. This is template-arm contact evidence, not crystallization of the complete named therapeutic. [Evidence](https://www.rcsb.org/structure/6RP8).
- Rule 4: **Volrustomig** (therapeutic; all observed PDBs). Thera-SAbDab exact variable-domain/arm match to the deposited tremelimumab construct; retained as a separate therapeutic identity. This is template-arm contact evidence, not crystallization of the complete named therapeutic. [Evidence](https://www.rcsb.org/structure/5GGV).
- Rule 5: **Erfonrilimab** (therapeutic; all observed PDBs). Thera-SAbDab exact variable-domain/arm match to the deposited KN044 nanobody construct; retained as a separate therapeutic identity. This is template-arm contact evidence, not crystallization of the complete named therapeutic. [Evidence](https://www.rcsb.org/structure/6RQM).
- Rule 6: **Gotistobart** (therapeutic; all observed PDBs). USAN explicitly lists HL32 as a gotistobart code; 6XY2 is the HL32 Fab. Consolidates that binding-domain alias without claiming the intact Fc-engineered therapeutic was crystallized. [Evidence](https://searchusan.ama-assn.org/usan/documentDownload?uri=%2Funstructured%2Fbinary%2Fusan%2Fgotistobart-.pdf).
- Rule 7: **Porustobart** (therapeutic; all observed PDBs). Exact Thera-SAbDab variable-domain match to the anti-CTLA-4 VH in 7DV4; binding-domain contacts, not evidence for the intact therapeutic format. [Evidence](https://www.rcsb.org/structure/7DV4).
- Rule 8: **Tremelimumab** (therapeutic; all observed PDBs). The cited structure is tremelimumab Fab; the IEDB multi-alias label refers to the same named antibody. Preserve each assay and residue observation. [Evidence](https://www.rcsb.org/structure/5GGV).
- Rule 9: **Unresolved Fab 7ELX** (unclassified; all observed PDBs). The PDB names an unspecified Fab and has no published primary paper. Exact variable-domain matches support an ipilimumab-like arm, but do not identify a complete antibody construct; retain separately. [Evidence](https://www.rcsb.org/structure/7ELX).
- Rule 10: **KN044 nanobody** (tool; all observed PDBs). The deposited molecule is the blocking camelid KN044 nanobody. Keep distinct from erfonrilimab, whose matching arm does not establish full construct identity. [Evidence](https://www.rcsb.org/structure/6RQM).
- Rule 11: **non-blocking-CTLA-4 Nanobody** (tool; all observed PDBs). The deposited nonblocking camelid nanobody is distinct from blocking KN044; no therapeutic identity established. [Evidence](https://www.rcsb.org/structure/6RPJ).
- Rule 12: **JS007** (therapeutic; all observed PDBs). JS007 is a named clinical anti-CTLA-4 antibody; 8HIT measures its bound antibody fragment. Do not merge it with HL32 despite related epitopes. [Evidence](https://pmc.ncbi.nlm.nih.gov/articles/PMC11443874/).
- Rule 13: **mipi.4** (tool; all observed PDBs). Engineered ipilimumab variant mipi.4 with altered species reactivity; keep separate from parent ipilimumab. [Evidence](https://www.rcsb.org/structure/9DQ3).
- Rule 14: **CD80** (endogenous_large; all observed PDBs). Natural B7-family extracellular protein ligand; target-bound structure directly establishes the interface. [Evidence](https://www.rcsb.org/structure/1I8L).
- Rule 15: **CD86** (endogenous_large; all observed PDBs). Natural B7-family extracellular protein ligand; target-bound structure directly establishes the interface. [Evidence](https://www.rcsb.org/structure/1I85).
- Rule 62: **Ipilimumab** (therapeutic; all observed PDBs). Parent ipilimumab binding-domain aliases. Narrower 7SU0/7SU1 overrides below preserve the two engineered acidic-pH variants. [Evidence](https://www.rcsb.org/structure/5TRU).
- Rule 63: **Ipi.105** (tool; 7su0). PDB and PMID 35192429 identify the acidic-pH-selective engineered ipilimumab variant Ipi.105; correct the AACDB parent-antibody shorthand without changing raw observations. [Evidence](https://www.rcsb.org/structure/7SU0).
- Rule 64: **Ipi.106** (tool; 7su1). PDB and PMID 35192429 identify the distinct acidic-pH-selective engineered ipilimumab variant Ipi.106; keep separate from both Ipi.105 and parent ipilimumab. [Evidence](https://www.rcsb.org/structure/7SU1).
- Rule 68: **mipi.4** (tool; 9dq3). Structure-scoped SAbDab source ID in a complex with one named antibody; deposited title/entity identity supports the same binding construct. Raw source ID and residues are preserved. [Evidence](https://www.rcsb.org/structure/9DQ3).

### CD40 — P25942

| Original named label | Original category | Representative PDB | Proposed identity/category |
|---|---|---|---|
| CD40 ligand | endogenous_large | 3qd6 | CD40 ligand / endogenous_large |
| Bleselumab | therapeutic | 8yx1 | Bleselumab / therapeutic |
| Cifurtilimab | therapeutic | 8yx9 | Cifurtilimab / therapeutic |
| Dacetuzumab | therapeutic | 8yx9 | Dacetuzumab / therapeutic |
| Ravagalimab | therapeutic | 6pe8 | Ravagalimab / therapeutic |
| Teneliximab | therapeutic | 5dmi | Teneliximab / therapeutic |
| 3h56-5 | unclassified | 5dmj | 3H56-5 / tool |
| 3H56-5 VH-sdAb | unclassified | 5dmj | 3H56-5 / tool |
| 516 | unclassified | 6pe9 | FAB516 / tool |
| ABBV-323 | unclassified | 6pe8 | Ravagalimab / therapeutic |
| Chi220 | unclassified | 5dmi | Teneliximab / therapeutic |
| ChiLob 7/4 | unclassified | 6fax | ChiLob 7/4 / therapeutic |
| FAB516 | unclassified | 6pe9 | FAB516 / tool |
| Lob 7.4 | unclassified | 6fax | ChiLob 7/4 / therapeutic |

Applied rule rationale and citation:

- Rule 16: **CD40 ligand** (endogenous_large; all observed PDBs). Natural CD40LG/CD154 ligand; IUPHAR and PDBe rows represent the same ligand and retain separate structural observations. [Evidence](https://www.rcsb.org/structure/3QD6).
- Rule 17: **Bleselumab** (therapeutic; all observed PDBs). PDB and primary paper identify the deposited bleselumab Fab; catalogue chain match is supporting identification, not intact-IgG structure evidence. [Evidence](https://www.rcsb.org/structure/8YX1).
- Rule 18: **Dacetuzumab** (therapeutic; all observed PDBs). PDB and primary paper identify dacetuzumab Fab bound to CD40. [Evidence](https://www.rcsb.org/structure/8YX9).
- Rule 19: **Cifurtilimab** (therapeutic; all observed PDBs). Thera-SAbDab reports the same Fv sequence as dacetuzumab; 8YX9 is deposited as dacetuzumab. Preserve the distinct therapeutic and mark its evidence as a matched template arm, not a separately crystallized cifurtilimab. [Evidence](https://opig.stats.ox.ac.uk/webapps/sabdab-sabpred/therasabdab/therasummary/?INN=Cifurtilimab).
- Rule 20: **Ravagalimab** (therapeutic; all observed PDBs). The primary structural paper explicitly identifies ABBV-323 as ravagalimab; merge its Fab/source aliases. [Evidence](https://www.rcsb.org/structure/6PE8).
- Rule 21: **Teneliximab** (therapeutic; all observed PDBs). 5DMI identifies Chi220 Fab and its Thera-SAbDab chain annotations identify teneliximab; cached exact VH/VL match corroborates the binding-domain alias. [Evidence](https://www.rcsb.org/annotations/5DMI).
- Rule 22: **3H56-5** (tool; all observed PDBs). Same single-domain anti-CD40 construct across 5DMJ/5IHL and IEDB/AACDB labels; not another antibody with an overlapping footprint. [Evidence](https://www.rcsb.org/structure/5DMJ).
- Rule 23: **FAB516** (tool; all observed PDBs). Same deposited FAB516 agonist construct. Remains separate from the closely related ravagalimab/ABBV-323 antagonist; the structural paper describes a functionally important LCDR1 substitution. [Evidence](https://www.rcsb.org/structure/6PE9).
- Rule 24: **ChiLob 7/4** (therapeutic; all observed PDBs). The primary paper identifies 6FAX as ChiLob 7/4; clinical Phase I evidence exists (PMID 24778319). Consolidate the named Fab alias only, preserving source construct information. [Evidence](https://pmc.ncbi.nlm.nih.gov/articles/PMC7280789/).
- Rule 69: **Bleselumab** (therapeutic; 8yx1). Structure-scoped SAbDab source ID in a complex with one named antibody; deposited title/entity identity supports the same binding construct. Raw source ID and residues are preserved. [Evidence](https://www.rcsb.org/structure/8YX1).

### TNFRSF4 — P43489

| Original named label | Original category | Representative PDB | Proposed identity/category |
|---|---|---|---|
| OX-40 ligand | endogenous_large | 2hev | OX-40 ligand / endogenous_large |
| Vonlerolizumab | therapeutic | 6okn | Vonlerolizumab / therapeutic |
| 1A7 | unclassified | 6okn | Vonlerolizumab / therapeutic |
| 3C8 | unclassified | 6okm | 3C8 / tool |
| 6OGX_1 | unclassified | 6ogx | Vonlerolizumab / therapeutic |
| 6OGX_2 | unclassified | 6ogx | 3C8 / tool |
| Ab1 | unclassified | 6ogx | Vonlerolizumab / therapeutic |
| Ab2 | unclassified | 6ogx | 3C8 / tool |
| DF004 | unclassified | 8ag1 | DF004 / tool |
| RG7888 | unclassified | 7yk4 | Vonlerolizumab / therapeutic |

Applied rule rationale and citation:

- Rule 25: **OX-40 ligand** (endogenous_large; all observed PDBs). Human TNFSF4/OX40L native ligand. The separate murine OX40L observation (P43488, 2HEY) is not merged into the human ligand. [Evidence](https://www.rcsb.org/structure/2HEV).
- Rule 26: **Vonlerolizumab** (therapeutic; all observed PDBs). RG7888 is a vonlerolizumab alias. 6OGX Fab1 author C/D sequences exactly equal 6OKN 1A7 heavy/light sequences; cached exact VH/VL matches connect these to vonlerolizumab. IEDB Ab1 spans 6OGX/6OKN. Consolidate binding-domain aliases, not the distinct Fab2. [Evidence](https://www.guidetopharmacology.org/GRAC/LigandDisplayForward?ligandId=9245&tab=clinical).
- Rule 27: **3C8** (tool; all observed PDBs). 6OGX Fab2 author H/L sequences exactly equal 6OKM 3C8 heavy/light sequences. The paper identifies 6OKM as Fab2 and IEDB Ab2 spans both entries. Keep separate from Fab1/vonlerolizumab. [Evidence](https://www.rcsb.org/structure/6OGX).
- Rule 28: **DF004** (tool; all observed PDBs). Named experimental agonist antibody in the primary paper (PMCID PMC9496217); distinct CRD2-binding clone, not RG7888/vonlerolizumab. [Evidence](https://www.rcsb.org/structure/8AG1).
- Rule 67: **Murine OX40L (experimental xenolog)** (tool; 2hey). 2HEY explicitly complexes murine OX40L with human OX40. This is an experimental cross-species ligand, not a second observation of the native human TNFSF4 ligand. [Evidence](https://www.rcsb.org/structure/2HEY).
- Rule 70: **3C8** (tool; 6okm). Structure-scoped SAbDab source ID in a complex with one named antibody; deposited title/entity identity supports the same binding construct. Raw source ID and residues are preserved. [Evidence](https://www.rcsb.org/structure/6OKM).

### TNFRSF9 — Q07011

| Original named label | Original category | Representative PDB | Proposed identity/category |
|---|---|---|---|
| 4-1BB ligand | endogenous_large | 6cpr | 4-1BB ligand / endogenous_large |
| Evunzekibart | therapeutic | 8oz3 | Evunzekibart / therapeutic |
| Urelumab | therapeutic | 6mhr | Urelumab / therapeutic |
| utomilumab | therapeutic | 6a3w | Utomilumab / therapeutic |
| 1618 | unclassified | 7yxu | 1618 / therapeutic |
| Fab1618 | unclassified | 7yxu | 1618 / therapeutic |
| HZ-L-Yr-16 | unclassified | 7d4b | HZ-L-Yr-16 / therapeutic |
| peptide | unclassified | 6y8k | BCY10916 / tool |

Applied rule rationale and citation:

- Rule 29: **4-1BB ligand** (endogenous_large; all observed PDBs). Natural TNFSF9 ligand; cross-source duplicates retain observations. 6CU0 explicitly uses a C121S receptor construct, which must remain in structural provenance. [Evidence](https://www.rcsb.org/structure/6CPR).
- Rule 30: **Evunzekibart** (therapeutic; all observed PDBs). Named antibody binding-domain structure with cached exact VH/VL match; the intact therapeutic is not implied. [Evidence](https://www.rcsb.org/structure/8OZ3).
- Rule 31: **Urelumab** (therapeutic; all observed PDBs). Named antibody binding-domain structure with cached exact VH/VL match; the intact therapeutic is not implied. [Evidence](https://www.rcsb.org/structure/6MHR).
- Rule 32: **Utomilumab** (therapeutic; all observed PDBs). Named antibody binding-domain structure with cached exact VH/VL match; the intact therapeutic is not implied. [Evidence](https://www.rcsb.org/structure/6A3W).
- Rule 33: **1618** (therapeutic; all observed PDBs). 1618 is the directly observed Fab in the structural work on ALG.APV-527; this is the anti-4-1BB binding domain, not a crystal of the complete 4-1BB x 5T4 bispecific. Merge the two source labels only. [Evidence](https://www.rcsb.org/structure/7YXU).
- Rule 34: **HZ-L-Yr-16** (therapeutic; all observed PDBs). Directly observed llama VHH used as the 4-1BB binding domain in the PM1003 development study; no claim that the entire bispecific is crystallized. [Evidence](https://www.rcsb.org/structure/7D4B).
- Rule 35: **BCY10916** (tool; 6y8k). 6Y8K identifies synthetic cyclic peptide BCY10916, a discovery binder used in TICA development, not a natural endogenous peptide. [Evidence](https://www.rcsb.org/structure/6Y8K).
- Rule 71: **Utomilumab** (therapeutic; 6a3w). Structure-scoped SAbDab source ID in a complex with one named antibody; deposited title/entity identity supports the same binding construct. Raw source ID and residues are preserved. [Evidence](https://www.rcsb.org/structure/6A3W).

### TIGIT — Q495A1

| Original named label | Original category | Representative PDB | Proposed identity/category |
|---|---|---|---|
| Ociperlimab | therapeutic | 8jel | Ociperlimab / therapeutic |
| Renvistobart | therapeutic | 8szy | Renvistobart / therapeutic |
| Tiragolumab | therapeutic | 8jeo | Tiragolumab / therapeutic |
| Vibostolimab | therapeutic | 8vtd | Vibostolimab / therapeutic |
| anti-TIGIT MG1131 | unclassified | 7vyt | MG1131 / tool |
| CHA.9.543 | unclassified | 8szy | CHA.9.543 / tool |
| NECTIN2 | unclassified | 5v52 | NECTIN2 / endogenous_large |
| PVR | unclassified | 3udw | PVR / endogenous_large |

Applied rule rationale and citation:

- Rule 36: **Ociperlimab** (therapeutic; all observed PDBs). Deposited antibody variable-domain contacts with exact VH/VL support; preserve distinct therapeutic identity and original construct metadata. [Evidence](https://www.rcsb.org/structure/8JEL).
- Rule 37: **Renvistobart** (therapeutic; all observed PDBs). Deposited antibody variable-domain contacts with exact VH/VL support; preserve distinct therapeutic identity and original construct metadata. [Evidence](https://www.rcsb.org/structure/8SZY).
- Rule 38: **Tiragolumab** (therapeutic; all observed PDBs). Deposited antibody variable-domain contacts with exact VH/VL support; preserve distinct therapeutic identity and original construct metadata. [Evidence](https://www.rcsb.org/structure/8JEO).
- Rule 39: **Vibostolimab** (therapeutic; all observed PDBs). Deposited antibody variable-domain contacts with exact VH/VL support; preserve distinct therapeutic identity and original construct metadata. [Evidence](https://www.rcsb.org/structure/8VTD).
- Rule 40: **MG1131** (tool; all observed PDBs). Primary study directly characterizes the MG1131 scFv as a preclinical research antibody; no clinical therapeutic identity is inferred. [Evidence](https://www.rcsb.org/structure/7VYT).
- Rule 41: **CHA.9.543** (tool; all observed PDBs). Distinct nonblocking anti-TIGIT Fab used to obtain the ternary crystal, on the opposing face from BMS-986207. Author AB/CD chains are CHA.9.543; HL/IM are renvistobart. Never merge these Fabs. [Evidence](https://www.rcsb.org/structure/8SZY).
- Rule 42: **NECTIN2** (endogenous_large; all observed PDBs). Natural cell-surface protein ligand with directly observed TIGIT-bound interface. [Evidence](https://www.rcsb.org/structure/5V52).
- Rule 43: **PVR** (endogenous_large; all observed PDBs). Natural cell-surface protein ligand with directly observed TIGIT-bound interface. [Evidence](https://www.rcsb.org/structure/3UDW).
- Rule 72: **Vibostolimab** (therapeutic; 8vtd). Structure-scoped SAbDab source ID in a complex with one named antibody; deposited title/entity identity supports the same binding construct. Raw source ID and residues are preserved. [Evidence](https://www.rcsb.org/structure/8VTD).

### CD27 — P26842

| Original named label | Original category | Representative PDB | Proposed identity/category |
|---|---|---|---|
| CD70 | endogenous_large | 7kx0 | CD70 / endogenous_large |
| Boserolimab | therapeutic | 8ds5 | Boserolimab / therapeutic |
| 2177 | unclassified | 5tl5 | M2177 / tool |
| H2191 | unclassified | 5tlk | H2191 / tool |
| M2177 | unclassified | 5tl5 | M2177 / tool |
| M2191 | unclassified | 5tlj | M2191 / tool |
| MK-5890 | unclassified | 8ds5 | Boserolimab / therapeutic |
| MK5890 | unclassified | 8ds5 | Boserolimab / therapeutic |

Applied rule rationale and citation:

- Rule 44: **CD70** (endogenous_large; all observed PDBs). Native TNFSF7/CD70 ligand; IUPHAR/PDBe source duplicate preserved as observations. [Evidence](https://www.rcsb.org/structure/7KX0).
- Rule 45: **Boserolimab** (therapeutic; all observed PDBs). NCI explicitly lists MK-5890/MK5890 as boserolimab names; 8DS5 is its Fab-CD27 complex. [Evidence](https://www.cancer.gov/publications/dictionaries/cancer-drug/def/boserolimab).
- Rule 46: **M2177** (tool; all observed PDBs). IEDB 2177 at 5TL5 and AACDB M2177 identify the same deposited antibody. 5TLJ/5TLK preserve the same clone in ternary complexes. [Evidence](https://www.rcsb.org/structure/5TL5).
- Rule 47: **M2191** (tool; all observed PDBs). Original M2191 research antibody; keep separate from humanized H2191 rather than collapsing related constructs. [Evidence](https://www.rcsb.org/structure/5TLJ).
- Rule 48: **H2191** (tool; all observed PDBs). Humanized H2191 research antibody; distinct construct from M2191 in 5TLJ. [Evidence](https://www.rcsb.org/structure/5TLK).
- Rule 73: **M2177** (tool; 5tl5). Structure-scoped SAbDab source ID in a complex with one named antibody; deposited title/entity identity supports the same binding construct. Raw source ID and residues are preserved. [Evidence](https://www.rcsb.org/structure/5TL5).

### BTLA — Q7Z6A9

| Original named label | Original category | Representative PDB | Proposed identity/category |
|---|---|---|---|
| Venanprubart | therapeutic | 8f6o | Venanprubart / therapeutic |
| 22B3 | unclassified | 8f6o | h22B3 / tool |
| 25F7 | unclassified | 8f6l | h25F7 / tool |
| h22B3 | unclassified | 8f6o | h22B3 / tool |
| h25F7 | unclassified | 8f6l | h25F7 / tool |
| r23C8 | unclassified | 8f60 | r23C8 / tool |
| TNFRSF14 | unclassified | 2aw2 | HVEM / receptor_partner |

Applied rule rationale and citation:

- Rule 49: **Venanprubart** (therapeutic; all observed PDBs). Cached exact VH/VL match to h22B3 in 8F6O; retain as a separately named therapeutic template-arm record. Primary clinical text also calls 22B3 a non-competing occupancy reagent, so do not assert whole-construct synonymy from sequence alone. [Evidence](https://www.rcsb.org/structure/8F6O).
- Rule 50: **h22B3** (tool; all observed PDBs). IEDB 22B3 and AACDB h22B3 refer here to the same humanized structural construct in 8F6O; remain separate from the venanprubart catalogue projection pending full-construct reconciliation. [Evidence](https://www.rcsb.org/structure/8F6O).
- Rule 51: **h25F7** (tool; all observed PDBs). IEDB 25F7 and AACDB h25F7 refer here to the same humanized structural construct in 8F6L. [Evidence](https://www.rcsb.org/structure/8F6L).
- Rule 52: **r23C8** (tool; all observed PDBs). Distinct BTLA antibody in the three-antibody structural study; keep separate from h22B3 and h25F7. [Evidence](https://www.rcsb.org/structure/8F60).
- Rule 53: **HVEM (TNFRSF14)** (receptor_partner; all observed PDBs). Natural cell-surface HVEM/BTLA receptor-partner interaction; not an antibody or small molecule. [Evidence](https://www.rcsb.org/structure/2AW2).
- Rule 74: **r23C8** (tool; 8f60). Structure-scoped SAbDab source ID in a complex with one named antibody; deposited title/entity identity supports the same binding construct. Raw source ID and residues are preserved. [Evidence](https://www.rcsb.org/structure/8F60).

### CD40LG — P29965

| Original named label | Original category | Representative PDB | Proposed identity/category |
|---|---|---|---|
| Ruplizumab | therapeutic | 1i9r | Ruplizumab / therapeutic |
| Tegoprubart | therapeutic | 1i9r | Tegoprubart / therapeutic |
| Velaprumig | therapeutic | 1i9r | Velaprumig / therapeutic |
| 5c8 | unclassified | 6w9g | 5c8* fluorescent variant / tool; parent 1I9R vs fluorescent 6W9G split |
| 5c8* | unclassified | 6w9g | 5c8* fluorescent variant / tool |
| 5c8* WH47L | unclassified | 7sgm | 5c8* WH47L / tool |
| CD40 | unclassified | 3qd6 | CD40 / receptor_partner |
| humanized 5c8 | unclassified | 1i9r | Ruplizumab / therapeutic |
| LKJ | unclassified | 3lkj | BIO8898 / tool |
| TNC | unclassified | 6brb | VIB4920-related Tn3 binding domain / therapeutic |

Applied rule rationale and citation:

- Rule 54: **Ruplizumab** (therapeutic; all observed PDBs). Humanized 5C8 parent binding domain in 1I9R matches ruplizumab. Deliberately do not match raw 5C8 Fab globally: that normalized label also names an engineered fluorescent construct at 6W9G. [Evidence](https://www.rcsb.org/structure/1I9R).
- Rule 55: **Tegoprubart** (therapeutic; all observed PDBs). Cached exact variable-domain match to the humanized 5C8 Fab template. Preserve the distinct therapeutic; the deposited Fab does not establish crystallization of the complete named therapeutic. [Evidence](https://www.rcsb.org/structure/1I9R).
- Rule 56: **Velaprumig** (therapeutic; all observed PDBs). Cached exact variable-domain match to the humanized 5C8 Fab template. Preserve the distinct therapeutic; the deposited Fab does not establish crystallization of the complete named therapeutic. [Evidence](https://www.rcsb.org/structure/1I9R).
- Rule 57: **5c8* fluorescent variant** (tool; all observed PDBs). Engineered fluorescent noncanonical-amino-acid 5c8* construct, not the parent humanized 5C8 therapeutic; keep separate from WH47L. [Evidence](https://www.rcsb.org/structure/6W9G).
- Rule 58: **5c8* WH47L** (tool; all observed PDBs). Distinct fluorescent 5c8* W47L heavy-chain variant characterized for blocked excited-state proton transfer; not parent 5C8 or unmodified 5c8*. [Evidence](https://www.rcsb.org/structure/7SGM).
- Rule 59: **CD40** (receptor_partner; all observed PDBs). Natural receptor partner of CD40LG/CD154 with directly observed complex. [Evidence](https://www.rcsb.org/structure/3QD6).
- Rule 60: **BIO8898** (tool; all observed PDBs). PDB ligand LKJ is synthetic inhibitor BIO8898; primary study establishes CD40L binding through trimer subunit fracture. Not an endogenous small molecule. [Evidence](https://www.rcsb.org/structure/3LKJ).
- Rule 61: **VIB4920-related Tn3 binding domain** (therapeutic; 6brb). 6BRB deposits an engineered Tn3-like scaffold and cites the VIB4920 clinical development paper. The UniProt scaffold-parent mapping is not evidence for natural tenascin-C binding CD40L; this is a binding-domain construct, not the full therapeutic. [Evidence](https://www.rcsb.org/structure/6BRB).
- Rule 65: **Ruplizumab** (therapeutic; 1i9r). 1I9R is the humanized 5C8 parent Fab, supported by exact VH/VL match to ruplizumab; scope is required because casefolded 5c8 also names an engineered construct. [Evidence](https://www.rcsb.org/structure/1I9R).
- Rule 66: **5c8* fluorescent variant** (tool; 6w9g). 6W9G specifically deposits the fluorescent noncanonical-amino-acid 5c8* variant; source shorthand 5c8 must not collapse this into parent humanized 5C8. [Evidence](https://www.rcsb.org/structure/6W9G).
- Rule 75: **5c8* fluorescent variant** (tool; 6w9g). Structure-scoped SAbDab source ID in a complex with one named antibody; deposited title/entity identity supports the same binding construct. Raw source ID and residues are preserved. [Evidence](https://www.rcsb.org/structure/6W9G).

## All-observation provenance audit

The unchanged input contains every residue array. The audit below inventories every unique source/raw-label/PDB group, including records omitted from the named overview. The count column sums to all original observations.


### CTLA4 raw observation groups

| Source | Raw partner | Source display label | PDB | Context | Observations | Proposed display |
|---|---|---|---|---|---:|---|
| AACDB | 7ELX Fab |  | 7elx | extracellular_explicit | 2 | Unresolved Fab 7ELX |
| AACDB | HL32 Fab |  | 6xy2 | extracellular_explicit | 1 | Gotistobart |
| AACDB | Ipilimumab Fab |  | 5tru | extracellular_explicit | 2 | Ipilimumab |
| AACDB | Ipilimumab Fab |  | 6rp8 | extracellular_explicit | 2 | Ipilimumab |
| AACDB | Ipilimumab Fab |  | 7su0 | extracellular_explicit | 2 | Ipi.105 |
| AACDB | Ipilimumab Fab |  | 7su1 | extracellular_explicit | 1 | Ipi.106 |
| AACDB | blocking-KN044 Nanobody |  | 6rqm | extracellular_explicit | 1 | KN044 nanobody |
| AACDB | ipilimumab Fv |  | 5xj3 | extracellular_explicit | 4 | Ipilimumab |
| AACDB | non-blocking-CTLA-4 Nanobody |  | 6rpj | extracellular_explicit | 1 | non-blocking-CTLA-4 Nanobody |
| AACDB | tremelimumab Fab |  | 5ggv | extracellular_explicit | 1 | Tremelimumab |
| IEDB | 1230 | tremelimumab, CP-675, CP-675206, ticilimumab |  | extracellular_explicit | 3 | Tremelimumab |
| IEDB | 1230 | tremelimumab, CP-675, CP-675206, ticilimumab | 5ggv | extracellular_explicit | 1 | Tremelimumab |
| IEDB | 18356 | ipilimumab | 5tru | extracellular_explicit | 1 | Ipilimumab |
| IEDB | 18356 | ipilimumab | 5xj3 | extracellular_explicit | 1 | Ipilimumab |
| IEDB | 197603 | JS007 | 8hit | extracellular_explicit | 1 | JS007 |
| IEDB | 208925 | HL32 | 6xy2 | extracellular_explicit | 1 | Gotistobart |
| IEDB | 209190 | mipi.4 | 9dq3 | extracellular_explicit | 1 | mipi.4 |
| PDB/PDBe | P27986 |  | 7cio | non_extracellular:cytoplasmic | 1 | P27986 |
| PDB/PDBe | P33681 | CD80 | 1i8l | extracellular_explicit | 1 | CD80 |
| PDB/PDBe | P42081 | CD86 | 1i85 | extracellular_explicit | 1 | CD86 |
| PDB/PDBe | Q96CW1 | AP2M1 | 1h6e | non_extracellular:cytoplasmic | 1 | AP2M1 |
| SAbDab | sabdab2_H051TL03VW | sabdab2_H051TL03VW (FAB) | 9dq3 | extracellular_explicit | 1 | mipi.4 |
| Thera-SAbDab | Danvilostomig |  | 5tru | extracellular_explicit | 2 | Danvilostomig |
| Thera-SAbDab | Danvilostomig |  | 5xj3 | extracellular_explicit | 4 | Danvilostomig |
| Thera-SAbDab | Danvilostomig |  | 6rp8 | extracellular_explicit | 2 | Danvilostomig |
| Thera-SAbDab | Danvilostomig |  | 7elx | extracellular_explicit | 2 | Danvilostomig |
| Thera-SAbDab | Erfonrilimab |  | 6rqm | extracellular_explicit | 1 | Erfonrilimab |
| Thera-SAbDab | Gotistobart |  | 6xy2 | extracellular_explicit | 1 | Gotistobart |
| Thera-SAbDab | Ipilimumab |  | 5tru | extracellular_explicit | 2 | Ipilimumab |
| Thera-SAbDab | Ipilimumab |  | 5xj3 | extracellular_explicit | 4 | Ipilimumab |
| Thera-SAbDab | Ipilimumab |  | 6rp8 | extracellular_explicit | 2 | Ipilimumab |
| Thera-SAbDab | Ipilimumab |  | 7elx | extracellular_explicit | 2 | Ipilimumab |
| Thera-SAbDab | Porustobart |  | 7dv4 | extracellular_explicit | 5 | Porustobart |
| Thera-SAbDab | Sovipostobart |  | 5tru | extracellular_explicit | 2 | Sovipostobart |
| Thera-SAbDab | Sovipostobart |  | 5xj3 | extracellular_explicit | 4 | Sovipostobart |
| Thera-SAbDab | Sovipostobart |  | 6rp8 | extracellular_explicit | 2 | Sovipostobart |
| Thera-SAbDab | Sovipostobart |  | 7elx | extracellular_explicit | 2 | Sovipostobart |
| Thera-SAbDab | Tazlestobart |  | 5tru | extracellular_explicit | 2 | Tazlestobart |
| Thera-SAbDab | Tazlestobart |  | 5xj3 | extracellular_explicit | 4 | Tazlestobart |
| Thera-SAbDab | Tazlestobart |  | 6rp8 | extracellular_explicit | 2 | Tazlestobart |
| Thera-SAbDab | Tazlestobart |  | 7elx | extracellular_explicit | 2 | Tazlestobart |
| Thera-SAbDab | Tremelimumab |  | 5ggv | extracellular_explicit | 1 | Tremelimumab |
| Thera-SAbDab | Volrustomig |  | 5ggv | extracellular_explicit | 1 | Volrustomig |

### CD40 raw observation groups

| Source | Raw partner | Source display label | PDB | Context | Observations | Proposed display |
|---|---|---|---|---|---:|---|
| AACDB | 3H56-5 VH-sdAb |  | 5dmj | extracellular_explicit | 2 | 3H56-5 |
| AACDB | 3H56-5 VH-sdAb |  | 5ihl | extracellular_explicit | 4 | 3H56-5 |
| AACDB | 516 Fab |  | 6pe9 | extracellular_explicit | 3 | FAB516 |
| AACDB | ABBV-323 Fab |  | 6pe8 | extracellular_explicit | 2 | Ravagalimab |
| AACDB | Chi220 Fab |  | 5dmi | extracellular_explicit | 1 | Teneliximab |
| AACDB | Lob 7.4 Fab |  | 6fax | extracellular_explicit | 1 | ChiLob 7/4 |
| IEDB | 1203 | Chi220 | 5dmi | extracellular_explicit | 1 | Teneliximab |
| IEDB | 18496 | ChiLob 7/4 | 6fax | extracellular_explicit | 1 | ChiLob 7/4 |
| IEDB | 197330 | ABBV-323 | 6pe8 | extracellular_explicit | 1 | Ravagalimab |
| IEDB | 197330 | FAB516 | 6pe9 | extracellular_explicit | 1 | FAB516 |
| IEDB | 2182 | 3h56-5 | 5dmj | extracellular_explicit | 1 | 3H56-5 |
| IEDB | 2182 | 3h56-5 | 5ihl | extracellular_explicit | 1 | 3H56-5 |
| IUPHAR+PDBe | GTOPDB:5077 | CD40 ligand (CD40LG) | 3qd6 | extracellular_explicit | 1 | CD40 ligand |
| PDB/PDBe | P29965 | CD40 ligand (CD40LG) | 3qd6 | extracellular_explicit | 1 | CD40 ligand |
| PDB/PDBe | Q12933 |  | 1czz | non_extracellular:cytoplasmic | 1 | Q12933 |
| PDB/PDBe | Q12933 |  | 1d00 | non_extracellular:cytoplasmic | 1 | Q12933 |
| PDB/PDBe | Q13114 |  | 1fll | non_extracellular:cytoplasmic | 1 | Q13114 |
| PDB/PDBe | Q9Y4K3 |  | 1lb6 | non_extracellular:cytoplasmic | 1 | Q9Y4K3 |
| SAbDab | sabdab2_H04Y3L03S6 | sabdab2_H04Y3L03S6 (FAB) | 8yx1 | extracellular_explicit | 1 | Bleselumab |
| Thera-SAbDab | Bleselumab |  | 8yx1 | extracellular_explicit | 2 | Bleselumab |
| Thera-SAbDab | Cifurtilimab |  | 8yx9 | extracellular_explicit | 2 | Cifurtilimab |
| Thera-SAbDab | Dacetuzumab |  | 8yx9 | extracellular_explicit | 2 | Dacetuzumab |
| Thera-SAbDab | Ravagalimab |  | 6pe8 | extracellular_explicit | 2 | Ravagalimab |
| Thera-SAbDab | Teneliximab |  | 5dmi | extracellular_explicit | 1 | Teneliximab |

### TNFRSF4 raw observation groups

| Source | Raw partner | Source display label | PDB | Context | Observations | Proposed display |
|---|---|---|---|---|---:|---|
| AACDB | 1A7 Fab |  | 6okn | extracellular_explicit | 2 | Vonlerolizumab |
| AACDB | 3C8 Fab |  | 6okm | extracellular_explicit | 1 | 3C8 |
| AACDB | 6OGX_1 Fab |  | 6ogx | extracellular_explicit | 1 | Vonlerolizumab |
| AACDB | 6OGX_2 Fab |  | 6ogx | extracellular_explicit | 1 | 3C8 |
| IEDB | 197309 | Ab1 | 6ogx | extracellular_explicit | 1 | Vonlerolizumab |
| IEDB | 197309 | Ab1 | 6okn | extracellular_explicit | 1 | Vonlerolizumab |
| IEDB | 197310 | Ab2 | 6ogx | extracellular_explicit | 1 | 3C8 |
| IEDB | 197310 | Ab2 | 6okm | extracellular_explicit | 1 | 3C8 |
| IEDB | 208909 | RG7888 | 7yk4 | extracellular_explicit | 1 | Vonlerolizumab |
| IEDB | 208917 | DF004 | 8ag1 | extracellular_explicit | 1 | DF004 |
| IUPHAR+PDBe | GTOPDB:5076 | OX-40 ligand (TNFSF4) | 2hev | extracellular_explicit | 1 | OX-40 ligand |
| PDB/PDBe | P23510 | OX-40 ligand (TNFSF4) | 2hev | extracellular_explicit | 1 | OX-40 ligand |
| PDB/PDBe | P43488 |  | 2hey | extracellular_explicit | 1 | Murine OX40L |
| PDB/PDBe | Q12933 |  | 1d0a | non_extracellular:cytoplasmic | 1 | Q12933 |
| SAbDab | sabdab2_H020YL01MJ | sabdab2_H020YL01MJ (FAB) | 6okm | extracellular_explicit | 1 | 3C8 |
| Thera-SAbDab | Vonlerolizumab |  | 6ogx | extracellular_explicit | 1 | Vonlerolizumab |
| Thera-SAbDab | Vonlerolizumab |  | 6okn | extracellular_explicit | 2 | Vonlerolizumab |
| Thera-SAbDab | Vonlerolizumab |  | 7yk4 | extracellular_explicit | 2 | Vonlerolizumab |

### TNFRSF9 raw observation groups

| Source | Raw partner | Source display label | PDB | Context | Observations | Proposed display |
|---|---|---|---|---|---:|---|
| AACDB | 1618 Fab |  | 7yxu | extracellular_explicit | 1 | 1618 |
| AACDB | Urelumab Fab |  | 6mhr | extracellular_explicit | 2 | Urelumab |
| AACDB | Utomilumab Fab |  | 6mi2 | extracellular_explicit | 2 | Utomilumab |
| AACDB | utomilumab Fv |  | 6a3w | extracellular_explicit | 4 | Utomilumab |
| BioLiP | peptide |  | 6y8k | extracellular_explicit | 1 | BCY10916 |
| IEDB | 196765 | Fab1618 | 7yxu | extracellular_explicit | 1 | 1618 |
| IEDB | 197111 | urelumab | 6mhr | extracellular_explicit | 1 | Urelumab |
| IEDB | 197118 | utomilumab | 6mi2 | extracellular_explicit | 1 | Utomilumab |
| IEDB | 207757 | utomilumab | 6a3w | extracellular_explicit | 1 | Utomilumab |
| IEDB | 209605 | HZ-L-Yr-16 | 7d4b | extracellular_explicit | 1 | HZ-L-Yr-16 |
| IUPHAR+PDBe | GTOPDB:5081 | 4-1BB ligand (TNFSF9) | 6a3v | extracellular_explicit | 1 | 4-1BB ligand |
| IUPHAR+PDBe | GTOPDB:5081 | 4-1BB ligand (TNFSF9) | 6bwv | extracellular_explicit | 1 | 4-1BB ligand |
| IUPHAR+PDBe | GTOPDB:5081 | 4-1BB ligand (TNFSF9) | 6cpr | extracellular_explicit | 1 | 4-1BB ligand |
| IUPHAR+PDBe | GTOPDB:5081 | 4-1BB ligand (TNFSF9) | 6cu0 | extracellular_explicit | 1 | 4-1BB ligand |
| IUPHAR+PDBe | GTOPDB:5081 | 4-1BB ligand (TNFSF9) | 6mgp | extracellular_explicit | 1 | 4-1BB ligand |
| PDB/PDBe | P41273 | 4-1BB ligand (TNFSF9) | 6a3v | extracellular_explicit | 1 | 4-1BB ligand |
| PDB/PDBe | P41273 | 4-1BB ligand (TNFSF9) | 6bwv | extracellular_explicit | 1 | 4-1BB ligand |
| PDB/PDBe | P41273 | 4-1BB ligand (TNFSF9) | 6cpr | extracellular_explicit | 1 | 4-1BB ligand |
| PDB/PDBe | P41273 | 4-1BB ligand (TNFSF9) | 6cu0 | extracellular_explicit | 1 | 4-1BB ligand |
| PDB/PDBe | P41273 | 4-1BB ligand (TNFSF9) | 6mgp | extracellular_explicit | 1 | 4-1BB ligand |
| SAbDab | sabdab2_H01W8L01GX | sabdab2_H01W8L01GX (FV) | 6a3w | extracellular_explicit | 1 | Utomilumab |
| Thera-SAbDab | Evunzekibart |  | 8oz3 | extracellular_explicit | 2 | Evunzekibart |
| Thera-SAbDab | Urelumab |  | 6mhr | extracellular_explicit | 2 | Urelumab |
| Thera-SAbDab | Utomilumab |  | 6a3w | extracellular_explicit | 4 | Utomilumab |
| Thera-SAbDab | Utomilumab |  | 6mi2 | extracellular_explicit | 2 | Utomilumab |

### TIGIT raw observation groups

| Source | Raw partner | Source display label | PDB | Context | Observations | Proposed display |
|---|---|---|---|---|---:|---|
| AACDB | CHA.9.543 Fab |  | 8szy | extracellular_explicit | 1 | CHA.9.543 |
| AACDB | anti-TIGIT MG1131 Fv |  | 7vyt | extracellular_explicit | 2 | MG1131 |
| IEDB | 209586 | vibostolimab | 8vtd | extracellular_explicit | 1 | Vibostolimab |
| IEDB | 209587 | tiragolumab | 8vte | extracellular_explicit | 1 | Tiragolumab |
| PDB/PDBe | P15151 | PVR | 3udw | extracellular_explicit | 1 | PVR |
| PDB/PDBe | Q92692 | NECTIN2 | 5v52 | extracellular_explicit | 1 | NECTIN2 |
| SAbDab | sabdab2_H04HAL03G4 | sabdab2_H04HAL03G4 (FAB) | 8vtd | extracellular_explicit | 1 | Vibostolimab |
| Thera-SAbDab | Ociperlimab |  | 8jel | extracellular_explicit | 2 | Ociperlimab |
| Thera-SAbDab | Ociperlimab |  | 8jen | extracellular_explicit | 2 | Ociperlimab |
| Thera-SAbDab | Renvistobart |  | 8szy | extracellular_explicit | 2 | Renvistobart |
| Thera-SAbDab | Tiragolumab |  | 8jeo | extracellular_explicit | 2 | Tiragolumab |
| Thera-SAbDab | Tiragolumab |  | 8vte | extracellular_explicit | 2 | Tiragolumab |
| Thera-SAbDab | Vibostolimab |  | 8vtd | extracellular_explicit | 1 | Vibostolimab |

### CD27 raw observation groups

| Source | Raw partner | Source display label | PDB | Context | Observations | Proposed display |
|---|---|---|---|---|---:|---|
| AACDB | H2191 Fab |  | 5tlk | extracellular_explicit | 2 | H2191 |
| AACDB | M2177 Fab |  | 5tl5 | extracellular_explicit | 1 | M2177 |
| AACDB | M2177 Fab |  | 5tlj | extracellular_explicit | 1 | M2177 |
| AACDB | M2177 Fab |  | 5tlk | extracellular_explicit | 2 | M2177 |
| AACDB | M2191 Fab |  | 5tlj | extracellular_explicit | 1 | M2191 |
| AACDB | MK5890 Fab |  | 8ds5 | extracellular_explicit | 1 | Boserolimab |
| IEDB | 1022 | M2177 | 5tlj | extracellular_explicit | 1 | M2177 |
| IEDB | 1022 | M2177 | 5tlk | extracellular_explicit | 1 | M2177 |
| IEDB | 1023 | M2191 | 5tlj | extracellular_explicit | 1 | M2191 |
| IEDB | 18360 | 2177 | 5tl5 | extracellular_explicit | 1 | M2177 |
| IEDB | 197504 | MK-5890 | 8ds5 | extracellular_explicit | 1 | Boserolimab |
| IEDB | 949 | H2191 | 5tlk | extracellular_explicit | 1 | H2191 |
| IUPHAR+PDBe | GTOPDB:5079 | CD70 | 7kx0 | extracellular_explicit | 1 | CD70 |
| PDB/PDBe | P32970 | CD70 | 7kx0 | extracellular_explicit | 1 | CD70 |
| SAbDab | sabdab2_H01EQL0173 | sabdab2_H01EQL0173 (FAB) | 5tl5 | extracellular_explicit | 1 | M2177 |
| Thera-SAbDab | Boserolimab |  | 8ds5 | extracellular_explicit | 1 | Boserolimab |

### BTLA raw observation groups

| Source | Raw partner | Source display label | PDB | Context | Observations | Proposed display |
|---|---|---|---|---|---:|---|
| AACDB | h22B3 Fab |  | 8f6o | extracellular_explicit | 1 | h22B3 |
| AACDB | h25F7 Fab |  | 8f6l | extracellular_explicit | 1 | h25F7 |
| IEDB | 197662 | r23C8 | 8f60 | extracellular_explicit | 1 | r23C8 |
| IEDB | 197663 | 25F7 | 8f6l | extracellular_explicit | 1 | h25F7 |
| IEDB | 197667 | 22B3 | 8f6o | extracellular_explicit | 1 | h22B3 |
| PDB/PDBe | Q92956 | TNFRSF14 | 2aw2 | extracellular_explicit | 1 | HVEM |
| SAbDab | sabdab2_H03S0L02YG | sabdab2_H03S0L02YG (FAB) | 8f60 | extracellular_explicit | 1 | r23C8 |
| Thera-SAbDab | Venanprubart |  | 8f6o | extracellular_explicit | 1 | Venanprubart |

### CD40LG raw observation groups

| Source | Raw partner | Source display label | PDB | Context | Observations | Proposed display |
|---|---|---|---|---|---:|---|
| AACDB | 5C8 Fab |  | 1i9r | extracellular_explicit | 1 | Ruplizumab |
| AACDB | 5c8 Fab |  | 6w9g | extracellular_explicit | 2 | 5c8* fluorescent variant |
| AACDB | 5c8* WH47L Fab |  | 7sgm | extracellular_explicit | 3 | 5c8* WH47L |
| BioLiP | LKJ |  | 3lkj | extracellular_explicit | 1 | BIO8898 |
| IEDB | 197456 | 5c8* | 6w9g | extracellular_explicit | 1 | 5c8* fluorescent variant |
| IEDB | 917 | humanized 5c8 | 1i9r | extracellular_explicit | 1 | Ruplizumab |
| PDB/PDBe | P24821 | TNC | 6brb | extracellular_explicit | 1 | VIB4920-related Tn3 binding domain |
| PDB/PDBe | P25942 | CD40 | 3qd6 | extracellular_explicit | 1 | CD40 |
| SAbDab | sabdab2_H001ML01EN | sabdab2_H001ML01EN (FAB) | 6w9g | extracellular_explicit | 1 | 5c8* fluorescent variant |
| Thera-SAbDab | Ruplizumab |  | 1i9r | extracellular_explicit | 1 | Ruplizumab |
| Thera-SAbDab | Tegoprubart |  | 1i9r | extracellular_explicit | 1 | Tegoprubart |
| Thera-SAbDab | Velaprumig |  | 1i9r | extracellular_explicit | 1 | Velaprumig |

## Evidence files

`checkpoints/` contains all 73 queried PDB entry JSONs, focused polymer-entity metadata, the unchanged relevant AACDB/Thera match rows, and the generation/validation helper files. Each entry can be re-fetched at `https://data.rcsb.org/rest/v1/core/entry/{pdb}`; polymer entities at `https://data.rcsb.org/rest/v1/core/polymer_entity/{pdb}/{entity_id}`. The primary citation DOI/PMID is retained in each entry JSON. No paid model, private database, or production write was used.
