# Surfaceome public API (Cloudflare Worker)

Read-only public API serving the `surfaceome_public` D1 mirror.

## Endpoints

| Method | Path | Returns |
|---|---|---|
| `GET` | `/v1/health` | `{ ok, n_annotations }` — confirms DB binding |
| `GET` | `/v1/genes` | List of annotated genes (summary fields) |
| `GET` | `/v1/genes/:symbol` | Full `SurfaceomeRecord` JSON (latest schema_version) |
| `GET` | `/v1/orthologs/:symbol` | Mouse + cyno ortholog identity from latest Compara release |
| `GET` | `/v1/benchmark` | Full benchmark truth labels (latest bench_version) |
| `GET` | `/v1/benchmark/:symbol` | Single gene's truth label |
| `GET` | `/v1/benchmark/export.tsv` | Long-format TSV: bench-restricted multi-model sweep (gene × model × variant), 24 cols including truth labels + per-source DB votes joined in. Flat shape of `/v1/benchmark/matrix`. |
| `GET` | `/v1/benchmark/matrix` | Wide nested JSON: per-gene truth + DB votes + per-model verdicts across all prompt variants. Drives the benchmark figures. |
| `GET` | `/v1/catalog` | Genome-wide table — candidate-universe rows × DB flags × latest triage × deep-dive flag (drives the viewer's index) |
| `GET` | `/v1/triage/:symbol` | Triage agent verdicts across (model × variant × replicate) — no costs |
| `GET` | `/v1/triage/export.tsv` | Long-format TSV of every triage run for one `run_id`, 21 cols including DB votes + `uniprot_acc` joined server-side. Default `run_id=mainbench_canonical_v1`; pass `run_id=genome_full_sonnet_ncbi_v1` for the full ~19k-gene sweep. |

All responses are JSON (or TSV where noted). CORS open (`*`). Cache-Control: `public, max-age=60` on list endpoints, `public, max-age=86400` on per-gene records and exports.

## Deploy

Pre-reqs (one-time):

1. The `surfaceome_public` D1 exists on the account. Its UUID lives in
   your `.env` as `CLOUDFLARE_D1_SURFACEOME_PUBLIC_ID` — **not** in the
   repo. The committed `wrangler.toml.example` is a template with a
   placeholder.
2. Schema applied: `cloudflare/d1_public_schema.sql` has been executed
   against it.
3. Wrangler CLI installed locally: `npm i -g wrangler`, or use `npx
   wrangler ...`.

Bootstrap the local `wrangler.toml` from the template (gitignored):

```bash
cd cloudflare/workers/surfaceome_api

# pull the UUID out of the repo-root .env
set -a; source ../../../.env; set +a
sed "s/REPLACE_WITH_PUBLIC_D1_UUID/${CLOUDFLARE_D1_SURFACEOME_PUBLIC_ID}/" \
  wrangler.toml.example > wrangler.toml
```

Deploy:

```bash
npx wrangler deploy
```

Custom domain (one-time, on Cloudflare dashboard):
- Workers & Pages → `surfaceome-api` → Settings → Triggers → Custom Domains → add `api.deliverome.org/surfaceome/*` (or `surfaceome-api.deliverome.org`).

Local dev:

```bash
npx wrangler dev
# → http://localhost:8787/v1/health
```

## Sync from the private DB

This Worker reads what the **sync script** writes. The Worker doesn't pull from private D1 directly — it only reads `surfaceome_public`. To refresh data:

```bash
uv run python scripts/sync_public_d1.py
```

That script reads `surfaceome_agents` (private, contains costs/tokens/prompt text) and writes the column-whitelisted subset to `surfaceome_public`.

## What does NOT live here

- The full prompt text (`prompt_version.text`). Sync script keeps only the SHA + filename.
- Token counts, dollar costs, cache_creation / cache_read tokens — operational, not useful to consumers.
- Cached source bodies (`data/sources/*.json`). Those go to Cloudflare R2 / CDN in a separate sync if/when we want them public.

## Integration with the deliverome Pages project

If you'd rather attach this Worker to the existing `deliverome` Pages project (single deploy umbrella) instead of running it standalone, copy the `[[d1_databases]]` binding from `wrangler.toml` here into the Pages project's `wrangler.toml`, then point the routes block at `api.deliverome.org/surfaceome/*`. The Worker code in `src/index.js` is portable.
