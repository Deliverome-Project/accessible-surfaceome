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
   listed in `EXTRA_FILES_RELATIVE`. By default the repo tarball is
   NOT included (auto-archive handles that); pass
   `--include-repo-tarball` to bundle everything into one record if
   you've disabled auto-archive.

The Zenodo deposit is created as a **draft** — nothing is published
until you click "Publish" in the Zenodo UI. Drafts can be deleted.

## Before you run it

1. **Edit `EXTRA_FILES_RELATIVE`** in `publish-archive.py`. Uncomment
   or add paths (relative to repo root) for any heavy data outputs you
   want to bundle: triage runs, benchmark runs, deep dives, etc. The
   default list is empty — running with it empty just bundles the repo
   tarball alone (which is fine, but probably not what you want for a
   real release).

2. **Edit `SEED_METADATA`** if the default title / description / author
   list / keywords don't match what you want for this release. You can
   also edit metadata in the Zenodo UI after the draft is created — but
   getting it right here means less clicking later.

3. **Generate a Zenodo Personal Access Token** at
   <https://zenodo.org/account/settings/applications/tokens/new/>
   with the `deposit:write` scope. Add `deposit:actions` if you ever
   want to publish via API rather than the UI.

4. **(Optional) Test in sandbox first.** Sign up at
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
   `scripts/embed_figure_gist_metadata.py`: set `zenodo_doi` on the
   top-level entry for each figure that's covered by this deposit.
4. **Re-run** `scripts/embed_figure_gist_metadata.py` to refresh the
   embedded metadata in `data/analysis/figures/*.{png,pdf}`.
5. **Commit** the metadata bump.

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
