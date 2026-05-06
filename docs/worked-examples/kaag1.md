# Worked example — KAAG1 (Q9UBP8)

> **Status (2026-05-02):** Investigated by hand as a stress test of the M1 candidate-universe assembly. KAAG1 surfaced this way: it is listed as a delivery handle in Becca's positive-control set (sourced from patent WO2024036333A2) but received **zero votes** from the six M1 input sources. This document records (a) the diagnosis of why M1 missed it, (b) the actual primary biology, (c) why this case argues for two specific schema extensions before M3 prompt design, and (d) the verbatim quotes that would populate the evidence table.

## Headline

**KAAG1 is the canonical "out-of-scope but worth documenting" case for therapeutic delivery.** Its only well-characterized surface biology is **MHC-I peptide presentation** (LPRWPPPQL on HLA-B7), not conventional anchored display. The "tumor surface ADC target" framing lives in patents and corporate preclinical work, not in peer-reviewed primary literature. We should annotate it transparently — including the MHC-presentation mechanism — but treat it as an **edge case for a separate annotation lane**, not as a conventional surface protein.

## Identifier resolution

| Field | Value |
|---|---|
| HGNC symbol | KAAG1 |
| HGNC alias | RU2AS |
| NCBI Gene ID | 353219 |
| NCBI Gene description | "kidney associated DCDC2 antisense RNA 1" |
| Ensembl gene | ENSG00000146049 |
| Ensembl protein | ENSP00000274766 |
| UniProt accession | Q9UBP8 (Open Targets flags `source: uniprot_obsolete` — needs follow-up) |
| Locus | 6p22.3, antisense to first intron of DCDC2 |
| Length | 84 aa |
| Isoforms | 1 (no `ALTERNATIVE PRODUCTS` section in UniProt; single Chain 1–84) |
| `isoform_flattened` | `False` |

Sequence: `MDDDAAPRVEGVPVAVHKHALHDGLRQVAGPGAAAAHLPRWPPPQLAASRREAPPLSQRPHRTQGAGSPPETNEKLTNPQVKEK`

The antigenic 9-mer **LPRWPPPQL** corresponds to residues 38–46 of this ORF.

## DB-comparison panel (M1 sources)

| Source | Vote | Why |
|---|---|---|
| UniProt (`cc_scl_term_exact` + `ft_topo_dom:Extracellular`) | Miss | Entry has zero subcellular-location annotation and zero topology features. Query can't fire. |
| GO (`GO:0009986/0009897/0005887` + descendants) | Miss | Only GO annotation is `GO:0006955 immune response` (NAS — non-traceable author statement). No surface terms. |
| SURFY (in raw snapshot, `surfy_is_surface=0`) | Miss | SURFY ML rated not-surface. TM count, signal peptide, topology string, almen class columns are all empty — no features to learn from on an 84-aa orphan. |
| CSPA (Wollscheid MS-surfaceome, PMID 25894527) | Miss | Not detected in the cell-surface protein atlas. |
| DeepTMHMM | Miss (and not run) | Q9UBP8 not in the 22.8% subset processed; even if run, no TM helix to predict (highly Pro/Arg-rich, no hydrophobic stretch ≥19 aa). |
| HPA subcellular | Miss (subcell), partial (antibody) | No subcellular reliability call published; antibody HPA036021 exists (Antibodypedia 25266) but didn't pass HPA's PM threshold. |
| JensenLab COMPARTMENTS | Miss (top calls intracellular) | Integrated stars: cellular_component 3.37, intracellular 3.23, cytoplasm 2.02. "Membrane" only 0.65, "Extracellular region" 0.47 — below our surface threshold. |

Diagnosis: not a single-source bug. Each source is working as intended; KAAG1 is genuinely outside the rules every conventional source uses, because the surface-display biology is non-canonical.

## Primary biology — what KAAG1 actually is

The locus is bidirectionally transcribed. RU2S (sense) is ubiquitously expressed and not antigenic. RU2AS (= KAAG1, antisense) is tumor-enriched and encodes the antigenic ORF.

**Foundational paper — Brandle et al. 1999, J Exp Med, PMID [10601354](https://pubmed.ncbi.nlm.nih.gov/10601354/), PMC2195717:**

> Verbatim quote (candidate evidence span): *"The antigenic peptide recognized by the CTLs has the sequence LPRWPPPQL and is encoded by a new gene, which we named RU2. This gene is transcribed in both directions. The antigenic peptide is not encoded by the sense transcript, RU2S, which is expressed ubiquitously. It is encoded by an antisense transcript, RU2AS, which starts from a cryptic promoter located on the reverse strand of the first intron and ends up on the reverse strand of the RU2S promoter…"*

> Verbatim quote (tissue distribution): *"Antisense transcript RU2AS is expressed in a high proportion of tumors of various histological types. It is absent in most normal tissues, but is expressed in testis and kidney, and, at lower levels, in urinary bladder and liver. Short-term cultures of normal epithelial cells from the renal proximal tubule expressed significant levels of RU2AS message and were recognized by the CTLs."*

So the only well-characterized surface biology is: **HLA-B7 + LPRWPPPQL is recognized by CTLs on renal-carcinoma cells.** That is MHC-I peptide presentation, mechanistically distinct from a conventional anchored surface protein.

**Sequence properties of the 84-aa ORF** (consistent with the MHC-only story):
- N-terminus `MDDDAAPRVEGV` — no canonical signal-peptide cleavage site
- C-terminus `…NPQVKEK` — no GPI ω-site signal (no hydrophobic tail)
- No central hydrophobic stretch ≥19 aa — no transmembrane helix
- No annotated lipidation or glycosylation
- Highly Pro/Arg-rich — atypical for either a soluble globular protein or an anchored surface protein

The 84-aa polypeptide has **never been observed as a free polypeptide on a cell surface in any peer-reviewed paper** I could find.

## The "tumor surface ADC target" framing — provenance trail

PubMed coverage is genuinely thin: a bare-term search for "KAAG1" returns only 3 hits. NCBI gene2pubmed returns 6 PMIDs total for gene id 353219; of those, **only one is KAAG1-substantive primary research** (Brandle 1999); the others are bulk genomic / proteomic datasets that mention KAAG1 incidentally:

| PMID | Year | What it is |
|---|---|---|
| [10601354](https://pubmed.ncbi.nlm.nih.gov/10601354/) | 1999 | **Brandle et al., J Exp Med — foundational** |
| 14574404 | 2003 | Mungall et al. — chromosome 6 sequence |
| 12477932 | 2002 | Strausberg et al. — MGC cDNA bulk sequencing |
| 33961781 | 2021 | Huttlin et al. — BioPlex 3.0 (proteome-scale AP-MS) |
| 26598620 | 2015 | Dart et al. — PAK4/RhoU paper, KAAG1 mentioned incidentally |
| 15489334 | n/a | (one further bulk-genomic context) |

A second substantive paper, **Chandra et al. 2022, J Obstet Gynaecol Res, PMID [36184073](https://pubmed.ncbi.nlm.nih.gov/36184073/)**, reports KAAG1 promoter hypermethylation in cervical SCC.

**Everything else lives in patents and review-citation chains:**

- **WO2024036333A2** (the patent that put KAAG1 on Becca's handles list)
- **Alethia Biotherapeutics 2010–2012 patent family**: "ANTIBODIES THAT SPECIFICALLY BLOCK THE BIOLOGICAL ACTIVITY OF KIDNEY ASSOCIATED ANTIGEN 1" and related applications. Alethia's anti-KAAG1 mAb **H460-16-2** was the lead asset, with renal/ovarian/pancreatic cancer claims. This work appears never to have been published as primary peer-reviewed research.
- Recent ADC-target review articles (e.g., PMID 38159059, 36996620, 37821099, 36966267, 41238753) include KAAG1 in target-list tables, but trace those citations back and they all eventually point to the Alethia patents — not to original biological characterization.

When a recent review says *"KAAG1 is highly and selectively expressed on tumor cell surface,"* that statement is **two citation-hops removed from any primary surface-detection experiment.** The original primary experiment underlying the patent claims is mAb staining of fixed tumor sections (IHC), which doesn't formally distinguish:

- (a) free 84-aa polypeptide on the cell surface,
- (b) HLA-B7 + LPRWPPPQL complex (i.e. a TCR-mimic mAb), or
- (c) intracellular antigen made accessible by fixation/permeabilization.

This ambiguity is **the** load-bearing question for whether KAAG1 is a delivery handle. None of the public literature resolves it.

## Best sources for learning about KAAG1 (priority-ordered)

1. **Brandle et al. 1999** — PMID [10601354](https://pubmed.ncbi.nlm.nih.gov/10601354/), PMC free full text (PMC2195717). Read this first.
2. **NCBI Gene 353219** — current "antisense RNA 1" framing. Tells you the field's current view differs from UniProt's "canonical protein" view.
3. **UniProt Q9UBP8** — sparse but lists original references and tissue-specificity comment. **Verify obsolescence**: Open Targets returns `source: uniprot_obsolete` on this accession; needs a UniProt REST status / merged-into check.
4. **Open Targets** target page for ENSG00000146049 — full disease-evidence panel even when subcellular/tractability are empty.
5. **WO2024036333A2 + Alethia Bio 2010–2012 patent family** (Google Patents) — where the most concrete IHC/flow surface-detection data live, but unpublished.
6. **Chandra et al. 2022** — PMID [36184073](https://pubmed.ncbi.nlm.nih.gov/36184073/) — KAAG1 promoter hypermethylation in cervical SCC.
7. **The DCDC2 locus literature** — DCDC2 expression-regulation papers inform when KAAG1 (its antisense) is co-regulated.
8. **PDB** — empty. No structure deposited.
9. **HPA antibody HPA036021** — exists, raw IHC images may be available even though no subcellular call was published.

## Proposed annotation (with the existing schema)

| Field | Value |
|---|---|
| `surface_status` | `contradictory` |
| `topology` | `not_pm_associated` *(see schema-extension proposal below — this is the wrong answer in the existing enum, but it's the closest available value)* |
| `confidence` | `low` |
| `primary_evidence_count` | 1 (Brandle 1999) |
| `secondary_evidence_count` | several (review citations, patent citations) |
| `confidence_reasoning` | "Only one peer-reviewed primary paper characterizing KAAG1 biology, and that paper establishes MHC-I peptide presentation (LPRWPPPQL on HLA-B7), not conventional anchored surface display. The 'tumor surface ADC target' framing in review articles cites Alethia Biotherapeutics patent family (e.g. WO2024036333A2), which is not peer-reviewed. The 84-aa polypeptide has no canonical signal peptide, transmembrane helix, GPI ω-signal, or characterized lipidation. Direct surface-detection experiments distinguishing free polypeptide from MHC-bound peptide complex are absent from the literature." |
| `cited_evidence_ids` | PMID:10601354 (primary biology); WO2024036333A2 (patent surface claim); NCBI:Gene:353219 (current antisense-RNA framing); PMID:36184073 (cervical SCC methylation); Open Targets `uniprot_obsolete` flag |

## What this case argues for changing in the project

### (1) Add a `patent_handle_flag` 7th input lane to M1
Becca's `canonical_delivery_positive_controls.controls.json` already contains the patent-disclosed delivery handles (KAAG1, MELTF, GPR56, etc.) used as a downstream QC panel. If those rows were also a candidate-universe input source, KAAG1 would have entered the universe via that lane and been processed by the LLM pipeline. This is the smallest M1 change that would have caught it. ~50–100 genes affected.

### (2) Schema extension — `topology` enum
The current enum forces a choice from `{transmembrane_single_pass, transmembrane_multi_pass, outer_leaflet_peripheral, gpi_anchored, inner_leaflet_peripheral, cytosolic_pm_adjacent, not_pm_associated}`. None of these capture KAAG1. **Propose adding:**

- `topology = mhc_displayed_peptide` — applies to genes whose surface-display mechanism is MHC-I or MHC-II peptide presentation, not conventional anchoring. Therapeutically real (TCR-mimic ADCs, Foghorn/Cue/Gritstone-class biologics target this exact mechanism), and mechanistically distinct from any of the current values.
- `topology = empirical_surface_unknown_anchor` — applies to genes with credible empirical surface detection but no annotated anchor mechanism (small ORFs, dark proteins, antisense-encoded peptides). Distinct from `not_pm_associated` (which asserts non-association) and from the conventional-anchor values.

### (3) Schema extension — evidence-provenance grade
Add `evidence_provenance ∈ {peer_reviewed_primary, peer_reviewed_review, patent, corporate_preclinical, conference_abstract, db_annotation_only}` to `Evidence`. KAAG1 is the case where most "surface" evidence is `patent` or `corporate_preclinical`, and downstream consumers should be able to filter on this.

### (4) Document this as a worked-example category
"Out-of-scope-for-conventional-delivery but worth documenting" is a real category — also includes most cancer-testis antigens, MHC-displayed neoantigens with under-annotated parent loci, and antisense-encoded peptide antigens. The output table should let users **filter for or exclude** this category, not just collapse it into `surface_status=contradictory`.

## Open follow-ups

- Verify the `uniprot_obsolete` flag on Q9UBP8 — pull the current UniProt entry-status field and merged-into accession (if any).
- Pull Alethia Bio's full patent family (WO numbers, priority dates, claim language) to check whether the IHC/flow data are figure-disclosed and reproducible.
- Decide with Becca whether KAAG1 should be retained as a positive control in `surfaceome_control_panel.tsv` once the MHC-presentation framing is documented, or moved to a separate `mhc_displayed_handles` panel.
- Pre-register the `mhc_displayed_peptide` topology value as a v0 schema change before M3 prompt design, so the LLM has the right enum to emit.
