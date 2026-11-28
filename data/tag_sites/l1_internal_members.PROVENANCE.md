# `l1_internal_members.tsv` — L1 members that need an INTERNAL tag site

One row per Library-1 member whose tag placement is `internal`: there is no
usable extracellular terminus to tag (or the protein was routed to internal
placement for GPI / shedding / propeptide reasons), so the site goes in an
extracellular loop or ectodomain segment.

**607 rows · 548 distinct genes · sha256
`874db68acba95be6aad3c43fef592f866d07aca840fd5859f2766c287680a5f3`**

## Where it came from

| | |
|---|---|
| source repo | `deliverome-surfaceome-library-v1` (synced from `deliverome-analysis`) |
| path | `library/l1/orf-design/l1_internal_members.tsv` |
| cut | `bundle-2026-11-26` (`2026-11-25-pre-freeze-e`) |
| previous vendored cut | 566 rows · 518 genes (`c7359a249592...`, 2026-10-15) |
| delta vs previous cut | +90 added, −49 removed, 517 shared (14 `sequence_sha256` updated) |

The file here is **byte-identical** to that export, deliberately: the sha256
above is pinned by `tests/test_tag_sites_internal_members.py`, so re-exporting
upstream and diffing the hash is a complete check that the two have not
diverged. Do not reformat it, sort it, or add comment lines — put commentary in
this file instead.

## The unit is the MEMBER, not the gene

Each row's topology is DeepTMHMM v1 computed on **that member's own ordered
sequence**, matched by sha256 of the translated designed CDS — not by
accession. A designed ORF is an Ensembl-transcript product, and for a
substantial minority that corresponds to a UniProt *isoform* record rather than
the canonical one, so resolving by accession hands back a different protein's
topology.

In this 607-member set, **102 members are not numbered on the human canonical
sequence**:

| `topology_cohort` | members |
|---|---|
| `human_canonical` | 505 |
| `human_isoforms` | 62 |
| `library_designed_orf` | 7 |
| `cyno_ortholog` (+ repick) | 16 |
| `mouse_ortholog` (+ repick / cds_policy) | 17 |

Positions are numbered in the member's own frame and stamped with the
`sequence_sha256` they were numbered against — see
`src/accessible_surfaceome/agents/tag_site/frames.py`.

## Where the tag goes: branch on `longest_ecto_run_position`

Three columns describe the extracellular region, and they are not
interchangeable:

| column | meaning |
|---|---|
| `longest_inter_tm_ecto_run_aa` | longest extracellular run with a TM helix on **both** sides — a true inter-TM loop |
| `longest_ecto_run_aa` / `_start` | longest extracellular run with **no** such restriction, and where it begins |
| `longest_ecto_run_position` | which kind that longest run is: `n_terminal` / `inter_tm` / `c_terminal` / `no_tm` |

In this 607-member cut:
- **580 members** have `longest_ecto_run_position == "inter_tm"` (true multipass loops).
- **27 members** have `longest_ecto_run_position != "inter_tm"` (`n_terminal`: 20,
  `no_tm`: 4, `c_terminal`: 3 — including `gpi_rerouted` `BST2` plus single-pass /
  GPI / ectodomain-routed proteins such as `AREG`, `BACE1`, `CDH3`, `CDH5`,
  `EFNA1`, `ENTPD2`, `ITGB3`, `PDCD1`, `VTCN1`, and two multipass proteins
  `GABRA2`/`MFSD2A` whose longest ectodomain is N-terminal).
- **5 genuinely multipass short-loop members** have `longest_inter_tm_ecto_run_aa < 8`
  and `longest_ecto_run_position == "inter_tm"`: `TMEM86A`, `TMEM86B`, `TMEM139`,
  `TMEM169`, `TMEM268`.

**Parse this file by column NAME.** The three run columns sit at positions
13–15, beside `longest_inter_tm_ecto_run_aa`.

## Loop availability (`longest_inter_tm_ecto_run_aa`)

| longest inter-TM extracellular run | members |
|---|---|
| 0–7 aa (5 multipass + 27 ectodomain-routed) | 32 |
| 8–11 aa | 8 |
| 12–19 aa | 31 |
| 20–29 aa | 55 |
| ≥ 30 aa | 481 |

## Shedding

23 members carry a recorded `shed_risk` (2 high, 19 moderate, 2 low).
