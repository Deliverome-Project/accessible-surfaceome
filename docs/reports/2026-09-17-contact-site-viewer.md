# Contact-site viewer and source priorities

The contact-only audit snapshot covers **1,680 / 5,130 candidate genes**. Of these, **661** have strictly extracellular evidence. The exporter represents 5,106 unambiguous canonical mappings; 24 shared-accession genes remain uncredited.

Prioritize **PDB/PDBe** for breadth, **SAbDab** for antibody-specific interfaces, and **Thera-SAbDab** to name therapeutic binders. Add **BioLiP** for curated biological ligands, **AACDB/IEDB** for additional antibody/epitope records, and **GPCRdb/IUPHAR** for specialized pharmacology. Structure-derived contacts establish proximity in the experimental structure; they do not independently establish physiological binding or extracellular accessibility. No calibrated confidence probabilities are available.

| Source | Genes | Evidence sites | EC genes | EC evidence sites | Interpretation |
|---|---:|---:|---:|---:|---|
| PDB/PDBe | 1,326 | 22,883 | 507 | 5,474 | Largest breadth; nonself interfaces may include nonphysiological contacts |
| BioLiP | 851 | 851 | 186 | 186 | Biological-ligand curation; one representative mapped site per gene; may include cofactors |
| SAbDab | 409 | 409 | 259 | 259 | Antibody-specific; one representative interface per gene in this audit |
| AACDB | 210 | 879 | 156 | 667 | Antibody structural contacts; complementary records, overlapping genes |
| PDBe | 209 | 850 | 36 | 118 | IUPHAR-linked chemical contacts |
| GPCRdb | 190 | 1,521 | 15 | 56 | Specialized GPCR contacts; many sites span transmembrane regions |
| IEDB | 182 | 897 | 129 | 639 | Experimental epitopes; assay and native accessibility vary |
| IUPHAR+PDBe | 120 | 471 | 54 | 212 | IUPHAR-linked natural protein ligands |
| Thera-SAbDab | 80 | 419 | 61 | 352 | Exact named therapeutic domains; overlaps antibody structure sources |
| BioGRID+literature | 1 | 2 | 0 | 0 | Experimentally supported minibinder contacts; very limited coverage |

These are **retained audit evidence records**, not total database site counts or unique physical pockets. Deduplication is within source by partner, PDB, canonical residue set, context and reference. Different sources/structures can describe the same interface. SAbDab and BioLiP were sampled for gene coverage, so their site totals cannot rank database completeness. “EC” excludes secreted-only, membrane-spanning, intracellular, and unknown-location sites.

IntAct regions (1,610 genes) and mutation effects (494 genes) remain separate audit evidence; neither is rendered as exact contacts. SurfaceBind remains a distinct predicted-anchor view (1,609 genes in the audit comparison).

## Viewer behavior

“Contact sites” sits directly beside SURFACE-Bind in the 3D controls. It defaults to extracellular evidence and provides a source filter, keyboard-accessible slider, previous/next buttons, source-colored residue highlights and legend, partner/source labels, PDB and evidence links, and canonical positions. Scrubbing preserves the camera. Projection is enabled only on the canonical AlphaFold model, never isoforms, orthologs or experimental chain numbering. Empty, unavailable and unaudited states are distinct.

The static assets are separate from annotation JSON/D1. This PR makes no production database writes. Sixty-four lazily loaded JSON shards keep the deployment file count bounded. Rebuild from the committed compressed evidence using `PYTHONPATH=src uv run python scripts/audit/build_contact_site_assets.py`. The accompanying manifest records the input hash and counting rules.

Validation: targeted biological-evidence/export tests, TypeScript, and browser checks on EGFR (122 EC records; Thera-SAbDab filter yields 14 records including cetuximab; next-site navigation and isoform suppression).

The offline production build passed (987 exported files, including all 64 contact shards); the live EGFR and ABCB9 record previews were checked separately. Full-cohort regeneration and exhaustive SAbDab/BioLiP site ingestion are not implied by this snapshot.

## EGFR example

The binder/ligand filter now searches readable gene names as well as stable partner identifiers. Labels come from the existing unambiguous UniProt-to-HGNC cohort mapping; identifiers are retained. EGFR (P00533) has ten PDB/PDBe records for EGF (P01133), all classified extracellular. Searching EGF selects these records, starting with 1IVO (37 canonical EGFR contact residues). These are ten structural observations, not ten distinct binding pockets. IUPHAR names are now enriched from the provenance-tracked ligand catalogue sidecar; other names outside the cohort retain source identifiers.

Validation: three export tests including the EGFR–EGF regression, name/identifier/source-filter checks, TypeScript, scoped Ruff/ty, and browser confirmation of the ten EGF results and 1IVO residue count.

## Similar-site grouping

The viewer now groups similar sites by default, with a toggle to restore all records. Within each source, exact partner ID and compartment, every pair in a group must have Jaccard residue-set similarity of at least 0.70. Complete-link grouping prevents an intermediate footprint from bridging two dissimilar sites. The largest observed footprint is rendered; residue sets are not unioned into a synthetic site. Every original structure/reference remains accessible under supporting records. Different partner identifiers and sources are deliberately not merged without verified identity crosswalks.

EGFR extracellular records reduce from 122 to 58 groups; the ten EGF records reduce to three groups (7, 2 and 1 supporting records). These are browsing groups, not inferred distinct biological binding pockets. Validation: TypeScript, two grouping regression tests covering identity/context separation and overlap-chain prevention, and browser checks of grouped counts, expanded evidence, and restoration of all records.

## Compact footprint comparison

The count now distinguishes all-ligand results from a ligand search and reads “Group N of M”; it is not a count of distinct biological sites. Comparison shows the selected group and up to two additional groups with pairwise overlap no greater than 20% of the smaller residue set. This spatial display heuristic does not establish simultaneous binding. Source colors remain consistent; numbered outlines and differing line patterns distinguish footprints that share a source.

Three fixed, orthogonal C-alpha projections (XY, ZY, XZ) are zoomed to the compared contact residues. Thick convex outlines enclose each observed residue set; enclosed gaps are explicitly not claimed as contacts or a molecular surface. The main interactive 3D view renders all compared footprints with larger translucent atom markers. Evidence details and methodology are collapsible. The projections use only validated numeric coordinates from the currently loaded canonical model and disappear on noncanonical models or when the model is unavailable.

Validation: four grouping/comparison/outline regression tests; TypeScript; browser verification of all-ligand three-footprint comparison, EGF-only three-group/one-footprint display, and slider updates. EGF alternative footprints overlap and are therefore not automatically presented as independent sites.

## Readable ligand names and stable navigation

The binder picker includes EGF (IUPHAR 4916), epiregulin/EREG (4918), epigen/EPGN (4917), and TGFα/TGFA (5059). The committed name sidecar records the GtoPdb catalogue version, source URL and hash; asset manifests hash the sidecar. Stable partner identifiers are retained. EGF now finds 20 evidence records across IUPHAR+PDBe and PDB/PDBe, representing the same ten PDB complexes; these remain six source-specific similarity groups (three per source), not six independent biological sites.

Slider controls precede changing labels and projections, with fixed columns for the arrows and a separate counter row. Cross-binder comparison is opt-in and labels each comparison binder separately. IMC-11F8 Fab's eight AACDB records form their own group; no TGFA record is merged into that group.

Validation: five grouping/comparison tests, three exporter tests, scoped Ruff/ty, successful production export, and browser verification of the named EGF picker, unchecked comparison default, and next-site navigation.

## Ligand-first overview

Default browsing now shows one representative footprint per normalized named ligand across sources, with all source observations retained under evidence. EGFR has 17 named extracellular partner entries in this view; 11 records with unresolved identities are excluded from the overview but searchable by identifier. This is not an exhaustive biological ligand census. Selecting or searching a ligand restores its source-specific footprint groups. IEDB receptor names are restored from observations.tsv.gz using source, binder ID and reference; the manifest hashes this name source. GtoPdb protein ligands and corresponding UniProt partners share names. Case, Fab/Fv/VHH suffixes, parenthetical aliases and the audited necitumumab/IMC-11F8 alias are normalized for browsing only. GC1118 and GC1118A remain separate without a verified equivalence.

Validation: six viewer regression tests, three exporter tests, production build, and browser checks of the 17-entry overview and EGF's six source-specific groups.

## Main-structure design refinement

The default contact panel now uses the surrounding viewer's typography, spacing, line and accent tokens, with a ligand picker, stable navigation, and one compact source/residue summary. Search, source/compartment filters, comparison and orthogonal projections are collapsed under Filters & comparison. Evidence remains available in a separate disclosure.

Selected contacts render as nearly opaque atom-sized spheres against a faded canonical backbone. Focus site frames the selected residue set on the main interactive model; Whole protein restores the full-protein framing. Scrubbing still preserves the camera. These are observed contact atoms, not a fabricated envelope or a bound-ligand structure. Browser-verified with EGF's two separated contact patches visible in the main model.

Validation: six contact regressions and successful production build/export with TypeScript validation. The standalone check initially encountered stale development-route types from an earlier temporary EGFR route; the production build passed.

## Ligand totals and role colors

The contact panel always displays the named-ligand total for the selected compartment scope, independent of the current ligand search or source filter, alongside category counts. EGFR shows 17 extracellular named entries and 34 across all compartments. The extracellular breakdown is 4 endogenous large molecules (proteins/peptides), 0 endogenous small molecules, 5 therapeutic agents, 4 reviewed research tools, and 4 unclassified partners. These are snapshot named partner counts, not an exhaustive biological ligand census.

Category colors now match the main structure, slider, category legend and optional projection views; source provenance remains in evidence details. The picker is grouped by category. Metadata is rebuilt with scripts/audit/build_ligand_categories.py using the cached GtoPdb endogenous target–ligand annotations and ligand types, the Thera-SAbDab therapeutic-name catalogue, and explicit cited EGFR role reviews. The resulting committed sidecar contains source hashes and review references. Therapeutic includes investigational and discontinued programs. Absence from Thera-SAbDab never automatically makes a binder a research tool. GC1118 is therapeutic based on its phase I study (PMID 31164456); GC1118A remains unclassified without a verified identity crosswalk. ERBB2 is also unclassified rather than relabeling a receptor partner an endogenous ligand.

Validation: seven viewer regression tests, three exporter tests, scoped Ruff/ty, successful production build/export, and browser checks of persistent totals, category counts, grouped picker, and EGF category labeling.

## Single-entry ligand browsing and source explanations

Selecting a ligand now keeps a single representative observed footprint, rather than opening a source-specific group slider. EGF has one displayed entry with ten unique structures and twenty source records; the source records and their individual residue sets remain under Alternative observations. Navigation appears only when browsing multiple ligands. This supersedes the earlier search-to-groups interaction.

Ligand and source pickers use styled disclosure menus with categorized options, keyboard-accessible buttons, Escape dismissal and focus restoration. The app's existing InfoTip component explains each source's evidence and limitations, both beside the selected ligand's source list and within observation details. IUPHAR+PDBe explicitly explains overlap with PDB/PDBe.

Validation: seven regression tests (including one-entry EGF browsing with all twenty observations preserved), successful production build/export, and browser verification of the styled picker, absence of an EGF slider, ten-structure/twenty-record summary, and the IUPHAR source tooltip.

## All-ligand overlay

All ligands now renders all named representative footprints matching the compartment/source scope together, rather than selecting the first entry. EGFR's default shows 17 extracellular footprints. Selecting one ligand isolates its single representative. Focus sites frames their combined residues. The overview lists all displayed ligands under evidence and no longer presents a per-ligand navigation slider.

Residue coloring aggregates category membership before rendering. Residues shared across categories use an explicit blue-gray overlap color, avoiding last-record color overwrite; the display does not establish simultaneous binding. The Unclassified info tooltip lists 059-152, DL11, ERBB2 and GC1118A for EGFR. Unclassified means a category assignment has not been verified, not that contact evidence is absent.

Validation: eight viewer regression tests, including complete residue-union preservation and overlap labeling; production build/export; browser confirmation of the 17-footprint overview and the unclassified-name tooltip.
