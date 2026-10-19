# `reagent_inventory_constructs.tsv` — provenance

A snapshot of the plasmid constructs recorded in the Reagent Inventory, vendored
so the construct↔proposed-site join is reproducible from the repo.

| | |
|---|---|
| Source | Google Sheet "Reagent Inventory", `Plasmid` tab |
| Sheet id | `1yOJaTL6gXu_jbhshuAVcbjLgkpAaH14GTuQQTgOtK98` |
| Columns taken | `ID`, `Name`, `Status`, `Insert / Target gene`, `Tag / Fusion`, `Tag location` |
| Snapshot date | 2026-10-19 |
| Rows | 38 constructs with a gene assigned (backbones and packaging plasmids excluded) |

**This is a snapshot and it goes stale.** The inventory is the live record; this
file exists because a committed join has to read committed data. Re-take it when
constructs are added, and keep the column set narrow — the inventory carries
storage locations, concentrations and owners that have no business in this repo.

## Why it is here at all

The two registries are split by artefact type and nothing joins them: the
inventory records what was **built**, `tag_site_public` records what the pipeline
**proposed**. P-0007 is a built-and-received SpyTag-ALFA construct at TFRC V291 —
a residue this pipeline proposes, and for which `tag_fit` returns
"ALFA, DogTag". So our own table recommends a different chemistry at the exact
position a plasmid already occupies, and nothing surfaced that until the join
existed. On 2026-10-18 a review recommended dropping SpyTag003 from six
about-to-be-ordered plasmids partly because that counterexample was invisible.

## Conventions, which do not match

`Tag location` is free text and carries at least two conventions:

- `loop, after 146` / `cassette after residue 32` — states the junction.
- `V291 (preceding)` — names a residue and says the cassette goes *before* it,
  so the junction is after 290. One residue off the other reading.

The join reports the named residue and flags the convention rather than
silently decrementing. Guessing between them is precisely the off-by-one that
moved p0033 from after-162 to after-161 in the same batch.
