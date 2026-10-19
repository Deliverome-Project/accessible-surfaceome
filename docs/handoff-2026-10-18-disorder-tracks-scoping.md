# Handoff — scoping the `disorder_tracks` wiring

**Date:** 2026-10-18 · **Branch:** `claude/tag-site-enrichment-pipeline` · PR [#414](https://github.com/Deliverome-Project/accessible-surfaceome/pull/414)

The task was: **scope what wiring `disorder_tracks` would cost — before/after
candidate counts cohort-wide, and how placements shift against validated
junctions.** That measurement is **NOT done.** What follows is the ground work,
and one error of mine to correct rather than inherit.

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
