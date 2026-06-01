# GPR75 — Surface Accessibility Brief

*Schema v1.1.0 · generated 2026-05-30T15:41:15.685694Z · model `claude-sonnet-4-6`*

> GPR75 is a Class A orphan GPCR (Gαq-coupled, 7TM) with canonical plasma-membrane topology confirmed by computational prediction, GPCRdb annotation, BRET trafficking assay, and immunofluorescence localizing the endogenous protein to primary cilia of hypothalamic neurons. Expression is predominantly CNS-restricted (brain/spinal cord >> periphery), with secondary sites in retina and pancreatic islets. The receptor is surface-accessible but CNS localization limits systemic binder access; pancreatic beta cells represent the most therapeutically tractable peripheral compartment. Evidence grade is supportive-but-indirect; no direct live-cell flow or surface biotinylation data exist.

**Vitals**

| Field | Value |
|---|---|
| HGNC | [HGNC:4526](https://www.genenames.org/data/gene-symbol-report/#!/hgnc_id/HGNC:4526) |
| UniProt | [O95800](https://www.uniprot.org/uniprotkb/O95800) |
| NCBI Gene | [10936](https://www.ncbi.nlm.nih.gov/gene/10936) |
| Ensembl | [ENSG00000119737](https://www.ensembl.org/Homo_sapiens/Gene/Summary?g=ENSG00000119737) |
| Subcategory | GPCR |
| Surface accessibility | Moderate |
| Confidence | Moderate |
| Evidence grade | Supportive but indirect |
| Triage signal | Likely accessible |

## 1. Executive summary

GPR75 is a Class A orphan GPCR (Gαq-coupled, 7TM) with canonical plasma-membrane topology confirmed by computational prediction, GPCRdb annotation, BRET trafficking assay, and immunofluorescence localizing the endogenous protein to primary cilia of hypothalamic neurons. Expression is predominantly CNS-restricted (brain/spinal cord >> periphery), with secondary sites in retina and pancreatic islets. The receptor is surface-accessible but CNS localization limits systemic binder access; pancreatic beta cells represent the most therapeutically tractable peripheral compartment. Evidence grade is supportive-but-indirect; no direct live-cell flow or surface biotinylation data exist.

## 2. Filters / catalog facets

| Group | Facets |
|---|---|
| Accessibility | overall=Moderate · conf=Moderate · subcategory=GPCR · grade=Supportive but indirect · ecd=Moderate · density=High |
| Expression | level=High · breadth=Restricted · specificity=Surface Dominant |
| Risks | shed=false · secreted=false · coreceptor=false · masking=true · subdomain=true |
| Cross-species | mouse=74.2% · cyno=98.9% |
| Paralogs | max %ECD identity = 35.7% |
| Topology | TM=7 · N-term-ECF=true · C-term-ECF=false |

## 3. Surface evidence

**Evidence grade** · Supportive but indirect

No direct surface assay (live-cell flow, non-permeabilized IF, surface biotinylation, or IHC with nonperm specification) is present. The strongest positive evidence is: (1) immunofluorescence showing GPR75 in primary cilia of hypothalamic cells (a plasma-membrane subdomain; moderate weight, but permeabilization status unspecified); (2) IP-MS from endogenous-knockin brain lysate with KO controls (moderate weight, fractionation not surface-specific); and (3) a BRET PM-trafficking assay in HEK293 OE cells (low weight, exogenous signal peptide). These collectively imply surface localization consistent with canonical Class A GPCR topology (supported by computational predictions and GPCRdb annotation), but none constitute a direct extracellular-face surface assay. Grade: supportive_but_indirect.

### Whole Cell Proteomics — Weak Or Ambiguous

*Permeabilization: Unknown · expression: Knock In Tag*

**Antibodies**

- anti-Flag — Unknown epitope; Strong validation; Validated by parallel Gpr75-/- knockout mice generated in same study; Flag tag inserted at endogenous Gpr75 locus.

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Brain lysate from 3xFlag-Gpr75 knockin mice; endogenous-level expression across multiple brain regions | Ex Vivo | Moderate | 1 |

### Whole Cell Proteomics — Supports Membrane Association

*Permeabilization: Unknown · expression: Knock In Tag*

**Antibodies**

- anti-Flag — Unknown epitope; Strong validation; Gpr75-/- knockout mice used as negative control for immunoprecipitation specificity.

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Flag immunoprecipitates from 3xFlag-Gpr75 knockin mouse brain lysates; GPR75-interacting proteins identified by mass spectrometry | Ex Vivo | Moderate | 1 |

### Permeabilized IF — Supports Surface Localization

*Permeabilization: Fixed Unknown · expression: Knock In Tag*

**Antibodies**

- anti-Flag — Unknown epitope; Strong validation; 3xFlag knockin at endogenous Gpr75 locus; Gpr75-/- mice serve as negative control. Fixation confirmed; permeabilization status not explicitly stated.

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Primary hypothalamic cells from 3xFlag-Gpr75 knockin mice; GPR75 localizes to primary cilia; Thinner mutation L144P and some human GPR75 variants fail to localize to cilia | Ex Vivo | Moderate | 1 |

### IHC Membranous — Expression Only

*Permeabilization: Permeabilized · expression: Endogenous*

**Antibodies**

- anti-GPR75 — Unknown epitope; None validation

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Pancreatic islets; GPR75 detected by western blot and immunohistochemistry; mRNA expression confirmed by qRT-PCR | Primary Human Tissue | Moderate | 1 |

### Unknown — Supports Surface Localization

*Permeabilization: Live Cell · expression: Overexpression*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| HEK293 cells overexpressing GPR75 with exogenous cleavable signal sequence fused to Rluc8; BRET to plasma membrane marker indicates efficient trafficking to cell surface | Established Cell Line | Moderate | 1 |

**Non-surface expression**

| Context | Sample | Measurement | Level | Cites |
|---|---|---|---|---|
| Mouse brain (multiple regions), endogenous 3xFlag-Gpr75 knockin mice | Ex Vivo | Bulk Protein | Moderate | 1 |
| Pancreatic islets (islet cells, implied beta cells) | Primary Human Tissue | Bulk Protein | Moderate | 1 |
| Pancreatic islets — mRNA expression of CCL5 receptors including GPR75 | Primary Human Tissue | RNA | Moderate | 1 |
| Pancreatic islets — IHC protein detection | Primary Human Tissue | IHC Protein | Moderate | 1 |

## 4. Biological context

**Tissues × disease context**

| Tissue | Disease context | Level (protein) | Cell types | Cell states |
|---|---|---|---|---|
| brain | Normal | High | GABAergic neurons, glutamatergic neurons, monoaminergic neurons (dopaminergic, noradrenergic, serotonergic) | — |
| brain | Normal | High | GABAergic neurons, glutamatergic neurons, monoaminergic neurons (dopaminergic, noradrenergic, serotonergic) | — |
| retina | Normal | High | retinal pigment epithelium, perivascular cells of retinal arterioles | — |
| retina | Normal | High | photoreceptors (inner segments), outer plexiform layer neurons | — |
| cerebellum | Normal | High | cerebellar GABAergic neurons, cerebellar glutamatergic neurons | — |
| hippocampus | Normal | High | neurons | — |
| substantia nigra / ventral tegmental area | Normal | High | dopaminergic neurons | — |
| locus coeruleus | Normal | High | noradrenergic neurons | — |
| raphe nucleus | Normal | High | serotonergic neurons | — |
| spinal cord | Normal | Moderate | — | — |
| pancreatic islet | Normal | Moderate | pancreatic beta cells | — |
| pancreatic islet | Normal | Moderate | pancreatic beta cells | — |
| pancreatic beta cell line (NIT-1) | Normal | Moderate | NIT-1 pancreatic beta cells | liraglutide-treated (10 nM, 60 min) — upregulated |
| spleen | Normal | Low | — | — |
| kidney | Normal | Low | — | — |
| heart | Normal | Low | — | — |
| hypothalamus | Other Disease | Unknown | — | high-fat diet-induced obesity |
| peripheral blood mononuclear cells / platelets | Normal | Unknown | B cells, CD4+ T cells, CD8+ T cells, NK cells, dendritic cells, monocytes, GM-CSF-treated macrophage-like monocytes, platelets | — |

**Primary subcellular compartment**: Plasma membrane

**Anatomical accessibility**

- hypothalamic neurons (primary cilia) — Ciliary · *Restricted*: GPR75 localizes to primary cilia of hypothalamic cells. Cilia are behind the blood-brain barrier and within a specialized membrane subdomain; systemic binders face dual barriers (BBB + ciliary compartment), severely restricting access.
- CNS neurons (brain and spinal cord) — Unknown · *Restricted*: GPR75 is predominantly expressed in CNS neurons. The blood-brain barrier prevents systemic antibodies/binders from accessing parenchymal neurons, making CNS-expressed GPR75 largely inaccessible to peripherally delivered therapeutics.
- pancreatic islet beta cells — Blood Interstitial Facing · *Favorable*: Pancreatic islets are highly vascularized and lack a tight-junction barrier equivalent to the BBB. GPR75 shows functional surface expression in beta cells responding to exogenous CCL5, indicating the receptor faces the islet interstitium accessible to systemic delivery.

**Accessibility modulation**

- *Tissue Restricted Surface* · lineage: Neural: Peripheral tissues (spleen, kidney, heart) and most non-CNS organs → CNS neurons (brain and spinal cord) across multiple regions — GPR75 protein and mRNA are predominantly restricted to the CNS, with significantly higher expression in brain and spinal cord versus peripheral tissues. Endogenous protein is exclusively detected in brain in knockin mice.
- *Tissue Restricted Surface* · lineage: Specialized Somatic Other: General retinal tissue without cell-type specificity → Human retinal pigment epithelium (RPE) and perivascular cells surrounding retinal arterioles — In human retina, GPR75 transcript is specifically localized to RPE and perivascular cells of retinal arterioles, not uniformly across all retinal cell types.
- *Dual Localization*: Hypothalamic cells with wild-type GPR75 (normal BMI-associated variants) → Hypothalamic cells expressing Thinner mutation (L144P) or human GPR75 variants associated with lower BMI — Wild-type GPR75 localizes to primary cilia of hypothalamic cells; the L144P (Thinner) mutation and lower-BMI-associated human variants fail to traffic to the ciliary membrane, losing ciliary surface localization.
- *Tissue Restricted Surface* · lineage: Endocrine: Non-islet pancreatic tissue or general non-endocrine tissues → Pancreatic islets (beta cells) in mouse and human — GPR75 is expressed at mRNA and protein level specifically in pancreatic islets, with functional surface expression confirmed by CCL5-evoked calcium signaling in live primary beta cells.
- *Cell State Induced* · trigger: Other: Unstimulated NIT-1 pancreatic beta cells → NIT-1 pancreatic beta cells treated with 10 nM liraglutide (GLP-1 receptor agonist) for 60 min — GPR75 mRNA levels are significantly upregulated at 60 min following liraglutide treatment, suggesting transcriptional induction of GPR75 in beta cells under GLP-1 agonist stimulation.

## 5. Isoforms

*Deterministic · UniProt + DeepTMHMM deeptmhmm-1.0.24*

| Isoform | UniProt | TM | N-term | Signal pep | ECD len | ICD len |
|---|---|---|---|---|---|---|
| **canonical** | O95800 | 7 | Extracellular | 0 aa | 89 aa | 296 aa |

## 6. Paralogs

*Compara Compara r112*

| Paralog | UniProt | ECD %id | Family |
|---|---|---|---|
| OR9G1 | [Q8NH87](https://www.uniprot.org/uniprotkb/Q8NH87) | 35.7% | Bilateria |
| OR51F1 | [A6NGY5](https://www.uniprot.org/uniprotkb/A6NGY5) | 30.7% | Bilateria |
| GPR19 | [Q15760](https://www.uniprot.org/uniprotkb/Q15760) | 28.7% | Bilateria |
| OR11A1 | [Q9GZK7](https://www.uniprot.org/uniprotkb/Q9GZK7) | 26.5% | Bilateria |
| OR11G2 | [Q8NGC1](https://www.uniprot.org/uniprotkb/Q8NGC1) | 26.4% | Bilateria |
| NPY1R | [P25929](https://www.uniprot.org/uniprotkb/P25929) | 25.8% | Bilateria |
| TACR2 | [P21452](https://www.uniprot.org/uniprotkb/P21452) | 25.0% | Bilateria |
| NPY4R | [P50391](https://www.uniprot.org/uniprotkb/P50391) | 25.0% | Bilateria |
| NPY4R2 | [P0DQD5](https://www.uniprot.org/uniprotkb/P0DQD5) | 25.0% | Bilateria |
| PRLHR | [P49683](https://www.uniprot.org/uniprotkb/P49683) | 24.7% | Bilateria |
| OR11H2 | [Q8NH07](https://www.uniprot.org/uniprotkb/Q8NH07) | 24.7% | Bilateria |
| OR11H1 | [Q8NG94](https://www.uniprot.org/uniprotkb/Q8NG94) | 24.7% | Bilateria |
| PROKR1 | [Q8TCW9](https://www.uniprot.org/uniprotkb/Q8TCW9) | 23.6% | Bilateria |
| OR11H12 | [B2RN74](https://www.uniprot.org/uniprotkb/B2RN74) | 23.5% | Bilateria |
| GPR83 | [Q9NYM4](https://www.uniprot.org/uniprotkb/Q9NYM4) | 23.0% | Bilateria |
| TACR3 | [P29371](https://www.uniprot.org/uniprotkb/P29371) | 22.7% | Bilateria |
| NPY2R | [P49146](https://www.uniprot.org/uniprotkb/P49146) | 22.5% | Bilateria |
| OR9A4 | [Q8NGU2](https://www.uniprot.org/uniprotkb/Q8NGU2) | 22.4% | Bilateria |
| OR9A2 | [Q8NGT5](https://www.uniprot.org/uniprotkb/Q8NGT5) | 21.2% | Bilateria |
| MCHR1 | [Q99705](https://www.uniprot.org/uniprotkb/Q99705) | 20.7% | Bilateria |
| OR11H7 | [Q8NGC8](https://www.uniprot.org/uniprotkb/Q8NGC8) | 20.6% | Bilateria |
| PROKR2 | [Q8NFJ6](https://www.uniprot.org/uniprotkb/Q8NFJ6) | 20.2% | Bilateria |
| NPY5R | [Q15761](https://www.uniprot.org/uniprotkb/Q15761) | 20.2% | Bilateria |
| OR11H6 | [Q8NGC7](https://www.uniprot.org/uniprotkb/Q8NGC7) | 19.7% | Bilateria |
| OR10X1 | [Q8NGY0](https://www.uniprot.org/uniprotkb/Q8NGY0) | 19.0% | Bilateria |
| GPR88 | [Q9GZN0](https://www.uniprot.org/uniprotkb/Q9GZN0) | 18.6% | Bilateria |
| OR11H4 | [Q8NGC9](https://www.uniprot.org/uniprotkb/Q8NGC9) | 18.4% | Bilateria |
| MCHR2 | [Q969V1](https://www.uniprot.org/uniprotkb/Q969V1) | 17.5% | Bilateria |
| GPR50 | [Q13585](https://www.uniprot.org/uniprotkb/Q13585) | 15.6% | Bilateria |
| TACR1 | [P25103](https://www.uniprot.org/uniprotkb/P25103) | 15.2% | Bilateria |
| MTNR1A | [P48039](https://www.uniprot.org/uniprotkb/P48039) | 14.5% | Bilateria |
| MTNR1B | [P49286](https://www.uniprot.org/uniprotkb/P49286) | 12.5% | Bilateria |

*Per-antibody cross-reactivity behavior is captured per-clone under §3 (Surface evidence → antibodies). The LLM cross-reactivity verdict is deferred to v1.x.*

## 7. Orthologs

**Mouse**

| Canonical | Isoform | Symbol | UniProt | Type | Full-length %id | ECD %id | ECD %sim | ECD len | TM |
|---|---|---|---|---|---|---|---|---|---|
| ✓ | Q6X632 | Gpr75 | [Q6X632](https://www.uniprot.org/uniprotkb/Q6X632) | One2one | 88.0% | 74.2% | 74.2% | 89 aa | 7 |

**Cynomolgus**

| Canonical | Isoform | Symbol | UniProt | Type | Full-length %id | ECD %id | ECD %sim | ECD len | TM |
|---|---|---|---|---|---|---|---|---|---|
| ✓ | A0A7N9DAV0 | GPR75 | [A0A7N9DAV0](https://www.uniprot.org/uniprotkb/A0A7N9DAV0) | One2one | 99.1% | 98.9% | 98.9% | 89 aa | 7 |

## 8. Accessibility risks

**Shed form**

- present: false
- severity: Low
- evidence: Weak

**Secreted form**

- present: false
- severity: Low
- evidence: Weak

**Restricted subdomain**

- present: true
- severity: Moderate
- evidence: Strong
- domain: Ciliary
- rationale: IF in endogenous 3xFlag-Gpr75 knockin hypothalamic cells shows GPR75 concentrated at the primary cilium membrane subdomain. Ciliary localization is variant-dependent: Thinner L144P and lower-BMI human variants fail to traffic to cilia. For CNS-targeted binders this is a compounding restriction (BBB + ciliary compartment).

**Co-receptor requirements**

- dependency: None
- evidence basis: Trafficking
- rationale: GPR75 is a canonical Class A GPCR; surface trafficking follows the constitutive secretory pathway. The BRET trafficking assay and ciliary IF data show surface delivery without any obligate co-receptor. No evidence in the ledger implicates a chaperone or partner required for membrane insertion.

**ECD size assessment**

- ECD class: Moderate
- rationale: GPR75 is a 540-aa Class A GPCR with a canonical extracellular N-terminus and three extracellular loops (ECL1-3). The combined extracellular-accessible surface of a typical Class A GPCR N-terminus + ECLs totals ~80-120 residues, placing it in the moderate class. ECLs are the primary binder-engagement surface for GPCR antibodies.

**Epitope masking**

- severity: Moderate
- evidence: Inferred
- mechanism: Conformational
- rationale: Class A GPCRs characteristically bury ECL2 deep in the orthosteric pocket and present conformationally flexible loops. No direct glycan-shielding or partner-masking data exist for GPR75 in the ledger, but conformational restriction of ECLs is an intrinsic feature of the 7TM fold relevant to antibody epitope accessibility.

## 9. Structure summary

| Field | Value |
|---|---|
| AFDB ID | [AF-O95800-F1](https://alphafold.ebi.ac.uk/entry/O95800) |
| AFDB version | v6 |
| ECD mean pLDDT | 65.4 |
| ECD disordered fraction | 57.3% |

Structure data from [AlphaFold DB](https://alphafold.ebi.ac.uk/entry/O95800) · © DeepMind / EMBL-EBI · licensed [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · cite `10.1038/s41586-021-03819-2`; `10.1093/nar/gkad1011`.

## 10. Evidence ledger

30 entries · 19 primary · 11 secondary · 0 tertiary · 22 PMC OA.

- `a1_evi_01` · *Primary* — The original 1999 cloning paper (Tarttelin et al.) reports sequence-based prediction of seven transmembrane domains for GPR75, classifying it as a G-protein coupled receptor with canonical 7TM topology. This is the foundational topology assignment from the discovery paper. (https://pubmed.ncbi.nlm.nih.gov/10381362/)
- `a1_evi_02` · *Secondary* — Review-level topology summary from GPCRdb annotation: GPR75 has 7 transmembrane helices, 3 extracellular loops (ECL1-3) accessible outside the receptor for ligand binding, 3 intracellular loops (ICL1-3) for G-protein interaction, an extracellular N-terminus, and a cytoplasmic C-terminus. This is consistent with canonical Class A GPCR topology placing the N-terminal domain and ECLs at the extracellular face. ([PMC12071931](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12071931/))
- `a1_evi_03` · *Secondary* — GPR75 is a 540-amino-acid protein encoded by 2 exons on human chromosome 2p16, providing the basic structural context for the receptor's architecture relevant to surface-accessibility framing. ([PMC10495892](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10495892/))
- `a1_evi_04` · *Primary* — CRISPR/Cas9-generated 3xFlag-Gpr75 knockin mice were produced by inserting a 3xFlag tag at the endogenous Gpr75 locus using the native Gpr75 sequence context (no foreign signal peptide substitution). The knockin construct retains the native N-terminal signal sequence, ensuring that any trafficking or localization observed reflects the endogenous protein's biology. Gpr75-knockout (Gpr75-/-) mice were also generated in parallel, providing genetic KO validation controls. This methodological approach enables endogenous-level surface detection via immunoprecipitation with anti-Flag antibodies. ([PMC11444156](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11444156/))
- `a1_evi_05` · *Primary* — Mass spectrometric identification of GPR75-interacting proteins from Flag immunoprecipitates of 3xFlag-Gpr75 knockin mouse brain lysates. This experiment uses endogenous-level expression (knockin, not overexpression) with anti-Flag antibody pulldown from brain tissue, establishing that GPR75 protein is detectable in brain at endogenous expression levels. The use of KO mice as controls (paired generation in same paper) validates antibody specificity. This supports surface accessibility in the context of neuronal/brain membrane protein interaction networks. ([PMC11444156](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11444156/))
- `a1_evi_06` · *Secondary* — Endogenous GPR75 protein, detected using 3xFlag-tagged knockin mice (endogenous locus), is expressed in the brains of these mice with consistent expression across different brain regions. This is a tissue-level expression observation at the protein level using endogenous-tagging strategy, supporting that GPR75 protein is present in brain tissue. Does not directly demonstrate surface localization without fractionation, but the endogenous knockin context and subsequent IP-MS data in the same paper support membrane-resident form. ([PMC11444156](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11444156/))
- `a1_evi_07` · *Primary* — GPR75 localizes to the primary cilia of hypothalamic cells, representing a specialized membrane compartment accessible from the extracellular face. The Thinner mutation L144P and certain human GPR75 variants associated with lower BMI fail to localize to cilia, implying that loss of ciliary surface localization is relevant to the protein's physiological function. This is a topology/subcellular surface accessibility finding: GPR75 reaches the ciliary membrane (a plasma membrane subdomain), but specific variants abolish this localization. ([PMC11444156](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11444156/))
- `a1_evi_08` · *Secondary* — In the BRET-based GPCR trafficking assay (PMC8062009), GPR75 and other receptors were expressed using constructs in which the receptor coding sequence was amplified with a common forward primer corresponding to a cleavable signal sequence (exogenous/foreign signal peptide, not the native Gpr75 signal sequence) and ligated into a pRluc8-N1 vector. This means the overexpression construct uses an exogenous signal peptide, which forces secretory-pathway entry regardless of native protein trafficking. Surface localization results from this system should be interpreted with caution as they may not fully reflect endogenous trafficking behavior. OE construct uses foreign SP (preprotein cleavable signal sequence from common primer), not the native GPR75 leader. ([PMC8062009](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8062009/))
- `a1_evi_09` · *Secondary* — In a BRET-based GPCR trafficking screen, GPR75 (along with most other tested receptors) showed substantial BRET to a plasma membrane marker and less BRET to an ER marker, indicating efficient trafficking to the cell surface. This is functional BRET evidence for plasma membrane localization of GPR75 in an overexpression system. Note: the construct uses an exogenous cleavable signal sequence (see paired methods clip), so trafficking is partially forced; evidence tier is secondary/supportive-indirect rather than primary. The result is directionally positive for surface presence. ([PMC8062009](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8062009/))
- `a1_evi_10` · *Secondary* — BRET methodology detail: interactions between GPCRs including GPR75 and G proteins are monitored using BRET between receptors fused to Renilla luciferase (Rluc8) and G protein heterotrimers tagged with Venus fluorescent protein. This functional assay at the plasma membrane monitors cell-surface receptor–G protein interactions, providing methodological context for interpreting the surface trafficking BRET result. The assay measures receptor–G protein coupling at the cell surface, indirectly supporting surface localization. ([PMC8062009](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8062009/))
- `a1_evi_11` · *Secondary* — GPR75 was detected in pancreatic islets by western blotting and immunohistochemistry. mRNA expression of islet CCL5 receptors including GPR75 was measured by quantitative RT-PCR. The IHC provides protein-level localization evidence in islet tissue, while WB confirms protein expression. Neither WB nor IHC in this context explicitly demonstrates surface fractionation (whole-cell WB; tissue IHC without surface-specific method), so these are non-surface expression observations that qualify a surface claim (protein present in islet cells but surface localization not specifically resolved by these methods). (https://pubmed.ncbi.nlm.nih.gov/23979485/)
- `a2_evi_01` · *Primary* — GPR75 mRNA is highly expressed in human brain, detected as a 7 kb transcript by Northern blot in the original cloning study. This establishes brain as a primary expression site. (https://pubmed.ncbi.nlm.nih.gov/10381362/)
- `a2_evi_02` · *Primary* — GPR75 transcript is localized in human retinal pigment epithelium (RPE) and in cells surrounding retinal arterioles (perivascular cells), as shown by in situ hybridization and Northern blot analysis of human retinal sections. (https://pubmed.ncbi.nlm.nih.gov/10381362/)
- `a2_evi_03` · *Primary* — In mouse retina, GPR75 transcript localizes to photoreceptor inner segments and the outer plexiform layer — a distinct cellular distribution from human retina where it is found in RPE and perivascular cells. This cross-species discrepancy in retinal cell-type distribution is noteworthy. (https://pubmed.ncbi.nlm.nih.gov/10381362/)
- `a2_evi_04` · *Primary* — GPR75 mRNA is expressed across all analysed CNS regions in mouse, with significant variation between brain areas and spinal cord, following a pattern consistent with the Human Protein Atlas. ([PMC12920073](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12920073/))
- `a2_evi_05` · *Primary* — GPR75 mRNA expression is significantly higher in the CNS (brain and spinal cord) compared to peripheral tissues including spleen, kidney, and heart in mouse, consistent with Human Protein Atlas data. ([PMC12920073](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12920073/))
- `a2_evi_06` · *Primary* — GPR75 mRNA is expressed in multiple neuronal populations in the mouse CNS, including GABAergic and glutamatergic neurons across brain regions. ([PMC12920073](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12920073/))
- `a2_evi_07` · *Primary* — GPR75 mRNA is highly expressed in monoaminergic neurons in select mouse brain regions: substantia nigra/ventral tegmental area (dopaminergic), locus coeruleus (noradrenergic), and raphe nucleus (serotonergic). ([PMC12920073](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12920073/))
- `a2_evi_08` · *Primary* — GPR75 mRNA is highly expressed in cerebellar GABAergic and glutamatergic neurons in mouse, suggesting a role in motor/equilibrium activity. ([PMC12920073](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12920073/))
- `a2_evi_09` · *Secondary* — GPR75 mRNA is abundant in neurons of the mouse hippocampus, as previously established by Speidell et al. 2023. ([PMC12920073](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12920073/))
- `a2_evi_10` · *Primary* — Endogenous GPR75 protein is exclusively expressed in the brains of knockin mice (3xFlag-Gpr75), with consistent expression across different brain regions, confirmed by protein-level detection in a physiologically tagged animal model. ([PMC11444156](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11444156/))
- `a2_evi_11` · *Primary* — GPR75 protein localizes to the primary cilia of hypothalamic cells. The Thinner mutation (L144P) and human GPR75 variants associated with lower BMI fail to localize to the cilia, implicating ciliary surface localization as functionally important for energy regulation. This places GPR75 at the ciliary membrane subdomain in hypothalamic neurons. ([PMC11444156](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11444156/))
- `a2_evi_12` · *Primary* — Mouse and human pancreatic islets express GPR75 at mRNA level (RT-PCR) and protein level (western blot and IHC), establishing islets as a primary expression site for GPR75. (https://pubmed.ncbi.nlm.nih.gov/23979485/)
- `a2_evi_13` · *Primary* — GPR75 is detected in mouse and human islets by western blotting and immunohistochemistry. The study was specifically designed to test whether islet cells express GPR75 as a receptor for CCL5 to mediate calcium elevation and insulin secretion in beta cells. (https://pubmed.ncbi.nlm.nih.gov/23979485/)
- `a2_evi_14` · *Primary* — In pancreatic beta cells, CCL5 reversibly increases intracellular calcium via GPR75 in a phospholipase C- and calcium-influx-dependent manner, confirming functional surface expression of GPR75 in primary beta cells and its coupling to Gq signaling. (https://pubmed.ncbi.nlm.nih.gov/23979485/)
- `a2_evi_15` · *Primary* — In mouse NIT-1 pancreatic beta cells, GPR75 mRNA levels are significantly upregulated at 60 min with 10 nM liraglutide treatment (GLP-1 receptor agonist), suggesting transcriptional induction of GPR75 expression in beta cells under GLP-1 agonist stimulation. ([PMC12058015](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12058015/))
- `a2_evi_16` · *Secondary* — GPR75, a 540 amino acid Gαq-class GPCR, was originally characterized for its expression in the human retina, establishing the retina as its founding tissue-expression context. ([PMC12920073](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12920073/))
- `a2_evi_17` · *Secondary* — GPR75 plays critical roles in metabolic health, glucose regulation, and stability of the nervous and cardiovascular systems, establishing its biological relevance across these organ systems. ([PMC12071931](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12071931/))
- `a2_evi_18` · *Secondary* — GPCR transcript profiling was performed across human white blood cell populations (B cells, CD4+ T cells, CD8+ T cells, NK cells, dendritic cells, monocytes, GM-CSF-treated macrophage-like monocytes) and platelets using a sensitive semi-quantitative method. GPR75 may or may not be among the ~160 GPCR mRNAs detected on average. ([PMC11436766](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11436766/))
- `a2_evi_19` · *Primary* — Gpr75 knockout mice show reduced food intake under high-fat diet (HFD) conditions, with pair-feeding normalizing body weight. This loss-of-function phenotype in hypothalamic feeding circuits supports GPR75's functional role in the CNS under HFD-induced metabolic state. ([PMC11444156](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11444156/))

## Appendix · Downloads & reproduction

This Markdown is generated from the canonical JSON record at `/data/surfaceome/GPR75.json`. The JSON is the source of truth; this file is the human-readable mirror.

**Links**

- Viewer page: [https://surfaceome.deliverome.org/GPR75](https://surfaceome.deliverome.org/GPR75)
- Canonical JSON: [https://surfaceome.deliverome.org/data/surfaceome/GPR75.json](https://surfaceome.deliverome.org/data/surfaceome/GPR75.json)
- This Markdown: [https://surfaceome.deliverome.org/data/surfaceome/GPR75.md](https://surfaceome.deliverome.org/data/surfaceome/GPR75.md)
- AlphaFold DB entry: [https://alphafold.ebi.ac.uk/entry/O95800](https://alphafold.ebi.ac.uk/entry/O95800)
- AFDB prediction API: [https://alphafold.ebi.ac.uk/api/prediction/O95800](https://alphafold.ebi.ac.uk/api/prediction/O95800) (returns current `pdbUrl`, `cifUrl`, `uniprotSequence`, …)
- UniProt: [https://www.uniprot.org/uniprotkb/O95800](https://www.uniprot.org/uniprotkb/O95800)

**AlphaFold model downloads**

- mmCIF model: [https://alphafold.ebi.ac.uk/files/AF-O95800-F1-model_v6.cif](https://alphafold.ebi.ac.uk/files/AF-O95800-F1-model_v6.cif)
- PDB model: [https://alphafold.ebi.ac.uk/files/AF-O95800-F1-model_v6.pdb](https://alphafold.ebi.ac.uk/files/AF-O95800-F1-model_v6.pdb)
- PAE (predicted aligned error) JSON: [https://alphafold.ebi.ac.uk/files/AF-O95800-F1-predicted_aligned_error_v6.json](https://alphafold.ebi.ac.uk/files/AF-O95800-F1-predicted_aligned_error_v6.json)
- AFDB model version: 6

### Canonical UniProt sequence

*540 aa · `O95800` · embedded at build time*

```
   1  MNSTGHLQDAPNATSLHVPHSQEGNSTSLQEGLQDLIHTATLVTCTFLLAVIFCLGSYGN
  61  FIVFLSFFDPAFRKFRTNFDFMILNLSFCDLFICGVTAPMFTFVLFFSSASSIPDAFCFT
 121  FHLTSSGFIIMSLKTVAVIALHRLRMVLGKQPNRTASFPCTVLLTLLLWATSFTLATLAT
 181  LKTSKSHLCLPMSSLIAGKGKAILSLYVVDFTFCVAVVSVSYIMIAQTLRKNAQVRKCPP
 241  VITVDASRPQPFMGVPVQGGGDPIQCAMPALYRNQNYNKLQHVQTRGYTKSPNQLVTPAA
 301  SRLQLVSAINLSTAKDSKAVVTCVIIVLSVLVCCLPLGISLVQVVLSSNGSFILYQFELF
 361  GFTLIFFKSGLNPFIYSRNSAGLRRKVLWCLQYIGLGFFCCKQKTRLRAMGKGNLEVNRN
 421  KSSHHETNSAYMLSPKPQKKFVDQACGPSHSKESMVSPKISAGHQHCGQSSSTPINTRIE
 481  PYYSIYNSSPSQEESSPCNLQPVNSFGFANSYIAMHYHTTNDLVQEYDSTSAKQIPVPSV
```

### Canonical ortholog sequences

**Mouse — Gpr75** (`Q6X632` · 540 aa)

```
   1  MNTSAPLQNVPNATLLNMPPLHGGNSTSLQEGLRDFIHTATLVTCTFLLAIIFCLGSYGN
  61  FIVFLSFFDPSFRKFRTNFDFMILNLSFCDLFICGVTAPMFTFVLFFSSASSIPDSFCFT
 121  FHLTSSGFVIMSLKMVAVIALHRLRMVMGKQPNCTASFSCILLLTLLLWATSFTLATLAT
 181  LRTNKSHLCLPMSSLMDGEGKAILSLYVVDFTFCVAVVSVSYIMIAQTLRKNAQVKKCPP
 241  VITVDASRPQPFMGASVKGNGDPIQCTMPALYRNQNYNKLQHSQTHGYTKNINQMPIPSA
 301  SRLQLVSAINFSTAKDSKAVVTCVVIVLSVLVCCLPLGISLVQMVLSDNGSFILYQFELF
 361  GFTLIFFKSGLNPFIYSRNSAGLRRKVLWCLRYTGLGFLCCKQKTRLRAMGKGNLEINRN
 421  KSSHHETNSAYMLSPKPQRKFVDQACGPSHSKESAASPKVSAGHQPCGQSSSTPINTRIE
 481  PYYSIYNSSPSQQESGPANLPPVNSFGFASSYIAMHYYTTNDLMQEYDSTSAKQIPIPSV
```

**Cynomolgus — GPR75** (`A0A7N9DAV0` · 540 aa)

```
   1  MNSTGHLQDAPNATSLHVPHSPEGNSTSLQEGLQDLIHTATLVTCTFLLAVIFCLGSYGN
  61  FIVFLSFFDPAFRKFRTNFDFMILNLSFCDLFICGVTAPMFTFVLFFSSASSIPDAFCFT
 121  FHLTSSGFIIMSLKTVAVIALHRLRMVLGKQPNRMASFPCTVLLTLLLWATSFTLATLAT
 181  LKTSKSHLCLPMSSLIAGKGKAILSLYVVDFTFCVAVVSVSYIMIAQTLRKNAQVRKCPP
 241  VITVDASRPQPFMGVPVQGGGDPIQCAMPALYRNQNYNKLQHVQTRGYTKSPNQLATPAA
 301  SRLQLVSAINLSTAKDSKAVVTCVIIVLSVLVCCLPLGISLVQVVLSSNGSFILYQFELF
 361  GFTLIFFKSGLNPFIYSRNSAGLRRKVLWCLQYIGLGFFCCKQKTRLRAMGKGNLEVNRN
 421  KSSHHETNSAYMLSPKPQKKFVDQACGPSHSKESVVSPKISAGHQHCGQSSSTPINTRIE
 481  PYYSIYNSSPSQEESSPCNLQPVNSFGFANSYIAMHYHTTNDLMQEYDSTSAKQIPVPSV
```

### Per-residue DeepTMHMM topology

*Five-letter alphabet: `M` = TM helix, `O` = extracellular, `I` = intracellular, `S` = signal peptide, `B` = β-strand. Aligned to the UniProt sequence above (residue indices in the left column).*

**canonical** (`O95800`, deeptmhmm-1.0.24)

```
   1  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOMMMMMMMMMMMMMMMMMMM
  61  MMMMMIIIIIIIIIIIIIIIMMMMMMMMMMMMMMMMMMMMMMMMMMOOOOOOOOOOOOOO
 121  MMMMMMMMMMMMMMMMMMMMMIIIIIIIIIIIIIIIIIIIIMMMMMMMMMMMMMMMMMMM
 181  MOOOOOOOOOOOOOOOOOOOOMMMMMMMMMMMMMMMMMMMMMMMIIIIIIIIIIIIIIII
 241  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 301  IIIIIIIIIIIIIIIIIIIIIIMMMMMMMMMMMMMMMMMMMMOOOOOOOOOOOOOOMMMM
 361  MMMMMMMMMMMMMMMMMIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 421  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 481  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
```

### Data sources

- AlphaFold DB structures — CC BY 4.0 (© DeepMind / EMBL-EBI)
- DeepTMHMM topology — deeptmhmm-1.0.24 · DTU Health Tech (Hallgren et al. 2022)
- Ensembl Compara orthologs & paralogs — ensembl_compara_2026_05_12 · open data with citation (EMBL-EBI; Howe et al. 2024 + Vilella et al. 2009)
- SURFACE-Bind binding-site scoring — MaSIF-based surface patch scoring on the AlphaFold model (Balbi et al. 2026, [PMID 41604262](https://pubmed.ncbi.nlm.nih.gov/41604262/), PNAS) · [surface-bind.inria.fr](https://surface-bind.inria.fr/)
- UniProt — CC BY 4.0 (UniProt Consortium)

*Confidence moderate — Confidence is moderate because no direct surface-specific assay (live-cell flow cytometry, non-permeabilized immunostaining, or surface biotinylation) has been published for GPR75. The surface call rests on canonical GPCR topology (computational + GPCRdb), a BRET trafficking assay using an exogenous signal peptide construct, and ciliary IF with unspecified permeabilization — all supportive but indirect. Additionally, the ciliary localization finding comes from a single study (PMC11444156). Confidence would be lifted by a live-cell antibody staining or surface biotinylation experiment on endogenous GPR75-expressing neurons or beta cells, or by an independent group confirming ciliary trafficking in hypothalamic preparations.*
