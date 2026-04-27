> **Companion one-pager:** [`docs/onepagers/m1-candidate-universe/index.html`](../onepagers/m1-candidate-universe/index.html) (PDF: [`m1-candidate-universe.pdf`](../onepagers/m1-candidate-universe/m1-candidate-universe.pdf)). That document describes how the seven primary sources are merged into the M1 candidate universe; this report is the source-methodology companion — per-source dossiers, cross-source dependency matrix, and full citation index.

The strongest dependencies are not symmetric across all seven sources. The main downstream aggregator is **COMPARTMENTS**, which explicitly combines UniProtKB knowledge, GO term mapping/propagation, HPA immunofluorescence data, STRING 9.1-based dictionaries for text mining of Medline abstracts, and WoLF PSORT/YLoc predictors. The main bidirectional dependency is **UniProt ↔ GO/GOA**: GOA builds human GO annotations by mapping UniProt controlled vocabularies and InterPro to GO terms, while UniProt exposes GO annotations and GO mappings in its own records and subcellular-location vocabulary. Orthogonally, **SURFY** depends directly on **CSPA** for its positive training set, whereas **DeepTMHMM** looked comparatively standalone in the primary-source material I could retrieve. **HPA** sits between these layers by explicitly comparing its IF patterns against UniProtKB/Swiss-Prot and exporting GO-id columns. ([ORBilu][1])

## Deliverable 0 — Documentation Index

| #   | Source       | Document title                                                                             | Type                  | View URL                                                                                                               | Download URL                                                                                                          | Version / date               | Access date (UTC) | Notes                                                                              |
| --- | ------------ | ------------------------------------------------------------------------------------------ | --------------------- | ---------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- | ---------------------------- | ----------------- | ---------------------------------------------------------------------------------- |
| D1  | UniProt      | UniProt: the Universal Protein Knowledgebase in 2025                                       | Paper (peer-reviewed) | [view](https://academic.oup.com/nar/article/53/D1/D609/7902999)                                                        | [pdf](https://academic.oup.com/nar/advance-article-pdf/doi/10.1093/nar/gkae1010/60719276/gkae1010.pdf)                | 2025                         | 2026-04-18        | OA                                                                                 |
| D2  | UniProt      | UniProt release 2026_01                                                                    | Help page             | [view](https://www.uniprot.org/release-notes/2026-01-28-release)                                                       | view-only                                                                                                             | Released 2026-01-27/28       | 2026-04-18        | Release used for the user’s UniProt snapshot                                       |
| D3  | UniProt      | Release Notes                                                                              | Help page             | [view](https://www.uniprot.org/release-notes)                                                                          | view-only                                                                                                             | current index                | 2026-04-18        | Release history landing page                                                       |
| D4  | UniProt      | Downloads | UniProt help                                                                   | Help page             | [view](https://www.uniprot.org/help/downloads)                                                                         | view-only                                                                                                             | updated 2026-01-29           | 2026-04-18        | States update cadence                                                              |
| D5  | UniProt      | License & disclaimer | UniProt help                                                        | License               | [view](https://www.uniprot.org/help/license)                                                                           | view-only                                                                                                             | updated 2024-12-17           | 2026-04-18        | CC BY 4.0                                                                          |
| D6  | UniProt      | Subcellular location | UniProt help                                                        | Help page             | [view](https://www.uniprot.org/help/subcellular_location)                                                              | view-only                                                                                                             | updated 2026-01-29           | 2026-04-18        | Current help for CC/SUBCELLULAR LOCATION                                           |
| D7  | UniProt      | Gene Ontology (GO) | UniProt help                                                          | Help page             | [view](https://www.uniprot.org/help/gene_ontology)                                                                     | view-only                                                                                                             | updated 2026-04-01           | 2026-04-18        | Current GO help                                                                    |
| D8  | UniProt      | Evidence | UniProt help                                                                    | Help page             | [view](https://www.uniprot.org/help/evidences)                                                                         | view-only                                                                                                             | updated 2025-11-25           | 2026-04-18        | Includes GO evidence-note language                                                 |
| D9  | UniProt      | UniProt FTP docs directory                                                                 | Download-page note    | [view](https://ftp.uniprot.org/pub/databases/uniprot/current_release/knowledgebase/complete/docs/)                     | view-only                                                                                                             | Release 2026_01 / 2026-01-28 | 2026-04-18        | Directory listing for docs files                                                   |
| D10 | UniProt      | subcell.txt                                                                                | Data-file header      | [view](https://ftp.uniprot.org/pub/databases/uniprot/current_release/knowledgebase/complete/docs/subcell.txt)          | [txt](https://ftp.uniprot.org/pub/databases/uniprot/current_release/knowledgebase/complete/docs/subcell.txt)          | Release 2026_01 / 2026-01-28 | 2026-04-18        | Controlled vocabulary with GO mappings                                             |
| D11 | UniProt      | userman.htm                                                                                | Help page             | [view](https://ftp.uniprot.org/pub/databases/uniprot/current_release/knowledgebase/complete/docs/userman.htm)          | [html](https://ftp.uniprot.org/pub/databases/uniprot/current_release/knowledgebase/complete/docs/userman.htm)         | Release 2026_01 / 2026-01-28 | 2026-04-18        | Flat-file manual                                                                   |
| D12 | UniProt      | sec_ac.txt                                                                                 | Data-file header      | [view](https://ftp.uniprot.org/pub/databases/uniprot/current_release/knowledgebase/complete/docs/sec_ac.txt)           | [txt](https://ftp.uniprot.org/pub/databases/uniprot/current_release/knowledgebase/complete/docs/sec_ac.txt)           | 2026-01-28                   | 2026-04-18        | Secondary-to-primary accession mapping                                             |
| D13 | UniProt      | delac_sp.txt                                                                               | Data-file header      | [view](https://ftp.uniprot.org/pub/databases/uniprot/current_release/knowledgebase/complete/docs/delac_sp.txt)         | [txt](https://ftp.uniprot.org/pub/databases/uniprot/current_release/knowledgebase/complete/docs/delac_sp.txt)         | 2026-01-28                   | 2026-04-18        | Deleted Swiss-Prot accessions                                                      |
| D14 | UniProt      | Proteomes · Homo sapiens (Human) (UP000005640)                                             | Help page             | [view](https://www.uniprot.org/proteomes/UP000005640)                                                                  | view-only                                                                                                             | current                      | 2026-04-18        | Page indexed; exact reviewed-human FASTA button target not exposed in static fetch |
| D15 | GO           | GO citation policy and license                                                             | Help page             | [view](https://geneontology.org/docs/go-citation-policy/)                                                              | view-only                                                                                                             | current                      | 2026-04-18        | Cites GO 2026 paper DOI and terms                                                  |
| D16 | GO           | Guide to GO evidence codes                                                                 | Help page             | [view](https://geneontology.org/docs/guide-go-evidence-codes/)                                                         | view-only                                                                                                             | current                      | 2026-04-18        | Current evidence-code guide                                                        |
| D17 | GO           | GO Association File (GAF) format 2.2                                                       | Help page             | [view](https://geneontology.org/docs/go-annotation-file-gaf-format-2.2/)                                               | view-only                                                                                                             | current                      | 2026-04-18        | Current GAF spec                                                                   |
| D18 | GO           | Download Annotations | Gene Ontology Consortium                                            | Download-page note    | [view](https://current.geneontology.org/products/pages/downloads.html)                                                 | view-only                                                                                                             | release 2026-03-25           | 2026-04-18        | Current release page; CC BY 4.0 footer                                             |
| D19 | GO           | goa_human.gaf.gz (current)                                                                 | Data-file header      | [view](https://current.geneontology.org/annotations/goa_human.gaf.gz)                                                  | [gaf.gz](https://current.geneontology.org/annotations/goa_human.gaf.gz)                                               | release 2026-03-25           | 2026-04-18        | Current human GAF                                                                  |
| D20 | GO           | GO Archive                                                                                 | Help page             | [view](https://geneontology.org/docs/go-archives/)                                                                     | view-only                                                                                                             | current                      | 2026-04-18        | Archive structure and deprecated/current formats                                   |
| D21 | GO           | Gene Ontology Data Archive — 2026-01-23                                                    | Download-page note    | [view](https://release.geneontology.org/2026-01-23/)                                                                   | view-only                                                                                                             | 2026-01-23                   | 2026-04-18        | January 2026 release root                                                          |
| D22 | GO           | goa_human.gaf.gz (archive 2026-01-23)                                                      | Data-file header      | [view](https://release.geneontology.org/2026-01-23/annotations/goa_human.gaf.gz)                                       | [gaf.gz](https://release.geneontology.org/2026-01-23/annotations/goa_human.gaf.gz)                                    | 2026-01-23                   | 2026-04-18        | Archive path inferred from official release structure                              |
| D23 | GO           | Electronic Annotation Methods | EBI GOA                                                    | Help page             | [view](https://www.ebi.ac.uk/GOA/ElectronicAnnotationMethods)                                                          | view-only                                                                                                             | current                      | 2026-04-18        | GOA pipeline overview                                                              |
| D24 | GO           | UniProtKB-Subcellular Location2GO | EBI GOA                                                | Help page             | [view](https://www.ebi.ac.uk/GOA/SubcellularLocation2GO)                                                               | view-only                                                                                                             | current                      | 2026-04-18        | UniProt SL → GO mapping page                                                       |
| D25 | GO           | UniProtKB-Keyword2GO | EBI GOA                                                             | Help page             | [view](https://www.ebi.ac.uk/GOA/Keyword2GO)                                                                           | view-only                                                                                                             | current                      | 2026-04-18        | UniProt keywords → GO mapping page                                                 |
| D26 | GO           | InterPro2GO mapping | EBI GOA                                                              | Help page             | [view](https://www.ebi.ac.uk/GOA/InterPro2GO)                                                                          | view-only                                                                                                             | current                      | 2026-04-18        | InterPro → GO mapping page                                                         |
| D27 | SURFY        | The in silico human surfaceome                                                             | Paper (peer-reviewed) | [view](https://www.pnas.org/doi/10.1073/pnas.1808790115)                                                               | [pdf](https://www.pnas.org/doi/pdf/10.1073/pnas.1808790115)                                                           | 2018                         | 2026-04-18        | Publisher article and PDF                                                          |
| D28 | SURFY        | The in silico human surfaceome — PMC                                                       | Paper (peer-reviewed) | [view](https://pmc.ncbi.nlm.nih.gov/articles/PMC6243280/)                                                              | view-only                                                                                                             | 2018                         | 2026-04-18        | OA mirror                                                                          |
| D29 | SURFY        | In silico human surfaceome (Wollscheid lab)                                                | Help page             | [view](https://wlab.ethz.ch/surfaceome/)                                                                               | view-only                                                                                                             | 2018 resource                | 2026-04-18        | Resource landing page                                                              |
| D30 | CSPA         | A Mass Spectrometric-Derived Cell Surface Protein Atlas                                    | Paper (peer-reviewed) | [view](https://journals.plos.org/plosone/article?id=10.1371%2Fjournal.pone.0121314)                                    | [pdf](https://journals.plos.org/plosone/article/file?id=10.1371/journal.pone.0121314&type=printable)                  | 2015-04-20                   | 2026-04-18        | Publisher article                                                                  |
| D31 | CSPA         | A Mass Spectrometric-Derived Cell Surface Protein Atlas — ETH PDF                          | Paper (peer-reviewed) | [view](https://www.research-collection.ethz.ch/bitstreams/884fe485-66ed-4b7c-9ff5-954cd6ef1439/download)               | [pdf](https://www.research-collection.ethz.ch/bitstreams/884fe485-66ed-4b7c-9ff5-954cd6ef1439/download)               | 2015                         | 2026-04-18        | Open PDF mirror used for quoted methods text                                       |
| D32 | CSPA         | A Mass Spectrometric-Derived Cell Surface Protein Atlas (Wollscheid lab resource)          | Help page             | [view](https://wlab.ethz.ch/CSPA/)                                                                                     | view-only                                                                                                             | current resource             | 2026-04-18        | Resource landing page and downloads                                                |
| D33 | CSPA         | S2 File — validated surfaceome proteins                                                    | Supplementary PDF     | [view](https://wlab.ethz.ch/CSPA/data/S2_File.xlsx)                                                                    | [xlsx](https://wlab.ethz.ch/CSPA/data/S2_File.xlsx)                                                                   | 2015 supplement              | 2026-04-18        | Tables A and B                                                                     |
| D34 | CSPA         | S3 File — corrected topologies                                                             | Supplementary PDF     | [view](https://wlab.ethz.ch/CSPA/data/S3_File.pdf)                                                                     | [pdf](https://wlab.ethz.ch/CSPA/data/S3_File.pdf)                                                                     | 2015 supplement              | 2026-04-18        | Topology correction supplement                                                     |
| D35 | DeepTMHMM    | DeepTMHMM 1.0 — DTU service                                                                | Help page             | [view](https://services.healthtech.dtu.dk/services/DeepTMHMM-1.0/)                                                     | view-only                                                                                                             | service 1.0                  | 2026-04-18        | Includes abstract and usage/license                                                |
| D36 | DeepTMHMM    | DeepTMHMM — DTU BioLib                                                                     | Help page             | [view](https://dtu.biolib.com/DeepTMHMM/)                                                                              | view-only                                                                                                             | current                      | 2026-04-18        | Model landing page                                                                 |
| D37 | DeepTMHMM    | DeepTMHMM predicts alpha and beta transmembrane proteins using deep neural networks        | Preprint              | [view](https://www.biorxiv.org/content/10.1101/2022.04.08.487609.full)                                                 | view-only                                                                                                             | posted 2022-04-10            | 2026-04-18        | bioRxiv full text                                                                  |
| D38 | DeepTMHMM    | DeepTMHMM predicts alpha and beta transmembrane proteins using deep neural networks — PDF  | Preprint              | [view](https://www.biorxiv.org/content/10.1101/2022.04.08.487609v1.full.pdf)                                           | [pdf](https://www.biorxiv.org/content/10.1101/2022.04.08.487609v1.full.pdf)                                           | 2022-04-10                   | 2026-04-18        | Preprint PDF                                                                       |
| D39 | DeepTMHMM    | DeepTMHMM preprint source XML                                                              | Preprint              | [view](https://www.biorxiv.org/content/biorxiv/early/2022/04/10/2022.04.08.487609.source.xml)                          | [xml](https://www.biorxiv.org/content/biorxiv/early/2022/04/10/2022.04.08.487609.source.xml)                          | 2022-04-10                   | 2026-04-18        | Machine-readable full text                                                         |
| D40 | DeepTMHMM    | Supplementary Information — DeepTMHMM                                                      | Supplementary PDF     | [view](https://www.biorxiv.org/content/biorxiv/early/2022/04/10/2022.04.08.487609/DC1/embed/media-1.pdf?download=true) | [pdf](https://www.biorxiv.org/content/biorxiv/early/2022/04/10/2022.04.08.487609/DC1/embed/media-1.pdf?download=true) | 2022-04-10                   | 2026-04-18        | Supplement                                                                         |
| D41 | HPA          | Subcellular localization method — imaging                                                  | Help page             | [view](https://www.proteinatlas.org/humanproteome/subcellular/method/imaging)                                          | view-only                                                                                                             | current                      | 2026-04-18        | Current method page                                                                |
| D42 | HPA          | Subcellular location data                                                                  | Help page             | [view](https://www.proteinatlas.org/humanproteome/subcellular/data)                                                    | view-only                                                                                                             | version 25.0 / Ensembl 109   | 2026-04-18        | File columns and location→GO IDs                                                   |
| D43 | HPA          | Downloadable data                                                                          | Download-page note    | [view](https://www.proteinatlas.org/about/download)                                                                    | view-only                                                                                                             | version 25.0                 | 2026-04-18        | Download landing page                                                              |
| D44 | HPA          | subcellular_location.tsv.zip                                                               | Data-file header      | [view](https://www.proteinatlas.org/download/tsv/subcellular_location.tsv.zip)                                         | [zip](https://www.proteinatlas.org/download/tsv/subcellular_location.tsv.zip)                                         | version 25.0                 | 2026-04-18        | Exact file endpoint                                                                |
| D45 | HPA          | Licence & Citation                                                                         | License               | [view](https://www.proteinatlas.org/about/licence)                                                                     | view-only                                                                                                             | current                      | 2026-04-18        | CC BY-SA 4.0; lists primary publications                                           |
| D46 | HPA          | Release history                                                                            | Help page             | [view](https://www.proteinatlas.org/about/releases)                                                                    | view-only                                                                                                             | v25 released 2025-11-11      | 2026-04-18        | Used for last release date                                                         |
| D47 | HPA          | Assays and annotation (v19 archive)                                                        | Help page             | [view](https://v19.proteinatlas.org/about/assays%2Bannotation)                                                         | view-only                                                                                                             | version 19 archive           | 2026-04-18        | Historical wording of reliability-class definitions                                |
| D48 | COMPARTMENTS | COMPARTMENTS — Downloads                                                                   | Download-page note    | [view](https://compartments.jensenlab.org/Downloads)                                                                   | view-only                                                                                                             | current weekly-updated       | 2026-04-18        | Current downloads page; CC BY 4.0                                                  |
| D49 | COMPARTMENTS | COMPARTMENTS: unification and visualization of protein subcellular localization evidence   | Paper (peer-reviewed) | [view](https://academic.oup.com/database/article/doi/10.1093/database/bau012/2633793)                                  | view-only                                                                                                             | 2014                         | 2026-04-18        | Publisher article page                                                             |
| D50 | COMPARTMENTS | COMPARTMENTS — OUP PDF                                                                     | Paper (peer-reviewed) | [view](https://academic.oup.com/database/article-pdf/doi/10.1093/database/bau012/8244417/bau012.pdf)                   | [pdf](https://academic.oup.com/database/article-pdf/doi/10.1093/database/bau012/8244417/bau012.pdf)                   | 2014                         | 2026-04-18        | PDF used for methods quotes                                                        |
| D51 | COMPARTMENTS | human_compartment_integrated_full.tsv                                                      | Data-file header      | [view](https://download.jensenlab.org/human_compartment_integrated_full.tsv)                                           | [tsv](https://download.jensenlab.org/human_compartment_integrated_full.tsv)                                           | current weekly               | 2026-04-18        | Integrated human channel                                                           |
| D52 | COMPARTMENTS | human_compartment_knowledge_full.tsv                                                       | Data-file header      | [view](https://download.jensenlab.org/human_compartment_knowledge_full.tsv)                                            | [tsv](https://download.jensenlab.org/human_compartment_knowledge_full.tsv)                                            | current weekly               | 2026-04-18        | Knowledge channel                                                                  |
| D53 | COMPARTMENTS | human_compartment_experiments_full.tsv                                                     | Data-file header      | [view](https://download.jensenlab.org/human_compartment_experiments_full.tsv)                                          | [tsv](https://download.jensenlab.org/human_compartment_experiments_full.tsv)                                          | current weekly               | 2026-04-18        | Experiments channel                                                                |
| D54 | COMPARTMENTS | human_compartment_textmining_full.tsv                                                      | Data-file header      | [view](https://download.jensenlab.org/human_compartment_textmining_full.tsv)                                           | [tsv](https://download.jensenlab.org/human_compartment_textmining_full.tsv)                                           | current weekly               | 2026-04-18        | Text-mining channel                                                                |
| D55 | COMPARTMENTS | human_compartment_predictions_full.tsv                                                     | Data-file header      | [view](https://download.jensenlab.org/human_compartment_predictions_full.tsv)                                          | [tsv](https://download.jensenlab.org/human_compartment_predictions_full.tsv)                                          | current weekly               | 2026-04-18        | Predictions channel                                                                |
| D56 | COMPARTMENTS | human_compartment_benchmark.tsv                                                            | Data-file header      | [view](https://download.jensenlab.org/human_compartment_benchmark.tsv)                                                 | [tsv](https://download.jensenlab.org/human_compartment_benchmark.tsv)                                                 | original 2014 benchmark      | 2026-04-18        | Uses STRING v9.1 identifiers                                                       |
| D57 | External     | STRING v9.1: protein-protein interaction networks, with increased coverage and integration | Paper (peer-reviewed) | [view](https://academic.oup.com/nar/article/41/D1/D808/1057425)                                                        | [pdf](https://academic.oup.com/nar/article-pdf/41/D1/D808/3617210/gks1094.pdf)                                        | 2013 / v9.1                  | 2026-04-18        | External upstream only                                                             |

## Deliverable 2 — Cross-source dependency matrix

| Consumer ↓ / Producer → | UniProt      | GO           | SURFY | CSPA         | DeepTMHMM | HPA          | COMPARTMENTS | InterPro     | STRING        | SignalP | TMHMM | WoLF PSORT    | YLoc          | Pfam | Medline/PubMed | PMC full-text |
| ----------------------- | ------------ | ------------ | ----- | ------------ | --------- | ------------ | ------------ | ------------ | ------------- | ------- | ----- | ------------- | ------------- | ---- | -------------- | ------------- |
| UniProt                 | ∅            | ✔ direct [1] | ∅     | ∅            | ∅         | ∅            | ∅            | ∅            | ∅             | ∅       | ∅     | ∅             | ∅             | ∅    | ∅              | ∅             |
| GO                      | ✔ direct [2] | ∅            | ∅     | ∅            | ∅         | ∅            | ∅            | ✔ direct [3] | ∅             | ∅       | ∅     | ∅             | ∅             | ∅    | ∅              | ∅             |
| SURFY                   | ∅            | ∅            | ∅     | ✔ direct [4] | ∅         | ∅            | ∅            | ∅            | ∅             | ?       | ?     | ∅             | ∅             | ?    | ∅              | ∅             |
| CSPA                    | ∅            | ∅            | ∅     | ∅            | ∅         | ∅            | ∅            | ∅            | ∅             | ∅       | ∅     | ∅             | ∅             | ∅    | ∅              | ∅             |
| DeepTMHMM               | ∅            | ∅            | ∅     | ∅            | ∅         | ∅            | ∅            | ∅            | ∅             | ?       | ?     | ∅             | ∅             | ?    | ∅              | ∅             |
| HPA                     | ✔ direct [5] | ✔ direct [6] | ∅     | ∅            | ∅         | ∅            | ∅            | ∅            | ∅             | ∅       | ∅     | ∅             | ∅             | ∅    | ∅              | ∅             |
| COMPARTMENTS            | ✔ direct [7] | ✔ direct [8] | ∅     | ∅            | ∅         | ✔ direct [9] | ∅            | ∅            | ✔ direct [10] | ∅       | ∅     | ✔ direct [11] | ✔ direct [12] | ∅    | ✔ direct [13]  | ∅             |

1. **UniProt ← GO.** UniProt help says GO annotations are “displayed” in UniProtKB, and `subcell.txt` carries a `GO` mapping field. [D7, §Gene Ontology (GO), accessed 2026-04-18; D10, §header/record format, accessed 2026-04-18] ([uniprot.org][2])
2. **GO ← UniProt.** GOA’s electronic pipeline uses UniProtKB controlled vocabularies, including `Keyword2GO` and `Subcellular Location2GO`, to create IEA annotations. [D23, §Electronic Annotation Methods, accessed 2026-04-18; D24, §SubcellularLocation2GO, accessed 2026-04-18; D25, §Keyword2GO, accessed 2026-04-18] ([EMBL-EBI][3])
3. **GO ← InterPro.** The GOA `InterPro2GO` page says its mapping file is used to “assign annotations to UniProtKB proteins” at each GOA release. [D26, §InterPro2GO mapping, accessed 2026-04-18] ([EMBL-EBI][4])
4. **SURFY ← CSPA.** The SURFY paper says the training set used “high-confidence cell-surface proteins” from “the Cell Surface Protein Atlas (CSPA)” and “trained a random forest.” [D27, §Abstract/Methods, accessed 2026-04-18] ([PNAS][5])
5. **HPA ← UniProt.** HPA’s knowledge-based annotation step says it will “compare stainings” with `UniProtKB/Swiss-Prot`. [D41, §Knowledge-based annotation, accessed 2026-04-18] ([Human Protein Atlas][6])
6. **HPA ← GO.** The HPA subcellular file page includes a `GO id` column described as the “Gene Ontology Cellular Component term identifier.” [D42, §Subcellular location, accessed 2026-04-18] ([Human Protein Atlas][7])
7. **COMPARTMENTS ← UniProt.** The paper says it imported subcellular localization annotations from UniProtKB comment and cross-reference fields into the knowledge channel. [D50, §Knowledge channel, accessed 2026-04-18] ([ORBilu][8])
8. **COMPARTMENTS ← GO.** COMPARTMENTS maps evidence onto “Gene Ontology terms,” and the downloads page says evidence is propagated through `is_a` and `part_of` relationships. [D49, §Abstract, accessed 2026-04-18; D48, §Downloads, accessed 2026-04-18] ([Københavns Universitets Forskningsportal][9])
9. **COMPARTMENTS ← HPA.** The experiments channel “imported Human Protein Atlas data,” then manually mapped HPA locations to GO terms. [D50, §Experiments channel, accessed 2026-04-18] ([ORBilu][8])
10. **COMPARTMENTS ← STRING.** The text-mining channel used the “protein dictionary from STRING 9.1.” [D50, §Text mining of Medline abstracts, accessed 2026-04-18] ([ORBilu][8])
11. **COMPARTMENTS ← WoLF PSORT.** The predictions channel contains `WoLF PSORT`. [D50, §Predictions channel, accessed 2026-04-18] ([ORBilu][8])
12. **COMPARTMENTS ← YLoc.** The predictions channel contains `YLoc`. [D50, §Predictions channel, accessed 2026-04-18] ([ORBilu][8])
13. **COMPARTMENTS ← Medline/PubMed.** The paper’s text-mining section is explicitly “Text mining of Medline abstracts.” [D50, §Text mining of Medline abstracts, accessed 2026-04-18] ([ORBilu][8])

## Deliverable 3 — Source dependency graph

![Source dependency graph: seven primary sources (UniProt, Gene Ontology, CSPA, HPA, SURFY, COMPARTMENTS, DeepTMHMM) and their external upstream dependencies (InterPro, STRING 9.1, WoLF PSORT, YLoc, Medline), arranged as a layered left-to-right flow with UniProt ↔ Gene Ontology as a bidirectional hub and COMPARTMENTS as the main aggregation sink.](figures/2026-04-17-source-dependency-graph.svg)

*Figure. Direct ingestion relationships among the seven primary sources and their external upstreams, rendered as a layered flow diagram. Mirrors the edges in Deliverable 2. Downstream merge into `candidate_universe.tsv` is covered by the companion one-pager and omitted here to keep the figure focused on dependencies. Source file: [`figures/2026-04-17-source-dependency-graph.svg`](figures/2026-04-17-source-dependency-graph.svg) — editable as text.*

The graph mirrors the direct edges in Deliverable 2: UniProt and Gene Ontology form a mapping loop through GOA pipelines (`Keyword2GO`, `SubcellularLocation2GO`, `InterPro2GO`), CSPA feeds SURFY's positive training set, HPA consults UniProt for knowledge-based annotation and emits GO CC identifiers, and COMPARTMENTS is the main integration sink — consuming UniProt comments, GO term mapping with ontology propagation, HPA imaging data, STRING 9.1's protein dictionary, WoLF PSORT and YLoc predictions, and Medline abstracts. DeepTMHMM is standalone in the retrieved primary-source documentation. ([EMBL-EBI][3])

## Deliverable 1 — Per-source dossiers

## Cell Surface Protein Atlas (CSPA)

* Canonical URL: [CSPA resource](https://wlab.ethz.ch/CSPA/)
* Version / release used: 2015 atlas; Tables A and B from the validated-surfaceome supplement
* Primary paper (DOI): 10.1371/journal.pone.0121314
* License / redistribution terms: [unresolved] The PLOS paper is openly downloadable; I did not find a separate license statement for the ETH-hosted download bundle. ([PLOS][10])

### What the evidence is (verbatim)

> “Cell Surface Capture (CSC) technology” [D32, §landing page, accessed 2026-04-18] ([Wollscheid Lab][11])

> “41 human and 31 mouse cell types” [D32, §landing page, accessed 2026-04-18] ([Wollscheid Lab][11])

> “mass-spectrometry derived Cell Surface Protein Atlas” [D30, §Abstract, accessed 2026-04-18] ([PLOS][10])

### How each annotation is generated (verbatim)

> “tagging oxidized extracellular exposed glycans” [D31, §Introduction, accessed 2026-04-18] ([Research Collection][12])

> “two-step identification approach” [D31, §Results, accessed 2026-04-18] ([Research Collection][12])

### Confidence / evidence tier scheme (verbatim)

> “validated surfaceome proteins” [D30, §S2 File, accessed 2026-04-18] ([PLOS][10])

> “Corrected topologies” [D30, §S3 File, accessed 2026-04-18] ([PLOS][10])

No first-party star ladder or evidence-code hierarchy like GO/HPA/COMPARTMENTS was stated in the retrieved CSPA docs. The main dataset distinction is file-level: validated atlas tables versus corrected-topology supplement. ([PLOS][10])

### Upstream inputs this source ingests (verbatim where possible)

* **CSC glycoproteomics / MS**, experimental channel.

  > “Cell Surface Capture (CSC) technology” [D32, §landing page, accessed 2026-04-18] ([Wollscheid Lab][11])

* **PROTTER**, topology-figure channel.

  > “created with PROTTER” [D30, §S3 File, accessed 2026-04-18] ([PLOS][10])

### Known failure modes / caveats (verbatim where stated)

> “non-detection of a surfaceome protein by CSC-MS does not rule out its absence” [D31, §Discussion, accessed 2026-04-18] ([Research Collection][12])

### Update cadence / last release date

The resource appears static around the 2015 publication and supplement set; I did not find a later versioned release stream on the first-party page. ([Wollscheid Lab][13])

## COMPARTMENTS

* Canonical URL: [COMPARTMENTS downloads](https://compartments.jensenlab.org/Downloads)
* Version / release used: current human integrated + per-channel TSVs; benchmark file remains the original publication dataset
* Primary paper (DOI): 10.1093/database/bau012
* License / redistribution terms: CC BY 4.0. ([Compartments][14])

### What the evidence is (verbatim)

> “integrates all sources listed above as well as the results of automatic text mining” [D49, §Abstract, accessed 2026-04-18] ([Københavns Universitets Forskningsportal][9])

> “database annotations, automatic text mining of the biomedical literature, and sequence-based predictions” [D48, §entity-page description surfaced by search, accessed 2026-04-18] ([Compartments][15])

### How each annotation is generated (verbatim)

* **Knowledge channel**

  > “imported subcellular localization annotations” [D50, §Knowledge channel, accessed 2026-04-18] ([ORBilu][8])

* **Experiments channel**

  > “Human Protein Atlas data” [D50, §Experiments channel, accessed 2026-04-18] ([ORBilu][8])

* **Text-mining channel**

  > “protein dictionary from STRING 9.1” [D50, §Text mining of Medline abstracts, accessed 2026-04-18] ([ORBilu][8])

* **Predictions channel**

  > “WoLF PSORT” [D50, §Predictions channel, accessed 2026-04-18] ([ORBilu][8])
  > “YLoc” [D50, §Predictions channel, accessed 2026-04-18] ([ORBilu][8])

### Confidence / evidence tier scheme (verbatim)

> “five stars” [D50, §Knowledge channel, accessed 2026-04-18] ([ORBilu][8])

> “supportive”, “uncertain”, “non-supportive” [D50, §Experiments channel, accessed 2026-04-18] ([ORBilu][8])

> “four stars” [D50, §Text mining of Medline abstracts, accessed 2026-04-18] ([ORBilu][8])

> “three stars” [D50, §Predictions channel, accessed 2026-04-18] ([ORBilu][8])

### Upstream inputs this source ingests (verbatim where possible)

* **UniProtKB**, channel/field: knowledge channel, comments and database cross-references.

  > “comments and database cross-reference fields of UniProtKB” [D50, §Knowledge channel, accessed 2026-04-18] ([ORBilu][8])

* **GO**, channel/field: mapping target + ontology propagation.

  > “Gene Ontology terms” [D49, §Abstract, accessed 2026-04-18] ([Københavns Universitets Forskningsportal][9])
  > “is_a and part_of relationships” [D48, §Downloads, accessed 2026-04-18] ([Compartments][14])

* **HPA**, channel/field: experiments channel.

  > “Human Protein Atlas data” [D50, §Experiments channel, accessed 2026-04-18] ([ORBilu][8])

* **STRING 9.1**, channel/field: protein dictionary for text mining.

  > “protein dictionary from STRING 9.1” [D50, §Text mining of Medline abstracts, accessed 2026-04-18] ([ORBilu][8])

* **Medline/PubMed**, channel/field: text-mining corpus.

  > “Text mining of Medline abstracts” [D50, §Text mining of Medline abstracts, accessed 2026-04-18] ([ORBilu][8])

* **WoLF PSORT / YLoc**, channel/field: predictions channel.

  > “WoLF PSORT” [D50, §Predictions channel, accessed 2026-04-18] ([ORBilu][8])
  > “YLoc” [D50, §Predictions channel, accessed 2026-04-18] ([ORBilu][8])

* **MGI / SGD / FlyBase / WormBase**, channel/field: curated GO knowledge import for model organisms.
  [inferred] The paper explicitly says COMPARTMENTS imported cellular-component GO annotations from the corresponding model-organism databases for mouse, yeast, fly, and worm; those resources do not feed the human candidate universe directly, but they do define the multi-species knowledge-channel design. ([ORBilu][8])

### Known failure modes / caveats (verbatim where stated)

I did not find a first-party “failure modes” section. The closest operational caveat is versioning: the live channel files are current and weekly-updated, whereas the benchmark file is frozen to the publication-era identifiers. ([Compartments][14])

### Update cadence / last release date

> “updated on a weekly basis” [D48, §Downloads, accessed 2026-04-18] ([Compartments][14])

## DeepTMHMM

* Canonical URL: [DTU service](https://services.healthtech.dtu.dk/services/DeepTMHMM-1.0/)
* Version / release used: DeepTMHMM 1.0 service
* Primary paper (DOI): 10.1101/2022.04.08.487609
* License / redistribution terms: the DTU page says the web service is free for academic and commercial use, but commercial own-server deployment requires a license. ([DTU Health Tech][16])

### What the evidence is (verbatim)

> “protein language model-based algorithm” [D35, §Abstract, accessed 2026-04-18] ([DTU Health Tech][16])

> “alpha helical and beta barrels” [D35, §Abstract, accessed 2026-04-18] ([DTU Health Tech][16])

### How each annotation is generated (verbatim)

> “five types of proteins” [D39, §Training/testing description, accessed 2026-04-18] ([BioRxiv][17])

> “pre-trained language model (ESM-1b)” [D39, §Encoder, accessed 2026-04-18] ([BioRxiv][18])

> “conditional random field (CRF)” [D39, §Decoder, accessed 2026-04-18] ([BioRxiv][17])

### Confidence / evidence tier scheme (verbatim)

No first-party star/reliability tier scheme was retrieved. The source instead exposes output **class/topology labels**, e.g. `Alpha TM`, `SP+TM`, `Beta`, `Globular`, `SP+Globular`. [D39, §Output classes, accessed 2026-04-18] ([BioRxiv][17])

### Upstream inputs this source ingests (verbatim where possible)

* **ESM-1b**, channel/field: encoder representation.

  > “pre-trained language model (ESM-1b)” [D39, §Encoder, accessed 2026-04-18] ([BioRxiv][18])

* [unresolved] **SignalP / TMHMM / Pfam lineage.** I retrieved first-party evidence for ESM-1b plus the CRF architecture, but not a first-party sentence proving direct ingestion of SignalP, TMHMM, or Pfam into the released DeepTMHMM model. ([BioRxiv][18])

### Known failure modes / caveats (verbatim where stated)

I did not retrieve a first-party caveat section beyond the licensing/usage notes on the service page. [unresolved] A peer-reviewed journal version also did not surface in primary-source search results. ([DTU Health Tech][16])

### Update cadence / last release date

The accessible first-party materials are the current service pages plus the 2022 bioRxiv preprint/supplement. I did not find a later peer-reviewed release statement. ([DTU Health Tech][16])

## Gene Ontology (GO GAF, human)

* Canonical URL: [GO downloads](https://current.geneontology.org/products/pages/downloads.html)
* Version / release used: `goa_human.gaf.gz`, January 2026 archive release (`2026-01-23`)
* Primary paper (DOI): 10.1093/nar/gkaf1292
* License / redistribution terms: CC BY 4.0. ([Gene Ontology][19])

### What the evidence is (verbatim)

> “single association between a gene product and a GO term” [D17, §GAF 2.2 description, accessed 2026-04-18] ([Gene Ontology Resource][20])

> “with an evidence code” [D17, §GAF 2.2 description, accessed 2026-04-18] ([Gene Ontology Resource][20])

### How each annotation is generated (verbatim)

> “manually map GO terms” [D23, §Electronic Annotation Methods, accessed 2026-04-18] ([EMBL-EBI][3])

> “mapped to GO terms” [D24, §UniProtKB-Subcellular Location2GO, accessed 2026-04-18] ([EMBL-EBI][21])

> “assign annotations to UniProtKB proteins” [D26, §InterPro2GO mapping, accessed 2026-04-18] ([EMBL-EBI][4])

### Confidence / evidence tier scheme (verbatim)

> “Experimental” [D16, §Evidence categories, accessed 2026-04-18] ([Gene Ontology Resource][22])

> “Phylogenetic” [D16, §Evidence categories, accessed 2026-04-18] ([Gene Ontology Resource][22])

> “Computational Analysis” [D16, §Evidence categories, accessed 2026-04-18] ([Gene Ontology Resource][22])

> “Author Statement” [D16, §Evidence categories, accessed 2026-04-18] ([Gene Ontology Resource][22])

> “Curator Statement” [D16, §Evidence categories, accessed 2026-04-18] ([Gene Ontology Resource][22])

> “Automatically-assigned” [D16, §Evidence categories, accessed 2026-04-18] ([Gene Ontology Resource][22])

> “not manually reviewed” [D16, §IEA, accessed 2026-04-18] ([Gene Ontology Resource][22])

### Upstream inputs this source ingests (verbatim where possible)

* **UniProtKB controlled vocabularies**, channel/field: Keyword2GO and SubcellularLocation2GO.

  > “controlled vocabularies used by the UniProt Knowledgebase” [D23, §Electronic Annotation Methods, accessed 2026-04-18] ([EMBL-EBI][3])

* **UniProt subcellular locations**, channel/field: SubcellularLocation2GO.

  > “Subcellular Locations” [D23, §Electronic Annotation Methods, accessed 2026-04-18] ([EMBL-EBI][3])
  > “manually mapped to GO terms” [D24, §UniProtKB-Subcellular Location2GO, accessed 2026-04-18] ([EMBL-EBI][21])

* **UniProt keywords**, channel/field: Keyword2GO.

  > “UniProtKB keywords” [D23, §Electronic Annotation Methods, accessed 2026-04-18] ([EMBL-EBI][3])
  > “Keyword2GO” [D25, §page title/section, accessed 2026-04-18] ([EMBL-EBI][23])

* **InterPro**, channel/field: InterPro2GO.

  > “InterPro2GO” [D23, §Electronic Annotation Methods, accessed 2026-04-18] ([EMBL-EBI][3])
  > “assign annotations to UniProtKB proteins at each GOA release” [D26, §InterPro2GO mapping, accessed 2026-04-18] ([EMBL-EBI][4])

### Known failure modes / caveats (verbatim where stated)

> “Electronic (IEA) annotations are not manually reviewed” [D16, §IEA, accessed 2026-04-18] ([Gene Ontology Resource][22])

### Update cadence / last release date

The current GO download page is release-dated `2026-03-25`, while the archive confirms the January 2026 snapshot at `2026-01-23`. The archive is organized as monthly releases. ([Gene Ontology][19])

## Human Protein Atlas (HPA)

* Canonical URL: [Subcellular location data page](https://www.proteinatlas.org/humanproteome/subcellular/data)
* Version / release used: subcellular_location.tsv, version 25.0, Ensembl 109
* Primary paper (DOI): 10.1126/science.aal3321
* License / redistribution terms: CC BY-SA 4.0. ([Human Protein Atlas][24])

### What the evidence is (verbatim)

> “immunofluorescently stained cells” [D42, §Subcellular location, accessed 2026-04-18] ([Human Protein Atlas][7])

> “manually annotated” [D41, §Annotation, accessed 2026-04-18] ([Human Protein Atlas][6])

### How each annotation is generated (verbatim)

> “compare stainings” [D41, §Knowledge-based annotation, accessed 2026-04-18] ([Human Protein Atlas][6])

> “UniProtKB/Swiss-Prot” [D41, §Knowledge-based annotation, accessed 2026-04-18] ([Human Protein Atlas][6])

> “all antibodies targeting the same protein are taken in consideration” [D41, §Knowledge-based annotation, accessed 2026-04-18] ([Human Protein Atlas][6])

### Confidence / evidence tier scheme (verbatim)

Current v25-facing pages expose the class names:

> “Enhanced” [D42, §columns, accessed 2026-04-18] ([Human Protein Atlas][7])
> “Supported” [D42, §columns, accessed 2026-04-18] ([Human Protein Atlas][7])
> “Approved” [D42, §columns, accessed 2026-04-18] ([Human Protein Atlas][7])
> “Uncertain” [D42, §columns, accessed 2026-04-18] ([Human Protein Atlas][7])

The fuller prose definitions were easiest to retrieve from the archived v19 assays page:

> “enhanced validated” [D47, §Reliability score, accessed 2026-04-18] ([Human Protein Atlas][25])
> “reported in literature” [D47, §Reliability score, accessed 2026-04-18] ([Human Protein Atlas][25])
> “only one antibody” [D47, §Reliability score, accessed 2026-04-18] ([Human Protein Atlas][25])
> “contradicts experimental data” [D47, §Reliability score, accessed 2026-04-18] ([Human Protein Atlas][25])

### Upstream inputs this source ingests (verbatim where possible)

* **UniProtKB/Swiss-Prot**, channel/field: knowledge-based annotation review.

  > “compare stainings” … “with UniProtKB/Swiss-Prot” [D41, §Knowledge-based annotation, accessed 2026-04-18] ([Human Protein Atlas][6])

* **GO**, channel/field: `GO id` output column.

  > “Gene Ontology Cellular Component term identifier” [D42, §Subcellular location, accessed 2026-04-18] ([Human Protein Atlas][7])
  > [inferred] Direction is **HPA location → GO CC identifier**, not a GO-derived confidence assignment.

### Known failure modes / caveats (verbatim where stated)

> “Reliability score is set manually” [D41, §Reliability score, accessed 2026-04-18] ([Human Protein Atlas][6])

### Update cadence / last release date

Version 25 was released on **2025-11-11**. The subcellular data page explicitly states `version 25.0` and `Ensembl 109`. ([Human Protein Atlas][26])

## SURFY

* Canonical URL: [SURFY resource](https://wlab.ethz.ch/surfaceome/)
* Version / release used: 2018 in-silico surfaceome resource
* Primary paper (DOI): 10.1073/pnas.1808790115
* License / redistribution terms: [unresolved] The paper/resource are openly viewable; I did not retrieve a separate first-party site-file license statement. ([PNAS][27])

### What the evidence is (verbatim)

> “machine-learning approach” [D27, §Abstract, accessed 2026-04-18] ([PNAS][27])

> “public resource” [D29, §landing page, accessed 2026-04-18] ([Wollscheid Lab][28])

> “2,886 proteins” [D29, §landing page, accessed 2026-04-18] ([Wollscheid Lab][28])

### How each annotation is generated (verbatim)

> “high-confidence cell-surface proteins” [D27, §Methods/abstract snippet, accessed 2026-04-18] ([PNAS][5])

> “Cell Surface Protein Atlas (CSPA)” [D27, §Methods/abstract snippet, accessed 2026-04-18] ([PNAS][5])

> “trained a random forest” [D27, §Methods/abstract snippet, accessed 2026-04-18] ([PNAS][5])

### Confidence / evidence tier scheme (verbatim)

> “1%, 5%, and 15% FPRs” [D27, §Fig. 1 snippet, accessed 2026-04-18] ([PNAS][29])

### Upstream inputs this source ingests (verbatim where possible)

* **CSPA**, channel/field: positive training set.

  > “high-confidence cell-surface proteins” … “Cell Surface Protein Atlas (CSPA)” [D27, §Methods/abstract snippet, accessed 2026-04-18] ([PNAS][5])

* [unresolved] **Negative training-set provenance.** The article snippets indicate a defined nonsurface training set, but I did not recover a single first-party sentence with the full database provenance of every negative subset. ([PNAS][27])

### Known failure modes / caveats (verbatim where stated)

I did not retrieve a first-party caveat section. The resource presents a static prediction set and score cutoffs, but not an explicit failure-mode taxonomy on the landing page. ([Wollscheid Lab][28])

### Update cadence / last release date

The public resource and paper are from late 2018, and I did not find a later first-party versioned release. ([Wollscheid Lab][28])

## UniProt

* Canonical URL: [Human proteome page](https://www.uniprot.org/proteomes/UP000005640)
* Version / release used: Swiss-Prot reviewed human set, release 2026_01
* Primary paper (DOI): 10.1093/nar/gkae1010
* License / redistribution terms: CC BY 4.0. ([uniprot.org][30])

### What the evidence is (verbatim)

> “Controlled vocabulary of subcellular locations and membrane topologies and orientations” [D10, §header, accessed 2026-04-18] ([UniProt FTP][31])

### How each annotation is generated (verbatim)

> “SUBCELLULAR LOCATION” [D11, §CC line format, accessed 2026-04-18] ([UniProt FTP][32])

> “TRANSMEM” [D11, §Feature table, accessed 2026-04-18] ([UniProt FTP][32])

[inferred] Your release-pinned surface-candidate universe is consistent with filtering reviewed human entries on the controlled `SUBCELLULAR LOCATION` vocabulary plus topology-related flat-file features, rather than on a standalone “surfaceome” table. ([UniProt FTP][31])

### Confidence / evidence tier scheme (verbatim)

> “Evidence at protein level” [D11, §Protein existence, accessed 2026-04-18] ([UniProt FTP][32])
> “Evidence at transcript level” [D11, §Protein existence, accessed 2026-04-18] ([UniProt FTP][32])
> “Inferred from homology” [D11, §Protein existence, accessed 2026-04-18] ([UniProt FTP][32])
> “Predicted” [D11, §Protein existence, accessed 2026-04-18] ([UniProt FTP][32])
> “Uncertain” [D11, §Protein existence, accessed 2026-04-18] ([UniProt FTP][32])

### Upstream inputs this source ingests (verbatim where possible)

* **GO**, channel/field: GO annotations shown on entries and GO mappings in the subcellular vocabulary.

  > “GO annotations” [D7, §GO help, accessed 2026-04-18] ([uniprot.org][2])
  > “GO mapping” [D10, §record fields, accessed 2026-04-18] ([UniProt FTP][31])

* [unresolved] I did **not** recover a stronger UniProt-side first-party sentence saying, in so many words, that UniProt “imports GO terms from GO/GOA”; the strongest explicit directionality I found is on the GOA side, which says GOA “provides GO annotation to the UniProt Knowledgebase.” ([EMBL-EBI][33])

### Known failure modes / caveats (verbatim where stated)

> “updated roughly every eight weeks” [D4, §Downloads, accessed 2026-04-18] ([uniprot.org][34])

That cadence is a practical reproducibility caveat: surface-candidate queries must be release-pinned. Release `2026_01` is explicitly dated in the release notes and in the FTP docs directory. ([uniprot.org][35])

### Update cadence / last release date

Release `2026_01` was issued in late January 2026, and UniProt states an approximately eight-week release cadence. ([uniprot.org][35])

## Unresolved claims appendix

* **[unresolved] UniProt exact reviewed-human FASTA endpoint.** I found the first-party human proteome page and API-query help examples, but the current proteome page returned a JS fallback in static fetch, so I could not extract the exact button target for the current reviewed-human FASTA download from first-party HTML alone. ([uniprot.org][36])
* **[unresolved] UniProt-side wording for GO ingestion.** I found first-party evidence that UniProt displays GO annotations and that `subcell.txt` carries GO mappings, plus GOA’s explicit statement that it provides GO annotations to UniProtKB; I did not find a stronger UniProt-side ingest sentence. ([uniprot.org][2])
* **[inferred] GO archive direct January 2026 human GAF URL.** The `release.geneontology.org/2026-01-23/annotations/goa_human.gaf.gz` path follows the official archive structure and release-root page, but I did not retrieve that exact file directly through indexed search results. ([Gene Ontology Data Archive][37])
* **[inferred] HPA v25 reliability-class prose.** Current v25 pages clearly expose the class names and method overview, but the full prose definitions I quoted were easiest to retrieve from the archived v19 assays page; I treated those as historical wording for the same scheme. ([Human Protein Atlas][38])
* **[unresolved] SURFY negative training-set provenance in one first-party sentence.** I recovered direct first-party evidence for the positive CSPA training set and the random-forest model, but not a single equally explicit sentence enumerating every negative-source component. ([PNAS][5])
* **[unresolved] SURFY supplementary methods PDF direct retrieval.** I retrieved the article page, publisher PDF, PMC mirror, and ETH resource page, but not a directly fetchable first-party supplement URL with stable open access. ([PNAS][27])
* **[unresolved] DeepTMHMM peer-reviewed publication.** I found the DTU service page, BioLib page, bioRxiv full text/PDF, and supplement, but no primary-source journal article. ([DTU Health Tech][16])
* **[unresolved] DeepTMHMM dependence on SignalP/TMHMM/Pfam.** The retrieved first-party docs clearly mention ESM-1b plus a CRF, but not an explicit ingestion statement for those other tools/databases. ([BioRxiv][18])
* **[unresolved] Separate site-file licenses for SURFY/CSPA downloads.** The papers/resources are openly accessible, but I did not surface clear standalone license statements for the ETH-hosted site download bundles. ([Wollscheid Lab][13])
* **[unresolved] COMPARTMENTS `/Help` page.** Search surfaced the current Downloads page, entity pages, and the 2014 paper/PDF, but not a retrievable help page at the user-provided path with richer channel prose. ([Compartments][14])

[1]: https://orbilu.uni.lu/bitstream/10993/27111/1/Database-2014-Binder-database_bau012.pdf "https://orbilu.uni.lu/bitstream/10993/27111/1/Database-2014-Binder-database_bau012.pdf"
[2]: https://www.uniprot.org/help/gene_ontology "https://www.uniprot.org/help/gene_ontology"
[3]: https://www.ebi.ac.uk/GOA/ElectronicAnnotationMethods "https://www.ebi.ac.uk/GOA/ElectronicAnnotationMethods"
[4]: https://www.ebi.ac.uk/GOA/InterPro2GO "https://www.ebi.ac.uk/GOA/InterPro2GO"
[5]: https://www.pnas.org/doi/abs/10.1073/pnas.1808790115?url_ver=Z39.88-2003 "https://www.pnas.org/doi/abs/10.1073/pnas.1808790115?url_ver=Z39.88-2003"
[6]: https://www.proteinatlas.org/humanproteome/subcellular/method/imaging?utm_source=chatgpt.com "The human subcellular proteome - Methods summary - The Human Protein Atlas"
[7]: https://www.proteinatlas.org/humanproteome/subcellular/data "https://www.proteinatlas.org/humanproteome/subcellular/data"
[8]: https://orbilu.uni.lu/bitstream/10993/27111/1/Database-2014-Binder-database_bau012.pdf?utm_source=chatgpt.com "OP-DABA140012 1..9"
[9]: https://researchprofiles.ku.dk/en/publications/compartments-unification-and-visualization-of-protein-subcellular/ "https://researchprofiles.ku.dk/en/publications/compartments-unification-and-visualization-of-protein-subcellular/"
[10]: https://journals.plos.org/plosone/article?id=10.1371%2Fjournal.pone.0121314&utm_source=chatgpt.com "A Mass Spectrometric-Derived Cell Surface Protein Atlas"
[11]: https://wlab.ethz.ch/CSPA/?utm_source=chatgpt.com "Cell Surface Protein Atlas"
[12]: https://www.research-collection.ethz.ch/bitstreams/884fe485-66ed-4b7c-9ff5-954cd6ef1439/download?utm_source=chatgpt.com "A Mass Spectrometric-Derived Cell Surface Protein Atlas"
[13]: https://wlab.ethz.ch/CSPA/ "https://wlab.ethz.ch/CSPA/"
[14]: https://compartments.jensenlab.org/Downloads "https://compartments.jensenlab.org/Downloads"
[15]: https://compartments.jensenlab.org/Entity?experiments=10&figures=subcell_cell_%25&id1=ENSP00000357283&knowledge=10&predictions=10&textmining=10&type1=9606&type2=-22 "https://compartments.jensenlab.org/Entity?experiments=10&figures=subcell_cell_%25&id1=ENSP00000357283&knowledge=10&predictions=10&textmining=10&type1=9606&type2=-22"
[16]: https://services.healthtech.dtu.dk/services/DeepTMHMM-1.0/ "https://services.healthtech.dtu.dk/services/DeepTMHMM-1.0/"
[17]: https://www.biorxiv.org/content/biorxiv/early/2022/04/10/2022.04.08.487609.source.xml "https://www.biorxiv.org/content/biorxiv/early/2022/04/10/2022.04.08.487609.source.xml"
[18]: https://www.biorxiv.org/content/10.1101/2022.04.08.487609.full "https://www.biorxiv.org/content/10.1101/2022.04.08.487609.full"
[19]: https://current.geneontology.org/products/pages/downloads.html "https://current.geneontology.org/products/pages/downloads.html"
[20]: https://geneontology.org/docs/go-annotation-file-gaf-format-2.2/ "https://geneontology.org/docs/go-annotation-file-gaf-format-2.2/"
[21]: https://www.ebi.ac.uk/GOA/SubcellularLocation2GO "https://www.ebi.ac.uk/GOA/SubcellularLocation2GO"
[22]: https://geneontology.org/docs/guide-go-evidence-codes/ "https://geneontology.org/docs/guide-go-evidence-codes/"
[23]: https://www.ebi.ac.uk/GOA/Keyword2GO "https://www.ebi.ac.uk/GOA/Keyword2GO"
[24]: https://www.proteinatlas.org/about/licence "https://www.proteinatlas.org/about/licence"
[25]: https://v19.proteinatlas.org/about/assays%2Bannotation "https://v19.proteinatlas.org/about/assays%2Bannotation"
[26]: https://www.proteinatlas.org/about/releases "https://www.proteinatlas.org/about/releases"
[27]: https://www.pnas.org/doi/10.1073/pnas.1808790115 "https://www.pnas.org/doi/10.1073/pnas.1808790115"
[28]: https://wlab.ethz.ch/surfaceome/ "https://wlab.ethz.ch/surfaceome/"
[29]: https://www.pnas.org/doi/pdf/10.1073/pnas.1808790115 "https://www.pnas.org/doi/pdf/10.1073/pnas.1808790115"
[30]: https://www.uniprot.org/help/license "https://www.uniprot.org/help/license"
[31]: https://ftp.uniprot.org/pub/databases/uniprot/current_release/knowledgebase/complete/docs/subcell.txt "https://ftp.uniprot.org/pub/databases/uniprot/current_release/knowledgebase/complete/docs/subcell.txt"
[32]: https://ftp.uniprot.org/pub/databases/uniprot/current_release/knowledgebase/complete/docs/userman.htm "https://ftp.uniprot.org/pub/databases/uniprot/current_release/knowledgebase/complete/docs/userman.htm"
[33]: https://www.ebi.ac.uk/GOA/RGI "https://www.ebi.ac.uk/GOA/RGI"
[34]: https://www.uniprot.org/help/downloads "https://www.uniprot.org/help/downloads"
[35]: https://www.uniprot.org/release-notes/2026-01-28-release "https://www.uniprot.org/release-notes/2026-01-28-release"
[36]: https://www.uniprot.org/proteomes/UP000005640 "https://www.uniprot.org/proteomes/UP000005640"
[37]: https://release.geneontology.org/2026-01-23/ "https://release.geneontology.org/2026-01-23/"
[38]: https://www.proteinatlas.org/humanproteome/subcellular/method/imaging "https://www.proteinatlas.org/humanproteome/subcellular/method/imaging"
