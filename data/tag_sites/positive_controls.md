# Extracellular tag-site positive controls

Ground truth for the tag-site benchmark. Machine-readable source is
`positive_controls.tsv` (23 published-success rows + A24 asserted; plus batch-2
rows B1–B13, see "Extended set — batch 2" below). Verify residue
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

---

## Extended set — batch 2 (10 proteins, 13 rows: B1–B13)

Added 2026-08-15 from a second curated batch (multi-pass channels/transporters +
short-loop cases). Machine-readable rows are in `positive_controls.tsv` (ids `B*`).
**Every stated residue was checked against the UniProt canonical sequence** with
`scripts/verify_tag_site_positive_controls.py`-style verification — results below.

| # | Protein | Accession | Site | Tag | Residue check | Source |
|---|---|---|---|---|---|---|
| B1 | SLC5A6 / SMVT | Q9Y289 | replace **484–516** (EL3) | ALFA | span present (len 635) | Nat Commun 2026 |
| B2 | AQP1 | P29972 | after **T120** | Myc | ✅ 120=T, 121=G | PMC2157255 |
| B3 | SLC19A1 / RFC | P41440 | after **P297** | HA | ✅ 297=P | PubMed 10347183 |
| B4 | PMP22 | Q01453 | after **H125** | Myc | ✅ 125=H, 126=L | PMC13382790 |
| B5 | VANGL1 | Q8TAA9 | after **R139** | HA | ✅ 139=R (no letter stated) | PubMed 21291170 |
| B6 | VANGL1 | Q8TAA9 | after **D213** | HA | ✅ 213=D (no letter stated) | PubMed 21291170 |
| B7 | SLC4A1 / kAE1 | P02730 | after **V557** (anchor) | HA/Myc | ✅ 557=V; numbering varies across papers | PMC3468346 |
| B8 | KCNQ1 | P51787 | after **E146** | Myc | ✅ 146=E, 147=Q | PMC5842040 |
| B9 | KCNQ1 | P51787 | after **E146** | HA | ✅ same site, HA (portability) | PMC10642763 |
| B10 | ASIC1a | P78348 | after **F147** | HA/FLAG | ✅ 147=F, 148=K | *citation pending* |
| B11 | ASIC1a | P78348 | after **D298** | HA | ✅ 298=D, 299=L | *citation pending* |
| B12 | CFTR | P13569 | after **N901** | 3×HA | ✅ 901=N | PMC3266683 |
| B13 | **ANO1** / TMEM16A | Q5XXA6 | after **H396** | 3×HA | ❌ **MISMATCH** — Q5XXA6 396=**A**, 397=**T** | PMC7291285 |

**Batch-2 verification caveats:**
- **B13 (ANO1) is UNVERIFIED against the canonical sequence.** The cited site H396/N397
  does not match Q5XXA6 (which has Ala396/Thr397) — almost certainly TMEM16A **isoform
  numbering** (the a/b/c/d N-terminal splice variants shift the register). Reconcile against
  the exact isoform the source used before treating this as ground truth; the row is kept but
  flagged `UNVERIFIED` in the TSV, the same way A24 (TFRC C-term) is kept-but-asserted.
- **B10/B11 (ASIC1a)** have no citation in hand yet (`source_key` blank) — residues verify
  against P78348, but attach the source before use. B10 electrophysiology is not fully neutral;
  B11 function is reduced (`function_perturbed`).
- **B1 (SLC5A6)** is a **replacement** (EL3 484–516 → ALFA), not a pure insertion; surface
  display + cryo-EM structures obtained, biotin transport retained but Vmax ~3× lower.

### Batch-2 sources

| Key | Citation |
|---|---|
| `smvt_natcommun2026` | Structural basis for multivitamin recognition and transport by human SMVT. *Nat Commun* 2026. |
| `aqp1_pmc2157255` | Long-range non-anomalous diffusion of Qdot-labeled Aquaporin-1 water channels. PMC2157255. |
| `rfc_pubmed10347183` | Topological and functional analysis of the human reduced folate carrier by HA epitope insertion. PubMed 10347183. |
| `pmp22_pmc13382790` | Stable and tunable expression of human PMP22 in rat Schwann cells. PMC13382790. |
| `vangl1_pubmed21291170` | Transmembrane topology of mammalian planar cell polarity protein Vangl1. PubMed 21291170. |
| `slc4a1_pmc3468346` | AP-1 complexes regulate intracellular trafficking of kidney anion exchanger 1. PMC3468346. |
| `kcnq1_pmc5842040` | Mechanisms of KCNQ1 dysfunction in long-QT (extracellular Myc-KCNQ1 surface flow). PMC5842040. |
| `kcnq1_pmc10642763` | Arrhythmia-associated calmodulin variants interact with KCNQ1 (HA-KCNQ1). PMC10642763. |
| `cftr_pmc3266683` | CFTR Folding Consortium: methods for CFTR folding/correction (3×HA surface reporter). PMC3266683. |
| `ano1_pmc7291285` | Regulation of TMEM16A by CK2 (extracellular 3×HA, non-permeabilized). PMC7291285. *Numbering unreconciled — see B13.* |

---

## Verification pass — 2026-08-15 (5 literature agents + UniProt residue re-check)

Every control (A1–A24, B1–B13) was re-verified: residue vs UniProt canonical FASTA, and the primary citation vs PubMed/PMC full text. **All stated residues match UniProt** (after the fixes below). Outcomes:

**Citation corrections (were wrong/vague):**
- **A6 CD46** — "Kim 2023" does not exist → **Madsen & Semple 2019**, Wellcome Open Res (PMID 31363496). HiBiT on the CD46 ectodomain, iPSC knock-in. `surface_only`.
- **A8 ADORA1** — "Various" → **Soave et al. 2020**, SLAS Discov (PMID 31583945). N-terminal HiBiT; pharmacology intact. `surface_and_function`.
- **B2 AQP1** — primary is **Crane & Verkman 2007**, Biophys J (PMID 17890385), not the Qdot-diffusion PMC. `surface_only`.

**Sources found (were blank/pending):**
- **A22 SLC26A1** P155 → **Pfau et al. 2023**, JCI (PMID 36719378). `surface_and_function`.
- **A23 SLC9A6** M53 → **Ilie et al. 2016**, Mol Neurodegener (PMID 27590723). `surface_and_function`.
- **B10 ASIC1a** F147 → **Zeng et al. 2013**, J Neurosci (PMID 23595764). `surface_and_function` (decreased proton affinity — the "not neutral" caveat, confirmed).
- **B11 ASIC1a** D298 → **Song et al. 2020**, Neurosci Bull (PMID 32996060). `surface_and_function` (current reduced; best surface/total ratio).

**Reconciliations:**
- **B13 ANO1** — paper's H396/N397 is the human **"abcd" isoform**; **canonical Q5XXA6 = H374/N375** (+22 aa from an alt-spliced N-terminal segment; His confirms human, not mouse). **TSV junction updated 396 → 374.** Citation **Pinto/Kunzelmann 2020**, Cells (PMID 32380794). `surface_and_function`.
- **A21 KCNH2** — **T436 is correct** (BBS between T436/E437, Kanner 2018, PMID 29725305, `surface_only`). The **T443/E444 HA** construct is a *separate, also-real* construct (**Kozek et al. 2020**, Heart Rhythm, PMID 32522694). The earlier "Garg 2020" attribution is **unverified/likely a mislabel** — the site is real, the name was wrong.

**Primary-provenance flags (cited paper reuses an earlier construct):** B4 PMP22 → Liu 2004 / Tobler 1999; B7 SLC4A1 → Cordat 2003/2006 (+ kAE1 numbering drops 65); B12 CFTR primary = Sharma 2004 (PMID 15007060); A19 hDAT possibly Sorkina 2005.

**Weak controls (structural — FLAG is a purification tag, no tagged-vs-untagged):** **A3 CALCR** (3C-cleaved off), **A7 NPY1R**, **A20 EDNRB**. Marked `not_measured`. If the set is meant to be "tag preserves surface + function," these three are the weakest positives.

**Still unresolved:** **A24 TFRC C-terminus** — no published C-terminal extracellular tag on TFRC was found; remains **asserted, not sourced**.

### New/corrected sources (this pass)

| Key | Citation |
|---|---|
| `madsen2019` | Madsen RR, Semple RK. HiBiT CD46 surface reporter. Wellcome Open Res 2019;4:37. PMID 31363496. |
| `soave2020` | Soave M, et al. HiBiT A1 adenosine receptor. SLAS Discov 2020;25:186. PMID 31583945. |
| `crane2007` | Crane JM, Verkman AS. Qdot-labeled AQP1-myc diffusion. Biophys J 2007;94:702. PMID 17890385. |
| `pfau2023` | Pfau A, et al. SLC26A1 sulfate homeostasis (HA after P155). J Clin Invest 2023;133:e161849. PMID 36719378. |
| `ilie2016` | Ilie A, et al. Christianson-syndrome NHE6 (3xFLAG-HA after M53). Mol Neurodegener 2016;11:63. PMID 27590723. |
| `zeng2013` | Zeng W-Z, et al. Constitutive endocytosis of ASIC1a (HA 147/148). J Neurosci 2013;33:7066. PMID 23595764. |
| `song2020` | Song N, et al. Surface-localized hASIC1a (HA 298/299). Neurosci Bull 2020;37:145. PMID 32996060. |
| `sharma2004` | Sharma M, et al. CFTR-3HA misfolding/surface. J Cell Biol 2004;164:923. PMID 15007060. |
| `pinto2020` | Pinto MC, et al. TMEM16A CK2 (3xHA in ECL1, H374/N375 canonical). Cells 2020;9:1138. PMID 32380794. |
| `kozek2020` | Kozek KA, et al. hERG HA (T443/E444) trafficking DMS. Heart Rhythm 2020. PMID 32522694. |

---

## Set revision — 2026-08-15 (PI review)

**Removed (3) — the tag was only a purification aid, not a validated surface tag:**
- **A3 CALCR**, **A7 NPY1R**, **A20 EDNRB** — all cryo-EM structural constructs where the
  FLAG epitope is an affinity/3C-cleavage purification tag (A3's is literally cleaved off
  before the structure), with no tagged-vs-untagged surface or function comparison. Dropped
  from the benchmark set (37 → 34 rows).

**Accepted (1) by direct instruction:**
- **A24 TFRC C-terminus** — no published construct was located, but accepted as a valid
  control per Becca (2026-08-15). `source_key=pi_asserted`, `impact_measured=accepted_pi`.

**Deterministic misses — root cause (both are the 3D-feature veto, by design):**
- **SLC6A4 N211** — folded (pLDDT 88), buried (RSA-window 0.23), and **6.7 Å from the two
  glycosylation sites N208/N217** it is threaded between (+ disulfide 200). All gates reject.
- **ANO1 H374** — an exposed loop (RSA 0.79) but pLDDT 70.6 (just above the disorder cutoff)
  and **8.8 Å from the ECL1 disulfide cluster (370/379/382)**.
- Both are the pipeline being conservative near glycosites/disulfides — correct in general,
  but these published constructs deliberately thread the tag between/beside those features
  while preserving them. A future refinement: veto the glycosite/disulfide *residue* but
  allow an exposed insertion point a few residues away.
