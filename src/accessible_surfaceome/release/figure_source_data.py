"""The figure-source-data tarball shipped with every numbered data release.

Each published figure is cited through its reproduction gist's SWHID, and the
gist bundles the one TSV the figure is drawn from. The Zenodo data record
also carries those same TSVs, plus the four canonical figure-input tables
they are cut from, as ``figure-source-data_{version}.tar.gz``, so the record
alone is enough to reanalyze every figure without GitHub or the gists.

The member list is not curated here. It is ``TSV_BUNDLE`` in
``scripts/figures/sync_figure_gists_bundle_data.py`` (the files bundled into
the gists) plus ``CANONICAL_FIGURE_INPUTS``, so a figure TSV added to the
gists ships in the next release without a second edit. Everything is read
from the working tree, so the tarball is rebuildable from a checkout at the
release commit, and it is built deterministically (sorted members, zeroed
mtime / owner, gzip mtime 0 and no embedded filename): the same checkout
always gives the same bytes, so an unchanged tarball re-syncs as unchanged.

Layout, under one top-level directory ``figure-source-data_{version}/``:

    README.md      what the files are, how to regenerate each figure, licence
    manifest.tsv   one row per (figure, file): MANIFEST_COLUMNS
    data/...       every TSV at its path in the repository
"""

from __future__ import annotations

import ast
import csv
import gzip
import hashlib
import io
import json
import re
import tarfile
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

TARBALL_PREFIX = "figure-source-data"
GIST_BUNDLE_SCRIPT = "scripts/figures/sync_figure_gists_bundle_data.py"
FIGURE_MANIFEST = "paper/figure_manifest.json"
GIST_MAP = "data/analysis/figures/gist_map.json"
SWHID_MAP = "data/analysis/figures/swhid_map.json"

# The four canonical figure-input tables (CLAUDE.md, "Figure-input TSV
# conventions"). The per-figure TSVs are cut from these; shipping them lets a
# reader rebuild or extend a figure table rather than only replot it.
CANONICAL_FIGURE_INPUTS: tuple[str, ...] = (
    "data/processed/candidate_universe/candidate_universe.tsv",
    "data/eval/triage_benchmark_v1.tsv",
    "data/processed/triage_bench/mainbench_canonical_v2.tsv",
    "data/processed/triage_bench/db_optimized_cutoffs.tsv",
)
OPTIMIZED_CUTOFFS = "data/processed/triage_bench/db_optimized_cutoffs.tsv"
# Figure inputs with no reproduction gist, as slug → (manuscript label, files).
# Figure 4 is a composed schematic; its funnel panel is drawn by
# scripts/figures/pipeline_funnel.py from the kept and the trimmed universe.
PANEL_INPUTS: dict[str, tuple[str, tuple[str, ...]]] = {
    "pipeline_funnel": (
        "Figure 4",
        (
            "data/processed/candidate_universe/candidate_universe_v3.tsv",
            "data/processed/candidate_universe/candidate_universe_v3_dropped.tsv",
        ),
    ),
}

MANIFEST_COLUMNS: tuple[str, ...] = (
    "role", "figure", "slug", "path", "sha256", "rows", "gist_url", "swhid", "generator",
)
ROLE_FIGURE = "figure_source"
ROLE_CANONICAL = "canonical_input"

# paper/figure_manifest.json section → the label the manuscript prints.
_FIGURE_SECTIONS = (
    ("figures", "Figure"),
    ("supplementary_figures", "Supplementary Figure"),
    ("appendix_figures", "Appendix Figure"),
)
_GIST_URL_RE = re.compile(r'^GIST_URL\s*=\s*"([^"]+)"', re.MULTILINE)


def tarball_name(version: str) -> str:
    return f"{TARBALL_PREFIX}_{version}.tar.gz"


def gist_bundle(repo_root: Path = REPO_ROOT) -> dict[str, list[str]]:
    """``TSV_BUNDLE`` from the gist sync script, read without importing it
    (the script shells out to ``gh``; tests/test_gist_single_tsv.py does the same)."""
    tree = ast.parse((repo_root / GIST_BUNDLE_SCRIPT).read_text(encoding="utf-8"))
    for node in tree.body:
        if (isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
                and node.target.id == "TSV_BUNDLE" and node.value is not None):
            return ast.literal_eval(node.value)
    raise RuntimeError(f"TSV_BUNDLE not found in {GIST_BUNDLE_SCRIPT}")


def member_paths(repo_root: Path = REPO_ROOT) -> list[str]:
    """Every data file the tarball carries, repo-relative and sorted."""
    paths = {p for ps in gist_bundle(repo_root).values() for p in ps}
    paths |= {p for _, ps in PANEL_INPUTS.values() for p in ps}
    return sorted(paths | set(CANONICAL_FIGURE_INPUTS))


def figure_labels(repo_root: Path = REPO_ROOT) -> dict[str, str]:
    """slug → manuscript label ("Figure 3", "Supplementary Figure 16")."""
    manifest = json.loads((repo_root / FIGURE_MANIFEST).read_text(encoding="utf-8"))
    labels: dict[str, str] = {}
    for section, word in _FIGURE_SECTIONS:
        for number, entry in manifest.get(section, {}).items():
            labels[entry["slug"]] = f"{word} {number}"
    return labels


def _label_sort_key(label: str) -> tuple[int, int]:
    for rank, (_, word) in enumerate(_FIGURE_SECTIONS):
        if label.startswith(f"{word} ") and label[len(word) + 1:].isdigit():
            return rank, int(label[len(word) + 1:])
    return len(_FIGURE_SECTIONS), 0  # not a manuscript figure: after all of them


def _gist_url(repo_root: Path, slug: str, gist_id: str) -> str:
    """The URL the figure's gist mirror embeds (tests/test_figure_gist_map_sync.py
    keeps it equal to gist_map.json); the bare gist URL if the mirror has none."""
    mirror = repo_root / "data/analysis/figures" / f"make_{slug}.py"
    if mirror.is_file():
        m = _GIST_URL_RE.search(mirror.read_text(encoding="utf-8"))
        if m and m.group(1).rstrip("/").endswith(gist_id):
            return m.group(1)
    return f"https://gist.github.com/{gist_id}"


def _read_member(repo_root: Path, path: str) -> bytes:
    full = repo_root / path
    if not full.is_file():
        raise FileNotFoundError(f"figure source file missing from the checkout: {path}")
    data = full.read_bytes()
    if data[:40].startswith(b"version https://git-lfs"):
        raise RuntimeError(f"{path} is an LFS pointer — run `git lfs pull` first")
    return data


def count_rows(data: bytes) -> int:
    """Data rows in a TSV (header excluded). Parsed, not line-counted: a quoted
    field can hold a newline (db_cutoff_tradeoff_points.tsv does)."""
    text = data.decode("utf-8")
    return max(sum(1 for _ in csv.reader(io.StringIO(text, newline=""), delimiter="\t")) - 1, 0)


def manifest_rows(repo_root: Path = REPO_ROOT) -> list[dict[str, str]]:
    """One row per (figure, file), manuscript figures in print order, then
    figures outside the manuscript, then the canonical inputs."""
    labels = figure_labels(repo_root)
    gists = json.loads((repo_root / GIST_MAP).read_text(encoding="utf-8"))
    swhids = json.loads((repo_root / SWHID_MAP).read_text(encoding="utf-8"))
    figure_rows = []
    for slug, paths in gist_bundle(repo_root).items():
        generator = f"scripts/figures/{slug}.py"
        for path in paths:
            data = _read_member(repo_root, path)
            figure_rows.append({
                "role": ROLE_FIGURE,
                "figure": labels.get(slug, ""),
                "slug": slug,
                "path": path,
                "sha256": hashlib.sha256(data).hexdigest(),
                "rows": str(count_rows(data)),
                "gist_url": _gist_url(repo_root, slug, gists[slug]) if slug in gists else "",
                "swhid": swhids.get(slug, ""),
                "generator": generator if (repo_root / generator).is_file() else "",
            })
    for slug, (label, paths) in PANEL_INPUTS.items():
        generator = f"scripts/figures/{slug}.py"
        for path in paths:
            data = _read_member(repo_root, path)
            figure_rows.append({
                "role": ROLE_FIGURE,
                "figure": label,
                "slug": slug,
                "path": path,
                "sha256": hashlib.sha256(data).hexdigest(),
                "rows": str(count_rows(data)),
                "gist_url": "",
                "swhid": "",
                "generator": generator if (repo_root / generator).is_file() else "",
            })
    figure_rows.sort(key=lambda r: (_label_sort_key(r["figure"]), r["slug"], r["path"]))
    canonical_rows = []
    for path in CANONICAL_FIGURE_INPUTS:
        data = _read_member(repo_root, path)
        canonical_rows.append({
            "role": ROLE_CANONICAL, "figure": "", "slug": "", "path": path,
            "sha256": hashlib.sha256(data).hexdigest(), "rows": str(count_rows(data)),
            "gist_url": "", "swhid": "", "generator": "",
        })
    return figure_rows + canonical_rows


def _manifest_tsv(rows: list[dict[str, str]]) -> bytes:
    lines = ["\t".join(MANIFEST_COLUMNS)]
    lines += ["\t".join(r[c] for c in MANIFEST_COLUMNS) for r in rows]
    return ("\n".join(lines) + "\n").encode("utf-8")


@dataclass(frozen=True)
class Summary:
    """Counts the deposit README states about the tarball."""

    n_files: int          # data TSVs (excludes README.md + manifest.tsv)
    n_figure_files: int   # per-figure source TSVs
    n_figures: int        # figures with a source TSV (manuscript or not)
    n_manuscript_figures: int
    optimized_cutoffs_rows: int
    compressed_bytes: int
    uncompressed_bytes: int


def figures_without_table(rows: list[dict[str, str]], repo_root: Path = REPO_ROOT) -> list[str]:
    """Manuscript figures with no gist source table (schematics, screenshots)."""
    have = {r["figure"] for r in rows if r["figure"]}
    return sorted((label for label in figure_labels(repo_root).values() if label not in have),
                  key=_label_sort_key)


def join_labels(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def _inner_readme(version: str, rows: list[dict[str, str]], repo_root: Path) -> str:
    root = tarball_name(version).removesuffix(".tar.gz")
    fig = [r for r in rows if r["role"] == ROLE_FIGURE]
    n_ms = len({r["figure"] for r in fig if r["figure"]})
    n_other = len({r["slug"] for r in fig if not r["figure"]})
    other = (f" plus {n_other} figure{'s' if n_other != 1 else ''} published only with the "
             "project's blog posts") if n_other else ""
    missing = figures_without_table(rows, repo_root)
    no_table = (f"{join_labels(missing)} {'has' if len(missing) == 1 else 'have'} no source table "
                "in a reproduction gist, so no row here.\n\n" if missing else "")
    opt_rows = next(r["rows"] for r in rows if r["path"] == OPTIMIZED_CUTOFFS)
    canonical = "\n".join(f"- `{p}`" for p in CANONICAL_FIGURE_INPUTS)
    return f"""# Figure source data — data release {version}

The tables every figure of the accessible-surfaceome manuscript is drawn from,
shipped with data release {version} of the Zenodo data record so the record
alone is enough to reanalyze each figure.

## Layout

Every file sits under `{root}/` at its path in the project repository
(<https://github.com/Deliverome-Project/accessible-surfaceome>), so
`tar xzf {tarball_name(version)} --strip-components=1` inside a checkout puts
each file where the figure scripts read it.

- `manifest.tsv` — one row per (figure, file); columns below.
- `data/...` — {len(fig)} per-figure source tables, each the exact file bundled
  into that figure's reproduction gist ({n_ms} manuscript figures{other}; Figure
  4's funnel tables have no gist, so their gist and SWHID columns are blank), and
  the four canonical figure-input tables the per-figure tables are cut from:

{canonical}

| `manifest.tsv` column | Meaning |
|---|---|
| `role` | `figure_source` (a figure's own table) or `canonical_input` (one of the four tables above) |
| `figure` | the manuscript label (`Figure 3`, `Supplementary Figure 16`); blank for a figure outside the manuscript and for canonical inputs |
| `slug` | the figure's short name; its gist script is `make_<slug>.py` |
| `path` | the file's path inside `{root}/` (= its repository path) |
| `sha256` | sha256 of the file's bytes |
| `rows` | data rows, header excluded |
| `gist_url` | the figure's reproduction gist (script + this table + README) |
| `swhid` | Software Heritage identifier of that gist's commit, the figure's citation |
| `generator` | the canonical figure script in the code record |

{no_table}Verify the files, from inside `{root}/`:

```python
import csv, hashlib
for row in csv.DictReader(open("manifest.tsv"), delimiter="\\t"):
    assert hashlib.sha256(open(row["path"], "rb").read()).hexdigest() == row["sha256"], row["path"]
```

## Regenerating a figure

Each figure regenerates from its gist with `uv run make_<slug>.py` (the gist
bundles the same table, and the script declares its own dependencies), or from
the project's code record at the release commit with
`uv run python scripts/figures/<slug>.py`.

## `db_optimized_cutoffs.tsv` is a positive list

`data/processed/triage_bench/db_optimized_cutoffs.tsv` gives, per UniProt
accession, each source database's native surface flag and the
SurfaceBench-recalibrated one (`uniprot_optimized`, `cspa_optimized`; GO, SURFY
and HPA are unchanged by the recalibration). It lists only the {int(opt_rows):,}
accessions that pass at least one optimized cutoff. An accession absent from it
is 0 under the optimized rule — never fall back to its native flag.

## Licence

CC0 1.0: dedicated to the public domain, to the extent we hold rights in it.
The tables carry derived values (flags, scores, identifiers, coded reasons)
computed from public sources that keep their own terms; the per-source table
is the project's `LICENSING.md`.
"""


def _build(version: str, repo_root: Path) -> tuple[bytes, Summary]:
    rows = manifest_rows(repo_root)
    root = tarball_name(version).removesuffix(".tar.gz")
    members: dict[str, bytes] = {p: _read_member(repo_root, p) for p in member_paths(repo_root)}
    members["manifest.tsv"] = _manifest_tsv(rows)
    members["README.md"] = _inner_readme(version, rows, repo_root).encode("utf-8")
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w", format=tarfile.PAX_FORMAT) as tar:
        for name in sorted(members):
            data = members[name]
            info = tarfile.TarInfo(f"{root}/{name}")
            info.size, info.mtime, info.mode = len(data), 0, 0o644
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            tar.addfile(info, io.BytesIO(data))
    raw = buf.getvalue()
    out = io.BytesIO()
    with gzip.GzipFile(fileobj=out, mode="wb", mtime=0, filename="") as gz:
        gz.write(raw)
    blob = out.getvalue()
    fig = [r for r in rows if r["role"] == ROLE_FIGURE]
    summary = Summary(
        n_files=len(members) - 2,
        n_figure_files=len(fig),
        n_figures=len({r["figure"] or r["slug"] for r in fig}),
        n_manuscript_figures=len({r["figure"] for r in fig if r["figure"]}),
        optimized_cutoffs_rows=int(next(r["rows"] for r in rows if r["path"] == OPTIMIZED_CUTOFFS)),
        compressed_bytes=len(blob),
        uncompressed_bytes=sum(len(members[p]) for p in member_paths(repo_root)),
    )
    return blob, summary


@lru_cache(maxsize=8)
def summary(version: str, repo_root: Path = REPO_ROOT) -> Summary:
    """Counts + sizes of the tarball a build would produce (builds it in memory)."""
    return _build(version, repo_root)[1]


def build_figure_source_tarball(out_dir: Path, version: str, repo_root: Path = REPO_ROOT) -> Path:
    """Write ``figure-source-data_{version}.tar.gz`` into ``out_dir``; return its path."""
    blob, _ = _build(version, repo_root)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / tarball_name(version)
    out.write_bytes(blob)
    return out
