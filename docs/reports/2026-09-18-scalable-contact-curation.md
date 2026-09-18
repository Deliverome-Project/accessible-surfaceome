# Scalable contact curation and coverage expansion

Draft PR #235; unpublished release `contacts-c7126e61a544377fbf0f`. Production remains `contacts-ba6680878403e6980464`. No merge, production API activation or D1 writes.

| Metric | Previous draft | Updated draft |
|---|---:|---:|
| Proteins with mapped evidence, any compartment | 1,685 | 1,711 |
| Proteins with named extracellular overview evidence | 551 | 551 |
| Extracellular observations eligible for overview | 7,962 | 7,962 |
| All retained observations | 29,189 | 29,358 |

The earlier 1,680 baseline is now 1,711 (+31): five initial chemical targets, 16 additional chemical targets, and ten proteins recovered by retaining processing-segment evidence. These gains do **not** expand mature extracellular coverage.

## Identity safety

Name-only global ligand IDs are replaced by chemical component IDs, explicitly accepted construct fingerprints, target-scoped reviewed aliases, catalogue IDs, stable UniProt parent groups, IEDB receptor groups, and target/source-scoped clone groups. Unresolved observations remain separate and ambiguous display names receive source/structure suffixes. Global IDs no longer collapse unrelated VHH6 or generic peptide records merely because their names match.

Protein-parent, source-clone and receptor groups are useful browsing units, not a census of exact molecular constructs or peptide sequences. Complete molecule equivalence is asserted only for the three accepted deposited-construct pairs. Existing reviewed aliases and EGFR's 16 default ligand groups are preserved. Unreviewed cross-source MF3958 and JS003 labels remain distinct pending an explicit identity decision; these raise the ERBB2 and CD274 displayed counts by one each.

## Reproducible coordinate checks

`scripts/audit/validate_reviewed_chemical_contacts.py` replays all 41 accepted ligand instances from hash-pinned mmCIF and SIFTS files and canonical sequences. It checks first-model positive-occupancy heavy-atom contacts within 5 Å, exact target accession, chain mapping and residue identity. Modified residues, mixed-accession chains, ambiguous mappings and mismatched contact residues fail closed. No predicted coordinates or inferred affinity are used.

The asset builder requires a successful validation ledger pinned to both the reviewed input bytes and validator implementation. Stale reviews or changed validation code require a new replay. Offline replay verified 41/41 instances, including the original eight. Source coordinates are downloadable caches, not committed bulk artifacts; file hashes and canonical sequence hashes are retained in the committed ledger.

## Construct-aware deduplication

The reusable suggestion audit examines deposited monomer sequences, reference mappings and covalent chemistry. Its first snapshot contains 207 records and 18 same-construct suggestions; 73 records are held. It does not automatically accept suggestions. Missing/incomplete chemistry information is held rather than interpreted as no modifications.

Independent review supports exactly three pairs: FZD8–FKBP fusion (21KR/21KS), CTNND1 isoform4A deletion construct (3L6X/3L6Y), and H2AX-derived presented nine-mer RIIPRHLQL (2D31/2DYP). Exact target/accession/PDB scopes and source hashes gate acceptance. Every original target state and footprint is preserved. Native full-length protein or unmodeled chemistry equivalence is not implied. See [peer review](2026-09-18-construct-equality-peer-review.md).

## Remaining chemical targets

The bounded screen covers all 74 remaining uncovered targets / 171 source records. It nominated 28 pairs across 19 targets. Independent coordinate replay accepted 24 pairs across 16 targets (33 instances, 29 distinct exported observations).

Four pairs remain held: acetylcholine/8XTW for Q16572 and spermidine/9D7V plus spermine/9D7X for Q6NT16 have mixed-accession target chains; NKO/9L0O for O14494 has a noncanonical contact residue. None was overridden. Other additives, unresolved lipid species, and unsupported identity/context assignments remain in the screen ledger. See [complete 74-target screen](2026-09-18-remaining-chemical-candidates.md).

Contexts for accepted footprints were recalculated from the actual validated positions and canonical UniProt features; original source topology remains separately recorded in the review input. Therapeutic category describes the molecule's use, not efficacy or mechanism at this particular target. Most additions occupy membrane pockets or intracellular domains.

## Processing-segment evidence

Retain 140 distinct experimental observations across 37 proteins that overlap annotated signal, transit or propeptide segments. These include ten previously uncovered proteins. Every such record carries an explicit processing qualifier and is excluded from the mature extracellular overview. No processing-segment contact is relabeled as extracellular solely to increase coverage. RGMA's previously held processing-domain observations are now available as qualified all-contact evidence.

## Conservation and validation

All 29,189 previous observations retain their original source, partner, partner label, structure, residue positions, context, reference and method. The committed 82-target preservation test now checks each baseline observation as a multiset subset, permitting additions without permitting deletion or field changes. Added evidence totals 169 observations (140 processing +29 chemical).

54 focused Python tests and 20 Node contact/API tests pass; repository Ruff, targeted type checks, and viewer-schema synchronization pass. Publisher dry run reports 5,106 summaries, 6,969 identity groups, 9,138 associations and 29,358 observations, with no writes. Identity group counts cannot be compared as biological ligand discovery gains because the identity policy changed.

The network-enabled full suite passes 1,981 tests with 82 skipped; two unrelated structural-signal tests fail because the shared environment lacks the declared `freesasa` dependency. Repository-wide local type checking similarly finds missing `pydssp`; all changed modules pass targeted checking. The shared environment is left unchanged. CI installs the complete locked dependencies. The viewer production build status is recorded in the PR validation.

## Reproduction

With repository source caches hydrated, run the coordinate validator with `--review data/analysis/deep_dive_binding_sites/reviewed_chemical_contacts.json --cache-dir <coordinate-cache> --output data/analysis/deep_dive_binding_sites/reviewed_chemical_validation.json` (add `--offline` to prohibit downloads), then `scripts/audit/build_contact_site_assets.py`, then `node scripts/audit/export_contact_release.mjs <unpublished-bundle.json>`. Use `PYTHONPATH=src` and `uv run --no-sync python` in the existing worktree.

The construct suggestion generator accepts `--fetch` for public PDBe caches. Regenerating suggestions deliberately invalidates the accepted snapshot hash until its six accepted member records are rechecked. The chemical screen consumes the pinned prior release and primary metadata caches; its committed JSON preserves all decisions and input hashes.
