# Public record history and numbered data releases — design

**Date:** 2026-09-27
**Status:** approved in brainstorming, pending spec review

## Problem

The public API serves only the latest deep-dive record per gene.
`publish_record` deletes a gene's other `schema_version` rows before it
upserts, and the per-gene Markdown export in R2 (`surfaceome-gene-md/{SYMBOL}.md`)
is overwritten in place. A reader who saw or downloaded a record cannot
retrieve it after the next republish, so they cannot cite what they saw.
A manuscript reviewer asked exactly this ("Are individual records
versioned, so a user can cite what they saw?").

The site badge shows the code release (`pyproject.toml` version, currently
1.2.0), and GitHub releases already mint version DOIs on the Zenodo code
record (concept `10.5281/zenodo.22116981`). The data record (concept
`10.5281/zenodo.20805383`) has a single version (record 20805384,
2026-08-15, blank `version` field) and no link between a release number
and the records it contains.

## Goals

- Every distinct state of a gene's public record — JSON **and** Markdown
  export — that the API served is retrievable forever at a stable URL.
- Numbered data releases (1.0.0, 1.3.0, …) name a fixed set of
  per-gene revisions, match the GitHub release / site badge, and match a
  Zenodo data-record version byte-for-byte.
- The live endpoints are unchanged.

## Non-goals

- Diffs between revisions.
- A history-browsing UI in the viewer (only a one-line citation strip).
- History for triage (already queryable by `run_id`), the benchmark, or
  the catalog endpoint.
- Re-enriching old records with historical deterministic-table versions.

## Key decisions

1. **Granularity:** every revision, with releases as tags over revisions.
2. **A revision is what the API served** (approach A): three parts,
   fetched from the Worker — the enriched `/v1/genes/{sym}` record (which
   the Worker serves **without** `evidence`), the split-out evidence ledger
   `/v1/genes/{sym}/evidence` (verbatim quotes + serve-time `papers`
   citation join), and the `/v1/genes/{sym}.md` export — not the stored
   `annotation_json`. The Worker joins ~10
   deterministic tables at serve time (topology, orthologs, paralogs,
   SURFACE-Bind, Schweke, identifiers), and those can change without a
   republish; archiving the served response captures them.
3. **Content-addressed storage.** Bytes are written only when content
   changes; a release is a list of pointers.
4. **Seed:** revision 1 = the 2026-08-15 Zenodo deposit
   (`deep_dives_all.tar.gz`, record 20805384), tagged as data release
   **1.0.0**. The first release cut under this system is **1.3.0**. No data
   tags for 1.1.0 / 1.2.0 (no data snapshot of them exists).
5. **Path-based URLs only.** The zone cache rule ignores query strings,
   so `?revision=` would be answered with the cached live record.

## 1. Storage and data model

**R2 bucket `surfaceome-record-history`** (new). Objects:

- `records/sha256/{json_hash}.json` — a served record response, exactly as
  first seen.
- `records/sha256/{evidence_hash}.json` — a served evidence-ledger response.
- `records/sha256/{md_hash}.md` — a served Markdown export.

Release exports for Zenodo are built on demand from these objects (§4)
and are not stored in the bucket.

Objects are write-once; nothing overwrites or deletes them. The Worker
reads through a new binding `RECORD_HISTORY`; only Python tooling writes,
via `accessible_surfaceome.cloud.r2_client`.

**Public D1 tables** (added to `cloudflare/d1_public_schema.sql`):

```sql
CREATE TABLE IF NOT EXISTS record_revision (
    gene_symbol           TEXT NOT NULL,
    hgnc_id               TEXT,
    revision              INTEGER NOT NULL,   -- 1, 2, 3 … per gene
    json_hash             TEXT NOT NULL,      -- sha256 hex of the record
    evidence_hash         TEXT,               -- NULL when evidence was inline (seed) or absent
    md_hash               TEXT,               -- NULL when no .md existed
    published_at          TEXT NOT NULL,      -- ISO-8601 UTC, when archived
    source                TEXT NOT NULL,      -- 'seed:zenodo-1.0.0' | 'publish' | 'sweep'
    schema_version        TEXT,
    prompt_corpus_version TEXT,
    PRIMARY KEY (gene_symbol, revision)
);
CREATE INDEX IF NOT EXISTS idx_record_revision_hgnc ON record_revision (hgnc_id);

CREATE TABLE IF NOT EXISTS data_release (
    version             TEXT PRIMARY KEY,   -- '1.3.0'
    cut_at              TEXT NOT NULL,
    github_tag          TEXT,               -- 'v1.3.0'; NULL for 1.0.0
    zenodo_version_doi  TEXT,               -- filled after deposit
    n_genes             INTEGER NOT NULL,
    notes               TEXT
);

CREATE TABLE IF NOT EXISTS data_release_member (
    version      TEXT NOT NULL,
    gene_symbol  TEXT NOT NULL,
    revision     INTEGER NOT NULL,
    PRIMARY KEY (version, gene_symbol)
);
```

**Dedup rule.** A new revision is written only when
`(json_hash, evidence_hash, md_hash)`
differs from the gene's **latest** revision. A revert (A → B → A) is a new
revision pointing at A's existing object; no bytes are duplicated.

**Hash.** `sha256` over the canonical JSON (sorted keys, `(",", ":")`
separators, UTF-8) of the served response with volatile fields removed.
The evidence ledger hashes the same way. Markdown hashes over the UTF-8
text with the `generated <timestamp>` token in its header line normalized. The
volatile set lives in one function in `record_history.py`, pinned by a
test. It starts as `record_generated_at` plus any field the Worker stamps
per request; implementation enumerates the latter by fetching the same
gene twice and diffing, and the test pins the result.

**Size.** ~120 KB per JSON revision; a cohort-wide change adds ~600 MB to
R2 and ~5,130 rows to D1.

`surface_annotation` is untouched: it stays live-only, and its
delete-on-publish rule remains.

## 2. Public API

All additive; `/v1/genes/{sym}` and `/v1/genes/{sym}.md` are unchanged and
keep serving the latest record with today's enrichment.

| Endpoint | Returns | Cache |
|---|---|---|
| `GET /v1/genes/{sym}/revisions` | `{gene_symbol, hgnc_id, current_revision, revisions:[{revision, published_at, source, json_hash, evidence_hash, md_hash, schema_version, prompt_corpus_version, releases:[{version, zenodo_version_doi}], url, evidence_url, md_url}]}`, newest first | 60 s, purged on write |
| `GET /v1/genes/{sym}/revisions/{n}` | archived JSON bytes | 1 y, `immutable` |
| `GET /v1/genes/{sym}/revisions/{n}/evidence` | archived evidence-ledger bytes | 1 y, `immutable` |
| `GET /v1/genes/{sym}/revisions/{n}.md` | archived Markdown bytes | 1 y, `immutable` |
| `GET /v1/releases` | `[{version, cut_at, github_tag, zenodo_version_doi, n_genes}]` | 60 s, purged on write |
| `GET /v1/releases/{ver}` | release metadata + `members:[{gene_symbol, hgnc_id, revision, json_hash, md_hash}]` | 1 y, `immutable` once `zenodo_version_doi` is set; 60 s before |
| `GET /v1/releases/{ver}/genes/{sym}` | same bytes as the matching revision | 1 y, `immutable` |
| `GET /v1/releases/{ver}/genes/{sym}/evidence` | same bytes as the matching revision's evidence ledger | 1 y, `immutable` |
| `GET /v1/releases/{ver}/genes/{sym}.md` | same bytes as the matching revision's `.md` | 1 y, `immutable` |

- Archived bodies are read straight from R2 (not wrapped in the edge/KV
  cache wrapper, which would drop their headers) and carry `ETag: "{hash}"`, `X-Surfaceome-Revision`,
  `X-Surfaceome-Content-Hash`.
- `{ver}` accepts `1.3.0` or `v1.3.0`, normalized, validated against
  `^\d+\.\d+\.\d+$`.
- Errors: `invalid_symbol`, `gene_not_annotated`, `revision_not_found`,
  `release_not_found`, `gene_not_in_release`, `markdown_not_archived` /
  `evidence_not_archived` (404 for a revision with a NULL hash; the seed
  revision's evidence is inline in its record). A D1 row whose R2 object is
  missing returns `500 archive_body_missing` — never a live-record fallback.
- `/v1/releases/{ver}` uses `RATE_LIMITER_HEAVY`.
- All endpoints are listed in the `/v1` index and API docs.

**Cache bypass for the archiver.** Requests carrying
`X-Archive-Bypass: <secret>` matching Worker secret `ARCHIVE_BYPASS_TOKEN`
skip the edge (`caches.default`) and KV (`RECORD_CACHE`) reads **and**
writes, and the per-IP rate limiter, on every route. Missing or wrong
token → normal cached path (no error, no signal).

## 3. Write paths

**`src/accessible_surfaceome/cloud/record_history.py`**

- `volatile_fields()` / `content_hash_json(body) -> str` /
  `content_hash_md(text) -> str`.
- `archive_gene(symbol, *, source, http, store) -> ArchiveResult` —
  fetch the live record, evidence ledger and `.md` with the bypass header; hash; `head_object` →
  `put_object` for any missing object; insert the revision with a single
  statement that computes `MAX(revision)+1` and only inserts when the
  latest row's hashes differ (idempotent, race-safe); purge
  `/v1/genes/{sym}/revisions` and `/v1/releases`. `ArchiveResult` reports
  `created | unchanged | failed` and the revision number.

**Callers**

- `cloud/surface_annotation.py::_publish_dict` → `archive_gene(source="publish")`
  after its purge. Failure logs a warning and records it on the publish
  result; it does not fail the publish (the sweep backstops it). Skipped
  when D1 publishing is skipped (no `CLOUDFLARE_*` env).
- `scripts/build/backfill_deep_block_rollups.py` → `archive_gene` after each
  direct `UPDATE`. (`scripts/archive/backfill_surface_bind_attribution.py`
  is retired and left alone.)
- `scripts/cloud/sweep_record_history.py` — `archive_gene(source="sweep")`
  over every symbol from `/v1/genes`; thread pool; dry-run default,
  `--execute`, `--genes A,B`. Run after any bulk deterministic-table sync.
- `scripts/cloud/seed_record_history.py` (one-off, refuses to run if
  `record_revision` is non-empty) — download `deep_dives_all.tar.gz` from
  Zenodo record 20805384; write each record as revision 1
  (`source='seed:zenodo-1.0.0'`, `md_hash` NULL, `published_at` =
  2026-08-15); create release `1.0.0` (`cut_at` 2026-08-15,
  `zenodo_version_doi` `10.5281/zenodo.20805384`, `github_tag` NULL,
  members = all seeded genes). Then run the sweep: changed genes get
  revision 2; genes annotated after 2026-08-15 start at revision 1.

Revision 1 from the seed is the stored record as deposited (never
enriched, evidence inline); its `source` says so.

The `.md` export is regenerated by the viewer build, not by a publish, so
a publish archives the new record next to the previous `.md`; the next
sweep after the export rebuild records the refreshed `.md` as a further
revision. Both states were served, so both are real revisions.

## 4. Release process

`scripts/release/cut_data_release.py --version X.Y.Z` (dry-run default):

1. Refuse unless `pyproject.toml` version == `X.Y.Z` and the release does
   not exist.
2. Run the full sweep.
3. Write `data_release` + one `data_release_member` per currently
   annotated gene → its latest revision. Members are immutable from here.
4. Export from R2: `genes/{SYMBOL}.json`, `genes/{SYMBOL}.evidence.json`,
   `genes/{SYMBOL}.md`, `manifest.tsv` (symbol, hgnc_id, revision,
   json_hash, evidence_hash, md_hash) → `deep_dives_X.Y.Z.tar.gz`.
5. Create a **draft new version** of Zenodo data record concept 20805383
   (`actions/newversion` on the latest version), upload the tarball, set
   `version` = `X.Y.Z`, and print the draft URL. The script never
   publishes (a Zenodo publish is irreversible); the human reviews and
   publishes, then runs `cut_data_release.py --set-doi X.Y.Z <doi>` to
   record the version DOI. `publish-archive.py` keeps its first-deposit
   role; later data versions go through this path.
6. The human creates GitHub release `vX.Y.Z` (code DOI follows via the
   GitHub–Zenodo integration; the badge reads `X.Y.Z` on next deploy).

A gene removed from the live set is absent from later release members; its
revisions remain.

## 5. Viewer

- The site-header badge reads the version from `pyproject.toml` at build
  time (`NEXT_PUBLIC_RELEASE_VERSION`), replacing the `v1.0` literal.
- The gene page is a client component that loads the live record in the
  browser; it fetches `/v1/genes/{sym}/revisions` alongside its other
  secondary enrichments after first paint. On failure the strip is
  omitted. The strip, near the record header:
  *Revision N · published YYYY-MM-DD · in release vX.Y.Z · Cite this
  version · All revisions*. "Cite this version" → the immutable revision
  URL, plus the release's Zenodo version DOI when the revision is in a
  release.

## 6. Testing

- **Python:** hash stability and volatile-field exclusion (pinned list);
  unchanged republish writes nothing; revert → new revision, no new object;
  md-only change → new revision; `archive_gene` against fake D1/R2/HTTP;
  seed tarball parsing and refusal on non-empty table; release members =
  latest revisions.
- **Worker** (alongside `tests/test_worker_*.py`): routing for all nine
  endpoints incl. `/evidence` and `.md` suffixes; version normalization; immutable cache
  headers; missing R2 object → 500; bypass honoured only with the correct
  secret; shared-API contract cases; `tests/test_cohort_cache_purge.py`
  classifies the new routes.
- **Live:** seed + sweep dry-runs, then execute; `curl` spot-checks of each
  endpoint for a few genes.

## Rollout

1. Apply the DDL to public D1 (`D1Client.query`, one statement per call).
2. Create the R2 bucket; set `ARCHIVE_BYPASS_TOKEN` as a Worker secret and
   in `.env`.
3. Deploy the Worker — check `origin/main` first and reconcile with dev
   (shared API).
4. Seed, then sweep; spot-check.
5. Cut 1.3.0 (pyproject bump, release script, Zenodo version, GitHub
   release).
6. Viewer PR (badge + citation strip).
7. Docs: CLAUDE.md + AGENTS.md (in sync), API docs page, `llms.txt`,
   API skill file, a Methods sentence in the manuscript.
