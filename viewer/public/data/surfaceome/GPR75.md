# GPR75 — Surface Accessibility Brief

*Schema v1.0.0 · generated 2026-05-17T13:04:00.801564Z · model `claude-sonnet-4-6`*

> GPR75 is a 7-TM GPCR confirmed at the cell surface by non-permeabilizing sulfo-NHS-LC-biotin in SH-SY5Y cells and corroborated by HPA IHC (plasma membrane/primary cilium/vesicles, 'Supported'). Expression is strongly brain-restricted, with meaningful secondary presence in vascular cells, pancreatic islets, and retina. The dominant surface pool resides behind the BBB in hypothalamic and other CNS neurons; vascular and islet fractions are systemically accessible. Ciliary enrichment under high-fat diet conditions and agonist-driven internalization (CCL5, 20-HETE) add moderate state-dependence. GPR75 is an active anti-obesity drug target at preclinical stage.

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
| Evidence grade | Direct, single method |
| Triage signal | Likely accessible |

## 1. Executive summary

GPR75 is a 7-TM GPCR confirmed at the cell surface by non-permeabilizing sulfo-NHS-LC-biotin in SH-SY5Y cells and corroborated by HPA IHC (plasma membrane/primary cilium/vesicles, 'Supported'). Expression is strongly brain-restricted, with meaningful secondary presence in vascular cells, pancreatic islets, and retina. The dominant surface pool resides behind the BBB in hypothalamic and other CNS neurons; vascular and islet fractions are systemically accessible. Ciliary enrichment under high-fat diet conditions and agonist-driven internalization (CCL5, 20-HETE) add moderate state-dependence. GPR75 is an active anti-obesity drug target at preclinical stage.

## 2. Filters / catalog facets

| Group | Facets |
|---|---|
| Accessibility | overall=Moderate · conf=Moderate · subcategory=GPCR · grade=Direct, single method · ecd=Small · density=Moderate |
| Expression | level=Moderate · breadth=Restricted · specificity=Surface Dominant |
| Risks | shed=false · secreted=false · coreceptor=false · masking=false · subdomain=true |
| Cross-species | mouse=74.2% · cyno=98.9% |
| Paralogs | max %ECD identity = 35.7% |
| Topology | TM=7 · N-term-ECF=true · C-term-ECF=false |

## 3. Surface evidence

**Evidence grade** · Direct, single method

The strongest direct evidence comes from cell-surface biotinylation (sulfo-NHS-LC-biotin) in SH-SY5Y neuroblastoma cells (Dedoni et al. 2018), showing GPR75 at the plasma membrane under non-permeabilizing conditions and CCL5-induced internalization. Supporting evidence includes HPA IHC ('Supported' reliability; plasma membrane, primary cilium, vesicles) and immunofluorescence of tagged and endogenous GPR75 in primary cilia of hypothalamic neurons. No live-cell flow cytometry of GPR75 protein itself, mass-spec surfaceome, or intact non-permeabilized IF hits were found. Grade reflects one confirmed direct surface method corroborated by HPA and structural annotations.

### Surface Biotinylation — Direct Surface Accessibility

*Permeabilization: Nonpermeabilized · expression: Endogenous*

**Antibodies**

- anti-GPR75 (Abcam ab75581) (Abcam · ab75581 · AB_1523717) — Intracellular epitope; Moderate validation; Epitope aa 395–425 (intracellular C-terminus); CRISPR-Cas9 knockdown (~70% reduction) confirmed specificity in same study.

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| GPR75 detected at cell surface of RA-differentiated SH-SY5Y cells by sulfo-NHS-LC-biotin; CCL5 induced time-dependent internalization confirmed by streptavidin pulldown and GPR75 immunoblot. | Established Cell Line | Moderate | 2 |

### Permeabilized IF — Supports Surface Localization

*Permeabilization: Fixed Unknown · expression: Overexpression*

**Antibodies**

- anti-Flag M2 (M2 · MilliporeSigma) — Isoform Specific epitope; Moderate validation; Flag-tag antibody; specificity confirmed by 3xFlag-tagged knockin controls vs WT mice.

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| 3xFlag-Gpr75 in mIMCD3 and N11 cells localizes to primary cilia. Endogenous GPR75 in knockin mouse primary hypothalamic neurons co-localizes with ADCY3. Human GPR75 also cilia-localised; LOF mutations fail to reach cilia. | Established Cell Line | High | 2 |

### IHC Membranous — Supports Surface Localization

*Permeabilization: Permeabilized · expression: Endogenous*

**Antibodies**

- HPA antibody (GPR75) (Human Protein Atlas) — Unknown epitope; Weak validation

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| HPA IHC classifies GPR75 subcellular location as Plasma membrane, Primary cilium, and Vesicles with 'Supported' reliability tier across human tissue panel. | Primary Human Tissue | Moderate | 2 |

**Non-surface expression**

| Context | Sample | Measurement | Level | Cites |
|---|---|---|---|---|
| Northern blot showed 7 kb GPR75 transcript highly expressed in brain; in situ hybridisation localised transcript to retinal pigment epithelium and perivascular cells around retinal arterioles (Tarttelin et al. 1999). | Primary Human Tissue | RNA | High | 1 |
| Western blot of whole-cell lysates from RA-differentiated SH-SY5Y and rat cortical neurons detected GPR75 at ~59 kDa; lower intensity in astrocytes, undifferentiated SH-SY5Y, thymus, and spleen (Dedoni et al. 2018). | Established Cell Line | Bulk Protein | Moderate | 1 |
| In 3xFlag-Gpr75 knockin mice, endogenous GPR75 protein detected exclusively in brain by Flag-IP western blot; Gpr75 mRNA highest in brain vs all other mouse tissues by RT-qPCR (Jiang et al. 2024). | Primary Human Tissue | Bulk Protein | High | 1 |
| Exome sequencing of 645,626 individuals identified GPR75 PTVs associated with lower BMI and 54% lower odds of obesity; GPR75 classified as brain-expressed GPCR. Genetic association, not a direct surface assay (Akbari et al. 2021). | Patient Sample | Bulk Protein | Low | 1 |

**Therapeutic engagement**

*Preclinical In Vivo*

AstraZeneca and other companies have initiated GPR75 antagonist programs for obesity based on human genetics (PTVs → 54% lower obesity odds). Gpr75 knockout mice resist diet-induced weight gain. No approved drug or clinical trial for GPR75 documented in searched literature.

> Surface-form rationale: GPR75 is a 7-TM GPCR with extracellular N-terminus bearing three N-glycosylation sites and extracellular loops accessible at the plasma membrane and primary cilia. Antagonists targeting GPR75 engage the extracellular ligand-binding pocket at the cell surface.

**Contradicting evidence**

- *Alternative Localization* (severity Low): Jiang et al. 2024 found GPR75 localizes predominantly to primary cilia of hypothalamic neurons rather than the general plasma membrane; two obesity-protective LOF variants (p.Ala110fs, p.Gln234*) failed to reach the cilia or plasma membrane.
  - Likely explanation: Primary cilia are a specialised outgrowth of the plasma membrane and remain cell-surface accessible. Surface-biotinylation data independently confirmed surface-exposed GPR75 in SH-SY5Y cells. Ciliary localisation refines, rather than negates, surface accessibility.

## 4. Biological context

**Tissues × disease context**

| Tissue | Disease context | Level (protein) | Cell types | Cell states |
|---|---|---|---|---|
| brain | Normal | High | neurons, GABAergic neurons, glutamatergic neurons, monoaminergic neurons | — |
| spinal cord | Normal | High | neurons | — |
| retina | Normal | Moderate | retinal pigment epithelium cells, perivascular cells, cone photoreceptors | — |
| pancreatic islet | Normal | Moderate | beta cells | — |
| vasculature | Normal | Moderate | endothelial cells, vascular smooth muscle cells | — |
| prostate | Tumor | Moderate | prostate cancer cells (PC-3) | androgen-insensitive |

**Primary subcellular compartment**: Plasma membrane

**Anatomical accessibility**

- Vascular endothelial cells and smooth muscle cells — systemic circulation-facing — Blood Interstitial Facing · *Favorable*: GPR75 is expressed on the luminal surface of vascular endothelial cells and smooth muscle cells that are directly bathed by blood flow. A systemic binder would have straightforward access to these cell surfaces.
- Neuronal plasma membrane in brain parenchyma — Unknown · *Restricted*: GPR75 is highly expressed in brain neurons. Access by systemic macromolecular binders requires blood-brain barrier (BBB) crossing; this severely limits the accessibility of any systemically administered antibody or large molecule.
- Primary cilia of hypothalamic neurons — Ciliary · *Restricted*: GPR75 localizes to primary cilia of hypothalamic neurons under HFD conditions. Primary cilia project into restricted extracellular spaces within the brain parenchyma; even if BBB were bypassed, ciliary localization adds a further anatomical constraint on binder reach.
- Retinal pigment epithelium (RPE) and retinal perivascular cells — Unknown · *Restricted*: RPE sits behind the blood-retinal barrier. Perivascular cells around retinal arterioles face an intraocular fluid compartment. Both are poorly accessible to systemic large-molecule binders without specialized delivery.
- Pancreatic islet beta cells — Blood Interstitial Facing · *Favorable*: Pancreatic islets are highly vascularized; beta cells are adjacent to fenestrated capillaries. Systemically delivered binders can reach islet GPR75.

**Accessibility modulation**

- *Cell State Induced* · trigger: Nutrient Deprivation: Hypothalamic neurons under normal chow diet → Hypothalamic neurons under high-fat diet (HFD) feeding — GPR75 redistribution to primary cilia of hypothalamic cells is triggered by HFD feeding; GPR75 variants (Thinner L144P) and human obesity-protective variants fail to localize to cilia under the same conditions.
- *Activation Induced* · trigger: Cytokine Stimulation: Resting neuronal or endothelial cells with GPR75 at the cell surface → After CCL5 or 20-HETE ligand stimulation — CCL5 promotes time-dependent internalization of GPR75 from the plasma membrane in SH-SY5Y cells; 20-HETE activates GPR75 and recruits β-arrestin, initiating classical GPCR internalization.
- *Disease State Induced* · trigger: Oncogenic Transformation: Normal prostate epithelial cells with basal GPR75 expression → Androgen-insensitive prostate cancer cells (PC-3) exposed to 20-HETE — 20-HETE–GPR75 signaling drives EMT, MMP-2 release, actin stress fiber formation, cell invasion and anchorage-independent growth; GPR75 expression sustains a mesenchymal, invasive phenotype.
- *Tissue Restricted Surface* · lineage: Neural: Peripheral tissues with low or absent GPR75 expression → CNS neurons — brain regions including hypothalamus, hippocampus, cerebellum, substantia nigra, locus coeruleus — GPR75 mRNA and protein expression is markedly enriched in the CNS compared with peripheral tissues; mouse knockin data confirm endogenous protein is predominantly brain-restricted.

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
| ✓ | Q6X632 | Gpr75 | Q6X632 | One2one | 88.0% | 74.2% | 74.2% | 90 aa | 7 |

**Cynomolgus**

| Canonical | Isoform | Symbol | UniProt | Type | Full-length %id | ECD %id | ECD %sim | ECD len | TM |
|---|---|---|---|---|---|---|---|---|---|
| ✓ | A0A7N9DAV0 | GPR75 | A0A7N9DAV0 | One2one | 99.1% | 98.9% | 98.9% | 89 aa | 7 |

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
- rationale: Endogenous GPR75 co-localizes with cilia marker ADCY3 in primary hypothalamic neurons; HPA annotates primary cilium as a primary subcellular site. Under HFD, hypothalamic GPR75 is enriched in primary cilia, a subdomain with restricted access to systemic binders even if the BBB were bypassed.

**Co-receptor requirements**

- dependency: Modulatory
- evidence basis: Knockout
- partners: TULP3
- rationale: Ciliary trafficking of GPR75 requires TULP3; Tulp3-knockout cells lose ciliary GPR75 localization. However, GPR75 still reaches the general plasma membrane independently, so TULP3 is modulatory for ciliary targeting rather than required for any surface expression.

**ECD size assessment**

- ECD class: Small
- rationale: GPR75 is a class A GPCR with seven transmembrane domains. Its extracellular surface comprises a short N-terminal domain and three extracellular loops (ECLs); the N-terminus bears three predicted N-glycosylation sites but the overall exposed ECD is small relative to single-pass receptors, consistent with typical GPCR druggability via small molecules or nanobodies.

**Epitope masking**

- severity: Low
- evidence: Inferred
- mechanism: Glycan
- rationale: Three N-glycosylation sites are predicted on the extracellular N-terminus of GPR75 by sequence analysis. Glycan shielding of the small ECD could partially mask epitopes for antibody binders, but no experimental evidence in the ledger directly demonstrates masking; severity is rated low and inferred from topology.

## 9. Structure summary

| Field | Value |
|---|---|
| AFDB ID | [AF-O95800-F1](https://alphafold.ebi.ac.uk/entry/O95800) |
| AFDB version | v6 |
| ECD mean pLDDT | 65.4 |
| ECD disordered fraction | 57.3% |

Structure data from [AlphaFold DB](https://alphafold.ebi.ac.uk/entry/O95800) · © DeepMind / EMBL-EBI · licensed [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · cite `10.1038/s41586-021-03819-2`; `10.1093/nar/gkad1011`.

## 10. Evidence ledger

27 entries · 17 primary · 10 secondary · 0 tertiary · 7 PMC OA.

- `a1_evi_01` · *Primary* — GPR75 is present at the plasma membrane of differentiated SH-SY5Y cells; CCL5 induced time-dependent internalization of surface GPR75 beginning at 30 min, confirmed by streptavidin pulldown and GPR75 immunoblot. ([PMC6198807](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6198807/))
- `a1_evi_02` · *Primary* — Cell-impermeant sulfo-NHS-LC-biotin was used to label surface proteins on SH-SY5Y cells; biotinylated proteins were precipitated with streptavidin-agarose and GPR75 detected by immunoblot, establishing a direct cell-surface readout. ([PMC6198807](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6198807/))
- `a1_evi_03` · *Secondary* — Immunofluorescence in mIMCD3 cells expressing 3xFlag-Gpr75 showed GPR75 localisation to primary cilia (acetylated tubulin marker); ciliary localisation was TULP3-dependent and lost in Tulp3-knockout cells. ([PMC11444156](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11444156/))
- `a1_evi_04` · *Primary* — Endogenous GPR75 (3xFlag knockin) co-localises with cilia marker ADCY3 in primary mouse hypothalamic neurons; human GPR75 also cilia-localised in N11 cells; obesity-protective LOF mutations p.Ala110fs and p.Gln234* fail to reach primary cilia. ([PMC11444156](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11444156/))
- `a1_evi_05` · *Secondary* — Human Protein Atlas IHC data for GPR75 report subcellular locations as Plasma membrane, Primary cilium, and Vesicles, consistent with a 7-TM GPCR at the cell surface. (https://www.proteinatlas.org/ENSG00000119737/cell)
- `a1_evi_06` · *Secondary* — Human Protein Atlas flags GPR75 as plasma-membrane accessible with 'Supported' IHC reliability tier, indicating reproducible antibody-based evidence for membrane localisation. (https://www.proteinatlas.org/ENSG00000119737/cell)
- `a1_evi_07` · *Secondary* — Original GPR75 cloning paper (Tarttelin et al. 1999) identified a 540-aa protein with seven predicted transmembrane domains by sequence analysis; Northern blot showed a 7 kb transcript highly expressed in brain. (https://pubmed.ncbi.nlm.nih.gov/10381362/)
- `a1_evi_08` · *Secondary* — Western blot of whole-cell lysates from RA-differentiated SH-SY5Y cells and rat cortical neurons detected GPR75 at ~59 kDa; lower intensity in astrocytes, undifferentiated SH-SY5Y, thymus, and spleen. Bulk-protein expression readout, not surface-specific. ([PMC6198807](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6198807/))
- `a1_evi_09` · *Secondary* — Endogenous GPR75 protein detected exclusively in brain tissue of 3xFlag-Gpr75 knockin mice by Flag-IP western blot; Gpr75 mRNA highest in brain vs all other mouse tissues by RT-qPCR. Bulk-protein/RNA readout.
- `a1_evi_10` · *Secondary* — Exome sequencing of 645,626 individuals identified GPR75 PTVs associated with 1.8 kg/m² lower BMI and 54% lower odds of obesity; GPR75 classified as brain-expressed GPCR. Genetic association data, not a surface-localisation assay.
- `a1_evi_11` · *Secondary* — AstraZeneca and other companies have initiated GPR75 antagonist development as novel anti-obesity therapeutics, consistent with GPR75 being a druggable cell-surface GPCR. ([PMC12462478](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12462478/))
- `a1_evi_12` · *Secondary* — GPR75 is described as an anti-obesity target first discovered by human molecular genetics from the UKBiobank, affirming its status as a validated GPCR target accessible at the cell surface. ([PMC12462478](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12462478/))
- `a2_evi_01` · *Primary* — Northern blot analysis shows GPR75 mRNA is highly expressed in human brain and spinal cord, with in situ hybridization localizing transcripts to the retinal pigment epithelium (RPE) and perivascular cells surrounding retinal arterioles in human sections. (https://pubmed.ncbi.nlm.nih.gov/10381362/)
- `a2_evi_02` · *Primary* — GPR75 mRNA expression is abundant in the CNS more than peripheral tissues; RNAscope FISH in mouse CNS confirms GPR75 expression in GABAergic and glutamatergic neuronal populations across multiple brain regions.
- `a2_evi_03` · *Primary* — GPR75 mRNA is expressed in monoaminergic neurons in the substantia nigra/VTA, locus coeruleus, and raphe nucleus, and is highly expressed in cerebellar GABAergic and glutamatergic neurons in mouse brain.
- `a2_evi_04` · *Primary* — In situ hybridization on human retina sections localizes GPR75 transcripts to the RPE and perivascular cells surrounding retinal arterioles in the ganglion cell/nerve fiber layer. (https://pubmed.ncbi.nlm.nih.gov/10381362/)
- `a2_evi_05` · *Primary* — GPR75 is expressed in the retina and is functionally required to maintain cone photoreceptor health; knockout mice show age-dependent loss of M-cone and S-cone photoreceptor cells.
- `a2_evi_06` · *Primary* — Mouse and human pancreatic islets express GPR75 at the mRNA level; GPR75 protein is detected in islet cells by western blotting and immunohistochemistry. (https://pubmed.ncbi.nlm.nih.gov/23979485/)
- `a2_evi_07` · *Primary* — Mouse and human islets express GPR75 and its ligand CCL5; CCL5 via GPR75 increases beta-cell intracellular calcium and stimulates insulin secretion. (https://pubmed.ncbi.nlm.nih.gov/23979485/)
- `a2_evi_08` · *Primary* — GPR75 is expressed in cultured human endothelial cells and vascular smooth muscle cells; 20-HETE binding to GPR75 stimulates Gαq/11 dissociation and downstream signaling causing vasoconstriction and endothelial dysfunction in vascular cells.
- `a2_evi_09` · *Primary* — GPR75 is expressed in androgen-insensitive PC-3 prostate cancer cells; 20-HETE via GPR75 drives EMT, MMP-2 release, invasion, and anchorage-independent growth, which are blocked by GPR75 silencing.
- `a2_evi_10` · *Primary* — RNAscope technology identifies GPR75 puncta in NeuN-positive hippocampal neurons in mouse brain, and GPR75 knockout reduces synaptic markers (synapsin I and II), demonstrating neuronal expression.
- `a2_evi_11` · *Primary* — qPCR and flow cytometry confirm that SH-SY5Y human neuroblastoma cells express GPR75 but do not express CCR5, CCR3, or CCR1 receptors, establishing this cell line as a GPR75-expressing neuronal model.
- `a2_evi_12` · *Primary* — CCL5 promotes time-dependent internalization of GPR75 from the cell surface in SH-SY5Y neuroblastoma cells, indicating agonist-induced receptor endocytosis.
- `a2_evi_13` · *Primary* — Endogenous GPR75 protein is exclusively expressed in the brains of knockin mice and localizes to primary cilia of hypothalamic cells; GPR75 variants associated with lower BMI in humans fail to localize to primary cilia.
- `a2_evi_14` · *Secondary* — HPA database annotates GPR75 subcellular localization as plasma membrane, primary cilium, and vesicles, with IHC reliability rated as Supported. (https://www.proteinatlas.org/ENSG00000119737/cell)
- `a2_evi_15` · *Primary* — Large-scale exome sequencing of 645,626 individuals identifies GPR75 as one of five brain-expressed GPCRs with exome-wide significant association with BMI; protein-truncating variants in GPR75 are associated with 1.8 kg/m² lower BMI and 54% lower odds of obesity.

## Appendix · Downloads & reproduction

This Markdown is generated from the canonical JSON record at `/data/surfaceome/GPR75.json`. The JSON is the source of truth; this file is the human-readable mirror.

**Links**

- Viewer page: [https://surfaceome.deliverome.org/GPR75](https://surfaceome.deliverome.org/GPR75)
- Canonical JSON: [https://surfaceome.deliverome.org/data/surfaceome/GPR75.json](https://surfaceome.deliverome.org/data/surfaceome/GPR75.json)
- This Markdown: [https://surfaceome.deliverome.org/data/surfaceome/GPR75.md](https://surfaceome.deliverome.org/data/surfaceome/GPR75.md)
- AlphaFold DB entry: [https://alphafold.ebi.ac.uk/entry/O95800](https://alphafold.ebi.ac.uk/entry/O95800)
- AFDB prediction API: [https://alphafold.ebi.ac.uk/api/prediction/O95800](https://alphafold.ebi.ac.uk/api/prediction/O95800) (returns current `pdbUrl`, `cifUrl`, `uniprotSequence`, …)
- UniProt: [https://www.uniprot.org/uniprotkb/O95800](https://www.uniprot.org/uniprotkb/O95800)

### Canonical UniProt sequence

*540 aa · fetched from AFDB API at build time*

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
- Ensembl Compara orthologs & paralogs — ensembl_compara_2026_05_12 · open data with citation (EMBL-EBI; Howe et al. 2024 + Vilella et al. 2009)
- DeepTMHMM topology — deeptmhmm-1.0.24 · DTU Health Tech (Hallgren et al. 2022)
- UniProt — CC BY 4.0 (UniProt Consortium)

*Confidence moderate — A1 grades evidence as direct_single_method: one confirmed non-permeabilized surface-biotinylation study (Dedoni 2018) plus HPA IHC support. No mass-spec surfaceome, live-cell flow of GPR75 protein, or second independent direct surface method exists. A2 adds moderate state-dependence: ciliary enrichment is HFD-conditional and agonist-driven internalization reduces the accessible surface pool. The sole contradicting A1 item (ciliary vs. general membrane) is low severity but narrows the accessible compartment. No direct contradictions between A1/A2 surface calls. Combined, this justifies moderate rather than high confidence.*
