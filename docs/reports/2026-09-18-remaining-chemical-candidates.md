# Remaining chemical-contact candidates: bounded manual review

Pinned baseline `contacts-b960b69373f6486dc9e9`: **89** unique uncovered chemical-contact targets minus **15** previously reviewed EC targets = **74** targets, **171** source records. All 74 receive an individual disposition; no rules or assets are changed.

**28 proposals across 19 targets** are offered for independent coordinate/canonical-sequence validation. These are recommendations, not accepted footprints. One representative PDB per chemical is prioritized. Repeated deposits remain in the ledger.

## Limits

- Screening recommendations only: no coordinates, SIFTS chain identity, canonical sequence/mutation checks, or contact footprints validated here.
- Source topology is preserved, not converted into extracellular accessibility. Several targets are organellar transporters or intracellular domains.
- RCSB entry/CCD metadata corroborates identity and experimental purpose; a CCD in a paper title is never substituted for another source CCD.
- A native chemical name/category does not assert physiological exposure, efficacy, affinity, or that the exact lipid acyl species is the principal in vivo ligand.
- All nonrecommended rows remain explicit holds; no source observation is deleted.

## Strongest explicit pairs

| Accession | CCD | PDB | Name | Category |
|---|---|---|---|---|
| Q16572 | ACH | [8XTW](https://www.rcsb.org/structure/8XTW) | Acetylcholine | endogenous_small |
| O75751 | C0R | [7ZH6](https://www.rcsb.org/structure/7ZH6) | Corticosterone | endogenous_small |
| O76082 | X8M | [9PFB](https://www.rcsb.org/structure/9PFB) | Ipratropium | therapeutic |
| O76082 | 152 | [9PDQ](https://www.rcsb.org/structure/9PDQ) | Carnitine | endogenous_small |
| Q4U2R8 | 5HG | [9M9V](https://www.rcsb.org/structure/9M9V) | Adefovir | therapeutic |
| Q4U2R8 | L8P | [9J04](https://www.rcsb.org/structure/9J04) | Cidofovir | therapeutic |
| Q4U2R8 | GBM | [9J06](https://www.rcsb.org/structure/9J06) | Glibenclamide | therapeutic |
| Q4U2R8 | OLM | [9KLZ](https://www.rcsb.org/structure/9KLZ) | Olmesartan | therapeutic |
| P50443 | OXL | [8TNX](https://www.rcsb.org/structure/8TNX) | Oxalate | endogenous_small |
| Q9Y289 | BTN | [26VA](https://www.rcsb.org/structure/26VA) | Biotin | endogenous_small |
| Q9Y289 | LPA | [26VC](https://www.rcsb.org/structure/26VC) | Alpha-lipoic acid | endogenous_small |
| P48065 | BET | [9W99](https://www.rcsb.org/structure/9W99) | Betaine | endogenous_small |
| P48065 | ABU | [9W9A](https://www.rcsb.org/structure/9W9A) | GABA | endogenous_small |
| P48029 | CRN | [9V8X](https://www.rcsb.org/structure/9V8X) | Creatine | endogenous_small |
| Q9NYB5 | T44 | [9DXP](https://www.rcsb.org/structure/9DXP) | L-thyroxine | endogenous_small |
| Q8TF71 | T44 | [9GSZ](https://www.rcsb.org/structure/9GSZ) | L-thyroxine | endogenous_small |
| Q7Z2H8 | 4AX | [9V3V](https://www.rcsb.org/structure/9V3V) | D-cycloserine | therapeutic |
| Q6NT16 | SPD | [9D7V](https://www.rcsb.org/structure/9D7V) | Spermidine | endogenous_small |
| Q6NT16 | SPM | [9D7X](https://www.rcsb.org/structure/9D7X) | Spermine | endogenous_small |
| P09769 | VSE | [7UY0](https://www.rcsb.org/structure/7UY0) | A-419259 | tool |
| Q13393 | MKG | [6OHR](https://www.rcsb.org/structure/6OHR) | PLD1 inhibitor compound 5 (CCD MKG) | tool |
| O00400 | ACO | [9M0S](https://www.rcsb.org/structure/9M0S) | Acetyl-CoA | endogenous_small |
| O00400 | GDS | [9MUN](https://www.rcsb.org/structure/9MUN) | Oxidized glutathione | endogenous_small |
| Q8N323 | ACO | [9PJA](https://www.rcsb.org/structure/9PJA) | Acetyl-CoA | endogenous_small |
| Q5U3C3 | LPC | [9LW1](https://www.rcsb.org/structure/9LW1) | 1-myristoyl lysophosphatidylcholine | endogenous_small |
| O14494 | NKO | [9L0O](https://www.rcsb.org/structure/9L0O) | 1-palmitoyl lysophosphatidic acid | endogenous_small |
| Q9BY76 | PLM | [6U1U](https://www.rcsb.org/structure/6U1U) | Palmitic acid | endogenous_small |
| Q9BY76 | MYR | [6U73](https://www.rcsb.org/structure/6U73) | Myristic acid | endogenous_small |

## Every-target disposition ledger

Each source row below retains its exact CCD, PDB, topology, primary entry title and reason in the accompanying JSON. Primary entry metadata and CCD metadata were checked; contact-specific mutations still require the independent coordinate validator. This is a manual review of the bounded input chemicals, not a search for other ligands in the same structures.

### KCNK1 — O00180

1 source records; 1 CCD identities. Undecane hydrocarbon membrane model, not independently supported pharmacological ligand.

- CCD:UND / [3UKM](https://www.rcsb.org/structure/3UKM): **hold_hydrocarbon_or_partial_lipid_model**; source topology `transmembrane`. Primary entry: Crystal structure of the human two pore domain potassium ion channel K2P1 (TWIK-1). CCD: UNDECANE.

### SLC33A1 — O00400

2 source records; 2 CCD identities. Separate oxidized glutathione 9MUN and acetyl-CoA 9M0S transport complexes explicitly supported by primary studies; ER transporter topology must not imply cell-surface exposure.

- CCD:ACO / [9M0S](https://www.rcsb.org/structure/9M0S): **promotion_candidate**; source topology `mixed:cytoplasmic;extracellular;transmembrane`. Primary entry: Acetyl-CoA-bound SLC33A1 in a cytoplasm-facing conformation. CCD: ACETYL COENZYME *A.
- CCD:GDS / [9MUN](https://www.rcsb.org/structure/9MUN): **promotion_candidate**; source topology `mixed:cytoplasmic;extracellular;transmembrane`. Primary entry: Structure of Human SLC33A1 in complex with oxidized glutathione. CCD: OXIDIZED GLUTATHIONE DISULFIDE.

### PLPP1 — O14494

7 source records; 3 CCD identities. 9L0O specifically LPA-bound PLPP1: NKO is palmitoyl lysophosphatidic acid. LPP is different dipalmitoyl phosphatidic acid; AV0 detergent. Prioritize NKO substrate only.

- CCD:AV0 / [9L0U](https://www.rcsb.org/structure/9L0U): **hold_preparation_additive**; source topology `mixed:extracellular;transmembrane`. Primary entry: Cryo-EM structure of human lipid phosphate phosphatase 1 complexed with PO4.MAG. CCD: Lauryl Maltose Neopentyl Glycol.
- CCD:LPP / [9L0I](https://www.rcsb.org/structure/9L0I): **hold_lipid_or_chemical_specificity_unresolved**; source topology `mixed:extracellular;transmembrane`. Primary entry: Cryo-EM structure of human lipid phosphate phosphatase 1. CCD: 2-(HEXADECANOYLOXY)-1-[(PHOSPHONOOXY)METHYL]ETHYL HEXADECANOATE.
- CCD:LPP / [9L0O](https://www.rcsb.org/structure/9L0O): **hold_lipid_or_chemical_specificity_unresolved**; source topology `mixed:extracellular;transmembrane`. Primary entry: Cryo-EM structure of human lipid phosphate phosphatase 1 complexed with LPA. CCD: 2-(HEXADECANOYLOXY)-1-[(PHOSPHONOOXY)METHYL]ETHYL HEXADECANOATE.
- CCD:LPP / [9L0S](https://www.rcsb.org/structure/9L0S): **hold_lipid_or_chemical_specificity_unresolved**; source topology `mixed:extracellular;transmembrane`. Primary entry: Cryo-EM structure of human lipid phosphate phosphatase 1 complexed with VO4. CCD: 2-(HEXADECANOYLOXY)-1-[(PHOSPHONOOXY)METHYL]ETHYL HEXADECANOATE.
- CCD:LPP / [9L0U](https://www.rcsb.org/structure/9L0U): **hold_lipid_or_chemical_specificity_unresolved**; source topology `mixed:extracellular;transmembrane`. Primary entry: Cryo-EM structure of human lipid phosphate phosphatase 1 complexed with PO4.MAG. CCD: 2-(HEXADECANOYLOXY)-1-[(PHOSPHONOOXY)METHYL]ETHYL HEXADECANOATE.
- CCD:LPP / [9VL3](https://www.rcsb.org/structure/9VL3): **hold_lipid_or_chemical_specificity_unresolved**; source topology `mixed:extracellular;transmembrane`. Primary entry: Cryo-EM structure of human lipid phosphate phosphatase 1 complexed with PO4 in nanodiscs. CCD: 2-(HEXADECANOYLOXY)-1-[(PHOSPHONOOXY)METHYL]ETHYL HEXADECANOATE.
- CCD:NKO / [9L0O](https://www.rcsb.org/structure/9L0O): **promotion_candidate**; source topology `mixed:extracellular;transmembrane`. Primary entry: Cryo-EM structure of human lipid phosphate phosphatase 1 complexed with LPA. CCD: (2R)-2-hydroxy-3-(phosphonooxy)propyl hexadecanoate.

### PLPP3 — O14495

1 source records; 1 CCD identities. Dilauroyl PA is a short-chain/model phosphatase substrate candidate; generic title insufficient to establish exact biological versus preparation role.

- CCD:PX2 / [25QP](https://www.rcsb.org/structure/25QP): **hold_specific_ligand_needs_context_or_construct_review**; source topology `mixed:extracellular;transmembrane`. Primary entry: Cryo-EM Structure of PLPP3. CCD: 1,2-DILAUROYL-SN-GLYCERO-3-PHOSPHATE.

### PTPRT — O14522

1 source records; 1 CCD identities. BisTris propane buffer in PTPRT catalytic-domain structure.

- CCD:B3P / [2OOQ](https://www.rcsb.org/structure/2OOQ): **hold_preparation_additive**; source topology `cytoplasmic`. Primary entry: Crystal Structure of the Human Receptor Phosphatase PTPRT. CCD: 2-[3-(2-HYDROXY-1,1-DIHYDROXYMETHYL-ETHYLAMINO)-PROPYLAMINO]-2-HYDROXYMETHYL-PROPANE-1,3-DIOL.

### PLPP2 — O43688

1 source records; 1 CCD identities. Palmitoyl-linoleoyl-PC is not phosphatidic acid substrate; membrane lipid held.

- CCD:CPL / [21NW](https://www.rcsb.org/structure/21NW): **hold_lipid_or_chemical_specificity_unresolved**; source topology `mixed:lumenal;transmembrane`. Primary entry: Cryo-EM structure of human Lipid Phosphate Phosphatase 2. CCD: 1-PALMITOYL-2-LINOLEOYL-SN-GLYCERO-3-PHOSPHOCHOLINE.

### SMPD2 — O60906

2 source records; 2 CCD identities. Tetradecane and heptane hydrocarbon fragments do not independently identify intact sphingomyelin substrate.

- CCD:C14 / [8J2F](https://www.rcsb.org/structure/8J2F): **hold_hydrocarbon_or_partial_lipid_model**; source topology `mixed:transmembrane;unknown`. Primary entry: Human neutral shpingomyelinase. CCD: TETRADECANE.
- CCD:HP6 / [8J2F](https://www.rcsb.org/structure/8J2F): **hold_hydrocarbon_or_partial_lipid_model**; source topology `mixed:transmembrane;unknown`. Primary entry: Human neutral shpingomyelinase. CCD: HEPTANE.

### KCNJ13 — O60928

5 source records; 2 CCD identities. PIO is short-chain PIP2 model in Kir7.1; supported regulation but distinguish synthetic acyl chains from native PIP2 and from steroid named in 9PR7.

- CCD:CLR / [9PR5](https://www.rcsb.org/structure/9PR5): **hold_lipid_or_chemical_specificity_unresolved**; source topology `mixed:transmembrane;unknown`. Primary entry: Cryo-EM structure of the human inward-rectifier potassium 7.1 channel (Kir7.1) extended state. CCD: CHOLESTEROL.
- CCD:PIO / [9PR5](https://www.rcsb.org/structure/9PR5): **hold_specific_ligand_needs_context_or_construct_review**; source topology `mixed:cytoplasmic;transmembrane`. Primary entry: Cryo-EM structure of the human inward-rectifier potassium 7.1 channel (Kir7.1) extended state. CCD: [(2R)-2-octanoyloxy-3-[oxidanyl-[(1R,2R,3S,4R,5R,6S)-2,3,6-tris(oxidanyl)-4,5-diphosphonooxy-cyclohexyl]oxy-phosphoryl]oxy-propyl] octanoate.
- CCD:PIO / [9PR6](https://www.rcsb.org/structure/9PR6): **hold_specific_ligand_needs_context_or_construct_review**; source topology `mixed:cytoplasmic;transmembrane`. Primary entry: Cryo-EM structure of the human inward-rectifier potassium 7.1 channel (Kir7.1) docked state. CCD: [(2R)-2-octanoyloxy-3-[oxidanyl-[(1R,2R,3S,4R,5R,6S)-2,3,6-tris(oxidanyl)-4,5-diphosphonooxy-cyclohexyl]oxy-phosphoryl]oxy-propyl] octanoate.
- CCD:PIO / [9PR7](https://www.rcsb.org/structure/9PR7): **hold_specific_ligand_needs_context_or_construct_review**; source topology `mixed:cytoplasmic;transmembrane`. Primary entry: Cryo-EM structure of the human inward-rectifier potassium 7.1 channel (Kir7.1) with enantiomer of 17-hydroxyprogesterone caproate. CCD: [(2R)-2-octanoyloxy-3-[oxidanyl-[(1R,2R,3S,4R,5R,6S)-2,3,6-tris(oxidanyl)-4,5-diphosphonooxy-cyclohexyl]oxy-phosphoryl]oxy-propyl] octanoate.
- CCD:PIO / [9TG6](https://www.rcsb.org/structure/9TG6): **hold_specific_ligand_needs_context_or_construct_review**; source topology `transmembrane`. Primary entry: Cryo-EM structure of the inward rectifying potassium channel 7.1 (Kir7.1) in complex with PIP2. CCD: [(2R)-2-octanoyloxy-3-[oxidanyl-[(1R,2R,3S,4R,5R,6S)-2,3,6-tris(oxidanyl)-4,5-diphosphonooxy-cyclohexyl]oxy-phosphoryl]oxy-propyl] octanoate.

### SLC22A3 — O75751

1 source records; 1 CCD identities. 7ZH6 explicitly models corticosterone as OCT3 inhibitor. Endogenous steroid with an experimental inhibitory role.

- CCD:C0R / [7ZH6](https://www.rcsb.org/structure/7ZH6): **promotion_candidate**; source topology `mixed:transmembrane;unknown`. Primary entry: Structure of human OCT3 in complex with inhibitor Corticosterone. CCD: CORTICOSTERONE.

### TNFSF13 — O75888

1 source records; 1 CCD identities. Tris buffer in engineered APRIL-BAFF heterotrimer; not receptor/ligand evidence.

- CCD:144 / [4ZCH](https://www.rcsb.org/structure/4ZCH): **hold_preparation_additive**; source topology `unknown`. Primary entry: Single-chain human APRIL-BAFF-BAFF Heterotrimer. CCD: TRIS-HYDROXYMETHYL-METHYL-AMMONIUM.

### SLC22A5 — O76082

2 source records; 2 CCD identities. 9PFB ipratropium and 9PDQ carnitine are explicitly modeled OCTN2 inhibitor/substrate complexes.

- CCD:152 / [9PDQ](https://www.rcsb.org/structure/9PDQ): **promotion_candidate**; source topology `transmembrane`. Primary entry: Human OCTN2 bound to carnitine in the occluded conformation. CCD: CARNITINE.
- CCD:X8M / [9PFB](https://www.rcsb.org/structure/9PFB): **promotion_candidate**; source topology `transmembrane`. Primary entry: Human OCTN2 bound to ipratropium in an inward-facing conformation. CCD: IPRATROPIUM.

### TMEM63A — O94886

2 source records; 2 CCD identities. Cholesterol modulation explicitly studied, whereas POPC is separate membrane lipid. Regulatory lipid plausible but outside bounded promotions.

- CCD:CLR / [9WXV](https://www.rcsb.org/structure/9WXV): **hold_lipid_or_chemical_specificity_unresolved**; source topology `mixed:cytoplasmic;transmembrane`. Primary entry: Cryo-EM structure of TMEM63A-digitonin-cholesterol. CCD: CHOLESTEROL.
- CCD:POV / [8GRS](https://www.rcsb.org/structure/8GRS): **hold_lipid_or_chemical_specificity_unresolved**; source topology `mixed:cytoplasmic;transmembrane`. Primary entry: human TMEM63A. CCD: (2S)-3-(hexadecanoyloxy)-2-[(9Z)-octadec-9-enoyloxy]propyl 2-(trimethylammonio)ethyl phosphate.

### GUSB — P08236

1 source records; 1 CCD identities. MPD crystallization additive.

- CCD:MRD / [3HN3](https://www.rcsb.org/structure/3HN3): **hold_preparation_additive**; source topology `unknown`. Primary entry: Human beta-glucuronidase at 1.7 A resolution. CCD: (4R)-2-METHYLPENTANE-2,4-DIOL.

### FGR — P09769

2 source records; 2 CCD identities. 7UY0 explicitly names A-419259 inhibitor of Fgr kinase; research inhibitor, not a marketed therapeutic. Citrate in HAL2 regulatory domains is distinct additive.

- CCD:FLC / [10FV](https://www.rcsb.org/structure/10FV): **hold_preparation_additive**; source topology `unknown`. Primary entry: Crystal Structure of Human Fgr SH3-SH2-High Affinity Linker Mutant 2 (HAL2) Domains.. CCD: CITRATE ANION.
- CCD:VSE / [7UY0](https://www.rcsb.org/structure/7UY0): **promotion_candidate**; source topology `unknown`. Primary entry: Crystal structure of human Fgr tyrosine kinase in complex with A-419259. CCD: 7-[trans-4-(4-methylpiperazin-1-yl)cyclohexyl]-5-(4-phenoxyphenyl)-7H-pyrrolo[2,3-d]pyrimidin-4-amine.

### DSP — P15924

2 source records; 2 CCD identities. Reduced/oxidized DTT laboratory reducing-agent contacts in desmoplakin fragment.

- CCD:D1D / [3R6N](https://www.rcsb.org/structure/3R6N): **hold_preparation_additive**; source topology `unknown`. Primary entry: Crystal structure of a rigid four spectrin repeat fragment of the human desmoplakin plakin domain. CCD: (4S,5S)-1,2-DITHIANE-4,5-DIOL.
- CCD:DTT / [3R6N](https://www.rcsb.org/structure/3R6N): **hold_preparation_additive**; source topology `unknown`. Primary entry: Crystal structure of a rigid four spectrin repeat fragment of the human desmoplakin plakin domain. CCD: 2,3-DIHYDROXY-1,4-DITHIOBUTANE.

### BPI — P17213

2 source records; 1 CCD identities. BPI primary paper explicitly describes two bound phospholipids. PC1 is a generic diacylphosphocholine model; hold molecular-species identity rather than call it an unspecified physiological ligand.

- CCD:PC1 / [1BP1](https://www.rcsb.org/structure/1BP1): **hold_lipid_or_chemical_specificity_unresolved**; source topology `unknown`. Primary entry: CRYSTAL STRUCTURE OF BPI, THE HUMAN BACTERICIDAL PERMEABILITY-INCREASING PROTEIN. CCD: 1,2-DIACYL-SN-GLYCERO-3-PHOSPHOCHOLINE.
- CCD:PC1 / [1EWF](https://www.rcsb.org/structure/1EWF): **hold_lipid_or_chemical_specificity_unresolved**; source topology `unknown`. Primary entry: THE 1.7 ANGSTROM CRYSTAL STRUCTURE OF BPI. CCD: 1,2-DIACYL-SN-GLYCERO-3-PHOSPHOCHOLINE.

### CD53 — P19397

1 source records; 1 CCD identities. Monoolein in CD53 structure; membrane/crystallization lipid role unresolved.

- CCD:OLC / [6WVG](https://www.rcsb.org/structure/6WVG): **hold_lipid_or_chemical_specificity_unresolved**; source topology `transmembrane`. Primary entry: human CD53. CCD: (2R)-2,3-dihydroxypropyl (9Z)-octadec-9-enoate.

### PTPRE — P23469

1 source records; 1 CCD identities. Pentaethylene glycol in engineered PTP epsilon D2 domain; additive.

- CCD:1PE / [6D4F](https://www.rcsb.org/structure/6D4F): **hold_preparation_additive**; source topology `cytoplasmic`. Primary entry: Crystal structure of PTP epsilon D2 domain (A455N/V457Y/E597D). CCD: PENTAETHYLENE GLYCOL.

### GJB2 — P29033

14 source records; 1 CCD identities. Repeated generic PE contacts across WT and K125E connexin26 structures; no 14 distinct ligands or drug inference.

- CCD:PTY / [7QEO](https://www.rcsb.org/structure/7QEO): **hold_lipid_or_chemical_specificity_unresolved**; source topology `mixed:extracellular;transmembrane`. Primary entry: human Connexin 26 at 55mm Hg PCO2, pH7.4: two masked subunits, class C. CCD: PHOSPHATIDYLETHANOLAMINE.
- CCD:PTY / [7QEQ](https://www.rcsb.org/structure/7QEQ): **hold_lipid_or_chemical_specificity_unresolved**; source topology `mixed:extracellular;transmembrane`. Primary entry: human Connexin 26 dodecamer at 90mmHg PCO2, pH7.4. CCD: PHOSPHATIDYLETHANOLAMINE.
- CCD:PTY / [7QER](https://www.rcsb.org/structure/7QER): **hold_lipid_or_chemical_specificity_unresolved**; source topology `mixed:extracellular;transmembrane`. Primary entry: human Connexin 26 dodecamer at 55mm Hg PCO2, pH7.4. CCD: PHOSPHATIDYLETHANOLAMINE.
- CCD:PTY / [7QES](https://www.rcsb.org/structure/7QES): **hold_lipid_or_chemical_specificity_unresolved**; source topology `mixed:extracellular;transmembrane`. Primary entry: human Connexin 26 at 55mm Hg PCO2, pH7.4: two masked subunits, class A. CCD: PHOSPHATIDYLETHANOLAMINE.
- CCD:PTY / [7QET](https://www.rcsb.org/structure/7QET): **hold_lipid_or_chemical_specificity_unresolved**; source topology `mixed:extracellular;transmembrane`. Primary entry: human Connexin 26 dodecamer at 20mmHg PCO2, pH7.4. CCD: PHOSPHATIDYLETHANOLAMINE.
- CCD:PTY / [7QEU](https://www.rcsb.org/structure/7QEU): **hold_lipid_or_chemical_specificity_unresolved**; source topology `mixed:extracellular;transmembrane`. Primary entry: human Connexin 26 at 55mmHg PCO2, pH7.4: two masked subunits, class B. CCD: PHOSPHATIDYLETHANOLAMINE.
- CCD:PTY / [7QEV](https://www.rcsb.org/structure/7QEV): **hold_lipid_or_chemical_specificity_unresolved**; source topology `mixed:extracellular;transmembrane`. Primary entry: human Connexin 26 at 55mm Hg PCO2, pH7.4:two masked subunits, class D. CCD: PHOSPHATIDYLETHANOLAMINE.
- CCD:PTY / [7QEW](https://www.rcsb.org/structure/7QEW): **hold_lipid_or_chemical_specificity_unresolved**; source topology `mixed:extracellular;transmembrane`. Primary entry: human Connexin 26 class 2 hexamer at 90mmHg PCO2, pH7.4. CCD: PHOSPHATIDYLETHANOLAMINE.
- CCD:PTY / [7QEY](https://www.rcsb.org/structure/7QEY): **hold_lipid_or_chemical_specificity_unresolved**; source topology `mixed:extracellular;transmembrane`. Primary entry: human Connexin 26 class 1 hexamer at 90mmHg PCO2, pH7.4. CCD: PHOSPHATIDYLETHANOLAMINE.
- CCD:PTY / [8Q9Z](https://www.rcsb.org/structure/8Q9Z): **hold_lipid_or_chemical_specificity_unresolved**; source topology `mixed:extracellular;transmembrane`. Primary entry: Cryo-EM structure of Cx26 gap junction K125E mutant in bicarbonate buffer (classification on hemichannel). CCD: PHOSPHATIDYLETHANOLAMINE.
- CCD:PTY / [8QA0](https://www.rcsb.org/structure/8QA0): **hold_lipid_or_chemical_specificity_unresolved**; source topology `mixed:extracellular;transmembrane`. Primary entry: Cryo-EM structure of Cx26 solubilised in LMNG - hemichannel classification - NConst conformation. CCD: PHOSPHATIDYLETHANOLAMINE.
- CCD:PTY / [8QA1](https://www.rcsb.org/structure/8QA1): **hold_lipid_or_chemical_specificity_unresolved**; source topology `mixed:cytoplasmic;extracellular;transmembrane`. Primary entry: Cryo-EM structure of Cx26 solubilised in LMNG - Hemichannel classification NFlex conformation. CCD: PHOSPHATIDYLETHANOLAMINE.
- CCD:PTY / [8QA2](https://www.rcsb.org/structure/8QA2): **hold_lipid_or_chemical_specificity_unresolved**; source topology `mixed:cytoplasmic;extracellular;transmembrane`. Primary entry: Cryo-EM structure of Cx26 solubilised in LMNG: classification on subunit A; Nconst-mon conformation. CCD: PHOSPHATIDYLETHANOLAMINE.
- CCD:PTY / [8QA3](https://www.rcsb.org/structure/8QA3): **hold_lipid_or_chemical_specificity_unresolved**; source topology `mixed:extracellular;transmembrane`. Primary entry: Cryo-EM structure of Cx26 solubilised in LMNG: classification on subunit A; NFlex conformation. CCD: PHOSPHATIDYLETHANOLAMINE.

### AVPR1A — P37288

4 source records; 1 CCD identities. Only cholesterol contacts in input; atosiban, SRX246 and balovaptan named in titles must not be assigned to CLR.

- CCD:CLR / [9UWI](https://www.rcsb.org/structure/9UWI): **hold_lipid_or_chemical_specificity_unresolved**; source topology `mixed:extracellular;transmembrane`. Primary entry: Cryo-EM structure of human V1aR bound with atosiban at a resolution of 2.8 angstrom. CCD: CHOLESTEROL.
- CCD:CLR / [9UWJ](https://www.rcsb.org/structure/9UWJ): **hold_lipid_or_chemical_specificity_unresolved**; source topology `mixed:extracellular;transmembrane`. Primary entry: Cryo-EM structure of human V1aR bound with balovaptan at a resolution of 3.0 angstrom. CCD: CHOLESTEROL.
- CCD:CLR / [9UWL](https://www.rcsb.org/structure/9UWL): **hold_lipid_or_chemical_specificity_unresolved**; source topology `mixed:extracellular;transmembrane`. Primary entry: Cryo-EM structure of human V1aR bound with SRX246 at a resolution of 2.6 angstrom. CCD: CHOLESTEROL.
- CCD:CLR / [9XB1](https://www.rcsb.org/structure/9XB1): **hold_lipid_or_chemical_specificity_unresolved**; source topology `mixed:extracellular;transmembrane`. Primary entry: Cryo-EM structure of human V1aR in apo state at a resolution of 2.8 angstrom. CCD: CHOLESTEROL.

### SLC6A8 — P48029

2 source records; 1 CCD identities. CRN is creatine, not carnitine; substrate identity supported by the creatine-transporter structural study.

- CCD:CRN / [9KRH](https://www.rcsb.org/structure/9KRH): **supported_alternate_structure_not_promoted**; source topology `transmembrane`. Primary entry: human creatine transporter. CCD: N-[(E)-AMINO(IMINO)METHYL]-N-METHYLGLYCINE.
- CCD:CRN / [9V8X](https://www.rcsb.org/structure/9V8X): **promotion_candidate**; source topology `transmembrane`. Primary entry: membrane protein S6A8 with Crea. CCD: N-[(E)-AMINO(IMINO)METHYL]-N-METHYLGLYCINE.

### SLC6A12 — P48065

6 source records; 3 CCD identities. Betaine and GABA are explicit substrate complexes. Cholesterol records are separate and remain held.

- CCD:ABU / [9LNM](https://www.rcsb.org/structure/9LNM): **supported_alternate_structure_not_promoted**; source topology `transmembrane`. Primary entry: human Betaine/GABA transporter 1 in complex with GABA. CCD: GAMMA-AMINO-BUTANOIC ACID.
- CCD:ABU / [9W9A](https://www.rcsb.org/structure/9W9A): **promotion_candidate**; source topology `transmembrane`. Primary entry: Structure of GABA-bound state of the human betaine/GABA transporter 1. CCD: GAMMA-AMINO-BUTANOIC ACID.
- CCD:BET / [9LNN](https://www.rcsb.org/structure/9LNN): **supported_alternate_structure_not_promoted**; source topology `transmembrane`. Primary entry: human Betaine/GABA transporter 1 in complex with Betaine. CCD: TRIMETHYL GLYCINE.
- CCD:BET / [9W99](https://www.rcsb.org/structure/9W99): **promotion_candidate**; source topology `mixed:transmembrane;unknown`. Primary entry: Structure of betaine-bound state of the human betaine/GABA transporter 1. CCD: TRIMETHYL GLYCINE.
- CCD:CLR / [9LNM](https://www.rcsb.org/structure/9LNM): **hold_lipid_or_chemical_specificity_unresolved**; source topology `mixed:extracellular;transmembrane;unknown`. Primary entry: human Betaine/GABA transporter 1 in complex with GABA. CCD: CHOLESTEROL.
- CCD:CLR / [9LNO](https://www.rcsb.org/structure/9LNO): **hold_lipid_or_chemical_specificity_unresolved**; source topology `mixed:extracellular;transmembrane;unknown`. Primary entry: human Betaine/GABA transporter 1 in inward facing conformation. CCD: CHOLESTEROL.

### SLC26A2 — P50443

1 source records; 1 CCD identities. Oxalate source CCD and substrate-binding primary study support a transported anion; verify canonical footprint before acceptance.

- CCD:OXL / [8TNX](https://www.rcsb.org/structure/8TNX): **promotion_candidate**; source topology `transmembrane`. Primary entry: Substrate Binding Plasticity Revealed by Cryo-EM Structures of SLC26A2. CCD: OXALATE ION.

### TNFAIP6 — P98066

1 source records; 1 CCD identities. Nonaethylene glycol additive, not hyaluronan.

- CCD:2PE / [2PF5](https://www.rcsb.org/structure/2PF5): **hold_preparation_additive**; source topology `unknown`. Primary entry: Crystal Structure of the Human TSG-6 Link Module. CCD: NONAETHYLENE GLYCOL.

### DEFA6 — Q01524

2 source records; 1 CCD identities. Inositol hexakisphosphate explicitly drives HD6 filament assembly; dietary ligand, not established endogenous human ligand. Held for assembly-specific category review.

- CCD:IHP / [9R7L](https://www.rcsb.org/structure/9R7L): **hold_specific_ligand_needs_context_or_construct_review**; source topology `unknown`. Primary entry: HD6 defensin filament with IP6. CCD: INOSITOL HEXAKISPHOSPHATE.
- CCD:IHP / [9R7M](https://www.rcsb.org/structure/9R7M): **hold_specific_ligand_needs_context_or_construct_review**; source topology `unknown`. Primary entry: HD6 defensin filament with IP6. CCD: INOSITOL HEXAKISPHOSPHATE.

### PLD1 — Q13393

1 source records; 1 CCD identities. 6OHR explicitly models compound 5 in PLD1 catalytic domain; retain exact paper-local name and CCD MKG, no speculative clinical alias.

- CCD:MKG / [6OHR](https://www.rcsb.org/structure/6OHR): **promotion_candidate**; source topology `unknown`. Primary entry: Structure of compound 5 bound human Phospholipase D1 catalytic domain. CCD: 4-fluoro-N-{(2S)-1-[(5R)-5-(3-fluorophenyl)-2-oxo-1-oxa-3,9-diazaspiro[5.5]undecan-9-yl]propan-2-yl}benzamide.

### SLC75A1 — Q14728

1 source records; 1 CCD identities. Monoolein in TETRAN structure; not sufficient substrate assignment.

- CCD:OLC / [6S4M](https://www.rcsb.org/structure/6S4M): **hold_lipid_or_chemical_specificity_unresolved**; source topology `mixed:transmembrane;unknown`. Primary entry: Crystal structure of the human organic anion transporter MFSD10 (TETRAN). CCD: (2R)-2,3-dihydroxypropyl (9Z)-octadec-9-enoate.

### SLC18A3 — Q16572

3 source records; 1 CCD identities. Acetylcholine-bound VAChT entries explicitly model neurotransmitter substrate.

- CCD:ACH / [8XTW](https://www.rcsb.org/structure/8XTW): **promotion_candidate**; source topology `transmembrane`. Primary entry: Structure of human VAChT in complex with acetylcholine. CCD: ACETYLCHOLINE.
- CCD:ACH / [8ZMS](https://www.rcsb.org/structure/8ZMS): **supported_alternate_structure_not_promoted**; source topology `transmembrane`. Primary entry: Acetylcholine-bound VAChT. CCD: ACETYLCHOLINE.
- CCD:ACH / [9KKN](https://www.rcsb.org/structure/9KKN): **supported_alternate_structure_not_promoted**; source topology `transmembrane`. Primary entry: Cryo-EM structure of human VAChT in complex with ACh. CCD: ACETYLCHOLINE.

### SLC22A6 — Q4U2R8

5 source records; 4 CCD identities. OAT1 entries explicitly name adefovir, cidofovir, glibenclamide and olmesartan. Transporter binding does not establish the drugs therapeutic mechanism at this target.

- CCD:5HG / [9M9V](https://www.rcsb.org/structure/9M9V): **promotion_candidate**; source topology `transmembrane`. Primary entry: Cryo-EM structure of human OAT1 in complex with adefovir. CCD: {[2-(6-AMINO-9H-PURIN-9-YL)ETHOXY]METHYL}PHOSPHONIC ACID.
- CCD:GBM / [9J06](https://www.rcsb.org/structure/9J06): **promotion_candidate**; source topology `mixed:extracellular;transmembrane`. Primary entry: Cryo-EM structure of hOAT1 in complex with glibenclamide. CCD: 5-chloro-N-(2-{4-[(cyclohexylcarbamoyl)sulfamoyl]phenyl}ethyl)-2-methoxybenzamide.
- CCD:L8P / [9J04](https://www.rcsb.org/structure/9J04): **promotion_candidate**; source topology `transmembrane`. Primary entry: Cryo-EM structure of hOAT1 in complex with cidofovir. CCD: ({[(2S)-1-(4-amino-2-oxopyrimidin-1(2H)-yl)-3-hydroxypropan-2-yl]oxy}methyl)phosphonic acid.
- CCD:OLM / [9KLZ](https://www.rcsb.org/structure/9KLZ): **promotion_candidate**; source topology `mixed:cytoplasmic;transmembrane`. Primary entry: Human OAT1 in complex with olmesartan. CCD: Olmesartan.
- CCD:OLM / [9UNX](https://www.rcsb.org/structure/9UNX): **supported_alternate_structure_not_promoted**; source topology `mixed:cytoplasmic;extracellular;transmembrane`. Primary entry: Cryo-EM structure of human OAT1 in complex with olmesartan and bromide ion.. CCD: Olmesartan.

### SLC45A4 — Q5BKX6

3 source records; 2 CCD identities. Only cholesterol/PE input contacts; polyamine transport paper does not convert these to polyamine observations.

- CCD:3PE / [9GHZ](https://www.rcsb.org/structure/9GHZ): **hold_lipid_or_chemical_specificity_unresolved**; source topology `transmembrane`. Primary entry: Cryo-EM structure of human SLC45A4 in lipid nanodiscs. CCD: 1,2-Distearoyl-sn-glycerophosphoethanolamine.
- CCD:3PE / [9GIU](https://www.rcsb.org/structure/9GIU): **hold_lipid_or_chemical_specificity_unresolved**; source topology `transmembrane`. Primary entry: Cryo-EM structure of human SLC45A4 in detergent. CCD: 1,2-Distearoyl-sn-glycerophosphoethanolamine.
- CCD:CLR / [9GHZ](https://www.rcsb.org/structure/9GHZ): **hold_lipid_or_chemical_specificity_unresolved**; source topology `mixed:cytoplasmic;extracellular;transmembrane`. Primary entry: Cryo-EM structure of human SLC45A4 in lipid nanodiscs. CCD: CHOLESTEROL.

### TMEM164 — Q5U3C3

4 source records; 2 CCD identities. Myristoyl-LPC exact molecular species in substrate-bound phospholipid-remodeling TMEM164 study; cholesterol distinct. Native physiological chain distribution not inferred.

- CCD:CLR / [9LW1](https://www.rcsb.org/structure/9LW1): **hold_lipid_or_chemical_specificity_unresolved**; source topology `mixed:transmembrane;unknown`. Primary entry: TMEM164-substrate. CCD: CHOLESTEROL.
- CCD:CLR / [9LW3](https://www.rcsb.org/structure/9LW3): **hold_lipid_or_chemical_specificity_unresolved**; source topology `mixed:transmembrane;unknown`. Primary entry: TMEM164-substrate. CCD: CHOLESTEROL.
- CCD:LPC / [9LW1](https://www.rcsb.org/structure/9LW1): **promotion_candidate**; source topology `mixed:transmembrane;unknown`. Primary entry: TMEM164-substrate. CCD: [1-MYRISTOYL-GLYCEROL-3-YL]PHOSPHONYLCHOLINE.
- CCD:LPC / [9LW3](https://www.rcsb.org/structure/9LW3): **supported_alternate_structure_not_promoted**; source topology `mixed:transmembrane;unknown`. Primary entry: TMEM164-substrate. CCD: [1-MYRISTOYL-GLYCEROL-3-YL]PHOSPHONYLCHOLINE.

### RNLS — Q5VYX0

1 source records; 1 CCD identities. FAD-binding renalase is a defined enzyme cofactor; not prioritized as a drug/substrate or accessible extracellular binder.

- CCD:FAD / [3QJ4](https://www.rcsb.org/structure/3QJ4): **hold_regulatory_nucleotide_or_cofactor**; source topology `unknown`. Primary entry: Crystal structure of Human Renalase (isoform 1). CCD: FLAVIN-ADENINE DINUCLEOTIDE.

### SLC18B1 — Q6NT16

2 source records; 2 CCD identities. SPD and SPM are explicitly spermidine/spermine-bound vesicular polyamine transporter states.

- CCD:SPD / [9D7V](https://www.rcsb.org/structure/9D7V): **promotion_candidate**; source topology `transmembrane`. Primary entry: The spd-bound structure. CCD: SPERMIDINE.
- CCD:SPM / [9D7X](https://www.rcsb.org/structure/9D7X): **promotion_candidate**; source topology `mixed:extracellular;transmembrane`. Primary entry: The spm-bound structure. CCD: SPERMINE.

### CNNM4 — Q6P4Q7

4 source records; 1 CCD identities. MgATP is a specific regulatory nucleotide; 9Y9D is WT whereas 9Y9F/9Y9G/11GQ are mutants. Hold outside the bounded drug/substrate priority set.

- CCD:ATP / [11GQ](https://www.rcsb.org/structure/11GQ): **hold_regulatory_nucleotide_or_cofactor**; source topology `cytoplasmic`. Primary entry: Cryo-EM structure of human CNNM4(E284A) tetramer with Magnesium and MgATP in outward-facing state. CCD: ADENOSINE-5'-TRIPHOSPHATE.
- CCD:ATP / [9Y9D](https://www.rcsb.org/structure/9Y9D): **hold_regulatory_nucleotide_or_cofactor**; source topology `cytoplasmic`. Primary entry: Cryo-EM structure of wild-type human CNNM4 tetramer with Magnesium and MgATP in outward-facing state. CCD: ADENOSINE-5'-TRIPHOSPHATE.
- CCD:ATP / [9Y9F](https://www.rcsb.org/structure/9Y9F): **hold_regulatory_nucleotide_or_cofactor**; source topology `cytoplasmic`. Primary entry: Cryo-EM structure of human CNNM4(D262C) tetramer with Magnesium and MgATP in occluded state. CCD: ADENOSINE-5'-TRIPHOSPHATE.
- CCD:ATP / [9Y9G](https://www.rcsb.org/structure/9Y9G): **hold_regulatory_nucleotide_or_cofactor**; source topology `cytoplasmic`. Primary entry: Cryo-EM structure of human CNNM4(K113A/R140A/R141A) tetramer with Magnesium and MgATP in outward-facing state. CCD: ADENOSINE-5'-TRIPHOSPHATE.

### SLC4A10 — Q6U841

3 source records; 1 CCD identities. Only cholesterol source contacts; carbonate and compound 38J in titles are different chemicals.

- CCD:CLR / [9MIX](https://www.rcsb.org/structure/9MIX): **hold_lipid_or_chemical_specificity_unresolved**; source topology `mixed:cytoplasmic;extracellular;transmembrane`. Primary entry: Cryo-EM structure of human NBCn2. CCD: CHOLESTEROL.
- CCD:CLR / [9MJO](https://www.rcsb.org/structure/9MJO): **hold_lipid_or_chemical_specificity_unresolved**; source topology `mixed:cytoplasmic;extracellular;transmembrane`. Primary entry: Cryo-EM structure of human NBCn2 bound to Carbonate. CCD: CHOLESTEROL.
- CCD:CLR / [9MK6](https://www.rcsb.org/structure/9MK6): **hold_lipid_or_chemical_specificity_unresolved**; source topology `mixed:cytoplasmic;extracellular;transmembrane`. Primary entry: Cryo-EM structure of human NBCn2 bound to Compound 38J. CCD: CHOLESTEROL.

### SLC36A1 — Q7Z2H8

1 source records; 1 CCD identities. 9V3V explicitly models D-cycloserine; CCD 4AX is the R stereoisomer. Drug bound to transporter, not an efficacy claim.

- CCD:4AX / [9V3V](https://www.rcsb.org/structure/9V3V): **promotion_candidate**; source topology `transmembrane`. Primary entry: SLC36A1 bound to D-cycloserine. CCD: (R)-4-AMINO-ISOXAZOLIDIN-3-ONE.

### TRPM8 — Q7Z2W7

2 source records; 2 CCD identities. Apo TRPM8 contains undecane and POPC; no pharmacological ligand in these input rows.

- CCD:POV / [8BDC](https://www.rcsb.org/structure/8BDC): **hold_lipid_or_chemical_specificity_unresolved**; source topology `mixed:cytoplasmic;transmembrane`. Primary entry: Human apo TRPM8 in a closed state (composite map). CCD: (2S)-3-(hexadecanoyloxy)-2-[(9Z)-octadec-9-enoyloxy]propyl 2-(trimethylammonio)ethyl phosphate.
- CCD:UND / [8BDC](https://www.rcsb.org/structure/8BDC): **hold_hydrocarbon_or_partial_lipid_model**; source topology `mixed:transmembrane;unknown`. Primary entry: Human apo TRPM8 in a closed state (composite map). CCD: UNDECANE.

### ATG9A — Q7Z3C6

3 source records; 2 CCD identities. POPC in nanodiscs and LMNG detergent; lipid-scrambling biology alone does not identify a unique named ligand.

- CCD:LMN / [6WQZ](https://www.rcsb.org/structure/6WQZ): **hold_preparation_additive**; source topology `mixed:cytoplasmic;transmembrane;unknown`. Primary entry: Structure of human ATG9A, the only transmembrane protein of the core autophagy machinery. CCD: Lauryl Maltose Neopentyl Glycol.
- CCD:LMN / [6WR4](https://www.rcsb.org/structure/6WR4): **hold_preparation_additive**; source topology `mixed:cytoplasmic;transmembrane;unknown`. Primary entry: Structure of human ATG9A, the only transmembrane protein of the core autophagy machinery. CCD: Lauryl Maltose Neopentyl Glycol.
- CCD:POV / [7JLP](https://www.rcsb.org/structure/7JLP): **hold_lipid_or_chemical_specificity_unresolved**; source topology `mixed:cytoplasmic;lumenal;transmembrane;unknown`. Primary entry: cryo-EM structure of human ATG9A in nanodiscs. CCD: (2S)-3-(hexadecanoyloxy)-2-[(9Z)-octadec-9-enoyloxy]propyl 2-(trimethylammonio)ethyl phosphate.

### CALHM1 — Q8IU99

3 source records; 1 CCD identities. POPC membrane contacts; 8GMP I109W engineered channel. No ruthenium-red identity transfer.

- CCD:POV / [8GMP](https://www.rcsb.org/structure/8GMP): **hold_lipid_or_chemical_specificity_unresolved**; source topology `transmembrane`. Primary entry: Cryo-EM structure of octameric human CALHM1 with a I109W point mutation. CCD: (2S)-3-(hexadecanoyloxy)-2-[(9Z)-octadec-9-enoyloxy]propyl 2-(trimethylammonio)ethyl phosphate.
- CCD:POV / [8GMR](https://www.rcsb.org/structure/8GMR): **hold_lipid_or_chemical_specificity_unresolved**; source topology `transmembrane`. Primary entry: Cryo-EM structure of octameric human CALHM1. CCD: (2S)-3-(hexadecanoyloxy)-2-[(9Z)-octadec-9-enoyloxy]propyl 2-(trimethylammonio)ethyl phosphate.
- CCD:POV / [8S8Z](https://www.rcsb.org/structure/8S8Z): **hold_lipid_or_chemical_specificity_unresolved**; source topology `transmembrane`. Primary entry: Cryo-EM structure of octameric human CALHM1 (I109W) in complex with ruthenium red. CCD: (2S)-3-(hexadecanoyloxy)-2-[(9Z)-octadec-9-enoyloxy]propyl 2-(trimethylammonio)ethyl phosphate.

### MCOLN2 — Q8IZK6

1 source records; 1 CCD identities. EUJ is a short-chain PI(3,5)P2 model in ML2-SA1/PIP2-bound TRPML2. Regulatory lipid analogue; do not relabel as ML2-SA1 or native long-chain phosphoinositide.

- CCD:EUJ / [9EL1](https://www.rcsb.org/structure/9EL1): **hold_specific_ligand_needs_context_or_construct_review**; source topology `mixed:cytoplasmic;transmembrane`. Primary entry: ML2-SA1/PI(3,5)P2 bound TRPML2 in an open state. CCD: (2R)-3-{[(S)-hydroxy{[(1S,2R,3R,4S,5S,6R)-2,4,6-trihydroxy-3,5-bis(phosphonooxy)cyclohexyl]oxy}phosphoryl]oxy}propane-1,2-diyl dioctanoate.

### NXPE1 — Q8N323

1 source records; 1 CCD identities. Acetyl-CoA contact in NXPE1 sialic-acid O-acetyltransferase supports catalytic donor role; coordinate acceptance still required.

- CCD:ACO / [9PJA](https://www.rcsb.org/structure/9PJA): **promotion_candidate**; source topology `unknown`. Primary entry: Cryo-EM structure of human NXPE1. CCD: ACETYL COENZYME *A.

### CALHM5 — Q8N5C1

3 source records; 1 CCD identities. Short-chain phosphatidic acid in CALHM5; titles concern ruthenium red, not this lipid. Do not exchange chemical identity.

- CCD:PA8 / [7D60](https://www.rcsb.org/structure/7D60): **hold_lipid_or_chemical_specificity_unresolved**; source topology `mixed:cytoplasmic;extracellular;transmembrane`. Primary entry: Cryo-EM Structure of human CALHM5 in the presence of rubidium red. CCD: 1,2-DIOCTANOYL-SN-GLYCERO-3-PHOSPHATE.
- CCD:PA8 / [7D61](https://www.rcsb.org/structure/7D61): **hold_lipid_or_chemical_specificity_unresolved**; source topology `mixed:cytoplasmic;transmembrane`. Primary entry: Cryo-EM Structure of human CALHM5 in the presence of EDTA. CCD: 1,2-DIOCTANOYL-SN-GLYCERO-3-PHOSPHATE.
- CCD:PA8 / [7D65](https://www.rcsb.org/structure/7D65): **hold_lipid_or_chemical_specificity_unresolved**; source topology `mixed:cytoplasmic;extracellular;transmembrane`. Primary entry: Cryo-EM Structure of human CALHM5 in the presence of Ca2+. CCD: 1,2-DIOCTANOYL-SN-GLYCERO-3-PHOSPHATE.

### NIPA2 — Q8N8Q9

1 source records; 1 CCD identities. ATP-bound NIPA2; specific nucleotide interaction, role and unusual source TM annotation require separate validation.

- CCD:ATP / [9Z7T](https://www.rcsb.org/structure/9Z7T): **hold_regulatory_nucleotide_or_cofactor**; source topology `transmembrane`. Primary entry: Human NIPA2 with ATP. CCD: ADENOSINE-5'-TRIPHOSPHATE.

### MIGA1 — Q8NAN2

1 source records; 1 CCD identities. Dipalmitoyl-PE bound lipid-targeting domain in lipid-transport study; plausible cargo but held species/physiological specificity.

- CCD:PEF / [9JCW](https://www.rcsb.org/structure/9JCW): **hold_lipid_or_chemical_specificity_unresolved**; source topology `unknown`. Primary entry: Crystal structure of human MIGA1 LD targeting domain. CCD: DI-PALMITOYL-3-SN-PHOSPHATIDYLETHANOLAMINE.

### TMEM87A — Q8NBN3

2 source records; 2 CCD identities. PE-bound TMEM87A is explicit, but structural lipid versus specific regulation unresolved. Cholesterol distinct.

- CCD:CLR / [8HSI](https://www.rcsb.org/structure/8HSI): **hold_lipid_or_chemical_specificity_unresolved**; source topology `mixed:cytoplasmic;lumenal;transmembrane`. Primary entry: Cryo-EM structure of human TMEM87A, PE-bound. CCD: CHOLESTEROL.
- CCD:L9Q / [8HSI](https://www.rcsb.org/structure/8HSI): **hold_lipid_or_chemical_specificity_unresolved**; source topology `transmembrane`. Primary entry: Cryo-EM structure of human TMEM87A, PE-bound. CCD: (1S)-2-{[(S)-(2-aminoethoxy)(hydroxy)phosphoryl]oxy}-1-[(octadecanoyloxy)methyl]ethyl (9Z)-octadec-9-enoate.

### AQP11 — Q8NBQ7

1 source records; 1 CCD identities. Decane in LMNG-solubilized AQP11; not an independently established substrate.

- CCD:D10 / [9VXW](https://www.rcsb.org/structure/9VXW): **hold_hydrocarbon_or_partial_lipid_model**; source topology `transmembrane`. Primary entry: Cryo-EM structure of hAQP11 in LMNG. CCD: DECANE.

### SPPL2A — Q8TCT8

1 source records; 1 CCD identities. Generic phosphocholine in intramembrane protease; no substrate inference.

- CCD:PC1 / [9K92](https://www.rcsb.org/structure/9K92): **hold_lipid_or_chemical_specificity_unresolved**; source topology `transmembrane`. Primary entry: Cryo-EM structure of human signal peptide peptidase like 2A (SPPL2a). CCD: 1,2-DIACYL-SN-GLYCERO-3-PHOSPHOCHOLINE.

### SLC16A10 — Q8TF71

1 source records; 1 CCD identities. 9GSZ explicitly names L-thyroxine bound to MCT10.

- CCD:T44 / [9GSZ](https://www.rcsb.org/structure/9GSZ): **promotion_candidate**; source topology `mixed:extracellular;transmembrane`. Primary entry: Human monocarboxylate transporter 10 bound to L-thyroxine. CCD: 3,5,3',5'-TETRAIODO-L-THYRONINE.

### SLC44A1 — Q8WWI5

2 source records; 2 CCD identities. CHT is choline in CTL1 deposit. Functional substrate purpose needs more than the fold-atlas title; retained as bounded unresolved substrate candidate.

- CCD:CHT / [7WWB](https://www.rcsb.org/structure/7WWB): **hold_specific_ligand_needs_context_or_construct_review**; source topology `mitochondrial intermembrane`. Primary entry: Choline transporter-like protein 1. CCD: CHOLINE ION.
- CCD:CLR / [7WWB](https://www.rcsb.org/structure/7WWB): **hold_lipid_or_chemical_specificity_unresolved**; source topology `mixed:mitochondrial intermembrane;transmembrane`. Primary entry: Choline transporter-like protein 1. CCD: CHOLESTEROL.

### SLC9A6 — Q92581

5 source records; 3 CCD identities. PCF/PC1/3PE membrane phospholipids are not the PIP2 named in the NHE6 titles; no identity substitution.

- CCD:3PE / [9R8L](https://www.rcsb.org/structure/9R8L): **hold_lipid_or_chemical_specificity_unresolved**; source topology `mixed:transmembrane;unknown`. Primary entry: Structure of human NHE6.0. CCD: 1,2-Distearoyl-sn-glycerophosphoethanolamine.
- CCD:PC1 / [9R8M](https://www.rcsb.org/structure/9R8M): **hold_lipid_or_chemical_specificity_unresolved**; source topology `mixed:transmembrane;unknown`. Primary entry: Structure of human NHE6.1 bound to PIP2. CCD: 1,2-DIACYL-SN-GLYCERO-3-PHOSPHOCHOLINE.
- CCD:PC1 / [9R8N](https://www.rcsb.org/structure/9R8N): **hold_lipid_or_chemical_specificity_unresolved**; source topology `mixed:transmembrane;unknown`. Primary entry: Structure of human NHE6.1 bound to PIP2 (core-TM domain). CCD: 1,2-DIACYL-SN-GLYCERO-3-PHOSPHOCHOLINE.
- CCD:PCF / [9R8M](https://www.rcsb.org/structure/9R8M): **hold_lipid_or_chemical_specificity_unresolved**; source topology `mixed:transmembrane;unknown`. Primary entry: Structure of human NHE6.1 bound to PIP2. CCD: 1,2-DIACYL-SN-GLYCERO-3-PHOSHOCHOLINE.
- CCD:PCF / [9R8N](https://www.rcsb.org/structure/9R8N): **hold_lipid_or_chemical_specificity_unresolved**; source topology `mixed:transmembrane;unknown`. Primary entry: Structure of human NHE6.1 bound to PIP2 (core-TM domain). CCD: 1,2-DIACYL-SN-GLYCERO-3-PHOSHOCHOLINE.

### GJD4 — Q96KN9

3 source records; 3 CCD identities. Cholesterol and generic PE membrane contacts in connexin40.1; specificity unresolved.

- CCD:3PE / [8GN7](https://www.rcsb.org/structure/8GN7): **hold_lipid_or_chemical_specificity_unresolved**; source topology `mixed:extracellular;transmembrane`. Primary entry: structure of human connexin 40.1 intercellular gap junction channel by cryoEM. CCD: 1,2-Distearoyl-sn-glycerophosphoethanolamine.
- CCD:CLR / [8GN7](https://www.rcsb.org/structure/8GN7): **hold_lipid_or_chemical_specificity_unresolved**; source topology `mixed:extracellular;transmembrane`. Primary entry: structure of human connexin 40.1 intercellular gap junction channel by cryoEM. CCD: CHOLESTEROL.
- CCD:PTY / [8GN7](https://www.rcsb.org/structure/8GN7): **hold_lipid_or_chemical_specificity_unresolved**; source topology `mixed:cytoplasmic;transmembrane`. Primary entry: structure of human connexin 40.1 intercellular gap junction channel by cryoEM. CCD: PHOSPHATIDYLETHANOLAMINE.

### PANX3 — Q96QZ0

1 source records; 1 CCD identities. Generic phosphatidylethanolamine membrane lipid in PANX3; no specific ligand-purpose inference.

- CCD:PTY / [8GTR](https://www.rcsb.org/structure/8GTR): **hold_lipid_or_chemical_specificity_unresolved**; source topology `mixed:extracellular;transmembrane`. Primary entry: CryoEM structure of human Pannexin isoform 3. CCD: PHOSPHATIDYLETHANOLAMINE.

### ABCA3 — Q99758

3 source records; 3 CCD identities. ATP-bound ABCA3 and phosphatidylcholines are mechanistic cofactor/lipid contacts. ATP model may have catalytic construct modifications; held outside prioritized set.

- CCD:ATP / [7W02](https://www.rcsb.org/structure/7W02): **hold_regulatory_nucleotide_or_cofactor**; source topology `unknown`. Primary entry: Cryo-EM structure of ATP-bound ABCA3. CCD: ADENOSINE-5'-TRIPHOSPHATE.
- CCD:POV / [7W01](https://www.rcsb.org/structure/7W01): **hold_lipid_or_chemical_specificity_unresolved**; source topology `mixed:transmembrane;unknown`. Primary entry: Cryo-EM structure of nucleotide-free ABCA3. CCD: (2S)-3-(hexadecanoyloxy)-2-[(9Z)-octadec-9-enoyloxy]propyl 2-(trimethylammonio)ethyl phosphate.
- CCD:PX4 / [7W01](https://www.rcsb.org/structure/7W01): **hold_lipid_or_chemical_specificity_unresolved**; source topology `mixed:transmembrane;unknown`. Primary entry: Cryo-EM structure of nucleotide-free ABCA3. CCD: 1,2-DIMYRISTOYL-SN-GLYCERO-3-PHOSPHOCHOLINE.

### SLC6A7 — Q99884

5 source records; 1 CCD identities. Cholesterol modulation is explicitly studied, including cholesterol-bound 9WMP; plausible regulatory lipid but held from bounded substrate/drug promotion.

- CCD:CLR / [9WML](https://www.rcsb.org/structure/9WML): **hold_lipid_or_chemical_specificity_unresolved**; source topology `mixed:extracellular;transmembrane;unknown`. Primary entry: Structural mechanism of substrate binding of the human Proline Transporter. CCD: CHOLESTEROL.
- CCD:CLR / [9WMM](https://www.rcsb.org/structure/9WMM): **hold_lipid_or_chemical_specificity_unresolved**; source topology `mixed:extracellular;transmembrane;unknown`. Primary entry: Structure of the cholesterol-bound human proline transporter purified in DDM/CHS buffer. CCD: CHOLESTEROL.
- CCD:CLR / [9WMN](https://www.rcsb.org/structure/9WMN): **hold_lipid_or_chemical_specificity_unresolved**; source topology `mixed:extracellular;transmembrane;unknown`. Primary entry: Structure of the apo-state human proline transporter purified in DDM/CHS buffer. CCD: CHOLESTEROL.
- CCD:CLR / [9WMO](https://www.rcsb.org/structure/9WMO): **hold_lipid_or_chemical_specificity_unresolved**; source topology `mixed:extracellular;transmembrane;unknown`. Primary entry: Structure of the apo-state human proline transporter purified in DDM buffer. CCD: CHOLESTEROL.
- CCD:CLR / [9WMP](https://www.rcsb.org/structure/9WMP): **hold_lipid_or_chemical_specificity_unresolved**; source topology `mixed:extracellular;transmembrane;unknown`. Primary entry: Structure of the cholesterol-bound human proline transporter purified in DDM buffer. CCD: CHOLESTEROL.

### ABHD6 — Q9BV23

1 source records; 1 CCD identities. ABHD6 explicitly bound oleic acid and detergent; fatty-acid product/substrate distinction unresolved, held.

- CCD:OLA / [7OTS](https://www.rcsb.org/structure/7OTS): **hold_specific_ligand_needs_context_or_construct_review**; source topology `cytoplasmic`. Primary entry: Crystal structure of human Monoacylglycerol Lipase ABHD6 in complex with oleic acid and octyl glucoside. CCD: OLEIC ACID.

### ANGPTL4 — Q9BY76

3 source records; 3 CCD identities. ANGPTL4 C-terminal structures explicitly model myristic and palmitic acid; binding-pocket evidence, not proof of systemic physiological ligand function. PEG remains additive.

- CCD:1PE / [6EUB](https://www.rcsb.org/structure/6EUB): **hold_preparation_additive**; source topology `unknown`. Primary entry: The fibrinogen-like domain of human Angptl4. CCD: PENTAETHYLENE GLYCOL.
- CCD:MYR / [6U73](https://www.rcsb.org/structure/6U73): **promotion_candidate**; source topology `unknown`. Primary entry: Human Angiopoietin-Like 4 C-Terminal Domain (cANGPTL4) with Myristic Acid. CCD: MYRISTIC ACID.
- CCD:PLM / [6U1U](https://www.rcsb.org/structure/6U1U): **promotion_candidate**; source topology `unknown`. Primary entry: Human Angiopoietin-Like 4 C-Terminal Domain (cANGPTL4) with Palmitic Acid. CCD: PALMITIC ACID.

### TM6SF1 — Q9BZW5

1 source records; 1 CCD identities. Cholesterol in TM6SF1 deposit; specific regulatory role unresolved.

- CCD:CLR / [10UP](https://www.rcsb.org/structure/10UP): **hold_lipid_or_chemical_specificity_unresolved**; source topology `mixed:transmembrane;unknown`. Primary entry: Structure of human TM6SF1. CCD: CHOLESTEROL.

### SLC12A5 — Q9H2X9

1 source records; 1 CCD identities. ATP bound to KCC2b T906A/T1007A phospho-knockout mutant. Regulatory nucleotide and construct caveat; held.

- CCD:ATP / [9RNJ](https://www.rcsb.org/structure/9RNJ): **hold_regulatory_nucleotide_or_cofactor**; source topology `cytoplasmic`. Primary entry: Cryo-EM structure of the human potassium chloride cotransporter T906A/T1007A phospho-knockout mutants KCC2b bound ATP in LMNG (outward-facing state, dimer). CCD: ADENOSINE-5'-TRIPHOSPHATE.

### SLC52A2 — Q9HAB3

1 source records; 1 CCD identities. RBF exact riboflavin source identity, but generic entry title leaves modeled substrate-purpose corroboration bounded/unresolved.

- CCD:RBF / [8XSM](https://www.rcsb.org/structure/8XSM): **hold_specific_ligand_needs_context_or_construct_review**; source topology `mixed:transmembrane;unknown`. Primary entry: transporter. CCD: RIBOFLAVIN.

### SLC52A3 — Q9NQ40

1 source records; 1 CCD identities. Exact RBF riboflavin source identity supported, but generic entry/paper title provides insufficient ligand-purpose detail for this bounded recommendation set.

- CCD:RBF / [8XSN](https://www.rcsb.org/structure/8XSN): **hold_specific_ligand_needs_context_or_construct_review**; source topology `mixed:extracellular;transmembrane`. Primary entry: transporter. CCD: RIBOFLAVIN.

### TMEM45A — Q9NWC5

1 source records; 1 CCD identities. Generic phosphocholine membrane model in TMEM45A; no independently supported ligand assignment.

- CCD:PC1 / [7OQZ](https://www.rcsb.org/structure/7OQZ): **hold_lipid_or_chemical_specificity_unresolved**; source topology `mixed:transmembrane;unknown`. Primary entry: Cryo-EM structure of human TMEM45A. CCD: 1,2-DIACYL-SN-GLYCERO-3-PHOSPHOCHOLINE.

### SLCO1C1 — Q9NYB5

3 source records; 3 CCD identities. WT thyroxine 9DXP prioritized. Estrone sulfate/glucuronide 9DXO/9MR5 are F240A complexes and remain construct-qualified held candidates.

- CCD:E3G / [9MR5](https://www.rcsb.org/structure/9MR5): **hold_specific_ligand_needs_context_or_construct_review**; source topology `mixed:extracellular;transmembrane`. Primary entry: Cryo-EM structure of human OATP1C1 F240A mutant in complex with estrone 3-glucuronide. CCD: ESTRONE BETA-D-GLUCURONIDE.
- CCD:FY5 / [9DXO](https://www.rcsb.org/structure/9DXO): **hold_specific_ligand_needs_context_or_construct_review**; source topology `mixed:extracellular;transmembrane`. Primary entry: Cryo-EM structure of human OATP1C1 F240A mutant in complex with estrone 3-sulfate. CCD: estrone 3-sulfate.
- CCD:T44 / [9DXP](https://www.rcsb.org/structure/9DXP): **promotion_candidate**; source topology `mixed:extracellular;transmembrane`. Primary entry: Cryo-EM structure of human OATP1C1 in complex with thyroid hormone T4. CCD: 3,5,3',5'-TETRAIODO-L-THYRONINE.

### NINJ2 — Q9NZG7

1 source records; 1 CCD identities. Cholesterol in NINJ2 filament; no independently resolved specific ligand role.

- CCD:CLR / [8SZB](https://www.rcsb.org/structure/8SZB): **hold_lipid_or_chemical_specificity_unresolved**; source topology `transmembrane`. Primary entry: Cryo-EM Structure of NINJ2 Filament at 3.07 Angstrom Resolution. CCD: CHOLESTEROL.

### MYOF — Q9NZM1

4 source records; 1 CCD identities. Short-chain PSF model in explicitly formulated lipid nanodiscs; preserve membrane-binding context and truncated myoferlin, no unique soluble endogenous ligand.

- CCD:PSF / [9H6X](https://www.rcsb.org/structure/9H6X): **hold_lipid_or_chemical_specificity_unresolved**; source topology `cytoplasmic`. Primary entry: Cryo-EM structure of lipid-bound human myoferlin (25 mol% DOPS/5 mol% PI(4,5)P2 nanodisc). CCD: 1,2-DICAPROYL-SN-PHOSPHATIDYL-L-SERINE.
- CCD:PSF / [9QKV](https://www.rcsb.org/structure/9QKV): **hold_lipid_or_chemical_specificity_unresolved**; source topology `cytoplasmic`. Primary entry: Human myoferlin (1-1997) in complex with an MSP2N2 lipid nanodisc (15 mol% DOPS, 5 mol% Cholesterol). CCD: 1,2-DICAPROYL-SN-PHOSPHATIDYL-L-SERINE.
- CCD:PSF / [9QLE](https://www.rcsb.org/structure/9QLE): **hold_lipid_or_chemical_specificity_unresolved**; source topology `cytoplasmic`. Primary entry: Human myoferlin (1-1997) in complex with an MSP2N2 lipid nanodisc (15 mol% DOPS, 2 mol% PI(4,5)P2). CCD: 1,2-DICAPROYL-SN-PHOSPHATIDYL-L-SERINE.
- CCD:PSF / [9QLF](https://www.rcsb.org/structure/9QLF): **hold_lipid_or_chemical_specificity_unresolved**; source topology `cytoplasmic`. Primary entry: Human myoferlin (1-1997) in complex with an MSP2N2 lipid nanodisc (25 mol% DOPS, 5 mol% PI(4,5)P2 and 5 mol% Cholesterol). CCD: 1,2-DICAPROYL-SN-PHOSPHATIDYL-L-SERINE.

### HCN3 — Q9P1Z3

1 source records; 1 CCD identities. cAMP-specific HCN3 regulation is supported by entry and study. Regulatory nucleotide held outside drug/substrate priorities.

- CCD:CMP / [8IO0](https://www.rcsb.org/structure/8IO0): **hold_regulatory_nucleotide_or_cofactor**; source topology `cytoplasmic`. Primary entry: Cryo-EM structure of human HCN3 channel with cAMP. CCD: ADENOSINE-3',5'-CYCLIC-MONOPHOSPHATE.

### BIN2 — Q9UBW5

1 source records; 1 CCD identities. HEPES buffer contact; no specific endogenous ligand claim.

- CCD:EPE / [4AVM](https://www.rcsb.org/structure/4AVM): **hold_preparation_additive**; source topology `unknown`. Primary entry: Crystal structure of the N-BAR domain of human bridging integrator 2.. CCD: 4-(2-HYDROXYETHYL)-1-PIPERAZINE ETHANESULFONIC ACID.

### UTS2R — Q9UKP6

1 source records; 1 CCD identities. Glycochenodeoxycholic acid is distinct from [Pen5]-urotensin peptide named by structure; possible preparation component, physiological receptor-ligand claim unresolved.

- CCD:CHO / [9JFK](https://www.rcsb.org/structure/9JFK): **hold_lipid_or_chemical_specificity_unresolved**; source topology `mixed:extracellular;transmembrane`. Primary entry: Cryo-EM structure of [Pen5]-urotensin (4-11)-bounded human Urotensin receptor (UTS2R)-Gq complex. CCD: GLYCOCHENODEOXYCHOLIC ACID.

### EPDR1 — Q9UM22

1 source records; 1 CCD identities. Nonaethylene glycol additive in EPDR1; not native lipoprotein cargo.

- CCD:2PE / [6E8N](https://www.rcsb.org/structure/6E8N): **hold_preparation_additive**; source topology `unknown`. Primary entry: Crystal structure of glycosylated human EPDR1. CCD: NONAETHYLENE GLYCOL.

### SHANK2 — Q9UPX8

1 source records; 1 CCD identities. BisTris buffer in L1800W Shank2 SAM mutant; no specific ligand promotion.

- CCD:BTB / [8B10](https://www.rcsb.org/structure/8B10): **hold_preparation_additive**; source topology `unknown`. Primary entry: Crystal Structure of Shank2-SAM mutant domain - L1800W. CCD: 2-[BIS-(2-HYDROXY-ETHYL)-AMINO]-2-HYDROXYMETHYL-PROPANE-1,3-DIOL.

### KCNK6 — Q9Y257

2 source records; 2 CCD identities. Heptane/decane contacts only; pimozide discussed in study is not these source chemicals.

- CCD:D10 / [9E94](https://www.rcsb.org/structure/9E94): **hold_hydrocarbon_or_partial_lipid_model**; source topology `mixed:cytoplasmic;transmembrane;unknown`. Primary entry: Cryo-EM structure of human TWIK-2 at pH 7.5. CCD: DECANE.
- CCD:HP6 / [9MEK](https://www.rcsb.org/structure/9MEK): **hold_hydrocarbon_or_partial_lipid_model**; source topology `transmembrane`. Primary entry: Structure of the human TWIK-2 potassium channel. CCD: HEPTANE.

### SLC5A6 — Q9Y289

2 source records; 2 CCD identities. 26VA and 26VC explicitly distinguish biotin and alpha-lipoic acid substrates. CCD LPA here is lipoic acid, not lysophosphatidic acid.

- CCD:BTN / [26VA](https://www.rcsb.org/structure/26VA): **promotion_candidate**; source topology `mixed:transmembrane;unknown`. Primary entry: Biotin-bound SMVT in the occluded state. CCD: BIOTIN.
- CCD:LPA / [26VC](https://www.rcsb.org/structure/26VC): **promotion_candidate**; source topology `mixed:transmembrane;unknown`. Primary entry: Alpha-lipoic acid-bound SMVT in the occluded state. CCD: LIPOIC ACID.

### SLC6A5 — Q9Y345

3 source records; 1 CCD identities. Only cholesterol is in the input. GlyT2 inhibitor names in the paper/title must not be assigned to CLR.

- CCD:CLR / [9HUE](https://www.rcsb.org/structure/9HUE): **hold_lipid_or_chemical_specificity_unresolved**; source topology `mixed:transmembrane;unknown`. Primary entry: Outward-open structure of human glycine transporter 2 bound to allosteric inhibitor ORG25543. CCD: CHOLESTEROL.
- CCD:CLR / [9HUF](https://www.rcsb.org/structure/9HUF): **hold_lipid_or_chemical_specificity_unresolved**; source topology `mixed:transmembrane;unknown`. Primary entry: Outward-open structure of human glycine transporter 2 bound to allosteric inhibitor RPI-GLYT2-82. CCD: CHOLESTEROL.
- CCD:CLR / [9HUG](https://www.rcsb.org/structure/9HUG): **hold_lipid_or_chemical_specificity_unresolved**; source topology `mixed:transmembrane;unknown`. Primary entry: Inward-open structure of human glycine transporter 2 in substrate-free state. CCD: CHOLESTEROL.

### TRPV2 — Q9Y5S1

6 source records; 3 CCD identities. 2-APB specifically modeled in S651H/T654D/D655N TRPV2, not WT. Hold canonical applicability; cholesterol/PE separate.

- CCD:CLR / [11HZ](https://www.rcsb.org/structure/11HZ): **hold_lipid_or_chemical_specificity_unresolved**; source topology `mixed:cytoplasmic;transmembrane`. Primary entry: Apo human TRPV2, wild-type. CCD: CHOLESTEROL.
- CCD:CLR / [11IA](https://www.rcsb.org/structure/11IA): **hold_lipid_or_chemical_specificity_unresolved**; source topology `mixed:cytoplasmic;transmembrane`. Primary entry: Apo human TRPV2, S651H/T654D/D655N. CCD: CHOLESTEROL.
- CCD:CLR / [11IB](https://www.rcsb.org/structure/11IB): **hold_lipid_or_chemical_specificity_unresolved**; source topology `mixed:cytoplasmic;transmembrane`. Primary entry: 2-APB bound human TRPV2, S651H/T654D/D655N. CCD: CHOLESTEROL.
- CCD:FZ4 / [11IB](https://www.rcsb.org/structure/11IB): **hold_specific_ligand_needs_context_or_construct_review**; source topology `mixed:cytoplasmic;transmembrane`. Primary entry: 2-APB bound human TRPV2, S651H/T654D/D655N. CCD: 2-aminoethyl diphenylborinate.
- CCD:PEX / [11HZ](https://www.rcsb.org/structure/11HZ): **hold_lipid_or_chemical_specificity_unresolved**; source topology `mixed:cytoplasmic;transmembrane`. Primary entry: Apo human TRPV2, wild-type. CCD: 1,2-DIDECANOYL-SN-GLYCERO-3-PHOSPHOETHANOLAMINE.
- CCD:PEX / [11IA](https://www.rcsb.org/structure/11IA): **hold_lipid_or_chemical_specificity_unresolved**; source topology `mixed:cytoplasmic;transmembrane`. Primary entry: Apo human TRPV2, S651H/T654D/D655N. CCD: 1,2-DIDECANOYL-SN-GLYCERO-3-PHOSPHOETHANOLAMINE.

### SLC30A1 — Q9Y6M5

4 source records; 1 CCD identities. AV0 is LMNG detergent. Zinc transport paper does not make this organic detergent a substrate.

- CCD:AV0 / [8XM6](https://www.rcsb.org/structure/8XM6): **hold_preparation_additive**; source topology `mixed:cytoplasmic;transmembrane`. Primary entry: Cryo-EM structure of human ZnT1 WT, in the absence of zinc, determined in an outward-facing conformation. CCD: Lauryl Maltose Neopentyl Glycol.
- CCD:AV0 / [8XMA](https://www.rcsb.org/structure/8XMA): **hold_preparation_additive**; source topology `mixed:cytoplasmic;transmembrane`. Primary entry: Cryo-EM structure of human ZnT1 WT, in the presence of zinc, determined in an outward-facing conformation. CCD: Lauryl Maltose Neopentyl Glycol.
- CCD:AV0 / [8XMF](https://www.rcsb.org/structure/8XMF): **hold_preparation_additive**; source topology `mixed:cytoplasmic;transmembrane`. Primary entry: Cryo-EM structure of human ZnT1 WT at a low PH, in the presence of zinc, determined in an inward-facing conformation.. CCD: Lauryl Maltose Neopentyl Glycol.
- CCD:AV0 / [8XMJ](https://www.rcsb.org/structure/8XMJ): **hold_preparation_additive**; source topology `mixed:cytoplasmic;transmembrane`. Primary entry: Cryo-EM structure of human ZnT1 WT, in the presence of zinc, determined in heterogeneous conformations- one subunit in an inward-facing and the other in an outward-facing conformation. CCD: Lauryl Maltose Neopentyl Glycol.

## Reproducibility

Run `uv run --no-sync python scripts/audit/audit_remaining_chemical_candidates.py --baseline-release /private/tmp/contact-review-50/release.json --excluded-observations /private/tmp/contact-expansion-review/chemical-observations.json`. The script does not fetch or publish; it uses bounded cached RCSB entry/CCD metadata. SHA-256 hashes of all four pinned inputs are recorded in the JSON.

Disposition totals: `{"hold_hydrocarbon_or_partial_lipid_model": 7, "hold_lipid_or_chemical_specificity_unresolved": 86, "hold_preparation_additive": 19, "hold_regulatory_nucleotide_or_cofactor": 9, "hold_specific_ligand_needs_context_or_construct_review": 15, "promotion_candidate": 28, "supported_alternate_structure_not_promoted": 7}`.
