# Full-text coverage expansion (Unpaywall → publisher APIs / OpenAlex / bioRxiv) — evaluated, **deferred**

**Status: DEFERRED — not worth building now.** Captured so the analysis isn't
re-done. Revisit only if the trigger conditions at the bottom are met.

**Date:** 2026-06-02
**Related:** issue #45 (Unpaywall + PDF fallback, shipped in PR #55), issue #51
(shared discovery+triage+fetch), `scripts/probe_pdf_fallback.py`,
`scripts/probe_triage_fetch.py`.

---

## Context

PR #55 added a third body-retrieval fallback to the Deep Dive v2
`plan_trim_select` triage stage: when a `worth_fetching` paper has no PMC JATS,
resolve its DOI → open-access PDF via Unpaywall → pdfplumber → `PaperSection`.
On a real 30-paper MS4A1 sample it recovered `pmc_xml=16, unpaywall_pdf=2,
fell_back=12`. The fallback works and fails gracefully, but recovery is **capped
by publisher 403-blocking of our polite User-Agent** (ASH/Blood, Wiley) and by
genuine paywalls (Oncogene, BBRC) — not by our code.

This doc records the options we evaluated to push full-text coverage *further*,
and why we're not building any of them right now.

## Hard constraints (set by the project)

- **Non-profit. No publisher licenses, no journal fees.** This removes the
  entire "subscribe / pay for entitlement" class of solutions.
- **Keep a polite, best-practices User-Agent.** No browser-UA impersonation to
  evade publisher bot-blocks (ToS/ethics).
- We *do* redistribute small, substring-anchored portions of text (≤600-char
  clips) — defensible as fair use, but it constrains what we may re-host.

## Decision summary

| Option | Adds full-text bodies? | Verdict | Why |
|---|---|---|---|
| **Publisher TDM APIs (Wiley, Elsevier, …)** | Yes, for entitled content | ❌ Rejected | Require a license/institutional token; we can't pay. Wiley TDM also restricts redistribution. |
| **OpenAlex (self-hosted in S3/DB)** | **No** | ❌ Not worth it | OpenAlex is a metadata+abstract+citation graph, **not** a full-text repo; its OA links == the Unpaywall data we already use. ~0 additional bodies; hosting 200M+ records is a big lift. Use the free API on-demand if we ever want its citation/concept signal. |
| **bioRxiv bulk full text (requester-pays S3)** | Yes, preprints only | ⏸ Deferred | Technically clean and *license-clear*, but modest ROI right now (see funnel) and a real one-time cost + build. Best value is the orphan/novel-target tail. |
| **EPMC-preprint `fetch_fulltext` generalization** | Yes, funded-preprint subset | 🟢 Cheap adjacent win (separate) | Small, free, no new infra — relax `fetch_fulltext`'s `PMC\d+`-only guard to use EPMC full text for any `inEPMC=Y` record. Track separately from this doc. |

## What we verified (live, 2026-06-02)

- **OpenAlex ≠ full text.** Per-gene OpenAlex counts are the *same order of
  magnitude* as our existing Europe PMC discovery, and often **fewer** (EPMC's
  biomedical synonym handling wins on MS4A1/TFRC; OpenAlex only edges ahead on
  the orphan GPR75). OpenAlex hosts abstracts + OA *links* (== Unpaywall), not
  bodies. Conclusion: it does not move the full-text needle.
- **bioRxiv has no usable per-paper full-text route.** `api.biorxiv.org/
  details/biorxiv/{doi}` works and returns the per-preprint **`license`**
  (e.g. `cc_by_nc_nd`, `cc_no`) + a `jatsxml` URL — but that URL, and the
  `.pdf`, both **403** (same bot wall as the website). The **only** un-blocked
  full-text source is the **Requester-Pays S3 TDM bucket**
  (`s3://biorxiv-src-monthly`, `.meca` packages, ~6 TB, ~$0.09/GB ≈ **$500**
  to pull all of it). Requester-Pays is an **AWS bandwidth cost, not a
  publisher license** — the content is free.
- **bioRxiv blesses text mining.** Authors consent to TDM at submission;
  bioRxiv "explicitly overrides the less open licenses for text mining," and
  calls bulk TDM "consistent with fair use." The one hard rule: **don't
  re-host full text / derivatives; link back to bioRxiv.** ~18% of preprints
  are CC-BY (portion reuse with attribution explicitly OK); the rest →
  fair-use snippet + link-back.

## Funnel estimate (why ROI is modest now)

Per gene: ~150 discovered → ~25 `worth_fetching` → ~15 fetched today (~60%).
Of the ~10 failures: ~4 no-DOI notices, ~4–6 paywalled/403 **published**
papers, ~1–2 bioRxiv preprints.

- **bioRxiv bulk** recovers the ~1–2 preprint failures/gene → ~60% → **~65–67%**
  recovery. Cohort-wide (papers are shared across genes), ~**1–5k unique
  additional bodies**, skewed recent and to **orphan/novel surface targets**
  where a preprint may be the only source.
- **OpenAlex** recovers **~0** full-text bodies (different axis: discovery +
  abstracts + ranking).
- **Neither breaks the real wall:** the paywalled/403 *published* landmark
  papers (Blood/Wiley/AACR) that issue #45 cared about. bioRxiv doesn't touch
  them (not preprints); OpenAlex doesn't (same OA links). That gap needs
  publisher TDM or institutional access — which our constraints rule out.

## If/when revisited: bioRxiv ingestion architecture

Fits the existing Cloudflare **R2 + D1 + Worker** stack (no new platform).

```
INGEST  (periodic batch w/ AWS creds; boto3 / s5cmd --request-payer requester)
  s3://biorxiv-src-monthly   pull .meca        unzip (.meca is a ZIP container)
   Back_Content/   (one-time backfill)   ├─ JATS XML  → R2 (PRIVATE; full text, never served)
   Current_Content/ (monthly increments) ├─ parse JATS → sections + DOI/title/abstract
  api.biorxiv.org/details  → license/ver  └─ UPSERT → D1 biorxiv_fulltext
                                              (doi, version PK; title, abstract, license, r2_key, sha)
                                              + optional D1 FTS5 over title+abstract

DISCOVERY  (per gene — FREE; OpenAlex/EPMC already index bioRxiv abstracts)
  gene → candidate 10.1101/… DOIs

FETCH  (per preprint)
  Worker GET /biorxiv/fulltext/{doi} → D1 → R2 JATS → parse_jats_sections()  ← REUSE, no pdfplumber
         license-gate clips; emit short quotes + link back to bioRxiv DOI

PIPELINE
  _fetch_body_drafts: 4th fallback — a 10.1101/… DOI → bioRxiv Worker (instead of the 403-ing PDF)
```

Design principles:
1. **JATS, not PDF** — reuse `parse_jats_sections`; skip pdfplumber for preprints.
2. **Private store, public snippets, link-back** — satisfies bioRxiv's "don't
   re-host" rule; mirrors the repo's private-D1 / public-mirror split and the
   "never ship full prose" TSV rule.
3. **License-gated redistribution** — store per-preprint license; CC-BY* →
   attribution portion reuse; else → fair-use snippet + link-back. Add a row to
   the per-source licensing table. Per-paper cap on total quoted chars.
4. **Discovery is already free** (OpenAlex/EPMC); we'd build only the full-text
   store. D1 FTS index optional (self-contained search).
5. **Withdrawals** fold into the existing `RetractionIndex` / retraction gate.

### Keeping it updated (the steady-state job)

- **Update unit = the current month's `Current_Content/<Month_Year>/` folder.**
  New preprints *and new versions of old ones* (a 2021 v3 deposited this month)
  both land there — so you **never re-scan `Back_Content/` (6 TB) again**.
- **Loop:** monthly cron → `s3 ls --request-payer requester` current (+ just-
  closed) month → diff vs a D1 ingested-`.meca` manifest (key+ETag) → pull only
  new/changed → unzip → JATS → idempotent UPSERT on `(doi, version)`. ~4–5k
  packages/month ≈ 50–100 GB ≈ **$5–9/month**. No DOI→key map needed for
  increments (pull the DOI out of each `.meca` manifest).
- **Home:** a monthly **GitHub Actions cron**, mirroring `d1-backup.yml`
  (Actions secrets hold AWS + Cloudflare creds). The metadata API is a free
  completeness cross-check (alert if S3 count diverges from `details/{range}`).
- **Reproducibility:** content SHA + a `corpus_synced_through` watermark, like
  `resolver_version` / `bench_version`.

### Cost / effort if built

- One-time backfill: ~$500 AWS transfer (XML-only R2 storage afterward is small,
  tens of GB, no egress fees). Or **$0 upfront, forward-only** — ingest only new
  months, accept no historical coverage (selective historical fetch is hard:
  `.meca` aren't DOI-addressable, so a complete DOI→XML index needs the full
  one-time scan).
- Build: ingest script + D1 schema + one Worker endpoint + the 4th-fallback
  wire-in. ~A few days; all mirrors existing scripts (`d1_client`,
  `surfaceome_api` Worker, `d1-backup` workflow).
- **First spike step (cheapest de-risk):** one `s3 ls --request-payer requester
  s3://biorxiv-src-monthly/Current_Content/` (a few cents) to confirm the
  monthly-folder structure + revisions-land-in-current-month assumption, then
  pull a *single month* (~$1) and validate `.meca → JATS → parse_jats_sections`
  end-to-end before any backfill spend.

## Why deferred

The realistic payoff (~+5–7 points of `worth_fetching` recovery, ~1–5k unique
bodies, preprint-only) doesn't justify the one-time cost + ongoing maintenance
*right now*, given that the highest-value gap (paywalled published papers) is
untouched by any of these options under our no-license constraint. The Unpaywall
+ PDF fallback already in PR #55 captures the freely-downloadable OA wins.

## Revisit triggers

Build the bioRxiv ingestion if **any** of these become true:
- Orphan/novel surface targets become a focus and their evidence is
  preprint-bound (the case where this has the highest marginal value).
- A grant or institutional budget covers the one-time backfill + build.
- We see, via an instrumented `probe_triage_fetch.py` run across a 20–30 gene
  sample, that the *measured* preprint fraction of `worth_fetching` failures is
  materially higher than the ~1–2/gene this analysis assumed.

## Adjacent cheap win (do separately, not part of this deferral)

Generalize `fetch_fulltext` (currently `PMC\d+`-only) to use EPMC full text for
any `inEPMC=Y` record, keyed on the record's own `source`/`id`. Picks up the
funded/COVID preprint subset that Europe PMC already hosts as JATS — free, no
new infra, reuses `parse_jats_sections`. Track as its own small issue.

## Update — additional measured findings (2026-06-02, later)

Follow-up investigation that sharpens the conclusions above:

- **CORE (core.ac.uk) evaluated, doesn't help our failures.** CORE hosts
  full text *when a repository deposited it*, but on our actual blocked DOIs
  (Wiley, ASH, bioRxiv, Oncogene) CORE held **metadata only** — its
  `downloadUrl` relayed the *same* bot-blocked publisher URLs (per CORE's own
  docs, a non-CORE `downloadUrl` = not hosted). Its free ~395 GB bulk dump is
  attractive *if* green-OA coverage of our blocked set proves high, but the
  quick probe says it's low. Revisit only with a key-based sweep.
- **Preprints have no PMID → structurally excluded today.** bioRxiv/Research
  Square/Preprints.org records carry only a `PPR…` id + DOI; our `Paper` model
  requires a PMID and `paper_source_id`→`UNKNOWN` skips them. So **adding
  bioRxiv needs a data-model change (PMID-optional, DOI/PPR-keyed) on top of the
  `.meca` store** — a prerequisite this doc originally missed. And **bioRxiv is
  only ~30% of discovered preprints** (Research Square dominates), so a
  bioRxiv-only build under-covers the preprint axis.
- **The biggest *addressable* loss is publisher bot-blocking of OA, not closed
  access.** Of papers we still miss, ~⅓ are OA-but-bot-blocked (ASH/Blood,
  Wiley, AME landing-page redirects, PNAS), ~½ genuinely closed. But the blocked
  pool is **mostly review/commentary/tangential** — only ~¼–⅓ are useful
  primary surface-biology papers, and the few gems are structural/mechanistic
  (PD-L1 structure, CEACAM–HopQ, MET surface presentation). So heroic
  bot-block recovery has low ROI; *targeted* recovery (repository fall-through)
  is the right altitude.
- **Two cheap wins were shipped in PR #55** rather than deferred: (a) the picker
  now tries *all* OA locations (publisher-blocked → repository fall-through),
  and (b) font-aware run-in/bold heading parsing recovers JCI/PNAS-style PDFs.
  Together they lifted the 13-gene Unpaywall recovery ~7 → ~10, including the
  CD19 antigen-loss (JCI) and CEACAM5 IgV-structural (PNAS) papers. A small
  remaining parser gap (genuinely headingless short-form: 2-page comments /
  reviews) is not worth chasing.
