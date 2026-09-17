# BioLiP and GPCRdb: full deep-dive cohort audit

This audit uses the frozen 5,130-gene cohort and its 3,157 explicitly
LLM-labelled natural-ligand=yes subset. Stable HGNC/UniProt joins and the
24 unresolved shared-accession exclusions match the previous audit.

## Results

| Source / evidence | All 5,130 genes | LLM ligand=yes, 3,157 | New versus previous 631 (all genes) |
|---|---:|---:|---:|
| BioLiP: mapped biological ligand sites | 853 (16.63%) | 713 (22.58%) | 483 |
| GPCRdb: mapped experimental contacts | 190 (3.70%) | 182 (5.76%) | 46 |
| Both new sources, deduplicated | 905 (17.64%) | 762 (24.14%) | 504 |
| **Previous + new sources** | **1,135 (22.12%)** | **969 (30.69%)** | **504** |
| Entirely extracellular union | 384 (7.49%) | 364 (11.53%) | — |
| BioLiP representatives carrying affinity annotations | 236 (4.60%) | 202 (6.40%) | 92 |
| GPCRdb binding-mutagenesis records, separate tier | 43 (0.84%) | 43 (1.36%) | 5 |

The old union was 631/5,130 (12.30%) and 575/3,157 (18.21%); entirely
extracellular coverage was 302 and 287 respectively. The new sources add 394
genes in the ligand=yes subset. Source rows overlap: GPCRdb adds 21 genes after
BioLiP (18 in the ligand=yes subset), not another 46 independent genes.

Examples of those 21 GPCRdb additions include S1PR5, OR2T2, OR51E2, OR52E4,
GPR139, ADRA2C, DRD4, DRD5, GNRHR, HTR1F, MC1R and PTH2R. These display names
were obtained after stable-ID joins, not used as query identifiers.

BioLiP yielded 989,058 total rows, 40,405 matching unambiguous cohort accessions,
and 940 genes with qualifying sites in native structure numbering; 853 mapped
under the conservative representative-site rules. Their selected representatives
comprise 671 organic-compound and 182 peptide sites. One example illustrating
the breadth of the criterion is RHAG with cholesterol (CCD CLR, PDB 7UZQ): an
identified structural ligand, not evidence of a drug-like targeting reagent.

GPCRdb retrieval covered 787 cohort human receptors, 1,502 ligand-containing
experimental structures, and 4,019 successful API responses including canonical
residue tables. Native interaction coverage was 198 genes; canonical mapping
retained 190. Ninety-two individual ligand-site groups failed residue-numbering
or sequence checks; no missing contact/mutation responses were treated as
negative results. Site failures are distinct from gene failures because other
sites can cover the same gene.

BioLiP affinity annotations are retained verbatim, without claiming normalized
Kd confidence or that all 853 genes have affinity measurements. Requiring the
BioLiP representative to carry an affinity annotation, while retaining the
previous union and GPCRdb structures, gives a narrower union of 768/5,130
(14.97%) or 687/3,157 (21.76%). This is an annotation-present sensitivity check,
not a fully validated affinity catalogue.

**Recommendation:** prioritize BioLiP for broad ligand-site coverage and GPCRdb
for receptor-focused structural/experimental detail. Keep direct contacts,
affinity annotations, mutation evidence and predicted SurfaceBind patches as
separate evidence fields. The results support both integrations, but not an
undifferentiated claim that every newly covered gene has a usable therapeutic binder.

## Interpretation

BioLiP adds a different corroboration route from the previous IUPHAR-supported
chemical pairs: curated biological relevance of a ligand in an experimental
structure. Its accepted sites include substrates, lipids, cofactors and peptide
fragments; they are not all drugs, therapeutic binders, or affinity-validated
reagents. The expanded union is therefore *experimental ligand-site coverage*,
not a count of ready-to-use targeting reagents. Neither structural contacts nor
mutational effects alone establish an energetic epitope or live-cell accessibility.

The current [BioLiP download portal](https://zhanggroup.org/BioLiP/download.html)
now also advertises BioLiP3 computed/LLM-derived affinity collections. This audit
uses only its redundant experimental `BioLiP.txt.gz` annotations, not those new
computed or LLM collections. The portal reports removal of PDBbind-CN affinity
data in January 2025; historical database totals should not be treated as the
current downloadable affinity coverage.

## Methods and limits

- Scan every row in the redundant BioLiP experimental annotation download;
  require one exact cohort UniProt accession. Keep peptide ligands identified
  by deposited PDB/chain/instance, or carbon-containing CCD compounds with at
  least six heavy atoms. Exclude the existing audit's common additive, ion and
  attached-sugar list; DNA/RNA and unknown CCD identities are not counted.
- For canonical mapping, try at most ten sites per protein, preferring records
  with an affinity annotation and then better experimental resolution. Stop
  after the first successfully mapped site. Thus category, affinity and
  extracellular counts characterize these representatives, not exhaustive
  per-gene inventories of every type of evidence.
- Align BioLiP's observed receptor sequence to the cached canonical UniProt
  sequence (match +2, mismatch -3, gap open -5, extension -0.5, free end gaps).
  Require at least 95% of construct residues to match, every contact residue
  to match exactly, and a unique optimal alignment. Retain original structure
  numbering alongside mapped canonical positions. Unresolved mappings remain
  in a separate native-site tier, not in the mapped union.
- GPCRdb human receptors are joined by accession; its experimental structure
  list is filtered to cohort receptors with ligands and experimental methods.
  Retrieve both chemical and peptide interactions by **PDB ID**, avoiding the
  peptide endpoint's accession-based AlphaFold-model lookup. Exclude records
  whose sole interaction designation is `accessible`.
- Resolve GPCRdb generic residue numbers through the receptor's canonical
  residue table where available; otherwise verify the reported sequence
  position directly. Every contact's amino acid must match canonical UniProt.
  Disagreement excludes the site rather than silently treating an engineered
  construct's residue number as canonical.
- Mutation evidence requires a named ligand, publication, matching wild-type
  residue, and a nonzero WT Kd/Ki/pKd/pKi/Kh/Kl value with units. This deliberately
  excludes functional-only and incomplete records. It is reported separately:
  changed affinity can reflect folding/allostery, while no change is not an
  epitope. No mutation record enters the direct structural-site union.
- Entirely extracellular sites require all accepted contact residues to be
  labelled extracellular by UniProt topology. Transmembrane pockets, mixed
  sites and unknown topology do not count as entirely extracellular.

The [BioLiP schema](https://zhanggroup.org/BioLiP/download/readme.txt) provides
ligand identities, residue numbering, sequences, references and affinity fields.
The [GPCRdb API](https://gpcrdb.org/services/) provides receptors, experimental
structures, chemical/peptide interactions, canonical residues and mutations.

## Reproduction

Run `PYTHONPATH=src uv run python scripts/audit/audit_biolip_gpcrdb.py --fetch`
to populate ignored caches, then the same command without `--fetch` to build
outputs. No model calls, database writes or deployment steps occur. The existing
UniProt cache and frozen cohort from the earlier audit are required.

`biolip_gpcrdb_genes.tsv` contains all denominator rows and source flags;
`biolip_gpcrdb_summary.tsv` contains source and incremental coverage;
`biolip_gpcrdb_evidence.tsv.gz` contains representative BioLiP sites and the
accepted GPCRdb evidence. The manifest records source URLs and hashes, including
per-request cached metadata. Downloaded inputs remain uncommitted.
