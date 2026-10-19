# Binder evidence coverage pilot — 16 September 2026

A dedicated binder section is feasible now: the pilot finds identifiable binders for **677/1,059 (63.9%) genes in the existing `classical_surface_receptor` triage category**. Reported live-cell antibody evidence is available for **385/1,059 (36.4%)**. The strictest existing validation subset is **174/1,059 (16.4%)**. These are different evidence levels, not interchangeable confidence scores.

This is a measured data pilot and an inspectable report, **not a production viewer/API rollout**. No live D1 records, prompts, or viewer snapshots were modified. No paid model calls were made.

Open [the searchable report](../../data/analysis/binder_coverage/report.html) locally to inspect a gene's binder names, reagent IDs, assay context, affinity/potency, broad epitope region, validation and sources. The [per-gene table](../../data/analysis/binder_coverage/gene_coverage.tsv) includes every denominator gene, including zero-coverage genes. [All observations](../../data/analysis/binder_coverage/observations.tsv.gz) are downloadable as a compressed TSV.

## Measured coverage

| Evidence available | Classical receptor category, n=1,059 | All candidate genes, n=5,574 |
|---|---:|---:|
| Any identifiable binder | 677 (63.9%) | 2,229 (40.0%) |
| Existing antibody with clone, catalog or RRID | 622 (58.7%) | 1,720 (30.9%) |
| Reported live-cell antibody | 385 (36.4%) | 683 (12.3%) |
| Live-cell antibody with recorded moderate/strong validation beyond vendor claims | 174 (16.4%) | 310 (5.6%) |
| IUPHAR interaction | 235 (22.2%) | 1,146 (20.6%) |
| IUPHAR antibody | 98 (9.3%) | 159 (2.9%) |
| IUPHAR endogenous ligand | 64 (6.0%) | 396 (7.1%) |
| IUPHAR approved drug | 85 (8.0%) | 514 (9.2%) |
| BioGRID designed binder, all scaffold classes | 44 (4.2%) | 84 (1.5%) |
| BioGRID minibinder / multivalent minibinder specifically | 11 (1.0%) | 15 (0.3%) |
| Quantitative measurement, including potency | 207 (19.5%) | 1,009 (18.1%) |
| IUPHAR Kd/Ki or pKd/pKi | 153 (14.4%) | 629 (11.3%) |
| Therapeutic-antibody sequence match | 81 (7.6%) | 134 (2.4%) |
| Exact-sequence antibody structure lead | 34 (3.2%) | 51 (0.9%) |

Categories overlap; do not sum them. The broader surface-positive triage set has 1,548/2,424 (63.9%) identifiable-binder coverage. The classical-receptor category is a pre-existing triage label, **not an exhaustive receptor ontology**; many GPCRs are assigned other labels. The denominator is gene-based: 5,680 accession rows collapse to 5,574 nonempty HGNC IDs, all found in the canonical identifier cache. Rows without HGNC IDs do not enter the denominator.

The 32,829 observation rows retain repeat assays and source overlap. They are not 32,829 unique binders. “Identifiable” includes intracellular/fixed-sample antibody reagents; the first row must not be advertised as extracellular binder coverage.

## What each source contributed

- **Existing public-D1 annotations:** 5,130 records queried; 4,081 candidate genes have annotations. They contain 16,923 candidate-gene antibody observations. Generic “anti-X” mentions without clone/catalog/RRID are preserved but excluded from identifiable-binder coverage. Existing specificity assessments and citations are inherited, not independently reaudited.
- **[IUPHAR/BPS](https://www.guidetopharmacology.org/download.jsp):** bulk interactions and ligand metadata, release 2026.3. Human-only target mappings use canonical UniProt accessions, including protein ligands when they are the target. Explicit complexes are kept as component associations but excluded from single-protein headline coverage. Kd/Ki, IC50/EC50 and log-molar quantities remain distinct. Missing original measurements (`-`) must not turn a pKi value into nM.
- **[Thera-SAbDab](https://opig.stats.ox.ac.uk/webapps/sabdab-sabpred/therasabdab/search/):** 1,133 therapeutic entries. Unambiguous exact therapeutic-name/alias matches enrich IUPHAR pairs with sequence availability and exact-sequence structure leads. No free-text target-symbol resolution. Its downloaded clinical-stage column is labeled February 2025, so this pilot does not reuse it as current clinical status. An antibody-only structure does not establish its epitope.
- **[BioGRID synthetic proteins](https://thebiogrid.org/project/12):** retrieved all 608 synthetic proteins and their detail pages, then mapped target pages through explicit HGNC IDs. The cohort receives 584 observations for 309 synthetic binder IDs across 84 genes; 61 genes have a reported affinity value. The scaffold classes include DARPins, monobodies, nanobodies, EndoTags and minibinders. Only 15 genes have records explicitly classified as minibinders. Species filters exclude nonhuman records. The public table's affinity text is preserved because its endpoint type is not always specified.

BioGRID “Surface Display” can mean yeast/phage display and is **not** counted as native mammalian live-cell binding. Other BioGRID associations can still need complex/construct adjudication in primary papers. IUPHAR target pharmacology alone does not locate a drug's binding site outside the cell.

## Literature feasibility and concrete epitope examples

The 84 BioGRID-matched candidate genes point to **76 distinct papers**. The [Europe PMC retrieval audit](../../data/analysis/binder_coverage/literature_retrieval.tsv) found metadata for all 76, retrieved full-text XML for 38, and found epitope/binding-site terms in the body of 32 and structural terms in 28. Supplementary-file availability is flagged for 52; supplements were not downloaded. Transient errors were retried. This is a lower bound from one full-text route, not an assessment of all possible publisher/Unpaywall access.

Keyword hits are review leads; they may concern another molecule, a prediction or background literature. They are **not** epitope evidence and do not enter an epitope coverage numerator.

To test whether the papers can actually supply the desired detail, two positive examples were inspected in [the TLR3 minibinder paper, PMID 39890776](https://pmc.ncbi.nlm.nih.gov/articles/PMC11785957/):

| Exact binder | Reported receptor binding region | Experimental evidence | Affinity in BioGRID |
|---|---|---|---|
| Minibinder 7.7 | Concave TLR3 surface, LRR15–LRRCT; receptor contacts include I510, I534, I566, I590 | Human ectodomain cryo-EM complex, 2.9 Å; [8YHT](https://www.rcsb.org/structure/8YHT) | 31 nM |
| Minibinder 8.6 | Concave TLR3 surface, LRR13–LRRCT; receptor contacts include I510, I534, I566, I590 | Human ectodomain cryo-EM complex, 2.9 Å; [8YHU](https://www.rcsb.org/structure/8YHU) | 37 nM |

These examples are separately recorded in [literature_examples.tsv](../../data/analysis/binder_coverage/literature_examples.tsv), with source locators and a full-text checksum. Contacts are the authors' reported human TLR3 numbering, not an independently computed complete interface or verified UniProt coordinate mapping. The constructs use K27–A700 ectodomain. The paper also distinguishes multivalent agonists from monomeric binders; their functions should not be transferred between formats. One selected positive paper cannot estimate proteome-wide epitope coverage.

## Recommended production increment

1. Promote existing exact reagent observations into a dedicated “Known binders” section, retaining assay and permeabilization context, validation method and citation. Do not hide unvalidated/intracellular context under an overall confidence badge.
2. Add an independent, versioned binder-observation store populated by IUPHAR and BioGRID, keyed by HGNC ID plus source binder ID and assay. Use Thera-SAbDab for sequence/structure links. Do not rerun the full deep-dive pipeline for these deterministic imports.
3. Start the literature pass with the 76 source-linked BioGRID papers and exact antibody structure leads. Extract binder identity, species, construct, binding endpoint, domain/contact residues, numbering reference and supporting figure/table. Validate residue coordinates against the referenced isoform before displaying them on a sequence.
4. Publish separate labels for binding evidence, epitope evidence, and live-cell accessibility. “Measured affinity; epitope unknown; live-cell accessibility untested” is a useful result.

ChEMBL, BindingDB and IEDB were not imported in this pilot. The legacy SAbDab bulk URL returned an HTML application rather than a data table and was not counted as structural coverage. Additional sources may improve coverage; missing rows are not evidence of absent binders.

## Reproduce and inspect

```bash
uv run python scripts/audit/fetch_binder_coverage.py
uv run python -m accessible_surfaceome.binders.coverage
uv run python scripts/audit/probe_binder_literature.py
uv run python scripts/audit/render_binder_coverage.py
uv run pytest -q tests/test_binder_coverage.py
```

The fetch step needs the existing public-D1 read configuration in `.env`. Database downloads and full text remain under ignored `data/external/binder_coverage/`. `--refresh` downloads updated source records. Exact replay of the normalized tables requires the source files with matching checksums; a fresh fetch can reflect changed upstream databases. The committed observation export and coverage tables permit independent reanalysis without those credentials. The two literature examples are a deliberately selected, assistant-reviewed curation input; they are not generated by keyword matching.

[Source manifest](../../data/analysis/binder_coverage/source_manifest.json) records URLs, queries and hashes; [analysis manifest](../../data/analysis/binder_coverage/manifest.json) records input/output fingerprints and assumptions. IUPHAR-derived contents retain CC BY-SA 4.0 attribution and the database ODbL terms; BioGRID data are MIT licensed. Thera-SAbDab sequences and paper full text are not republished.

Validation: seven focused regression tests pass; Ruff, scoped type checking, Python compilation and report JavaScript syntax checks pass. The repository-wide check stops on the existing environment's missing `pydssp` dependency. An attempted full pytest run encountered network-dependent failures and was interrupted while retrying unavailable network access; it is not reported as a pass. Browser security policy blocked local-file preview, so the report has not been visually verified in this session.
