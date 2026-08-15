# Extracellular tag-site positive controls

Ground truth for the tag-site benchmark. Machine-readable source is
`positive_controls.tsv` (23 published-success rows + A24 asserted). Verify residue
positions against UniProt with:

```bash
uv run python scripts/verify_tag_site_positive_controls.py
```

**Provenance.** This set was curated by Becca Carlson (Deliverome) and shared 2026-07-26.
It is the authoritative ground truth for this repo's tag-site work; the deterministic
and literature pipelines are benchmarked *against* it, never the other way around.

**Human only.** Non-human sites were deliberately excluded — cross-species tolerance does
not transfer cleanly.

**Junction convention.** `after N` means the tag sits between residue `N` and `N+1` in
UniProt canonical numbering. Source papers use inconsistent conventions; all are
normalized here, and every position with a stated residue has been checked against the
UniProt sequence mechanically.

**Replacements are marked.** Several constructs delete native residues rather than purely
inserting. Where that happens the deleted span is named explicitly.

This set contains **only published successes (23 rows, one tier)**. Topology-derived
candidates with no experimental backing were removed, as were negative controls
(published failures) and distractors — see the caveats section for what existed and
where the sources are if any of those categories are wanted back later.

---

## Published successes

### Terminal-extracellular sites

| # | Protein | Accession | Site | Signal peptide | Tag | Impact measured vs untagged | Source |
|---|---|---|---|---|---|---|---|
| A1 | **SELE** | P16581 | after **A21** | native SP retained, tag downstream | HiBiT (11) + GSSG | **Yes** — TNFα EC50 0.06 ± 0.01 nM edited vs 0.016 ± 0.003 nM untagged (different assay formats, so not cleanly attributable) | Ogrodzinski 2023 |
| A2 | **ADRB2** | P07550 | before **residue 1** | none native; tested **± added IL6 leader** | HiBiT (11) + VS + 2×GSSG | **Yes — no difference** between clones with and without the added leader, by binding and CRE signaling | Boursier 2020 |
| A3 | **CALCR** | P30988 | after **P24** | native SP (2–24) **replaced** by HA SP | FLAG (8) + 3C | **Yes — no change**: ¹²⁵I-sCT(8-32) binding and cAMP, n=4. *"The presence of purification tags does not alter receptor pharmacology."* | Liang 2017 |
| A4 | **GIPR** | P48546 | after **Q21** | HA SP replaces native | FLAG (8) | **Yes** — GIP pEC50 10.8 ± 0.35 (tagged) vs **8.6 ± 0.19 for the untagged control**, P<0.01; cassette *required* to detect arrestin recruitment | Al-Sabah 2020 |
| A5 | **GLP1R** | P43220 | after **P23** | native SP retained, tag downstream | VSV-G (11) | **Yes** — 100 ± 0.58% surface detection; cAMP 99.57 ± 0.43% | Thompson 2014 |
| A6 | **CD46** | P15529 | after **A34** | native SP retained, tag downstream | HiBiT (11) + GGG | NOT MEASURED | Kim 2023 |
| A7 | **NPY1R** | P25929 | after **M1** (M1 deleted) | none — NPY1R has no SP | FLAG (8) | NOT MEASURED vs untagged; tag shown surface-accessible by anti-FLAG ELISA on non-permeabilized cells | Park 2022 |
| A8 | **ADORA1** | P30542 | before **residue 1**, Met1→Leu | none added | HiBiT (11) + GSSGGSSG | Partial — NanoBRET pK_D 7.17 ± 0.03; DPCPX pK_B 8.28 ± 0.12 matches reference | Various |
| A24 | **TFRC** | P02786 | **C-terminus**, residue 760 | none — TFRC is type II, C-terminus is the ectodomain end | short epitope | **Kept per direct instruction as experimentally supported; the specific citation is not yet in hand.** | *pending citation* |

**A1 and A2 are the strongest terminal rows** — both are endogenous CRISPR knock-ins with
quantified function. A3–A5 are recombinant but carry explicit tagged-vs-untagged
pharmacology. A6–A8 lack a functional comparison. **A24 is asserted, not sourced** — see
the caveat below the internal-sites table.

### Internal sites

| # | Protein | Accession | Site | Structural context | Tag | Impact measured vs untagged | Source |
|---|---|---|---|---|---|---|---|
| A9 | **ITGB1** | P05556 | after **G101** | hybrid domain, exposed βX–βA loop (92–114) | ALFA (15), GS both sides | Retains 12G10 activation / Mab13 inhibition, n=12 | EndoNB |
| A10 | ITGB1 | P05556 | after **G101** | same loop | eGFP (239) | Rescues collagen + fibronectin adhesion indistinguishably from untagged; restores FN9-10 binding and surface α5; normal activation index | Huet-Calderwood 2017 |
| A11 | ITGB1 | P05556 | after **G101** | same loop | pHluorin (238) | Full panel as A10; pH-sensing retained | Huet-Calderwood 2017 |
| A12 | ITGB1 | P05556 | after **G101** | same loop | HaloTag (297) | Full panel as A10; labelled by **cell-impermeant** ligand — direct proof of extracellular display | Huet-Calderwood 2017 |
| A13 | **ITGB5** | P18084 | after **A102** | hybrid/β-I loop, ITGB1-equivalent | ALFA (15) | Colocalizes with anti-αVβ5 (15F11); ECM-dependent uptake matches published behaviour, n=10 | EndoNB |
| A14 | **TFRC** | P02786 | after **I290** | ectodomain surface loop | ALFA (15), **no linkers** | Transferrin uptake retained and ligand-independent, n=4 | EndoNB |
| A15 | **AXL** | P30530 | after **P184** | extracellular inter-domain linker | ALFA (15) | GAS6-driven internalization retained, plateau 15 min, n=4 | EndoNB |
| A16 | **TMEM123** | Q8N131 | after **A33** | unstructured ectodomain, 7 aa past SP cleavage | ALFA (15) | Endocytosis within 15 min; transferrin-endosome colocalization, n=23 cells | EndoNB |
| A17 | **TRPC5** | Q9UL62 | after **Y460** | S3–S4 loop, distal from pore | DogTag (23), G4S both sides | **Yes** — functional channels, normal englerin-A Ca²⁺ influx side-by-side with untagged; labelling itself neutral | Keeble 2022 |
| A18 | **SLC6A4** (hSERT) | P31645 | after **N211**, **replaces 212–215 (YFSE)** | EL2, between the two glycan sequons N208/N217 | HA+SL (11) | **Yes** — Vmax 55.0 ± 7.0% of WT; Km comparable (0.82 vs 0.57 µM) | Rahbek-Clemmensen 2014 |
| A19 | **SLC6A3** (hDAT) | Q01959 | after **A192**, **replaces 193–203 (HPGDSSGDSSG)** — isometric | EL2, between glycans N188/N205 | HA+SL (11) | **Yes — no change**: Km ~3 µM, Vmax ~20 pmol/min/well | Sorkina 2006 |
| A20 | **EDNRB** | P24530 | after **G57**, **replaces 58–65 (SNASLARS)** — isometric | extracellular domain | FLAG (8) | NOT MEASURED; 2.80 Å cryo-EM structure obtained | Sano 2023 |
| A21 | **KCNH2** (hERG) | Q12809 | after **T436** | S1–S2 extracellular loop | BBS (13) | NOT MEASURED — authors state so explicitly | Kanner 2018 |
| A22 | **SLC26A1** | Q9H2B4 | after **P155** | extracellular loop | HA (9) | NOT MEASURED | — |
| A23 | **SLC9A6** (NHE6) | Q92581 | after **M53** | first exofacial loop | 3×FLAG (32) | Asserted by reference to prior work, NOT MEASURED here | — |

### A24 (TFRC C-terminus) — kept on direct instruction, citation still needed

My own search did not find a published tag at TFRC's C-terminus (residue 760, the
ectodomain end — TFRC is type II, so this is the opposite terminus from the usual
cytoplasmic N-terminal GFP-TfR construct, which the literature places at the N-terminus
specifically to avoid interfering with C-terminal ligand binding). You've told me directly
that this is experimentally supported and verifiable. I've kept the row rather than
argue with that, but I have not located the paper myself, so **the citation is a known
gap, not a resolved one** — replace `*pending citation*` in the table above with the real
source, and I'll re-verify the residue number against it once you have it in hand.

---

## Design heuristics stated in the source papers

Ranked by evidence strength. Only rules a paper actually states.

1. **The tag must sit downstream of the signal-peptidase cleavage site.** Stated by GIPR
   (*"in order to N-terminally label the receptors, a FLAG-tag was introduced immediately
   downstream of the predicted signal peptide"*) and CD46. The consequence of getting this
   wrong is a **silent failure** — a construct upstream of the cleavage site can traffic and
   signal normally while surface tag detection drops to zero, because the signal peptide
   is cleaved and takes the tag with it. This is documented in the Thompson 2014 GLP1R
   paper (A5's source), which built both orientations side by side.
2. **Expect ±1 residue disagreement between paper and UniProt on where the SP ends.**
   Store both numbers.
3. **A heterologous HA signal peptide is about expression yield, not correctness.** Several
   GPCR papers add one *"to increase the expression yield"*, but A2 (ADRB2, ± IL6 leader)
   and A7 (NPY1R, none) show it is not required. GIPR is the one case where the cassette
   measurably rescued a failing assay.
4. **Linker length is not critical at an extracellular N-terminus.** Observed practice
   spans none at all through a 16-aa linker; all worked. CD46 is the only paper to justify
   its choice — `GGG` because it resists chymotrypsin, factor Xa, thrombin and trypsin.
5. **For internal sites in glycosylated loops, place the tag between the two N-glycan
   sequons and do not destroy them.** hSERT (A18) and hDAT (A19) both do this. EDNRB
   (A20) is a **counterexample**: its FLAG ablates the N59 sequon and still gave a 2.8 Å
   structure, so the rule is a strong prior, not an absolute requirement.
6. **Bigger loop ≠ safer loop.** TRPC5 chose the 22-aa S3–S4 loop over the 68-aa S5–S6
   turret because *"antibodies generated against TRPC5's longer third extracellular loop
   inhibit TRPC5 function."*
7. **Isometric replacement is a recurring trick.** hDAT swaps 11 native Gly/Ser residues
   for an 11-aa tag; EDNRB swaps 8 for 8. Keeps loop geometry constant.
8. **Always validate on non-permeabilized cells.** Every case here did.

---

## Cross-tag reference: SpyTag in loops (not scored)

**Not benchmark rows** — none are human cell-surface proteins. Recorded because they bear
on cassette choice for this project.

| System | Site | SpyTag / SpyTag003 | DogTag, same site | Source |
|---|---|---|---|---|
| sfGFP | loop A, V22/N23 | k₂ = 87 ± 8 M⁻¹s⁻¹ — **~6,000× slower than terminal SpyTag003** | 1.0 ± 0.08 × 10³ | Keeble 2022 |
| Gre2p | loop B, E229/D230 | 156 ± 14 M⁻¹s⁻¹ | 850 ± 12 | Keeble 2022 |
| HaloTag7 | 139/140 | **no soluble expression** | reacted normally | Keeble 2022 |
| HBcAg capsid | spike tip, P79–A80 | **aggregation; capsids failed to assemble** | assembled, ~100% coupling | Raupach 2025 |
| Ad5 hexon | HVR1/2/5 | poorly reactive despite 7× more SpyCatcher | full coverage | Dicks 2022 |
| Ad5 fiber | HI loop | <50% conjugation | near-complete | Rice-Boucher 2025 |
| Mi3 cage | **C-terminus** | worked | — | Ma 2024 |
| IMX313 | **N-terminus** | worked | — | Sun 2026 |

Loop-specific, not a general SpyTag problem. SpyTag is a β-strand that must complete a
β-sheet in SpyCatcher and cannot while tethered at both ends; DogTag's β-hairpin was
engineered to solve exactly this. In TRPC5 (A17) DogTag was **250× faster than SpyTag003**
when loop-inserted, while being *slower* at a terminus. (Primary source: Keeble 2022,
Cell Chem Biol, DOI 10.1016/j.chembiol.2021.07.005, PMID 34324879 — the abstract states
DogTag "inserted in loops … reacts much faster than SpyTag003", terminal the reverse.)

**Why this matters here.** The pipeline assigns the `SPY003_ALFA` cassette to **internal**
sites. Fine for terminal sites. For internal loops the evidence predicts the SpyTag003 arm
conjugates poorly — the ALFA arm is unaffected, being an α-helical nanobody epitope with no
folding requirement and exactly what EndoNB validated internally. So an internal
`SPY003_ALFA` site is likely **ALFA-detection-only in practice**, and DogTag is the
loop-appropriate covalent arm. This is encoded in `tag_sites/surface_loop.py::tag_fit`
(internal loops → `ALFA, DogTag`; SpyTag003 reserved for termini). Literature-based
prediction, not measured in-house.

## Tag sequences

| Tag | Length | Sequence |
|---|---:|---|
| ALFA | 15 aa | `PSRLEEELRRRLTEP` |
| ALFA as installed by EndoNB | 19 aa | `GS` + ALFA + `GS` (TFRC: no linkers) |
| DogTag | 23 aa | `DIPATYEFTDGKHYITNEPIPPK` |
| SpyTag003 | 16 aa | `RGVPHIVMVDAYKRYK` |
| SpyTag (original) | 13 aa | `AHIVMVDAYKPTK` |
| FLAG | 8 aa | `DYKDDDDK` |
| HA | 9 aa | `YPYDVPDYA` |
| HiBiT | 11 aa | `VSGWRLFKKIS` |
| BBS | 13 aa | `WRYYESSLEPYPD` |
| 6E | 14 aa | `QADQEAKELARQIS` |

## Sources

| Key | Citation |
|---|---|
| `endonb` | Lenaerts A-S, et al. **EndoNB: A general strategy to study the internalization of cell surface proteins.** bioRxiv, 8 Jun 2025. DOI [10.1101/2025.06.08.658482](https://doi.org/10.1101/2025.06.08.658482). *Preprint.* |
| `huet2017` | Huet-Calderwood C, et al. **Novel ecto-tagged integrins reveal their trafficking in live cells.** Nat Commun 2017;8:570. DOI [10.1038/s41467-017-00646-w](https://doi.org/10.1038/s41467-017-00646-w). PMC5603536. |
| `keeble2022` | Keeble AH, et al. **DogCatcher allows loop-friendly protein-protein ligation.** Cell Chem Biol 2022;29(2):339–350.e10. DOI [10.1016/j.chembiol.2021.07.005](https://doi.org/10.1016/j.chembiol.2021.07.005). PMC8878318. |
| `park2022` | Park C, et al. **Structural basis of neuropeptide Y signaling through Y1 receptor.** Nat Commun 2022;13:853. DOI [10.1038/s41467-022-28510-6](https://doi.org/10.1038/s41467-022-28510-6). PMC8844075. PDB 7VGX. |
| `liang2017` | Liang Y-L, et al. **Phase-plate cryo-EM structure of a class B GPCR–G-protein complex.** Nature 2017;546:118–123. DOI [10.1038/nature22327](https://doi.org/10.1038/nature22327). PMC5832441. |
| `alsabah2020` | Al-Sabah S, Adi L, Bünemann M, Krasel C. **Fluorescent labelling of the GIP receptor.** Front Pharmacol 2020;11:1271. DOI [10.3389/fphar.2020.01271](https://doi.org/10.3389/fphar.2020.01271). PMC7438548. |
| `thompson2014` | Thompson A, Kanamarlapudi V. **Distinct regions in the C-terminus required for GLP-1R cell surface expression.** Sci Rep 2014;4:7410. DOI [10.1038/srep07410](https://doi.org/10.1038/srep07410). PMC4344312. |
| `ogrodzinski2023` | Ogrodzinski MP, et al. **Measuring endogenous E-selectin with a HiBiT knock-in.** iScience 2023;26:107232. DOI [10.1016/j.isci.2023.107232](https://doi.org/10.1016/j.isci.2023.107232). PMC10366498. |
| `rahbek2014` | Rahbek-Clemmensen T, et al. *J Biol Chem* 2014;289:23004–23019. DOI [10.1074/jbc.M113.495754](https://doi.org/10.1074/jbc.M113.495754). PMC4132800. |
| `sorkina2006` | Sorkina T, et al. *J Neurosci* 2006;26:8195–8205. DOI [10.1523/JNEUROSCI.1301-06.2006](https://doi.org/10.1523/JNEUROSCI.1301-06.2006). PMC6673793. |
| `sano2023` | Sano FK, et al. *eLife* 2023;12:e85821. DOI [10.7554/eLife.85821](https://doi.org/10.7554/eLife.85821). PMC10129325. |
| `boursier2020` | Boursier ME, et al. *J Biol Chem* 2020;295:5124–5135. DOI [10.1074/jbc.RA119.011952](https://doi.org/10.1074/jbc.RA119.011952). PMC7152755. |
| `kanner2018` | Kanner SA, et al. *Front Physiol* 2018;9:397. DOI [10.3389/fphys.2018.00397](https://doi.org/10.3389/fphys.2018.00397). PMC5917007. |
| `kim2023` | Kim (CD46 HiBiT) 2023 — see A6. |
| *pending* | TFRC C-terminal tag (row A24) — citation not yet identified. |

## Curation caveats

- **Every stated residue position except A24 was verified against the UniProt sequence.**
  Verification run: 29 passed / 4 skipped / 0 failed on this set; skips are the rows with
  no declared position (A24 among them, since it names a terminus rather than a checkable
  junction), plus TRPC5 and KCNH2, which sit outside the surfaceome reference set and were
  checked directly against UniProt instead (Q9UL62 Y460/N461, Q12809 T436/E437).
- **A24 (TFRC C-terminus) has no citation yet** — kept on direct instruction, see the note
  under the internal-sites table. Treat it as asserted, not verified, until a source is
  attached.
- **A7 (NPY1R)** is a recombinant insect-cell construct, not a knock-in, with no
  tagged-vs-untagged comparison. Well pinned on architecture, weak on functional impact.
- **EndoNB residue labels are inconsistent** — four entries name the residue before the
  junction, TFRC names the one after. Normalized here.
- **EndoNB reports no failures**; they screened 2–3 gRNAs per gene and published only the
  winner, so its 5/5 success rate is survivorship-filtered.
- **Huet-Calderwood write "Gly101 and Tyr102"** but P05556 residue 102 is **threonine**, as
  their own Fig. 1c and primer table show. Recorded as Gly101/Thr102.
- **Excluded on the human-only rule:** rat PTH1R multi-ECL epitope map (PMID 9794466, the
  best GPCR loop-insertion screen anywhere), mouse Slc11a2/DMT1 13-site HA screen
  (PMC2736113, 5/13 sites killed transport), rat NKCC2, and the canonical HA-GLUT4 /
  GLUT4-myc reagents (rat; no human version found).
- **Removed by request, twice.** Two categories existed in earlier versions of this
  document and were removed:
  - Topology-derived candidates with no experimental backing (ITGB1 after residue 20,
    ITGB5 after residue 24, AXL after residue 32, TMEM123 after residue 26 — all N-termini
    inferred from DeepTMHMM topology, not from any publication). TFRC's C-terminus was in
    this same category before being kept per direct instruction as A24.
  - Published failures and one pipeline distractor (GLP1R tag-upstream-of-SP, ITGB1 +
    SNAP-tag, CFTR HA-vs-FLAG at ECL4, hSERT/hDAT other-site failures, and NPY1R's ECL3
    site down-ranked on loop-capacity and Spy-chemistry grounds). If negative scoring is
    wanted later, re-derive from those sources rather than starting over.

## Known gaps — searched and empty, not unsearched

- **No verified human ALFA tag at an extracellular terminus.** Götzke 2019 has no
  knock-in and no non-permeabilized surface staining; its only membrane construct is an
  artificial reporter. Do not enter an ALFA surface-terminal case on current evidence.
- **No verified human case for AviTag/BAP, StrepII, Myc, tetracysteine, or GFP11** at a
  terminal extracellular position with residue-level methods.
- **No human GPCR extracellular-*loop* short-tag case.** GPCR tagging is overwhelmingly
  terminal; EDNRB (A20) is the closest.
- **No human RTK, cadherin, GPI-anchored, or immune-checkpoint case** cleared the bar. An
  EGFR HiBiT knock-in at residues 24/25 exists but only as vendor documentation with no
  DOI or PMCID, so it was not entered.
