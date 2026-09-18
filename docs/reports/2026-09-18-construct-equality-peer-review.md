# Independent review of three construct-equality candidates

All three proposed pairs support a shared **deposited partner construct** label. This is a bounded identity decision for these pairs; it does not equate the entire complexes, target variants, biological states, or unmodeled chemistry. No accepted rules were edited by this reviewer.

| Pair / target | Independent evidence | Recommended shared label |
|---|---|---|
| FZD8–FKBP,21KR/21KS; LRP6 O75581 | The271 deposited monomers match exactly, including His/linker/FLAG sequences. Both map FZD8 Q9H46131–155 to entity positions12–136 and FKBP1A P629422–108 to157–263. Five intrachain disulfides match; neither partner has a deposited external covalent attachment. Partner entities are3 and1 respectively. Both also carry the same deposited C178S annotation; its numbering/origin must not be guessed. Target LRP6 constructs differ between the complexes, which does not make the partner fusion different. | **FZD8–FKBP fusion construct (21KR/21KS)** |
| CTNND1,3L6X/3L6Y; CDH1 P12830 | Both entity1 polymers have584 identical monomers and the same O60716 mapping span, including the internal deletion. Both explicitly describe p120-catenin isoform4A, deletion613–643 in depositor numbering. No modified-residue table or deposited internal/external covalent link changes. E-cadherin target is an18-residue intracellular juxtamembrane core fragment, not full surface protein. | **CTNND1 isoform4A deletion construct (3L6X/3L6Y)** |
| H2AX-derived peptide,2D31/2DYP; HLA-G P17693 | Both entity3 polymers are the exact nine-mer **RIIPRHLQL**, mapping P1610478–86. No deposited nonstandard monomers or covalent attachments. HLA-G target is wild-type disulfide-linked dimer context in2D31 and C42S/LILRB2 complex context in2DYP. Keep those target differences in source evidence.9RWI's eight-mer IIPRHLQL remains separate. | **H2AX-derived presented peptide RIIPRHLQL (9-mer)** |

Evidence independently read from all six full mmCIFs and mappings in `data/external/contact_construct_audit/`: `_entity_poly_seq`, `_entity_poly`, `_entity.pdbx_mutation`, `_entity.pdbx_fragment`, `_struct_conn`, `_struct_asym`, plus parent accession/entity mappings. The source hashes recorded in `contact_construct_suggestions.json` pin these files.

Primary/deposit references:

- [21KR](https://www.rcsb.org/structure/21KR), [21KS](https://www.rcsb.org/structure/21KS), [shared primary study](https://doi.org/10.1016/j.cell.2026.05.006).
- [3L6X](https://www.rcsb.org/structure/3L6X), [3L6Y](https://www.rcsb.org/structure/3L6Y), [shared primary study](https://doi.org/10.1016/j.cell.2010.01.017).
- [2D31](https://www.rcsb.org/structure/2D31), [2DYP](https://www.rcsb.org/structure/2DYP), [HLA-G dimer study](https://doi.org/10.1074/jbc.M512305200), [LILRB2–HLA-G study](https://doi.org/10.1073/pnas.0605228103).

## Algorithm boundaries

The script is appropriate as a **suggestion generator** and these three manual acceptances are supported. Its fingerprint is stronger than residue-footprint overlap: it compares exact deposited monomer IDs, parent accessions, reference spans and intrachain covalent links, while holding external covalent attachments and alternative polymer monomers.

Two qualifications should remain explicit before broader automatic use:

1. `chemistry_checked=True` currently means deposited annotations were inspected, not that all chemistry is experimentally known. Missing `_struct_conn` or modified-residue annotations cannot prove absence of unmodeled glycosylation, terminal modifications, ligation or preparation differences. These three pairs have matching deposited descriptions and no conflicting annotations; do not generalize that absence as universal proof.
2. `rows()` returns an empty list when any requested field is absent. For a partially populated chemistry category, this can silently treat unknown annotation as no links. Before allowing automatic acceptance, distinguish an absent category from an incomplete category and hold incomplete records. This did not affect the six inspected files: the matching relevant link categories are complete (or absent in both peptide/deletion deposits), and the raw partner metadata were independently checked.

Use the computed fingerprint only for the specifically accepted pairs. Preserve each original PDB, contact footprint, target state, raw source identity, and provenance. No native full-length FZD8/CTNND1/histone equivalence follows from these merges.
