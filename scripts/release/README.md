# Release scripts

One-shot rituals for promoting `accessible-surfaceome` to durable
storage. Run manually, only when you're ready.

## What's here

### `publish-archive.py`

Bundles three release tasks into one command:

1. **Submit repo + every figure gist to Software Heritage** (free
   archive, content-addressed SWHIDs, no DOIs).
2. **Audit every figure's embedded provenance** by deferring to
   `tests/test_figure_provenance.py`. Surfaces stale or malformed
   metadata before you commit to a Zenodo deposit.
3. **Create a draft Zenodo deposit** containing the repo at HEAD as a
   tarball plus any heavy data outputs listed in `EXTRA_FILES_RELATIVE`
   at the top of the script.

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

# 4. The real thing
ZENODO_TOKEN='real-token' \
  ./scripts/release/publish-archive.py
```

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

## Why this isn't automatic

The default GitHub-Zenodo integration auto-archives every release. This
script intentionally doesn't — for several reasons:

- **You want to control timing.** Some commits aren't releases. Some
  versions are pre-publication and shouldn't have DOIs minted yet.
- **You want to include heavy data files** that aren't in the repo.
  GitHub auto-archive only contains the repo tarball.
- **One bundled record is cleaner** than two (repo-only + heavy-data)
  for citation purposes — paper readers click one DOI, get everything.

The trade-off: each release is a manual ritual (~5 minutes of clicking
in the Zenodo UI to finalize). For a once-or-twice-a-year publication
cadence, that's the right call.

If you later prefer the auto-archive model, enable it at
<https://zenodo.org/account/settings/github/> and stop using this
script. The two approaches are mutually exclusive — running both
creates two record series with different DOIs.

## Do I need a separate Zenodo record for heavy data files?

**No — this script puts everything in one record.** The repo tarball
and the heavy data files (triage runs, benchmark runs, deep dives) all
go into a single Zenodo deposit with a single DOI.

The only case where you'd want two records:

- You ALSO enable GitHub-release auto-archive on the repo (separate
  record series for routine code releases)
- AND keep this script for the heavy-data bundle (its own record
  series)

That's two concept DOIs to manage. The single-record model (this
script's default) avoids that.

## Safety reminders

- SWH submissions are **append-only**. Once SWH archives a piece of
  content, you can't ask them to delete it (their mission is permanent
  preservation). Don't submit content you don't want archived forever.
- Zenodo deposits start as **drafts** (private, deletable). After you
  publish, the bytes are **immutable** — you can edit metadata
  forever, but you can't add or remove files. To add files later,
  publish a new version (separate version DOI, same concept DOI).
- The Zenodo token in your env is sensitive; don't commit it.
