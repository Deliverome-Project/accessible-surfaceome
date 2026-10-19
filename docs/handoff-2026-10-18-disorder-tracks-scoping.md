# Handoff — scoping the `disorder_tracks` wiring

**Date:** 2026-10-18 · **Branch:** `claude/tag-site-enrichment-pipeline` · PR [#414](https://github.com/Deliverome-Project/accessible-surfaceome/pull/414)

The task was: **scope what wiring `disorder_tracks` would cost — before/after
candidate counts cohort-wide, and how placements shift against validated
junctions.**

**It is now done, and the answer is: do not wire it.** The measurement was run by
the `claude/disorder-tracks-scoping-0ee4b1` session over 2,470 genes (97.6% of
published disorder sites) plus the 25-site internal corpus. Headlines, with the
sections below kept as the ground work they were written as:

- **No placement accuracy to recover.** All three arms place at a **median 2 aa**
  from the validated junction on the internal corpus; paired sign test A vs B
  **p = 0.508**. My 40 aa framing (§2) was measured on N-terminal junctions and
  has **no analogue** on internal sites.
- **Wiring it would mislabel a third of its own output.** `DISORDER_PCT_MIN = 60`
  is a within-protein rank with no absolute floor, so it admits the top 40% of
  every protein regardless of whether the protein has disorder. **33.4% of arm
  B's post-NMS sites (7,772 / 23,281) carry their own pLDDT ≥ 70** while shipping
  `disorder.py`'s fixed rationale "within a low-pLDDT disordered extracellular
  run" — false for them, and inside `surface_loop`'s territory. Arm A: **0 of
  15,561**. A provenance defect, not a count change.
- **Counts** (pool → post-NMS): A 149,356 → 15,561; B 228,187 → 23,281 (+50%);
  C 201,697 → 21,724 (+40%). NMS does not absorb it — the cap binds on only
  207→433 genes. Median Jaccard of B and C against published is **0.000**: for
  over half of genes, wiring shares zero residues with what ships.
- **B ≈ C**, so C's two extra predictors do not earn their D1 dependency
  (median Jaccard 0.188, totals 7% apart) — but neither is ≈ A.
- **The one real win is ordering.** Top-ranked site median **79 aa → 11 aa**,
  sign test **p = 0.006** (n = 15). Worth capturing as a tie-break *inside* the
  existing `plddt < 70` run, not as its threshold. Not implemented.
- **Caveat they stated rather than buried:** their cohort arm-A reconstruction
  totals 15,561 where production published 12,283 on the same genes (1.27×,
  exact per-gene match 31.8%), because D1 signals cannot model the hazard veto
  (`hazard_res=∅` leaves every `feature_dist` infinite) or `_drop_near_terminus`
  (needs CA coords). Both are arm-identical, so between-arm ratios hold; the
  absolute arm-A count is not production's. The corpus arm has no such caveat.

**Two corrections to my ground work below, both verified here:**

1. **`disorder_public` IS committed** — `cloudflare/migrations/disorder_public.sql`
   (`c159c7729`). It is absent from `d1_public_schema.sql` only, which is a
   documentation gap, not a missing schema. §1 said otherwise.
2. **The `ss3` substitution caveat in §4 is smaller than I wrote.** Production's
   `per_residue_ss` is pydssp 3-state H/E/C ([signals.py:127](../src/accessible_surfaceome/tag_sites/signals.py#L127)),
   the same alphabet as D1's `ss3`, so `LOOP_SS = {"C","T","S","G"}` reduces to
   `{C}` on both sides and T/S/G never appear in production either. Like-for-like
   alphabet; only the calls differ.

**A latent bug they found that is independent of all this and still live:**
`netsurfp-3.0` is the highest-weighted track in `consensus` (2.0) and scores only
the **first 400 residues**. 1,591 of 2,470 cohort genes (**64%**) are longer,
median 698 aa. So its "within-protein percentile" is really a within-first-400
percentile, and the consensus weighting **steps discontinuously at residue 400**
(`consensus` only adds a predictor where `res <= len(values)`). That is a defect
in `disorder_tracks.py` whether or not the module is ever wired in.

Their full numbers: `disorder-tracks-scoping-RESULTS.md` in the side-session
notes folder.

---

## 1. The finding, which stands

**A complete module reads the disorder data from D1, and nothing calls it.**

`src/accessible_surfaceome/tag_sites/disorder_tracks.py` (105 lines) has
everything: `fetch_tracks(client, accessions)` querying `disorder_public`,
`_decode` (one byte per residue, inverting pLDDT), `within_protein_percentile`,
and `consensus` (weighted mean of per-predictor percentiles, NetSurfP-3.0 at
2.0). It landed whole in `075d5a577` alongside the SP-interval work.

- **`fetch_tracks` is called by nothing** — verified by grep across `src`,
  `scripts`, `tests`.
- `consensus` *is* imported into `run.py` and used in `compute_signals`, but only
  under `if disorder_tracks:` — and no caller passes that argument, so the branch
  is dead. `run_gene` has no such parameter at all.
- So `disorder._flexible_runs` always takes its fallback path: contiguous
  extracellular runs of `plddt < 70` (`PLDDT_DISORDER_MAX = 70.0`), and the
  ranking key `-disorder.get(res, 0.0)` is uniformly 0.0, collapsing to RSA.

**Scale:** 12,584 deterministic `disorder_junction` sites across 2,111 genes —
**52% of the 24,016 internal deterministic sites** in `tag_site_public` (counted
by `site_id LIKE '%-disorder%'`).

**The data is there and is not the problem.** `disorder_public` on public D1,
version `dis_2026_09_28`, 20,224 rows per predictor over 11,395 canonical
accessions (plus `dis_ortho_2026_09_28`, 12,634 ortholog rows):

| predictor | `disorder_hex` | `plddt_hex` | `rsa_hex` | `ss3` |
|---|---|---|---|---|
| metapredict | 20,224 | — | — | — |
| netsurfp-3.0 | 20,224 | — | 20,224 | 20,224 |
| alphafold-disorder | — | 19,877 | 19,877 | — |

Note the table is **absent from `cloudflare/d1_public_schema.sql`** despite being
served; worth adding.

**The wiring itself is small** and has a just-landed precedent: `propeptide` was
threaded through `run_gene` → `compute_signals` in `cfbcaee42` in exactly the
shape this needs. It is a `fetch_tracks` call in `scripts/regenerate_tag_sites.py`
plus one threaded parameter. The expensive part is not the code, it is
re-deriving 2,111 genes.

---

## 2. My error — do not inherit the 40 aa framing

I claimed the proxy costs a median **40 aa** against validated junctions where
the predictors cost **3 aa**, and that this is the price being paid across those
12,584 internal sites. **The number is real but it is measured on a different
population, and I did not check before propagating it.**

The table lives in `disorder_tracks.py`'s own docstring:

    netsurfp-3.0         median  3 aa   86% within 5 aa
    metapredict          median  3 aa   74%
    alphafold-disorder   median  2 aa   76%
    pLDDT run (lane)     median 40 aa   15%

It is scored against Tedman's junctions. **Every one of the 946 rows in
`data/tag_sites/tedman_gpcr_controls.tsv` is `site_kind: terminal_n`** — 109
carry a `junction_after_residue`, 67 of those canonical. Those are
signal-peptide-proximal N-terminal placements, which is `sp_interval.py` and
`terminal.py` territory. **They are not internal disorder-lane sites.**

So whether rank-vs-run placement matters for *internal* junctions is **open**.
The internal corpus is `data/tag_sites/positive_controls.tsv`: 30 rows, **25
`internal`** and 5 `terminal`. `disorder.py`'s ranking comment cites both
populations for the *percentile threshold* (`DISORDER_PCT_MIN = 60.0`: "Tedman's
junctions sit at the 88th-93rd within-protein disorder percentile and our curated
internal positive controls at the 73rd-83rd"), which is a legitimate use of both.
The 3-vs-40 **placement** comparison is N-terminal only.

**Where I propagated the wrong framing, all needing correction:**

1. PR #414 body — the "A signal nothing supplies is inert" section.
2. `docs/handoff-2026-10-19-tag-site-gates.md` §3a.
3. `tests/test_tag_sites_signal_wiring.py` — the `KNOWN_UNWIRED["disorder_tracks"]`
   cost string. **This one matters most**: that string is the deliberate-edit
   record of what the gap costs, and it currently overstates it.
4. Memory `inert-optional-signal-bug-class.md`.

The *structural* finding in all four — a signal nothing supplies is inert while
the lane's tests pass — is unaffected and correct. Only the magnitude is
unestablished.

---

## 3. The cheaper option I did not get to test

`disorder_tracks.py` says: *"AlphaFold-disorder **is** 1 - pLDDT, so the gap is
not the signal but how it is read: a contiguous-run threshold versus a
within-protein rank."* And `_decode` confirms it — the `alphafold-disorder` track
is literally `1 - plddt_hex/255`, with `alphafold-disorder` scoring median 2 aa
against the lane's pLDDT-run 40 aa.

**If that holds for internal sites, the fix needs no D1 dependency at all**: the
lane already has `signals["plddt"]` from the model it fetches, so
rank-transforming it through `within_protein_percentile` would capture most of
the gain with no new data source and no `fetch_tracks` call. That belongs in the
comparison as a **third arm**, and it may be the right answer.

Three arms to measure, not two:

| arm | disorder signal | needs |
|---|---|---|
| A — current | contiguous `plddt < 70` run | nothing (status quo) |
| B — rank-transformed pLDDT | `within_protein_percentile(1 - plddt)` | nothing new |
| C — full consensus | `consensus()` over all three predictors | `fetch_tracks` + D1 |

If B ≈ C, ship B.

---

## 4. How to run the comparison without AFDB

The blocker on any cohort-wide re-derive is AlphaFold DB: `/files/` IP-bans
bursts with bare 429s, ~9 s/request, go quiet ~15 min to clear. 2,111 genes is
multi-hour. **But every signal the disorder lane gates on is already in
`disorder_public`** — `plddt_hex` (alphafold-disorder), `rsa_hex` (netsurfp or
alphafold), `ss3` (netsurfp) — plus topology from `topology_public`. So the
before/after can be computed from **D1 reads alone, zero AFDB fetches**.

Design that keeps it honest:

- **Vary only the disorder signal.** Hold pLDDT, RSA, SS, topology and
  `feature_dist` identical across arms (`hazard_res=∅` is fine — it is the same
  in both, so the delta is attributable to the disorder track alone).
- **Then validate the substitution on a small AFDB sample.** The `ss3` in D1 is
  netsurfp-3.0, a *sequence* predictor that never sees the model; it disagrees
  with DSSP on ~18% of extracellular residues, biased toward calling coil where
  the model is structured — the dangerous direction, since `surface_loop`'s
  `LOOP_SS` gate and `disorder`'s `_junction_tier` both read `ss`. So the
  D1-signal "before" is **not** production's before. Check ~20 genes with real
  models to confirm the delta survives.
- When reading public D1 at scale, **pace it to ~2 genes/second** — an unpaced
  sweep caused user-facing 500s on 2026-09-28.

Useful queries are in
`/private/tmp/claude-501/.../scratchpad/` (`lane_count.py`, `kw0336.py`) but
rewrite rather than trust them; they were exploratory.

---

## 5. What a complete answer looks like

1. Candidate counts per arm, cohort-wide: total sites, sites per gene, and how
   many genes gain or lose a site. `select_representatives` caps at 20 with
   8-residue spacing, so a change in the candidate pool may not move the
   published count — **report both pool and post-NMS counts**, they answer
   different questions.
2. Placement shift on the **internal** corpus (`positive_controls.tsv`, 25 sites).
   25 is small; say so, and give the per-site table rather than only a median.
3. Re-derive cost: genes affected × AFDB pacing, and whether arm B avoids it.
4. A recommendation between A, B and C.

Then correct the four places in §2 with whatever the measurement says.

---

## 6. Standing constraints

- No `Co-Authored-By` or AI-attribution trailer in commits or PR bodies.
- PR titles: Conventional Commits, scope from the allowlist (`tools`, `agents` here).
- `bash scripts/check-py.sh` before pushing (currently green: 2,913 passed).
- Gene identity by `hgnc_id`, never a bare symbol; sequence positions by sha256
  of the sequence.
- **Do not change what is published** as part of scoping. PR #414 is open and
  deliberately republishes nothing.
