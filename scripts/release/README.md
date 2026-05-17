# Release scripts

One-shot rituals for promoting `accessible-surfaceome` to durable
storage. Run manually, only when you're ready.

## Architecture: two Zenodo record series

The deliverome project uses two parallel Zenodo record series:

1. **Code releases** — handled automatically by the GitHub-Zenodo
   integration (one DOI per tagged GitHub Release; the auto-archive
   captures the repo tarball but **NOT** LFS bytes or content that
   isn't in the repo). Enable at <https://zenodo.org/account/settings/github/>.
   You do nothing per release once this is on.

2. **Heavy data outputs** — handled by this script. Things like full
   triage runs with reasoning, benchmark runs with reasoning, deep-dive
   analyses — files too large for the repo or not committed at all.
   Manual deposit each time you want to mint a fresh DOI for new data.

The two series link to each other via `related_identifiers` metadata
(this record `isSupplementTo` the code record). CrossRef/DataCite
indexes the relationship and Zenodo's UI shows it.

## What `publish-archive.py` does

Three release tasks in one command:

1. **Submit repo + every figure gist to Software Heritage** (free
   archive, content-addressed SWHIDs, no DOIs).
2. **Audit every figure's embedded provenance** by deferring to
   `tests/test_figure_provenance.py`. Surfaces stale or malformed
   metadata before you commit to a Zenodo deposit.
3. **Create a draft Zenodo deposit** containing the heavy data files
   listed in `EXTRA_FILES`. By default the repo tarball is
   NOT included (auto-archive handles that); pass
   `--include-repo-tarball` to bundle everything into one record if
   you've disabled auto-archive.

The Zenodo deposit is created as a **draft** — nothing is published
until you click "Publish" in the Zenodo UI. Drafts can be deleted.

## Before you run it

1. **Review `EXTRA_FILES`** in `publish-archive.py`. The default set is
   three data files plus a generated in-deposit README. All joins
   happen server-side in the Cloudflare Worker — the publish script
   just fetches pre-joined endpoints, so deposit bytes are atomic
   snapshots:
   - `triage-runs-with-reasoning.tsv` — long format, Sonnet × ~19k
     M1 candidate-universe genes, with DB votes + uniprot_acc joined
     in by the Worker. From
     `/v1/triage/export-enriched.tsv?run_id=genome_full_sonnet_ncbi_v1`.
   - `triage-benchmark-with-reasoning.tsv` — long format, Haiku +
     Sonnet + Opus × 4 prompt variants × 147 bench genes, with DB
     votes + truth labels joined in by the Worker. From
     `/v1/benchmark/triage-enriched.tsv`.
   - `deep_dives_all.tar.gz` — gzipped tarball, one `<SYMBOL>.json`
     per published `SurfaceomeRecord`; built by fetching `/v1/genes`
     for the index, then `/v1/genes/<SYMBOL>` per gene.
   - `README.md` — generated at deposit time; documents every column
     of every file and the live-API endpoint that produces it. Travels
     with the data on Zenodo.

   Each entry is either a `{"url", "filename"}` dict (verbatim API
   fetch), a path string relative to repo root (local file), or one
   of the special builder shapes: `{"deep_dives_bundle": True, ...}`
   (tarball), `{"deposit_readme": True, ...}` (in-deposit README).
   Comment out anything you don't want in this particular deposit.

2. **Deploy the Worker** if you've changed any of the enriched
   endpoints (`handleTriageExportEnriched` /
   `handleBenchmarkTriageEnriched` in
   `cloudflare/workers/surfaceome_api/src/index.js`) — the publish
   script depends on them. Skip if you haven't touched that file
   since the last deploy.

   ```bash
   cd cloudflare/workers/surfaceome_api && npx wrangler deploy
   ```

3. **Edit `SEED_METADATA`** if the default title / description / author
   list / keywords don't match what you want for this release. You can
   also edit metadata in the Zenodo UI after the draft is created — but
   getting it right here means less clicking later.

4. **Generate a Zenodo Personal Access Token** at
   <https://zenodo.org/account/settings/applications/tokens/new/>
   with the `deposit:write` scope. Add `deposit:actions` if you ever
   want to publish via API rather than the UI.

5. **(Optional) Test in sandbox first.** Sign up at
   <https://sandbox.zenodo.org/>, generate a sandbox token (separate
   account), and run with `ZENODO_SANDBOX=true`. Fake DOIs, real API,
   safe.

## How to run

```bash
# 1. Dry run — show what would happen, no API calls
./scripts/release/publish-archive.py --dry-run

# 2. Software Heritage only (no Zenodo activity)
./scripts/release/publish-archive.py --skip-zenodo

# 3. Sandbox Zenodo test
ZENODO_TOKEN='sandbox-token' ZENODO_SANDBOX=true \
  ./scripts/release/publish-archive.py

# 4. The real thing — heavy data record (auto-archive handles code)
ZENODO_TOKEN='real-token' \
  ./scripts/release/publish-archive.py

# 5. One-bundled-record mode (only if you've disabled auto-archive)
ZENODO_TOKEN='real-token' \
  ./scripts/release/publish-archive.py --include-repo-tarball
```

### Linking the data record back to the code record

The first time you run this script, the resulting Zenodo data record
won't yet know about the auto-archived code record (you may not have
made a tagged release yet).

After both records exist:

1. Note the **concept DOI** of the code record series (the always-
   latest one, found at the top of any auto-archived release's Zenodo
   page).
2. Edit `SEED_METADATA["metadata"]["related_identifiers"]` in
   `publish-archive.py` to declare the link:
   ```python
   "related_identifiers": [
       {
           "identifier": "10.5281/zenodo.<CONCEPT-DOI>",
           "relation": "isSupplementTo",
           "scheme": "doi",
       },
   ],
   ```
3. Next time you mint a data record, it'll be linked in DataCite.
4. For the data records you've already published, edit the metadata in
   the Zenodo UI to add the same `related_identifiers` entry — Zenodo
   lets you edit metadata after publication (just not files).

## After the script runs

1. **Open the Zenodo draft URL** the script prints. Review:
   - Metadata is correct (creators, ORCIDs, license, keywords)
   - Files are uploaded (the repo tarball + your heavy data files)
   - "Related identifiers" — link the SWHID of the repo and the gists
     here so the Zenodo record cross-references them in DataCite
2. **Click "Publish"** in the Zenodo UI when you're ready. The reserved
   DOI activates and the record is locked.
3. **Update `FIGURE_PROVENANCE`** in
   `scripts/embed_figure_gist_metadata.py`: set `doi` on the
   top-level entry for each figure that's covered by this deposit.
4. **Re-run** `scripts/embed_figure_gist_metadata.py` to refresh the
   embedded metadata in `data/analysis/figures/*.{png,pdf}`.
5. **Commit** the metadata bump.

## The full publication ritual (both records together)

The data record (this script) and the code record (GitHub-release
auto-archive) are independent — they can be released at different
cadences. But for a real publication moment, you usually want both
refreshed together. The end-to-end ritual:

### Prerequisites (one-time)

1. **Enable GitHub-Zenodo auto-archive** for `accessible-surfaceome`
   at <https://zenodo.org/account/settings/github/>. Find the repo
   in the list, flip its toggle to ON. From this point forward, every
   GitHub Release (not just a tag — needs an actual published Release
   in the GitHub UI) creates a new Zenodo record automatically.
2. **(Optional) Add a `.zenodo.json`** at the repo root with default
   metadata (creators, license, keywords). Without it, Zenodo guesses
   from the release notes. With it, the auto-deposit has clean,
   complete metadata from version 1.

### Per-release ritual

When you're ready to publish a new version of the project:

```bash
# 1. Audit + run the data deposit (this script).
ZENODO_TOKEN='...' ./scripts/release/publish-archive.py
# → drafts a Zenodo record with EXTRA_FILES contents
# → audit phase 2.5 surfaces any data inputs the gists reference
#   that aren't already deposited — fix EXTRA_FILES if needed

# 2. Open the draft URL the script printed, review, click Publish.
#    Note the new data record DOI (e.g. 10.5281/zenodo.NEW_DATA).

# 3. Tag a new version in the repo:
git tag -a v1.2.0 -m "Release v1.2.0: <one-line summary>"
git push origin v1.2.0

# 4. Create a GitHub Release for that tag:
gh release create v1.2.0 --generate-notes
# → Zenodo auto-archive watches for this event, fetches the repo tarball,
#   creates a new Zenodo record with a new version DOI under the existing
#   concept-DOI series.

# 5. After both records exist, link them via metadata in the Zenodo UI:
#    on the data record: relatedIdentifier isSupplementTo <code-concept-DOI>
#    on the code record: relatedIdentifier isSupplementedBy <data-concept-DOI>
#    (Zenodo lets you edit metadata after publishing; just not files.)

# 6. Update FIGURE_PROVENANCE with the new code-record's concept DOI
#    so future figure renders pick it up:
#    edit scripts/embed_figure_gist_metadata.py → set `doi` per figure
#    → uv run python scripts/embed_figure_gist_metadata.py
#    → git add data/analysis/figures/ && git commit
```

After step 6, the figures know about both their gist SWHID (for the
reproduction artifact) and the bundle DOI (for the publication
citation), and the Zenodo records know about each other.

## Auto-archive vs this script — they're complementary

If you already have GitHub-Zenodo auto-archive enabled (recommended
for code), you have **two parallel Zenodo record series** in flight:

| | Code series (auto) | Data series (this script) |
|---|---|---|
| Created by | GitHub release event | manual run of this script |
| What's in it | Repo tarball at tag | Heavy data files outside the repo |
| Cadence | Per release | Per data milestone |
| Versioning | New version per GitHub release | New version per script run (manual) |
| Concept DOI | One per series | One per series |

The two are linked via `related_identifiers` metadata in the data
record's spec. Citing the code DOI, citing the data DOI, or citing
both gives readers the full picture.

### When NOT to use this script

- If your heavy data fits comfortably in the repo (e.g., everything
  under ~100 MB total) AND you've committed it: auto-archive captures
  it automatically. Skip this script entirely.
- If you DON'T want to mint DOIs for data: just keep using SWHIDs via
  the figure provenance schema. Software Heritage covers durability;
  DOIs are about citation, which not all data needs.

### When to use this script

- You have data outputs (triage runs, benchmark runs, deep dives)
  that are too large for the repo, OR generated externally, OR
  LFS-tracked (LFS bytes don't get included in auto-archive).
- You want a citeable DOI for those data files, separate from any
  paper they appear in.

## Safety reminders

- SWH submissions are **append-only**. Once SWH archives a piece of
  content, you can't ask them to delete it (their mission is permanent
  preservation). Don't submit content you don't want archived forever.
- Zenodo deposits start as **drafts** (private, deletable). After you
  publish, the bytes are **immutable** — you can edit metadata
  forever, but you can't add or remove files. To add files later,
  publish a new version (separate version DOI, same concept DOI).
- The Zenodo token in your env is sensitive; don't commit it.
