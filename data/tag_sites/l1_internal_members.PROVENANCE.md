# `l1_internal_members.tsv` — L1 members that need an INTERNAL tag site

One row per Library-1 member whose tag placement is `internal`: there is no
extracellular terminus to tag, so the site has to go in an extracellular loop
(or, for the GPI pair below, the ectodomain).

**566 rows · 518 distinct genes · sha256
`c7359a2495925587125ff36bba4644c0a902f1f8fef3a8333da2f5cebe1d9999`**

## Where it came from

| | |
|---|---|
| source repo | `deliverome-analysis` |
| path | `analysis/sprint4/s4e9-orf-design-fg-panel/l1_internal_members.tsv` |
| branch / commit | `claude/p022-p038-plasmid-order-a20f79` @ `fa1e762` |
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

## Where the tag goes: branch on `longest_ecto_run_position`

Three columns describe the extracellular region, and they are not
interchangeable:

| column | meaning |
|---|---|
| `longest_inter_tm_ecto_run_aa` | longest extracellular run with a TM helix on **both** sides — a true inter-TM loop |
| `longest_ecto_run_aa` / `_start` | longest extracellular run with **no** such restriction, and where it begins |
| `longest_ecto_run_position` | which kind that longest run is: `n_terminal` / `inter_tm` / `c_terminal` / `no_tm` |

**`longest_ecto_run_position` is the one to branch on.** `inter_tm` means the
site belongs in a loop and the loop inventory applies; anything else means the
extracellular region is a terminus-adjacent span with no inter-TM loop to
describe. That replaces "`gpi_rerouted` plus a hardcoded symbol list" with a
property of the topology itself, so an L2 pass picks up its equivalents
(GPC1 539 aa, SPRN 133 aa) with no code change.

In this set the split is `inter_tm` 564 / `c_terminal` 2, and those 2 are
exactly the members where the restricted and unrestricted measures disagree:

| | tm | inter-TM run | longest ecto run | position |
|---|---|---|---|---|
| BST2 (`l1-p0188`) | 1 | 0 | **137** aa from 44 | `c_terminal` |
| RGMB (`l1-p1731`) | 1 | 0 | **394** aa from 85 | `c_terminal` |

Both are single-pass GPI-anchored proteins that reached `internal` placement
because the ω-site removes their C-terminus, **not** because they are
multipass. `longest_inter_tm_ecto_run_aa` returns 0 for any single-pass protein
**by construction**, so that 0 must never be read as "no site available" — it
is an artefact of the restriction, and these two have 137 and 394 residues of
ectodomain to aim at. `gpi_rerouted` still flags them and agrees exactly; it is
corroboration, not the branch point.

Relatedly, an N-terminal ectodomain is *not* an inter-TM loop. Reading one as a
loop candidate is the recorded ADGRB1 error, where a 918-residue N-terminal
segment was once taken for a loop.

**The unrestricted measure CONFIRMS the hard stratum rather than softening
it.** For the five genuinely-multipass short-loop members the ectodomain run
*equals* the inter-TM run — TMEM86A 7, TMEM86B 7, TMEM268 7, TMEM139 6,
TMEM169 1 — because that short loop is their only extracellular region. Two
independent measures therefore agree they are the hardest stratum, and
BST2/RGMB never belonged in it.

**Parse this file by column NAME.** The three run columns were inserted at
positions 13–15, beside `longest_inter_tm_ecto_run_aa`, rather than appended at
the end, so positional readers would silently shift.

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

## Upstream churn that does NOT affect this file

A MICA repoint landed on S3 (`candidate_cds.json` now 7,016 entries; `lib:MICA`
is the 383-aa TM-bearing form; `iso:MICA:Q29983` removed as redundant). It took
L2 from 3,188 to 3,187 classified, because `l2-p0939` no longer has a designed
CDS and drops out of any run keyed on the manifest. **L1 is unaffected at 2,700
and none of the 566 internal members changed.**

Note for anyone who follows the trail upstream: the committed manifest there
still names the old MICA transcript, so the manifest and `candidate_cds.json`
currently disagree. That is recorded in `TAG_PATHS.md` upstream and belongs to
the MICA work, not here.
