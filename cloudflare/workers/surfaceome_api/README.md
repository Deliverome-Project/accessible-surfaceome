# Surfaceome public API (Cloudflare Worker)

Read-only public API serving the `surfaceome_public` D1 mirror.

## Endpoints

Grouped by scope: **SurfaceBench** (labeled eval) → **genome-wide** sweep → per-gene **deep dive**.

### SurfaceBench (147-gene labeled eval)

| Method | Path | Returns |
|---|---|---|
| `GET` | `/v1/benchmark` | Full benchmark truth labels (latest bench_version) |
| `GET` | `/v1/benchmark/:symbol` | Single gene's truth label |
| `GET` | `/v1/benchmark/export.tsv` | Long-format TSV: bench-restricted multi-model sweep (gene × model × variant), 24 cols including truth labels + per-source DB votes joined in. Flat shape of `/v1/benchmark/matrix`. |
| `GET` | `/v1/benchmark/matrix` | Wide nested JSON: per-gene truth + DB votes + per-model verdicts across all prompt variants. Drives the benchmark figures. |

### Genome-wide (~19k human protein-coding genes)

| Method | Path | Returns |
|---|---|---|
| `GET` | `/v1/catalog` | Genome-wide table — candidate-universe rows × DB flags × latest triage × deep-dive flag (drives the viewer's index) |
| `GET` | `/v1/triage/:symbol` | Triage agent verdicts across (model × variant × replicate) — no costs |
| `GET` | `/v1/triage/export.tsv` | Long-format TSV of every triage run for one `run_id`, 21 cols including DB votes + `uniprot_acc` joined server-side. Default `run_id=mainbench_canonical_v1`; pass `run_id=genome_full_sonnet_ncbi_v1` for the full ~19k-gene sweep. |

### Deep dive (per-gene)

| Method | Path | Returns |
|---|---|---|
| `GET` | `/v1/genes/:symbol` | Full `SurfaceomeRecord` JSON (latest schema_version) |
| `GET` | `/v1/orthologs/:symbol` | Mouse + cyno orthologs for any gene from latest Compara release (broad genome-wide raw Compara — full-length identity; distinct from the deep ECD/topology orthologs inside the per-gene record) |
| `GET` | `/v1/genes` | List of annotated genes (summary fields) |
| `GET` | `/v1/health` | `{ ok, n_annotations }` — confirms DB binding |

All responses are JSON (or TSV where noted). CORS open (`*`). Cache-Control: `public, max-age=60` on list endpoints, `public, max-age=86400` on per-gene records and exports, each with `stale-while-revalidate` + `stale-if-error` so the edge serves a stale copy instantly on a miss/revalidate and keeps serving it if the Worker errors (this is what absorbs the catalog's historical CPU-budget 503s).

## Caching & abuse protection

The API is intentionally public + unauthenticated — the data is
publish-intended. The risk it guards against is **cost / availability**
(D1 bills per row read; the catalog handler is CPU-heavy), not access.
Four layers:

1. **Aggressive edge caching** carries the load (the TTLs above). Don't
   shorten them to chase freshness — see purge below.
2. **Cache rule** (apply once / after a TTL change with
   [`scripts/apply_cf_edge_rules.py`](../../../scripts/apply_cf_edge_rules.py)
   — dry-run by default, `--execute` to apply) that makes the cache key
   **ignore the query string**, so `?_=<random>` can't bust the cache and
   amplify D1 load. Cache Rules are available on every plan.
3. **Per-IP rate limiting in the Worker** via the native Workers Rate
   Limiting binding (`env.RATE_LIMITER` / `RATE_LIMITER_HEAVY`, configured
   in `wrangler.toml`). In-colo, free on every plan, **not KV** (no
   per-request storage cost). A generous ceiling on the route + a tighter
   one on `/v1/catalog` + the `*.tsv` exports; over-limit → `429`. We use
   the Worker binding because Cloudflare's zone-level **WAF Rate Limiting
   Rules** are a Pro/Business+ feature — `apply_cf_edge_rules.py --only
   ratelimit` applies those instead, for zones that have them.
   Cloudflare's always-on L7 DDoS protection (free) handles volumetric
   attacks underneath either one.
4. **Purge-on-publish.** `cloud/surface_annotation.publish_record` purges
   the per-gene + `/v1/catalog` + `/v1/genes` cache entries (targeted
   by-URL, never `purge_everything` — this Worker shares the
   `deliverome.org` zone) right after the D1 write. That's what lets the
   TTLs stay long *and* a republished record go live immediately, instead
   of being stale for up to a day. Needs `CLOUDFLARE_ZONE_ID` + a Cache
   Purge scope on the token; missing either soft-skips with a warning.

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

## Feedback flow (per-gene reader submissions)

Three endpoints added 2026-05-25, driven by docs/superpowers/specs/2026-05-25-feedback-button-design.md.

### `POST /v1/feedback/submit`

Submitter sends from the gene-page modal. Server-side: validates input,
verifies the Turnstile token via siteverify, applies a 5-per-IP-per-hour
rate limit (Workers KV), inserts the row into `surfaceome_agents.feedback`
(private DB), and sends a Resend notification email to the maintainer
containing the submission details + magic-link approval buttons.

Body (JSON):
```json
{
  "gene":             "SRC",
  "uniprot_acc":      "P12931",
  "name":             "...",
  "email":            "...",
  "subject":          "Surfaceome SRC (P12931) entry update request",
  "comment":          "...",
  "public_requested": false,
  "referrer":         "https://surfaceome.deliverome.org/SRC",
  "user_agent":       "Mozilla/5.0 ...",
  "site_version":     "8faeb338",
  "turnstile_token":  "..."
}
```

Responses: 200 `{ ok: true, id }`, 400 `{ error: "invalid_*" | "invalid_json" | "turnstile_failed" }`, 429 `{ error: "rate_limited" }`.

### `GET /v1/feedback/moderate?id=<id>&action=<public|discard>&t=<hmac>`

The magic-link approval endpoint. Verifies the HMAC-signed token, updates
the row's status, and (on `action=public`) copies a sanitized subset to
`surfaceome_public.feedback_public`. Returns a small HTML confirmation
page. Idempotent — re-clicking a link after moderation returns "Already
handled".

### `GET /v1/feedback/public?gene=<SYMBOL>`

Returns the approved-only community notes for a gene, used by the
`<CommunityNotesCard>` at the bottom of each gene page.

Response shape: `{ "gene": "SYMBOL", "notes": [{ id, submitter_name, comment, approved_at }, ...] }`.

Required bindings (`wrangler.toml`):
- `DB` — public D1 (`surfaceome_public`) — already present.
- `FEEDBACK_DB` — private D1 (`surfaceome_agents`) for submissions + audit.
- `FEEDBACK_RATELIMIT` — KV namespace for per-IP rate-limit counters.

Required secrets (`wrangler secret put`):
- `RESEND_API_KEY` — Resend API key for outbound notifications.
- `TURNSTILE_SECRET_KEY` — Cloudflare Turnstile secret for token verification.
- `MAGIC_LINK_SECRET` — 32-byte secret used as HMAC key for magic links.
- `MAINTAINER_EMAIL` — destination + From address for notification e-mails.

### Full-text paper uploads

`POST /v1/feedback/submit` also accepts `multipart/form-data`: the same
fields as JSON (booleans encoded as `"true"` or `"false"`), plus repeated
`papers` file fields and `paper_rights_confirmed=true`. Up to three PDFs,
10 MiB combined. Extension, MIME type and PDF signature are checked; this
is file-type validation, not malware scanning or complete PDF parsing.
Body size is bounded while streaming, even without Content-Length.

The rights checkbox is required only for uploads and enforced server-side.
Its exact text is stored in each private `feedback_paper` row with the
submission ID and acknowledgment timestamp (`created_at`). This records
claimed authorization for private storage and feedback review, not a verified
licence or permission for public redistribution or AI processing. Authorship
alone is insufficient. When unsure, submit a DOI, repository URL or publisher
sharing link in the comment instead.
The upload form links to [Jisc Open Policy Finder](https://openpolicyfinder.jisc.ac.uk/)
for checking the permitted manuscript version, embargo and hosting location.
The link and acknowledgment do not establish permission to host a public copy.

PDF bytes go to the private `FEEDBACK_PAPERS` R2 bucket. Feedback and paper
metadata commit together in D1 before Resend sends PDFs and seven-day signed
download links. Email failure preserves the saved submission; logs identify
it for manual recovery (no automatic retry). Storage failure returns 503.
Partial R2 objects are retained because D1 commit failures can be ambiguous;
reconcile unreferenced objects before deleting them.

Additional errors: 400 `invalid_pdf`, `too_many_papers`,
`paper_rights_required`, `invalid_body`; 413 `upload_too_large`; 503
`uploads_unavailable` or `storage_failed`. Legacy JSON works without files.

### Public feedback API and private downloads

- `GET /v1/genes/{symbol}/feedback` — approved comments for one gene.
- `GET /v1/feedback/public?gene={symbol}` — equivalent existing endpoint.
- `GET /v1/feedback/public` — approved comments across genes.
- Comment feeds accept `offset` (default 0), return up to 50 notes and
  `next_offset` (null at the end). Notes contain `id`, `gene_symbol`,
  `submitter_name`, `comment`, `approved_at`. Envelope `gene` is null for
  the broad feed. Offsets paginate a live feed, not an immutable snapshot.
- `GET /v1/feedback/paper?id={paper_id}&expires={unix_seconds}&t={hmac}` —
  private download requiring the signed URL from the maintainer email.
  Links are bearer credentials: anyone possessing one can use it until
  expiration. Downloads use `private, no-store` and attachment disposition.

Approval publishes only the comment and attribution. No PDF bytes, file
metadata, private comments, emails or download links enter public feeds or
the gene record. Papers are not automatically fed into annotation. Comment
feeds use `no-store` to prevent query mixing under the zone's query-string-
ignoring cache rule. Do not override origin `no-store` for `/v1/feedback/*`
or `/v1/genes/*/feedback` in edge caching rules.

### Deployment and operations

Before deploying Worker and viewer:

1. Apply `cloudflare/d1_feedback_papers_schema.sql` to private D1
   (`surfaceome_agents`): an idempotent additive migration also included
   in `cloudflare/d1_schema.sql` for fresh databases.
2. Create `surfaceome-feedback-papers` in R2, bind as `FEEDBACK_PAPERS`
   (see `wrangler.toml.example`), and keep public access disabled.
3. Deploy Worker then viewer. Existing `MAGIC_LINK_SECRET` signs paper
   links in a separate `paper:` namespace; no new API key.
4. For deletion requests, query `feedback_paper` by `feedback_id`, delete
   its R2 objects, then metadata and private feedback (and public note if
   present). Discarding a comment does not delete attachments. Expiring a
   link does not delete stored files.
5. Recover failed emails or expired links through private D1 metadata and
   authenticated R2 administration. There is no public private-paper list.

D1 backups include metadata, not PDF bytes. R2 is the durable file store;
bucket backup/retention remains a separate operational decision.

Validate after installing viewer dependencies:
`bash cloudflare/workers/surfaceome_api/tests/run.sh` from the repo root.
