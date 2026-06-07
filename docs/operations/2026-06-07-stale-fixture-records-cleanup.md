# 2026-06-07 — Stale fixture records cleanup (deploy unblock)

## What happened

The PR #57 merge to `main` (commit `196135b5`) triggered a Cloudflare Pages
build that failed during static-site generation. Root cause: two
records in public D1 `surface_annotation` predated the v1.1 schema and
were missing `deterministic_features.surface_bind`, which the v2.x
viewer page renderer hard-requires:

```text
Error occurred prerendering page "/OLDREC".
TypeError: Cannot read properties of undefined (reading 'surface_bind')
    at bq (.next/server/app/[symbol]/page.js:2:166692)

Error occurred prerendering page "/FAKE3".
TypeError: Cannot read properties of undefined (reading 'surface_bind')
```

Build crashed → no new deploy → production stuck on the pre-merge
build. Symptoms users saw: missing GeneJump freshness dots, missing
deep-dive pages for genes that *should* have been deployed
(TGOLN2 / TACSTD2 / SRC / GPR75 / HMGB1), HMGB1's bench verdict
still showing as the pre-PR-57 value.

## Records dropped

Both clearly named as test fixtures, neither is a real gene:

| Symbol  | Schema   | Notes                              |
|---------|----------|------------------------------------|
| OLDREC  | 0.5.0    | predates `surface_bind` block      |
| FAKE3   | 1.0.0    | predates `surface_bind` block      |
| FAKE1   | 1.1.0    | predates `surface_bind` block (caught on the SECOND retry — only `deterministic_features` itself was present, no `surface_bind` inside) |

The first pass dropped only OLDREC + FAKE3 and left FAKE1 because its
schema string (1.1.0) matched records that DO render cleanly. That call
was wrong — schema-version-string alone doesn't promise the record
carries the v2.x renderer's hard-required field set. The retry deploy
crashed on FAKE1 with the same
`Cannot read properties of undefined (reading 'surface_bind')`
trace, so it joins the OLDREC / FAKE3 retirement.

The right gate is structural, not version-string-based — see
"Systemic guard" below.

Final `surface_annotation` distribution after cleanup (17 records):

| Schema | n  | Notes                                                    |
|--------|----|----------------------------------------------------------|
| 2.9.0  | 5  | GPR75, HMGB1, SRC, TACSTD2, TGOLN2 — the v2 archetype reruns |
| 2.6.0  | 2  | CD81, SLC7A5 — one minor cycle stale                     |
| 1.1.0  | 10 | BAX, CLDN18, EGFR, FN1, HSPA5, IZUMO4, KIR2DL1, KLK2, LRP2, LYN |

Once the rebuild succeeds, the GeneJump freshness dots will use
`max(schema_version)` from `/v1/genes` as the "current" cohort — so
the 5 archetypes render green (current) and the 13 older deep-dives
render orange/stale, which is the intended UX.

## Why a code-free PR

Per `CLAUDE.md`: "Don't paper over JSON ↔ D1 schema drift with
defensive shims / `?.` chains in the loader. Fix the records and
re-sync D1." Adding a defensive `?.` chain on `surface_bind` in
`[symbol]/page.tsx` would have silently rendered the stale-schema
records as partial pages — exactly the failure mode the rule was
written to prevent.

The fix is operational (drop bad rows from D1), not code. This PR
exists only to retrigger the Cloudflare Pages build on `main` — the
deploy webhook fires on `push` to `main`, not on D1 mutation, so the
deploy stays broken until something new lands on `main`.

## Audit pointer

Ran via `D1Client(D1Config.from_env_public())` against
`surfaceome_public` D1; private DB rows untouched (history preserved
for traceability).

## Systemic guard (added 2026-06-07, second pass)

The recurrence-by-FAKE1 made it clear that the existing drift coverage
had a hand-list shape that let new broken records slip through:

* `tests/test_worker_response_shape.py` calls
  `SurfaceomeRecord.model_validate` per gene, but only for a hand-
  curated 4-gene list (EGFR / SRC / GPR75 / HSPA5). Records outside
  that list aren't checked.
* It's also marked `@pytest.mark.network` and gated behind
  `--run-network`, so CI skips it by default.

Replaced with `tests/test_d1_records_schema_drift.py`, which:

1. Enumerates **every** row in public-D1 `surface_annotation` — no
   allowlist to update.
2. For each record, walks a small list of `REQUIRED_PATHS` that mirror
   the v2.x renderer's hard-dereference set (root-level blocks plus
   `deterministic_features.surface_bind` specifically). A missing or
   `None` leaf fails the test with the offending
   `(gene_symbol, schema_version, missing_path)` tuples.
3. Skips when the public-D1 credentials are absent (local `pytest -q`
   without `.env`), so it doesn't trip on fork PRs that legitimately
   can't read secrets. CI runs that wire the secrets enforce it.

`.github/workflows/ci.yml` now passes `CLOUDFLARE_API_TOKEN`,
`CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_D1_SURFACEOME_PUBLIC_ID` into the
python-checks step. Same secrets the d1-backup workflow already uses;
the public-DB scope is read-only by convention.

**Why path-walking, not strict Pydantic**: legacy v1.x records carry
removed-in-v2 fields (e.g. `cell_states` merged into
`accessibility_modulation` at schema 2.5.0). Strict Pydantic
(`extra='forbid'`) rejects them, but the renderer reads specific
fields only and ignores legacy extras. We care about
renderer-crashing drift, not historical-shape drift — matching the
renderer's actual access pattern catches the right thing.

When the renderer dereferences a new field without a `?.` chain,
extend `REQUIRED_PATHS`. Drift in the other direction (renderer stops
touching a field) just leaves a harmless dead entry.
