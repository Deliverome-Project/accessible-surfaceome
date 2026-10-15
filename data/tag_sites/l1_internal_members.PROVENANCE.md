# `l1_internal_members.tsv` — L1 members that need an INTERNAL tag site

One row per Library-1 member whose tag placement is `internal`: there is no
extracellular terminus to tag, so the site has to go in an extracellular loop
(or, for the GPI pair below, the ectodomain).

**566 rows · 518 distinct genes · sha256
`c791e3cd032d296edc49024170d0945c9bf755f815b76823bc6f38ad9cc05c1e`**

## Where it came from

| | |
|---|---|
| source repo | `deliverome-analysis` |
| path | `analysis/sprint4/s4e9-orf-design-fg-panel/l1_internal_members.tsv` |
| branch / commit | `claude/p022-p038-plasmid-order-a20f79` @ `96b2ef1` |
| S3 | `processed://sprint4/s4e9-orf-design-fg-panel/l1_internal_members.tsv` |
| generator | `export_internal_members.py`, same folder |
| context | `TAG_PATHS.md`, same folder |

The file here is **byte-identical** to that export, deliberately: the sha256
above is pinned by `tests/test_tag_sites_internal_members.py`, so re-exporting
upstream and diffing the hash is a complete check that the two have not
diverged. Do not reformat it, sort it, or add comment lines — put commentary in
this file instead.

It is vendored rather than read across repos at sweep time because a sweep that
reaches into another repository's working branch is not auditable after the
fact: the branch moves, and nothing in this repo records which bytes a run
actually used.

## The unit is the MEMBER, not the gene

Each row's topology is DeepTMHMM v1 computed on **that member's own ordered
sequence**, matched by sha256 of the translated designed CDS — not by
accession. A designed ORF is an Ensembl-transcript product, and for a
substantial minority that corresponds to a UniProt *isoform* record rather than
the canonical one, so resolving by accession hands back a different protein's
topology (with a plausible length and a plausible helix count, which is what
makes it dangerous).

In this set, **71 of 566 members are not numbered on the human canonical
sequence**:

| `topology_cohort` | members |
|---|---|
| `human_canonical` | 452 |
| `human_isoforms` | 47 |
| `library_designed_orf` | 24 |
| `cyno_ortholog` (+ repick) | 32 |
| `mouse_ortholog` (+ repick) | 11 |

A tag position for any of those, expressed in canonical coordinates, is a
position in a different protein. Positions are therefore numbered in the
member's own frame and stamped with the `sequence_sha256` they were numbered
against — see `src/accessible_surfaceome/agents/tag_site/frames.py`.

## Two columns that are easy to misread

**`gpi_rerouted`** — 2 members (BST2, RGMB). These are single-pass,
GPI-anchored proteins that reached `internal` placement because the ω-site
removes their C-terminus, **not** because they are multipass. Their site lives
somewhere in the ectodomain, not in an inter-TM loop. Key any
"loop inventory" logic on this column rather than on a hardcoded symbol list,
so an L2 pass picks up the equivalent members (GPC1, SPRN) automatically.

**`longest_inter_tm_ecto_run_aa`** — counts only extracellular runs with a TM
helix on **both** sides. So:

* it returns 0 for any single-pass protein **by construction**, which is why it
  is meaningless for the `gpi_rerouted` pair and must not be read there as "no
  site available";
* an N-terminal ectodomain is *not* an inter-TM loop. Reading it as one is the
  recorded ADGRB1 error, where a 918-residue N-terminal segment was once taken
  for a loop candidate.

## Loop availability

| longest inter-TM extracellular run | members |
|---|---|
| 0–7 aa | 7 |
| 8–11 aa | 7 |
| 12–19 aa | 26 |
| 20–29 aa | 54 |
| ≥ 30 aa | 472 |

The 8-aa figure is a convention, not physics: an insertion *lengthens* a loop
rather than replacing it, and s4e9 placed a real site in SLC2A4's 9-aa loop. Of
the 7 members under 8 aa, 5 are genuinely multipass — TMEM86A, TMEM86B,
TMEM169, TMEM139, TMEM268 — and the other 2 are the `gpi_rerouted` pair, which
do not belong in a loop-length stratum at all.

## Shedding

12 members carry a recorded `shed_risk` (1 high, 9 moderate, 2 low). Per
`SHEDDING_AND_TAGS.md` upstream it is a **flag only** and reroutes nothing: no
shedding-risk member has a usable inter-TM loop to move the site to.
