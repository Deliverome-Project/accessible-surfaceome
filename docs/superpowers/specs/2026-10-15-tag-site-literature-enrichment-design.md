# Tag-site literature enrichment for the L1 internal-site members

**Status:** design, for review
**Date:** 2026-10-15
**Scope:** a second literature pass over the 566 Library-1 members that need an
internal (loop) tag site, publishing **additively** alongside the existing
literature sites rather than replacing them.

## Why

566 L1 members (518 distinct genes) have **no extracellular terminus**, so their
tag can only go in an extracellular loop. The first literature sweep
(`tag_site_library_v1`, prompt 1.4.0) found a literature internal-extracellular
site for only 50 of them. The question was whether that is a property of the
literature or of our search.

It was substantially our search. Measured across 559 archived runs for this set:

| signal | median | max |
|---|---|---|
| papers discovered | 77 | 182 |
| clips in the pool | **315** | 1,167 |
| clips the selector was shown | **100** (`_MAX_CLIP_MENU`) | — |
| clips boosted for naming an extracellular residue | **0** | 18 |
| sites returned | 0 | 7 |

419 of 559 runs had a pool larger than the menu, so **two thirds of the evidence
never reached the model**, and the boost meant to lift loop clips fired on ~1.5
clips in 315. Discovery was capped too (`_MAX_PER_SOURCE=30` × 2 EuropePMC
passes + 30 PubTator ≈ 90 against a median 77), and the faceted mode that would
triple the pool was disabled with this comment:

> *"It triples the clip pool … against a selector that still keeps only the top
> 100 … Revisit together with the menu cap, not before."*

### What the 20-gene spike measured

`tag_site_spike_depth_v1`, 20 genes (15 seeded-random + the 5 largest pools),
0 failures, $21.04:

| | |
|---|---|
| new internal-loop sites | **6**, of which 4 carry a residue and 2 are region-level |
| re-finds of already-published sites | 9 |
| terminal sites returned | **0** |
| cost | $1.11/gene median |
| v1 menu starvation | median **84%** of each pool hidden |

Unbiased rate from the random stratum alone: 0.267 new internal sites/gene →
**~138 across 518 at ~$575, ≈$4.16 per site.** 80% of genes gain nothing,
because the literature genuinely has no loop insertion for most multipass
proteins — ADCY2 is the clean case: five published constructs, every one tagging
a cytoplasmic terminus, and the agent correctly returned zero.

So the value is **a published precedent where we currently offer only a
computed candidate**, not coverage. Every gene in this set already has
deterministic internal candidates.

## Four findings that shape the design

### 1. The pool is not monotonic across runs — publishing must be additive

SLC6A3 returned 7 sites in v1 and 3 in the spike. Not menu dilution: 9 of its 12
previously-cited clips were still in the pool and all 9 made the top-400 menu.
The 3 that vanished were **absent from the pool entirely**, because **179 papers
degraded to abstract-only across the sweep** (EuropePMC `fullTextXML` 500s). A
paper that degrades contributes no methods clips, so a correct site becomes
unreachable for reasons unrelated to depth.

A rerun holding less evidence than its predecessor is therefore the *normal*
case under transient fetch failure, not a signal. Two independent brakes:

* publish scoped to its own provenance, so v1 rows are never deleted;
* `sync_tag_sites_to_d1.py` already **refuses a sync that would shrink any
  gene** without `--allow-deletes`.

And one fix in this design: **seed the ledger from the prior run's cited clips**
(§Ledger seeding), so a transient 500 cannot lose a site at all.

### 2. Proteoform frames are worthless at clip selection and valuable at position validation

Across **2,320 real pre-menu clips**, the number that named a residue only a
non-reference frame confirmed was **13, and all 13 were nomenclature**: APOE
E3/E4 genotypes read as Glu-3/Glu-4, ubiquitin E1/E2/E3 enzymes, dopamine D1–D4
receptors. Zero signal.

So the frame resolver must **not** be wired into `tag_site_relevance` or
`boost_residue_clips`, which was the original plan — it would add noise to the
menu. It operates only at position validation, where the text is already known
to be about a tag insertion. That is also where its four real rescues came from
(the GABA-A mature-frame trio and CACNA2D1's isoform frame).

The spelled-residue requirement (PR #376) rejects 13/13 of that noise while
keeping all four rescues.

### 3. `site_kind` is not a reliable terminal/internal discriminator

The five literature sites at positions 4–5 are **topologically identical** — no
signal peptide, extracellular N-terminus, junction inside the N-terminal `O` run
— yet two are labelled `internal` and three `terminal_n`, with both paralogue
pairs (ABCC1/ABCC2, SLC5A1/SLC5A4) disagreeing with their own partner. There is
no defined boundary between "terminal" and "internal" for a tag a few residues
into an extracellular tail, so the model picks per call.

Reproduce:

```sql
SELECT gene_symbol, residue_label, site_kind, insert_after_residue
FROM tag_site_public
WHERE provenance='literature_retrieved' AND insert_after_residue BETWEEN 2 AND 10;
```

**Consequence:** a site is counted and recorded as an internal **loop** site
only when its junction's extracellular run has a TM helix on *both* sides,
derived from the member's own topology — never from the model's label. This is
`longest_ecto_run_position` applied per-site instead of per-member.

### 4. The member is usually, but not always, the canonical protein

A designed ORF is an Ensembl-transcript product. In this set, **71 of 566
members are numbered on something other than the human canonical sequence** (47
`human_isoforms`, 24 `library_designed_orf`), plus 43 non-human ortholog-cohort
members. A canonical-framed position for any of those is a position in a
different protein.

This is not theoretical: the spike's own *verification script* resolved
`topology_acc` against `cohort='human_canonical'` and silently failed on KCNN2,
whose `topology_acc` is `l1-p1037` — a designed ORF — nearly reporting two real
sites as non-loops.

## Design

### Gene/member set

`data/tag_sites/l1_internal_members.tsv`, vendored byte-identical from
`deliverome-analysis` (sha256 pinned by
`tests/test_tag_sites_internal_members.py`). 566 rows / 518 genes.

Branch synthesis context on **`longest_ecto_run_position`**, not on
`gpi_rerouted` plus a symbol list:

* `inter_tm` (564 members) → hand the model the loop inventory;
* anything else (2: BST2, RGMB — single-pass GPI, internal only because the ω
  site removes the C-terminus) → hand it the ectodomain span from
  `longest_ecto_run_start`, and no loop inventory.

### Unit of work

One literature search **per gene** (518 searches — papers talk about proteins,
not ORFs); position resolution and site emission **per member** (566).

The split matters most for the members that are not the human canonical protein,
and it is what makes them tractable rather than special cases:

* **Search is unaffected.** A designed ORF has no UniProt accession, but it still
  has a human `gene_symbol`, and discovery keys on symbol + UniProt names +
  aliases. So `l1-p1037` searches as KCNN2, which is correct — the literature on
  SK2 is the literature for that ORF.
* **Numbering is per member.** The same search feeds every member of that gene,
  and each resolves the cited position in its own frame. Two members of one gene
  can legitimately land on different junctions from the same paper.
* **The 43 ortholog-cohort members** (31 cyno, 11 mouse, 1 cyno-repick) are
  searched on the human gene and numbered on the ortholog sequence. A paper
  citing a human position is then a cross-species claim, which the frame
  resolver cannot currently resolve in either direction, because
  `compara_ortholog.ortholog_uniprot_acc` is NULL in all 21,549 public-D1 rows —
  there is no join key from a human accession to the 12,222 mouse / 14,118 cyno
  sequences that do sit in `topology_public`. Those members therefore get a site
  only when the paper numbers in their own frame. **Out of scope here; tracked
  separately.** Do not paper over it by accepting a human position as an ortholog
  one.

### Member-frame resolution (prerequisite 1)

New `agents/tag_site/member_frames.py`:

1. read the member row from the vendored TSV;
2. resolve its sequence + `per_residue_topology` from `topology_public` via
   `library_topology_public.topology_acc`, **verifying `sha256(sequence)` against
   the row's `sequence_sha256`**;
3. a member whose sha does not match, or has no row, is **skipped and reported** —
   never silently given the canonical.

**Implemented and validated on all 566: 566/566 resolve, zero sha mismatches**,
and the longest inter-TM run derived from the resolved topology equals the
independently-computed `longest_inter_tm_ecto_run_aa` for every member.

The refusal-to-substitute earned its keep immediately. A first pass resolved
only 495/566, and the 71 misses were exactly the 47 isoform + 24 designed-ORF
members — the ones that need this most — with **zero sha mismatches among
them**, which said the query was wrong rather than the data. `topology_acc`
carries the suffixed accession (`P13637-3`) while `topology_public.uniprot_acc`
holds the base; the suffix is in `uniprot_acc_full`. Matching both fixed it. A
fallback-to-canonical would have hidden the bug and silently mis-numbered 71
members.

**Worked example — why this is not theoretical.** KCNN2's member is `l1-p1037`,
a 791-aa designed ORF against canonical Q9H2S1's 579. Two papers place tags at
canonical **A246** (TM3–TM4 loop) and **K162** (S1–S2 loop); the 20-gene spike
published exactly those numbers. Mapped into the member's frame they are **458**
and **374**, each landing on the *same residue identity* (A and K) inside a
genuine inter-TM extracellular run (442–465, 368–376). Placed at the canonical
numbers instead, a cassette in the real construct lands on **L246 and S162,
both topology `I`** — the tag would be intracellular, on a construct that
expresses and traffics normally and carries no detectable surface tag. Two of
the spike's six headline sites were numbered in the wrong frame.

`regenerate_tag_site_lit.py` takes the member sequence/topology instead of the
API record's `canonical_topology`. Every emitted site carries
`numbered_against = sequence_sha256`.

Also: `residue_before` / `residue_after` become **unconditionally computed** from
the member sequence at the accepted junction (`geometry._set_junction` already
does this) rather than taken from the model. `residue_label` derives from
`residue_before`, so one wrong letter poisons the label, and carrying the
computed flanks makes `build_loop_inserts.py`'s existing assertion a real
cross-check: a frame error then fails loudly at build time instead of placing a
cassette tens of residues off.

### Prior-ledger seeding (prerequisite 2)

Before clip selection, load the gene's prior `tag_site_run.ledger_json` (verbatim
quotes + source ids) and merge those clips into the pool, marked as carried
forward. A previously-cited clip therefore cannot be lost to a transient
full-text failure. The seeded clips do **not** count as new (see the pause gate).

### Dedupe, pause, and depth

* **Seen-clip ledger** — private D1 `tag_site_seen_clip`, keyed
  `(gene_symbol, source_id, sha256(normalized quote))`, written for every clip
  that entered a **menu**. Backfilled from v1 `ledger_json`, which holds promoted
  clips only — so the first enrichment run re-sees some v1 menu clips once and
  never again. Documented, not hidden.
* **Covered-position filter** — drop a clip when every residue it confirms sits
  within ±2 of a junction already published for that gene/member. Keep it if it
  confirms even one uncovered residue: a clip that corroborates *and* adds is not
  a duplicate.
* **Pause gate** — zero new clips after both filters ⇒ return **before**
  `select_clips` and synthesis. Gene row records `n_new_clips=0`,
  `outcome='no_new_evidence'`. Spend stops at triage.
* **Depth** (ported from the spike, now affordable): `faceted=True`,
  `_MAX_PER_SOURCE` 30→60, a new `internal_loop` facet (ECL1–3, "second
  extracellular loop", loop insertion, domain insertion, insertional
  mutagenesis, transposon, snorkel, re-entrant loop), and the selector **batched**
  4×100 over the score-ordered pool with picks unioned, instead of truncated.
* **Persist the pool's clip text and the emitted sites** in the run archive.
  Today only counts, boosted *keys* and the promoted ledger survive, so no
  question about what the model could have seen is answerable afterwards — the
  spike had to reconstruct junctions from log prose.

### Synthesis context

Into the **user** prompt (data, never the system prompt — the gene-agnostic
prompt-leak tests must keep passing): this construct has no extracellular
terminus so terminal sites are out of scope; plus the loop inventory (every
contiguous `O` run with start/end/length from the member's own topology). For the
GPI pair, the ectodomain span instead.

### Publishing — additive by construction

* Provenance **`literature_enriched`**; `publish_tag_sites(..., provenances=
  ["literature_enriched"])` always passed explicitly, so a gene that enriches to
  zero clears only its own rows.
* `site_id = {gene}-{candidate_id}-{site_kind}-{residue}-enr`. Carrying
  `candidate_id` stops two members of one gene colliding, and the `-enr` suffix
  makes `INSERT OR REPLACE` over a v1 `-lit` row structurally impossible.
* `tag_site_public` gains `candidate_id`, `library`, `numbered_against`,
  `loop_run_position` (the per-site `inter_tm` / `n_terminal` / `c_terminal`
  derivation from §3). Additive columns.
* **`tag_site_gene_public` PK migration — the riskiest step.** Its PK is
  `gene_symbol` alone, so an enrichment gene row would overwrite the v1 row and
  destroy the dated zero that table exists to preserve. D1 cannot `ALTER` a PK,
  so: create `tag_site_gene_public_v2` with PK `(gene_symbol, run_series)`, copy
  existing rows with `run_series='literature_v1'`, verify row counts match, then
  rename. One statement per HTTP call. Dry-run first; the Worker reads the old
  name until the rename lands, so the window is the rename itself.
* The Worker's gene lookup then selects the right series, and both "searched"
  claims are available. **A Worker deploy changes a response shape → manual
  purge**, and must run the main/dev-inclusive checklist in CLAUDE.md.

### Sweep

`sweep_tag_site_lit.py` gains `--members-file` and `--run-series`; the resume
skip-set becomes `(prompt_sha, run_series)`-aware so v1 rows don't read as done.
Pace held at ≤2 genes/s — each bypassed Worker record fetch costs ~17 queries on
the shared public D1, and an unpaced sweep caused user-facing 500s before.

## Testing

* **Member frames**: sha-verified resolution; a mismatched sha is skipped not
  substituted; a designed-ORF `topology_acc` resolves (the KCNN2 case); flanks
  recomputed from the member, not trusted from the model.
* **Ledger seeding**: a prior-cited clip absent from fresh discovery is still in
  the pool; seeded clips don't count as new.
* **Pause gate**: zero new clips ⇒ `select_clips` never called (assert with a
  client that raises).
* **Loop derivation**: an `inter_tm` junction counts; an N-terminal-tail junction
  does not, even when `site_kind` says `internal` (the ABCC1 R4 shape).
* **Publish**: an enriched publish does not delete `literature_retrieved` rows;
  site_id collision impossible; the v1 gene row survives an enrichment write.
* **Migration**: round-trip the PK change on a scratch table and assert counts.

## Risks

1. **The PK migration** is the only destructive step. Dry-run, verify counts,
   rename last.
2. **Frame generosity** raises false accepts; the two guards are the mitigation
   and the guard has **never been exercised** on a low-position non-initiator
   site — 0 rows match `p 2..10 AND validated AND position_frame IS NOT NULL`.
   Absence of evidence, recorded as such.
3. **Worker shape change** needs a manual purge or genes answer differently per
   POP.
4. **Yield is concentrated**: 80% of genes gain nothing. If the first ~100 genes
   of the sweep come in well under 0.267 new sites/gene, stop and re-decide
   rather than spending the remainder.
