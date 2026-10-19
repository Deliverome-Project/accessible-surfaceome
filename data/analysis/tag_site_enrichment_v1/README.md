# Tag-site literature enrichment — run intermediates (`literature_enriched_v1`)

The full intermediate record for every member the enrichment pass examined: the
clip pool it ranked, which clips the residue-boost lifted, which the selector
took, the evidence ledger, the synthesis metadata, and every site a gate
removed. 74 artifacts, one per library member, gzipped JSON, 2.2 MB.

`data/external/tag_site_runs/` is gitignored (derived, and it accumulates every
run), so these are the published copy: the 74 that back the sites now live in
public D1.

## Why these exist at all

The artifact used to record `n_clips` and not the clips. Across 26 members of a
live sweep `pool` was empty in **26 of 26** while `n_clips` read 60-214 — the
size was saved and the contents were not, so the one question the artifact
exists for ("why was this clip not picked?") still cost a fresh run to answer.
It also recorded `outcome: "incomplete"` on 10 of those, which is the field's
initial value: three `_empty()` return paths never stamped one. Both fixed in
`924d34d26`.

The record is deliberately **bounded**: `EvidenceClaimDraft.context_excerpt`
runs to 1500 chars and one member's pool held 2,175 clips, so persisting drafts
verbatim would be hundreds of megabytes across the cohort. Each pool entry keeps
`clip_id`, `source_id`, `section`, `quote_chars` (the true length),
`quote_head` (truncated to 180), `boosted_residues` and `selected`. Verified
here: 27,249 pool entries, `quote_head` max 180 / mean 150, and **zero** entries
carrying `context_excerpt`.

## What is in each file

| key | |
|---|---|
| `candidate_id`, `gene_symbol`, `run_series`, `numbered_against` | identity; `numbered_against` is the sha256 of the sequence the residues are numbered in, never an accession |
| `pool` | every clip the selector saw, with the decision per clip |
| `boosted`, `n_boosted` | clips lifted before the menu cap because they name an extracellular residue |
| `ledger` | the span-verified evidence |
| `sites`, `other_positions` | what it proposed |
| `rejected` | sites a gate removed, with the gate name and the failing quote |
| `synthesis_meta`, `notes`, `n_repair_attempts` | the synthesis step's own account |
| `outcome` | `synthesized` / `no_span_verified_evidence` / `no_papers_discovered` / `synthesis_returned_nothing` |
| `cost_usd` | per member |

## Read the outcomes before trusting a pool

    synthesized                53
    incomplete                 20
    no_span_verified_evidence    1

**The 20 `incomplete` are pre-fix.** The 52-member sweep's process had already
loaded the old code when `924d34d26` landed, so it could not pick the fix up;
those artifacts have an empty `pool` and the placeholder outcome. Split by sweep:

| sweep | artifacts | empty `pool` | `incomplete` |
|---|---|---|---|
| 52-member gap set (pre-fix process) | 62 | 51 | 20 |
| **20-member random sample (fix active)** | 10 | **0** | **0** |

So treat an empty `pool` here as "this run predates the fix", not "the pool was
empty". Re-running those 52 is the only way to recover their pools.

## What the pass yielded

73 searches over 70 unique members, $56.95. Seven site rows across six genes
reached public D1, and **two carry a residue**: AQP4 after 141 and FZD1 after 69
(both from the random sample). The other five name a paper that tags the protein
internally without giving a position — not orderable, and counted separately for
that reason.

The 53-member no-published-site gap set produced one row and **zero** positioned
sites. Selecting members *because* no published site exists selects against the
literature having anything to say about them, so that arm's yield says nothing
about the pipeline's.

On the random sample: 2 positioned sites from 18 members ≈ 11%, ~$28 per
orderable site. An earlier spike suggested 45%, which did not separate
positioned from unpositioned rows.

## Two defects in the sweep runner, recorded

`random20_members.tsv` held 20 **unique** members drawn from the full 566-member
table and disjoint from the gap set — the sampling was clean. The runner then
ran `l1-p1876` and `l1-p0131` **twice** and never ran `l1-p1544` or `l1-p1906`,
so 18 of 20 were covered and roughly $2 was spent twice. Fix the draw-to-run
step before the next sweep; this is not a sampling bias but it does mean the
denominator is 18, not 20.

## Licensing

`quote_head` holds short substring-anchored snippets (≤180 chars) of published
text, the same fair-use basis as the evidence ledgers the API already serves.
No full text, no PDFs; downloaded PDFs live in `data/external/blob_cache/`,
which stays gitignored.
