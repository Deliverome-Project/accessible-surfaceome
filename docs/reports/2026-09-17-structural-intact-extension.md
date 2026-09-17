# Broader structural interfaces and IntAct region audit

Audit date: 2026-09-17. This extends the frozen 5,130-gene comparison; it does not change production annotations.

## Findings

| Evidence tier | All 5,130 genes | LLM ligand=yes: 3,157 genes |
|---|---:|---:|
| Previous experimental EC sites | 386 (7.52%) | 365 (11.56%) |
| Existing sites with mature-protein topology repair | 407 (7.93%) | 384 (12.16%) |
| Broader structural interfaces, combined with repaired existing sites | 661 (12.88%) | 621 (19.67%) |
| IntAct binding regions alone | 501 (9.77%) | 465 (14.73%) |
| Structural sites OR IntAct binding regions | 855 (16.67%) | 783 (24.8%) |
| Also including interaction-changing mutations | 871 (16.98%) | 796 (25.21%) |

Broader structural retrieval plus topology repair adds **256 genes** over the previous 365/3,157 EC result. IntAct regions add a further **162 ligand-positive genes** (194 across all candidates) beyond this revised structural union. Mutation-effect evidence adds another **13 ligand-positive genes**, but is not direct-contact evidence.

The combined region total must not be described as exact-epitope coverage. Among 501 genes with accepted IntAct EC regions, the median shortest region is **197 residues**; only **26** have a region of 20 residues or fewer. Even a short fragment is not proof that every residue directly contacts a ligand.

## Scope and rules

- Denominators remain 5,130 unique HGNC genes and 3,157 with the LLM's `has_known_ligand=yes` flag. This flag is broader than experimentally validated natural extracellular ligands. The 24 ambiguous shared-UniProt genes remain in the denominators and receive no gene-specific credit.
- Query all 5,115 distinct cohort accessions for PDBe interfaces, without requiring an IUPHAR ligand or UniProt PDB cross-reference. For 5,106 unambiguous genes, 1,814 returned records and 3,292 returned 404; no retrieval errors. A 404 is endpoint absence, not proof of no structure.
- Require a named non-self UniProt protein partner for new structural interfaces. Preserve structure IDs, canonical positions and context. These are interfaces in experimental structures; physiological relevance, affinity and utility as an external targeting reagent remain unreviewed. Viral/heterologous partners and complexes are not silently called natural human ligands. Anonymous antibody chains remain outside this extension and are covered by the earlier antibody-specific audit.
- Topology now checks mature GPI-anchored chains as well as explicit extracellular intervals. Signal peptides and cleaved propeptides are excluded. Secreted mature proteins remain a separate category, not cell-surface EC. Existing all-site coverage loses ULBP2, RNLS and F2RL3 when their only previous accepted evidence touches removed precursor sequence; no previous EC gene is lost.
- The structural-plus-existing **EC-or-secreted** union is 781 (15.22%) across all candidates and 720 (22.81%) among ligand=yes. These broader values are deliberately excluded from the EC table.

## Coordinate fallback

For PDBe-404 genes lacking prior EC coverage, inspect at most three UniProt-linked experimental structures per gene, ranked by mapped extracellular/secreted span: **191 genes, 349 target–structure attempts, 346 distinct PDB structures**. This bounded search is a lower bound, not an exhaustive PDB search.

ITGA6 is a concrete endpoint miss: 7CEC has mapped EC contacts with laminin chains O15230, P07942 and P11047, as well as integrin beta-1.

Contact calculation uses deposited first-model coordinates and a 5 Å heavy-atom distance threshold, SIFTS residue mapping, canonical amino-acid identity checks and uniquely mapped target/partner chains. Unmapped partner tags cannot create a contact. Interfaces are not independently validated biological assemblies. Fallback contributes EC candidates for **3 genes**. Contact/attempt status counts: `{'no_distinct_uniquely_mapped_partner': 334, 'mapped': 95, 'no_contacts': 2676, 'error': 1}`. Counts here are chain-pair or target-failure records, not genes. The unresolved attempt is ABCB11 structure 6LR0: SIFTS returned 404 after retry, so it receives no credit.

Manual assembly review excludes CFAP95 contacts in [7UNG](https://www.rcsb.org/structure/7UNG) and [8J07](https://www.rcsb.org/structure/8J07) from EC coverage: these are intracellular axonemal microtubule complexes, despite predicted EC intervals in UniProt. The contacts remain in all-site evidence, with the original topology and review reason retained. Other candidates have not all undergone equivalent assembly-level review.

## IntAct/IMEx audit

Use the official **2026-01-14 IntAct export snapshot**: binding-region features, mutation features and negative-interaction records. Require affected human target, exact canonical coordinates, exact original-sequence agreement and an identifiable non-self protein partner. Exclude fuzzy intervals, sequence mismatches, missing sequences, whole-protein features and known negative interactions. Isoform-labelled features count only if the stated region matches the cohort canonical sequence at those same coordinates; this is local feature equivalence, not whole-isoform equivalence. Complex participants remain explicitly labelled as complexes.

The negative export supplied **977 interaction IDs** and excluded **21 binding-region records**; the EC gene totals were unchanged. Exclusion of known negative records is not proof that every remaining interaction has been independently replicated. Neutral/generic mutations and mutations creating a new interaction are excluded. Disrupting, decreasing and increasing mutations remain a distinct tier because folding or indirect effects can change an interaction.

IntAct often records the tested extracellular construct as a sufficient binding region. The [human IgSF interactome study](https://pubmed.ncbi.nlm.nih.gov/32822567/) is a substantial contributor; it screened 564 proteins and validated only a subset with follow-up assays. Broad regions from such screens should appear as experimental region evidence with assay/source provenance, never automatically as exact epitopes or physiological ligand claims.

Examples:

| Target | Partner / evidence | What is recovered |
|---|---|---|
| ULBP2 | NKG2D, IntAct EBI-16417738; [PMID 19424970](https://pubmed.ncbi.nlm.nih.gov/19424970/) | Mature binding region 26–217, distinct from the removed precursor-tail site in the previous audit. |
| PKD1 | CU062/Q9NYP8, EBI-55030383; [PMID 37681898](https://pubmed.ncbi.nlm.nih.gov/37681898/) | Region 1889–2148, with other extracellular fragments reported; region evidence rather than contact residues. |
| KLRB1 / CLEC2D | EBI-13640995 / EBI-13640997; [PMID 21572041](https://pubmed.ncbi.nlm.nih.gov/21572041/) | Regions 90–225 and 71–191 respectively. |
| TREML2 | Multiple partners in [PMID 32822567](https://pubmed.ncbi.nlm.nih.gov/32822567/) | Broad 19–268 construct; this does not resolve the separate disputed B7-H3 claim. |

## Revisit the random 50

The original frozen random sample now has structural EC candidates for **7/50**: CD59, ACVR1B, ITLN1, ERVFRD-1, AMHR2, ITGA6, PRNP. IntAct adds region evidence for **3** more: ULBP2, TREML2, PKD1. This is gene-level recovery; a new partner does not necessarily validate the ligand originally named by the LLM. These sample fractions should not be substituted for the full-cohort measurements above.

## Integration priority

1. Add broader PDB/PDBe retrieval and mature-protein topology handling first. Display exact target residues, structure, partner identity and structural-context confidence, with a separate biological-relevance review status.
2. Add IntAct as a separate binding-region and mutation-evidence layer. Display region width, feature type, interaction ID, publication and binary/complex status. Prioritize the 162 additional ligand-positive genes for paper-level review rather than presenting all broad fragments as epitopes.

SurfaceBind remains predicted-site evidence from the earlier comparison and is not included in these experimental unions. This audit measures new protein interfaces and curated protein-interaction features; it does not estimate new small-molecule affinity coverage.

## Artifacts and reproducibility

- `structural_site_context_overrides.tsv`: stable-ID keyed, source-linked assembly-context adjudications.
- `structural_intact_summary.tsv`: both denominators and incremental coverage.
- `structural_intact_genes.tsv`: stable identifiers and per-tier coverage flags for all 5,130 genes.
- `structural_intact_evidence.tsv.gz`: positions, partners, source IDs, context and confidence tier.
- `structural_intact_attempts.tsv.gz`: IntAct feature acceptance/rejection reasons.
- `structural_fallback_contacts.json.gz`: all fallback outcomes, including errors and mapping exclusions.
- `structural_intact_manifest.json`: source hashes, counts and definitions. Large source downloads remain in ignored caches.

Reproduce with `fetch_structural_intact_extension.py` stages `uniprot`, `pdbe`, `intact`, then `audit_structural_fallback.py --run`, then `audit_structural_intact_extension.py` (all under `scripts/audit/`, with `PYTHONPATH=src:scripts/audit`). Mutable upstream endpoints can change results; the committed hashes identify this run's exact inputs. No paid model calls, production D1 writes or viewer deployment were used.

Validation: nine focused topology, feature-parser and coordinate-contact tests; scoped Ruff and ty; full denominator/union reconciliation and gzip integrity checks. Full repository suite is not claimed.
