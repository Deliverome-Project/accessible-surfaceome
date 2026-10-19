# Plan — commit tag-sites to public D1

**Goal.** Serve tag-sites from the `surfaceome_public` D1 (like `surface_bind_*` and,
after PR #134, `surface_internalization`) instead of only static
`viewer/public/tag-sites/{SYMBOL}.json`. This makes tag-sites queryable
(by gene, provenance, validation), versioned, and served by the same Worker as the
rest of the record — no per-gene static-asset sprawl.

**Precedent to mirror (confirmed in-repo).**
- `surface_bind_site` — the per-site table shape: `(uniprot_acc, site_id)` PK, FK to a
  parent protein row, per-site columns, `*_version` + `synced_at`.
- `surface_internalization` (PR #134) — the newest additive dataset: canonical DDL in
  `cloudflare/d1_internalization_schema.sql` + `cloud/internalization.py::DDL`, indexes
  on `gene_symbol` / grade / `has_literature`, ingest via `cloud/d1_client.D1Client`.
- `scripts/sync_surface_bind_to_d1.py` — the ingest pattern (chunked UPSERT, idempotent
  on PK, `CLOUDFLARE_D1_SURFACEOME_PUBLIC_ID`).

## 1. Schema — `tag_site_public`

New table (additive; no existing table touched). One row per site, keyed like
`surface_bind_site`. Columns map 1:1 from the `TaggedSite` contract
(`viewer/lib/tag-sites-types.ts`) plus the agent-only fields.

```sql
CREATE TABLE IF NOT EXISTS tag_site_public (
    gene_symbol            TEXT NOT NULL,
    uniprot_acc            TEXT NOT NULL,
    site_id                TEXT NOT NULL,          -- e.g. "TFRC-surface_loop-291"
    provenance             TEXT NOT NULL,          -- deterministic_computed | literature_retrieved
    det_path               TEXT,                   -- disorder | surface_loop | NULL (lit)
    site_kind              TEXT NOT NULL,          -- terminal_n | terminal_c | internal
    insert_after_residue   INTEGER,
    residue_before         TEXT,
    residue_after          TEXT,
    residue_label          TEXT,                   -- "G101" (after-residue convention)
    residue_range          TEXT,                   -- "C89-R120" tolerant-feature span (det only)
    topology_state         TEXT,                   -- O/I/M/S
    extracellular          INTEGER NOT NULL,       -- 0/1
    compartment            TEXT,
    tag_type               TEXT,
    tag_length_aa          INTEGER,
    linker                 TEXT,
    evidence_type          TEXT,
    functional_impact_measured TEXT,
    confidence             TEXT,
    -- literature-agent honesty/quality fields (NULL for deterministic):
    validation_level       TEXT,                   -- surface_and_function | surface_only | ...
    position_evidence      TEXT,                   -- validated | inferred
    source_tier            TEXT,                   -- paper | patent | vendor
    supporting_pmid        INTEGER,
    -- deterministic numeric signals (NULL for literature):
    plddt                  REAL,
    conservation_rank      INTEGER,
    median_conservation    REAL,
    rationale              TEXT,
    sources_json           TEXT,                   -- JSON array of {citation,url,pmid,doi}
    tag_sites_version      TEXT NOT NULL,
    synced_at              TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (uniprot_acc, site_id)
);
CREATE INDEX IF NOT EXISTS idx_tag_site_symbol      ON tag_site_public (gene_symbol);
CREATE INDEX IF NOT EXISTS idx_tag_site_provenance  ON tag_site_public (provenance);
CREATE INDEX IF NOT EXISTS idx_tag_site_validation  ON tag_site_public (validation_level);
```

- Canonical DDL lives in **`cloudflare/d1_tag_sites_schema.sql`** + **`cloud/tag_sites.py::DDL`**
  (kept in sync, exactly as `internalization.py` mirrors `d1_internalization_schema.sql`),
  and is appended to `cloudflare/d1_public_schema.sql`.
- `tag_sites_version` enables latest-wins across re-derivations (same as `*_version` elsewhere).

## 2. Ingest — `scripts/sync_tag_sites_to_d1.py`

Mirror `sync_surface_bind_to_d1.py`:
- Read every `viewer/public/tag-sites/{SYMBOL}.json` (the pipeline's existing output —
  no new producer needed).
- Flatten each `TaggedSite` → one row; `sources` → `sources_json`; agent fields where present.
- `D1Client` INSERT OR REPLACE in chunks of 50 (D1 HTTP API has no multi-statement batch).
- Idempotent on `(uniprot_acc, site_id)`; stamp `tag_sites_version` (arg) + `synced_at`.
- `--dry-run` prints the row count and first rows without writing (house style).

## 3. Worker — `GET /v1/tag-sites/:symbol`

Add to `cloudflare/workers/surfaceome_api/src/index.js` next to the other `/v1/...` routes:
- `SELECT * FROM tag_site_public WHERE gene_symbol = ? ORDER BY provenance, insert_after_residue`.
- Shape the rows back into a `TaggedSitesFile` (`{has_data, gene_symbol, uniprot_acc, sites[]}`),
  parsing `sources_json`. Return `{has_data:false, sites:[]}` on no rows (same graceful contract
  the static asset has today).
- Reuse the existing latest-version / caching middleware.

## 4. Viewer

- `viewer/lib/tag-sites-client.ts::fetchTaggedSites` → fetch `${API_BASE}/v1/tag-sites/${symbol}`
  instead of the static `/tag-sites/{SYMBOL}.json`. `parseTaggedSitesFile` already validates the
  shape, so the component/overlay code is unchanged.
- Keep the static JSON as a build-time fallback for local dev (optional), or drop it once D1 is live.

## 5. Tests
- `cloud/tag_sites.py` DDL round-trips (in-memory sqlite): create → INSERT OR REPLACE → SELECT.
- `sync_tag_sites_to_d1.py --dry-run` on the committed TFRC.json → expected row count + a
  spot-checked row (e.g. `TFRC-surface_loop-291`, residue_range `K90-Y123`).
- Worker: a unit test (miniflare/sqlite) that the endpoint returns a valid `TaggedSitesFile`.
- Viewer: existing `tag_sites_client.test.ts` extended to point at the `/v1` shape (same parser).

## 6. Rollout (all additive — nothing existing changes)
1. Land the DDL (new table only) — safe to apply to prod D1 immediately.
2. Run `sync_tag_sites_to_d1.py` for the genes with committed JSON (today: TFRC; grows as the
   pipelines run more controls/genes).
3. Ship the Worker route.
4. Flip `fetchTaggedSites` to `/v1`.

Sequenced after PR #134 merges (this branch is already rebased on it), so `tag_site_public`
sits alongside `surface_internalization` in one coherent `d1_public_schema.sql`.
