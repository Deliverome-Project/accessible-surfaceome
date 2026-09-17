# Binder/site coverage across all 5,130 deep-dive genes

**631/5,130 deep-dive genes (12.3%) have a qualifying exact binder with mapped experimental contact residues or a curated exact epitope.** Including experimentally mapped epitope-containing/partial regions increases coverage to **726/5,130 (14.2%)**. These unions do not count unsupported chemical contacts, antibody-only structures, unnamed serum reactivity or literature keyword hits.

This is the full 5,130-record deep-dive snapshot used in the first pilot, **not the 1,059 classical-receptor subset and not the 5,574-gene candidate universe**. It contains 4,081 genes in the previous audit and **1,049 additional genes**, which were searched in this extension. The newly included genes contribute **48** members of the conservative mapped-site union, or **75** if broader epitope regions qualify.

## Source breakdown — denominator 5,130 throughout

| Source/evidence | Genes | Coverage | Genes with an entirely extracellular mapped site |
|---|---:|---:|---:|
| SAbDab antibody complexes, computed UniProt-mapped contacts | **411** | **8.0%** | 249 |
| IEDB named antibody + positive eligible assay + curated exact, sequence-validated epitope | **183** | **3.6%** | 125 |
| PDBe small-molecule contacts + independent IUPHAR ligand–target match | **209** | **4.1%** | 34 |
| IUPHAR endogenous protein ligand + PDBe mapped interface | **120** | **2.3%** | 54 |
| BioGRID literature-curated minibinders, coordinate-verified | **1** | **0.02%** | 0 |
| **Conservative deduplicated union** | **631** | **12.3%** | **302 (5.9%)** |
| IEDB broader mapped epitope-containing/partial regions, overlapping above | 201 | 3.9% | 84 |
| **Union including broader regions** | **726** | **14.2%** | **324 (6.3%)** |

Source counts overlap; do not add them. The conservative union for the previously audited 4,081 deep-dive genes is 583, with 48 additional covered genes among the newly searched 1,049. The newly covered sites did not meet the entirely-extracellular annotation criterion; that union remains 302.

Extracellular annotation means every mapped contact lies in an extracellular UniProt topological region. It is not proof of native live-cell binding or epitope accessibility. Cytoplasmic, transmembrane, lumenal, mixed and unknown sites remain available in the observation export. The BioGRID example is TLR3, whose relevant UniProt region is lumenal; its two experimentally solved minibinders are counted in total mapped-site coverage, not the entirely-extracellular subset.

## What was searched

- Built the cohort directly from all 5,130 public-D1 annotation records in the pilot snapshot. Joined their HGNC identifiers to the canonical identifier cache and checked annotation/canonical UniProt agreement. No gene-symbol lookup or candidate-universe filtering was used to select membership.
- The 5,130 gene records map to **5,115 distinct UniProt accessions**. Of these, **1,034 protein accessions** were absent from the previous structural audit and were newly queried. All 5,115 now have a PDBe ligand-site response: **1,772 with records, 3,343 without records (404), no transport failures**. Missing UniProt sequence/topology records were also retrieved.
- Rejoined the entire SAbDab export to the new cohort through SIFTS and extended contact extraction to previously unsearched proteins. There are **451 candidate target complexes**, of which **411** yielded qualifying mapped contacts. The other 40 remain unresolved under the representative-structure method, not confirmed binder-negative genes.
- Refiltered the complete **115,645 human-parent-antigen IEDB B-cell assays** against the full deep-dive cohort. Reusing the complete human assay download avoids incorrectly restricting the new search to proteins in the old candidate set. All identity, assay, sequence and epitope filters are unchanged.
- Rebuilt IUPHAR ligand–target observations for the full deep-dive set, checked the corresponding structural interfaces and retrieved identifiers/cross-links for **1,520 newly encountered chemical components**.
- Rejoined BioGRID's synthetic-protein data to the new cohort and repeated its linked-paper retrieval. There are **70 linked papers**, all with metadata, **35 with accessible full-text XML**, and target-matched PDB review leads for **25 genes across 10 papers**. Literature leads are not counted as exact-binder structural confirmations. The two TLR3 examples remain a selected positive demonstration, not a complete BioGRID epitope census.

## Identifier ambiguity stays visible

**24 gene records share nine canonical protein accessions.** They remain in the 5,130 denominator, with `identifier_status=shared_uniprot_ambiguous`, but receive no gene-specific coverage credit. The accession-level search was still performed. This is conservative: a protein-level observation cannot be uniquely attributed to one of these HGNC records without resolving the shared mapping. Their zeros mean unresolved gene attribution, not absence of binders. The shared groups are listed in the cohort manifest and per-gene table.

The other 5,106 records have unique canonical protein identifiers. Tests prevent unmarked duplicate accessions from silently overwriting a gene in a lookup table.

## Broader discovery sets

| Evidence not sufficient by itself for the conservative union | Genes / 5,130 |
|---|---:|
| Filtered non-polymer chemical contacts in experimental structures | 976 (19.0%) |
| Structural chemical contacts with a ChEMBL identity cross-link | 830 (16.2%) |
| Any IEDB B-cell assay | 1,699 (33.1%) |
| Named antibody with a positive eligible IEDB assay, before residue mapping | 347 (6.8%) |

ChEMBL links identify chemicals, not an independently confirmed affinity measurement or extracellular epitope. ChEMBL/BindingDB incremental affinity coverage remains unmeasured. These additional chemical contacts can guide a subsequent affinity-enrichment pass, but should not be advertised as 976 validated extracellular binders.

## Outputs and reproduction

- [All 5,130 cohort members](../../data/analysis/deep_dive_binding_sites/cohort.tsv)
- [Per-gene coverage and identifier status](../../data/analysis/deep_dive_binding_sites/gene_coverage.tsv)
- [Source coverage, including newly searched vs previously audited genes](../../data/analysis/deep_dive_binding_sites/coverage_summary.tsv)
- [Binder/site observations, compressed TSV](../../data/analysis/deep_dive_binding_sites/observations.tsv.gz)
- [Retrieval/mapping status](../../data/analysis/deep_dive_binding_sites/retrieval_status.tsv)
- [BioGRID literature reachability](../../data/analysis/deep_dive_binding_sites/literature_retrieval.tsv) and [structural review leads](../../data/analysis/deep_dive_binding_sites/biogrid_structure_leads.tsv)
- [Cohort provenance and shared identifiers](../../data/analysis/deep_dive_binding_sites/cohort_manifest.json), [source hashes](../../data/analysis/deep_dive_binding_sites/manifest.json)

The [preceding methods report](2026-09-17-binding-site-coverage-audit.md) describes contact geometry, SIFTS mapping, antibody representative selection, chemical exclusions, exact-identity joins, IEDB filtering and confidence limits. Its candidate-universe counts are historical and should not be substituted for this report's deep-dive denominator. The current audit uses the frozen 5,130-record snapshot, not a claim that the live site's annotation count will remain 5,130.

With the first pilot's raw source files and the shared audit cache present:

```sh
uv run python scripts/audit/build_deep_dive_binder_cohort.py
uv run python scripts/audit/fetch_binding_sites.py pdbe --deep-dives
uv run python scripts/audit/fetch_binding_sites.py compounds --deep-dives
uv run python scripts/audit/fetch_binding_sites.py uniprot --deep-dives
uv run python scripts/audit/fetch_binding_sites.py natural --deep-dives
uv run python scripts/audit/audit_antibody_contacts.py --deep-dives
uv run python scripts/audit/probe_binder_literature.py --deep-dives
uv run python scripts/audit/audit_biogrid_structure_leads.py --deep-dives
uv run python scripts/audit/summarize_binding_sites.py --deep-dives
```

For an empty shared audit cache, first run the bulk and IEDB retrieval steps documented in the preceding report. Batch cache names now include hashes of queried identifiers, so adding a cohort cannot accidentally reuse an unrelated metadata page.

Validation: 14 focused tests pass, including new shared-identifier regression tests. Repository-wide Ruff and scoped type checks pass. The full repository check remains blocked by the existing missing `pydssp` dependency; no full-suite pass is claimed. No live D1, viewer, prompts, paid model calls or deployment were changed.
