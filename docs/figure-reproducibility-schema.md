# Figure Reproducibility Schema (v1)

A figure is **reproducible** if, given just the image bytes, a stranger
can find:

1. the **code** that made it
2. the **environment** it ran in
3. the **data** it consumed

This document defines the minimal schema we embed into every figure
shipped from `accessible-surfaceome` so a downstream tool (such as the
deliverome figure-reproducibility page) can verify reproduction.

## Embedded key

Each figure carries a single canonical metadata key — `provenance` —
holding a JSON blob. Stored in the format's native metadata slot:

| Format | Slot |
|---|---|
| PNG | `tEXt` chunk, key `provenance` |
| PDF | `Keywords` field of Document Info dict |
| SVG | `<metadata id="provenance">` element |

Older `Source` (PNG) / `dc:source` (PDF) fields are preserved for
back-compat.

## Blob shape

```json
{
  "schema_version": "1",
  "title":      "M1 surface DB overlap — 5-way Venn",
  "gist_url":   "https://gist.github.com/beccajcarlson/d655abfc9c7deeaff1cfbe584de96ffa",
  "gist_sha":   "<40-char hex>",
  "swhid":      "swh:1:snp:<40-char hex>",
  "doi": null,
  "repo":       "Deliverome-Project/accessible-surfaceome",
  "repo_path":  "scripts/figures/triage_bench_db_venn.py",
  "repo_ref":   "<40-char commit SHA>",
  "repo_tag":   null,
  "data": [
    {
      "url":    "https://raw.githubusercontent.com/.../<commit-sha>/.../data.tsv",
      "sha256": "<64-char hex>",
      "swhid":  "swh:1:cnt:<40-hex>",
      "doi":    null
    }
  ]
}
```

All fields except `schema_version` and `title` are optional individually,
but at least one durable identifier (`swhid`, `doi`, or
`repo + repo_path + repo_ref-as-commit-sha`) is required.

### Data durability (per `data[]` entry)

`url + sha256` is **content-verifiable** (you can prove the bytes are
right when you find them) but not **storage-durable** (the URL can
disappear). For research-grade durability on data:

- `swhid` — Software Heritage assigns a content-addressed identifier
  per file blob (`swh:1:cnt:<40-hex>`). Free, durable, no DOI.
- `doi` — Zenodo / DataCite DOI for a data deposit. Durable, citeable
  in papers.

Each `data[]` entry accepts all three (`sha256`, `swhid`, `doi`)
independently. Validation enforces format only — the schema treats
content-verifiable and storage-durable as orthogonal properties.

## Validation rules

Six checks, applied in order. Code durability and data durability are
treated as independent concerns — a figure can have durably stored code
but mutable data, or vice versa, and each is reported on its own axis.

1. **Provenance present** — the metadata slot holds a JSON blob with
   `schema_version: "1"`.
2. **Code is locatable** — at least one of the code locators resolves:
   `swhid`, `doi`, `repo + repo_path + repo_ref`, or `gist_url`.
3. **Code environment is pinned** — the resolved artifact carries PEP
   723 inline metadata, `requirements.txt`, `pyproject.toml`,
   `environment.yml`, `renv.lock`, or a `Dockerfile`.
4. **Data is locatable and content-verifiable** — for every `data[]`
   entry: the URL resolves AND at least one of `sha256` / `swhid` /
   `doi` is declared. URL-only entries are locatable but not
   content-verifiable (warn).
5. **Code is durably stored** — `swhid` OR `doi` is present at
   the top level. A bare commit SHA (repo or gist) is locatable but
   storage-fragile (the repo or gist can be deleted) — warns until the
   code is archived to Software Heritage or Zenodo.
6. **Data is durably stored** — every `data[]` entry has `swhid` OR
   `doi`. `sha256` alone is content-verifiable but storage-fragile —
   warns. Any entry with none of `sha256` / `swhid` / `doi` fails.

Checks 2 and 5 reference the same set of code locators (`gist_url`,
`gist_sha`, `swhid`, `doi`, `repo + repo_path + repo_ref`), so a
"can I find the code?" answer is consistent with a "is the code
durable?" answer — the distinction is whether the storage backing the
locator is durable, not which fields you used to declare it.

`repo_ref` must be a 40-character hex commit SHA for the locator to
satisfy check 2's stable-id branch and check 5's storage-fragile warn
branch; tags don't qualify (use `repo_tag` for the human-readable
release tag).

## Durability tiers

|  | Identifier durable? | Storage durable? | Score |
|---|---|---|---|
| Gist URL (no SHA) | ❌ | ❌ | ⚠️ |
| Gist URL + revision SHA | ✅ | ❌ (gist deletable) | 🟡 |
| Repo + tag | ❌ (force-movable) | ❌ | ⚠️ |
| Repo + commit SHA | ✅ | ❌ (repo deletable) | 🟡 |
| SWHID | ✅ | ✅ (Software Heritage mission) | 🟢 |
| Zenodo DOI | ✅ (per-version) | ✅ (CERN) | 🟢🎓 |

## Save Code Now (Software Heritage)

To mint a SWHID for a gist:

```bash
curl -X POST "https://archive.softwareheritage.org/api/1/origin/save/git/url/<gist-url>/"
```

Poll the status until `succeeded`, then read the snapshot SWHID:

```bash
curl -s "https://archive.softwareheritage.org/api/1/origin/<gist-url>/visits/latest/" \
  | jq -r '"swh:1:snp:" + .snapshot'
```

Old SWHIDs continue to resolve to old content forever; new edits get
new SWHIDs.

## Implementation references

- Schema constants + validator: `src/accessible_surfaceome/_provenance.py`
- Metadata embedder: `scripts/figures/embed_figure_gist_metadata.py`
- Conformance test: `tests/test_figure_provenance.py`
- Worked example (Venn diagram):
  - canonical generator: `scripts/figures/triage_bench_db_venn.py`
  - standalone gist: <https://gist.github.com/beccajcarlson/d655abfc9c7deeaff1cfbe584de96ffa>
