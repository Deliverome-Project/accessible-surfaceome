# Tedman GPCR HA Control Tag Sites — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ingest Tedman et al.'s experimentally-validated N-terminal HA epitope-tag insertion sites for ~766 human GPCRs as a new `screen_validated` class of control tag sites, attach the measured HA-immunostaining surface expression, and surface them (canonical + per-isoform) in the viewer, publishing canonical sites live to public D1.

**Architecture:** Extend the existing `dev` tag-site subsystem — do not build a parallel one. A build script joins the Mendeley plasmid-map index (HA position) with the `deliverome-external` surface screen (immunostaining PME), resolves canonical UniProt IDs, and writes a committed curated TSV. An emitter merges one canonical `screen_validated` `TaggedSite` per gene (plus per-isoform control pins for isoforms already in the viewer) into `viewer/public/tag-sites/{SYMBOL}.json` via the existing `emit_tag_sites_json` merge-writer. Canonical sites sync to public D1 (`tag_site_public`, no schema change — `provenance` is free-text) and the Worker serves them; isoform pins ship static-only and go live on the Pages deploy. A new `screen_validated` provenance is wired through the Python constructor + TS types + card + tab gate + overlay + design tokens; it is durable because neither regenerate script touches non-`deterministic_computed`/non-`literature_retrieved` provenances.

**Tech Stack:** Python 3.11 (`uv`, `openpyxl`, `requests`), the repo's `tag_sites`/`cloud.tag_sites`/`gene_lookup` modules + `D1Client`; Next.js 16 viewer (TypeScript, vitest); Cloudflare D1 + Worker.

**Worktree:** `/Users/rebeccacarlson/Git/accessible-surfaceome/.claude/worktrees/gpcr-tag-sites-dev` (branch `claude/gpcr-control-tag-sites-tedman`, off `origin/dev`). Run everything here. Spec: [docs/superpowers/specs/2026-09-01-tedman-gpcr-control-tag-sites-design.md](../specs/2026-09-01-tedman-gpcr-control-tag-sites-design.md).

---

## Key facts the implementer must not rediscover

- **Junction convention** (`data/tag_sites/positive_controls.md`): `after N` = tag between UniProt-canonical residues `N` and `N+1`. `expected_residue` = residue `N` (the residue before the junction); for a before-residue-1 N-terminal tag, `insert_after_residue = null` and the anchor residue is residue 1.
- **Tedman `ha_insert_position`** is a `"X-Y"` string in **construct-ORF** numbering ("position 1 = first codon/AA"). `junction = int(X)`. `"0-1"` (834/946 rows) = bare N-terminal (before residue 1) → `insert_after_residue = null`. The other 112 track signal-peptide receptors (tag after SP cleavage, e.g. `"27-28"`).
- **`tagged_site()` in `tag_sites/model.py` hardcodes `provenance="deterministic_computed"`** — control sites need a **new** constructor emitting the same `TAGGED_SITE_KEYS` set with `provenance="screen_validated"`, `det_path=None`.
- **Per-gene JSON shape** = `TaggedSitesFile` `{has_data, gene_symbol, uniprot_acc, sites[], isoform_pins[], ortholog_pins[]}`. `emit_tag_sites_json(gene_symbol, uniprot_acc, sites, *, out_dir, isoform_pins=None)` merges by `site_id` (new wins) — reuse it, do not rewrite.
- **D1 sync** (`scripts/sync_tag_sites_to_d1.py` → `cloud/tag_sites.py::publish_tag_sites`) is replace-all-per-gene; `flat_row` passes `provenance` through verbatim (free-text TEXT column) — **no schema change** for `screen_validated`. `isoform_pins` are **not** synced to D1 (static-only; `rows_for_file` reads only `data["sites"]`).
- **isoform pins** identify their isoform by **UniProt isoform accession** (`isoform_id`, e.g. `P35372-10`), carry `isoform_residue` (isoform's own 1-indexed axis) + `left_pct`; the isoform must already exist in `record.deterministic_features.isoform_topologies` or the pin renders nowhere. No ENST↔UniProt-isoform resolver exists — match by protein sequence.
- **Records** come from the Worker: `GET {SURFACEOME_API_BASE}/v1/genes/{symbol}` (default `https://api.deliverome.org/surfaceome`), `.deterministic_features.canonical_topology.sequence` + `.isoform_topologies[].{isoform_id, sequence}`.
- **Citation** (`data/tag_sites/positive_controls.md` §Sources style): Tedman et al., *Efficient experimental characterization of the GPCRome via deep receptor scanning*, Nat Commun 2026, DOI `10.1038/s41467-026-76564-7`; bioRxiv `2025.09.19.677468` = `PMC12458215`; data DOI `10.17632/3b4n36z4bg`. The Nat Commun PMID is not yet indexed — the build attempts a DOI→PMID lookup and falls back to the PMC id.

---

## File structure

**New files**
- `data/external/tedman_gpcr_screen/PROVENANCE.md` — source pins (committed); the xlsx inputs cache here (gitignored).
- `data/tag_sites/tedman_gpcr_controls.tsv` — curated control table (committed); `tedman_gpcr_controls.md` — provenance.
- `src/accessible_surfaceome/tag_sites/control.py` — `control_tag_site()` + `control_isoform_pin()` constructors.
- `src/accessible_surfaceome/tag_sites/tedman.py` — pure helpers: `parse_ha_position`, `map_junction_to_canonical`, `match_isoform`.
- `scripts/build_tedman_gpcr_controls.py` — inputs → `tedman_gpcr_controls.tsv`.
- `scripts/emit_tedman_tag_sites.py` — TSV + records → per-gene JSON.
- Tests: `tests/test_tedman_tag_sites.py` (Python), `viewer/tests/tag_sites_screen_validated.test.ts`, `viewer/tests/tagged_sites_card_screen.test.tsx`.

**Modified files**
- `src/accessible_surfaceome/tag_sites/isoform.py` — export `control_isoform_pin` helper usage (constructor lives in `control.py`).
- `viewer/lib/tag-sites-types.ts`, `viewer/lib/tag-sites-overlay.ts`.
- `viewer/components/surfaceome/TaggedSitesCard/TaggedSitesCard.tsx`.
- `viewer/components/surfaceome/GeneDetail/GeneDetail.tsx`.
- `viewer/components/surfaceome/IsoformsCard/IsoformsCard.tsx`, `.../IsoformsCard/TopologyBar.tsx`.
- `viewer/app/design-tokens.css`.
- The ~766 generated `viewer/public/tag-sites/{SYMBOL}.json`.

---

# PHASE 1 — Extraction → curated TSV

### Task 1: Provenance + input acquisition

**Files:**
- Create: `data/external/tedman_gpcr_screen/PROVENANCE.md`
- Create: `data/external/tedman_gpcr_screen/.gitignore`

- [ ] **Step 1: Write the provenance doc**

`data/external/tedman_gpcr_screen/PROVENANCE.md`:
```markdown
# Tedman GPCR deep-receptor-scanning inputs

Two inputs, cached here (xlsx gitignored — CC BY 4.0 deposit data):

- `GPCR_Library_Index_Final.xlsx` — HA tag insertion position per plasmid.
  Mendeley Data 10.17632/3b4n36z4bg, "Doc S1. GPCR Plasmid Maps".
  sha256 574c1c57e94904f6597b2e2958a68f7f4f39671a1d1d20a7b95d7c508cb30bb0
  (byte-identical across deposit v1/v2/v3).
- `tedman2025_gpcr_screen_media-2.xlsx` — HA-immunostaining surface expression.
  deliverome-external://tedman-gpcr-surface-screen/2025-09-19/ (canonical);
  sha256 c0fbcbd1df5ab488e026239fb55aa92a7a8d9171154bec20bc837f6fb9685286.
  Byte-identical immunostaining cols to the Mendeley "Doc S2. GPCR DRS Master Table.xlsx".

Paper: Tedman et al., Nat Commun 2026, doi:10.1038/s41467-026-76564-7
(bioRxiv 2025.09.19.677468 = PMC12458215).
```

- [ ] **Step 2: gitignore the xlsx**

`data/external/tedman_gpcr_screen/.gitignore`:
```
*.xlsx
```

- [ ] **Step 3: Stage the input files into the cache**

Copy the verified surface-screen mirror and download the pinned library index:
```bash
WT=/Users/rebeccacarlson/Git/accessible-surfaceome/.claude/worktrees/gpcr-tag-sites-dev
DST="$WT/data/external/tedman_gpcr_screen"
mkdir -p "$DST"
cp "$(find /Users/rebeccacarlson/Git/deliverome-analysis -name tedman2025_gpcr_screen_media-2.xlsx -not -path '*/.git/*' | head -1)" "$DST/"
curl -sL -o "$DST/GPCR_Library_Index_Final.xlsx" "https://data.mendeley.com/public-files/datasets/3b4n36z4bg/files/67723077-187c-4b19-ad0f-6dd93cac3da6/file_downloaded"
shasum -a 256 "$DST"/*.xlsx
```
Expected: media-2 = `c0fbcbd1…`, index = `574c1c57…`.

- [ ] **Step 4: Commit**
```bash
git add data/external/tedman_gpcr_screen/PROVENANCE.md data/external/tedman_gpcr_screen/.gitignore
git commit -m "data(tag-sites): provenance + gitignore for Tedman GPCR screen inputs"
```

---

### Task 2: HA-position parsing + junction verification (pure, TDD)

**Files:**
- Create: `src/accessible_surfaceome/tag_sites/tedman.py`
- Test: `tests/test_tedman_tag_sites.py`

- [ ] **Step 1: Write the failing test**

`tests/test_tedman_tag_sites.py`:
```python
import pytest
from accessible_surfaceome.tag_sites.tedman import parse_ha_position, map_junction_to_canonical


def test_parse_ha_position_nterm():
    assert parse_ha_position("0-1") == 0


def test_parse_ha_position_post_sp():
    assert parse_ha_position("27-28") == 27


def test_parse_ha_position_bad():
    with pytest.raises(ValueError):
        parse_ha_position("garbage")


def test_map_junction_zero_is_bare_nterm():
    # seq MKT...; junction 0 -> insert_after_residue None, anchor residue 1 = M
    r = map_junction_to_canonical(0, "MKTIIALSYIFCLVFA")
    assert r.insert_after_residue is None
    assert r.residue_before is None
    assert r.residue_after == "M"
    assert r.verified is True


def test_map_junction_post_sp_matches_sequence():
    seq = "MKTIIALSYIFCLVFA" + "QDLPPQ"  # residue 16 = A (end of a 16-aa SP)
    r = map_junction_to_canonical(16, seq)
    assert r.insert_after_residue == 16
    assert r.residue_before == "A"       # residue 16
    assert r.residue_after == "Q"        # residue 17
    assert r.residue_label == "A16"
    assert r.verified is True


def test_map_junction_out_of_range_unverified():
    r = map_junction_to_canonical(999, "MKT")
    assert r.verified is False
```

- [ ] **Step 2: Run it — expect ImportError/fail**

Run: `cd $WT && uv run pytest tests/test_tedman_tag_sites.py -q`
Expected: FAIL (module/function not defined).

- [ ] **Step 3: Implement**

`src/accessible_surfaceome/tag_sites/tedman.py`:
```python
"""Pure helpers for the Tedman GPCR HA control tag-site build.

No I/O — parses the Mendeley `ha_insert_position` string and projects the
junction onto a canonical UniProt sequence, following the "after N" convention
in data/tag_sites/positive_controls.md.
"""
from __future__ import annotations

from dataclasses import dataclass


def parse_ha_position(value: str) -> int:
    """`"0-1"` -> 0, `"27-28"` -> 27 (the residue the HA tag is inserted AFTER,
    in the construct's own 1-indexed numbering). Raises ValueError on junk."""
    left = str(value).strip().split("-", 1)[0]
    if not left.lstrip("-").isdigit():
        raise ValueError(f"unparseable ha_insert_position: {value!r}")
    return int(left)


@dataclass(frozen=True)
class JunctionMapping:
    insert_after_residue: int | None   # None == bare N-terminal (before residue 1)
    residue_before: str | None
    residue_after: str | None
    residue_label: str | None
    verified: bool


def map_junction_to_canonical(junction: int, canonical_seq: str) -> JunctionMapping:
    """Project a construct-ORF junction onto the canonical UniProt sequence.

    junction 0  -> bare N-terminal tag (insert_after_residue None); anchor is
                   residue 1 (residue_after). verified iff the sequence is non-empty.
    junction N>0 -> tag between residues N and N+1; residue_before = seq[N-1].
                    verified iff 1 <= N <= len(seq).
    """
    seq = canonical_seq or ""
    if junction <= 0:
        after = seq[0] if seq else None
        return JunctionMapping(None, None, after, None, verified=bool(seq))
    if junction > len(seq):
        return JunctionMapping(junction, None, None, None, verified=False)
    before = seq[junction - 1]
    after = seq[junction] if junction < len(seq) else None
    return JunctionMapping(junction, before, after, f"{before}{junction}", verified=True)
```

- [ ] **Step 4: Run — expect PASS**

Run: `cd $WT && uv run pytest tests/test_tedman_tag_sites.py -q`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**
```bash
git add src/accessible_surfaceome/tag_sites/tedman.py tests/test_tedman_tag_sites.py
git commit -m "feat(tag-sites): Tedman HA-position parse + canonical junction mapping"
```

---

### Task 3: Build the curated TSV

**Files:**
- Create: `scripts/build_tedman_gpcr_controls.py`
- Create: `data/tag_sites/tedman_gpcr_controls.md`
- Output: `data/tag_sites/tedman_gpcr_controls.tsv`

- [ ] **Step 1: Implement the build script**

`scripts/build_tedman_gpcr_controls.py` — reads both xlsx, resolves canonical UniProt via the HGNC-ID resolver, maps junctions, joins surface expression on `SYMBOL_ENST`, writes the TSV. Core:
```python
"""Build data/tag_sites/tedman_gpcr_controls.tsv from the Tedman GPCR screen.

Join keys: `Receptor Name` (SYMBOL_ENST) between the surface screen and the
plasmid-map index. Canonical UniProt + sequence via resolve_by_hgnc_id (HGNC-ID
path — never bare symbols). Junction projected to canonical numbering + verified.

    uv run python scripts/build_tedman_gpcr_controls.py            # writes the TSV
    uv run python scripts/build_tedman_gpcr_controls.py --limit 20 # smoke subset
"""
from __future__ import annotations

import argparse, csv, logging
from pathlib import Path

import openpyxl

from accessible_surfaceome.env import load_env
from accessible_surfaceome.http_cache import CachedHTTP           # existing shared HTTP
from accessible_surfaceome.paths import REPO_ROOT
from accessible_surfaceome.tools.gene_lookup import resolve_by_hgnc_id
from accessible_surfaceome.tag_sites.tedman import parse_ha_position, map_junction_to_canonical

log = logging.getLogger("build_tedman")
SRC = REPO_ROOT / "data" / "external" / "tedman_gpcr_screen"
OUT = REPO_ROOT / "data" / "tag_sites" / "tedman_gpcr_controls.tsv"
COLS = [
    "gene_symbol", "hgnc_id", "uniprot_acc", "ensembl_gene_id", "ensembl_transcript_id",
    "is_canonical", "gpcr_class", "site_kind", "junction_after_residue", "expected_residue",
    "tag", "tag_length", "surface_expression_pme", "surface_expression_sd",
    "verified", "source_key",
]


def _index_rows(path: Path) -> list[dict]:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb["Sheet1"]; rows = list(ws.iter_rows(values_only=True)); hdr = list(rows[0])
    idx = {name: i for i, name in enumerate(hdr)}
    def g(r, name):
        for k, i in idx.items():
            if k and k.lower().startswith(name.lower()):
                return r[i]
        return None
    return [{
        "symbol": g(r, "hgnc_symbol"), "uniprot": g(r, "uniprot_id"),
        "ensg": g(r, "ensembl_gene_id"), "enst": g(r, "ensembl_transcript_id"),
        "gpcr_class": g(r, "gpcr_class"), "alt": g(r, "alt_isoform"),
        "ha": g(r, "ha_insert_position"),
    } for r in rows[1:] if g(r, "hgnc_symbol")]


def _staining(path: Path) -> dict[str, tuple[float, float]]:
    """`Receptor Name` -> (Immunostaining Intensity, SD) from the Canonical sheet.
    Receptor Name may be SYMBOL_ENST or SYMBOL_ENST_SP_HA — key on SYMBOL_ENST prefix."""
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb["Canonical"]; rows = list(ws.iter_rows(values_only=True)); hdr = list(rows[0])
    ix = {n: i for i, n in enumerate(hdr)}
    out: dict[str, tuple[float, float]] = {}
    for r in rows[1:]:
        name = r[ix["Receptor Name"]]
        if not name:
            continue
        key = "_".join(str(name).split("_")[:2])   # SYMBOL_ENST
        out[key] = (r[ix["Immunostaining Intensity"]], r[ix["Immunostaining Standard Deviation"]])
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    load_env()
    http = CachedHTTP()
    index = _index_rows(SRC / "GPCR_Library_Index_Final.xlsx")
    stain = _staining(SRC / "tedman2025_gpcr_screen_media-2.xlsx")
    if args.limit:
        index = index[: args.limit]

    seq_cache: dict[str, tuple[str, str, str]] = {}   # symbol -> (hgnc_id, acc, seq)
    written = 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS, delimiter="\t")
        w.writeheader()
        for row in index:
            sym = row["symbol"]
            if sym not in seq_cache:
                try:
                    b = resolve_by_hgnc_id_for_symbol(sym, row["uniprot"], http)  # see Step 2
                    seq_cache[sym] = b
                except Exception as e:                      # noqa: BLE001
                    log.warning("resolve failed %s: %s", sym, e); seq_cache[sym] = ("", "", "")
            hgnc_id, acc, seq = seq_cache[sym]
            jm = map_junction_to_canonical(parse_ha_position(row["ha"]), seq)
            key = f"{sym}_{row['enst']}"
            pme, sd = stain.get(key, (None, None))
            w.writerow({
                "gene_symbol": sym, "hgnc_id": hgnc_id, "uniprot_acc": acc,
                "ensembl_gene_id": row["ensg"], "ensembl_transcript_id": row["enst"],
                "is_canonical": str(row["alt"] == "canonical").lower(),
                "gpcr_class": row["gpcr_class"], "site_kind": "terminal_n",
                "junction_after_residue": "" if jm.insert_after_residue is None else jm.insert_after_residue,
                "expected_residue": jm.residue_before or (jm.residue_after or ""),
                "tag": "HA", "tag_length": 9,
                "surface_expression_pme": "" if pme is None else round(float(pme), 1),
                "surface_expression_sd": "" if sd is None else round(float(sd), 1),
                "verified": str(jm.verified).lower(), "source_key": "tedman2026",
            })
            written += 1
    log.info("wrote %d rows -> %s", written, OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Add the symbol→(hgnc_id, acc, seq) resolver shim**

The cohort/xlsx gives a symbol + a UniProt id but the canonical rule requires the HGNC-ID path. Add this near the top of the script (reads `hgnc_id` from the cohort file, then `resolve_by_hgnc_id`):
```python
import functools
import pandas as pd

COHORT = REPO_ROOT / "data" / "external" / "ncbi_gene_info" / "Homo_sapiens.protein_coding.with_hgnc.tsv"

@functools.lru_cache(maxsize=1)
def _symbol_to_hgnc() -> dict[str, str]:
    df = pd.read_csv(COHORT, sep="\t", dtype=str)
    return dict(zip(df["hgnc_symbol"], df["hgnc_id"]))

def resolve_by_hgnc_id_for_symbol(symbol: str, uniprot_hint: str, http) -> tuple[str, str, str]:
    hgnc_id = _symbol_to_hgnc().get(symbol)
    if not hgnc_id:
        raise ValueError(f"{symbol} not in cohort")
    bundle = resolve_by_hgnc_id(hgnc_id, http=http)
    return hgnc_id, bundle.uniprot_acc, bundle.sequence   # IdentifierBundle carries the canonical seq
```
NOTE: if `IdentifierBundle` does not expose `.sequence`, fetch the canonical FASTA via the resolver's UniProt client (the module already fetches UniProt) — read `gene_lookup.py` for the exact attribute before running, and adjust this one line.

- [ ] **Step 3: Smoke-run on a subset**

Run: `cd $WT && uv run python scripts/build_tedman_gpcr_controls.py --limit 20`
Expected: `wrote 20 rows -> …/tedman_gpcr_controls.tsv`; open it and confirm `FFAR1` has `junction_after_residue` empty (0-1 → None) and a numeric `surface_expression_pme`.

- [ ] **Step 4: Full run + sanity assertions**

Run:
```bash
cd $WT && uv run python scripts/build_tedman_gpcr_controls.py
uv run python - <<'PY'
import csv
rows = list(csv.DictReader(open("data/tag_sites/tedman_gpcr_controls.tsv"), delimiter="\t"))
print("rows:", len(rows))
print("verified:", sum(r["verified"]=="true" for r in rows))
print("with PME:", sum(bool(r["surface_expression_pme"]) for r in rows))
print("bare N-term:", sum(r["junction_after_residue"]=="" for r in rows))
PY
```
Expected: ~946 rows; the vast majority `verified=true`; ~834 bare N-term; most with PME. Investigate any gene where `verified=false` AND `junction_after_residue` is non-empty (SP-numbering shift) — these keep `verified=false` and are excluded from emission in Task 10.

- [ ] **Step 5: Write `tedman_gpcr_controls.md` + commit**

Write a short provenance md (mirror `positive_controls.md`'s header: source, join keys, junction convention, "screen_validated, kept separate from the hand-curated positive_controls.tsv benchmark"). Then:
```bash
git add data/tag_sites/tedman_gpcr_controls.tsv data/tag_sites/tedman_gpcr_controls.md scripts/build_tedman_gpcr_controls.py
git commit -m "feat(tag-sites): build Tedman GPCR HA control table from Mendeley + surface screen"
```

---

# PHASE 2 — `screen_validated` provenance wiring

### Task 4: Python `control_tag_site()` constructor (TDD)

**Files:**
- Create: `src/accessible_surfaceome/tag_sites/control.py`
- Test: `tests/test_tedman_tag_sites.py` (append)

- [ ] **Step 1: Append failing test**
```python
from accessible_surfaceome.tag_sites.control import control_tag_site
from accessible_surfaceome.tag_sites.model import TAGGED_SITE_KEYS

def test_control_tag_site_shape_and_provenance():
    s = control_tag_site(
        site_id="ADRB2-nterm-tedman", gene_symbol="ADRB2", uniprot_acc="P07550",
        insert_after_residue=None, residue_before=None, residue_after="M",
        pme=1234.5, pme_sd=67.8,
        sources=[{"citation": "Tedman et al. 2026", "doi": "10.1038/s41467-026-76564-7"}],
    )
    assert set(s.keys()) == TAGGED_SITE_KEYS
    assert s["provenance"] == "screen_validated"
    assert s["det_path"] is None
    assert s["site_kind"] == "terminal_n"
    assert s["tag_type"] == "HA"
    assert s["extracellular"] is True
    assert "1234.5" in s["functional_impact_measured"]   # PME rides in free-text evidence
```

- [ ] **Step 2: Run — expect FAIL** (`cd $WT && uv run pytest tests/test_tedman_tag_sites.py -q`)

- [ ] **Step 3: Implement**

`src/accessible_surfaceome/tag_sites/control.py`:
```python
"""Constructors for `screen_validated` control tag sites (Tedman GPCR screen).

Same key set as tag_sites.model.tagged_site, but provenance="screen_validated",
det_path=None, and the measured HA-immunostaining surface expression carried as
free-text in the evidence fields (no schema field — per design decision)."""
from __future__ import annotations

from typing import Any, Optional

from accessible_surfaceome.tag_sites.model import residue_label


def _pme_text(pme: Optional[float], sd: Optional[float]) -> str:
    if pme is None:
        return "Surface-displayed HA tag (Tedman deep receptor scanning)"
    sd_txt = f" ± {sd:g}" if sd is not None else ""
    return f"Surface immunostaining PME {pme:g}{sd_txt} (HA immunostaining, Tedman deep receptor scanning)"


def control_tag_site(
    *,
    site_id: str, gene_symbol: str, uniprot_acc: str,
    insert_after_residue: Optional[int], residue_before: Optional[str], residue_after: Optional[str],
    pme: Optional[float] = None, pme_sd: Optional[float] = None,
    sources: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    return {
        "site_id": site_id, "gene_symbol": gene_symbol, "uniprot_acc": uniprot_acc,
        "provenance": "screen_validated", "det_path": None, "site_kind": "terminal_n",
        "insert_after_residue": insert_after_residue,
        "residue_before": residue_before, "residue_after": residue_after,
        "residue_label": residue_label(residue_before, insert_after_residue),
        "residue_range": None, "topology_state": "S",
        "extracellular": True, "compartment": "extracellular",
        "tag_type": "HA", "tag_length_aa": 9, "linker": None,
        "evidence_type": "N-terminal HA epitope; parallel surface-display screen",
        "functional_impact_measured": _pme_text(pme, pme_sd),
        "confidence": "high",
        "rationale": (
            "Experimentally validated N-terminal HA epitope insertion (after "
            "signal-peptide cleavage where present); surface expression read out by "
            "HA immunostaining in Tedman et al. deep receptor scanning."
        ),
        "sources": sources or [],
        "plddt": None, "conservation_rank": None, "median_conservation": None,
    }
```

- [ ] **Step 4: Run — expect PASS.**  **Step 5: Commit**
```bash
git add src/accessible_surfaceome/tag_sites/control.py tests/test_tedman_tag_sites.py
git commit -m "feat(tag-sites): screen_validated control_tag_site constructor"
```

---

### Task 5: TS types — add `screen_validated` (TDD)

**Files:**
- Modify: `viewer/lib/tag-sites-types.ts`
- Test: `viewer/tests/tag_sites_screen_validated.test.ts`

- [ ] **Step 1: Write the failing vitest**

`viewer/tests/tag_sites_screen_validated.test.ts`:
```ts
import { describe, it, expect } from "vitest";
import { tagSiteCategory, CATEGORY_LABEL, CATEGORY_HEX } from "../lib/tag-sites-types";

describe("screen_validated", () => {
  it("maps to its own category", () => {
    const cat = tagSiteCategory({ provenance: "screen_validated", det_path: null, site_kind: "terminal_n" });
    expect(cat).toBe("screen_validated");
    expect(CATEGORY_LABEL[cat]).toBe("Screen-validated");
    expect(CATEGORY_HEX[cat]).toMatch(/^#/);
  });
});
```

- [ ] **Step 2: Run — expect FAIL**

Run: `cd $WT/viewer && npx vitest run tests/tag_sites_screen_validated.test.ts`
Expected: FAIL (type error / `screen_validated` not a category).

- [ ] **Step 3: Edit `viewer/lib/tag-sites-types.ts`**

(a) Add to the provenance union (line 9-12):
```ts
export type TaggedSiteProvenance =
  | "literature_retrieved"
  | "deterministic_computed"
  | "screen_validated"
  | "validated_literature"; // validation-only; never rendered
```
(b) Add to `TagSiteCategory` (line 114-120): add `| "screen_validated"`.
(c) In `tagSiteCategory` (line 123-138), before the `deterministic_computed` check:
```ts
  if (site.provenance === "screen_validated") return "screen_validated";
  if (site.provenance !== "deterministic_computed") return "literature";
```
(d) Add entries to `CATEGORY_HEX`, `CATEGORY_TOKEN`, `CATEGORY_LABEL`:
```ts
  // CATEGORY_HEX
  screen_validated: "#c2571f", // --tag-site-screen-validated (deep amber-orange)
  // CATEGORY_TOKEN
  screen_validated: "--tag-site-screen-validated",
  // CATEGORY_LABEL
  screen_validated: "Screen-validated",
```
(e) Widen `IsoformTagPin.classification` (line 175): `classification: "shared" | "unique" | "control";` and add an optional note:
```ts
  /** Optional free-text (e.g. isoform surface-expression PME) for the pin tooltip. */
  note?: string | null;
```

- [ ] **Step 4: Run — expect PASS.**  **Step 5: Commit**
```bash
git add viewer/lib/tag-sites-types.ts viewer/tests/tag_sites_screen_validated.test.ts
git commit -m "feat(viewer): screen_validated tag-site provenance + category"
```

---

### Task 6: Overlay renders `screen_validated` (TDD)

**Files:**
- Modify: `viewer/lib/tag-sites-overlay.ts`
- Test: `viewer/tests/tag_sites_overlay.test.ts` (append or new case)

- [ ] **Step 1: Failing test** — a `screen_validated` terminal_n site (extracellular) at residue 1 renders:
```ts
it("renders a screen_validated N-terminal site", () => {
  const site: any = {
    site_id: "X-nterm", gene_symbol: "X", uniprot_acc: "P1", provenance: "screen_validated",
    det_path: null, site_kind: "terminal_n", insert_after_residue: null, residue_before: null,
    residue_after: "M", topology_state: "S", extracellular: true, compartment: "extracellular",
    tag_type: "HA", tag_length_aa: 9, linker: null, evidence_type: null,
    functional_impact_measured: null, confidence: "high", rationale: null, sources: [],
    plddt: null, conservation_rank: null, median_conservation: null,
  };
  const out = renderableTagSites([site], 300);
  expect(out).toHaveLength(1);
  expect(out[0].category).toBe("screen_validated");
});
```

- [ ] **Step 2: Run — expect FAIL** (`cd $WT/viewer && npx vitest run tests/tag_sites_overlay.test.ts`).

- [ ] **Step 3: Edit `viewer/lib/tag-sites-overlay.ts`**

(a) Extend `RenderedProvenance` (line 11):
```ts
export type RenderedProvenance = "literature_retrieved" | "deterministic_computed" | "screen_validated";
```
(b) Add to `RENDERED` (line 27): `["literature_retrieved", "deterministic_computed", "screen_validated"]`.
(The intracellular-literature drop at line 63-68 is keyed on `literature_retrieved`, so `screen_validated` passes through; its sites are terminal_n + extracellular anyway.)

- [ ] **Step 4: Run — expect PASS.**  **Step 5: Commit**
```bash
git add viewer/lib/tag-sites-overlay.ts viewer/tests/tag_sites_overlay.test.ts
git commit -m "feat(viewer): render screen_validated sites in the tag-site overlay"
```

---

### Task 7: TaggedSitesCard — Screen-validated section (TDD)

**Files:**
- Modify: `viewer/components/surfaceome/TaggedSitesCard/TaggedSitesCard.tsx`
- Test: `viewer/tests/tagged_sites_card_screen.test.tsx`

- [ ] **Step 1: Failing test** — render a file with one `screen_validated` site; assert the "Screen-validated (1)" subhead + the PME text appear:
```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { TaggedSitesCard } from "../components/surfaceome/TaggedSitesCard/TaggedSitesCard";

const file: any = { has_data: true, gene_symbol: "ADRB2", uniprot_acc: "P07550", sites: [{
  site_id: "ADRB2-nterm-tedman", gene_symbol: "ADRB2", uniprot_acc: "P07550",
  provenance: "screen_validated", det_path: null, site_kind: "terminal_n",
  insert_after_residue: null, residue_before: null, residue_after: "M", topology_state: "S",
  extracellular: true, compartment: "extracellular", tag_type: "HA", tag_length_aa: 9, linker: null,
  evidence_type: "N-terminal HA epitope; parallel surface-display screen",
  functional_impact_measured: "Surface immunostaining PME 1234 ± 67 (HA immunostaining, Tedman deep receptor scanning)",
  confidence: "high", rationale: null, sources: [{ citation: "Tedman et al. 2026", doi: "10.1038/s41467-026-76564-7" }],
  plddt: null, conservation_rank: null, median_conservation: null,
}] };

describe("TaggedSitesCard screen_validated", () => {
  it("shows a Screen-validated section with the PME", () => {
    render(<TaggedSitesCard taggedSites={file} />);
    expect(screen.getByText(/Screen-validated \(1\)/)).toBeTruthy();
    expect(screen.getByText(/PME 1234/)).toBeTruthy();
  });
});
```

- [ ] **Step 2: Run — expect FAIL** (`cd $WT/viewer && npx vitest run tests/tagged_sites_card_screen.test.tsx`).

- [ ] **Step 3: Edit `TaggedSitesCard.tsx`**

(a) After the `det` const (line 377), add:
```tsx
  const screen = sites.filter(
    (s) => s.provenance === "screen_validated" &&
      (s.extracellular || s.site_kind === "terminal_n"),
  );
```
(b) In the `legendCategories` set (line 378-380), include `screen`:
```tsx
  const legendCategories = Array.from(
    new Set([...lit, ...det, ...screen].map((s) => tagSiteCategory(s))),
  );
```
(c) Update the empty-gate (line 382): `if (!taggedSites?.has_data || lit.length + det.length + screen.length === 0) {`
(d) Add a section before the Literature block (line 409). Reuse `LIT_COLUMNS` (its Evidence column already renders `evidence_type` + `functional_impact_measured`, i.e. the PME text):
```tsx
      {screen.length > 0 ? (
        <>
          <h3 className={styles.subhead}>Screen-validated ({screen.length})</h3>
          <SortableTable sites={screen} columns={LIT_COLUMNS} />
        </>
      ) : null}
```

- [ ] **Step 4: Run — expect PASS.**  **Step 5: Commit**
```bash
git add viewer/components/surfaceome/TaggedSitesCard/TaggedSitesCard.tsx viewer/tests/tagged_sites_card_screen.test.tsx
git commit -m "feat(viewer): Screen-validated section in TaggedSitesCard"
```

---

### Task 8: GeneDetail tab gate includes `screen_validated`

**Files:** Modify `viewer/components/surfaceome/GeneDetail/GeneDetail.tsx`

- [ ] **Step 1: Edit the gate (line 241-246)** to add the provenance:
```tsx
    ...(taggedSites?.has_data &&
    taggedSites.sites.some(
      (s) =>
        s.provenance === "literature_retrieved" ||
        s.provenance === "deterministic_computed" ||
        s.provenance === "screen_validated",
    )
```
- [ ] **Step 2: Verify build typechecks**

Run: `cd $WT/viewer && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 3: Commit**
```bash
git add viewer/components/surfaceome/GeneDetail/GeneDetail.tsx
git commit -m "feat(viewer): show Tag sites tab for screen_validated-only genes"
```

---

### Task 9: Design tokens

**Files:** Modify `viewer/app/design-tokens.css`

- [ ] **Step 1: Add tokens after line 120** (`--tag-site-snorkel`):
```css
  --tag-site-screen-validated: #c2571f;             /* Tedman N-terminal HA control (deep amber-orange) */
  /* Per-isoform pin colors referenced by IsoformsCard/TopologyBar (were undefined). */
  --tag-site-isoform-shared: var(--teal-mid);       /* transfers from canonical */
  --tag-site-isoform-unique: var(--lavender-bright);/* isoform-specific */
  --tag-site-isoform-control: #c2571f;              /* Tedman control pin — matches screen-validated */
```
- [ ] **Step 2: Confirm the hex matches `CATEGORY_HEX.screen_validated`** (`#c2571f`) in `tag-sites-types.ts` — they must agree (WebGL uses the hex, CSS uses the token).
- [ ] **Step 3: Commit**
```bash
git add viewer/app/design-tokens.css
git commit -m "feat(viewer): tag-site tokens for screen-validated + isoform pins"
```

---

# PHASE 3 — Emit canonical sites + publish live

### Task 10: Emitter (canonical path) + smoke (TDD on a fixture)

**Files:**
- Create: `scripts/emit_tedman_tag_sites.py`
- Test: `tests/test_tedman_tag_sites.py` (append — test the pure builder, not the network)

- [ ] **Step 1: Append a failing test for the pure per-gene builder**
```python
from accessible_surfaceome.tag_sites.tedman import build_control_sites_for_gene

def test_build_control_sites_for_gene():
    row = {"gene_symbol": "ADRB2", "uniprot_acc": "P07550", "junction_after_residue": "",
           "expected_residue": "M", "surface_expression_pme": "1234.5",
           "surface_expression_sd": "67.8", "verified": "true"}
    sites = build_control_sites_for_gene([row], sources=[{"citation": "Tedman et al. 2026"}])
    assert len(sites) == 1
    assert sites[0]["provenance"] == "screen_validated"
    assert sites[0]["site_id"] == "ADRB2-nterm-tedman"
    assert sites[0]["insert_after_residue"] is None
```
Add `build_control_sites_for_gene(rows, *, sources)` to `tag_sites/tedman.py` — a pure function that turns verified TSV rows into `control_tag_site(...)` dicts (site_id `f"{symbol}-nterm-tedman"` for the canonical row; skips `verified != "true"`; parses PME floats). Run → FAIL → implement → PASS.

- [ ] **Step 2: Implement `scripts/emit_tedman_tag_sites.py`**

Reads the TSV, groups by `gene_symbol`, fetches each gene's record for the canonical `uniprot_acc`, builds the Tedman source dict once (with DOI→PMID lookup + fallback to `PMC12458215`), and calls `emit_tag_sites_json(symbol, acc, sites, out_dir=viewer/public/tag-sites, isoform_pins=None)`:
```python
"""Emit/merge Tedman screen_validated control sites into viewer/public/tag-sites/{SYMBOL}.json.

    uv run python scripts/emit_tedman_tag_sites.py --gene ADRB2   # one gene
    uv run python scripts/emit_tedman_tag_sites.py                # all in the TSV
Canonical sites only here; per-isoform pins are added in a later task.
"""
from __future__ import annotations
import argparse, csv, itertools, logging
from accessible_surfaceome.paths import REPO_ROOT
from accessible_surfaceome.tag_sites.emit import emit_tag_sites_json
from accessible_surfaceome.tag_sites.tedman import build_control_sites_for_gene

TSV = REPO_ROOT / "data" / "tag_sites" / "tedman_gpcr_controls.tsv"
OUT = REPO_ROOT / "viewer" / "public" / "tag-sites"
SOURCES = [{
    "citation": "Tedman et al., Efficient experimental characterization of the GPCRome via deep receptor scanning, Nat Commun 2026",
    "doi": "10.1038/s41467-026-76564-7", "pmid": None,           # filled by DOI->PMID lookup if available
    "url": "https://doi.org/10.1038/s41467-026-76564-7",
    "claim": "N-terminal HA epitope inserted per receptor; surface expression read out by HA immunostaining in a pooled GPCRome screen.",
}]

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--gene"); ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    rows = [r for r in csv.DictReader(TSV.open(), delimiter="\t") if r["verified"] == "true"]
    rows = [r for r in rows if r["is_canonical"] == "true"]      # canonical construct per gene
    if args.gene:
        rows = [r for r in rows if r["gene_symbol"] == args.gene]
    rows.sort(key=lambda r: r["gene_symbol"])
    n = 0
    for symbol, grp in itertools.groupby(rows, key=lambda r: r["gene_symbol"]):
        grp = list(grp)
        acc = grp[0]["uniprot_acc"]
        if not acc:
            logging.warning("skip %s: no uniprot_acc", symbol); continue
        sites = build_control_sites_for_gene(grp, sources=SOURCES)
        emit_tag_sites_json(symbol, acc, sites, out_dir=OUT)
        n += 1
        if args.limit and n >= args.limit:
            break
    logging.info("emitted %d genes -> %s", n, OUT)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
```
NOTE: `build_control_sites_for_gene` already knows `uniprot_acc` from the row, so no record fetch is needed for the **canonical** path (the junction was verified against the canonical sequence in Task 3). The record fetch is only needed for isoform matching (Task 13).

- [ ] **Step 3: Smoke-run one gene that already has a JSON (merge coexists)**

Run: `cd $WT && uv run python scripts/emit_tedman_tag_sites.py --gene ADRB2`
Then confirm the file gained a `screen_validated` site without dropping any existing site:
```bash
uv run python - <<'PY'
import json; d=json.load(open("viewer/public/tag-sites/ADRB2.json"))
provs=[s["provenance"] for s in d["sites"]]
print("provenances:", provs); assert "screen_validated" in provs
PY
```
(ADRB2 may be a new file — that's fine; assert the screen_validated site is present.)

- [ ] **Step 4: Run the Python suite** (`cd $WT && uv run pytest tests/test_tedman_tag_sites.py -q`) → PASS.

- [ ] **Step 5: Commit the emitter (not the 766 JSON yet)**
```bash
git add scripts/emit_tedman_tag_sites.py src/accessible_surfaceome/tag_sites/tedman.py tests/test_tedman_tag_sites.py
git commit -m "feat(tag-sites): emit canonical screen_validated sites to viewer JSON"
```

---

### Task 11: Generate all canonical genes + commit the JSON

- [ ] **Step 1: Generate every gene**

Run: `cd $WT && uv run python scripts/emit_tedman_tag_sites.py`
Expected: `emitted ~766 genes`.

- [ ] **Step 2: Sanity-check counts + a signal-peptide gene**
```bash
cd $WT && uv run python - <<'PY'
import json, glob
files = glob.glob("viewer/public/tag-sites/*.json")
sv = [f for f in files if any(s["provenance"]=="screen_validated" for s in json.load(open(f)).get("sites",[]))]
print("files with a screen_validated site:", len(sv))
g = json.load(open("viewer/public/tag-sites/GIPR.json"))   # SP receptor
print("GIPR:", [(s["provenance"], s["insert_after_residue"], s["residue_label"]) for s in g["sites"] if s["provenance"]=="screen_validated"])
PY
```
Expected: ~766 files; GIPR's screen_validated site has a non-null `insert_after_residue` near its SP length.

- [ ] **Step 3: Rebuild the catalog tag-site counts (keeps the filter facet honest)**

Run: `cd $WT/viewer && node scripts/build-tag-site-counts.mjs`
(Read the script first; if it buckets by category it may need a `screen_validated`/`nterm_ec` line — add it if the counts don't include the new sites. This is a filter-count nicety, not a render gate.)

- [ ] **Step 4: Commit the generated JSON**
```bash
cd $WT && git add viewer/public/tag-sites/*.json viewer/public/data/tag-site-counts.json
git commit -m "data(tag-sites): Tedman GPCR canonical HA control sites (~766 genes)"
```

---

### Task 12: Publish canonical sites live to public D1 + purge edge cache

- [ ] **Step 1: Dry-run the sync**

Run: `cd $WT && uv run python scripts/sync_tag_sites_to_d1.py --dry-run --version 2026-09-01`
Expected: lists every gene + a nonzero total site count; "nothing written".

- [ ] **Step 2: Confirm live publish is intended**

This writes production public D1 + serves live. The user authorized "straight to live." Proceed:

Run: `cd $WT && uv run python scripts/sync_tag_sites_to_d1.py --version 2026-09-01`
Expected: `done: ~766 gene(s), N site row(s) -> tag_site_public`.

- [ ] **Step 3: Verify the Worker serves a gene**

Run: `curl -s https://api.deliverome.org/surfaceome/v1/tag-sites/ADRB2 | python3 -m json.tool | head -40`
Expected: a `screen_validated` site in `sites`. (If stale, it's the edge cache — purge next.)

- [ ] **Step 4: Purge the edge cache for the affected URLs**

Reuse the repo's purge helper (the same one `publish_record` uses — grep `purge` in `src/accessible_surfaceome/cloud/`). Purge `/v1/tag-sites/{SYMBOL}` for the published genes (by-URL, never `purge_everything` — shared zone). If no per-endpoint purge helper exists for tag-sites, add a small loop calling the existing zone purge-by-URL client. Re-run the Step 3 curl → the `screen_validated` site appears immediately.

- [ ] **Step 5: No commit** (D1 is external state). Note the version stamp `2026-09-01` in the PR description.

---

# PHASE 4 — Per-isoform control pins

### Task 13: Isoform matcher (ENST → UniProt isoform via record sequences) (TDD)

**Files:**
- Modify: `src/accessible_surfaceome/tag_sites/tedman.py`
- Test: `tests/test_tedman_tag_sites.py` (append)

- [ ] **Step 1: Failing test** — given a set of `(isoform_id, sequence)` from a record and a query protein sequence, return the matching isoform_id (exact length + ≥99% identity), else None:
```python
from accessible_surfaceome.tag_sites.tedman import match_isoform

def test_match_isoform_exact():
    isos = [("P1-1", "MKTLLA"), ("P1-2", "MKTLLAAA")]
    assert match_isoform("MKTLLAAA", isos) == "P1-2"

def test_match_isoform_none_when_no_close_match():
    isos = [("P1-1", "MKTLLA")]
    assert match_isoform("WWWWWW", isos) is None
```

- [ ] **Step 2: Run — expect FAIL.**

- [ ] **Step 3: Implement `match_isoform`** in `tedman.py`, reusing the repo's identity helper:
```python
from accessible_surfaceome.merge.isoform_identity import pct_identity  # confirm the import path

def match_isoform(query_seq: str, isoforms: list[tuple[str, str]], *, min_identity: float = 99.0) -> str | None:
    """Return the isoform_id whose sequence best matches query_seq (exact length
    preferred; identity >= min_identity), else None. `isoforms` = [(isoform_id, seq)]."""
    best, best_id = 0.0, None
    for iso_id, seq in isoforms:
        if not seq:
            continue
        ident = 100.0 if seq == query_seq else pct_identity(query_seq, seq)
        if len(seq) == len(query_seq):
            ident = max(ident, 100.0 if seq == query_seq else ident)
        if ident > best:
            best, best_id = ident, iso_id
    return best_id if best >= min_identity else None
```
NOTE: verify `merge/isoform_identity.pct_identity`'s exact name/signature before running (Task recon flagged it exists); if it takes/returns a fraction, scale accordingly.

- [ ] **Step 4: Run — expect PASS.**  **Step 5: Commit**
```bash
git add src/accessible_surfaceome/tag_sites/tedman.py tests/test_tedman_tag_sites.py
git commit -m "feat(tag-sites): sequence-identity isoform matcher for Tedman transcripts"
```

---

### Task 14: `control_isoform_pin()` + viewer pin plumbing

**Files:**
- Modify: `src/accessible_surfaceome/tag_sites/control.py`
- Modify: `viewer/components/surfaceome/IsoformsCard/IsoformsCard.tsx`, `.../TopologyBar.tsx`

- [ ] **Step 1: Add `control_isoform_pin` to `control.py`** (matches the `IsoformTagPin`/`isoform_pins[]` shape):
```python
def control_isoform_pin(
    *, canonical_site_id: str, isoform_id: str, isoform_residue: int, isoform_len: int,
    canonical_residue: int | None, note: str | None = None,
) -> dict[str, Any]:
    return {
        "site_id": f"{canonical_site_id}::iso::{isoform_id}",
        "isoform_id": isoform_id, "classification": "control", "det_path": None,
        "site_kind": "terminal_n", "tag_type": "HA",
        "isoform_residue": isoform_residue, "canonical_residue": canonical_residue,
        "left_pct": (isoform_residue / isoform_len) * 100 if isoform_len else 0.0,
        "note": note,
    }
```

- [ ] **Step 2: Thread pin classification/note through `IsoformsCard.pinsFor` (line 459-468)**:
```tsx
  const pinsFor = (isoformId: string): TopologyPin[] =>
    (taggedSites?.isoform_pins ?? [])
      .filter((pin) => pin.isoform_id === isoformId)
      .map((pin) => ({
        siteId: pin.site_id,
        leftPct: pin.left_pct,
        provenance: "deterministic_computed" as const,
        tagType: pin.tag_type ?? "tag",
        classification: pin.classification,   // now "shared" | "unique" | "control"
        note: pin.note ?? null,
      }));
```
Widen the `TopologyPin` type (find its definition — likely in `TopologyBar.tsx`): `classification?: "shared" | "unique" | "control";` and add `note?: string | null;`.

- [ ] **Step 3: `TopologyBar.tsx` pin title uses the note (line 156-160)**:
```tsx
          title={
            pin.classification
              ? `${pin.tagType} (${pin.classification})${pin.note ? " — " + pin.note : ""}`
              : `${pin.tagType} (${pin.provenance === "literature_retrieved" ? "literature" : "deterministic"})`
          }
```
The existing `background: var(--tag-site-isoform-${pin.classification})` now resolves `--tag-site-isoform-control` (added in Task 9).

- [ ] **Step 4: Typecheck + commit**

Run: `cd $WT/viewer && npx tsc --noEmit` → no errors.
```bash
cd $WT && git add src/accessible_surfaceome/tag_sites/control.py viewer/components/surfaceome/IsoformsCard/IsoformsCard.tsx viewer/components/surfaceome/IsoformsCard/TopologyBar.tsx
git commit -m "feat(viewer): render control-class isoform tag pins"
```

---

### Task 15: Emit isoform pins + regenerate + commit

**Files:** Modify `scripts/emit_tedman_tag_sites.py`

- [ ] **Step 1: Extend the emitter** — for genes with alt-isoform Tedman rows, fetch the record (`GET {API_BASE}/v1/genes/{symbol}`), read `deterministic_features.isoform_topologies[].{isoform_id, sequence}` and the canonical sequence; for each alt-isoform row, fetch the ENST protein sequence (Ensembl REST `/sequence/id/{ENST}?type=protein;content-type=text/plain`, via `CachedHTTP`), `match_isoform(...)` it to a viewer isoform, compute `isoform_residue` (map the junction onto the isoform's own axis via `map_junction_to_canonical(junction, isoform_seq)`), build a `control_isoform_pin(...)` with a `note` = the isoform's `Surface Expression` + `% change in PME` (from media-2's Isoforms sheet), and pass `isoform_pins=[...]` to `emit_tag_sites_json`. Skip (log) any ENST that doesn't match a viewer isoform.

- [ ] **Step 2: Run for a gene known to have isoforms**

Pick a gene present in both the Tedman Isoforms sheet and with `isoform_topologies` (find one:
`uv run python - <<'PY'` reading the TSV for `is_canonical==false` genes, then curl the record and check `isoform_topologies`). Run:
`cd $WT && uv run python scripts/emit_tedman_tag_sites.py --gene <SYMBOL>` and confirm the JSON now has an `isoform_pins` entry with `classification:"control"` and a matching `isoform_id`.

- [ ] **Step 3: Full regenerate + commit**

Run: `cd $WT && uv run python scripts/emit_tedman_tag_sites.py`
Report the resolved/unresolved isoform counts (logged). Then:
```bash
cd $WT && git add viewer/public/tag-sites/*.json scripts/emit_tedman_tag_sites.py
git commit -m "data(tag-sites): per-isoform Tedman control pins for in-viewer isoforms"
```
(Isoform pins are static-only — they go live on the Pages deploy of this branch, not via D1.)

---

# PHASE 5 — Gates + ship

### Task 16: Full quality gates

- [ ] **Step 1: Python** — `cd $WT && bash scripts/check-py.sh` → ruff + ty + pytest all green.
- [ ] **Step 2: Viewer unit tests** — `cd $WT/viewer && bash tests/run_tag_sites_tests.sh` (or `npx vitest run`) → green, incl. the three new tests.
- [ ] **Step 3: Viewer typecheck + lint** — `cd $WT/viewer && npx tsc --noEmit && npm run lint` → clean.
- [ ] **Step 4: Local visual check** — `cd $WT/viewer && npm run dev`, open a GPCR (e.g. `/ADRB2`, `/GIPR`, and one with isoforms). Confirm: the **Tag sites** tab shows a **Screen-validated** section with the PME; the structure viewer + topology bar show the N-terminal control marker; the Isoforms tab shows the control pin on the matched isoform. Fix any rendering gaps.

### Task 17: Push the branch

- [ ] **Step 1: Push**
```bash
cd $WT && git push -u origin claude/gpcr-control-tag-sites-tedman
```
- [ ] **Step 2: Open a PR to `dev`** titled `feat(tag-sites): Tedman GPCR HA control tag sites`, noting: canonical sites already live in public D1 (version `2026-09-01`, edge-purged); isoform pins ship on the Pages deploy; source = Mendeley `10.17632/3b4n36z4bg` + `deliverome-external` surface screen.

---

## Self-review

**Spec coverage:** sources + join (Task 1,3) ✓; HGNC-ID resolution + junction-in-canonical + verify (Task 2,3) ✓; `screen_validated` new category wired model→TS→card→gate→overlay→tokens (Task 4-9) ✓; surface expression as free-text evidence (Task 4, `_pme_text`) ✓; canonical emit + generate + **live D1 + purge** (Task 10-12) ✓; per-isoform control pins for in-viewer isoforms, ENST→UniProt-isoform by sequence (Task 13-15) ✓; separate `tedman_gpcr_controls.tsv`, not appended to `positive_controls.tsv` (Task 3) ✓; gates + push (Task 16-17) ✓.

**Placeholder scan:** two explicit "verify before running" notes remain by necessity — `IdentifierBundle.sequence` attribute (Task 3 Step 2) and `merge/isoform_identity.pct_identity` signature (Task 13 Step 3); both name the file to check and the one line to adjust. `build-tag-site-counts.mjs` bucket (Task 11 Step 3) is a read-then-maybe-edit. No TODO/TBD code.

**Type consistency:** `screen_validated` used identically in Python (`control.py`), `TaggedSiteProvenance`, `RenderedProvenance`, `RENDERED`, `tagSiteCategory`, `CATEGORY_*`; `--tag-site-screen-validated` = `#c2571f` in both `CATEGORY_HEX` and `design-tokens.css`; `classification:"control"` used in `control_isoform_pin`, `IsoformTagPin`, `TopologyPin`, `pinsFor`, and `--tag-site-isoform-control`; site_id scheme `"{symbol}-nterm-tedman"` (canonical) / `"…::iso::{isoform_id}"` (pins) consistent across emitter + tests.
