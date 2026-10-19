# Updated source coverage with curated binder denominators

Denominators: all 5,130 candidates; 621 membrane-associated CellPhoneDB single-protein participants; 244 membrane-associated Thera-SAbDab target genes. Catalogue membership does not require an epitope. The two curated sets overlap by 138 genes.

## Source-by-source coverage

| Source | All genes / 5,130 | Unique genes¹ | CPDB: any binder / 621 | Thera: any antibody epitope / 244 | EC: all / 5,130 | EC: CPDB / 621 | EC: Thera antibody / 244 |
|---|---:|---:|---:|---:|---:|---:|---:|
| SAbDab: antibody contacts | 409 (8.0%) | 9 | 157 (25.3%) | 126 (51.6%) | 259 (5.0%) | 116 (18.7%) | 111 (45.5%) |
| Thera-SAbDab: named antibody contacts | 80 (1.6%) | 0 | 44 (7.1%) | 62 (25.4%) | 61 (1.2%) | 40 (6.4%) | 55 (22.5%) |
| AACDB: antibody contacts | 210 (4.1%) | 0 | 92 (14.8%) | 88 (36.1%) | 156 (3.0%) | 81 (13.0%) | 83 (34.0%) |
| IEDB: exact antibody epitopes | 182 (3.5%) | 0 | 88 (14.2%) | 82 (33.6%) | 129 (2.5%) | 75 (12.1%) | 79 (32.4%) |
| PDBe + IUPHAR: chemical sites | 209 (4.1%) | 0 | 91 (14.7%) | — | 36 (0.7%) | 10 (1.6%) | — |
| PDBe + IUPHAR: protein ligands | 120 (2.3%) | 0 | 111 (17.9%) | — | 54 (1.1%) | 48 (7.7%) | — |
| BioGRID-linked minibinders | 1 (<0.1%) | 0 | 0 (0.0%) | — | 0 (0.0%) | 0 (0.0%) | — |
| BioLiP: biological ligand sites | 851 (16.6%) | 102 | 208 (33.5%) | — | 186 (3.6%) | 56 (9.0%) | — |
| GPCRdb: experimental contacts | 190 (3.7%) | 3 | 147 (23.7%) | — | 15 (0.3%) | 10 (1.6%) | — |
| PDB/PDBe: expanded protein interfaces | 1,326 (25.8%) | 127 | 412 (66.3%) | — | 507 (9.9%) | 235 (37.8%) | — |
| IntAct: binding regions | 1,610 (31.4%) | 387 | 384 (61.8%) | — | 501 (9.8%) | 239 (38.5%) | — |
| IntAct: interaction-changing mutations | 494 (9.6%) | 28 | 134 (21.6%) | — | 125 (2.4%) | 66 (10.6%) | — |
| SurfaceBind: predicted sites | 1,609 (31.4%) | 619 | 382 (61.5%) | — | — | — | — |
| Mapped-site union | 1,680 (32.7%) | — | 451 (72.6%) | 131 (53.7%) | 661 (12.9%) | 276 (44.4%) | 116 (47.5%) |
| Mapped sites OR IntAct regions | 2,391 (46.6%) | — | 539 (86.8%) | 131 (53.7%) | 855 (16.7%) | 343 (55.2%) | 116 (47.5%) |
| Also including mutation effects | 2,431 (47.4%) | — | 539 (86.8%) | 131 (53.7%) | 871 (17.0%) | 348 (56.0%) | 116 (47.5%) |
| Mapped sites OR SurfaceBind predictions | 2,587 (50.4%) | — | 566 (91.1%) | 131 (53.7%) | — | — | 116 (47.5%) |

## Effect of the pipeline improvements

These are before/after comparisons using the same curated denominator memberships, not the earlier LLM subset.

| Pipeline stage | CPDB: any binder site / 621 | CPDB: EC binder site / 621 | Thera: any antibody epitope / 244 | Thera: EC antibody epitope / 244 |
|---|---:|---:|---:|---:|
| Previous pipeline, same curated denominators | 332 (53.5%) | 166 (26.7%) | 131 (53.7%) | 112 (45.9%) |
| Mature-protein topology repair | 330 (53.1%) | 168 (27.1%) | 131 (53.7%) | 116 (47.5%) |
| Plus expanded PDB/PDBe retrieval | 451 (72.6%) | 276 (44.4%) | 131 (53.7%) | 116 (47.5%) |
| Plus IntAct binding regions | 539 (86.8%) | 343 (55.2%) | 131 (53.7%) | 116 (47.5%) |
| Plus IntAct mutation effects | 539 (86.8%) | 348 (56.0%) | 131 (53.7%) | 116 (47.5%) |

## Interpretation

- CPDB columns count any qualifying binder on a catalogue gene; the binder need not be the CellPhoneDB ligand. Thera columns count any qualifying antibody epitope on a catalogue target; it need not belong to the named therapeutic. Neither column is same-binder coverage.
- Streams without validated antibody identity show — in the Thera antibody columns: antibody-epitope coverage was not classified for those streams. Generic structure databases may contain antibody complexes, but those are not automatically credited. IntAct therefore increases binder-region coverage but does not increase the antibody-epitope numerator in this audit.
- IntAct regions are often broad constructs; mutation effects may be indirect. Their union rows broaden the evidence definition and must not be described as exact-site or exact-epitope coverage. The mapped-site union remains the primary residue-level result.
- SurfaceBind is predicted evidence and stays separate. Its anchor-only export cannot establish a wholly extracellular patch or an antibody epitope, so those columns are unassessed rather than zero.
- EC means all retained mapped site residues are explicitly extracellular or in a mature cell-membrane GPI chain, with precursor exclusions and the recorded CFAP95 assembly-context correction. Secreted-only targets are outside these membrane-associated denominator columns. Structural interfaces remain candidates with biological relevance not reviewed individually in every case.
- ¹ Unique genes means covered by that stream and none of the other 12 displayed source streams, including IntAct tiers and SurfaceBind. This is not order-dependent incremental coverage. The TSV also gives exclusivity among mapped-site sources only. Thera-SAbDab is an identity layer over structures, not an independent experimental corpus.
- The compartment denominator includes annotated forms/isoforms and a flagged generic-membrane plus extracellular-topology subset: 66 CellPhoneDB genes and 43 Thera genes. It does not demonstrate live-cell accessibility. Name-resolution and complex-membership exclusions are documented in [the denominator audit](../../../docs/reports/2026-09-17-binder-denominators.md).

## Reproduction

Run `PYTHONPATH=src:scripts/audit uv run python scripts/audit/tabulate_curated_binder_sources.py` after hydrating the existing audit inputs. Companion TSVs contain the full source table, fixed-denominator improvement stages and per-gene source membership with stable identifiers. No source downloads, paid model calls or production changes are needed.
