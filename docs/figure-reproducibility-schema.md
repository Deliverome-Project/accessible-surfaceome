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
  "zenodo_doi": null,
  "repo":       "Deliverome-Project/accessible-surfaceome",
  "repo_path":  "scripts/triage_bench_db_venn.py",
  "repo_ref":   "<40-char commit SHA>",
  "repo_tag":   null,
  "data": [
    {
      "url":    "https://raw.githubusercontent.com/.../<commit-sha>/.../data.tsv",
      "sha256": "<64-char hex>"
    }
  ]
}
```

All fields except `schema_version` and `title` are optional individually,
but at least one durable identifier (`swhid`, `zenodo_doi`, or
`repo + repo_path + repo_ref-as-commit-sha`) is required.

## Validation rules

Five checks, applied in order:

1. **Provenance present** — the metadata slot holds a JSON blob with
   `schema_version: "1"`.
2. **Provenance resolves** — `gist_url` / `swhid` / `zenodo_doi` returns
   HTTP 200.
3. **Code has pinned deps** — the resolved artifact carries PEP 723
   inline metadata, `requirements.txt`, `pyproject.toml`,
   `environment.yml`, `renv.lock`, or a `Dockerfile`.
4. **Data reachable** — each entry in `data[]` has a URL that resolves,
   or a DOI that resolves.
5. **Durable identifier** — `swhid` OR `zenodo_doi` OR
   (`repo + repo_path + repo_ref-as-commit-sha`) is set.

Checks 1–4 are must-pass for "reproducible." Check 5 is must-pass for
"durably reproducible." A figure that passes 1–4 but fails 5 gets a
⚠️ "mutable" warning.

`repo_ref` must be a 40-character hex commit SHA for durability; tags
are mutable and don't qualify (use `repo_tag` for the human-readable
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
- Metadata embedder: `scripts/embed_figure_gist_metadata.py`
- Conformance test: `tests/test_figure_provenance.py`
- Worked example (Venn diagram):
  - canonical generator: `scripts/triage_bench_db_venn.py`
  - standalone gist: <https://gist.github.com/beccajcarlson/d655abfc9c7deeaff1cfbe584de96ffa>
