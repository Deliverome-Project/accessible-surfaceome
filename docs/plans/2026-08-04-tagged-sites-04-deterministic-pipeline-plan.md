# Tagged Sites — Plan 4: Deterministic pipeline (2a port + 2b surface-loop compute)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce `deterministic_computed` tag sites and write them into `viewer/public/tag-sites/{SYMBOL}.json`, from two candidate-generation paths: **2a** = port the incumbent low-pLDDT + KIBBY sites; **2b** = a NEW surface-loop compute that catches insertion-tolerant loops in *ordered* (high-pLDDT) domains — the class the low-pLDDT screen structurally misses (e.g. EndoNB TFRC I290/V291).

**Architecture:** Pure Python transforms under `scripts/build/tag_sites/`, each with one responsibility, unit-tested with pytest (repo convention). 2a is a CSV→`TaggedSite` adapter. 2b computes per-residue structural signals on the AlphaFold model (RSA via `freesasa`, secondary structure via DSSP, indel-tolerance from the conservation MSA, 3D distance-from-features via biopython) and applies the composite gate from spec §7.2. An emit step merges both paths and writes the viewer JSON. Validated against the 23 curated controls.

**Tech Stack:** Python 3, pytest, pandas, biopython, freesasa, a DSSP provider (`pydssp` or `mkdssp`). Reuse the project's existing tooling where it already exists: `tools/afdb_plddt.py` (per-residue AlphaFold pLDDT + cached PDB) and `tools/gene_lookup.py` (gene→UniProt acc + canonical sequence) — Path 2b needs **no new AlphaFold plumbing and no MCP**. The `TaggedSite` field set matches `viewer/lib/tag-sites-types.ts` exactly.

**Unblocked now:** Path 2b (surface-loop compute) and the pure gate/model helpers need only Python + the AF model (via `tools/afdb_plddt.py`) — **no LFS file, no LLM, no MCP**. Only Path 2a (Task 2, the CSV port) is gated on the 77 MB LFS file (Task 0).

**Parent spec:** `docs/plans/2026-08-04-tagged-sites-viewer-design.md` §7.2 · **Depends on:** Plan 1 (schema shape). Independent of Plans 2–3.

**⚠ Prerequisites (resolve in Task 0 before 2a):**
- The port CSV `deliverome-internal/cloudflare/surfaceome_structure_site_viewer/deploy_static/insertion_sequence_library.csv` is a **77 MB git-LFS file** and did not materialize via `git lfs pull` in the analysis environment. Task 0 confirms a materialized copy (LFS fetch w/ credentials, or regeneration) before 2a can run on real data. 2a's adapter is developed/tested against a small committed CSV fixture regardless.
- Python deps `freesasa`, `biopython`, and a DSSP provider must be added to `pyproject.toml` (Task 0).

---

### Task 0: Prerequisites

- [ ] **Step 1: Confirm port-CSV availability.** Run `git lfs pull --include="cloudflare/surfaceome_structure_site_viewer/deploy_static/insertion_sequence_library.csv"` in the deliverome-internal checkout and verify `head -1` shows CSV headers, not a `version https://git-lfs...` pointer. If LFS is unavailable, note it and proceed with fixtures only (2a real-data run is blocked until the file is materialized) — do **not** fabricate rows.
- [ ] **Step 2: Add deps.** Add `freesasa`, `biopython`, `pydssp` (pure-python DSSP; avoids the `mkdssp` binary) to `pyproject.toml` `[project.dependencies]`; `uv sync` (or `pip install -e .`). Verify: `uv run python -c "import freesasa, Bio, pydssp; print('ok')"`.
- [ ] **Step 3: Commit** — `chore(deps): add freesasa/biopython/pydssp for deterministic tag-site compute`

---

### Task 1: Shared `TaggedSite` builder (Python)

**Files:**
- Create: `scripts/build/tag_sites/__init__.py`
- Create: `scripts/build/tag_sites/model.py`
- Test: `tests/test_tag_sites_model.py`

A single constructor guarantees every emitted record matches the TS `TaggedSite` shape (field names, `det_path`, deterministic-only fields).

- [ ] **Step 1: Failing test**

```python
# tests/test_tag_sites_model.py
from scripts.build.tag_sites.model import tagged_site, TAGGED_SITE_KEYS

def test_tagged_site_has_exact_keys():
    s = tagged_site(
        site_id="TFRC-internal-290-det", gene_symbol="TFRC", uniprot_acc="P02786",
        det_path="surface_loop", site_kind="internal", insert_after_residue=290,
        residue_before="I", residue_after="V", topology_state="O", extracellular=True,
        compartment="extracellular", tag_type="ALFA", tag_length_aa=15,
        plddt=96.0, conservation_rank=7, median_conservation=0.28,
        rationale="ordered surface loop", sources=[{"citation": "det surface_loop"}],
    )
    assert set(s.keys()) == TAGGED_SITE_KEYS
    assert s["provenance"] == "deterministic_computed"
    assert s["confidence"] in ("high", "medium", "low")

def test_literature_only_fields_default_null_for_det():
    s = tagged_site(site_id="x", gene_symbol="TFRC", uniprot_acc="P02786",
                    det_path="disorder", site_kind="internal", insert_after_residue=100,
                    residue_before="A", residue_after="B", topology_state="O",
                    extracellular=True, compartment="extracellular", tag_type="ALFA")
    assert s["evidence_type"] == "structural inference (disorder path)"
    assert s["plddt"] is None  # not provided
```

- [ ] **Step 2: Run → FAIL** (`pytest tests/test_tag_sites_model.py -q`).

- [ ] **Step 3: Implement**

```python
# scripts/build/tag_sites/model.py
"""Constructor for deterministic TaggedSite records matching viewer/lib/tag-sites-types.ts."""
from __future__ import annotations
from typing import Any, Literal, Optional

TAGGED_SITE_KEYS = {
    "site_id", "gene_symbol", "uniprot_acc", "provenance", "det_path", "site_kind",
    "insert_after_residue", "residue_before", "residue_after", "topology_state",
    "extracellular", "compartment", "tag_type", "tag_length_aa", "linker",
    "evidence_type", "functional_impact_measured", "confidence", "rationale",
    "sources", "plddt", "conservation_rank", "median_conservation",
}

_EVIDENCE = {
    "disorder": "structural inference (disorder path)",
    "surface_loop": "structural inference (surface_loop path)",
}

def tagged_site(
    *, site_id: str, gene_symbol: str, uniprot_acc: str,
    det_path: Literal["disorder", "surface_loop"],
    site_kind: Literal["terminal_n", "terminal_c", "internal"],
    insert_after_residue: Optional[int], residue_before: Optional[str],
    residue_after: Optional[str], topology_state: Optional[str],
    extracellular: bool, compartment: str, tag_type: str = "ALFA",
    tag_length_aa: Optional[int] = 15, linker: Optional[str] = "GS both sides",
    confidence: Literal["high", "medium", "low"] = "medium",
    functional_impact_measured: str = "NOT MEASURED",
    rationale: Optional[str] = None, sources: Optional[list[dict[str, Any]]] = None,
    plddt: Optional[float] = None, conservation_rank: Optional[int] = None,
    median_conservation: Optional[float] = None,
) -> dict[str, Any]:
    return {
        "site_id": site_id, "gene_symbol": gene_symbol, "uniprot_acc": uniprot_acc,
        "provenance": "deterministic_computed", "det_path": det_path, "site_kind": site_kind,
        "insert_after_residue": insert_after_residue, "residue_before": residue_before,
        "residue_after": residue_after, "topology_state": topology_state,
        "extracellular": extracellular, "compartment": compartment, "tag_type": tag_type,
        "tag_length_aa": tag_length_aa, "linker": linker,
        "evidence_type": _EVIDENCE[det_path],
        "functional_impact_measured": functional_impact_measured,
        "confidence": confidence, "rationale": rationale, "sources": sources or [],
        "plddt": plddt, "conservation_rank": conservation_rank,
        "median_conservation": median_conservation,
    }
```

- [ ] **Step 4: Run → PASS.** — [ ] **Step 5: Commit** — `feat(tag-sites): Python TaggedSite constructor matching viewer schema`

---

### Task 2: Path 2a — CSV port adapter

**Files:**
- Create: `scripts/build/tag_sites/port_deterministic.py`
- Create: `tests/fixtures/insertion_sequence_library_sample.csv` (small, hand-authored, mirroring the real columns)
- Test: `tests/test_tag_sites_port.py`

- [ ] **Step 1: Inspect real columns** (once Task 0 materialized the CSV): `head -1 <csv>` — expect columns incl. accession/gene, insertion span start/end, `median_conservation`, `conservation_rank`, `plddt`/`average_plddt`, topology. Record the exact names in a comment. Build the fixture CSV with those headers + 2 rows (one internal disorder site for a known gene).

- [ ] **Step 2: Failing test**

```python
# tests/test_tag_sites_port.py
from pathlib import Path
from scripts.build.tag_sites.port_deterministic import port_csv_to_sites

def test_port_maps_disorder_rows(tmp_path):
    csv = Path("tests/fixtures/insertion_sequence_library_sample.csv")
    sites = port_csv_to_sites(csv, sequence_by_acc={"P02786": "M" + "A" * 759})
    assert all(s["provenance"] == "deterministic_computed" for s in sites)
    assert all(s["det_path"] == "disorder" for s in sites)
    # residues verified against sequence: any row whose residue_before mismatches is dropped
    assert all(s["insert_after_residue"] is not None for s in sites)
```

- [ ] **Step 3: Implement** `port_csv_to_sites(csv_path, sequence_by_acc)` — read with pandas; for each internal-site row map span→`insert_after_residue` (choose the span midpoint or start per the real column semantics recorded in Step 1), set `residue_before/after` from the provided sequence, verify against sequence (drop mismatches, log count), attach `plddt`/`conservation_rank`/`median_conservation`, and build via `tagged_site(det_path="disorder", ...)`. Return the list.

- [ ] **Step 4: Run → PASS.** — [ ] **Step 5: Commit** — `feat(tag-sites): port incumbent low-pLDDT/KIBBY sites (path 2a)`

---

### Task 3: Path 2b — structural signals (RSA, DSSP, indel-tolerance)

**Files:**
- Create: `scripts/build/tag_sites/signals.py`
- Test: `tests/test_tag_sites_signals.py`

- [ ] **Step 1: Failing test** (uses the real AF model for P02786 to assert the I290 region is high-pLDDT + surface loop)

```python
# tests/test_tag_sites_signals.py
from pathlib import Path
from scripts.build.tag_sites.signals import per_residue_rsa, per_residue_ss, plddt_from_pdb

AF = Path("tests/fixtures/AF-P02786.pdb")  # committed small AF model (or skip if absent)

def test_tfrc_i290_is_ordered_and_surface():
    if not AF.exists():
        import pytest; pytest.skip("AF model fixture not present")
    plddt = plddt_from_pdb(AF)
    rsa = per_residue_rsa(AF)
    ss = per_residue_ss(AF)
    # I290/V291: high pLDDT (ordered), exposed flanks, loop/turn SS
    assert plddt[290] > 85 and plddt[291] > 85
    assert max(rsa[289], rsa[291]) > 0.30          # exposed flank
    assert ss[290] in ("C", "T", "S", "G")         # loop/turn, not H/E
```

- [ ] **Step 2: Run → FAIL.**

- [ ] **Step 3: Implement** `signals.py`:
  - `plddt_from_pdb(pdb) -> dict[int, float]` — parse CA B-factors (reuse the parse logic from the incumbent `average_plddt_from_pdb_text`).
  - `per_residue_rsa(pdb) -> dict[int, float]` — `freesasa.Structure`/`calc`, normalize by Tien-2013 max-ASA; **compute on the biological assembly** when available (note: monomer is acceptable for the apical-domain I290, but wire an `assembly` arg).
  - `per_residue_ss(pdb) -> dict[int, str]` — `pydssp` SS string, 1-indexed.
  - `column_gap_frequency(msa_path) -> dict[int, float]` — per-column gap fraction from the conservation MSA (indel-tolerance).

- [ ] **Step 4: Run → PASS** (or skip cleanly if fixtures absent). — [ ] **Step 5: Commit** — `feat(tag-sites): per-residue RSA/DSSP/pLDDT/indel signals`

---

### Task 4: Path 2b — composite gate → surface-loop sites

**Files:**
- Create: `scripts/build/tag_sites/surface_loop.py`
- Test: `tests/test_tag_sites_surface_loop.py`

- [ ] **Step 1: Failing test** (the gate must recover TFRC I290; must NOT nominate a buried/helix residue)

```python
# tests/test_tag_sites_surface_loop.py
from scripts.build.tag_sites.surface_loop import surface_loop_candidates

def test_gate_selects_exposed_ordered_loop_not_buried_helix():
    # synthetic per-residue signals: residue 100 = exposed ordered loop; 200 = buried helix
    signals = {
        "topology": {100: "O", 200: "O"},
        "plddt":    {100: 95.0, 200: 95.0},
        "rsa":      {100: 0.55, 200: 0.02},
        "ss":       {100: "C",  200: "H"},
        "gap_freq": {100: 0.30, 200: 0.00},
        "conservation": {100: 0.20, 200: 0.90},
        "feature_dist": {100: 25.0, 200: 25.0},  # Angstrom to nearest functional atom
        "sequence": "A" * 300,
    }
    picks = surface_loop_candidates(signals, gene_symbol="X", uniprot_acc="Q00000")
    picked = {p["insert_after_residue"] for p in picks}
    assert 100 in picked
    assert 200 not in picked
    assert all(p["det_path"] == "surface_loop" for p in picks)
```

- [ ] **Step 2: Run → FAIL.**

- [ ] **Step 3: Implement the composite gate** (spec §7.2 Path 2b):

```python
# scripts/build/tag_sites/surface_loop.py
"""Path 2b: confidently-folded surface-loop candidates the low-pLDDT screen misses."""
from __future__ import annotations
from typing import Any
from .model import tagged_site

PLDDT_MIN = 70.0           # reliability gate (not disorder)
RSA_MIN = 0.30             # solvent-exposed flank
GAP_MIN = 0.05             # some natural indel tolerance
FEATURE_DIST_MIN = 12.0    # Angstrom, 3D clearance from functional atoms
LOOP_SS = {"C", "T", "S", "G"}

def _extracellular(topology_ch: str) -> bool:
    return topology_ch == "O"

def surface_loop_candidates(signals: dict[str, Any], *, gene_symbol: str, uniprot_acc: str) -> list[dict[str, Any]]:
    seq = signals["sequence"]
    picks: list[dict[str, Any]] = []
    for res in sorted(signals["plddt"]):
        topo = signals["topology"].get(res, "?")
        if not _extracellular(topo):
            continue
        if signals["plddt"].get(res, 0.0) < PLDDT_MIN:
            continue                                   # reliability gate
        if signals["ss"].get(res, "?") not in LOOP_SS:
            continue                                   # loop/turn only
        if signals["rsa"].get(res, 0.0) < RSA_MIN:
            continue                                   # surface-exposed
        if signals["gap_freq"].get(res, 0.0) < GAP_MIN:
            continue                                   # indel-tolerant
        if signals["feature_dist"].get(res, 0.0) < FEATURE_DIST_MIN:
            continue                                   # 3D clearance veto
        rb = seq[res - 1] if 1 <= res <= len(seq) else None
        ra = seq[res] if 1 <= res < len(seq) else None
        picks.append(tagged_site(
            site_id=f"{gene_symbol}-internal-{res}-det", gene_symbol=gene_symbol,
            uniprot_acc=uniprot_acc, det_path="surface_loop", site_kind="internal",
            insert_after_residue=res, residue_before=rb, residue_after=ra,
            topology_state=topo, extracellular=True, compartment="extracellular",
            plddt=round(signals["plddt"][res], 1),
            median_conservation=signals["conservation"].get(res),
            rationale="ordered surface loop: pLDDT>=70, DSSP loop/turn, high RSA, indel-tolerant, 3D-clear of features",
        ))
    # rank: low conservation, then high RSA, then high gap frequency
    picks.sort(key=lambda p: (
        p["median_conservation"] if p["median_conservation"] is not None else 1.0,
        -signals["rsa"].get(p["insert_after_residue"], 0.0),
        -signals["gap_freq"].get(p["insert_after_residue"], 0.0),
    ))
    return picks
```

- [ ] **Step 4: Run → PASS.** — [ ] **Step 5: Commit** — `feat(tag-sites): surface-loop composite gate (path 2b) — catches the TFRC I290 class`

---

### Task 5: Emit merged deterministic sites to the viewer JSON

**Files:**
- Create: `scripts/build/tag_sites/emit.py`
- Test: `tests/test_tag_sites_emit.py`

- [ ] **Step 1: Failing test** — `emit_tag_sites_json(gene_symbol, uniprot_acc, sites, out_dir)` writes `{out_dir}/{SYMBOL}.json` with `has_data`, `gene_symbol`, `uniprot_acc`, `sites`, **merging** with an existing file (so a later literature run does not clobber deterministic sites and vice-versa), de-duping by `site_id`.
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement** `emit.py` — read existing `{SYMBOL}.json` if present, merge `sites` by `site_id` (new wins), set `has_data = len(sites) > 0`, write pretty JSON. This is the single writer both the deterministic and (Plan 5) literature pipelines call.
- [ ] **Step 4: Run → PASS.** — [ ] **Step 5: Commit** — `feat(tag-sites): merge-writer for public/tag-sites/{SYMBOL}.json`

---

### Task 6: Orchestrator + validation against the 23 controls

**Files:**
- Create: `scripts/build/tag_sites/run_deterministic.py` (CLI: `--genes TFRC,ITGB1,... --out viewer/public/tag-sites`)
- Create: `tests/fixtures/positive_controls.tsv` (the 23 controls — materialized from deliverome-internal via `git lfs pull`; this is the validation set, spec §8)
- Test: `tests/test_tag_sites_validation.py`

- [ ] **Step 1:** Materialize `positive_controls.tsv` (LFS) into the fixture; if unavailable, skip validation with a clear message (do not fabricate controls).

- [ ] **Step 2: Failing test** — `test_surface_loop_recovers_ordered_controls`: run Path 2b on TFRC/ITGB1/ITGB5 (using committed AF models) and assert the picks include a site within ±3 residues of the control junction (TFRC 290, ITGB1 101, ITGB5 102). Assert Path 2a alone does NOT (it's disorder-only) — demonstrating 2b's value.

- [ ] **Step 3: Implement** `run_deterministic.py`: for each gene, resolve UniProt acc + sequence + topology (from the record/AF model), run 2a (port, if CSV available) + 2b (compute), merge, and `emit_tag_sites_json`. Add a `--validate` mode that scores recall vs `positive_controls.tsv` (site recall, residue-exactness ±k, EC agreement) and prints a report.

- [ ] **Step 4: Run validation** — `uv run python -m scripts.build.tag_sites.run_deterministic --genes TFRC,ITGB1,ITGB5 --validate`. Record recall in the PR.

- [ ] **Step 5: Commit** — `feat(tag-sites): deterministic orchestrator + control-recall validation`

---

## Self-Review

**Spec coverage:** §7.2 Path 2a port → Task 2; Path 2b surface-loop compute (RSA/DSSP/indel/3D-veto/gate) → Tasks 3, 4; pLDDT-as-reliability-gate + conservation ranking → Task 4; merge-writer to `public/tag-sites/{SYMBOL}.json` → Task 5; validation vs 23 controls (§8) → Task 6; the two port-time confirmations (KIBBY rank direction, per-site pLDDT field) → Task 2 Step 1. ✓

**Placeholder scan:** Tasks 1, 4, 5 carry full code. Tasks 2, 3, 6 carry full test code + precise implementation specs (the exact CSV column names and AF-model parsing depend on materialized inputs recorded in-task — not guessable without the LFS file, so specified as an in-task inspection step rather than fabricated). This is the one honest gap and it is gated behind Task 0.

**Type consistency:** `tagged_site(...)` / `TAGGED_SITE_KEYS`, `port_csv_to_sites`, `per_residue_rsa/ss`, `surface_loop_candidates`, `emit_tag_sites_json` are used consistently. Output records match `viewer/lib/tag-sites-types.ts` (asserted by `TAGGED_SITE_KEYS` in Task 1).

**Risks:** (1) LFS port CSV (Task 0) — 2a real-data run blocked until materialized; 2b is independent and unblocked. (2) `freesasa` on multi-chain assemblies — wire the `assembly` arg (Task 3) and default to monomer only where safe. (3) DSSP provider: `pydssp` avoids the `mkdssp` binary; if numerical SS differs, pin thresholds against the TFRC fixture.
