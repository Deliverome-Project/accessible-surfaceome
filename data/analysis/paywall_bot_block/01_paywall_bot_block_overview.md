# Paywall & bot-block landscape for the v2 surfaceome deep-dive cohort

Single-panel horizontal stacked bar showing how 150 random genes from
the 6,521-gene v2 deep-dive cohort
(`candidate_universe_v2.tsv`) distribute across the four
operationally-relevant body-fetch outcomes. For each gene, the top-5
most-recent PubMed papers were classified (n = 680 total) by which
path through the production fetch chain would succeed.

## The four buckets

| Bucket | Share | What happens |
|---|---|---|
| **PMC** | **62%** (421/680) | Paper has a PMC ID → PMC native fetch returns the full body. The happy path. |
| **Unpaywall** | **14%** (93/680) | No PMC, but Unpaywall surfaces an OA copy from a non-blocked publisher / repository. The pipeline's PDF fallback succeeds. |
| **Bot-blocked** | **0.7%** (5/680) | Unpaywall's *only* OA path is a publisher that 403s our polite User-Agent (Wiley, ASH/*Blood*, Elsevier, OUP, MDPI, bioRxiv, medRxiv, JBC). Pipeline falls back to abstract. |
| **No OA** | **24%** (161/680) | Unpaywall returns `is_oa=false` (truly paywalled) OR has no record. Pipeline falls back to abstract. |

**Operational full-body success rate: ~76%** (PMC + Unpaywall). The
remaining ~24% degrades to abstract-only — note this isn't a wasted
paper; the abstract still produces evidence claims via the pipeline's
`keep_abstract` route, just at lower per-paper detail.

## Methodology + known biases

### Bot-block list (empirically HEAD-tested 2026-06-07)

The bot-block regex matches the publishers that return HTTP 403 to our
polite UA: **biorxiv.org, medrxiv.org, wiley.com, ashpublications.org,
sciencedirect.com, jbc.org, academic.oup.com, mdpi.com**. Not blocked
(returned 200): PMC, Springer Link, Nature (when OA), PLOS. Per-host
exclusion: a paper is only in the "bot-blocked" bucket when *every*
OA path Unpaywall surfaces routes through one of the blocked hosts.

### Why the bot-block bucket is small (0.7%) despite many hosts blocking us

Counter-intuitive, but holds up to scrutiny: most papers Unpaywall
classifies as OA have **multiple** `oa_locations`. Even a Wiley-only
paper often has a Green-OA repository or a PMC mirror later in the
list. The pipeline iterates the alternatives best-quality-first, so
the only failure mode is "all paths are 403". That happens for ~0.7%
of cohort papers, not the 10-20% the publisher-list size might
suggest.

### Selection bias: PubMed search ≠ EuropePMC search

The 150-gene sample used `NCBI esearch.fcgi?db=pubmed&sort=date` to
get the top-5 most-recent papers per gene. **The production pipeline
uses EuropePMC**, which also indexes preprints (bioRxiv, medRxiv).
This sample therefore *under-represents* preprints relative to what
the production pipeline actually fetches.

Direction of bias: preprints are mostly hosted on bot-blocked servers
(bioRxiv/medRxiv 403 us), so the production pipeline's bot-block rate
is probably **higher** than the 0.7% shown here. Magnitude is bounded
because (a) most well-cited preprints get published to a non-blocked
journal within ~12 months and gain a PMC mirror, and (b) the
selector preferentially picks fetchable papers when both fetchable
and unfetchable alternatives exist for the same gene-claim.

### Selection bias: "most-recent" inflates OA

Newer papers are MORE likely to be OA (recent OA mandates from
funders + journals). A random-walk sample across publication years
would have lower PMC + Unpaywall rates. The 76% success rate here is
the optimistic end of the cohort distribution.

## Run

```bash
uv run https://gist.githubusercontent.com/beccajcarlson/76242a980c18d98ee3a2fc759a756422/raw/make_paywall_bot_block_overview.py
```

PEP 723 inline-deps script — `uv` installs matplotlib / seaborn / httpx
on first run, then reads the cohort bucket data from the public repo at
`raw.githubusercontent.com/Deliverome-Project/accessible-surfaceome/main/data/analysis/paywall_bot_block/cohort_150_4bucket.json`.

Outputs two files in the current directory:
- `paywall_bot_block_overview.pdf` (vector, gist URL in `Subject` info field)
- `paywall_bot_block_overview.png` (raster, gist URL in `Source` tEXt chunk)

## Data sources

| File | Source |
|---|---|
| `cohort_150_4bucket.json` | 150 random genes from candidate_universe_v2.tsv × top-5 most-recent PubMed papers each (n=680). Per-paper bucket assigned by combining NCBI esummary (DOI + PMC ID lookup) with the Unpaywall API, classified against an empirically-verified bot-block host list. |
| Bot-blocked publisher list | HEAD-tested 2026-06-07 with the production UA: biorxiv.org, medrxiv.org, wiley.com, ashpublications.org, sciencedirect.com, jbc.org, academic.oup.com, mdpi.com all return 403. |
| Cohort definition | `data/processed/candidate_universe/candidate_universe_v2.tsv` (6,521 genes; Sonnet yes/contextual ∪ ≥1 DB-vote). |

## Canonical generator

The in-repo generator lives at
[`scripts/paywall_bot_block_overview.py`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/scripts/paywall_bot_block_overview.py)
and reuses `src/accessible_surfaceome/audit/_plotting_config.py` for
the Deliverome categorical palette + Manrope brand font. This gist
inlines those bits so the standalone version stays self-contained.
