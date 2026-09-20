# Intracellular-bucket pubmed rescue sweep — setup + results

Extends the [`reconfirm_sonnet_no_zero_db_v1`](../reconfirm_sonnet_no_zero_db_v1/README.md)
rescue lane to the population that sweep **deliberately excluded**: the
zero-DB / Sonnet-`no` genes whose `ncbi`-variant reason was one of the
three "confidently intracellular" buckets (`cytoplasmic`, `nuclear`,
`mitochondrial_internal`).

The original README justified skipping them on cost grounds — "pubmed_ncbi
is unlikely to flip them, so the per-call dollars are better spent on the
ambiguous tail." That reasoning no longer holds: the whole sweep came in at
**$70**, and it flipped 148 genes.

## Why this ran

NPM1 is the motivating case. It is zero-DB across all five canonical
sources, and the canonical `ncbi` triage called it `no` / `nuclear` at
**high** confidence with `n_web_searches: 0` — i.e. from model priors, not
literature. Meanwhile
[PMID 40269321](https://pubmed.ncbi.nlm.nih.gov/40269321/) (*Nat Biotechnol*
2026) characterizes cell-surface NPM1 (csNPM1) as an abundant surface
protein on AML blasts and leukemic stem cells but not normal HSCs, and
reports a monoclonal antibody with anti-tumor activity in syngeneic,
xenograft, and PDX models.

Because the reason was `nuclear`, NPM1 was routed into the excluded bucket
and never re-examined. The `pubmed_ncbi` variant flips it to
`contextual` / `cell_state_induced` in **3/3** replicates at $0.016/cell,
citing PMID 40269321 by ID — so the miss was the *exclusion rule*, not
model capability.

## Scope

`gene_list.tsv` — 10,287 rows. Derived as:

    {zero-DB} ∩ {ncbi-variant predicted_verdict = 'no'}
              ∖ {gene_symbols already in run_id genome_full_sonnet_pubmed_ncbi_v1}

| Prior `ncbi` reason | Count |
|---|---:|
| cytoplasmic | 5,544 |
| nuclear | 3,801 |
| mitochondrial_internal | 942 |
| **Total** | **10,287** |

This is the exact complement of the earlier lane: the 2,626-cell
`genome_full_sonnet_pubmed_ncbi_v1` run covers the other six reasons, so
between the two sweeps every zero-DB / Sonnet-`no` gene has now had a
literature-augmented second look.

## Run config

| Param | Value |
|---|---|
| Model | `claude-sonnet-4-6` |
| Variant | `pubmed_ncbi` |
| Replicates | 1 |
| Run ID | `genome_intracellular_pubmed_ncbi_v1` |
| Concurrency | 16 |
| D1 | private `surfaceome_agents` only (`--d1`, no `--publish-public`) |

```bash
uv run python scripts/triage_runner.py \
    --gene-list data/processed/intracellular_rescue_v1/gene_list.tsv \
    --model claude-sonnet-4-6 \
    --variants pubmed_ncbi \
    --replicates 1 \
    --d1 \
    --run-id genome_intracellular_pubmed_ncbi_v1 \
    --concurrency 16
```

## Results

| Metric | Value |
|---|---|
| Cells executed | 10,287 |
| Cost | **$70.06** ($0.0068/cell — cache-warm) |
| Wall clock | 1h49m at concurrency 16 |
| **Rescues (`yes` + `contextual`)** | **148 (1.44%)** |
| — `yes` | 6 (BAIAP3, BLCAP, CRLF3, FNDC11, MPPED1, SYT12) |
| — `contextual` | 142 |

Rescue reason breakdown: `cell_state_induced` 72, `dual_localization` 46,
`tissue_restricted_surface` 19, `classical_surface_receptor` 4, `other` 4,
`multipass_with_exposed_loops` 1, `gpi_anchored` 1, `lysosomal_exocytosis` 1.
Confidence: medium 103, low 45.

The 1.44% flip rate is well below the ambiguous tail's 6.7% (177/2,626) —
the original exclusion judgement was directionally right about *rate*, just
wrong about whether the rate justified the spend.

`rescues.tsv` carries the 148 rescued genes with prior and post reasons.

### RALGDS — resolved on retry

On the sweep, `RALGDS` returned `contextual` with reason
`inner_leaflet_anchored`, which is not a legal reason for a non-`no`
verdict, so the cell failed schema validation after retry and persisted
as an error row. Deleting that row and re-running the single cell under
the same `--run-id` produced a clean `no` / `inner_leaflet_anchored`
(valid, persisted). **It is not a rescue** — the count stands at 148,
and the sweep is now 10,287/10,287 with a valid verdict.

## Citation audit — 7% of citations are misattributed

`pubmed_ncbi` cites PMIDs inline in `verdict_reasoning`, and nothing in the
pipeline validates them. [`scripts/audit/audit_triage_citations.py`](../../../scripts/audit/audit_triage_citations.py)
checks each one; results in `citation_audit.tsv`.

| | count | |
|---|---:|---|
| Citations | 214 | across the 148 rescues |
| PMIDs that don't resolve | **0** | no invented identifiers |
| Resolve **and** name the gene | 200 (93%) | |
| Resolve but the gene is absent from title+abstract | **14 (7%)** | |

**The failure mode is misattribution, not fabrication.** Every cited PMID is a
real PubMed record; 7% are real papers about something else. That is the more
dangerous shape — an invented PMID fails the first existence check anyone runs,
while a misattributed one resolves, renders as a working link, and reads as
legitimate in a tooltip or reference list. Only reading the paper catches it.

All 14 were checked by hand; none is the benign "abstract didn't name the
protein" case:

| Gene | Cited to support | What the papers actually are |
|---|---|---|
| BLCAP | TM topology + membrane IF | yeast isocitrate dehydrogenase · p53 mutants · horse heart myoglobin · lymphotoxin |
| H2BC12 | surface histone | PVA–bacterial cellulose nanocomposite · Annexin A2/PCSK9 · ankle-fracture plating |
| PSMB4 | surface proteasome | HBV capsid particles · glyoxalase III/DJ-1 · SERS detection in spoiled pork |
| APOL6 | surface apolipoprotein | cohesin loading · HLA-F/NK receptors |
| NUDCD1 | surface NudC | curcumin/chromosomal passenger complex · Pterosin B osteoarthritis |

**Failures cluster completely**, which makes them cheap to detect: exactly 5
genes have zero verified citations, and in all 5 *every* citation fails, while
the other 143 have at least one that checks out. So **"all citations fail" is a
usable automated signal that a rescue is confabulated** — no human read needed.
The model appears to confabulate specifically when the literature has nothing,
rather than returning no evidence; the 30 genes that cite nothing at all are
the honest version of the same situation.

Three quality tiers follow:

* **113 genes** — ≥1 verified citation
* **30 genes** — no citations → unsupported, but honest
* **5 genes** — every citation misattributed → actively misleading

All 148 were carried into the deep dive regardless, for consistency with the
rest of the corpus (earlier runs were never citation-audited either).

**These tiers do NOT predict deep-dive outcomes.** The obvious hypothesis —
rank the cohort by verified citations and deep-dive the best-cited first —
is not supported by the result:

| Citation-audit bucket | n | → Likely+ |
|---|---:|---:|
| 4 verified | 9 | 11% |
| 3 verified | 12 | 8% |
| 2 verified | 35 | **0%** |
| 1 verified | 56 | 7% |
| no citations | 30 | 7% |
| confabulated | 5 | 0% |

Non-monotonic, and the spread is noise at these sample sizes. The 5
confabulated genes all landed no/low, but at a 5.4% base rate 5 genes predict
0.27 hits, so observing zero is unremarkable — the filter has no demonstrated
predictive value either. **The audit's value is in flagging unreliable
citations, not in triaging which rescues are worth the spend.**

What the outcome *did* validate: the deep dive independently overrode every
confabulated rescue (APOL6, BLCAP, H2BC12, NUDCD1 → `no`; PSMB4 → `low`),
including BLCAP's `yes` built on four misattributed papers.

## Downstream

The 148 rescues (minus NPM1, already deep-dived ad hoc) were fed to the v2
deep dive under `--cohort-run-id intracellular_rescue_v1_sonnet_2026_09`,
publishing to public D1. Result: **147/147 records, $145.92, 54.6 min** at
concurrency 28 via [`scripts/run_deep_dive_sweep.py`](../../../scripts/run_deep_dive_sweep.py).

**8 genes reached the `likely` tier; none reached `canonical`** — AMPD2,
C1orf56, DCLK1, H2BC26, SNRNP200, SRRM2, SSB, TAX1BP3 (all `moderate`
accessibility; 4 at moderate confidence, 4 at low). Yield is 5.4%, well under
the 18.6% implied by the contextual/zero-DB conversion rate — the better prior
would have been the observed 3.8% for zero-DB/triage-`no` genes. End-to-end
this cost ~$219 for 8 finds (~$27/find), against ~$2.44/find on the original
5,130-gene sweep.

**Caveat — the triage prior was adverse.** The deep dive's
`_D1_TRIAGE_PRIORITY` lists only `ncbi`-variant run_ids, so
`_load_triage_record` never sees either pubmed rescue lane. Every one of these
147 records therefore bakes in `triage_signal = "unlikely"` with the original
`no` reasoning — contradicting the rescue that selected the gene. The gene page
shows this as a `contextual` chip (live from `triage_run_public`) beside a
drawer reading `no` (baked into the record). The bias runs conservative, so the
8 `likely` calls were reached *against* an adverse prior; wiring the
reconciliation rule into `_D1_TRIAGE_PRIORITY` is the fix.

**Caveat — topology is a placeholder.** None of these genes are in the topology sweep cohort, so their
records carry `canonical_topology.tool_version = "placeholder-no-d1-row"` —
`tm_helix_count` / `ecd_length_residues` / `signal_peptide_length` read 0
because nothing was measured, not because a measurement returned zero. A
topology backfill over these accessions is outstanding.

## Reconciliation

The read-side rule from the original lane applies unchanged — defer to the
more inclusive verdict — but queries must now widen the `run_id` filter to
cover **both** rescue lanes:

```sql
AND pn.run_id IN ('genome_full_sonnet_pubmed_ncbi_v1',
                  'genome_intracellular_pubmed_ncbi_v1')
```
