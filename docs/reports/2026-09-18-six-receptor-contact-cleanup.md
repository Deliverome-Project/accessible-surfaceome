# Six-receptor contact cleanup

Reviewed the existing mapped-contact records for six targets using stable UniProt identifiers. This is identity and category curation of the audit snapshot, not a new exhaustive ligand search. Rules and supporting references are recorded in `data/analysis/deep_dive_binding_sites/reviewed_contact_partners.json`; source labels and all original residue observations remain intact.

| Target | UniProt | Previous EC names | Cleaned EC partners | Observations retained |
|---|---|---:|---:|---:|
| HER2 / ERBB2 | P04626 | 38 | 29 | 121 |
| PD-1 / PDCD1 | Q15116 | 28 | 26 | 85 |
| MET | P08581 | 7 | 5 | 52 |
| IL6R | P08887 | 7 | 6 | 21 |
| PD-L1 / CD274 | Q9NZQ7 | 19 | 15 | 31 |
| VEGFR2 / KDR | P35968 | 5 | 4 | 24 |
| Total | | 104 | 85 | 334 |

Counts describe named partners with mapped extracellular contacts, including receptor partners and sequence-matched therapeutic arms. They are not counts of drugs independently crystallized with each receptor.

## Identity corrections

Consolidated Herceptin/trastuzumab, construct variants of chA21 and HuA21 (retaining chA21 and HuA21 as distinct), F0178C1 aliases, Fab37/37, mAb059c/059c, camrelizumab constructs, avelumab constructs, KN035 constructs, and ramucirumab/1121B. Structure-specific labels resolve H218 at 3WLW, amivantamab's MET arm at 6WVZ, and MM-131's MET arm at 6I04. Corrected BM5-936559 to BMS-936559 and the 5J89 small-molecule label to BMS-202.

The CD80 entry from [7TPS](https://www.rcsb.org/structure/7TPS) is the engineered therapeutic davoceticept (ALPN-202), not wild-type CD80. IL6ST is displayed as gp130 and classified as a receptor partner. The PD-L2 entry from 6UMT explicitly notes its affinity-engineered complex. [NCI's ramucirumab entry](https://www.cancer.gov/publications/dictionaries/cancer-drug/def/ramucirumab) supports the 1121B synonym.

Thera-SAbDab observations for these targets now expose their matching method, antibody arm and chain metadata. Viewer evidence explains that the contact footprint comes from a sequence-matched arm; this does not prove that the complete named therapeutic was crystallized.

## Unresolved evidence retained

Three observations are excluded from the named overview but preserved in the complete API evidence:

- HER2 CMJ112 / [9IUT](https://www.rcsb.org/structure/9IUT): deposited structure identifies H2Mab-250; source identity conflict remains unresolved.
- HER2 H10-03-06 / [5K33](https://www.rcsb.org/structure/5K33): deposited structure identifies Fcab STAB19; equivalence is unresolved. H10-03-06's separate 5KWG observation remains in the overview.
- IL6R CYS / [1N26](https://www.rcsb.org/structure/1N26): deposited cysteine component without evidence establishing a functional receptor ligand.

Eight named partners retain unclassified roles: HER2 H10-03-06, MF3958, Oslo-2 and SF2; PD-1 21A08Ap1 and 609A; PD-L1 HZ-C-Ye-18 and JS003. The available records do not justify forcing a clinical or research-tool category.

## Publication and validation

Public D1 release `contacts-ba6680878403e6980464` passed complete payload readback before activation: 5,106 proteins, 5,339 ligand identities, 8,175 target–ligand associations and all 29,182 original observations. Previous validated release `contacts-37d700655fdf74b13746` remains available for rollback.

The development API returns the six cleaned counts above. EGFR remains unchanged at 16 extracellular / 33 total partners. Production API and Pages deployment remain pending; this change does not deploy either.

Validation: 10 contact-grouping tests, 6 API tests and 6 scoped Python tests passed; scoped Ruff and type checks passed; the viewer production build using the development API succeeded.
