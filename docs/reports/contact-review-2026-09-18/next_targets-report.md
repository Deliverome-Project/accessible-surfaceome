# Next eight targets: proposed contact-identity review

Release `contacts-ba6680878403e6980464`; reviewed 2026-09-18. **80 proposed rules, all 374 source observations retained.** No database writes, deployed changes, shared source edits, commits, or publication. Rules require independent review before integration.

The review audited every supplied named partner and all raw observation groups. It used public PDB entry metadata, focused deposited polymer sequences/mutation fields, primary structural publications, official clinical identity sources, and the unchanged therapeutic match cache. Canonical names identify verified constructs; they do not imply that every interaction establishes accessibility on an intact cell. Valid matched-arm therapeutics remain named with inference provenance, including Bexatamig and Mosunetuzumab. No blanket exclusions are proposed.

## Material findings

- **F3 P13726:** consolidate humanized D3H44 and hATR-5 source aliases. Keep 10H10 and its humanized derivative M1587 separate, as required by the [humanization study](https://pmc.ncbi.nlm.nih.gov/articles/PMC5825201/). Promote verified factor VIIa observations from P08709, but separate the V158D/E296V/M298Q construct at [3ELA](https://www.rcsb.org/structure/3ELA), YT and ST trypsin-loop chimeras at [4Z6A](https://www.rcsb.org/structure/4Z6A)/[4ZMA](https://www.rcsb.org/structure/4ZMA), and VYT at [6R2W](https://www.rcsb.org/structure/6R2W). Native-sequence VIIa remains endogenous_large in 1J9C/2PUQ/8CN9/8UUD, with active-site inhibitor/assembly context preserved.
- **NT5E P21589:** [the sponsor's structural figure](https://www.innate-pharma.com/sites/default/files/poster_sitc_2019_iph5301_120x120.pdf) and primary 6HXW study identify deposited IPH53 as IPH5301. Its [clinical program](https://www.innate-pharma.com/products/iph5301) supports therapeutic classification. TB19, TB38, and mAb19 remain separate experimental antibodies. [AP2](https://www.rcsb.org/ligand/AP2) and [A12](https://www.rcsb.org/ligand/A12) have the same InChIKey and represent AMPCP, a synthetic nucleotide inhibitor, not endogenous AMP/ADP.
- **DPP4 P27487:** chemical identifiers resolve to sitagliptin, teneligliptin, alogliptin, linagliptin, and anagliptin. Their deposited structural identities and clinical status support therapeutic classification; [PMDA teneligliptin review](https://www.pmda.go.jp/files/000153594.pdf) and [anagliptin review](https://www.pmda.go.jp/files/000218646.pdf) provide primary clinical corroboration. CJP and N7F stay experimental tools. [2BGR](https://www.rcsb.org/structure/2BGR) has HIV-1 Tat(1–9), while [2BGN](https://www.rcsb.org/structure/2BGN) has engineered Trp2-Tat(1–9); these are separate. Bovine ADA is explicitly cross-species and unclassified, with 1W1I/2BGN construct qualifiers pending their sequence-discrepancy reconciliation. [1R9N](https://www.rcsb.org/structure/1R9N) has a synthetic NPY(1–10) substrate fragment, not intact human NPY.
- **IL3RA P26951:** [NCI](https://www.cancer.gov/publications/dictionaries/cancer-drug/def/talacotuzumab) supports CSL362 = talacotuzumab. Bexatamig stays separate: [Thera-SAbDab](https://opig.stats.ox.ac.uk/webapps/sabdab-sabpred/therasabdab/therasummary/?INN=Bexatamig) lists 100% Fv1 matches to 4JZJ AB/HL; the unchanged cache labels this `Thera_100pct_structure_chain`. Its [WHO identity](https://cdn.who.int/media/docs/default-source/international-nonproprietary-names-%28inn%29/pl131.pdf) is a CD123/NKp46 engager, not the intact CSL362 antibody. **All supplied IL-3 cytokine complexes are engineered:** precursor W32Y equals mature W13Y; the 5UV8 and 6NMY shared cytokine sequence is identical, so both use one W13Y canonical identity. 6NMY differs in cloning prefix and terminal truncation only. 5UWC additionally has mature K116W, a distinct affinity-enhancing variant in the [primary study](https://pmc.ncbi.nlm.nih.gov/articles/PMC5785977/). CSF2RB at 6NMY includes an engineered domain and is labeled accordingly. EDT is [EDTA](https://www.rcsb.org/ligand/EDT), retained as an assay chelator, not a selective receptor therapeutic.
- **FCGRT P55899:** preserve nipocalimab, orilanolimab/SYNT001, and rozanolixizumab as distinct therapeutics. [The clinical register](https://www.clinicaltrialsregister.eu/ctr-search/trial/2019-004055-37/ES) explicitly relates orilanolimab/SYNT001/ALXN1830. DX-2507 remains a distinct preclinical tool; 5WHK heavy/light entity accessions explain S6BAN1/Q6NS95 source duplicates. B2M is a receptor component. EQY is UCB-303. Native albumin at 4N0F/4N0U is separate from **HSAopt** at 4K71/6QIO/6QIP. The 6QIP entity omits mutation metadata, but its sequence is identical to 6QIO, and the [primary study](https://doi.org/10.1021/acs.biochem.0c00019) explicitly documents four-substitution HSAopt. P01857 is the **YTE Fc variant** at 4N0U and **efgartigimod** at [7Q15](https://www.rcsb.org/structure/7Q15). P01861 at 6WNA and 6WOL represents two distinct engineered monomeric IgG4 Fc sequences. None should become generic native IgG contacts.
- **CD3E P07766:** OKT3 and muromonab consolidate; UCHT1 stays distinct. Mosunetuzumab is supported by exact VH/VL evidence to parental 40G5c. The [primary paper](https://doi.org/10.1080/19420862.2026.2658902) identifies 9T46 as the parental template for later pH-responsive engineering. **The target is a nine-residue CD3E peptide**, not the full ectodomain. CD3D/CD3G/CD247/TRB remain receptor components, while SYK/EPS8L1/NCK1 contacts are intracellular evidence retained in all scope. Generic BioLiP `peptide` at 9CI8 cannot be safely assigned to one of several short receptor chains without chain provenance; it remains explicitly unresolved.
- **IL2RA P01589:** basiliximab and daclizumab retain therapeutic identities; [NCI](https://www.cancer.gov/publications/dictionaries/cancer-drug/def/vopikitug) supports RG6292 = vopikitug. The misleading source label `CD25‑IL‑2 Fab` at 7F9W is **BT942**, a separate experimental antibody in the [primary study](https://doi.org/10.1038/s41598-021-02449-y), not IL-2 or BA9. Native-sequence IL-2 appears at 1Z92/2B5I/9KMC. **2ERJ has IL-2 C125A**, so it receives a separate tool identity. A deposited synonym says aldesleukin, but this C125A sequence does not establish the distinct aldesleukin drug identity.
- **KIT P10721:** Fab19 and Fab79D remain separate, including no-PDB IEDB records whose shared numeric ID 543 must never be used as an alias. Native SCF is kept separate from target KIT mutations in 8DFP/8DFQ. Imatinib, sunitinib, crenolanib, and pexidartinib are retained as intracellular drug evidence; [NCI crenolanib identity](https://www.cancer.gov/publications/dictionaries/cancer-drug/def/crenolanib) corroborates the 8S1A chemical name. SOCS6 and PIK3R1 are native intracellular peptide-binding partners. None is removed from all scope merely because it is not extracellular.

## Remaining uncertainties and intentionally unpromoted records

1. Viral partners are present among DPP4 and FcRn raw observations. The current enum has no viral/exogenous category. Their PDB titles are inventoried below; they remain raw and unclassified rather than being called endogenous human ligands. In particular A3EX94 appears with bat HKU4 at 4QZV and a pangolin-coronavirus description at 9K9N; a global accession rename would obscure this discrepancy. FcRn capsid mappings can represent different proteins in one viral polyprotein or different viruses; they should not be collapsed solely from shared receptor footprints.
2. Generic antibody constant-region accessions and anonymous SAbDab identifiers remain unpromoted unless specific deposited entity evidence was inspected, as for DX-2507. These are not additional endogenous ligands. The raw appendix identifies the source/PDB groups so a later chain-level pass can connect them without inventing an antibody identity.
3. CD3E's numerous TCR variable/constant accessions are assembly/domain mappings, not necessarily independent ligand species. The supplied named CD3D/CD3G/CD247/TRB groups are classified; additional domain accessions remain unchanged pending chain-level reconciliation. The GFP-related P42212 at 7PHR is an assay construct, not a native TCR ligand.
4. Bovine ADA at 1W1I is naturally sourced, but the entry-level page flags three sequence differences without an entity mutation description. It remains a construct-qualified unclassified row rather than a confident engineered/WT assertion. Bovine ADA at 2BGN has the same entry-level three-difference warning despite absent entity mutation annotation, and likewise remains construct-qualified and unclassified. Neither cross-species protein is classified as endogenous to humans. These two named constructs should be reconsidered together if reference-sequence reconciliation proves the discrepancies are only deposited-model corrections.
5. All IL-3 source “IL-3” labels are overridden only within their verified structures. Mutation numbering was reconciled rather than counted as an extra ligand: W32Y precursor = W13Y mature. K116W uses the mature numbering of the primary study; the raw deposit mixes numbering conventions. The sequence check is saved in `data/analysis/deep_dive_binding_sites/contact_review_sequence_checks.json`.
6. Category `tool` for preclinical antibodies means no clinical drug identity was established in this bounded review; it does not deny biological or therapeutic potential. A shared footprint or humanization relationship alone did not justify merging M1587/10H10, TB19/TB38, or distinct therapeutics.

## Matcher verification and estimated counts

All 80 rules match at least one supplied raw observation. Running the current production `apply_partner_review` function over all 374 observations produced no conflicting effective rules. Exact source names are used; no raw numeric IEDB identifier is used as a rule name. PDB-scoped rules use lowercase IDs and override global aliases. Reviewed canonical names retain qualifiers literally and promote verified bare accessions. No exclusion flags are set true. Existing compartment labels handle intracellular and membrane-spanning evidence.

Counts below reproduce the current named-partner/compartment predicates on the snapshot, not a rebuilt deployed release. They count named identities and experimental variants, not independent drugs or full-length structures. Increased counts reflect reviewed bare-accession promotion and variant splitting; decreased counts reflect justified aliases.

Peer review correction applied: both bovine ADA structures are unclassified, and 2BGN retains the same mutation-annotation caveat as 1W1I. Sequence checks compare deposited sequence strings, not independent resequencing or coordinate validation.

| Target | Accession | Original observations | Original all / EC names | Proposed all / EC names |
|---|---|---:|---:|---:|
| F3 | P13726 | 21 | 7 / 7 | 10 / 10 |
| NT5E | P21589 | 15 | 7 / 7 | 5 / 5 |
| DPP4 | P27487 | 25 | 7 / 7 | 12 / 12 |
| IL3RA | P26951 | 15 | 6 / 6 | 6 / 6 |
| FCGRT | P55899 | 61 | 6 / 6 | 12 / 12 |
| CD3E | P07766 | 186 | 11 / 6 | 11 / 5 |
| IL2RA | P01589 | 23 | 5 / 5 | 6 / 6 |
| KIT | P10721 | 28 | 9 / 5 | 9 / 3 |

## Explicit rule index and evidence

Indices are one-based in the companion JSON. Every rule preserves raw labels and contacts. `all PDBs` means the alias is intentionally global for this target; generic or engineered entities use a structure scope.

**1. P13726 — 10H10** (`tool`; 4m7l). Exact names: `10H10`; `10H10 Fab`. Deposited experimental antibody. M1587 is a humanized derivative of 10H10, not an identical clone; keep both separately named. [Evidence](https://www.rcsb.org/structure/4M7L).

**2. P13726 — 5G9** (`tool`; 1ahw). Exact names: `5G9`; `5G9 Fab`. Deposited experimental antibody. M1587 is a humanized derivative of 10H10, not an identical clone; keep both separately named. [Evidence](https://www.rcsb.org/structure/1AHW).

**3. P13726 — M1587** (`tool`; 5w06). Exact names: `M1587`; `M1587 Fab`. Deposited experimental antibody. M1587 is a humanized derivative of 10H10, not an identical clone; keep both separately named. [Evidence](https://www.rcsb.org/structure/5W06).

**4. P13726 — D3H44 (humanized)** (`tool`; 1jps). Exact names: `D3H44 Fab`; `humanized D3h44`. Humanized experimental anti-tissue-factor antibody, directly deposited; no verified clinical drug identity established in this review. [Evidence](https://www.rcsb.org/structure/1JPS).

**5. P13726 — hATR-5 (humanized)** (`tool`; 1uj3). Exact names: `hATR-5 Fab`; `humanized anti-tissue factor hATR-5`. Deposited humanized experimental anti-tissue-factor Fab. Both labels describe the same construct. [Evidence](https://www.rcsb.org/structure/1UJ3).

**6. P13726 — Factor VIIa** (`endogenous_large`; 1j9c). Exact names: `P08709`. Native-sequence coagulation factor VIIa partner. Active-site inhibitors and other entities in the assembly do not change this protein identity; preserve their assay context. [Evidence](https://www.rcsb.org/structure/1J9C).

**7. P13726 — Factor VIIa** (`endogenous_large`; 2puq). Exact names: `P08709`. Native-sequence coagulation factor VIIa partner. Active-site inhibitors and other entities in the assembly do not change this protein identity; preserve their assay context. [Evidence](https://www.rcsb.org/structure/2PUQ).

**8. P13726 — Factor VIIa** (`endogenous_large`; 8cn9). Exact names: `P08709`. Native-sequence coagulation factor VIIa partner. Active-site inhibitors and other entities in the assembly do not change this protein identity; preserve their assay context. [Evidence](https://www.rcsb.org/structure/8CN9).

**9. P13726 — Factor VIIa** (`endogenous_large`; 8uud). Exact names: `P08709`. Native-sequence coagulation factor VIIa partner. Active-site inhibitors and other entities in the assembly do not change this protein identity; preserve their assay context. [Evidence](https://www.rcsb.org/structure/8UUD).

**10. P13726 — Factor VIIa V158D/E296V/M298Q** (`tool`; 3ela). Exact names: `P08709`. Engineered factor VIIa construct explicitly documented in deposited entity metadata and primary publication; not wild-type factor VIIa. Mutation numbering follows the deposited construct. [Evidence](https://www.rcsb.org/structure/3ELA).

**11. P13726 — Factor VIIa–trypsin YT chimera** (`tool`; 4z6a). Exact names: `P08709`. Engineered factor VIIa construct explicitly documented in deposited entity metadata and primary publication; not wild-type factor VIIa. Mutation numbering follows the deposited construct. [Evidence](https://www.rcsb.org/structure/4Z6A).

**12. P13726 — Factor VIIa–trypsin ST chimera** (`tool`; 4zma). Exact names: `P08709`. Engineered factor VIIa construct explicitly documented in deposited entity metadata and primary publication; not wild-type factor VIIa. Mutation numbering follows the deposited construct. [Evidence](https://www.rcsb.org/structure/4ZMA).

**13. P13726 — Factor VIIa VYT variant** (`tool`; 6r2w). Exact names: `P08709`. Engineered factor VIIa construct explicitly documented in deposited entity metadata and primary publication; not wild-type factor VIIa. Mutation numbering follows the deposited construct. [Evidence](https://www.rcsb.org/structure/6R2W).

**14. P21589 — IPH5301** (`therapeutic`; 6hxw). Exact names: `IPH53 Fab`; `IPH5301`. Deposited IPH53 Fab is identified as IPH5301 in the primary study and sponsor structural figure. Clinical IPH5301 program verified; Fab evidence does not show intact Fc function. [Evidence](https://www.innate-pharma.com/sites/default/files/poster_sitc_2019_iph5301_120x120.pdf).

**15. P21589 — TB19** (`tool`; 6vc9). Exact names: `TB19`; `TB19 Fab`. Distinct experimental anti-CD73 antibody, documented in the primary structural study. Do not collapse with other anti-CD73 clones or infer a clinical drug identity. [Evidence](https://www.rcsb.org/structure/6VC9).

**16. P21589 — TB38** (`tool`; 6vca). Exact names: `TB38`; `TB38 Fab`. Distinct experimental anti-CD73 antibody, documented in the primary structural study. Do not collapse with other anti-CD73 clones or infer a clinical drug identity. [Evidence](https://www.rcsb.org/structure/6VCA).

**17. P21589 — mAb19** (`tool`; 7bbj). Exact names: `mAb19`; `mAb19 Fab`. Distinct experimental anti-CD73 antibody, documented in the primary structural study. Do not collapse with other anti-CD73 clones or infer a clinical drug identity. [Evidence](https://www.rcsb.org/structure/7BBJ).

**18. P26951 — Talacotuzumab** (`therapeutic`; all PDBs). Exact names: `Talacotuzumab`; `CSL362 Fab`. NCI identifies CSL362 as talacotuzumab. 4JZJ directly observes the Fab; cached exact VH/VL arm matches support the catalogue rows. Fc engineering is not observed. [Evidence](https://www.cancer.gov/publications/dictionaries/cancer-drug/def/talacotuzumab).

**19. P26951 — Bexatamig** (`therapeutic`; 4jzj). Exact names: `Bexatamig`. Retain separately named therapeutic-arm evidence to CSL362 template. Cached match tier is Thera_100pct_structure_chain; it is not a complete bispecific structure. Official Thera-SAbDab lists 100% Fv1 matches for 4JZJ AB/HL; Bexatamig is the distinct CD123/NKp46 engager. [Evidence](https://opig.stats.ox.ac.uk/webapps/sabdab-sabpred/therasabdab/therasummary/?INN=Bexatamig).

**20. P26951 — IL-3 W13Y variant** (`tool`; 5uv8). Exact names: `GTOPDB:4994`; `P08700`; `IL-3`. The deposited cytokine is engineered, not wild-type IL-3. Preserve the experimental mutation and construct numbering; source accession and GTOPDB labels are retained raw. W32Y in precursor numbering is W13Y after the 19-residue signal peptide. The 5UV8/6NMY overlapping cytokine sequence is identical; terminal construct truncation and cloning residues remain PDB-level provenance, not separate mutant identities. K116W follows the mature-numbered primary paper. [Evidence](https://www.rcsb.org/structure/5UV8).

**21. P26951 — IL-3 W13Y/K116W variant** (`tool`; 5uwc). Exact names: `GTOPDB:4994`; `P08700`; `IL-3`. The deposited cytokine is engineered, not wild-type IL-3. Preserve the experimental mutation and construct numbering; source accession and GTOPDB labels are retained raw. W32Y in precursor numbering is W13Y after the 19-residue signal peptide. The 5UV8/6NMY overlapping cytokine sequence is identical; terminal construct truncation and cloning residues remain PDB-level provenance, not separate mutant identities. K116W follows the mature-numbered primary paper. [Evidence](https://www.rcsb.org/structure/5UWC).

**22. P26951 — IL-3 W13Y variant** (`tool`; 6nmy). Exact names: `GTOPDB:4994`; `P08700`; `IL-3`. The deposited cytokine is engineered, not wild-type IL-3. Preserve the experimental mutation and construct numbering; source accession and GTOPDB labels are retained raw. W32Y in precursor numbering is W13Y after the 19-residue signal peptide. The 5UV8/6NMY overlapping cytokine sequence is identical; terminal construct truncation and cloning residues remain PDB-level provenance, not separate mutant identities. K116W follows the mature-numbered primary paper. [Evidence](https://www.rcsb.org/structure/6NMY).

**23. P26951 — CSF2RB (6NMY engineered construct)** (`receptor_partner`; 6nmy). Exact names: `P32927`; `CSF2RB`. Shared cytokine receptor beta subunit, represented by multiple deposited domain entities, one annotated N346Q. Keep receptor-partner biology but make engineered construct explicit; per-domain chain distinction exceeds the current matcher. [Evidence](https://www.rcsb.org/structure/6NMY).

**24. P55899 — Nipocalimab** (`therapeutic`; all PDBs). Exact names: `Nipocalimab`; `Nipocalimab Fab`. Named FcRn therapeutic Fab supported by primary structural evidence and cached exact VH/VL match. Orilanolimab is SYNT001 (6NHA); no equivalence to DX-2507 is inferred. [Evidence](https://www.rcsb.org/structure/9MI6).

**25. P55899 — Orilanolimab** (`therapeutic`; all PDBs). Exact names: `Orilanolimab`; `Orilanolimab Fab`. Named FcRn therapeutic Fab supported by primary structural evidence and cached exact VH/VL match. Orilanolimab is SYNT001 (6NHA); no equivalence to DX-2507 is inferred. [Evidence](https://www.rcsb.org/structure/6NHA).

**26. P55899 — Rozanolixizumab** (`therapeutic`; all PDBs). Exact names: `Rozanolixizumab`; `Rozanolixizumab Fab`. Named FcRn therapeutic Fab supported by primary structural evidence and cached exact VH/VL match. Orilanolimab is SYNT001 (6NHA); no equivalence to DX-2507 is inferred. [Evidence](https://www.rcsb.org/structure/6FGB).

**27. P55899 — B2M** (`receptor_partner`; all PDBs). Exact names: `P61769`; `B2M`. Beta-2-microglobulin is the structural light-chain component of the FcRn receptor, not an FcRn-blocking drug. [Evidence](https://www.rcsb.org/structure/1EXU).

**28. P55899 — DX-2507** (`tool`; 5whk). Exact names: `DX-2507 Fab`; `S6BAN1`; `Q6NS95`. Deposited heavy/light antibody chains explain both generic accession rows. Preclinical anti-FcRn reagent; no verified clinical identity in this review, and no merging with DX-2504 or named FcRn drugs. [Evidence](https://www.rcsb.org/structure/5WHK).

**29. P07766 — Muromonab (OKT3)** (`therapeutic`; all PDBs). Exact names: `Muromonab`; `OKT3 Fab`; `OKT3`. OKT3 is the therapeutic muromonab antibody; directly observed Fab contacts and exact VH/VL catalogue matches at 1SY6/9IRS. No inference of other humanized anti-CD3 drugs. [Evidence](https://www.rcsb.org/structure/1SY6).

**30. P07766 — UCHT1** (`tool`; all PDBs). Exact names: `UCHT1 Fv`; `UCHT1`. Distinct experimental anti-CD3 antibody; 1XIW deposits the single-chain UCHT1 antibody fragment. [Evidence](https://www.rcsb.org/structure/1XIW).

**31. P07766 — Mosunetuzumab** (`therapeutic`; 9t46). Exact names: `Mosunetuzumab`. Exact VH/VL catalogue match to parental 40G5c anti-CD3 Fab. The primary paper identifies 40G5c as the mosunetuzumab arm; 9T46 is the parental template, not a complete CD20/CD3 bispecific or the pH-engineered derivatives. Target evidence is a nine-residue CD3 epsilon peptide, not a full ectodomain accessibility experiment. [Evidence](https://doi.org/10.1080/19420862.2026.2658902).

**32. P07766 — CD3D** (`receptor_partner`; all PDBs). Exact names: `P04234`; `CD3D`. Subunit of the TCR-CD3 receptor complex; preserve source compartment labels, including membrane-spanning observations. [Evidence](https://www.rcsb.org/structure/6JXR).

**33. P07766 — CD3G** (`receptor_partner`; all PDBs). Exact names: `P09693`; `CD3G`. Subunit of the TCR-CD3 receptor complex; preserve source compartment labels, including membrane-spanning observations. [Evidence](https://www.rcsb.org/structure/6JXR).

**34. P07766 — CD247** (`receptor_partner`; all PDBs). Exact names: `P20963`; `CD247`. Subunit of the TCR-CD3 receptor complex; preserve source compartment labels, including membrane-spanning observations. [Evidence](https://www.rcsb.org/structure/6JXR).

**35. P07766 — TRB** (`receptor_partner`; all PDBs). Exact names: `P0DSE2`; `TRB`. Subunit of the TCR-CD3 receptor complex; preserve source compartment labels, including membrane-spanning observations. [Evidence](https://www.rcsb.org/structure/7FJD).

**36. P07766 — SYK** (`endogenous_large`; 1a81). Exact names: `P43405`; `SYK`. Native intracellular signaling protein/domain contacting a cytoplasmic CD3E peptide; retained in all-contact scope. Existing compartment annotation excludes it from extracellular scope. [Evidence](https://www.rcsb.org/structure/1A81).

**37. P07766 — EPS8L1** (`endogenous_large`; 2rol). Exact names: `Q8TE68`; `EPS8L1`. Native intracellular signaling protein/domain contacting a cytoplasmic CD3E peptide; retained in all-contact scope. Existing compartment annotation excludes it from extracellular scope. [Evidence](https://www.rcsb.org/structure/2ROL).

**38. P07766 — NCK1** (`endogenous_large`; 5qu2). Exact names: `P16333`; `NCK1`. Native intracellular signaling protein/domain contacting a cytoplasmic CD3E peptide; retained in all-contact scope. Existing compartment annotation excludes it from extracellular scope. [Evidence](https://www.rcsb.org/structure/5QU2).

**39. P01589 — Basiliximab** (`therapeutic`; all PDBs). Exact names: `Basiliximab`; `basiliximab`; `Basiliximab Fab`; `basiliximab Fab`; `basiliximab (Simulect)`. Named therapeutic antibody directly identified in the structural publication; consolidate spelling/Fab source aliases without altering raw observations. [Evidence](https://www.rcsb.org/structure/3IU3).

**40. P01589 — Daclizumab** (`therapeutic`; all PDBs). Exact names: `Daclizumab`; `daclizumab`; `Daclizumab Fab`; `daclizumab Fab`. Named therapeutic antibody directly identified in the structural publication; consolidate spelling/Fab source aliases without altering raw observations. [Evidence](https://www.rcsb.org/structure/3NFP).

**41. P01589 — Vopikitug** (`therapeutic`; all PDBs). Exact names: `Vopikitug`; `RG6292 Fab`. NCI identifies RG6292 as vopikitug; 6YIO observes its Fab and cached exact VH/VL links agree. [Evidence](https://www.cancer.gov/publications/dictionaries/cancer-drug/def/vopikitug).

**42. P01589 — BT942** (`tool`; 7f9w). Exact names: `CD25‑IL‑2 Fab`. The primary publication identifies the crystallized/cryo-EM Fab as BT942. CD25–IL-2 is an erroneous/generic source construct label, not the antibody identity; do not merge with IL-2 or BA9. [Evidence](https://doi.org/10.1038/s41598-021-02449-y).

**43. P01589 — IL-2** (`endogenous_large`; 1z92). Exact names: `P60568`. Native-sequence IL-2 cytokine in deposited entity metadata. Mutations in separate receptor subunits do not make the cytokine engineered. [Evidence](https://www.rcsb.org/structure/1Z92).

**44. P01589 — IL-2** (`endogenous_large`; 2b5i). Exact names: `P60568`. Native-sequence IL-2 cytokine in deposited entity metadata. Mutations in separate receptor subunits do not make the cytokine engineered. [Evidence](https://www.rcsb.org/structure/2B5I).

**45. P01589 — IL-2** (`endogenous_large`; 9kmc). Exact names: `P60568`. Native-sequence IL-2 cytokine in deposited entity metadata. Mutations in separate receptor subunits do not make the cytokine engineered. [Evidence](https://www.rcsb.org/structure/9KMC).

**46. P10721 — Fab19** (`tool`; all PDBs). Exact names: `19 Fab`; `Fab19`. Two distinct experimental KIT-blocking antibody clones. Consolidate explicit names, including no-PDB IEDB records, without matching shared IEDB numeric identifier 543. [Evidence](https://www.rcsb.org/structure/4K94).

**47. P10721 — Fab79D** (`tool`; all PDBs). Exact names: `79D Fab`; `Fab79D`. Two distinct experimental KIT-blocking antibody clones. Consolidate explicit names, including no-PDB IEDB records, without matching shared IEDB numeric identifier 543. [Evidence](https://www.rcsb.org/structure/4K9E).

**48. P10721 — Stem cell factor (KITLG)** (`endogenous_large`; all PDBs). Exact names: `GTOPDB:5055`; `P21583`; `stem cell factor`; `stem cell factor (KITLG)`. Native stem cell factor partner. 8DFP/8DFQ contain KIT target mutants, not engineered SCF; retain target construct provenance. [Evidence](https://www.rcsb.org/structure/2E9W).

**49. P10721 — Imatinib** (`therapeutic`; all PDBs). Exact names: `STI`. Direct kinase-domain ligand; retain all-contact evidence. These cytoplasmic contacts are excluded from EC by source compartment, not blanket exclusion. [Evidence](https://www.rcsb.org/structure/1T46).

**50. P10721 — Sunitinib** (`therapeutic`; all PDBs). Exact names: `CCD:B49`. Direct kinase-domain ligand; retain all-contact evidence. These cytoplasmic contacts are excluded from EC by source compartment, not blanket exclusion. [Evidence](https://www.rcsb.org/structure/3G0E).

**51. P10721 — Crenolanib** (`therapeutic`; all PDBs). Exact names: `CCD:6T2`. Direct kinase-domain ligand; retain all-contact evidence. These cytoplasmic contacts are excluded from EC by source compartment, not blanket exclusion. [Evidence](https://www.rcsb.org/structure/8S1A).

**52. P10721 — Pexidartinib** (`therapeutic`; all PDBs). Exact names: `CCD:P31`. Direct kinase-domain ligand; retain all-contact evidence. These cytoplasmic contacts are excluded from EC by source compartment, not blanket exclusion. [Evidence](https://www.rcsb.org/structure/7KHG).

**53. P10721 — SOCS6** (`endogenous_large`; 2vif). Exact names: `O14544`. Intracellular native signaling protein/domain bound to a KIT phosphotyrosyl peptide; preserve all-contact evidence and existing non-extracellular context. [Evidence](https://www.rcsb.org/structure/2VIF).

**54. P10721 — PIK3R1** (`endogenous_large`; 2iuh). Exact names: `P27986`. Intracellular native signaling protein/domain bound to a KIT phosphotyrosyl peptide; preserve all-contact evidence and existing non-extracellular context. [Evidence](https://www.rcsb.org/structure/2IUH).

**55. P21589 — AMPCP (adenosine 5′-methylenediphosphate)** (`tool`; all PDBs). Exact names: `AP2`; `CCD:AP2`; `CCD:A12`; `PHOSPHOMETHYLPHOSPHONIC ACID ADENOSYL ESTER`. Synthetic nonhydrolyzable nucleotide inhibitor; AP2 and A12 have identical deposited InChIKey OLCWZBFDIYXLAA-IOSLPCCCSA-N and formula. Do not call endogenous AMP/ADP. [Evidence](https://www.rcsb.org/ligand/A12).

**56. P27487 — Sitagliptin** (`therapeutic`; all PDBs). Exact names: `CCD:715`. Deposited DPP4 small-molecule inhibitor; drug identity follows primary structural publication and RCSB chemical-component drug mapping. Active moiety only, not a claim about the administered salt formulation. [Evidence](https://www.rcsb.org/structure/1X70).

**57. P27487 — Teneligliptin** (`therapeutic`; all PDBs). Exact names: `CCD:M51`. Deposited DPP4 small-molecule inhibitor; drug identity follows primary structural publication and RCSB chemical-component drug mapping. Active moiety only, not a claim about the administered salt formulation. [Evidence](https://www.rcsb.org/structure/3VJK).

**58. P27487 — Alogliptin** (`therapeutic`; all PDBs). Exact names: `CCD:T22`. Deposited DPP4 small-molecule inhibitor; drug identity follows primary structural publication and RCSB chemical-component drug mapping. Active moiety only, not a claim about the administered salt formulation. [Evidence](https://www.rcsb.org/structure/3G0B).

**59. P27487 — Linagliptin** (`therapeutic`; all PDBs). Exact names: `CCD:356`. Deposited DPP4 small-molecule inhibitor; drug identity follows primary structural publication and RCSB chemical-component drug mapping. Active moiety only, not a claim about the administered salt formulation. [Evidence](https://www.rcsb.org/structure/2RGU).

**60. P27487 — Anagliptin** (`therapeutic`; all PDBs). Exact names: `CCD:SKK`. Deposited DPP4 small-molecule inhibitor; drug identity follows primary structural publication and RCSB chemical-component drug mapping. Active moiety only, not a claim about the administered salt formulation. [Evidence](https://www.rcsb.org/structure/3WQH).

**61. P27487 — CJP indole-scaffold inhibitor** (`tool`; 4pv7). Exact names: `CCD:CJP`. Experimental indole-scaffold DPP4 inhibitor; no verified clinical drug identity. Keep distinct from approved gliptins. [Evidence](https://www.rcsb.org/structure/4PV7).

**62. P27487 — N7F heterocyclic DPP4 inhibitor** (`tool`; 4a5s). Exact names: `N7F`. Experimental heterocyclic DPP4 inhibitor from the deposited medicinal-chemistry study; no verified clinical identity. [Evidence](https://www.rcsb.org/structure/4A5S).

**63. P27487 — HIV-1 Tat(1–9) peptide** (`unclassified`; 2bgr). Exact names: `P12506`. Viral Tat-derived nonapeptide, sequence MDPVDPNIE, directly deposited. Viral/exogenous category is absent from enum; not an endogenous human ligand. [Evidence](https://www.rcsb.org/structure/2BGR).

**64. P27487 — HIV-1 Tat(1–9) Trp2 variant** (`tool`; 2bgn). Exact names: `P12506`. Engineered Tat-derived peptide MWPVDPNIE. Keep distinct from the unmodified viral peptide at 2BGR. [Evidence](https://www.rcsb.org/structure/2BGN).

**65. P27487 — Neuropeptide Y(1–10) substrate fragment** (`tool`; 1r9n). Exact names: `Q9XSW6`. Synthetic decapeptide YPSKPDNPGE (tNPY), not full endogenous NPY; accession maps rhesus NPY in SIFTS. Preserve fragment and mapping context without relabeling it as human full-length ligand. [Evidence](https://www.rcsb.org/structure/1R9N).

**66. P27487 — Bovine adenosine deaminase (2BGN construct)** (`unclassified`; 2bgn). Exact names: `P56658`. Naturally sourced bovine ADA, not an endogenous human ligand. RCSB structure page flags three sequence differences despite absent entity mutation annotation; retain a construct-qualified identity pending sequence reconciliation, as for 1W1I. [Evidence](https://www.rcsb.org/structure/2BGN).

**67. P26951 — EDTA (crystallographic chelator)** (`tool`; 5uwc). Exact names: `EDT`. CCD EDT is edetic acid/EDTA. Retain the raw contact observation as assay-reagent evidence, not a selective IL3RA therapeutic or native ligand. [Evidence](https://www.rcsb.org/ligand/EDT).

**68. P55899 — UCB-303** (`tool`; 6c99). Exact names: `EQY`. Deposited fragment/small-molecule FcRn binder UCB-303. Experimental inhibitor, not native metabolite or verified clinical drug. [Evidence](https://www.rcsb.org/structure/6C99).

**69. P55899 — Human serum albumin** (`endogenous_large`; 4n0f). Exact names: `P02768`. Native-sequence human serum albumin directly deposited; keep separate from affinity-optimized HSA variants. [Evidence](https://www.rcsb.org/structure/4N0F).

**70. P55899 — Human serum albumin** (`endogenous_large`; 4n0u). Exact names: `P02768`. Native-sequence human serum albumin directly deposited; keep separate from affinity-optimized HSA variants. [Evidence](https://www.rcsb.org/structure/4N0U).

**71. P55899 — HSAopt (V418M/T420A/E505G/V547A)** (`tool`; 4k71). Exact names: `P02768`. Affinity-optimized albumin with four substitutions (deposited numbering). 6QIP omits mutation metadata but its deposited sequence is identical to 6QIO and the primary publication explicitly uses HSAopt. Not native HSA or somapacitan. [Evidence](https://www.rcsb.org/structure/4K71).

**72. P55899 — HSAopt (V418M/T420A/E505G/V547A)** (`tool`; 6qio). Exact names: `P02768`. Affinity-optimized albumin with four substitutions (deposited numbering). 6QIP omits mutation metadata but its deposited sequence is identical to 6QIO and the primary publication explicitly uses HSAopt. Not native HSA or somapacitan. [Evidence](https://www.rcsb.org/structure/6QIO).

**73. P55899 — HSAopt (V418M/T420A/E505G/V547A)** (`tool`; 6qip). Exact names: `P02768`. Affinity-optimized albumin with four substitutions (deposited numbering). 6QIP omits mutation metadata but its deposited sequence is identical to 6QIO and the primary publication explicitly uses HSAopt. Not native HSA or somapacitan. [Evidence](https://www.rcsb.org/structure/6QIP).

**74. P55899 — IgG1 Fc YTE variant** (`tool`; 4n0u). Exact names: `P01857`. Deposited IgG1 Fc M252Y/S254T/T256E; engineered Fc-receptor ligand, not native IgG1. [Evidence](https://www.rcsb.org/structure/4N0U).

**75. P55899 — Efgartigimod** (`therapeutic`; 7q15). Exact names: `P01857`. Deposited IgG1-Fc-MST-HN is explicitly efgartigimod in the structure title and primary paper; this is direct engineered Fc-drug binding evidence, not an antibody Fab match. [Evidence](https://www.rcsb.org/structure/7Q15).

**76. P55899 — Engineered monomeric IgG4 Fc (6WNA)** (`tool`; 6wna). Exact names: `P01861`. Deposited monomeric IgG4 Fc has YTE plus L351F/S354E/T366R/P395K/F405R/Y407E substitutions. Keep distinct from 6WOL engineered Fc and native IgG4. [Evidence](https://www.rcsb.org/structure/6WNA).

**77. P55899 — Engineered monomeric IgG4 Fc (6WOL)** (`tool`; 6wol). Exact names: `P01861`. Distinct engineered Fc construct with L351F/S354E/T366R/P395K/F405R/Y407E and C-terminal substitutions/deletion; not the same sequence as 6WNA or native IgG4. [Evidence](https://www.rcsb.org/structure/6WOL).

**78. P07766 — Unresolved peptide partner (9CI8)** (`unclassified`; 9ci8). Exact names: `peptide`. Raw BioLiP record lacks partner-chain identity. Several short receptor chains exist in 9CI8; do not guess a clone or native subunit. Membrane-spanning source context already limits EC scope. [Evidence](https://www.rcsb.org/structure/9CI8).

**79. P01589 — IL-2 C125A variant** (`tool`; 2erj). Exact names: `P60568`. Deposited IL-2 entity explicitly has C125A. Not native IL-2, and not sufficient evidence for aldesleukin despite a generic deposited synonym (aldesleukin has a different sequence modification). [Evidence](https://www.rcsb.org/structure/2ERJ).

**80. P27487 — Bovine adenosine deaminase (1W1I construct)** (`unclassified`; 1w1i). Exact names: `P56658`. Naturally sourced bovine ADA, not human ADA. Entry flags three sequence differences but entity has no mutation annotation; retain a construct-qualified identity pending reference-sequence reconciliation rather than declare engineered or wild-type. [Evidence](https://www.rcsb.org/structure/1W1I).

## Complete raw-observation group audit

Rows group unchanged observations by source, raw partner, optional source label, compartment, and final proposed identity. Multiple PDBs are listed only when that complete disposition is the same. Unpromoted means the raw evidence remains available without a new named identity.

### F3 P13726

| Source | Raw partner / source label | PDB(s) | n | Compartment | Proposed disposition |
|---|---|---|---:|---|---|
| AACDB | 10H10 Fab | [4M7L](https://www.rcsb.org/structure/4M7L) | 1 | extracellular_explicit | 10H10 (tool) |
| AACDB | 5G9 Fab | [1AHW](https://www.rcsb.org/structure/1AHW) | 2 | extracellular_explicit | 5G9 (tool) |
| AACDB | D3H44 Fab | [1JPS](https://www.rcsb.org/structure/1JPS) | 1 | extracellular_explicit | D3H44 (humanized) (tool) |
| AACDB | M1587 Fab | [5W06](https://www.rcsb.org/structure/5W06) | 1 | extracellular_explicit | M1587 (tool) |
| AACDB | hATR-5 Fab | [1UJ3](https://www.rcsb.org/structure/1UJ3) | 1 | extracellular_explicit | hATR-5 (humanized) (tool) |
| IEDB | 18355 / 10H10 | [4M7L](https://www.rcsb.org/structure/4M7L) | 1 | extracellular_explicit | 10H10 (tool) |
| IEDB | 18355 / M1587 | [5W06](https://www.rcsb.org/structure/5W06) | 1 | extracellular_explicit | M1587 (tool) |
| IEDB | 916 / humanized D3h44 | [1JPS](https://www.rcsb.org/structure/1JPS) | 1 | extracellular_explicit | D3H44 (humanized) (tool) |
| IEDB | 980 / humanized anti-tissue factor hATR-5 | [1UJ3](https://www.rcsb.org/structure/1UJ3) | 1 | extracellular_explicit | hATR-5 (humanized) (tool) |
| PDB/PDBe | P01837 | [1AHW](https://www.rcsb.org/structure/1AHW) | 1 | extracellular_explicit | Unpromoted; raw evidence retained (unclassified) |
| PDB/PDBe | P01868 | [1AHW](https://www.rcsb.org/structure/1AHW) | 1 | extracellular_explicit | Unpromoted; raw evidence retained (unclassified) |
| PDB/PDBe | P08709 | [1J9C](https://www.rcsb.org/structure/1J9C), [2PUQ](https://www.rcsb.org/structure/2PUQ), [8CN9](https://www.rcsb.org/structure/8CN9), [8UUD](https://www.rcsb.org/structure/8UUD) | 4 | extracellular_explicit | Factor VIIa (endogenous_large) |
| PDB/PDBe | P08709 | [3ELA](https://www.rcsb.org/structure/3ELA) | 1 | extracellular_explicit | Factor VIIa V158D/E296V/M298Q (tool) |
| PDB/PDBe | P08709 | [4Z6A](https://www.rcsb.org/structure/4Z6A) | 1 | extracellular_explicit | Factor VIIa–trypsin YT chimera (tool) |
| PDB/PDBe | P08709 | [4ZMA](https://www.rcsb.org/structure/4ZMA) | 1 | extracellular_explicit | Factor VIIa–trypsin ST chimera (tool) |
| PDB/PDBe | P08709 | [6R2W](https://www.rcsb.org/structure/6R2W) | 1 | extracellular_explicit | Factor VIIa VYT variant (tool) |
| SAbDab | sabdab2_H004WL004M / sabdab2_H004WL004M (FAB) | [1JPS](https://www.rcsb.org/structure/1JPS) | 1 | extracellular_explicit | Unpromoted; raw evidence retained (unclassified) |

### NT5E P21589

| Source | Raw partner / source label | PDB(s) | n | Compartment | Proposed disposition |
|---|---|---|---:|---|---|
| AACDB | IPH53 Fab | [6HXW](https://www.rcsb.org/structure/6HXW) | 1 | extracellular_gpi_mature | IPH5301 (therapeutic) |
| AACDB | TB19 Fab | [6VC9](https://www.rcsb.org/structure/6VC9) | 1 | extracellular_gpi_mature | TB19 (tool) |
| AACDB | TB38 Fab | [6VCA](https://www.rcsb.org/structure/6VCA) | 4 | extracellular_gpi_mature | TB38 (tool) |
| AACDB | mAb19 Fab | [7BBJ](https://www.rcsb.org/structure/7BBJ) | 2 | extracellular_gpi_mature | mAb19 (tool) |
| BioLiP | AP2 | [6TVG](https://www.rcsb.org/structure/6TVG) | 1 | extracellular_gpi_mature | AMPCP (adenosine 5′-methylenediphosphate) (tool) |
| IEDB | 196856 / IPH5301 | [6HXW](https://www.rcsb.org/structure/6HXW) | 1 | extracellular_gpi_mature | IPH5301 (therapeutic) |
| IEDB | 197325 / TB19 | [6VC9](https://www.rcsb.org/structure/6VC9) | 1 | extracellular_gpi_mature | TB19 (tool) |
| IEDB | 197326 / TB38 | [6VCA](https://www.rcsb.org/structure/6VCA) | 1 | extracellular_gpi_mature | TB38 (tool) |
| PDBe | CCD:A12 / PHOSPHOMETHYLPHOSPHONIC ACID ADENOSYL ESTER | [4H2I](https://www.rcsb.org/structure/4H2I) | 1 | extracellular_gpi_mature | AMPCP (adenosine 5′-methylenediphosphate) (tool) |
| PDBe | CCD:AP2 / PHOSPHOMETHYLPHOSPHONIC ACID ADENOSYL ESTER | [6TVG](https://www.rcsb.org/structure/6TVG) | 1 | extracellular_gpi_mature | AMPCP (adenosine 5′-methylenediphosphate) (tool) |
| SAbDab | sabdab2_H02QFL025Z / sabdab2_H02QFL025Z (FV) | [6VC9](https://www.rcsb.org/structure/6VC9) | 1 | extracellular_gpi_mature | Unpromoted; raw evidence retained (unclassified) |

### DPP4 P27487

| Source | Raw partner / source label | PDB(s) | n | Compartment | Proposed disposition |
|---|---|---|---:|---|---|
| BioLiP | N7F | [4A5S](https://www.rcsb.org/structure/4A5S) | 1 | extracellular_explicit | N7F heterocyclic DPP4 inhibitor (tool) |
| PDB/PDBe | A0A0U1WJZ6 | [9V2P](https://www.rcsb.org/structure/9V2P) | 1 | extracellular_explicit | Unpromoted; raw evidence retained (unclassified) |
| PDB/PDBe | A0A2R4KP93 | [9JMJ](https://www.rcsb.org/structure/9JMJ), [9V2L](https://www.rcsb.org/structure/9V2L) | 2 | extracellular_explicit | Unpromoted; raw evidence retained (unclassified) |
| PDB/PDBe | A3EX94 | [4QZV](https://www.rcsb.org/structure/4QZV), [9K9N](https://www.rcsb.org/structure/9K9N) | 2 | extracellular_explicit | Unpromoted; raw evidence retained (unclassified) |
| PDB/PDBe | K0BRG7 | [4KR0](https://www.rcsb.org/structure/4KR0) | 1 | extracellular_explicit | Unpromoted; raw evidence retained (unclassified) |
| PDB/PDBe | K9N5Q8 | [22DX](https://www.rcsb.org/structure/22DX), [22DY](https://www.rcsb.org/structure/22DY), [22EA](https://www.rcsb.org/structure/22EA), [22EB](https://www.rcsb.org/structure/22EB), [8Z4T](https://www.rcsb.org/structure/8Z4T) | 5 | extracellular_explicit | Unpromoted; raw evidence retained (unclassified) |
| PDB/PDBe | P01857 | [9JMJ](https://www.rcsb.org/structure/9JMJ) | 1 | extracellular_explicit | Unpromoted; raw evidence retained (unclassified) |
| PDB/PDBe | P0DOX5 | [9JMM](https://www.rcsb.org/structure/9JMM) | 1 | extracellular_explicit | Unpromoted; raw evidence retained (unclassified) |
| PDB/PDBe | P12506 | [2BGN](https://www.rcsb.org/structure/2BGN) | 1 | extracellular_explicit | HIV-1 Tat(1–9) Trp2 variant (tool) |
| PDB/PDBe | P12506 | [2BGR](https://www.rcsb.org/structure/2BGR) | 1 | extracellular_explicit | HIV-1 Tat(1–9) peptide (unclassified) |
| PDB/PDBe | P56658 | [1W1I](https://www.rcsb.org/structure/1W1I) | 1 | extracellular_explicit | Bovine adenosine deaminase (1W1I construct) (unclassified) |
| PDB/PDBe | P56658 | [2BGN](https://www.rcsb.org/structure/2BGN) | 1 | extracellular_explicit | Bovine adenosine deaminase (2BGN construct) (unclassified) |
| PDB/PDBe | Q9XSW6 | [1R9N](https://www.rcsb.org/structure/1R9N) | 1 | extracellular_explicit | Neuropeptide Y(1–10) substrate fragment (tool) |
| PDBe | CCD:356 / 8-[(3R)-3-Aminopiperidin-1-yl]-7-but-2-yn-1-yl-3-methyl-1-[(4-methylquinazolin-2-yl)methyl]-3,7-dihydro-1H-purine-2,6-d ione | [2RGU](https://www.rcsb.org/structure/2RGU) | 1 | extracellular_explicit | Linagliptin (therapeutic) |
| PDBe | CCD:715 / (2R)-4-OXO-4-[3-(TRIFLUOROMETHYL)-5,6-DIHYDRO[1,2,4]TRIAZOLO[4,3-A]PYRAZIN-7(8H)-YL]-1-(2,4,5-TRIFLUOROPHENYL)BUTAN-2-A MINE | [1X70](https://www.rcsb.org/structure/1X70) | 1 | extracellular_explicit | Sitagliptin (therapeutic) |
| PDBe | CCD:CJP / 1-[2-(2,4-dichlorophenyl)-1-(methylsulfonyl)-1H-indol-3-yl]methanamine | [4PV7](https://www.rcsb.org/structure/4PV7) | 1 | extracellular_explicit | CJP indole-scaffold inhibitor (tool) |
| PDBe | CCD:M51 / {(2S,4S)-4-[4-(3-methyl-1-phenyl-1H-pyrazol-5-yl)piperazin-1-yl]pyrrolidin-2-yl}(1,3-thiazolidin-3-yl)methanone | [3VJK](https://www.rcsb.org/structure/3VJK) | 1 | extracellular_explicit | Teneligliptin (therapeutic) |
| PDBe | CCD:SKK / N-[2-({2-[(2S)-2-cyanopyrrolidin-1-yl]-2-oxoethyl}amino)-2-methylpropyl]-2-methylpyrazolo[1,5-a]pyrimidine-6-carboxamide | [3WQH](https://www.rcsb.org/structure/3WQH) | 1 | extracellular_explicit | Anagliptin (therapeutic) |
| PDBe | CCD:T22 / 2-({6-[(3R)-3-aminopiperidin-1-yl]-3-methyl-2,4-dioxo-3,4-dihydropyrimidin-1(2H)-yl}methyl)benzonitrile | [3G0B](https://www.rcsb.org/structure/3G0B) | 1 | extracellular_explicit | Alogliptin (therapeutic) |

### IL3RA P26951

| Source | Raw partner / source label | PDB(s) | n | Compartment | Proposed disposition |
|---|---|---|---:|---|---|
| AACDB | CSL362 Fab | [4JZJ](https://www.rcsb.org/structure/4JZJ) | 2 | extracellular_explicit | Talacotuzumab (therapeutic) |
| BioLiP | EDT | [5UWC](https://www.rcsb.org/structure/5UWC) | 1 | extracellular_explicit | EDTA (crystallographic chelator) (tool) |
| IUPHAR+PDBe | GTOPDB:4994 / IL-3 | [5UV8](https://www.rcsb.org/structure/5UV8), [6NMY](https://www.rcsb.org/structure/6NMY) | 2 | extracellular_explicit | IL-3 W13Y variant (tool) |
| IUPHAR+PDBe | GTOPDB:4994 / IL-3 | [5UWC](https://www.rcsb.org/structure/5UWC) | 1 | extracellular_explicit | IL-3 W13Y/K116W variant (tool) |
| PDB/PDBe | P08700 / IL-3 | [5UV8](https://www.rcsb.org/structure/5UV8), [6NMY](https://www.rcsb.org/structure/6NMY) | 2 | extracellular_explicit | IL-3 W13Y variant (tool) |
| PDB/PDBe | P08700 / IL-3 | [5UWC](https://www.rcsb.org/structure/5UWC) | 1 | extracellular_explicit | IL-3 W13Y/K116W variant (tool) |
| PDB/PDBe | P32927 / CSF2RB | [6NMY](https://www.rcsb.org/structure/6NMY) | 1 | extracellular_explicit | CSF2RB (6NMY engineered construct) (receptor_partner) |
| SAbDab | sabdab2_H0136L00Y9 / sabdab2_H0136L00Y9 (FAB) | [4JZJ](https://www.rcsb.org/structure/4JZJ) | 1 | extracellular_explicit | Unpromoted; raw evidence retained (unclassified) |
| Thera-SAbDab | Bexatamig | [4JZJ](https://www.rcsb.org/structure/4JZJ) | 2 | extracellular_explicit | Bexatamig (therapeutic) |
| Thera-SAbDab | Talacotuzumab | [4JZJ](https://www.rcsb.org/structure/4JZJ) | 2 | extracellular_explicit | Talacotuzumab (therapeutic) |

### FCGRT P55899

| Source | Raw partner / source label | PDB(s) | n | Compartment | Proposed disposition |
|---|---|---|---:|---|---|
| AACDB | DX-2507 Fab | [5WHK](https://www.rcsb.org/structure/5WHK) | 1 | extracellular_explicit | DX-2507 (tool) |
| AACDB | Rozanolixizumab Fab | [6FGB](https://www.rcsb.org/structure/6FGB) | 1 | extracellular_explicit | Rozanolixizumab (therapeutic) |
| BioLiP | EQY | [6C99](https://www.rcsb.org/structure/6C99) | 1 | extracellular_explicit | UCB-303 (tool) |
| PDB/PDBe | A0A0F6T703 | [7C9V](https://www.rcsb.org/structure/7C9V) | 1 | extracellular_explicit | Unpromoted; raw evidence retained (unclassified) |
| PDB/PDBe | A0A0R5YS56 | [6LA6](https://www.rcsb.org/structure/6LA6), [6LA7](https://www.rcsb.org/structure/6LA7) | 2 | extracellular_explicit | Unpromoted; raw evidence retained (unclassified) |
| PDB/PDBe | A0A1D5AKC8 | [7XXA](https://www.rcsb.org/structure/7XXA) | 1 | extracellular_explicit | Unpromoted; raw evidence retained (unclassified) |
| PDB/PDBe | A0A346I7K2 | [6LA6](https://www.rcsb.org/structure/6LA6), [6LA7](https://www.rcsb.org/structure/6LA7) | 2 | extracellular_explicit | Unpromoted; raw evidence retained (unclassified) |
| PDB/PDBe | A0A3G6VE21 | [9NAV](https://www.rcsb.org/structure/9NAV) | 1 | extracellular_explicit | Unpromoted; raw evidence retained (unclassified) |
| PDB/PDBe | A0A3G6VE58 | [9OC6](https://www.rcsb.org/structure/9OC6) | 1 | extracellular_explicit | Unpromoted; raw evidence retained (unclassified) |
| PDB/PDBe | A8BJF8 | [7C9V](https://www.rcsb.org/structure/7C9V) | 1 | extracellular_explicit | Unpromoted; raw evidence retained (unclassified) |
| PDB/PDBe | O12792 | [9DBT](https://www.rcsb.org/structure/9DBT) | 1 | extracellular_explicit | Unpromoted; raw evidence retained (unclassified) |
| PDB/PDBe | P01857 | [4N0U](https://www.rcsb.org/structure/4N0U) | 1 | extracellular_explicit | IgG1 Fc YTE variant (tool) |
| PDB/PDBe | P01857 | [7Q15](https://www.rcsb.org/structure/7Q15) | 1 | extracellular_explicit | Efgartigimod (therapeutic) |
| PDB/PDBe | P01861 | [6WNA](https://www.rcsb.org/structure/6WNA) | 1 | extracellular_explicit | Engineered monomeric IgG4 Fc (6WNA) (tool) |
| PDB/PDBe | P01861 | [6WOL](https://www.rcsb.org/structure/6WOL) | 1 | extracellular_explicit | Engineered monomeric IgG4 Fc (6WOL) (tool) |
| PDB/PDBe | P02768 | [4K71](https://www.rcsb.org/structure/4K71), [6QIO](https://www.rcsb.org/structure/6QIO), [6QIP](https://www.rcsb.org/structure/6QIP) | 3 | extracellular_explicit | HSAopt (V418M/T420A/E505G/V547A) (tool) |
| PDB/PDBe | P02768 | [4N0F](https://www.rcsb.org/structure/4N0F), [4N0U](https://www.rcsb.org/structure/4N0U) | 2 | extracellular_explicit | Human serum albumin (endogenous_large) |
| PDB/PDBe | P61769 / B2M | [1EXU](https://www.rcsb.org/structure/1EXU), [4K71](https://www.rcsb.org/structure/4K71), [4N0F](https://www.rcsb.org/structure/4N0F), [4N0U](https://www.rcsb.org/structure/4N0U), [5BJT](https://www.rcsb.org/structure/5BJT), [5BXF](https://www.rcsb.org/structure/5BXF), [5WHK](https://www.rcsb.org/structure/5WHK), [6C97](https://www.rcsb.org/structure/6C97), [6C98](https://www.rcsb.org/structure/6C98), [6C99](https://www.rcsb.org/structure/6C99), [6FGB](https://www.rcsb.org/structure/6FGB), [6ILM](https://www.rcsb.org/structure/6ILM), [6LA6](https://www.rcsb.org/structure/6LA6), [6LA7](https://www.rcsb.org/structure/6LA7), [6NHA](https://www.rcsb.org/structure/6NHA), [6QIO](https://www.rcsb.org/structure/6QIO), [6QIP](https://www.rcsb.org/structure/6QIP), [6WNA](https://www.rcsb.org/structure/6WNA), [6WOL](https://www.rcsb.org/structure/6WOL), [7B5F](https://www.rcsb.org/structure/7B5F), [7C9V](https://www.rcsb.org/structure/7C9V), [7Q15](https://www.rcsb.org/structure/7Q15), [9DBT](https://www.rcsb.org/structure/9DBT), [9MI6](https://www.rcsb.org/structure/9MI6), [9NAV](https://www.rcsb.org/structure/9NAV), [9OC6](https://www.rcsb.org/structure/9OC6), [9OC7](https://www.rcsb.org/structure/9OC7), [9TF0](https://www.rcsb.org/structure/9TF0) | 28 | extracellular_explicit | B2M (receptor_partner) |
| PDB/PDBe | Q2LJ73 | [6LA6](https://www.rcsb.org/structure/6LA6), [6LA7](https://www.rcsb.org/structure/6LA7) | 2 | extracellular_explicit | Unpromoted; raw evidence retained (unclassified) |
| PDB/PDBe | Q6NS95 | [5WHK](https://www.rcsb.org/structure/5WHK) | 1 | extracellular_explicit | DX-2507 (tool) |
| PDB/PDBe | Q82446 | [9OC7](https://www.rcsb.org/structure/9OC7) | 1 | extracellular_explicit | Unpromoted; raw evidence retained (unclassified) |
| PDB/PDBe | Q8V635 | [7B5F](https://www.rcsb.org/structure/7B5F), [9TF0](https://www.rcsb.org/structure/9TF0) | 2 | extracellular_explicit | Unpromoted; raw evidence retained (unclassified) |
| PDB/PDBe | S6BAN1 | [5WHK](https://www.rcsb.org/structure/5WHK) | 1 | extracellular_explicit | DX-2507 (tool) |
| SAbDab | sabdab2_H0251L01QH / sabdab2_H0251L01QH (FAB) | [6NHA](https://www.rcsb.org/structure/6NHA) | 1 | extracellular_explicit | Unpromoted; raw evidence retained (unclassified) |
| Thera-SAbDab | Nipocalimab | [9MI6](https://www.rcsb.org/structure/9MI6) | 1 | extracellular_explicit | Nipocalimab (therapeutic) |
| Thera-SAbDab | Orilanolimab | [6NHA](https://www.rcsb.org/structure/6NHA) | 1 | extracellular_explicit | Orilanolimab (therapeutic) |
| Thera-SAbDab | Rozanolixizumab | [6FGB](https://www.rcsb.org/structure/6FGB) | 1 | extracellular_explicit | Rozanolixizumab (therapeutic) |

### CD3E P07766

| Source | Raw partner / source label | PDB(s) | n | Compartment | Proposed disposition |
|---|---|---|---:|---|---|
| AACDB | OKT3 Fab | [1SY6](https://www.rcsb.org/structure/1SY6) | 1 | extracellular_explicit | Muromonab (OKT3) (therapeutic) |
| AACDB | UCHT1 Fv | [1XIW](https://www.rcsb.org/structure/1XIW) | 2 | extracellular_explicit | UCHT1 (tool) |
| IEDB | 3 / OKT3 | no PDB, [1SY6](https://www.rcsb.org/structure/1SY6) | 7 | extracellular_explicit | Muromonab (OKT3) (therapeutic) |
| IEDB | 991 / UCHT1 | [1XIW](https://www.rcsb.org/structure/1XIW) | 1 | extracellular_explicit | UCHT1 (tool) |
| PDB/PDBe | B7Z8B9 | [9JY4](https://www.rcsb.org/structure/9JY4) | 1 | extracellular_explicit | Unpromoted; raw evidence retained (unclassified) |
| PDB/PDBe | P01848 | [8TW4](https://www.rcsb.org/structure/8TW4) | 1 | extracellular_explicit | Unpromoted; raw evidence retained (unclassified) |
| PDB/PDBe | P01865 | [1SY6](https://www.rcsb.org/structure/1SY6) | 1 | extracellular_explicit | Unpromoted; raw evidence retained (unclassified) |
| PDB/PDBe | P04234 / CD3D | [1XIW](https://www.rcsb.org/structure/1XIW) | 1 | extracellular_explicit | CD3D (receptor_partner) |
| PDB/PDBe | P09693 / CD3G | [8TW4](https://www.rcsb.org/structure/8TW4) | 1 | extracellular_explicit | CD3G (receptor_partner) |
| PDB/PDBe | Q5XFY8 | [1SY6](https://www.rcsb.org/structure/1SY6) | 1 | extracellular_explicit | Unpromoted; raw evidence retained (unclassified) |
| SAbDab | sabdab2_H061FL04HH / sabdab2_H061FL04HH (FAB) | [9T46](https://www.rcsb.org/structure/9T46) | 1 | extracellular_explicit | Unpromoted; raw evidence retained (unclassified) |
| Thera-SAbDab | Mosunetuzumab | [9T46](https://www.rcsb.org/structure/9T46) | 1 | extracellular_explicit | Mosunetuzumab (therapeutic) |
| Thera-SAbDab | Muromonab | [1SY6](https://www.rcsb.org/structure/1SY6), [9IRS](https://www.rcsb.org/structure/9IRS) | 3 | extracellular_explicit | Muromonab (OKT3) (therapeutic) |
| BioLiP | peptide | [9CI8](https://www.rcsb.org/structure/9CI8) | 1 | membrane_spanning_site | Unresolved peptide partner (9CI8) (unclassified) |
| PDB/PDBe | A0A0B4J1U4 | [8JCB](https://www.rcsb.org/structure/8JCB), [8WXE](https://www.rcsb.org/structure/8WXE) | 2 | membrane_spanning_site | Unpromoted; raw evidence retained (unclassified) |
| PDB/PDBe | A0A0B4J271 | [6JXR](https://www.rcsb.org/structure/6JXR), [7FJD](https://www.rcsb.org/structure/7FJD), [7FJE](https://www.rcsb.org/structure/7FJE), [7FJF](https://www.rcsb.org/structure/7FJF) | 4 | membrane_spanning_site | Unpromoted; raw evidence retained (unclassified) |
| PDB/PDBe | A0A0K0K1A5 | [6JXR](https://www.rcsb.org/structure/6JXR), [7FJD](https://www.rcsb.org/structure/7FJD), [7FJE](https://www.rcsb.org/structure/7FJE), [7FJF](https://www.rcsb.org/structure/7FJF), [8TW4](https://www.rcsb.org/structure/8TW4), [8TW6](https://www.rcsb.org/structure/8TW6) | 6 | membrane_spanning_site | Unpromoted; raw evidence retained (unclassified) |
| PDB/PDBe | A0A1B0GX56 | [8JCB](https://www.rcsb.org/structure/8JCB), [8WXE](https://www.rcsb.org/structure/8WXE) | 2 | membrane_spanning_site | Unpromoted; raw evidence retained (unclassified) |
| PDB/PDBe | A0JD36 | [8JC0](https://www.rcsb.org/structure/8JC0), [8WY0](https://www.rcsb.org/structure/8WY0), [8WYI](https://www.rcsb.org/structure/8WYI), [8YC0](https://www.rcsb.org/structure/8YC0) | 4 | membrane_spanning_site | Unpromoted; raw evidence retained (unclassified) |
| PDB/PDBe | A0N4Z6 | [6JXR](https://www.rcsb.org/structure/6JXR), [7FJD](https://www.rcsb.org/structure/7FJD), [7FJE](https://www.rcsb.org/structure/7FJE), [7FJF](https://www.rcsb.org/structure/7FJF) | 4 | membrane_spanning_site | Unpromoted; raw evidence retained (unclassified) |
| PDB/PDBe | B7Z8B9 | [9JXZ](https://www.rcsb.org/structure/9JXZ), [9JY0](https://www.rcsb.org/structure/9JY0), [9JY1](https://www.rcsb.org/structure/9JY1) | 3 | membrane_spanning_site | Unpromoted; raw evidence retained (unclassified) |
| PDB/PDBe | B7Z8K6 | [8JC0](https://www.rcsb.org/structure/8JC0), [8JCB](https://www.rcsb.org/structure/8JCB), [8WXE](https://www.rcsb.org/structure/8WXE), [8WY0](https://www.rcsb.org/structure/8WY0), [8WYI](https://www.rcsb.org/structure/8WYI), [8YC0](https://www.rcsb.org/structure/8YC0), [9CI8](https://www.rcsb.org/structure/9CI8), [9CIA](https://www.rcsb.org/structure/9CIA), [9JY2](https://www.rcsb.org/structure/9JY2), [9JY3](https://www.rcsb.org/structure/9JY3) | 10 | membrane_spanning_site | Unpromoted; raw evidence retained (unclassified) |
| PDB/PDBe | P01848 | [6JXR](https://www.rcsb.org/structure/6JXR), [7FJD](https://www.rcsb.org/structure/7FJD), [7FJE](https://www.rcsb.org/structure/7FJE), [7FJF](https://www.rcsb.org/structure/7FJF), [8WYI](https://www.rcsb.org/structure/8WYI), [9BBC](https://www.rcsb.org/structure/9BBC), [9C3E](https://www.rcsb.org/structure/9C3E) | 7 | membrane_spanning_site | Unpromoted; raw evidence retained (unclassified) |
| PDB/PDBe | P01850 | [9BBC](https://www.rcsb.org/structure/9BBC) | 1 | membrane_spanning_site | Unpromoted; raw evidence retained (unclassified) |
| PDB/PDBe | P04234 / CD3D | [6JXR](https://www.rcsb.org/structure/6JXR), [7FJD](https://www.rcsb.org/structure/7FJD), [7FJE](https://www.rcsb.org/structure/7FJE), [7FJF](https://www.rcsb.org/structure/7FJF), [7PHR](https://www.rcsb.org/structure/7PHR), [8ES7](https://www.rcsb.org/structure/8ES7), [8ES8](https://www.rcsb.org/structure/8ES8), [8ES9](https://www.rcsb.org/structure/8ES9), [8JC0](https://www.rcsb.org/structure/8JC0), [8JCB](https://www.rcsb.org/structure/8JCB), [8TW4](https://www.rcsb.org/structure/8TW4), [8TW6](https://www.rcsb.org/structure/8TW6), [8WXE](https://www.rcsb.org/structure/8WXE), [8WY0](https://www.rcsb.org/structure/8WY0), [8WYI](https://www.rcsb.org/structure/8WYI), [8YC0](https://www.rcsb.org/structure/8YC0), [8ZA6](https://www.rcsb.org/structure/8ZA6), [9BBC](https://www.rcsb.org/structure/9BBC), [9C3E](https://www.rcsb.org/structure/9C3E), [9CI8](https://www.rcsb.org/structure/9CI8), [9CIA](https://www.rcsb.org/structure/9CIA), [9CQ4](https://www.rcsb.org/structure/9CQ4), [9IRS](https://www.rcsb.org/structure/9IRS), [9IRU](https://www.rcsb.org/structure/9IRU), [9JXZ](https://www.rcsb.org/structure/9JXZ), [9JY0](https://www.rcsb.org/structure/9JY0), [9JY1](https://www.rcsb.org/structure/9JY1), [9JY2](https://www.rcsb.org/structure/9JY2), [9JY3](https://www.rcsb.org/structure/9JY3), [9JY4](https://www.rcsb.org/structure/9JY4) | 30 | membrane_spanning_site | CD3D (receptor_partner) |
| PDB/PDBe | P09693 / CD3G | [6JXR](https://www.rcsb.org/structure/6JXR), [7FJD](https://www.rcsb.org/structure/7FJD), [7FJE](https://www.rcsb.org/structure/7FJE), [7FJF](https://www.rcsb.org/structure/7FJF), [7PHR](https://www.rcsb.org/structure/7PHR), [8ES7](https://www.rcsb.org/structure/8ES7), [8ES8](https://www.rcsb.org/structure/8ES8), [8ES9](https://www.rcsb.org/structure/8ES9), [8JC0](https://www.rcsb.org/structure/8JC0), [8JCB](https://www.rcsb.org/structure/8JCB), [8TW6](https://www.rcsb.org/structure/8TW6), [8WXE](https://www.rcsb.org/structure/8WXE), [8WY0](https://www.rcsb.org/structure/8WY0), [8WYI](https://www.rcsb.org/structure/8WYI), [8YC0](https://www.rcsb.org/structure/8YC0), [8ZA6](https://www.rcsb.org/structure/8ZA6), [9BBC](https://www.rcsb.org/structure/9BBC), [9C3E](https://www.rcsb.org/structure/9C3E), [9CI8](https://www.rcsb.org/structure/9CI8), [9CIA](https://www.rcsb.org/structure/9CIA), [9CQ4](https://www.rcsb.org/structure/9CQ4), [9IRS](https://www.rcsb.org/structure/9IRS), [9IRU](https://www.rcsb.org/structure/9IRU), [9JXZ](https://www.rcsb.org/structure/9JXZ), [9JY0](https://www.rcsb.org/structure/9JY0), [9JY1](https://www.rcsb.org/structure/9JY1), [9JY2](https://www.rcsb.org/structure/9JY2), [9JY3](https://www.rcsb.org/structure/9JY3), [9JY4](https://www.rcsb.org/structure/9JY4) | 29 | membrane_spanning_site | CD3G (receptor_partner) |
| PDB/PDBe | P0CF51 | [8JC0](https://www.rcsb.org/structure/8JC0), [8JCB](https://www.rcsb.org/structure/8JCB), [8WY0](https://www.rcsb.org/structure/8WY0), [8WYI](https://www.rcsb.org/structure/8WYI), [8YC0](https://www.rcsb.org/structure/8YC0), [9CI8](https://www.rcsb.org/structure/9CI8), [9CIA](https://www.rcsb.org/structure/9CIA), [9JXZ](https://www.rcsb.org/structure/9JXZ), [9JY0](https://www.rcsb.org/structure/9JY0), [9JY1](https://www.rcsb.org/structure/9JY1), [9JY2](https://www.rcsb.org/structure/9JY2), [9JY3](https://www.rcsb.org/structure/9JY3), [9JY4](https://www.rcsb.org/structure/9JY4) | 13 | membrane_spanning_site | Unpromoted; raw evidence retained (unclassified) |
| PDB/PDBe | P0DSE2 / TRB | [6JXR](https://www.rcsb.org/structure/6JXR), [7FJD](https://www.rcsb.org/structure/7FJD), [7FJE](https://www.rcsb.org/structure/7FJE), [7FJF](https://www.rcsb.org/structure/7FJF) | 4 | membrane_spanning_site | TRB (receptor_partner) |
| PDB/PDBe | P0DTU4 | [8TW4](https://www.rcsb.org/structure/8TW4), [8TW6](https://www.rcsb.org/structure/8TW6), [9C3E](https://www.rcsb.org/structure/9C3E) | 3 | membrane_spanning_site | Unpromoted; raw evidence retained (unclassified) |
| PDB/PDBe | P16333 | [5QU2](https://www.rcsb.org/structure/5QU2) | 1 | non_extracellular:cytoplasmic | NCK1 (endogenous_large) |
| PDB/PDBe | P20963 / CD247 | [6JXR](https://www.rcsb.org/structure/6JXR), [7FJD](https://www.rcsb.org/structure/7FJD), [7FJE](https://www.rcsb.org/structure/7FJE), [7FJF](https://www.rcsb.org/structure/7FJF), [7PHR](https://www.rcsb.org/structure/7PHR), [8ES7](https://www.rcsb.org/structure/8ES7), [8ES8](https://www.rcsb.org/structure/8ES8), [8ES9](https://www.rcsb.org/structure/8ES9), [8JC0](https://www.rcsb.org/structure/8JC0), [8JCB](https://www.rcsb.org/structure/8JCB), [8WXE](https://www.rcsb.org/structure/8WXE), [8WY0](https://www.rcsb.org/structure/8WY0), [8WYI](https://www.rcsb.org/structure/8WYI), [8YC0](https://www.rcsb.org/structure/8YC0), [8ZA6](https://www.rcsb.org/structure/8ZA6), [9BBC](https://www.rcsb.org/structure/9BBC), [9C3E](https://www.rcsb.org/structure/9C3E), [9CI8](https://www.rcsb.org/structure/9CI8), [9CIA](https://www.rcsb.org/structure/9CIA), [9CQ4](https://www.rcsb.org/structure/9CQ4), [9IRS](https://www.rcsb.org/structure/9IRS), [9IRU](https://www.rcsb.org/structure/9IRU), [9JXZ](https://www.rcsb.org/structure/9JXZ), [9JY0](https://www.rcsb.org/structure/9JY0), [9JY1](https://www.rcsb.org/structure/9JY1), [9JY2](https://www.rcsb.org/structure/9JY2), [9JY3](https://www.rcsb.org/structure/9JY3), [9JY4](https://www.rcsb.org/structure/9JY4) | 28 | membrane_spanning_site | CD247 (receptor_partner) |
| PDB/PDBe | P42212 | [7PHR](https://www.rcsb.org/structure/7PHR) | 1 | membrane_spanning_site | Unpromoted; raw evidence retained (unclassified) |
| PDB/PDBe | P43405 / SYK | [1A81](https://www.rcsb.org/structure/1A81) | 1 | non_extracellular:cytoplasmic | SYK (endogenous_large) |
| PDB/PDBe | Q6PJ56 | [8ZA6](https://www.rcsb.org/structure/8ZA6) | 1 | membrane_spanning_site | Unpromoted; raw evidence retained (unclassified) |
| PDB/PDBe | Q8TE68 / EPS8L1 | [2ROL](https://www.rcsb.org/structure/2ROL) | 1 | non_extracellular:cytoplasmic | EPS8L1 (endogenous_large) |
| PDB/PDBe | Q99603 | [8JC0](https://www.rcsb.org/structure/8JC0), [8WY0](https://www.rcsb.org/structure/8WY0), [8WYI](https://www.rcsb.org/structure/8WYI), [8YC0](https://www.rcsb.org/structure/8YC0), [9JXZ](https://www.rcsb.org/structure/9JXZ), [9JY0](https://www.rcsb.org/structure/9JY0), [9JY1](https://www.rcsb.org/structure/9JY1), [9JY4](https://www.rcsb.org/structure/9JY4) | 8 | membrane_spanning_site | Unpromoted; raw evidence retained (unclassified) |

### IL2RA P01589

| Source | Raw partner / source label | PDB(s) | n | Compartment | Proposed disposition |
|---|---|---|---:|---|---|
| AACDB | Basiliximab Fab | [3IU3](https://www.rcsb.org/structure/3IU3) | 3 | extracellular_explicit | Basiliximab (therapeutic) |
| AACDB | CD25‑IL‑2 Fab | [7F9W](https://www.rcsb.org/structure/7F9W) | 1 | extracellular_explicit | BT942 (tool) |
| AACDB | RG6292 Fab | [6YIO](https://www.rcsb.org/structure/6YIO) | 1 | extracellular_explicit | Vopikitug (therapeutic) |
| AACDB | daclizumab Fab | [3NFP](https://www.rcsb.org/structure/3NFP) | 2 | extracellular_explicit | Daclizumab (therapeutic) |
| IEDB | 158 / basiliximab (Simulect) | no PDB, [3IU3](https://www.rcsb.org/structure/3IU3) | 2 | extracellular_explicit | Basiliximab (therapeutic) |
| IEDB | 308 / daclizumab | no PDB, [3NFP](https://www.rcsb.org/structure/3NFP) | 2 | extracellular_explicit | Daclizumab (therapeutic) |
| PDB/PDBe | P01834 | [3IU3](https://www.rcsb.org/structure/3IU3) | 1 | extracellular_explicit | Unpromoted; raw evidence retained (unclassified) |
| PDB/PDBe | P60568 | [1Z92](https://www.rcsb.org/structure/1Z92), [2B5I](https://www.rcsb.org/structure/2B5I), [9KMC](https://www.rcsb.org/structure/9KMC) | 3 | extracellular_explicit | IL-2 (endogenous_large) |
| PDB/PDBe | P60568 | [2ERJ](https://www.rcsb.org/structure/2ERJ) | 1 | extracellular_explicit | IL-2 C125A variant (tool) |
| SAbDab | sabdab2_H02EFL01Z3 / sabdab2_H02EFL01Z3 (FAB) | [6YIO](https://www.rcsb.org/structure/6YIO) | 1 | extracellular_explicit | Unpromoted; raw evidence retained (unclassified) |
| Thera-SAbDab | Basiliximab | [3IU3](https://www.rcsb.org/structure/3IU3) | 3 | extracellular_explicit | Basiliximab (therapeutic) |
| Thera-SAbDab | Daclizumab | [3NFP](https://www.rcsb.org/structure/3NFP) | 2 | extracellular_explicit | Daclizumab (therapeutic) |
| Thera-SAbDab | Vopikitug | [6YIO](https://www.rcsb.org/structure/6YIO) | 1 | extracellular_explicit | Vopikitug (therapeutic) |

### KIT P10721

| Source | Raw partner / source label | PDB(s) | n | Compartment | Proposed disposition |
|---|---|---|---:|---|---|
| AACDB | 19 Fab | [4K94](https://www.rcsb.org/structure/4K94) | 1 | extracellular_explicit | Fab19 (tool) |
| AACDB | 79D Fab | [4K9E](https://www.rcsb.org/structure/4K9E) | 1 | extracellular_explicit | Fab79D (tool) |
| IEDB | 543 / Fab79D | no PDB, [4K9E](https://www.rcsb.org/structure/4K9E) | 4 | extracellular_explicit | Fab79D (tool) |
| IEDB | 543 / Fab19 | no PDB, [4K94](https://www.rcsb.org/structure/4K94) | 5 | extracellular_explicit | Fab19 (tool) |
| IUPHAR+PDBe | GTOPDB:5055 / stem cell factor (KITLG) | [2E9W](https://www.rcsb.org/structure/2E9W), [8DFM](https://www.rcsb.org/structure/8DFM), [8DFP](https://www.rcsb.org/structure/8DFP), [8DFQ](https://www.rcsb.org/structure/8DFQ) | 4 | extracellular_explicit | Stem cell factor (KITLG) (endogenous_large) |
| PDB/PDBe | P21583 / stem cell factor (KITLG) | [2E9W](https://www.rcsb.org/structure/2E9W), [8DFM](https://www.rcsb.org/structure/8DFM), [8DFP](https://www.rcsb.org/structure/8DFP), [8DFQ](https://www.rcsb.org/structure/8DFQ) | 4 | extracellular_explicit | Stem cell factor (KITLG) (endogenous_large) |
| SAbDab | sabdab2_H010AL00VY / sabdab2_H010AL00VY (FAB) | [4K94](https://www.rcsb.org/structure/4K94) | 1 | extracellular_explicit | Unpromoted; raw evidence retained (unclassified) |
| BioLiP | STI | [1T46](https://www.rcsb.org/structure/1T46) | 1 | non_extracellular:cytoplasmic | Imatinib (therapeutic) |
| PDB/PDBe | O14544 | [2VIF](https://www.rcsb.org/structure/2VIF) | 1 | non_extracellular:cytoplasmic | SOCS6 (endogenous_large) |
| PDB/PDBe | P27986 | [2IUH](https://www.rcsb.org/structure/2IUH) | 1 | non_extracellular:cytoplasmic | PIK3R1 (endogenous_large) |
| PDBe | CCD:6T2 / 1-(2-{5-[(3-Methyloxetan-3-yl)methoxy]-1H-benzimidazol-1-yl}quinolin-8-yl)piperidin-4-amine | [8S1A](https://www.rcsb.org/structure/8S1A) | 1 | non_extracellular:cytoplasmic | Crenolanib (therapeutic) |
| PDBe | CCD:B49 / N-[2-(diethylamino)ethyl]-5-[(Z)-(5-fluoro-2-oxo-1,2-dihydro-3H-indol-3-ylidene)methyl]-2,4-dimethyl-1H-pyrrole-3-carbo xamide | [3G0E](https://www.rcsb.org/structure/3G0E), [3G0F](https://www.rcsb.org/structure/3G0F), [8S14](https://www.rcsb.org/structure/8S14) | 3 | non_extracellular:cytoplasmic | Sunitinib (therapeutic) |
| PDBe | CCD:P31 / 5-[(5-chloro-1H-pyrrolo[2,3-b]pyridin-3-yl)methyl]-N-{[6-(trifluoromethyl)pyridin-3-yl]methyl}pyridin-2-amine | [7KHG](https://www.rcsb.org/structure/7KHG) | 1 | non_extracellular:cytoplasmic | Pexidartinib (therapeutic) |

## Evidence inventory and limits

The evidence cache includes entry metadata for all successfully fetched PDBs, focused polymer entities, unchanged antibody-arm match rows, exact sequence checks, and matcher/count results. 1W1I and 2ERJ entry REST requests failed but their public structure pages and focused polymer entity requests succeeded. Chemical REST requests failed; the RCSB ligand pages were used instead. No failed lookup was treated as biological absence. Primary metadata does not independently establish the biological relevance of every geometric contact, and full coordinates/contact extraction were not recomputed.

- [1A81](https://www.rcsb.org/structure/1A81): CRYSTAL STRUCTURE OF THE TANDEM SH2 DOMAIN OF THE SYK KINASE BOUND TO A DUALLY TYROSINE-PHOSPHORYLATED ITAM. [Primary publication](https://doi.org/10.1006/jmbi.1998.1964).
- [1AHW](https://www.rcsb.org/structure/1AHW): A COMPLEX OF EXTRACELLULAR DOMAIN OF TISSUE FACTOR WITH AN INHIBITORY FAB (5G9). [Primary publication](https://doi.org/10.1006/jmbi.1997.1512).
- [1EXU](https://www.rcsb.org/structure/1EXU): CRYSTAL STRUCTURE OF THE HUMAN MHC-RELATED FC RECEPTOR. [Primary publication](https://doi.org/10.1021/bi000749m).
- [1J9C](https://www.rcsb.org/structure/1J9C): Crystal Structure of tissue factor-factor VIIa complex. No DOI available in fetched primary-citation metadata.
- [1JPS](https://www.rcsb.org/structure/1JPS): Crystal structure of tissue factor in complex with humanized Fab D3h44. [Primary publication](https://doi.org/10.1006/jmbi.2001.5036).
- [1R9N](https://www.rcsb.org/structure/1R9N): Crystal Structure of human dipeptidyl peptidase IV in complex with a decapeptide (tNPY) at 2.3 Ang. Resolution. [Primary publication](https://doi.org/10.1110/ps.03460604).
- [1SY6](https://www.rcsb.org/structure/1SY6): Crystal Structure of CD3gammaepsilon Heterodimer in Complex with OKT3 Fab Fragment. [Primary publication](https://doi.org/10.1073/pnas.0402295101).
- [1T46](https://www.rcsb.org/structure/1T46): STRUCTURAL BASIS FOR THE AUTOINHIBITION AND STI-571 INHIBITION OF C-KIT TYROSINE KINASE. [Primary publication](https://doi.org/10.1074/jbc.M403319200).
- [1UJ3](https://www.rcsb.org/structure/1UJ3): Crystal structure of a humanized Fab fragment of anti-tissue-factor antibody in complex with tissue factor. [Primary publication](https://doi.org/10.1107/s0909049503023513).
- [1X70](https://www.rcsb.org/structure/1X70): HUMAN DIPEPTIDYL PEPTIDASE IV IN COMPLEX WITH A BETA AMINO ACID INHIBITOR. [Primary publication](https://doi.org/10.1021/jm0493156).
- [1XIW](https://www.rcsb.org/structure/1XIW): Crystal structure of human CD3-e/d dimer in complex with a UCHT1 single-chain antibody fragment. [Primary publication](https://doi.org/10.1073/pnas.0407359101).
- [1Z92](https://www.rcsb.org/structure/1Z92): structure of interleukin-2 with its alpha receptor. [Primary publication](https://doi.org/10.1126/science.1109745).
- [22DX](https://www.rcsb.org/structure/22DX): Cryo-EM structure of MERS-CoV S protein bound with receptor DPP4 in the conformation 1 (1 up RBD and 1 DPP4 bound).. No DOI available in fetched primary-citation metadata.
- [22DY](https://www.rcsb.org/structure/22DY): Local structure of MERS-CoV S protein bound with receptor DPP4 in the conformation 2 (2 up RBD and 2 DPP4 bound). No DOI available in fetched primary-citation metadata.
- [22EA](https://www.rcsb.org/structure/22EA): Cryo-EM structure of MERS-CoV S protein bound with receptor DPP4 in the conformation 3 (3 up RBD and 3 DPP4 bound).. No DOI available in fetched primary-citation metadata.
- [22EB](https://www.rcsb.org/structure/22EB): MERS-CoV RBD in complex with receptor DPP4. No DOI available in fetched primary-citation metadata.
- [2B5I](https://www.rcsb.org/structure/2B5I): cytokine receptor complex. [Primary publication](https://doi.org/10.1126/science.1117893).
- [2BGN](https://www.rcsb.org/structure/2BGN): HIV-1 Tat protein derived N-terminal nonapeptide Trp2-Tat(1-9) bound to the active site of Dipeptidyl peptidase IV (CD26). [Primary publication](https://doi.org/10.1074/JBC.M413400200).
- [2BGR](https://www.rcsb.org/structure/2BGR): Crystal structure of HIV-1 Tat derived nonapeptides Tat(1-9) bound to the active site of Dipeptidyl peptidase IV (CD26). [Primary publication](https://doi.org/10.1074/JBC.M413400200).
- [2E9W](https://www.rcsb.org/structure/2E9W): Crystal structure of the extracellular domain of Kit in complex with stem cell factor (SCF). [Primary publication](https://doi.org/10.1016/j.cell.2007.05.055).
- [2IUH](https://www.rcsb.org/structure/2IUH): Crystal structure of the PI3-kinase p85 N-terminal SH2 domain in complex with c-Kit phosphotyrosyl peptide. [Primary publication](https://doi.org/10.1038/NSB0496-364).
- [2PUQ](https://www.rcsb.org/structure/2PUQ): Crystal structure of active site inhibited coagulation factor VIIA in complex with soluble tissue factor. [Primary publication](https://doi.org/10.1042/BJ20061901).
- [2RGU](https://www.rcsb.org/structure/2RGU): Crystal structure of complex of human DPP4 and inhibitor. [Primary publication](https://doi.org/10.1021/jm701280z).
- [2ROL](https://www.rcsb.org/structure/2ROL): Structural Basis of PxxDY motif recognition in SH3 binding. [Primary publication](https://doi.org/10.1016/j.jmb.2008.07.008).
- [2VIF](https://www.rcsb.org/structure/2VIF): Crystal structure of SOCS6 SH2 domain in complex with a c-KIT phosphopeptide. [Primary publication](https://doi.org/10.1074/JBC.M110.173526).
- [3ELA](https://www.rcsb.org/structure/3ELA): Crystal structure of active site inhibited coagulation factor VIIA mutant in complex with soluble tissue factor. [Primary publication](https://doi.org/10.1074/jbc.M800841200).
- [3G0B](https://www.rcsb.org/structure/3G0B): Crystal structure of dipeptidyl peptidase IV in complex with TAK-322. [Primary publication](https://doi.org/10.1021/jm101016w).
- [3G0E](https://www.rcsb.org/structure/3G0E): KIT kinase domain in complex with sunitinib. [Primary publication](https://doi.org/10.1073/pnas.0812413106).
- [3G0F](https://www.rcsb.org/structure/3G0F): KIT kinase domain mutant D816H in complex with sunitinib. [Primary publication](https://doi.org/10.1073/pnas.0812413106).
- [3IU3](https://www.rcsb.org/structure/3IU3): Crystal structure of the Fab fragment of therapeutic antibody Basiliximab in complex with IL-2Ra (CD25) ectodomain. [Primary publication](https://doi.org/10.4049/jimmunol.0903178).
- [3NFP](https://www.rcsb.org/structure/3NFP): Crystal structure of the Fab fragment of therapeutic antibody daclizumab in complex with IL-2Ra (CD25) ectodomain. [Primary publication](https://doi.org/10.1038/cr.2010.130).
- [3VJK](https://www.rcsb.org/structure/3VJK): Crystal structure of human depiptidyl peptidase IV (DPP-4) in complex with MP-513. [Primary publication](https://doi.org/10.1016/j.bmc.2012.08.012).
- [3WQH](https://www.rcsb.org/structure/3WQH): Crystal Structure of human DPP-IV in complex with Anagliptin. [Primary publication](https://doi.org/10.3109/14756366.2014.1002402).
- [4A5S](https://www.rcsb.org/structure/4A5S): CRYSTAL STRUCTURE OF HUMAN DPP4 IN COMPLEX WITH A NOVAL HETEROCYCLIC DPP4 INHIBITOR. [Primary publication](https://doi.org/10.1016/J.BMCL.2011.11.054).
- [4H2I](https://www.rcsb.org/structure/4H2I): Human ecto-5'-nucleotidase (CD73): crystal form III (closed) in complex with AMPCP. [Primary publication](https://doi.org/10.1016/j.str.2012.10.001).
- [4JZJ](https://www.rcsb.org/structure/4JZJ): Crystal Structure of Receptor-Fab Complex. [Primary publication](https://doi.org/10.1016/j.celrep.2014.06.038).
- [4K71](https://www.rcsb.org/structure/4K71): Crystal structure of a high affinity Human Serum Albumin variant bound to the Neonatal Fc Receptor. [Primary publication](https://doi.org/10.1016/j.str.2013.08.022).
- [4K94](https://www.rcsb.org/structure/4K94): Crystal structure of KIT D4D5 fragment in complex with anti-Kit antibody Fab19. [Primary publication](https://doi.org/10.1073/pnas.1317118110).
- [4K9E](https://www.rcsb.org/structure/4K9E): Crystal structure of KIT D4D5 fragment in complex with anti-Kit antibodies Fab79D. [Primary publication](https://doi.org/10.1073/pnas.1317118110).
- [4KR0](https://www.rcsb.org/structure/4KR0): Complex structure of MERS-CoV spike RBD bound to CD26. [Primary publication](https://doi.org/10.1038/nature12328).
- [4M7L](https://www.rcsb.org/structure/4M7L): Crystal structure of the complex between human tissue factor extracellular domain and antibody 10H10 FAB fragment. No DOI available in fetched primary-citation metadata.
- [4N0F](https://www.rcsb.org/structure/4N0F): Human FcRn complexed with human serum albumin. [Primary publication](https://doi.org/10.1074/jbc.M113.537563).
- [4N0U](https://www.rcsb.org/structure/4N0U): Ternary complex between Neonatal Fc receptor, serum albumin and Fc. [Primary publication](https://doi.org/10.1074/jbc.M113.537563).
- [4PV7](https://www.rcsb.org/structure/4PV7): Cocrystal structure of dipeptidyl-peptidase 4 with an indole scaffold inhibitor. [Primary publication](https://doi.org/10.1016/j.cclet.2014.03.047).
- [4QZV](https://www.rcsb.org/structure/4QZV): Bat-derived coronavirus HKU4 uses MERS-CoV receptor human CD26 for cell entry. [Primary publication](https://doi.org/10.1016/j.chom.2014.08.009).
- [4Z6A](https://www.rcsb.org/structure/4Z6A): Crystal Structure of a FVIIa-Trypsin Chimera (YT) in Complex with Soluble Tissue Factor. [Primary publication](https://doi.org/10.1074/jbc.M115.698613).
- [4ZMA](https://www.rcsb.org/structure/4ZMA): Crystal Structure of a FVIIa-Trypsin Chimera (ST) in Complex with Soluble Tissue Factor. [Primary publication](https://doi.org/10.1074/jbc.M115.698613).
- [5BJT](https://www.rcsb.org/structure/5BJT): Crystal structure of human FcRn with a peptide inhibitor at multiple sites. [Primary publication](https://doi.org/10.1073/pnas.1618291114).
- [5BXF](https://www.rcsb.org/structure/5BXF): Apo FcRn Structure at pH 4.5. No DOI available in fetched primary-citation metadata.
- [5QU2](https://www.rcsb.org/structure/5QU2): Crystal Structure of human Nck SH3.1 in complex with peptide PPPVPNPDY. [Primary publication](https://doi.org/10.1074/jbc.RA120.012788).
- [5UV8](https://www.rcsb.org/structure/5UV8): Interleukin-3 Receptor Complex. [Primary publication](https://doi.org/10.1038/s41467-017-02633-7).
- [5UWC](https://www.rcsb.org/structure/5UWC): Cytokine-receptor complex. [Primary publication](https://doi.org/10.1038/s41467-017-02633-7).
- [5W06](https://www.rcsb.org/structure/5W06): HUMAN TISSUE FACTOR IN COMPLEX WITH ANTIBODY M1587. [Primary publication](https://doi.org/10.1080/19420862.2017.1412026).
- [5WHK](https://www.rcsb.org/structure/5WHK): Crystal structure of Fab fragment of antibody DX-2507 bound to FcRn-B2M. [Primary publication](https://doi.org/10.1074/jbc.M117.807396).
- [6C97](https://www.rcsb.org/structure/6C97): Crystal structure of FcRn at pH3. [Primary publication](https://doi.org/10.1371/journal.pbio.2006192).
- [6C98](https://www.rcsb.org/structure/6C98): Crystal structure of FcRn bound to UCB-84. [Primary publication](https://doi.org/10.1371/journal.pbio.2006192).
- [6C99](https://www.rcsb.org/structure/6C99): Crystal structure of FcRn bound to UCB-303. [Primary publication](https://doi.org/10.1371/journal.pbio.2006192).
- [6FGB](https://www.rcsb.org/structure/6FGB): Human FcRn extra-cellular domain complexed with Fab fragment of Rozanolixizumab. [Primary publication](https://doi.org/10.1080/19420862.2018.1505464).
- [6HXW](https://www.rcsb.org/structure/6HXW): structure of human CD73 in complex with antibody IPH53. [Primary publication](https://doi.org/10.1016/j.celrep.2019.04.091).
- [6ILM](https://www.rcsb.org/structure/6ILM): Cryo-EM structure of Echovirus 6 complexed with its uncoating receptor FcRn at PH 7.4. [Primary publication](https://doi.org/10.1016/j.cell.2019.04.035).
- [6JXR](https://www.rcsb.org/structure/6JXR): Structure of human T cell receptor-CD3 complex. [Primary publication](https://doi.org/10.1038/s41586-019-1537-0).
- [6LA6](https://www.rcsb.org/structure/6LA6): Cryo-EM structure of echovirus 11 complexed with its uncoating receptor FcRn at pH 7.4. [Primary publication](https://doi.org/10.1360/TB-2019-0786).
- [6LA7](https://www.rcsb.org/structure/6LA7): Cryo-EM structure of echovirus 11 complexed with its uncoating receptor FcRn at pH 5.5. [Primary publication](https://doi.org/10.1360/TB-2019-0786).
- [6NHA](https://www.rcsb.org/structure/6NHA): Crystal structure of SYNT001, a human FcRn blocking monoclonal antibody. [Primary publication](https://doi.org/10.1126/sciadv.aax9586).
- [6NMY](https://www.rcsb.org/structure/6NMY): A Cytokine-receptor complex. [Primary publication](https://doi.org/10.1158/2159-8290.CD-22-1396).
- [6QIO](https://www.rcsb.org/structure/6QIO): Ternary complex of FcRn ectodomain, FcRn binding optimised human serum albumin and the human growth hormone derivative somapacitan. [Primary publication](https://doi.org/10.1021/acs.biochem.0c00019).
- [6QIP](https://www.rcsb.org/structure/6QIP): Ternary complex of FcRn ectodomain, FcRn binding optimised human serum albumin and the albumin-biniding side chain of the human growth hormone derivative somapacitan. [Primary publication](https://doi.org/10.1021/acs.biochem.0c00019).
- [6R2W](https://www.rcsb.org/structure/6R2W): Crystal structure of the super-active FVIIa variant VYT in complex with tissue factor. [Primary publication](https://doi.org/10.1074/jbc.RA119.009183).
- [6TVG](https://www.rcsb.org/structure/6TVG): Human CD73 (ecto 5'-nucleotidase) in complex with AMPCP in the open state. [Primary publication](https://doi.org/10.1021/acs.jmedchem.9b01611).
- [6VC9](https://www.rcsb.org/structure/6VC9): TB19 complex. [Primary publication](https://doi.org/10.1074/jbc.RA120.012395).
- [6VCA](https://www.rcsb.org/structure/6VCA): TB38 complex. [Primary publication](https://doi.org/10.1074/jbc.RA120.012395).
- [6WNA](https://www.rcsb.org/structure/6WNA): Next generation monomeric IgG4 Fc. [Primary publication](https://doi.org/10.1038/s42003-021-02565-5).
- [6WOL](https://www.rcsb.org/structure/6WOL): Next generation monomeric IgG4 Fc bound to neonatal Fc receptor. [Primary publication](https://doi.org/10.1038/s42003-021-02565-5).
- [6YIO](https://www.rcsb.org/structure/6YIO): CRYSTAL STRUCTURE OF FAB RG6292 IN COMPLEX WITH CD25 ECD. [Primary publication](https://doi.org/10.1038/s43018-020-00133-0).
- [7B5F](https://www.rcsb.org/structure/7B5F): Structure of echovirus 18 in complex with neonatal Fc receptor. No DOI available in fetched primary-citation metadata.
- [7BBJ](https://www.rcsb.org/structure/7BBJ): CD73 in complex with the humanized antagonistic antibody mAb19. [Primary publication](https://doi.org/10.1158/1535-7163.MCT-21-0107).
- [7C9V](https://www.rcsb.org/structure/7C9V): E30 F-particle in complex with FcRn. [Primary publication](https://doi.org/10.1038/s41467-020-18251-9).
- [7F9W](https://www.rcsb.org/structure/7F9W): CD25 in complex with Fab. [Primary publication](https://doi.org/10.1038/s41598-021-02449-y).
- [7FJD](https://www.rcsb.org/structure/7FJD): Cryo-EM structure of a membrane protein(WT). [Primary publication](https://doi.org/10.1016/j.molcel.2022.02.017).
- [7FJE](https://www.rcsb.org/structure/7FJE): Cryo-EM structure of a membrane protein(LL). [Primary publication](https://doi.org/10.1016/j.molcel.2022.02.017).
- [7FJF](https://www.rcsb.org/structure/7FJF): Cryo-EM structure of a membrane protein(CS). [Primary publication](https://doi.org/10.1016/j.molcel.2022.02.017).
- [7KHG](https://www.rcsb.org/structure/7KHG): Crystal structure of KIT kinase domain with a small molecule inhibitor, PLX3397. [Primary publication](https://doi.org/10.1001/jamaoncol.2021.2086).
- [7PHR](https://www.rcsb.org/structure/7PHR): Structure of a fully assembled T-cell receptor engaging a tumor-associated peptide-MHC I. [Primary publication](https://doi.org/10.1016/j.cell.2022.07.010).
- [7Q15](https://www.rcsb.org/structure/7Q15): Crystal structure of FcRn and beta-2-microglobulin in complex with IgG1-Fc-MST-HN (efgartigimod). [Primary publication](https://doi.org/10.1038/s41467-022-33764-1).
- [7XXA](https://www.rcsb.org/structure/7XXA): Complex of Echo 18 and FcRn at pH7.4. [Primary publication](https://doi.org/10.1128/mbio.01166-22).
- [8CN9](https://www.rcsb.org/structure/8CN9): Factor VII binding Fab of the bispecific antibody HMB-001 in complex with Factor VII. [Primary publication](https://doi.org/10.1038/s44161-023-00418-4).
- [8DFM](https://www.rcsb.org/structure/8DFM): Ectodomain of full-length wild-type KIT-SCF dimers. [Primary publication](https://doi.org/10.1073/pnas.2300054120).
- [8DFP](https://www.rcsb.org/structure/8DFP): Ectodomain of full-length KIT(DupA502,Y503)-SCF dimers. [Primary publication](https://doi.org/10.1073/pnas.2300054120).
- [8DFQ](https://www.rcsb.org/structure/8DFQ): Ectodomain of full-length KIT(T417I,delta418-419)-SCF dimers. [Primary publication](https://doi.org/10.1073/pnas.2300054120).
- [8ES7](https://www.rcsb.org/structure/8ES7): CryoEM structure of PN45545 TCR-CD3 complex. [Primary publication](https://doi.org/10.1038/s41467-023-37532-7).
- [8ES8](https://www.rcsb.org/structure/8ES8): CryoEM structure of PN45545 TCR-CD3 in complex with HLA-A2 MAGEA4 (230-239). [Primary publication](https://doi.org/10.1038/s41467-023-37532-7).
- [8ES9](https://www.rcsb.org/structure/8ES9): CryoEM structure of PN45428 TCR-CD3 in complex with HLA-A2 MAGEA4. [Primary publication](https://doi.org/10.1038/s41467-023-37532-7).
- [8JC0](https://www.rcsb.org/structure/8JC0): V gamma9 V delta2 TCR and CD3 complex in LMNG. [Primary publication](https://doi.org/10.1038/s41586-024-07439-4).
- [8JCB](https://www.rcsb.org/structure/8JCB): Vgamma5 Vdelta1 T cell receptor complex. [Primary publication](https://doi.org/10.1038/s41586-024-07439-4).
- [8S14](https://www.rcsb.org/structure/8S14): c-KIT kinase domain in complex with sunitinib. No DOI available in fetched primary-citation metadata.
- [8S1A](https://www.rcsb.org/structure/8S1A): c-KIT kinase domain in complex with crenolanib. No DOI available in fetched primary-citation metadata.
- [8TW4](https://www.rcsb.org/structure/8TW4): TCR in nanodisc ND-I. [Primary publication](https://doi.org/10.1101/2023.08.22.554360).
- [8TW6](https://www.rcsb.org/structure/8TW6): TCR in nanodisc ND-II. [Primary publication](https://doi.org/10.1101/2023.08.22.554360).
- [8UUD](https://www.rcsb.org/structure/8UUD): BCX2627 complexed with human FVIIa and soluble Tissue Factor.. No DOI available in fetched primary-citation metadata.
- [8WXE](https://www.rcsb.org/structure/8WXE): Vgamma5Vdelta1 EH TCR-CD3 complex. [Primary publication](https://doi.org/10.1038/s41586-024-07439-4).
- [8WY0](https://www.rcsb.org/structure/8WY0): T cell receptor delta 2 gamma 9 with F283A, F290A, and F291A. [Primary publication](https://doi.org/10.1038/s41586-024-07439-4).
- [8WYI](https://www.rcsb.org/structure/8WYI): T cell receptor delta 2 gamma 9 with TCRD TM domain chimera of TRAC. [Primary publication](https://doi.org/10.1038/s41586-024-07439-4).
- [8YC0](https://www.rcsb.org/structure/8YC0): T cell receptor V delta2 V gamma9 in GDN. [Primary publication](https://doi.org/10.1038/s41586-024-07439-4).
- [8Z4T](https://www.rcsb.org/structure/8Z4T): MERS-CoV S ectodomain trimer in complex with receptor DPP4-750E. No DOI available in fetched primary-citation metadata.
- [8ZA6](https://www.rcsb.org/structure/8ZA6): Cryo-EM structure of the gdTCR-CD3 complex. [Primary publication](https://doi.org/10.1016/j.immuni.2025.04.012).
- [9BBC](https://www.rcsb.org/structure/9BBC): TCR GDN detergent micelle. [Primary publication](https://doi.org/10.1038/s41467-025-66939-7).
- [9C3E](https://www.rcsb.org/structure/9C3E): TCR - CD3 complex bound to HLA. [Primary publication](https://doi.org/10.1038/s41467-025-66939-7).
- [9CI8](https://www.rcsb.org/structure/9CI8): T cell receptor complex. [Primary publication](https://doi.org/10.1038/s41586-024-07920-0).
- [9CIA](https://www.rcsb.org/structure/9CIA): T cell receptor complex. [Primary publication](https://doi.org/10.1038/s41586-024-07920-0).
- [9CQ4](https://www.rcsb.org/structure/9CQ4): G115 gamma delta TCR/CD3 complex bound by OKT3 Fab. [Primary publication](https://doi.org/10.1038/s41467-024-55467-5).
- [9DBT](https://www.rcsb.org/structure/9DBT): Crystal structure of human astrovirus 1 capsid spike bound to human neonatal Fc receptor. [Primary publication](https://doi.org/10.1038/s41467-025-65203-2).
- [9IRS](https://www.rcsb.org/structure/9IRS): Cryo-EM structure of the TCR-OKT3 complex. No DOI available in fetched primary-citation metadata.
- [9IRU](https://www.rcsb.org/structure/9IRU): Cryo-em structure of TCR-4B1 complex. No DOI available in fetched primary-citation metadata.
- [9JMJ](https://www.rcsb.org/structure/9JMJ): Cryo-EM structure of the GD-BatCoV (BtCoV/Ii/GD/2014-422) RBD in complex with human DPP4. [Primary publication](https://doi.org/10.1126/sciadv.adv7296).
- [9JMM](https://www.rcsb.org/structure/9JMM): Cryo-EM structure of the SE-PangolinCoV (MjHKU4r-CoV-1) RBD in complex with human DPP4. [Primary publication](https://doi.org/10.1126/sciadv.adv7296).
- [9JXZ](https://www.rcsb.org/structure/9JXZ): V gamma9 V delta2 TCR and CD3 complex. No DOI available in fetched primary-citation metadata.
- [9JY0](https://www.rcsb.org/structure/9JY0): Fab-CD3-gamma epsilon-TCR complex. No DOI available in fetched primary-citation metadata.
- [9JY1](https://www.rcsb.org/structure/9JY1): delta epsilon/delta epsilon Fab-TCR tetramer. No DOI available in fetched primary-citation metadata.
- [9JY2](https://www.rcsb.org/structure/9JY2): Fab-CD3-delta epsilon-TCR complex. No DOI available in fetched primary-citation metadata.
- [9JY3](https://www.rcsb.org/structure/9JY3): delta epsilon/gamma epsilon Fab-TCR tetramer. No DOI available in fetched primary-citation metadata.
- [9JY4](https://www.rcsb.org/structure/9JY4): gamma epsilon/gamma epsilon Fab-TCR tetramer. No DOI available in fetched primary-citation metadata.
- [9K9N](https://www.rcsb.org/structure/9K9N): Cryo-EM structure of MjHKU4r-CoV-1 receptor-binding domain complexed with human CD26. [Primary publication](https://doi.org/10.1016/j.hlife.2025.05.005).
- [9KMC](https://www.rcsb.org/structure/9KMC): Cryo-EM structure of the heterotrimeric interleukin-2 receptor in complex with interleukin-2 and anti-CD25 Fab S417. [Primary publication](https://doi.org/10.1038/s41467-025-67745-x).
- [9MI6](https://www.rcsb.org/structure/9MI6): Crystal structure of human FcRn in complex with nipocalimab Fab fragment. [Primary publication](https://doi.org/10.1080/19420862.2025.2461191).
- [9NAV](https://www.rcsb.org/structure/9NAV): CryoEM structure of human astrovirus 1 spike in complex with human neonatal Fc receptor. No DOI available in fetched primary-citation metadata.
- [9OC6](https://www.rcsb.org/structure/9OC6): Crystal structure of receptor FcRn bound to Human Astrovirus 6 spike. [Primary publication](https://doi.org/10.1016/j.celrep.2025.116679).
- [9OC7](https://www.rcsb.org/structure/9OC7): Crystal structure of FcRn in complex with Human Astrovirus 2 spike. [Primary publication](https://doi.org/10.1016/j.celrep.2025.116679).
- [9T46](https://www.rcsb.org/structure/9T46): Crystal structure of the Fab 40G5c in complex with a CD3 epsilon peptide. [Primary publication](https://doi.org/10.1080/19420862.2026.2658902).
- [9TF0](https://www.rcsb.org/structure/9TF0): Structure of echovirus 18 in complex with neonatal Fc receptor. [Primary publication](https://doi.org/10.1073/pnas.2601182123).
- [9V2L](https://www.rcsb.org/structure/9V2L): Complex structure of 2014-422 spike RBD bound to human DPP4. No DOI available in fetched primary-citation metadata.
- [9V2P](https://www.rcsb.org/structure/9V2P): Complex structure of GX2012 spike RBD bound to human DPP4. No DOI available in fetched primary-citation metadata.
