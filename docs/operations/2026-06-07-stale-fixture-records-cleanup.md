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
| OLDREC  | 0.5.0    | predates surface_bind block        |
| FAKE3   | 1.0.0    | predates surface_bind block        |

`FAKE1` (schema 1.1.0) was left in place — it carries the required
fields and renders cleanly. Decision on whether to also retire it is
deferred to the next housekeeping pass.

Final `surface_annotation` distribution after cleanup (18 records):

| Schema | n  | Notes                                                    |
|--------|----|----------------------------------------------------------|
| 2.9.0  | 5  | GPR75, HMGB1, SRC, TACSTD2, TGOLN2 — the v2 archetype reruns |
| 2.6.0  | 2  | CD81, SLC7A5 — one minor cycle stale                     |
| 1.1.0  | 11 | BAX, CLDN18, EGFR, FAKE1, FN1, HSPA5, IZUMO4, KIR2DL1, KLK2, LRP2, LYN |

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
