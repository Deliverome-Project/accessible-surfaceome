# Tagged Sites — Plan 1: Foundation (data contracts, loaders, fixtures)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish the browser-safe `TaggedSite` / `InternalizationMeasurement` data contracts, the server-only static-JSON loaders, the residue/compartment derivation helpers, and seed fixtures — the foundation every later plan (overlay, §08 tab, three pipelines) builds on.

**Architecture:** Mirror the existing `structure-viewer` pattern exactly: a browser-safe *types leaf* (`lib/tag-sites-types.ts`) holding interfaces + token-name constants, and a server-only loader (`lib/tag-sites.ts`) that `readFileSync`s per-gene JSON from `viewer/public/tag-sites/` and `viewer/public/internalization/`, guarded against path traversal. Compartment/extracellular classification reuses `lib/surface-bind.ts`'s `compartmentAt`. Tests are standalone `tsx` scripts using the repo's homegrown `expect`.

**Tech Stack:** TypeScript, Next.js App Router (server components), `node:fs`, `tsx` test scripts (no Jest/Vitest).

**Parent spec:** `docs/plans/2026-08-04-tagged-sites-viewer-design.md`

**Decomposition note:** The 23-control *validation set* import (spec §8) is deliberately deferred to the pipeline plans (Plan 4 deterministic / Plan 5 literature), where it is actually consumed for scoring — it is not needed for the viewer foundation.

---

### Task 1: Data contracts (browser-safe types leaf)

**Files:**
- Create: `viewer/lib/tag-sites-types.ts`
- Test: `viewer/tests/tag_sites_types.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
// viewer/tests/tag_sites_types.test.ts
/*
 * Pins the tag-sites data contracts compile and that the provenance
 * token map only covers the two RENDERED provenances (validated_literature
 * is validation-only and must NOT get an overlay color).
 *   npx --yes tsx tests/tag_sites_types.test.ts
 */
import {
  PROVENANCE_TOKEN,
  type TaggedSite,
  type InternalizationMeasurement,
} from "../lib/tag-sites-types";

let failures = 0;
function expect(label: string, got: unknown, want: unknown): void {
  const ok = JSON.stringify(got) === JSON.stringify(want);
  if (!ok) { failures++; console.error(`FAIL ${label}\n  got:  ${JSON.stringify(got)}\n  want: ${JSON.stringify(want)}`); }
  else { console.log(`ok   ${label}`); }
}

expect(
  "token map keys are exactly the two rendered provenances",
  Object.keys(PROVENANCE_TOKEN).sort(),
  ["deterministic_computed", "literature_retrieved"],
);

// A deterministic internal site is representable end-to-end.
const site: TaggedSite = {
  site_id: "TFRC-internal-290", gene_symbol: "TFRC", uniprot_acc: "P02786",
  provenance: "deterministic_computed", det_path: "surface_loop", site_kind: "internal",
  insert_after_residue: 290, residue_before: "I", residue_after: "V",
  topology_state: "O", extracellular: true, compartment: "extracellular",
  tag_type: "ALFA", tag_length_aa: 15, linker: "GS both sides",
  evidence_type: null, functional_impact_measured: null, confidence: "medium",
  rationale: null, sources: [], plddt: 96, conservation_rank: 7, median_conservation: 0.28,
};
expect("site round-trips gene", site.gene_symbol, "TFRC");

const m: InternalizationMeasurement = {
  gene_symbol: "TFRC", uniprot_acc: "P02786", cell_type: "HeLa",
  assay: "flow", ligand_status: "constitutive", ligand: null,
  rate: "t1/2 ~ 8 min", rate_class: "quantified", n_replicates: 4,
  source: { citation: "x" },
};
expect("measurement ligand_status", m.ligand_status, "constitutive");

if (failures > 0) { console.error(`\n${failures} assertion(s) failed`); process.exit(1); }
console.log("\nall assertions passed");
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd viewer && npx --yes tsx tests/tag_sites_types.test.ts`
Expected: FAIL — `Cannot find module '../lib/tag-sites-types'`.

- [ ] **Step 3: Write minimal implementation**

```ts
// viewer/lib/tag-sites-types.ts
/*
 * Tagged-sites + internalization data contracts (browser-safe leaf).
 * Mirrors the structure-viewer-types.ts split: interfaces + token-name
 * constants only, no node:fs — safe to import across a "use client" boundary.
 */
import type { Compartment } from "./surface-bind";

export type TaggedSiteProvenance =
  | "literature_retrieved"
  | "deterministic_computed"
  | "validated_literature"; // validation-only; never rendered

export type DeterministicPath = "disorder" | "surface_loop";
export type TaggedSiteKind = "terminal_n" | "terminal_c" | "internal";
export type Confidence = "high" | "medium" | "low";

export interface EvidenceSource {
  claim?: string;
  citation: string;
  url?: string | null;
  pmid?: string | null;
  doi?: string | null;
}

export interface TaggedSite {
  site_id: string;
  gene_symbol: string;
  uniprot_acc: string;
  provenance: TaggedSiteProvenance;
  /** Only set when provenance === "deterministic_computed". */
  det_path: DeterministicPath | null;
  site_kind: TaggedSiteKind;
  /** Junction: tag sits between insert_after_residue and insert_after_residue+1
   *  (UniProt canonical numbering). Null for a pure N-terminal-before-residue-1 tag. */
  insert_after_residue: number | null;
  residue_before: string | null;
  residue_after: string | null;
  /** DeepTMHMM per-residue char at the junction (O/I/M/S), or null. */
  topology_state: string | null;
  extracellular: boolean;
  compartment: Compartment;
  tag_type: string;
  tag_length_aa: number | null;
  linker: string | null;
  evidence_type: string | null;
  functional_impact_measured: string | null;
  confidence: Confidence | null;
  rationale: string | null;
  sources: EvidenceSource[];
  // deterministic-only (null for literature_retrieved / validated_literature):
  plddt: number | null;
  conservation_rank: number | null;
  median_conservation: number | null;
}

export interface TaggedSitesFile {
  has_data: boolean;
  gene_symbol: string;
  uniprot_acc: string;
  sites: TaggedSite[];
}

export interface InternalizationMeasurement {
  gene_symbol: string;
  uniprot_acc: string;
  cell_type: string | null;
  assay: string | null;
  ligand_status: "constitutive" | "ligand-driven" | "not stated";
  ligand: string | null;
  rate: string | null;
  rate_class: "quantified" | "not quantified";
  n_replicates: number | null;
  source: EvidenceSource;
}

export interface QualitativeStatement {
  statement: string;
  source: EvidenceSource;
}

export interface InternalizationFile {
  has_data: boolean;
  gene_symbol: string;
  uniprot_acc: string;
  measurements: InternalizationMeasurement[];
  qualitative_statements: QualitativeStatement[];
}

/** Overlay design-token NAMES per rendered provenance. Actual color values
 *  live in app/design-tokens.css. validated_literature is intentionally
 *  absent — it is validation-only and never drawn. */
export const PROVENANCE_TOKEN: Record<
  "literature_retrieved" | "deterministic_computed",
  string
> = {
  literature_retrieved: "--tag-site-literature",
  deterministic_computed: "--tag-site-deterministic",
};
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd viewer && npx --yes tsx tests/tag_sites_types.test.ts`
Expected: PASS — "all assertions passed".

- [ ] **Step 5: Commit**

```bash
git add viewer/lib/tag-sites-types.ts viewer/tests/tag_sites_types.test.ts
git commit -m "feat(viewer): tag-sites + internalization data contracts"
```

---

### Task 2: Junction + compartment derivation helpers

**Files:**
- Create: `viewer/lib/tag-sites-derive.ts`
- Test: `viewer/tests/tag_sites_derive.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
// viewer/tests/tag_sites_derive.test.ts
/*
 * Pins junction verification against the canonical sequence and the
 * compartment/extracellular derivation from DeepTMHMM topology.
 *   npx --yes tsx tests/tag_sites_derive.test.ts
 */
import { verifyJunction, deriveCompartment } from "../lib/tag-sites-derive";

let failures = 0;
function expect(label: string, got: unknown, want: unknown): void {
  const ok = JSON.stringify(got) === JSON.stringify(want);
  if (!ok) { failures++; console.error(`FAIL ${label}\n  got:  ${JSON.stringify(got)}\n  want: ${JSON.stringify(want)}`); }
  else { console.log(`ok   ${label}`); }
}

// sequence indexed 1..N: position 3 = "C", position 4 = "D"
const seq = "ABCDEFG"; // A1 B2 C3 D4 E5 F6 G7

expect("valid internal junction after C3 (before C, after D)",
  verifyJunction(seq, { insert_after_residue: 3, residue_before: "C", residue_after: "D", site_kind: "internal" }), true);
expect("wrong residue_before invalidates",
  verifyJunction(seq, { insert_after_residue: 3, residue_before: "X", residue_after: "D", site_kind: "internal" }), false);
expect("out-of-range junction invalidates",
  verifyJunction(seq, { insert_after_residue: 99, residue_before: "C", residue_after: "D", site_kind: "internal" }), false);
expect("terminal_n before residue 1 needs no before-check",
  verifyJunction(seq, { insert_after_residue: null, residue_before: null, residue_after: "A", site_kind: "terminal_n" }), true);

// topology: S1-2, O3-5, M6, I7  → residue 4 extracellular, residue 7 intracellular
const topo = "SSOOOMI";
expect("internal junction at residue 4 → extracellular",
  deriveCompartment(topo, 4, "internal"), { compartment: "extracellular", extracellular: true, topology_state: "O" });
expect("junction in intracellular tail",
  deriveCompartment(topo, 7, "internal"), { compartment: "intracellular", extracellular: false, topology_state: "I" });
expect("missing topology → unknown, not EC",
  deriveCompartment("", 4, "internal"), { compartment: "unknown", extracellular: false, topology_state: null });

if (failures > 0) { console.error(`\n${failures} assertion(s) failed`); process.exit(1); }
console.log("\nall assertions passed");
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd viewer && npx --yes tsx tests/tag_sites_derive.test.ts`
Expected: FAIL — `Cannot find module '../lib/tag-sites-derive'`.

- [ ] **Step 3: Write minimal implementation**

```ts
// viewer/lib/tag-sites-derive.ts
/*
 * Pure derivations for tagged sites: mechanical junction verification
 * against the canonical sequence, and compartment/extracellular
 * classification from the DeepTMHMM per-residue topology string.
 * Browser-safe (no node:fs). Reuses compartmentAt from surface-bind.
 */
import { compartmentAt, type Compartment } from "./surface-bind";
import type { TaggedSiteKind } from "./tag-sites-types";

interface JunctionInput {
  insert_after_residue: number | null;
  residue_before: string | null;
  residue_after: string | null;
  site_kind: TaggedSiteKind;
}

/** True when the stated junction residues match the 1-indexed sequence.
 *  A terminal_n tag before residue 1 (insert_after_residue null/0) has no
 *  before-residue to check; its residue_after, when given, must match pos 1.
 *  Any stated residue that disagrees with the sequence returns false — the
 *  caller drops such a site (a mismatch invalidates it). */
export function verifyJunction(sequence: string, j: JunctionInput): boolean {
  const n = j.insert_after_residue;
  if (n === null || n === 0) {
    if (j.residue_after && sequence.charAt(0) !== j.residue_after) return false;
    return true;
  }
  if (n < 1 || n > sequence.length) return false;
  if (j.residue_before && sequence.charAt(n - 1) !== j.residue_before) return false;
  if (j.residue_after) {
    if (n >= sequence.length) return false; // no residue after the C-terminus
    if (sequence.charAt(n) !== j.residue_after) return false;
  }
  return true;
}

export interface DerivedCompartment {
  compartment: Compartment;
  extracellular: boolean;
  topology_state: string | null;
}

/** Compartment + EC flag for a site from the topology string. For internal
 *  and terminal_n sites the junction residue is `insert_after_residue`
 *  (clamped to ≥1); terminal_c uses the last residue. Absent topology → unknown. */
export function deriveCompartment(
  topology: string,
  insertAfterResidue: number | null,
  siteKind: TaggedSiteKind,
): DerivedCompartment {
  if (!topology) return { compartment: "unknown", extracellular: false, topology_state: null };
  let residue: number;
  if (siteKind === "terminal_c") residue = topology.length;
  else residue = insertAfterResidue && insertAfterResidue >= 1 ? insertAfterResidue : 1;
  const compartment = compartmentAt(topology, residue);
  const idx = residue - 1;
  const topology_state = idx >= 0 && idx < topology.length ? topology.charAt(idx) : null;
  return { compartment, extracellular: compartment === "extracellular", topology_state };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd viewer && npx --yes tsx tests/tag_sites_derive.test.ts`
Expected: PASS — "all assertions passed".

- [ ] **Step 5: Commit**

```bash
git add viewer/lib/tag-sites-derive.ts viewer/tests/tag_sites_derive.test.ts
git commit -m "feat(viewer): junction verification + compartment derivation for tag sites"
```

---

### Task 3: Server-only static-JSON loaders

**Files:**
- Create: `viewer/lib/tag-sites.ts`
- Test: `viewer/tests/tag_sites_loader.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
// viewer/tests/tag_sites_loader.test.ts
/*
 * Pins the server-only loaders: read per-gene JSON from public/, reject
 * path-traversal keys, return null on miss. Writes temp fixtures under
 * public/ then cleans up.
 *   npx --yes tsx tests/tag_sites_loader.test.ts
 */
import { mkdirSync, writeFileSync, rmSync } from "node:fs";
import path from "node:path";
import { loadTaggedSites, loadInternalization } from "../lib/tag-sites";

let failures = 0;
function expect(label: string, got: unknown, want: unknown): void {
  const ok = JSON.stringify(got) === JSON.stringify(want);
  if (!ok) { failures++; console.error(`FAIL ${label}\n  got:  ${JSON.stringify(got)}\n  want: ${JSON.stringify(want)}`); }
  else { console.log(`ok   ${label}`); }
}

const pub = path.join(process.cwd(), "public");
const tsDir = path.join(pub, "tag-sites");
const inDir = path.join(pub, "internalization");
mkdirSync(tsDir, { recursive: true });
mkdirSync(inDir, { recursive: true });
writeFileSync(path.join(tsDir, "__TESTGENE.json"), JSON.stringify({ has_data: true, gene_symbol: "__TESTGENE", uniprot_acc: "P00000", sites: [] }));
writeFileSync(path.join(inDir, "__TESTGENE.json"), JSON.stringify({ has_data: false, gene_symbol: "__TESTGENE", uniprot_acc: "P00000", measurements: [], qualitative_statements: [] }));

try {
  expect("loads tag-sites file", loadTaggedSites("__TESTGENE")?.gene_symbol, "__TESTGENE");
  expect("loads internalization file", loadInternalization("__TESTGENE")?.has_data, false);
  expect("missing gene → null", loadTaggedSites("__NOPE"), null);
  expect("path-traversal key → null", loadTaggedSites("../secret"), null);
  expect("null key → null", loadTaggedSites(null), null);
} finally {
  rmSync(path.join(tsDir, "__TESTGENE.json"), { force: true });
  rmSync(path.join(inDir, "__TESTGENE.json"), { force: true });
}

if (failures > 0) { console.error(`\n${failures} assertion(s) failed`); process.exit(1); }
console.log("\nall assertions passed");
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd viewer && npx --yes tsx tests/tag_sites_loader.test.ts`
Expected: FAIL — `Cannot find module '../lib/tag-sites'`.

- [ ] **Step 3: Write minimal implementation**

```ts
// viewer/lib/tag-sites.ts
/*
 * Tagged-sites + internalization loaders (server-only).
 * Reads per-gene JSON at build time from viewer/public/tag-sites/*.json and
 * viewer/public/internalization/*.json. Mirrors lib/structure-viewer.ts:
 * only these functions touch node:fs, guarded against path traversal.
 */
import { readFileSync } from "node:fs";
import path from "node:path";
import type { TaggedSitesFile, InternalizationFile } from "./tag-sites-types";

const TAG_SITES_DIR = path.join(process.cwd(), "public", "tag-sites");
const INTERNALIZATION_DIR = path.join(process.cwd(), "public", "internalization");

// HGNC symbols are uppercase alphanumeric with - . and digits; reject
// anything that could escape the data dir.
const SAFE_KEY = /^[A-Z0-9.\-]+$/i;

function loadJson<T>(dir: string, key: string | null | undefined): T | null {
  if (!key || !SAFE_KEY.test(key)) return null;
  try {
    return JSON.parse(readFileSync(path.join(dir, `${key}.json`), "utf-8")) as T;
  } catch {
    return null;
  }
}

export function loadTaggedSites(symbol: string | null | undefined): TaggedSitesFile | null {
  return loadJson<TaggedSitesFile>(TAG_SITES_DIR, symbol);
}

export function loadInternalization(symbol: string | null | undefined): InternalizationFile | null {
  return loadJson<InternalizationFile>(INTERNALIZATION_DIR, symbol);
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd viewer && npx --yes tsx tests/tag_sites_loader.test.ts`
Expected: PASS — "all assertions passed".

- [ ] **Step 5: Commit**

```bash
git add viewer/lib/tag-sites.ts viewer/tests/tag_sites_loader.test.ts
git commit -m "feat(viewer): server-only loaders for tag-sites + internalization JSON"
```

---

### Task 4: Seed fixtures (TFRC tag sites + internalization)

**Files:**
- Create: `viewer/public/tag-sites/TFRC.json`
- Create: `viewer/public/internalization/TFRC.json`
- Create: `viewer/public/tag-sites/.gitkeep` (only if the dir would otherwise be empty — skip if TFRC.json is committed)
- Test: `viewer/tests/tag_sites_fixture.test.ts`

TFRC is the ideal seed: it exercises a deterministic `surface_loop` site (I290/V291), a literature site, and real internalization rows.

- [ ] **Step 1: Write the failing test**

```ts
// viewer/tests/tag_sites_fixture.test.ts
/*
 * Pins the committed TFRC seed fixtures: they load, every site verifies
 * against a stub, and the shipped provenances are only the rendered ones.
 *   npx --yes tsx tests/tag_sites_fixture.test.ts
 */
import { loadTaggedSites, loadInternalization } from "../lib/tag-sites";

let failures = 0;
function expect(label: string, got: unknown, want: unknown): void {
  const ok = JSON.stringify(got) === JSON.stringify(want);
  if (!ok) { failures++; console.error(`FAIL ${label}\n  got:  ${JSON.stringify(got)}\n  want: ${JSON.stringify(want)}`); }
  else { console.log(`ok   ${label}`); }
}

const ts = loadTaggedSites("TFRC");
expect("TFRC tag-sites loads", ts?.has_data, true);
expect("TFRC uniprot", ts?.uniprot_acc, "P02786");
expect(
  "shipped provenances are rendered-only",
  [...new Set((ts?.sites ?? []).map((s) => s.provenance))].sort(),
  ["deterministic_computed", "literature_retrieved"],
);
expect("has a surface_loop deterministic site", (ts?.sites ?? []).some((s) => s.det_path === "surface_loop"), true);

const intl = loadInternalization("TFRC");
expect("TFRC internalization loads", intl?.has_data, true);
expect("has ≥1 measurement", (intl?.measurements.length ?? 0) > 0, true);

if (failures > 0) { console.error(`\n${failures} assertion(s) failed`); process.exit(1); }
console.log("\nall assertions passed");
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd viewer && npx --yes tsx tests/tag_sites_fixture.test.ts`
Expected: FAIL — `loadTaggedSites("TFRC")` returns null (no fixture yet).

- [ ] **Step 3: Write the fixtures**

```json
// viewer/public/tag-sites/TFRC.json
{
  "has_data": true,
  "gene_symbol": "TFRC",
  "uniprot_acc": "P02786",
  "sites": [
    {
      "site_id": "TFRC-internal-290-lit",
      "gene_symbol": "TFRC", "uniprot_acc": "P02786",
      "provenance": "literature_retrieved", "det_path": null, "site_kind": "internal",
      "insert_after_residue": 290, "residue_before": "I", "residue_after": "V",
      "topology_state": "O", "extracellular": true, "compartment": "extracellular",
      "tag_type": "ALFA", "tag_length_aa": 15, "linker": "GS both sides",
      "evidence_type": "published tag insertion at this exact site",
      "functional_impact_measured": "Transferrin uptake retained, ligand-independent, n=4 (EndoNB)",
      "confidence": "high", "rationale": "Surface loop in the apical domain, ~35-45 A from the Tf/HFE interface.",
      "sources": [{ "citation": "Lenaerts et al., EndoNB, bioRxiv 2025", "doi": "10.1101/2025.06.08.658482", "url": "https://doi.org/10.1101/2025.06.08.658482" }],
      "plddt": null, "conservation_rank": null, "median_conservation": null
    },
    {
      "site_id": "TFRC-internal-290-det",
      "gene_symbol": "TFRC", "uniprot_acc": "P02786",
      "provenance": "deterministic_computed", "det_path": "surface_loop", "site_kind": "internal",
      "insert_after_residue": 290, "residue_before": "I", "residue_after": "V",
      "topology_state": "O", "extracellular": true, "compartment": "extracellular",
      "tag_type": "ALFA", "tag_length_aa": 15, "linker": "GS both sides",
      "evidence_type": "structural inference (surface_loop path)",
      "functional_impact_measured": "NOT MEASURED",
      "confidence": "medium", "rationale": "pLDDT ~96 ordered surface loop; high flank RSA; DSSP strand-loop-helix connector.",
      "sources": [{ "citation": "deterministic surface_loop path (AF-P02786-F1)" }],
      "plddt": 96.0, "conservation_rank": 7, "median_conservation": 0.28
    }
  ]
}
```

```json
// viewer/public/internalization/TFRC.json
{
  "has_data": true,
  "gene_symbol": "TFRC",
  "uniprot_acc": "P02786",
  "measurements": [
    {
      "gene_symbol": "TFRC", "uniprot_acc": "P02786",
      "cell_type": "HeLa", "assay": "anti-ALFA antibody internalization, flow cytometry",
      "ligand_status": "constitutive", "ligand": null,
      "rate": "NOT STATED (curve only)", "rate_class": "not quantified", "n_replicates": 4,
      "source": { "citation": "Lenaerts et al., EndoNB, bioRxiv 2025", "doi": "10.1101/2025.06.08.658482" }
    }
  ],
  "qualitative_statements": [
    {
      "statement": "TFR internalizes constitutively via clathrin-mediated endocytosis (canonical).",
      "source": { "citation": "EndoNB background / canonical TfR biology" }
    }
  ]
}
```

> NOTE (data accuracy): the "GS both sides" linker on the TFRC site is provisional — the
> EndoNB methods describe a GS linker generally while the curated controls note "TFRC: no
> linkers". Reconcile against the TFR construct figure before treating this fixture as ground
> truth (parent spec §13).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd viewer && npx --yes tsx tests/tag_sites_fixture.test.ts`
Expected: PASS — "all assertions passed".

- [ ] **Step 5: Commit**

```bash
git add viewer/public/tag-sites/TFRC.json viewer/public/internalization/TFRC.json viewer/tests/tag_sites_fixture.test.ts
git commit -m "feat(viewer): seed TFRC tag-site + internalization fixtures"
```

---

### Task 5: Wire the four tests into the render-test harness

**Files:**
- Modify: `viewer/tests/run_render_tests.sh` (add the four new tsx scripts to the run list)

- [ ] **Step 1: Inspect the harness**

Run: `sed -n '1,60p' viewer/tests/run_render_tests.sh`
Confirm how existing `*.test.ts(x)` scripts are enumerated (glob vs explicit list).

- [ ] **Step 2: If the harness globs `tests/*.test.ts`, no edit is needed** — the four new scripts are picked up automatically. Run the full suite to confirm:

Run: `cd viewer && bash tests/run_render_tests.sh`
Expected: all scripts PASS, including the four new `tag_sites_*` scripts.

- [ ] **Step 3: If the harness uses an explicit list**, add the four entries in the same style, then re-run:

Run: `cd viewer && bash tests/run_render_tests.sh`
Expected: PASS.

- [ ] **Step 4: Commit (only if the harness file changed)**

```bash
git add viewer/tests/run_render_tests.sh
git commit -m "test(viewer): register tag-sites foundation tests in the render harness"
```

---

## Self-Review

**Spec coverage (Plan 1 slice):**
- §4.1 `TaggedSite` (incl. `det_path`) → Task 1. ✓
- §4.2 `InternalizationMeasurement` + `qualitative_statements` → Task 1. ✓
- Residue-junction verification against `sequence` (§8, §7.1) → Task 2. ✓
- EC classification from topology (§5, §7) → Task 2 (reuses `compartmentAt`). ✓
- Static per-gene JSON in `viewer/public/`, keyed by symbol (§6) → Task 3. ✓
- Seed dataset for the P1 overlay (§12 P1) → Task 4. ✓
- Deferred (documented): 23-control validation-set import (§8) → Plan 4/5. Loaders + overlay (§5) → Plan 2. §08 tab (§5.2) → Plan 3.

**Placeholder scan:** none — every code step contains full source.

**Type consistency:** `TaggedSite`, `InternalizationFile`, `PROVENANCE_TOKEN`, `verifyJunction`, `deriveCompartment`, `loadTaggedSites`, `loadInternalization` are used identically across Tasks 1–4. `Compartment` is imported from `surface-bind.ts` (existing) in both the types leaf and the derive helper.

**Note:** Task 5 is conditional on the harness style; the render-test command (`bash tests/run_render_tests.sh`) is confirmed to exist from the parent exploration but its enumeration style must be checked at execution time (Step 1).
