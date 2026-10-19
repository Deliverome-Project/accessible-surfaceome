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

## Resource comparison and the LLM natural-ligand denominator

Read-only public-D1 refresh on 2026-09-17: among the frozen 5,130 HGNC records,
3,157 have explicit `filters.has_known_ligand=true`, 1,973 have false, and none
are missing. Every true record has a nonempty rationale. This is an LLM label,
not independent validation of an endogenous ligand. No schema default was
substituted for missing values. All joins use HGNC IDs or unambiguous canonical
UniProt accessions; the same 24 shared-accession gene records remain uncredited.

| Resource / evidence counted | All 5,130 | LLM ligand=yes, 3,157 |
|---|---:|---:|
| SAbDab: antibody complexes with mapped contacts | 411 (8.01%) | 371 (11.75%) |
| IEDB: exact mapped epitopes | 183 (3.57%) | 167 (5.29%) |
| IEDB: broader epitope regions | 201 (3.92%) | 168 (5.32%) |
| PDBe + IUPHAR: chemical binder/site pairs | 209 (4.07%) | 192 (6.08%) |
| PDBe + IUPHAR: endogenous protein ligand interfaces | 120 (2.34%) | 120 (3.80%) |
| BioGRID-linked literature: mapped minibinders, limited extraction | 1 (0.02%) | 1 (0.03%) |
| **Deduplicated experimental mapped-site union** | **631 (12.30%)** | **575 (18.21%)** |
| Union allowing broader epitope regions | 726 (14.15%) | 646 (20.46%) |
| Mapped-site union with all contact residues extracellular | 302 (5.89%) | 287 (9.09%) |
| **SURFACE-Bind: at least one predicted site** | **1,609 (31.36%)** | **1,249 (39.56%)** |
| SURFACE-Bind: at least one predicted design seed | 1,575 (30.70%) | 1,222 (38.71%) |
| PDBe: chemical contacts before pharmacology confirmation | 976 (19.03%) | 820 (25.97%) |
| PDBe chemical-contact target with ChEMBL compound cross-link | 830 (16.18%) | 711 (22.52%) |

Rows overlap and must not be summed. The ligand=yes denominator restricts
which genes are counted; its numerators still include *any* qualifying binder,
not exclusively the endogenous ligand. The 120 endogenous-protein-ligand row
is a narrower analysis and does not include all classes of natural ligands.

SURFACE-Bind is already integrated into this repository. Its mirrored release
is `2024-08-09` (2,708 protein entries), not a fresh upstream release audit.
2,620 cohort genes are listed, but only 1,609 have a positive site count; mere
membership would overstate coverage. The public model exposes site anchors,
patch properties and design-seed counts, not experimentally validated binder
identities with complete epitopes. These are predicted design opportunities,
so they are excluded from the experimental union. See the
[official methodology](https://surface-bind.inria.fr/about.html).
If predicted and experimental opportunities are intentionally combined, their
deduplicated union is 1,929/5,130 (37.60%), or 1,530/3,157 (48.46%); this must
never be described as experimental binder coverage.

### Could additional sources yield more?

Yes. The experimental union is a conservative measured lower bound, not a
claim of exhaustive coverage or the largest database available. The audit
already finds chemical contacts for 976 genes, substantially more than the
209 passing the current IUPHAR pair check. Some are cofactors, detergents or
other incidental contacts, so all 976 cannot be promoted to useful binders.

The next priority is [BioLiP2](https://pmc.ncbi.nlm.nih.gov/articles/PMC10767969/),
which supplies biologically relevant ligand classifications, binding residues,
and affinity annotations for PDB-derived interactions. It could help validate
more of those existing chemical contacts and add ligand classes excluded from
the current chemical/protein rules. Its incremental cohort coverage has **not**
yet been measured. More structure databases do not automatically mean more
unique targets because they draw on overlapping PDB structures.

ChEMBL is also worth adding as *binding-assay corroboration* for exact
target–compound pairs that already have structural sites. The 830-target row
is only compound identity cross-link coverage, not ChEMBL affinity coverage.
A genuine ChEMBL audit must retrieve assays, check target attribution and
binding endpoints, and match the exact compound before claiming an uplift.
ChEMBL alone does not satisfy a residue-level epitope requirement.

Further gains can come from completing antibody-complex processing beyond
three attempted representatives per target, resolving IEDB mapping failures,
and extracting published minibinder coordinates and epitope experiments.
The one-gene BioGRID literature result is a limited validated extraction, not
the coverage ceiling of that literature. Confidence must remain evidence-type
specific: coordinate contacts, experimentally mapped epitope regions,
pharmacological corroboration, and predicted patches are different claims.

Reproduce with `scripts/audit/compare_binder_resources.py --fetch` (read-only);
omit `--fetch` to reuse the cached snapshots. Per-gene flags and subset totals
are in `resource_comparison_genes.tsv` and `resource_comparison.tsv`, with input
hashes, snapshot dates and query text in `resource_comparison_manifest.json`.


Follow-up completed: [BioLiP and GPCRdb audit](2026-09-17-biolip-gpcrdb-audit.md) adds 504 genes under a curated biological ligand-site criterion, bringing the expanded union to 1,135/5,130 (22.12%). See that report for the evidence-tier differences and subset results.
