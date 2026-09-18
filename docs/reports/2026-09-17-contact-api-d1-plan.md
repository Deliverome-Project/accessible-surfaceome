# Contact evidence: public D1 and API implementation plan

Status: proposed; no D1 writes or API deployment performed. Target the existing dev PR and staging environment first.

## Current state and scope

The viewer fetches 64 static shards under `viewer/public/data/contact-sites/`. `scripts/audit/build_contact_site_assets.py` explicitly performs no API or annotation writes. Main gene annotations already have a separate public-D1 publication path and Worker API.

Measured from the current export: 5,106 audited protein entries, 1,680 with contacts, 29,182 source evidence records, approximately 13.1 MB of JSON. EGFR/P00533 has 185 records across all compartments, displayed as 33 named partners overall and 16 extracellular partners. The largest compact per-protein payload is approximately 1.51 MB. Source records are not counts of independent experiments or unique ligands.

Publish the existing audited evidence, including original labels, mapping context, category provenance, and alternative observations. Keep SURFACE-Bind predictions separate. This migration does not expand database coverage or infer missing binders.

## 1. Establish the published data contract

Create a versioned export from the existing audit pipeline before uploading anything. Use HGNC IDs for genes and canonical UniProt accessions for residue numbering. Carry the reference sequence checksum and mapping version; validate coordinates against that sequence. Do not silently map canonical contacts onto isoforms or orthologs.

Assign opaque, persisted ligand IDs independent of display labels. Record source identifiers, aliases and explicit identity decisions. Consolidate known aliases such as GC1118/GC1118A while retaining each original label. Preserve construct distinctions; Fab/VHH stripping alone must not merge different molecules. Unresolved partners remain available as evidence but do not inflate the named-ligand total.

Assign deterministic observation IDs from the source record identity, target, partner/construct, PDB chain identifiers where available, mapped residues, context and reference. Cross-source reports remain separate observations; use a shared structure/interface identity where supported to describe duplication without claiming independent experiments.

Move display-name normalization, category ordering, and representative selection into the export contract. The API and offline fallback must agree. Each ligand has one actually observed representative footprint per requested scope, with a deterministic tie-break; never synthesize a residue union as that representative. Version these rules. Retain all supporting observations.

Reconcile the earlier 5,130-candidate cohort with the 5,106 exported proteins using stable IDs. Publish the exclusions and denominator hash. Track audited-with-evidence, audited-with-no-mapped-evidence, and not-audited separately. Keep the current source sampling caveats (especially SAbDab and BioLiP) in the release manifest.

## 2. Public D1 schema

Add versioned tables in `cloudflare/d1_public_schema.sql`:

| Table | Purpose and key |
| --- | --- |
| `contact_release` | Immutable release ID, schema/rule versions, input hashes, cohort identity, counts, timestamp, provenance manifest and loading/validated/published state. |
| `contact_active_release` | One pointer to the currently published release; allows atomic activation and rollback. |
| `contact_gene` | `(release_id, hgnc_id, uniprot_acc)`; audit status, reference sequence identity, totals and compact summary payload. Includes audited zero-result genes. |
| `contact_ligand` | `(release_id, ligand_id)`; canonical display name, identity cross-references, aliases, construct identity and role provenance. Target-specific interpretation remains on the target–ligand association. |
| `contact_gene_ligand` | `(release_id, uniprot_acc, ligand_id)`; category, named/unresolved status, scope-specific counts and representative observation IDs. |
| `contact_observation` | `(release_id, observation_id)`; indexed target, ligand, source, context, source/PDB identifiers, sorted residue positions and bounded evidence JSON. |

Index observation retrieval by release + accession + ligand + observation ID. Keep source references and mapping confidence descriptive unless a calibrated numeric measure exists. Category is not confidence. Preserve the present category enum, including receptor partner and unclassified.

Use compact residue arrays rather than a row per residue. Measure row and request sizes against current D1 limits before import. Paginated observation rows avoid relying on oversized gene blobs. Public D1 holds the publishable dataset; private D1 need not duplicate these public database-derived records. Preserve the reproducible release bundle and manifest in the repository/data archive workflow.

## 3. Read-only API in the existing Worker

Implement in `cloudflare/workers/surfaceome_api/src/index.js`, using existing CORS, error, rate-limit and cache conventions. Proposed paths, relative to `/surfaceome`:

| Endpoint | Response |
| --- | --- |
| `GET /v1/contact-sites/releases/current` | Active release ID, schema version, coverage summary, sources, provenance and sampling caveats. |
| `GET /v1/contact-sites/releases/:release/proteins/:uniprot` | Compact per-protein summary: stable gene IDs, audit status, category totals and named ligands with their representative footprints. Default scope extracellular; explicit `scope=all` supported. |
| `GET /v1/contact-sites/releases/:release/proteins/:uniprot/ligands/:ligandId/evidence` | Cursor-paginated original observations, source references, mapping context and alternative footprints. |

The release ID is explicit in data URLs. The viewer resolves the active release once and pins subsequent requests to it. Scope is an allowlisted query parameter; cursor tokens are validated and pagination bounded. Use query-aware internal cache keys and ensure edge rules do not collapse distinct scope/cursor responses. Use ETags derived from payload hashes. Immutable release URLs can have long cache lifetimes; the mutable current-release pointer needs a short freshness policy and targeted invalidation through the existing edge/KV machinery.

Return `200` plus empty ligands for audited-no-evidence, an explicit not-audited status for known proteins outside the release cohort, and `404` for unknown targets or releases. Do not use empty results to hide service errors. Do not enlarge the main `/v1/genes/:symbol` annotation response with all contact evidence.

## 4. Reproducible publisher and safe activation

Add a contact exporter/publisher under `src/accessible_surfaceome/cloud/` with a script entry point. Reuse `D1Client`, public D1 configuration and cache invalidation conventions; do not couple publication to rerunning the LLM annotation pipeline.

Default to a dry run reporting counts, changes, excluded mappings and expected bytes. An explicit execute mode inserts a new immutable release in bounded, resumable batches. Never truncate the active release. Validate IDs, foreign-key relationships, coordinate bounds, counts, payload hashes, categories and representative membership after readback. Mark the release validated only after all checks pass, then activate with a single pointer update. Cache invalidation failures must be visible and retryable. Rollback changes the pointer to the previous validated release.

Generate the API import bundle and static fallback from the same normalized release. The fallback includes its release ID so the viewer can disclose stale data rather than silently mixing releases. Extend the public-D1 backup/export process to cover the new tables; verify the current private-D1-only backup workflow does not leave this dataset uncovered. Add an upload/readback smoke test and a tested restore/rollback path.

## 5. Viewer migration

Replace the direct shard fetch in `StructureViewer.tsx` with a typed API loader keyed by UniProt accession and release. Load the summary when Contact sites opens; fetch individual evidence only when the user opens a tooltip/evidence section that needs it. Include lightweight source/count/category information in the summary so ordinary hover does not require a network round trip.

Use API-provided ligand IDs, categories, ordering and representative footprints. Preserve current All-ligands overlay, individual navigation, category colors and canonical-only projection. Derive the All-ligands union from the same returned representatives. Retain original observations behind evidence.

Use the static bundle only on a network/server failure, with a visible snapshot/release indicator. An authoritative empty API result must not trigger fallback. Cancel stale requests when switching genes and do not combine summaries and evidence from different releases.

## 6. Validation and rollout gates

1. Contract/export tests: known alias merges, distinct antibody identities, deterministic representative selection, source-record conservation, unknown roles and canonical residue bounds.
2. Publisher tests: dry run performs no writes; interrupted uploads resume; partial releases cannot activate; repeated publication is idempotent; pointer rollback works.
3. API tests: stable-ID lookup, empty versus unaudited versus unknown status, evidence pagination, scope-specific cache isolation, consistent release IDs, bounded payloads and service errors.
4. EGFR parity gate: preserve the existing 185 observations, 33 named partners overall, and 16 extracellular partners with categories 4 endogenous large / 0 endogenous small / 5 therapeutic / 6 tool / 1 receptor partner / 0 unclassified. Confirm EGF alternative observations and GC1118 aliases remain accessible. These are parity assertions for this snapshot, not permanently fixed biological totals.
5. Cohort gate: reconcile all 5,106 exported protein entries and the earlier 5,130 candidates; compare per-source counts and hashes, not just aggregate totals. Test a zero-result gene and the largest evidence-heavy proteins.
6. Deploy schema, import and API to staging; compare API output with the static baseline. Switch the dev viewer, test All → individual → evidence and error fallback, then publish to production through the normal deployment process. Retain the previous release and fallback until the production readback passes.

## Suggested implementation sequence

- PR 1: stable identity/export contract, D1 schema and dry-run/resumable publisher.
- PR 2: read-only API, caching, evidence pagination, API documentation and staging import/readback.
- PR 3: viewer API loader, shared-release fallback and browser parity checks; production activation after validation.

Acceptance: the viewer and external API clients retrieve the same versioned ligand identities and contact footprints from public D1, every displayed footprint links to its supporting observations, and incomplete audits remain explicitly distinguishable from biological absence.
