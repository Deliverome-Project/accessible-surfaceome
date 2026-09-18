# Site-independent binder denominators: CellPhoneDB and Thera-SAbDab

Audit date: 2026-09-17 (America/New_York). Source-based benchmarks replace the broad LLM ligand flag for these specific questions; the full 5,130-gene cohort is retained for context. This is an audit, not a production annotation change.

## Main comparison

| Benchmark within the 5,130 candidates | Membrane-associated denominator | Genes with an extracellular site | Gene-level same-binder evidence |
|---|---:|---:|---|
| CellPhoneDB single-protein participants | 621 | 276/621 (44.4%) with any audited binder | 149 genes with a matching catalogued protein partner; 212 including IntAct regions |
| Thera-SAbDab named antibody targets | 244 | 116/244 (47.5%) with any audited antibody | 53/244 (21.7%) with a matching named therapeutic |

The two membrane-associated sets overlap by **138 genes** and cover **727 genes in union**. CellPhoneDB contributes 483 genes outside Thera-SAbDab; Thera-SAbDab contributes 106 outside CellPhoneDB. These sets describe catalogued binding opportunities, not all genes capable of binding a reagent.

The broad gene-level site column is intentionally not same-binder coverage: an unrelated antibody site does not establish a natural ligand's interface, and a research antibody's epitope does not establish the therapeutic antibody's epitope.

## Same-binder assessment

| Assessed question | Membrane-associated targets | Secreted-only targets |
|---|---:|---:|
| Genes with a matching CellPhoneDB protein interface, among genes with an assessable single-protein pair | 149/511 (29.2%) | 15/60 (25.0%) |
| Same, allowing IntAct binding regions | 212/511 (41.5%) | 19/60 (31.7%) |
| Individual CellPhoneDB target–protein pairs with an external structural interface | 192/1199 (16.0%) | 19/142 (13.4%) |
| Same pairs, allowing IntAct binding regions | 314/1199 (26.2%) | 25/142 (17.6%) |
| Individual therapeutic-entry–target pairs with an external antibody site | 133/875 (15.2%) | 4/37 (10.8%) |

The CellPhoneDB same-pair denominator is **511 membrane-associated genes / 1,199 target-oriented protein pairs**, rather than all 621 participant genes. The other 110 lack an assessable single-protein, non-self partner under the present identity matching rules (for example, their partner is a chemical or a complex). This difference is retained explicitly rather than treating unassessed categories as demonstrated site absence.

Pair counts are target-oriented: if both interacting genes are cohort targets, each target's site is assessed separately. Protein partners require the exact UniProt accession recorded by the source; alternate partner isoforms are not silently collapsed. Thera matching requires the same therapeutic catalogue name and stable target HGNC ID, using the earlier exact variable-domain/contact audit. IntAct complex associations are excluded from direct pair matches. Region support remains distinct from residue-level structural contacts. Structural contacts retain the earlier audit's candidate status: their physiological relevance has not been individually reviewed in every case.

## Secreted and uncertain targets

CellPhoneDB has **714** resolved single-protein participants in the cohort: 621 membrane-associated, 84 secreted-only and 9 other/uncertain. Thera-SAbDab has **269** mapped named-binder target genes: 244 membrane-associated, 21 secreted-only and 4 other/uncertain. These raw catalogue-overlap denominators require no known epitope.

For secreted-only genes, CellPhoneDB any-binder external-site coverage is **30/84 (35.7%)**. Thera any-antibody external-site coverage is **5/21 (23.8%)**, and same-therapeutic external-site coverage is **4/21 (19.1%)**.

Location is gene-level and includes annotated isoforms and processed products. “Membrane-associated” includes explicit cell-membrane locations (including apical/lateral/basolateral) plus generic membrane annotations accompanied by an extracellular topological domain. It does not prove that every isoform or epitope is externally accessible. Of the main denominators, **66 CellPhoneDB genes and 43 Thera genes** rely on the generic-membrane plus topology rule. With only explicit cell-membrane annotations, denominators are **555 and 201**, respectively; broad site coverage is **235/555 (42.3%)** and **96/201 (47.8%)**. Compartment uncertainty must not be interpreted as evidence of intracellular-only localization.

The existing contact audit's conservative mature-protein site rules are unchanged. Consequently, some processed/isoform-specific secreted sites remain uncredited even when gene-level secretion is established. Sites that span transmembrane pockets are retained in separate any-site columns; they do not satisfy the wholly-extracellular-site metric.

## CellPhoneDB construction

Use the official [CellPhoneDB source catalogue](https://github.com/ventolab/cellphonedb-data/tree/71ffa8a163389913907d40993bec2821a111f64d/data), pinned to commit `71ffa8a163389913907d40993bec2821a111f64d`: **2,911 interaction rows**, with protein and complex metadata. No expression-data prediction or inferred statistical cell–cell interaction is used.

Both protein endpoints can be candidate targets, including adhesion proteins, not just rows designated receptor. The primary gene benchmark uses targets represented as individual proteins in at least one interaction. Complex-only membership is separate: including complex components increases the membrane-associated set to **784 genes**, of which **391 (49.9%)** have some audited extracellular site; that does not establish direct ligand contact by each component.

Biosynthesis/transport proxies for non-protein ligands are identified from the complex metadata and `_by...` naming, and never credited as the ligand. Multiple production pathways for one named chemical are collapsed. A protein that is also independently listed as a true interaction participant can still qualify through that separate record. Intracellular receptors are not promoted merely because CellPhoneDB calls them a receptor. Source `is_ppi=False` is not used alone to remove an interaction: some listed hCG protein complexes carry that flag.

We retain chemical-partner and complex records, but do not yet claim exact chemical identity/site matching or complete complex-interface coverage. Across all cohort locations, the pair export contains **1349** assessable single-protein pairs, **255** chemical-identity-unmapped records, **2156** complex-context records and **16** self-interface records. These are not all independent ligand–receptor units because complex components remain explicit rows.

## Thera-SAbDab construction

Use the complete downloaded **1,133-entry Thera-SAbDab catalogue**, without filtering on structural availability, trial phase or development status. Its bytes are identical to the snapshot underlying the earlier therapeutic contact audit. Clinical-status columns refer to the source's February 2025 snapshot, not current approval status. Thera is a therapeutic-antibody catalogue; it is not a census of research antibodies.

Resolve target annotations through the full HGNC approved-symbol/alias table to stable HGNC IDs. Approved symbols take precedence over colliding short aliases (for example, PD1), and case-sensitive explicit symbols prevent hK2 from becoming HK2 when KLK2 is named. Keep veterinary targets, unresolved names, family/complex targets and conflicting multi-gene slash groups separate. Never use the presence of a structure to infer a denominator target. Generic CD3/CD8 and integrin complexes are not automatically assigned to one contact subunit.

A small source-linked review table resolves explicit gene-product qualifiers such as APP amyloid peptides, EGFRvIII and activated clotting factors at the parent-gene level; the qualifier is preserved. Such mapping does not imply cross-isoform epitope equivalence. Antibody format and original target annotation are retained for further review of fusions and multispecific entries. Names in the catalogue can represent separate entries for parts of a multispecific therapeutic; pair totals are catalogue-entry–target pairs, not necessarily distinct clinical drug products.

[Abagovomab is excluded](https://pmc.ncbi.nlm.nih.gov/articles/PMC5795662/) as a direct MUC16 binder because it is an anti-idiotypic antibody generated against OC125 that mimics the antigen. This illustrates why a target field alone needs semantic review. Other mapped targets remain source-annotated intended targets, not a claim of independently verified affinity for every entry.

Mapping outcomes are exported for every parsed target component: `{'anti_idiotype_mimics_antigen_not_direct_target_binder': 1, 'approved_symbol': 1113, 'complex_target_not_direct_subunit': 22, 'unresolved_or_nonprotein': 136, 'nonhuman_target': 16, 'reviewed_gene_product': 8, 'ambiguous_alias': 1, 'unique_alias': 9, 'ambiguous_slash_group': 2}`. Unresolved/non-protein categories include foreign antigens, glycans, chemicals and some unresolved human names; they are not all missing human genes. The 24 ambiguous shared-UniProt cohort records remain in the full 5,130 reference denominator but receive no accession-specific benchmark credit.

## Deliverables and validation

- `binder_denominator_genes.tsv`: all 5,130 genes, source membership, localization and coverage flags.
- `binder_denominator_cpdb_pairs.tsv`: exact and unresolved-scope interaction records with source row ordinals, publications, partner IDs and supporting structures.
- `binder_denominator_thera_pairs.tsv`: mapped catalogue-entry–target pairs, including pairs without sites.
- `binder_denominator_thera_resolution.tsv`: complete name-resolution audit.
- `binder_denominator_target_review.tsv` and `binder_denominator_exclusions.tsv`: explicit reviewed qualifiers and exclusions.
- `binder_denominator_summary.tsv` and `binder_denominator_manifest.json`: machine-readable totals, source versions and hashes.

Reproduce with `PYTHONPATH=src:scripts/audit uv run python scripts/audit/audit_binder_denominators.py --fetch`, after hydrating the existing cohort, HGNC and structural audit inputs. No paid model calls, production writes or deployment. Five focused tests cover alias collisions, species exclusions, complex semantics, chemical proxies and compartment classification; scoped Ruff/ty and full export reconciliation are run. Coverage figures are measured lower bounds from the existing site evidence, not estimates of every site present in the literature.
