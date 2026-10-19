# Handoff — tag-site enrichment, gates, and the construct join

**Date:** 2026-10-19 · **Branch:** `claude/tag-site-enrichment-pipeline`
**Merged to `dev`:** #376, #377, #408, #409, #411

Read this top to bottom; it is ordered by what will bite you first.

---

## 1. The one thing to understand before touching the gates

The deterministic tag-site lanes gate candidates on four thresholds —
`PLDDT_MIN = 70`, `RSA_MIN = 0.40`, `FEATURE_DIST_MIN = 10.0` Å,
`MIN_LOOP_LEN = 8` — plus, until today, two more that I added and then removed.

**Evidence refused three of these in one day.** A clearance calibration over 185
published internal tag sites and a secondary-structure pass over the same set
found:

| veto | what it rejects, among *published working* sites |
|---|---|
| disulfide enclosure | 27/176 sit inside a closure; 12 function-validated |
| DSSP helix / strand | 57/185 (31%); 20 function-validated; 47 mid-element |
| 10 Å clearance floor | 22/130 (16.9%); 11/49 (22.4%) display-and-function |

The disulfide and helix vetoes are now **reported or ranked, not vetoed**. The
10 Å floor is still a hard veto and **is known too strict** — see §4.

**Why the form matters, not just the constants.** A veto's false negatives are
invisible: an excluded site leaves no row in `tag_site_public`, no pin on the
viewer, no artifact. All three problems above were found only by audits built
specifically to look. A ranking's errors are visible and someone argues with
them — which is how two parallel sessions caught my wrong calls on ACKR3 284 and
MS4A1 157.

**Scoping a conversion of the remaining thresholds to ranking signals is the
next task and it is not started.** See §6.

Two exclusions are categorical and should survive any conversion:

- **topology** — an extracellular tag at an intracellular residue is wrong by
  definition, not by degree;
- **the hazard residue itself** (`feature_dist == 0.0`) — "do not tag the
  glycosylation sequon". My first adjacency split dropped this and let TFRC
  N251, a sequon, read 19.4 Å and pass. A pre-existing test caught it.

---

## 2. What landed (all on `dev`)

| area | commit | state |
|---|---|---|
| member-keyed resume + sweep flags | #408 | merged, deployed |
| Worker serves all searches (`searches[]`) | #408 | deployed as version `224e2f0c` |
| `prompt_sha` regression fix | `afdc03cc8` | merged — see §3 |
| model disulfides → clearance veto | `c093cffb7` | merged, **wired** into all 3 callers |
| disorder lane: 3-tier junction ranking | `8b83caf78`, `2c3419b8a` | merged |
| enclosure audit (24,018 sites) | `c1b2de389` | merged, TSVs committed |
| TFRC P-0007 counterexample | `7d92e8372` | merged |
| construct ↔ proposed-site join | `883892eaa` | merged |
| **adjacency split** | `244732793` | **unmerged — needs a PR** |

Artifacts worth knowing:

- `data/analysis/tag_site_disulfide_enclosure/enclosed_sites.tsv` — 3,865
  enclosed sites with spans
- `data/analysis/construct_site_join/construct_vs_proposed.tsv` — built vs
  proposed
- `scripts/audit/audit_tag_site_disulfide_enclosure.py`,
  `scripts/audit/join_constructs_to_tag_sites.py`

---

## 3. Traps that have already cost something

**A schema field can enter the prompt and invalidate the cohort.**
`SYSTEM_PROMPT` ends in `format_output_contract()`, generated from the schema.
`position_frame` entered it and moved `prompt_sha`, marking all 2,370 archived
genes stale — ~$2,000 of re-runs — to ask the model for a value the pipeline
overwrites. Fields the model never supplies go in `_PIPELINE_INTERNAL`. The
guard is `PINNED_PROMPT_SHA` in `tests/test_tag_site_output_contract.py`.

**A Worker deploy silently drops unmerged response-body fields.** Land Worker
surface on `dev` and deploy from `dev`. Run
`scripts/cloud/worker_shape_guard.py --check` before and after.

**AFDB `/files/` IP-bans bursts** with bare 429s. ~9 s/request. A cohort-wide
re-derive is a paced multi-hour job, which is why nothing has been republished.

**Two distance conventions are in play and differ by 1–4 Å.** `features.py`
consumes **CA-CA**. Others have used CA-SG and heavy-atom. Name the convention
in every number — MS4A1 Y161 reads 11.3 CA-CA and 8.0 heavy, landing on opposite
sides of the 10 Å floor, and a session told Becca a construct "sat at the floor"
on the wrong ruler.

**Sequence adjacency is not spatial clearance.** At separation 1 the Cα–Cα
virtual bond fixes CA-CA at 3.81–3.86 Å *whatever the fold does*. I reported
ACKR3 P35 as a defect on a 3.83 Å reading that was its distance to C34 at
separation 1, and relayed that to two sessions. Fixed in `244732793`.

---

## 4. Open, blocked on nothing

1. **PR the adjacency split** (`244732793`). Branch is 1 ahead / 5 behind `dev`.
2. **The 10 Å floor is too strict and the calibration is now in-repo.** PR #412
   merged to `dev` on 2026-10-19 and **the session that produced it has ended**,
   so `tag_sites/features.py` — where the floor actually lives — is unowned. Note
   #412 added `audit/_disulfide_clearance.py` and `scripts/audit/calibrate_disulfide_clearance.py`
   and **never touched the gate**: the floor was measured, not changed. It is
   still 10.0.

   The sweep is per-tier in
   `data/analysis/disulfide_clearance_calibration/floor_sweep_*.tsv`. For
   function-validated published sites, CA-CA — the convention `features.py`
   consumes:

   | floor | rejected of 49 | |
   |---|---|---|
   | 10 Å (current) | 11 | 22.4% |
   | 8 Å | 10 | 20.4% |
   | 6 Å | 8 | 16.3% |
   | **5 Å** | **1** | **2.0%** |

   The cliff is between 5 and 6 Å, so a floor at 5 costs one published site
   against the current eleven. Read `REPORT.md` first: there is **no negative
   set** (every site in it worked, so it bounds the floor from above and can
   never confirm one from below) and `tag_length_aa` is NULL throughout, so
   nothing in it licenses a floor for the 51-aa cassette.

   **Settling the floor does NOT settle the 51-aa question, and they will look
   like one decision.** The corpus has `tag_length_aa` NULL on all 185 rows, so
   it bounds the floor from above *for an unrecorded cargo size*. The floor runs
   only on the internal lanes, which cohort-wide is the 24,018 internal
   deterministic sites — and the only constructs with a known cargo in that
   population are the six internal loop arms of the S4E9 batch (SLC2A4 67/319,
   MS4A1 146/161, CCR5 263, AVPR2 302), every one carrying the full 51-aa
   cassette, roughly five times a typical epitope tag. Their `LOOP_TAG_AA` was
   collapsed onto `CASSETTE_AA` on 2026-10-18, so the 19-aa internal convention
   no longer exists there.

   So: a cohort-wide floor change lands on exactly the cargo size the evidence
   cannot speak to. Move the floor on the false-negative rate if you like — 11
   of 49 is measured whatever the cargo — but do not let that read as having
   cleared 51 aa in a tight loop. That is a separate question and it is
   downstream.

   **One open question from that report is now answered.** It asks whether the
   veto also runs on terminal candidates, since a free chain end is not a
   threaded loop. It does not: `FEATURE_DIST_MIN` appears only in
   `surface_loop.py` and `disorder.py`, never in `terminal.py`. So the floor is
   applied to exactly the internal population it was fitted on.
3. **`surface_loop_candidates` still hard-gates `ss in LOOP_SS`** — rejects the
   same 20 function-validated published sites as the helix veto I removed from
   the disorder lane. Pre-existing. Relaxing it *adds* candidates cohort-wide,
   so it is a deliberate decision, not a patch.
4. **Viewer drops `literature_enriched`.** Three runtime filters:
   `lib/tag-sites-overlay.ts` (`RENDERED` array), `TaggedSitesCard.tsx` (three
   equality filters), `GeneDetail.tsx` (tab visibility). Plus union types in
   `StructureViewer.tsx` and `TopologyBar.tsx`. `tagSiteCategory` already maps
   any non-deterministic provenance to `"literature"`, so the colour axis needs
   no change. **I started this and stopped at the test-reading stage — nothing
   is edited.** Enrichment output currently stores and serves but renders
   nothing.
5. **The enrichment sweep has not run.** 566 members / 518 genes. 46% cannot
   host the 51-aa cassette on the permissive topological measure. The
   no-published-site gap is 53 members ≈ $56; the full sweep ≈ $595 at the
   measured $1.052/member. One gene re-ran as a spike: KCNN2 for $0.95, which
   pinned **A458** from a paper citing canonical 246 — a site the live record
   does not have.
6. **Nothing has been republished.** `tag_site_public` still carries MS4A1 N171
   (inside the 167–183 closure) and ACKR3 P35. Both are now detectable in code.
   P35 should **not** be retired — see §5.

---

## 5. Corrections I issued, so you do not re-derive them

- **Do not drop SpyTag003 from internal loops.** I recommended it from a
  reference table whose own second line says none of its rows are human
  cell-surface proteins. Internal SpyTag works for transferrin receptor:
  **P-0007** `pAG_Lenti_CMV_TFRC_V291_IRES_Puro`, status Received. Recorded in
  `data/tag_sites/positive_controls.md` with the retraction dated. Also note
  the DogTag arithmetic goes the wrong way — ALFA+DogTag is 58 aa against the
  51-aa cassette.
- **Do not retire ACKR3 P35.** 7.63 Å spatial, against a published minimum of
  5.29 Å.
- **Enclosure alone is not disqualifying.** A session recorded "treat any site
  inside a disulfide span as unvalidated", attributed to me. Too strong.

---

## 6. The next task, as scoped

Convert `PLDDT_MIN`, `RSA_MIN`, `FEATURE_DIST_MIN` and `MIN_LOOP_LEN` from
vetoes into ranking signals, keeping the two categorical exclusions in §1.

The volume objection is weaker than it looks: MS4A1 has 53 extracellular
residues, the thresholds cut that to 2 candidates, and
`select_representatives` already caps at 20 with 8-residue spacing. So the real
choice is "20 ranked candidates carrying their own numbers" versus "2
survivors". **The cap is doing the useful work; the thresholds are doing the
damage.**

The natural yardstick is the 185-site published corpus, and it is now in-repo
rather than owned by a live session: `scripts/audit/calibrate_disulfide_clearance.py`
reads it and the per-tier floor sweeps are committed under
`data/analysis/disulfide_clearance_calibration/`. A ranking that puts its 130
measurable sites in the top N is doing its job, and that is a number a veto
cannot produce. **Do not go looking for the session that built it — it has
ended.** Use the script.

Do it with before/after candidate counts cohort-wide. It changes what we
publish for 2,413 genes.

---

## 7. Parallel sessions

Two sessions are active on the same problem and have been reliable — each
caught real errors of mine by measuring what I asserted:

- **"P022–P038 plasmid ordering and epitope scoring"** — owns the 23-construct
  S4E9 batch. Four sites corrected on findings from here, three of them
  shipping: Q187→F146, after-162→after-161, S271→F263, and ACKR3 recorded as
  282-only and unbuilt. Running a `MIN_LOOP_LEN` recompute whose definition I
  agreed to align to.
- **"Protein tag location predictors"** — owned the scoring model and the
  clearance calibration; **merged #412 and has since ended.** Its `ss3` feature is netsurfp-3.0, a *sequence*
  predictor that never sees the model; it disagrees with DSSP on 18% of
  extracellular residues, biased toward calling coil where the model is
  structured, which is the dangerous direction.

**Unjoined registries are the structural problem behind several of these.** The
Reagent Inventory records what was *built*; `tag_site_public` records what was
*proposed*; nothing links them. `scripts/audit/join_constructs_to_tag_sites.py`
is a first pass over a vendored snapshot (38 constructs, 3 exact matches). A
proposed site that already has a plasmid is the most informative row in the
table and was invisible until today.
