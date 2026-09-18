# Why ligand-positive genes lack mapped extracellular sites: random 50-gene audit

The earlier 365/3,157 (11.56%) is **coverage under a strict residue-topology rule**,
not the fraction of known extracellular natural-ligand interactions that have
been discovered. The denominator uses the LLM field `has_known_ligand`, whose
rationales include intracellular interactors, transport substrates, receptor-family
inferences and some incorrect assignments. The numerator accepts any qualifying
binder, including antibodies, not necessarily the natural ligand named by the LLM.
These two distinctions matter when interpreting the percentage.

We randomly sampled **50 of the 2,792 ligand-positive genes without a credited EC
site**, without replacement (seed 20260917; eligible rows sorted by HGNC ID).
The sample was fixed before reviewing ligands; no substitutions were made.
Ten of the 50 already have some experimental mapped binder site in the existing
union, despite failing the EC criterion.

## Findings across all 50

Each gene has one primary diagnostic category; secondary issues are retained in
the [50-row audit](../../data/analysis/deep_dive_binding_sites/ligand_gap_sample50.tsv).
Categories describe the strongest observed explanation, not an exhaustive proof
that no other qualifying evidence exists.

| Primary explanation | Genes | Examples |
|---|---:|---|
| Binding, transport or functional evidence without an exact human interface recovered in this audit | 16 | PKD1–Wnt, GALR3–spexin, CDH13–adiponectin, NXPH3–neurexins |
| Intracellular or organelle interaction does not establish an EC ligand site | 10 | MLIP–lamin, SYNE2–SUN, JPT2–NAADP, CIB1–integrin cytoplasmic tail |
| LLM claim needs correction, qualification or exact ligand identification | 7 | LHFPL6, SLC38A12, OR6B2, OR2K2, OR4L1, HTR3C, TREML2 |
| Existing mapped site has a different compartment, binder or precursor context | 5 | CNR1, OPN1MW, SLC2A4, ULBP2, HSP90AA1 |
| Structural evidence missed by the retrieval strategy | 4 | AMHR2, ACVR1B, ERVFRD-1; ITGA6 has an additional laminin-complex lead |
| Existing mapped sites lack the explicit EC annotation required by the audit | 4 | PRNP, CD59, LRG1, ITLN1 |
| Structural/domain evidence comes from another species or paralog | 4 | SGCB, CLDN3, ROBO2, KREMEN2 |
| **Total** | **50** | |

The 16 unresolved cases are **not** a claim that no structure or epitope exists.
Some have mapped domains, functional mutations, or computational pocket models
that belong in a different evidence tier. For example, NXPH3 binding is localized
to a neurexin domain, while GALR3's cited loop contacts are docking predictions.
Nor are the seven flagged LLM records seven proven false interactions: the group
includes missing exact ligand identity, complex-level attribution and disputed
binding as well as a confirmed gene-identity error.

## Concrete recoveries and pitfalls

### Query PDBe interfaces without requiring an IUPHAR pair first

The direct protein-accession query returned candidate interfaces for three genes
that pass the existing explicit EC topology rule:

| Target | Partner | PDB | Why the previous path missed it |
|---|---|---|---|
| AMHR2 | AMH (P03971) | 7L0J | No target observation in the frozen IUPHAR-derived pair table |
| ACVR1B | Activin A (P08476); GDF11 (O95390) | 7OLY; 7MRZ | Natural-ligand IUPHAR rows were labelled complex components; the earlier pipeline admitted only single-protein targets |
| ERVFRD-1 / syncytin-2 | MFSD2A (Q8NA29) | 7OIX | No target observation in the frozen IUPHAR-derived pair table; target is also the ligand side of the biological relationship |

These are residue-indexed **candidate recoveries**, not newly published coverage.
AMHR2's complex is directly supported by the [deposited structure](https://www.rcsb.org/structure/7L0J).
The ACVR1B structure includes an engineered receptor fusion, and the
[syncytin complex](https://pdbj.org/mine/summary/7oix) uses thermostabilized constructs.
Constructs, mutations and chain mappings must remain attached to the evidence.
The [PDBe export](../../data/analysis/deep_dive_binding_sites/ligand_gap_pdbe_interfaces.tsv)
contains all sampled non-self interfaces, including irrelevant/intracellular ones;
its rows must not all be counted as natural-ligand evidence.

A fourth structural lead illustrates a second failure mode: **ITGA6** returns
404 from the accession-level PDBe interface endpoint, yet
[PDB 7CEC](https://www.rcsb.org/structure/7CEC) contains human alpha6beta1 bound to
laminin-511. SIFTS maps chain A to P23229. This is a different laminin complex
from the LLM's named laminin-332/LAMA4 examples; it is an alternative binder lead,
not validation of those exact pairs. PDB/SIFTS enumeration and coordinate-derived
contacts are a useful fallback when the aggregated interface endpoint is absent.

### Repair topology classification with mature-chain context

The old UniProt request only fetched sequence, topological domains and TM helices.
It omitted signal peptides, mature-chain boundaries, GPI attachment sites and
subcellular-location annotations. PRNP, CD59, LRG1 and ITLN1 therefore have mapped
sites classified as `unknown`, despite relevant extracellular/secreted mature
protein context. PRNP and LRG1's existing antibody sites are not the natural
interfaces named by the LLM, so recovery of their antibody coverage does not
validate those natural partners. CD59 additionally has direct C8/C9 interfaces
in PDBe and a [primary structural study](https://www.nature.com/articles/s41467-023-36441-z).

Do not simply label every GPI-protein residue extracellular. **ULBP2** is the
counterexample: the counted BioLiP Y01 contact positions 227 and 234 lie in its
218–246 propeptide, removed before the mature 26–217 chain is displayed. Its
PDBe interfaces in this probe concern GPI-processing machinery, not NKG2D.
[UniProt's processing annotations](https://www.uniprot.org/uniprotkb/Q9BZM5/entry)
make this distinction explicit. Secreted sites also need their own label;
secretion alone does not establish cell-surface anchoring or live-cell accessibility.

CNR1 and OPN1MW are different: their mapped ligand sites contain TM residues.
A membrane pocket can be accessible to a small molecule without being an entirely
EC protein epitope. SLC2A4's mapped cytochalasin site similarly fails the EC rule;
insulin-driven GLUT4 translocation is not direct insulin–GLUT4 binding.

### Validate the LLM ligand flag before using it as ground truth

- **LHFPL6:** the cited [GARLH paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC5347473/)
  identifies LHFPL3/4. The ledger mistakenly assigns LHFPL4's GABA-receptor role
  to LHFPL6. This is a confirmed attribution error.
- **OR6B2 and OR2K2:** the frozen rationales explicitly say the individual odorant
  has not been deorphanized, then assign `yes` from olfactory-receptor membership.
  **OR4L1** also lacks an exact ligand identity in its rationale.
- **SLC38A12:** cited ledger evidence concerns topology/expression, not transport
  of the three specifically claimed amino acids. [UniProt](https://www.uniprot.org/uniprotkb/Q8NE00/entry)
  still describes a putative transporter; the specific substrate assertion is unsubstantiated here.
- **HTR3C:** a [primary study](https://pubmed.ncbi.nlm.nih.gov/17392525/) supports
  coassembly with HTR3A. Complex-level serotonin responses do not establish an
  exact HTR3C contact site, and should not be converted into one.
- **TREML2–B7-H3:** the cited positive evidence includes murine work, while a
  [human binding study](https://pmc.ncbi.nlm.nih.gov/articles/PMC2978551/) found no
  interaction. Mark disputed/species-dependent rather than validated human binding.

Other cross-species/paralog examples are also concrete: the cited
[SGCB complex is mouse](https://pmc.ncbi.nlm.nih.gov/articles/PMC13178787/),
[6AKE is mouse Cldn3](https://www.rcsb.org/structure/6AKE), and
[5FWW contains KREMEN1, not KREMEN2](https://www.rcsb.org/structure/5FWW).
These can support a separately labelled transferred-site tier, not direct human
experimental coverage.

## Recommended next approach

1. **Improve the existing structural pipeline first.** Enumerate PDB/SIFTS
   complexes by stable protein ID in both ligand/receptor orientations; use
   unfiltered PDBe interfaces as leads, then confirm the pair and compute
   chain-level contacts. Keep complex-component leads instead of discarding them.
   Add mature-chain/GPI/secreted context and a separate membrane-pocket category.
   Three exact LLM partner matches and a fourth alternative-binder structure were
   found in this small audit, before adding another database.
2. **Add IntAct/IMEx feature-level evidence.** It explicitly captures binding
   regions and mutations affecting interactions, with experiment-level references.
   Retrieve those features, not just binary interaction edges. This is the most
   relevant new source for non-crystallographic sites; its incremental coverage
   has not yet been measured. [IntAct documentation](https://www.ebi.ac.uk/intact/documentation/user-guide)
3. **Use MatrixDB for extracellular matrix/glycan cases**, and
   **CellPhoneDB/OmniPath for pair and complex discovery**. These can supply
   better partner identities and literature leads for laminins, glycan binding,
   cytokines and multicomponent receptors. An interaction edge is not itself an
   epitope; it must be joined to structural or feature-level evidence.
   [MatrixDB](https://academic.oup.com/nar/article/39/suppl_1/D235/2507997),
   [CellPhoneDB documentation](https://cellphonedb.readthedocs.io/en/stable/RESULTS-DOCUMENTATION.html),
   [OmniPath](https://omnipathdb.org/)
4. **Mine the already collected primary references selectively.** Start from
   validated ligand pairs and look for deletion mapping, alanine scans, competition,
   crosslinking and binding assays. Store species, construct, direct versus indirect
   measurement, affinity, and residue/domain specificity. A mutation that changes
   signaling can affect folding or activation; it is not automatically a contact.
   Do not extract a cleavage position on the substrate as the receptor's binding site.

ChEMBL/BindingDB can enrich affinity and functional-assay records, but they are
not the first fix for the EC epitope gaps identified here. UniProt binding-site
features are useful too, provided their evidence codes are retained: the sampled
SLC2A5 fructose positions are annotated **by similarity**, not direct human
experimental sites. The [annotation export](../../data/analysis/deep_dive_binding_sites/ligand_gap_uniprot_sites.tsv)
retains those provenance codes.

## Scope, validation and reproducibility

All 50 frozen ligand rationales and their linked evidence-ledger claims were
reviewed. Public annotations were retrieved for all 50; fresh UniProt queries
succeeded for all 50. Direct PDBe queries returned 16 records and 34 HTTP 404s,
with no network errors. A 404 means absence from that endpoint, not absence of a
structure, as ITGA6 demonstrates. Primary-source web checks focused on structural
recoveries, disputed identities and species/paralog claims; this is not 50 exhaustive
systematic literature reviews. Two rationales (MLIP, CCNYL1) contain no ledger IDs.

All cached BioLiP rows for the sampled accessions were rechecked without the old
first-mapped-site stopping rule. This recovered **zero additional strict-EC genes
in this sample**. The stopping rule can still underestimate overall EC coverage;
no full-cohort extrapolation is justified from this result.

The seven primary categories are a manual diagnostic partition. Some genes have
multiple barriers, and these sample fractions must not be used to recalibrate the
full 3,157-gene denominator. No production records or previous coverage counts
were changed. Source hashes and sample membership are recorded in the
[manifest](../../data/analysis/deep_dive_binding_sites/ligand_gap_manifest.json).

Reproduce from cached inputs with:

```bash
PYTHONPATH=src:scripts/audit uv run python scripts/audit/audit_ligand_gaps.py
```

Add `--fetch` to retrieve missing public annotations and database records. Existing
cache entries are retained. Human-reviewed notes are committed separately, so
numerical sampling, retrieval summaries and output joins can be reproduced without
paid model calls. The previous audit's frozen inputs remain prerequisites.
