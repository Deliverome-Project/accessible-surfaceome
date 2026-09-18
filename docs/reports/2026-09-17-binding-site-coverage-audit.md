# Exact binders with mapped experimental sites — coverage audit

The conservative set covers **650/5,574 candidate genes (11.7%)**, including **211/1,059 genes in the classical-receptor triage category (19.9%)**. Requiring every mapped contact to lie in a UniProt-annotated extracellular region gives **302 candidates**, including **198 classical receptors (18.7%)**. These are gene-level unions, not numbers of unique binders.

If experimentally mapped epitope-containing regions are also acceptable, coverage rises to **747 candidates / 228 classical receptors (21.5%)**; the entirely extracellular subset is **324 candidates / 212 classical receptors (20.0%)**. Region evidence is kept separate from exact epitopes and structural contact residues.

**Recommendation:** prioritize **SAbDab + experimental PDB structures**, then **IEDB** for curated epitope detail, and **PDBe chemical contacts joined to curated pharmacology** for small molecules. Add ChEMBL as an identity/affinity enrichment of structurally supported pairs, rather than counting its activity catalogue as epitope coverage. No production viewer, API, D1, or model-generated annotations were changed.

## Measured source coverage

| Source and qualifying evidence | All candidates, n=5,574 | Classical-receptor category, n=1,059 | Classical receptors with entirely extracellular mapped residues |
|---|---:|---:|---:|
| SAbDab antibody complexes with computed, UniProt-mapped contacts | **413** | **177 (16.7%)** | **175** |
| IEDB named antibody + positive binding/structural assay + curated exact epitope, sequence-validated | **176** | **100 (9.4%)** | **100** |
| PDBe small-molecule contacts + matching IUPHAR ligand–target pair | **228** | **36 (3.4%)** | **12** |
| IUPHAR endogenous protein ligand + matching PDBe structural interface | **120** | **39 (3.7%)** | **38** |
| BioGRID literature-curated minibinders, independently computed contacts | **1** | **0** | **0** |
| **Union of the above** | **650** | **211 (19.9%)** | **198** |
| IEDB broader mapped epitope regions, including partial epitopes (overlaps above) | **204** | **68 (6.4%)** | **62** |
| **Union including broader regions** | **747** | **228 (21.5%)** | **212** |

The BioGRID positive example is **TLR3**, with two minibinders. TLR3 is not assigned to the existing classical-receptor or surface-positive triage subsets, and its mapped region is annotated lumenal rather than extracellular. It is included in the all-candidate denominator. The classical-receptor subset is **not a complete receptor ontology**; many GPCRs occur in other triage categories. The surface-positive subset, n=2,424, has **499 mapped-site genes (20.6%)**, of which **285 have an entirely extracellular site**. All three denominators are exported.

Sources overlap strongly. Adding sources in the order SAbDab → IEDB exact epitopes → supported small molecules → natural protein ligands adds **413 → 9 → 164 → 64** previously uncovered candidate genes, or **177 → 3 → 17 → 14** classical receptors. IEDB's main value is additional curated epitope/assay detail on already structurally covered targets; broader regions add another 17 classical receptors to the conservative union.

## Broader discovery sets, excluded from the conservative union

| Discovery set | Candidate genes | Classical receptors | Interpretation |
|---|---:|---:|---|
| SAbDab antigen-chain mappings | 464 | 183 | 51 candidate genes, including 6 classical receptors, did not yield mapped contacts in up to three representative structures. Unknown, not evidence of no binders. |
| Filtered PDBe non-polymer chemical contacts | 1,168 | 189 | Includes potential cofactors, lipids, detergents and nonspecific/crystal contacts. A short exclusion list cannot establish specificity. |
| The same structural chemical set with ChEMBL identity cross-links | 974 | 153 | Exact chemical identity enrichment, **not a ChEMBL binding-affinity audit**. |
| Any IEDB B-cell assay | 1,945 | 522 | Includes unnamed antibodies, serum, negative assays and other nonqualifying evidence. |
| IEDB named antibody with positive eligible assay | 348 | 147 | Some lack a canonical sequence-resolved epitope. |

PDBe exposes 115 classical receptors with at least one filtered chemical contact site wholly within an extracellular annotation; only 12 also passed the independent IUPHAR pair match. The difference is a review/enrichment opportunity, not proof that the remaining compounds are non-binders. Intracellular and transmembrane pockets are retained in the observation export but do not count as entirely extracellular sites.

ChEMBL's incremental assay-supported coverage and BindingDB's incremental coverage remain **unmeasured**. This audit establishes which structurally observed chemicals can be linked to ChEMBL: 974 candidate genes / 153 classical receptors. No affinity, specificity or epitope confidence is inferred from the presence of that link. The PDBe ligand-site response's `chemblId` field was empty throughout this retrieval; chemical-component `cross_links` supplied the actual mappings.

## Experimental evidence and confidence

- **Antibodies:** the current SAbDab export contains 22,264 antibody instances. Exact antigen-chain joins through the SIFTS bulk mapping produce 5,632 candidate-matched chain pairs across 464 genes. Antibody identity is retained as SAbDab ID, instance ID, chain IDs and variable-sequence hash. Up to three distinct PDB entries per target are attempted, preferring X-ray structures and lower reported resolution. The audit measures coverage using one successful representative per gene; it does not catalogue every antibody or maximize extracellular coverage over all structures.
- **Coordinate-derived contacts:** target residues with a non-hydrogen polymer atom within 5 Å of an antibody/binder-chain non-hydrogen polymer atom in the first deposited model. Zero-occupancy atoms are excluded. SIFTS residue-level mappings preserve author insertion codes and require the exact target UniProt accession. These are computed contacts in experimental structures, not mutagenesis-defined energetic hotspots. Protein fragments, engineered constructs, crystal packing and biological relevance still need context before receptor-page presentation. Target glycans are not included in these protein-residue contacts.
- **Small molecules:** PDBe observed ligand-contact residues are preserved separately per PDB entry. Common solvents, salts and glycans are excluded; components must be NON-POLYMER, explicitly not marked solvent, and have at least six reported atoms. The conservative subset additionally requires an exact ligand–target IUPHAR match using a ChEMBL cross-link or complete InChIKey. No chemical-name or target-symbol matching is used. Whole InChIKey matching can miss different protonation/salt/tautomer representations.
- **IEDB:** all **115,645 human-parent-antigen B-cell assay records** were retrieved in 232 ordered pages and checked for duplicate assay IDs. Records are joined to cohort UniProt IDs at assay level, avoiding antigen-level antibody/epitope cross-products. Qualifying records require a named antibody, a positive outcome, a binding/kinetic or structural assay, and the tested antigen being the epitope, source antigen or its fragment. Mimotopes and taxonomic/structural surrogate antigens are excluded. Linear peptides must match uniquely to the canonical sequence; discontinuous residue lists must match both position and amino-acid identity. IEDB's Exact Epitope label is separated from partial/epitope-containing regions. Its curated assignment is not an independent rereview of every primary paper.
- **Natural protein ligands:** curated endogenous IUPHAR pairs with direct ligand UniProt identifiers are intersected with PDBe experimental interface partners. Generic protein–protein interactions, unidentifiable complexes and symbol-based matches do not qualify. This does not cover every natural ligand, processed peptide or multicomponent ligand.
- **Topology:** all 5,574 cohort UniProt entries were retrieved. A site is called entirely extracellular only when every mapped residue has an extracellular topological-domain annotation. Mixed, unknown, lumenal, cytoplasmic and transmembrane sites remain separate. Topology evidence can itself be inferred. Extracellular annotation is **not evidence of native live-cell accessibility**, binding under physiological conditions, or lack of epitope masking.

Keep these evidence types explicit on a receptor page; do not collapse structural resolution, curated epitope precision, affinity and cellular accessibility into one confidence score.

## Designed-binder literature audit

The earlier BioGRID set covers 84 candidate genes and points to 76 papers; 38 full-text XML bodies were retrieved. Searching data-availability sections and explicit PDB links, followed by a target UniProt/SIFTS check, found **target-matched structure leads for 26 genes across 13 papers**. These are not exact-binder confirmations: cited structures may be apo targets, other binders or background references. The export preserves that distinction. Missing full text or missing detectable PDB links is unknown coverage. Supplements were not audited.

The two previously curated TLR3 minibinders were checked directly against experimental structures **8YHT (7.7)** and **8YHU (8.6)**. Deposited entity names identify the binder chains; SIFTS maps target residues. The audit finds **28 and 31 contact residues**, respectively, at 5 Å. The four design-hotspot residues highlighted in the pilot are contained in both observed interfaces, but are not the complete epitopes. These are selected positive examples, not a systematic estimate of BioGRID's epitope coverage.

## Outputs and reproduction

- [Per-gene coverage, including zeros](../../data/analysis/binding_site_audit/gene_coverage.tsv)
- [Coverage by source and denominator](../../data/analysis/binding_site_audit/coverage_summary.tsv)
- [Binder/site observations, compressed TSV](../../data/analysis/binding_site_audit/observations.tsv.gz)
- [Retrieval and mapping status](../../data/analysis/binding_site_audit/retrieval_status.tsv)
- [BioGRID structure-review leads](../../data/analysis/binding_site_audit/biogrid_structure_leads.tsv)
- [Input hashes and retrieval provenance](../../data/analysis/binding_site_audit/manifest.json)

The existing binder-pilot inputs must be present first. No new credentials or model calls are required. Downloads and coordinate files remain in ignored `data/external/binding_site_audit/`; compressed derived observations and small coverage tables are committed. The source caches contain request URLs, status and retrieval timestamps; bulk-source URLs/timestamps and file hashes are also recorded. Caches freeze the retrieval; remove the cache directory to perform a fresh audit against changed upstream releases.

```sh
uv run python scripts/audit/fetch_binding_sites.py bulk
uv run python scripts/audit/fetch_binding_sites.py pdbe
uv run python scripts/audit/fetch_binding_sites.py compounds
uv run python scripts/audit/fetch_binding_sites.py uniprot
uv run python scripts/audit/fetch_binding_sites.py iedb
uv run python scripts/audit/fetch_binding_sites.py natural
uv run python scripts/audit/audit_antibody_contacts.py
uv run python scripts/audit/audit_biogrid_structure_leads.py
uv run python scripts/audit/summarize_binding_sites.py
uv run pytest -q tests/test_binding_site_audit.py tests/test_binder_coverage.py
```

All 5,574 PDBe ligand queries finished: 2,073 returned data and 3,501 returned no records (404); there were no transport failures. All 85 chemical-component batches, 56 UniProt batches and 463 natural-ligand interface queries completed. The 51 unresolved antibody representatives are retained as mapping failures, not counted as negatives.

Validation: 12 focused tests passed; repository-wide Ruff and scoped type checking passed. The repository-wide check stops at the existing missing `pydssp` dependency in `tag_sites/signals.py`; the full suite is not claimed as passing. Tests cover per-structure residue separation, insertion codes, target identity, ambiguous peptide matches, amino-acid mismatches, mixed topology, model selection and hydrogen exclusion.

Sources: [PDBe API](https://www.ebi.ac.uk/pdbe/pdbe-rest-api), [SAbDab](https://sabdab.opig.stats.ox.ac.uk/), [SIFTS](https://www.ebi.ac.uk/pdbe/docs/sifts/), [IEDB Query API](https://query-api.iedb.org/docs/swagger/), [UniProt](https://rest.uniprot.org/), [IUPHAR downloads](https://www.guidetopharmacology.org/download.jsp), [BioGRID synthetic proteins](https://thebiogrid.org/project/12), [TLR3 minibinder paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC11785957/). IUPHAR-derived fields retain the pilot's CC BY-SA attribution and ODbL terms. Raw paper text and antibody sequences are not redistributed in the new audit outputs.
