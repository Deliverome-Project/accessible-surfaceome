# Contact evidence API and public D1 implementation

## Published development release

Release: `contacts-37d700655fdf74b13746`.

Development API: https://surfaceome-contact-api-dev.beccajcarlson.workers.dev/v1/contact-sites/releases/current

The release is uploaded, fully read back, validated and active in **surfaceome_public**. The separate development Worker exposes contact GET routes only and has an IP rate limiter. The existing production Worker route is implemented in this PR but has not been deployed over the production API. The local viewer is built against the development endpoint; its normal default remains the production API URL.

| Published content | Count |
| --- | ---: |
| Original cohort rows | 5,130 |
| Non-unique/unresolved identifier exclusions, listed in manifest | 24 |
| Audited protein summaries | 5,106 |
| Proteins with mapped evidence | 1,680 |
| Audited ligand identities, including unresolved source identities | 5,350 |
| Target–ligand associations | 8,191 |
| Original source observations | 29,182 |

The largest initial summary is 94,291 bytes; full observations are retrieved separately in pages of at most 100. Ligand identities here describe the existing audit's browsing identities. Raw source names and construct strings are retained in every observation; the migration does not upgrade biological identity or confidence claims.

## Data and serving contract

Six additive D1 tables hold immutable release metadata, an atomic active pointer, protein summaries, ligand identities, target–ligand associations and observations. The publisher uses bounded idempotent inserts, validates complete stored payloads by readback, and switches the pointer only after validation. The previous release can be reactivated without deleting anything.

The exporter reuses the viewer's alias and representative-footprint rules. Every displayed representative is an existing observation, not a union. Canonical residue bounds are validated against the audit's cached reference sequences and summary records carry the sequence SHA-256 and length. Every source observation has a deterministic ID. The release manifest preserves source hashes, sampling limitations and the 24 excluded identifiers.

Endpoints use stable UniProt IDs and explicit release IDs. Empty audited results and known-but-unaudited proteins are distinct; unknown IDs return 404 and storage errors return 503. Whole-protein evidence retrieval includes unresolved partners, even though the named-ligand summary omits them. Evidence pagination respects compartment scope.

Initial contact routes deliberately use `no-store`, with scope-specific summary ETags, rather than the existing cache wrapper: the current edge rule ignores query strings and must not conflate evidence pages or scopes. This also makes active-release changes immediately visible without edge/KV purge. The current rate limiting bounds reads; query-aware immutable caching can be added separately.

The viewer loads the summary from the API, then requests detailed observations only when evidence is expanded. Hover information uses source/count metadata already in the summary. All follow-up requests stay on the original release. Service failure falls back to the bundled static snapshot with an explicit snapshot/release label; an authoritative empty response does not trigger fallback. The export writes the matching fallback release sidecar.

Public D1 was already included in the repository's backup workflow. Contact schema, export, asset and publisher changes now trigger that workflow. No production API or Pages deployment was performed.

## Verification

- Six Python tests pass: exporter regressions and publisher resume, immutability, corruption rejection and validated-release activation/rollback.
- Fifteen Node tests pass: API scope/pagination/status semantics, viewer fallback and release consistency, and existing identity/footprint regressions.
- Scoped Ruff and Python type checks pass; viewer production build passes.
- Live API exact-payload comparisons pass for EGFR (185 observations), P62873 (3,399 observations, including pagination), and A0A075B734 (audited with zero observations).
- Live EGFR summary: 16 extracellular partners; 33 across all compartments. Categories: 4 endogenous large, 5 therapeutic, 6 research tools, 1 receptor partner, and zero endogenous small/unclassified.
- Live EGF evidence: 20 observations. Browser verification confirmed the 16/33 totals, individual navigation and lazy loading of all 20 EGF records from the development API, without the snapshot fallback label.

The machine's Python TLS transport failed against Cloudflare during the initial upload. The same publisher and readback/activation logic was run through a temporary Node fetch transport with normal TLS verification; no credentials were printed or committed. The committed publisher retains the project's standard D1Client. Deployment used the installed Wrangler runtime.

## Production rollout

Deploy the main Worker changes before rolling out the viewer with its default API base. The public D1 tables and active release are already present. Verify `/surfaceome/v1/contact-sites/releases/current` and EGFR after deployment, then deploy the viewer through the normal dev-to-production process. The isolated development Worker remains available for review. See the Worker README for repeatable export, dry-run, publication and rollback commands.
