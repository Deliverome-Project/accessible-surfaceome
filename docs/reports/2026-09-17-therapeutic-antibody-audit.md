# Therapeutic antibody and AACDB audit

This audit extends the frozen 5,130-gene comparison with exact therapeutic
binding-domain identities and AACDB's experimentally determined antibody
interfaces. It uses the same HGNC cohort, canonical UniProt mappings and
3,157 explicit LLM natural-ligand=yes denominator. Shared protein accessions
remain uncredited for gene-specific coverage.

## Results

| Evidence | All 5,130 genes | Ligand=yes, 3,157 | EC sites: all genes | EC sites: ligand=yes | New genes versus previous experimental union |
|---|---:|---:|---:|---:|---:|
| Exact therapeutic-domain interfaces | 80 (1.56%) | 71 (2.25%) | 60 (1.17%) | 57 (1.81%) | 1 |
| AACDB mapped antibody contacts | 211 (4.11%) | 196 (6.21%) | 151 (2.94%) | 147 (4.66%) | 0 |
| All experimental sources combined | 1,136 (22.14%) | 970 (30.73%) | 386 (7.52%) | 365 (11.56%) | 1 |

The therapeutic pass verifies **161 therapeutic names, 171 therapeutic–target
pairs and 371 distinct deposited interfaces** across the 80 genes. These are
not 161 independent antibody sequences: products can share binding domains.
The [named catalogue](../../data/analysis/deep_dive_binding_sites/therapeutic_antibody_catalogue.tsv)
provides gene IDs, drug names, matched arms, PDBs, exact-match provenance and
extracellular-site flags. Residue-level observations are in the compressed
evidence export. The [updated all-source table](../../data/analysis/deep_dive_binding_sites/all_source_comparison.md)
recomputes exclusivity across all ten displayed evidence streams.

**Nemolizumab–IL31RA** supplies the additional experimentally covered gene.
IL31RA already had a SurfaceBind prediction, so the experimental-or-predicted
union remains 2,302/5,130 (44.87%) and 1,806/3,157 (57.21%). A zero in the table's
all-source exclusivity column therefore does not mean Thera-SAbDab added no
experimental evidence.

AACDB adds a structural antibody interface for **IL18RAP** beyond the original
411-gene SAbDab representative pass, but IEDB already covered that gene. It adds
no new gene beyond the combined antibody sources. The antibody-only union
(SAbDab, exact IEDB epitopes, AACDB and therapeutic-domain matches) rises from
419 to 420 genes. The entirely extracellular union across all experimental
sources rises from 384 to 386 genes: **CYBB** and **IL31RA**.

All 702 required PDB/SIFTS retrievals succeeded. AACDB yielded 1,129 cohort chain
entries covering 226 candidate genes; 1,033 entries mapped under the strict
residue rules, covering 211 genes. The therapeutic candidate set comprised 526
entries, 165 names and 81 genes; 500 entries mapped, covering 161 names and 80
genes. Remaining attempts were eight unlocated exact variable domains, sixteen
noncanonical antigen-contact cases, and two instances with no variable-domain
contacts. These are unresolved or nonqualifying records, not negative binding
experiments. Candidate names not promoted to mapped coverage are bafisontamab,
osemitamab, panitumumab and zolbetuximab.

**Interpretation:** finishing Thera-SAbDab is useful primarily for putting named
therapeutic binders and their structural sites on already-covered receptor
pages. AACDB is a useful annotation cross-check, with little additional gene
coverage against this newer SAbDab/IEDB audit. Neither result supports expecting
a large target-coverage increase just by adding another PDB-derived antibody
database. Patent-linked evidence remains unmeasured.

## Evidence rules

Thera-SAbDab was already present in the original IUPHAR enrichment pipeline.
This pass instead checks **all cached SAbDab2 antibody–antigen complexes** against
Thera-SAbDab, and checks AACDB antibody-chain sequences as another matching route.
It accepts either an exact paired VH/VL sequence match (including an individual
bispecific arm or single-domain antibody) or Thera-SAbDab's explicitly listed
100%-identity PDB/antibody-chain combination. A PDB match without the correct
antibody chains does not qualify. The 99% and 95–98% match columns are excluded.

A therapeutic name denotes an INN-listed therapeutic binding domain, not proof
that the entire marketed molecule, ADC, fusion or bispecific was crystallized.
Multiple therapeutic names can share one binding domain. Discontinued and
investigational molecules are included. The cached clinical-stage column is
labelled February 2025 and is **not used as current approval status**.

SAbDab2 splits chain-sharing constructs into logical chain IDs (for example,
A1/A2 for domains originally on author chain A). Following its documented
convention, these are resolved to physical chains only when the construct is
flagged and the exact variable-domain sequence is uniquely located. This
recovers the nemolizumab–IL31RA interface that the earlier representative audit
missed. The generic SAbDab audit has not been rerun for all other unresolved
constructs, so its original 411-gene row remains a lower bound.

For each eligible complex, the exact antibody variable-domain sequence must
be located unambiguously in the deposited polymer sequence. Contact computation
uses only those variable-domain atoms: Fc and constant-domain contacts cannot
create a therapeutic epitope. The deposited heavy-atom contact cutoff is 5 Å;
the first coordinate model and positive-occupancy ATOM records are used, following
the earlier audit. SIFTS maps native antigen-chain positions, including insertion
codes, to canonical UniProt. Contact residues that differ from the canonical sequence are
rejected, whether due to a mutation, alternate isoform, or another construct difference. These are structural interfaces, not experimentally measured energetic
epitopes or new affinity measurements.

AACDB v1.0 (2024-05-30) contains 7,498 curated complexes. Its paper describes an
underlying search ending in November 2023; therefore it should not be treated as
a more recent structural corpus than the current SAbDab export. The full summary
and distance-based contact archive are searched. Antigen chains are matched via
SIFTS, **not** the summary's potentially multi-protein `targets` column. Contacts
are filtered to ≤5 Å for comparability. Every accepted native contact position
must map uniquely and match the canonical residue. AACDB's contact text omits
insertion codes: sites with ambiguous native residue numbers are excluded.
Therapeutic names in AACDB's clinical annotations are retained only as source
annotations; they do not independently establish an exact drug-sequence match.

Every matching therapeutic/arm/target/structure combination and every matching
AACDB antigen-chain entry is attempted; there is no three-structure-per-gene
limit for this extension. Entirely extracellular requires every mapped contact
residue to have a UniProt extracellular topological-domain annotation. Missing
or mixed topology is not silently treated as extracellular.

## Explicit unresolved therapeutic target

CLDN18 has candidate complexes labelled as CLDN18.2 in the deposited structure
titles: osemitamab (9V2U, 9V31) and zolbetuximab (9V32). Their contact residues
differ from the cohort's canonical sequence, so this audit does not promote
them to canonical mapped-epitope coverage. They remain visible in the attempt
export. This is a reference-sequence limitation, not an absence of therapeutic
antibodies to CLDN18; a future isoform-aware mapping should retain the specific
protein reference rather than silently transplanting those residues.

## Sources and reproduction

- [Thera-SAbDab methodology](https://opig.stats.ox.ac.uk/webapps/sabdab-sabpred/therasabdab/about)
- [SAbDab2 chain conventions](https://sabdab.opig.stats.ox.ac.uk/about)
- [AACDB download portal](https://i.uestc.edu.cn/AACDB/download.html)
- [AACDB publication and curation assessment](https://elifesciences.org/articles/104934)

Run `PYTHONPATH=src uv run python scripts/audit/audit_therapeutic_antibodies.py --fetch`,
then repeat without `--fetch`. The earlier cohort, UniProt, SAbDab2 and Thera-SAbDab
snapshots are prerequisites. Downloads are cached under ignored external-data
paths. The per-gene coverage, summary, evidence, retrieval attempts and manifest
are exported under `data/analysis/deep_dive_binding_sites/therapeutic_aacdb*`.
No model calls, live D1 writes, or viewer deployment are involved.
