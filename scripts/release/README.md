# Release scripts

One-shot rituals for promoting `accessible-surfaceome` to durable
storage. Run manually, only when you're ready.

## Architecture: three Zenodo record series + per-figure SWHIDs

Long-term citable storage for the project splits across four channels:

1. **Code releases** (Zenodo record series, **auto**) — handled by the
   GitHub-Zenodo integration. One DOI per tagged GitHub Release; the
   auto-archive captures the repo tarball but **NOT** LFS bytes or
   content that isn't in the repo. Enable at
   <https://zenodo.org/account/settings/github/>. You do nothing per
   release once this is on.

2. **Heavy data outputs** (Zenodo record series, **this script**) —
   triage-runs with reasoning, benchmark runs with reasoning, the
   eventual deep-dive bundle. Files too large for the repo or not
   committed at all. Manual deposit each time you want to mint a fresh
   DOI for new data. Lives at the reserved DOI
   `10.5281/zenodo.20805384`.

3. **Manuscript** (Zenodo record series, **separate from data**,
   uses bioRxiv DOI as external) — a one-record-per-preprint series
   that hosts the paper PDF + JATS XML at a Zenodo URL but registers
   the record under the bioRxiv DOI rather than minting a new Zenodo
   DOI. Done via the "I already have a DOI" path in the Zenodo upload
   form. Unpaywall harvests Zenodo over OAI-PMH and adds the Zenodo
   PDF as an `oa_location` under the bioRxiv DOI within ~2–4 weeks —
   gives a bot-accessible full-text URL for a DOI bioRxiv itself
   blocks bots from fetching. See the **"Manuscript deposit"** section
   below for the procedure.

4. **Per-figure reproduction units** (gists, cited via **SWHID**,
   not DOI) — each figure's gist bundles `01_<slug>.md` + bundled
   TSV(s) + `make_<slug>.py` and is cited as `swh:1:rev:<sha>` of the
   gist's HEAD commit. See `data/analysis/figures/swhid_map.json`.

The data record (2) and the code record (1) link to each other via
`related_identifiers` metadata (data `isSupplementTo` code). The
manuscript record (3) links to the data record via Related Identifier
`isSupplementedBy` → data DOI, and the data record links back with
`isSupplementTo` → bioRxiv DOI. CrossRef/DataCite indexes all
relationships; Zenodo's UI surfaces them on every record's landing
page.

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
     `/v1/triage/export.tsv?run_id=genome_full_sonnet_ncbi_v1`.
   - `triage-benchmark-with-reasoning.tsv` — long format, Haiku +
     Sonnet + Opus × 4 prompt variants × 147 bench genes, with DB
     votes + truth labels joined in by the Worker. From
     `/v1/benchmark/export.tsv`.
   - `deep_dives_all.tar.gz` — gzipped tarball, one `<SYMBOL>.json`
     per published `SurfaceomeRecord`; built by fetching `/v1/genes`
     for the index, then `/v1/genes/<SYMBOL>` per gene.
   - `README.md` — generated at deposit time; documents every column
     of every file and the live-API endpoint that produces it. Travels
     with the data on Zenodo.

   Each entry is either a `{"url", "filename"}` dict (verbatim API
   fetch), a path string relative to repo root (local file), or one
   of the special builder shapes: `{"deep_dives_bundle": True, ...}`
   (tarball), `{"deposit_readme": True, ...}` (in-deposit README),
   `{"manuscript": True, ...}` (pre-built PDF + pandoc-generated
   JATS XML for the paper — off by default; see below). Comment out
   anything you don't want in this particular deposit.

2. **Deploy the Worker** if you've changed `handleTriageExport` or
   `handleBenchmarkExport` in
   `cloudflare/workers/surfaceome_api/src/index.js` — the publish
   script depends on the JOINs those handlers do. Skip if you
   haven't touched that file since the last deploy.

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

## Auto-archive vs this script vs manuscript record — three series

If you have GitHub-Zenodo auto-archive enabled (recommended for code),
you have **three parallel Zenodo record series** at play:

| | Code series (auto) | Data series (this script) | Manuscript record (manual UI) |
|---|---|---|---|
| Created by | GitHub release event | manual run of this script | manual upload to zenodo.org/uploads/new |
| What's in it | Repo tarball at tag | Heavy data files outside the repo | manuscript.pdf + JATS XML |
| DOI shape | Zenodo-minted per release | Zenodo-minted per data milestone | **bioRxiv DOI (external)** |
| Cadence | Per release | Per data milestone | Per preprint version |
| Versioning | New version per GitHub release | New version per script run | New version per preprint revision |
| Concept DOI | One per series | One per series | One per series |

The series link to each other via `related_identifiers` metadata.
Citing the code DOI, the data DOI, the bioRxiv DOI, or any
combination gives readers the full picture. The bioRxiv DOI is the
"canonical" citation for the paper itself; the Zenodo records on
each side are durable archival copies.

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

For the manuscript itself, do NOT use this script — see the
"Manuscript deposit" section above. The manuscript lives in a
**separate Zenodo record** registered under the bioRxiv DOI, not
bundled into this data deposit.

## Manuscript deposit — separate record, bioRxiv DOI as external

**The manuscript is NOT bundled into the data deposit.** It gets its
own Zenodo record, registered under the bioRxiv preprint's DOI rather
than a Zenodo-minted DOI. The rationale is bot-reach: bioRxiv blocks
automated PDF retrieval (your User-Agent gets 403), so an Unpaywall
query against the bioRxiv DOI returns no fetchable OA location. By
hosting the same PDF on Zenodo under the same DOI, Unpaywall's
OAI-PMH harvest picks up the Zenodo URL and adds it to the bioRxiv
DOI's `oa_locations` — your paper becomes bot-fetchable everywhere
without a second DOI to cite.

### Why a separate record (not a file in the data deposit)

The "I already have a DOI" option in Zenodo's upload form applies to
the **whole record's primary DOI**. If you used it on the data deposit
(20805384), the deposit's identity would become "this is the bioRxiv
preprint" — semantically wrong since the deposit also contains
genome-wide triage TSVs, the deep-dive bundle, and the README. The
clean split:

| Record | DOI | Contents |
|---|---|---|
| `zenodo.20805384` (this script's data record) | Zenodo-minted `10.5281/zenodo.20805384` | triage TSVs + deep-dive bundle (when ready) + README |
| **New manuscript record** | bioRxiv DOI (external) | `manuscript.pdf` + `manuscript.xml` (JATS) + optionally `manuscript.txt` |

### The procedure (post-bioRxiv-acceptance)

1. **Post the preprint to bioRxiv.** You get a DOI like
   `10.1101/2026.06.27.123456`.
2. **Build the manuscript outputs** via `paper/build.py`:
   ```bash
   uv run python paper/build.py paper/manuscript.docx
   # produces paper/build/manuscript.{pdf,xml,html}
   ```
3. **Create a new Zenodo deposit** at <https://zenodo.org/uploads/new>.
4. On the **DOI** field, select **"Yes, I already have a DOI"** and
   paste the bioRxiv DOI. Zenodo will NOT mint a new DOI for this
   record. **Critical:** answering "No" here would mint a Zenodo
   DOI and break the Unpaywall route described below.
5. **Upload the files:**
   - `manuscript.pdf` — primary citable
   - `manuscript.xml` — pandoc-generated JATS (PMC-compatible)
   - `manuscript.txt` (optional) — plain-text extracted version
     (some text-miners prefer it; harmless to add)
6. **Set license** = CC-BY 4.0 (matches the rest of the project).
7. **Add Related Identifiers** in the metadata form:
   - `isSupplementedBy` → `10.5281/zenodo.20805384` (the data record)
   - (data record's metadata, separately) `isSupplementTo` →
     the bioRxiv DOI
8. **Publish.** Zenodo registers the record under the bioRxiv DOI;
   the OAI-PMH endpoint (`https://zenodo.org/oai2d`) now exposes
   the record with `dc:identifier=doi:<bioRxiv DOI>` and file URLs.
9. **Wait ~2–4 weeks** for Unpaywall's harvester to pick it up.
   Verify with:
   ```bash
   curl -s "https://api.unpaywall.org/v2/<bioRxiv-DOI>?email=becca@deliverome.org" \
     | jq '.oa_locations[] | {host: .host_type, url, license, version}'
   ```
   Should show both bioRxiv and Zenodo entries.
10. **If still not indexed after ~6 weeks**, submit at
    <https://unpaywall.org/data-feedback> with the bioRxiv DOI + the
    Zenodo URL — usually picks up within a week.

### Why both PDF and JATS

- **PDF** is what reviewers / readers actually open. Verbatim copy
  of whatever your build chain produced.
- **JATS XML** is what PMC, reference managers, and downstream
  text-miners ingest. Most journals derive the JATS at publication
  time; pre-depositing it makes the record machine-readable from day
  one and gives readers a stable structured representation regardless
  of which journal eventually accepts the paper.

The `paper/build.py` chain ([paper/README.md](../../paper/README.md))
produces both formats in one command via pandoc + WeasyPrint.

### Versioning the manuscript record

If the manuscript is revised post-bioRxiv (e.g. a v2 preprint), use
Zenodo's "New version" button on the existing manuscript record. The
bioRxiv DOI stays the same (or you also have a new bioRxiv version
DOI — that's a separate Zenodo record). One Zenodo concept-DOI covers
all versions of the manuscript on Zenodo's side.

## Safety reminders

- SWH submissions are **append-only**. Once SWH archives a piece of
  content, you can't ask them to delete it (their mission is permanent
  preservation). Don't submit content you don't want archived forever.
- Zenodo deposits start as **drafts** (private, deletable). After you
  publish, the bytes are **immutable** — you can edit metadata
  forever, but you can't add or remove files. To add files later,
  publish a new version (separate version DOI, same concept DOI).
- The Zenodo token in your env is sensitive; don't commit it.
