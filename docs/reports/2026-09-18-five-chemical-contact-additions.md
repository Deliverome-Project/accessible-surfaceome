# Five reviewed chemical-contact additions — 18 September 2026

Added ABCA1–cholesterol (7TBY), ENPEP–bestatin (4KXB), GRIA2–ZK200775 (5ZG2), GRID1–GABA (8BN5) and KCNK13–halothane (9M9Q) to the unpublished contact release. Mapped protein coverage rises from1,680 to1,685; observations rise from29,182 to29,189. All29,182 original observations are unchanged, including original labels, context, references, methods and positions.

The new reviewed-chemical input is an explicit acceptance list, not a relaxation of all chemical-contact filtering. It adds eight ligand-instance footprints; two identical GRIA2 footprints collapse to one existing-style observation. All five genes have a named extracellular display group. Per-instance ligand IDs, coordinate/SIFTS hashes and mapping checks remain in `reviewed_chemical_contacts.json`.

## Evidence and display categories

| Target | Partner | Category | Source and caveat |
|---|---|---|---|
| ABCA1 | Cholesterol | Endogenous small molecule | [7TBY](https://www.rcsb.org/structure/7TBY): sterol-like density modeled as cholesterol; exact chemical identity uncertain. Wild-type nanodisc structure used. |
| ENPEP | Bestatin | Therapeutic | [4KXB](https://www.rcsb.org/structure/4KXB): inhibitor footprint matches canonical residues despite construct mutations elsewhere. Bestatin/ubenimex clinical role supported by [trial](https://pubmed.ncbi.nlm.nih.gov/2224060/); not an ENPEP-specific approval claim. |
| GRIA2 | ZK200775 | Therapeutic (investigational/discontinued) | [5ZG2](https://www.rcsb.org/structure/5ZG2): canonical contact residues. [Phase II trial](https://pubmed.ncbi.nlm.nih.gov/16131799/) stopped for safety. Full construct/isoform equivalence is not asserted. |
| GRID1 | GABA | Endogenous small molecule | [8BN5](https://www.rcsb.org/structure/8BN5): published binding, structural and functional support. |
| KCNK13 | Halothane | Therapeutic | [9M9Q](https://www.rcsb.org/structure/9M9Q): released experimental deposition, associated paper unpublished. Evidence confidence and review reason retain this distinction. |

Coordinates were independently checked using the first deposited model, positive-occupancy heavy atoms within5 Å, exact SIFTS accession and canonical amino-acid identity. These recalculated footprints have their own stated method; they are not represented as unchanged PDBe aggregated contact sets. A mapping mismatch rejects the canonical-only acceptance route. The builder hashes the supplemental input into the release manifest.

## Held records

ENPP3/6C02 remains excluded because T205A directly contacts AMPCPP. RGMA/BMP2 and GDF5 remain pending processed-product review. Nine other extracellular chemical candidates contained only buffers/PEG/additives; they are not promoted. The earlier GRIA2/5H8S footprint with a contact-site sequence discrepancy remains excluded. The accession search of22 uncovered therapeutic targets found no additional antibody complex in its returned entries; this is not an exhaustive literature or isoform search.

## Validation

18 focused Python tests,20 Node contact/API tests, scoped Ruff/type checks and a full viewer build pass. Tests cover coverage counts, retained confidence caveats and rejection of mutant-contact inputs. Full release comparison preserves all old observations. Publisher dry run is used without execute; no D1 writes or production changes. Draft PR235 remains held.

Unpublished release: `contacts-2e5ae951b1f791d2f280`.
