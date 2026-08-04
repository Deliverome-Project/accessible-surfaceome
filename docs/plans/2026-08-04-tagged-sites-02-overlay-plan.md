# Tagged Sites — Plan 2: Overlay (topology bar + 3D, colored by method)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render tag-insertion sites as an overlay on the linear topology bar **and** the 3D structure viewer, colored by sourcing method (`literature_retrieved` vs `deterministic_computed`), fed by client-fetching the static `public/tag-sites/{SYMBOL}.json`.

**Architecture:** The gene route is a **client shell** (`app/gene/page.tsx`) that fetches per-gene data from the Worker at runtime. So the overlay data is client-fetched (not read via the server-only `lib/tag-sites.ts`), threaded `app/gene/page.tsx → GeneDetail → GeneHeader → { StructureViewer, TopologyBar }`. All coordinate/color logic goes in **pure, unit-tested helpers**; the component edits are mechanical prop-threading verified by `tsc` + render tests. 3Dmol/WebGL can't consume CSS vars, so a JS provenance→hex map is kept in sync with the `--tag-site-*` tokens.

**Tech Stack:** TypeScript, React 19 client components, 3Dmol.js, CSS Modules, `tsx` unit tests + `renderToStaticMarkup` render tests.

**Parent spec:** `docs/plans/2026-08-04-tagged-sites-viewer-design.md` · **Depends on:** Plan 1 (contracts/loaders/fixtures — merged).

**Prerequisite:** viewer deps installed (`cd viewer && npm install`) — needed for `npm run check` and the render harness.

---

### Task 1: Design tokens + provenance→hex map

**Files:**
- Modify: `viewer/app/design-tokens.css` (add two tokens near the semantic aliases, ~line 110)
- Modify: `viewer/lib/tag-sites-types.ts` (add `PROVENANCE_HEX` beside `PROVENANCE_TOKEN`)
- Test: `viewer/tests/tag_sites_colors.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
// viewer/tests/tag_sites_colors.test.ts
/*
 * Pins the WebGL hex map: same two keys as PROVENANCE_TOKEN, each a #rrggbb
 * string. 3Dmol needs concrete hex (CSS vars don't resolve in WebGL), so the
 * hex map must stay in sync with the --tag-site-* tokens.
 *   npx --yes tsx tests/tag_sites_colors.test.ts
 */
import { PROVENANCE_TOKEN, PROVENANCE_HEX } from "../lib/tag-sites-types";

let failures = 0;
function expect(label: string, got: unknown, want: unknown): void {
  const ok = JSON.stringify(got) === JSON.stringify(want);
  if (!ok) { failures++; console.error(`FAIL ${label}\n  got:  ${JSON.stringify(got)}\n  want: ${JSON.stringify(want)}`); }
  else { console.log(`ok   ${label}`); }
}

expect("hex map keys match token map keys",
  Object.keys(PROVENANCE_HEX).sort(), Object.keys(PROVENANCE_TOKEN).sort());
for (const [k, v] of Object.entries(PROVENANCE_HEX)) {
  expect(`${k} is #rrggbb`, /^#[0-9a-fA-F]{6}$/.test(v), true);
}

if (failures > 0) { console.error(`\n${failures} assertion(s) failed`); process.exit(1); }
console.log("\nall assertions passed");
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd viewer && npx --yes tsx tests/tag_sites_colors.test.ts`
Expected: FAIL — `PROVENANCE_HEX` is not exported.

- [ ] **Step 3: Add the tokens (design-tokens.css) and the hex map (tag-sites-types.ts)**

In `viewer/app/design-tokens.css`, add near the semantic color aliases (e.g. after the `--info:` line ~110):

```css
--tag-site-literature: var(--lavender-bright);   /* literature_retrieved overlay */
--tag-site-deterministic: var(--teal-mid);       /* deterministic_computed overlay */
```

In `viewer/lib/tag-sites-types.ts`, append after `PROVENANCE_TOKEN`:

```ts
/** Concrete hex per rendered provenance for WebGL (3Dmol) spheres, which
 *  cannot consume CSS vars. MUST stay in sync with the --tag-site-* tokens:
 *  literature = --lavender-bright (#8878c8), deterministic = --teal-mid (#3d6b60). */
export const PROVENANCE_HEX: Record<
  "literature_retrieved" | "deterministic_computed",
  string
> = {
  literature_retrieved: "#8878c8",
  deterministic_computed: "#3d6b60",
};
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd viewer && npx --yes tsx tests/tag_sites_colors.test.ts`
Expected: PASS.

- [ ] **Step 5: Verify the hex matches the tokens**

Run: `grep -E '\--lavender-bright|--teal-mid' viewer/app/design-tokens.css`
Confirm `--lavender-bright: #8878c8` and `--teal-mid: #3d6b60` (if either differs, update `PROVENANCE_HEX` to match, then re-run Step 4).

- [ ] **Step 6: Commit**

```bash
git add viewer/app/design-tokens.css viewer/lib/tag-sites-types.ts viewer/tests/tag_sites_colors.test.ts
git commit -m "feat(viewer): tag-site provenance color tokens + WebGL hex map"
```

---

### Task 2: Pure renderable-sites mapper (shared by pins + spheres)

Both overlays consume the same derived list. One pure mapper: drops the non-rendered `validated_literature` provenance, resolves each site to a residue (terminal_c → C-terminus), and computes a left-percent for the linear bar.

**Files:**
- Create: `viewer/lib/tag-sites-overlay.ts`
- Test: `viewer/tests/tag_sites_overlay.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
// viewer/tests/tag_sites_overlay.test.ts
/*
 * Pins the pure overlay mapper: rendered provenances only, residue resolution
 * (terminal_c -> C-terminus), left-percent, and clamping.
 *   npx --yes tsx tests/tag_sites_overlay.test.ts
 */
import { renderableTagSites } from "../lib/tag-sites-overlay";
import type { TaggedSite } from "../lib/tag-sites-types";

let failures = 0;
function expect(label: string, got: unknown, want: unknown): void {
  const ok = JSON.stringify(got) === JSON.stringify(want);
  if (!ok) { failures++; console.error(`FAIL ${label}\n  got:  ${JSON.stringify(got)}\n  want: ${JSON.stringify(want)}`); }
  else { console.log(`ok   ${label}`); }
}

function site(p: Partial<TaggedSite>): TaggedSite {
  return {
    site_id: "s", gene_symbol: "TFRC", uniprot_acc: "P02786",
    provenance: "literature_retrieved", det_path: null, site_kind: "internal",
    insert_after_residue: 100, residue_before: null, residue_after: null,
    topology_state: "O", extracellular: true, compartment: "extracellular",
    tag_type: "ALFA", tag_length_aa: 15, linker: null, evidence_type: null,
    functional_impact_measured: null, confidence: null, rationale: null,
    sources: [], plddt: null, conservation_rank: null, median_conservation: null,
    ...p,
  };
}

const L = 200; // topology length

const out = renderableTagSites([
  site({ site_id: "internal", insert_after_residue: 100, provenance: "literature_retrieved" }),
  site({ site_id: "cterm", site_kind: "terminal_c", insert_after_residue: null, provenance: "deterministic_computed", det_path: "disorder" }),
  site({ site_id: "validated", provenance: "validated_literature" }), // must be dropped
  site({ site_id: "nulljunction", site_kind: "internal", insert_after_residue: null }), // -> residue 1
], L);

expect("validated_literature dropped", out.map((s) => s.siteId), ["internal", "cterm", "nulljunction"]);
expect("internal residue 100 -> 50%", out[0].leftPct, 50);
expect("terminal_c resolves to C-terminus (residue L)", out[1].residue, L);
expect("terminal_c -> 100%", out[1].leftPct, 100);
expect("null internal junction -> residue 1", out[2].residue, 1);
expect("provenance carried", out[1].provenance, "deterministic_computed");

// out-of-range residue is dropped, not clamped silently into a wrong position
const oob = renderableTagSites([site({ site_id: "oob", insert_after_residue: 9999 })], L);
expect("out-of-range residue dropped", oob.length, 0);

if (failures > 0) { console.error(`\n${failures} assertion(s) failed`); process.exit(1); }
console.log("\nall assertions passed");
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd viewer && npx --yes tsx tests/tag_sites_overlay.test.ts`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement the mapper**

```ts
// viewer/lib/tag-sites-overlay.ts
/*
 * Pure overlay derivation shared by the linear TopologyBar pins and the 3D
 * StructureViewer spheres. Browser-safe (no node:fs). Drops the non-rendered
 * validated_literature provenance; resolves each site to a residue and a
 * left-percent along a topology of the given length.
 */
import type { TaggedSite, TaggedSiteProvenance } from "./tag-sites-types";

export type RenderedProvenance = "literature_retrieved" | "deterministic_computed";

export interface RenderableTagSite {
  siteId: string;
  residue: number;               // 1-indexed, within [1, topologyLength]
  leftPct: number;               // 0..100 along the linear bar
  provenance: RenderedProvenance;
  tagType: string;
  siteKind: TaggedSite["site_kind"];
}

const RENDERED: TaggedSiteProvenance[] = ["literature_retrieved", "deterministic_computed"];

/** Resolve a site to its display residue: terminal_c -> C-terminus (length);
 *  internal / terminal_n -> insert_after_residue (null -> 1). */
function residueOf(site: TaggedSite, topologyLength: number): number | null {
  if (site.site_kind === "terminal_c") return topologyLength;
  const n = site.insert_after_residue;
  if (n === null || n === 0) return 1;
  return n;
}

export function renderableTagSites(
  sites: readonly TaggedSite[],
  topologyLength: number,
): RenderableTagSite[] {
  if (topologyLength <= 0) return [];
  const out: RenderableTagSite[] = [];
  for (const site of sites) {
    if (!RENDERED.includes(site.provenance)) continue; // drop validated_literature
    const residue = residueOf(site, topologyLength);
    if (residue === null || residue < 1 || residue > topologyLength) continue;
    out.push({
      siteId: site.site_id,
      residue,
      leftPct: (residue / topologyLength) * 100,
      provenance: site.provenance as RenderedProvenance,
      tagType: site.tag_type,
      siteKind: site.site_kind,
    });
  }
  return out;
}
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd viewer && npx --yes tsx tests/tag_sites_overlay.test.ts`
Expected: PASS.

- [ ] **Step 5: Register both new unit tests in the runner**

Edit `viewer/tests/run_tag_sites_tests.sh` `tests=(...)` to add `tag_sites_colors.test.ts` and `tag_sites_overlay.test.ts`. Run: `cd viewer && bash tests/run_tag_sites_tests.sh` → PASS (6 tests).

- [ ] **Step 6: Commit**

```bash
git add viewer/lib/tag-sites-overlay.ts viewer/tests/tag_sites_overlay.test.ts viewer/tests/run_tag_sites_tests.sh
git commit -m "feat(viewer): pure renderable-tag-sites mapper (pins + spheres)"
```

---

### Task 3: TopologyBar pin overlay

Add an optional `pins` prop to `TopologyBar`. Pins are absolutely positioned, so they need a `position:relative` wrapper *outside* `.bar` (whose `overflow:hidden` would clip them).

**Files:**
- Modify: `viewer/components/surfaceome/IsoformsCard/TopologyBar.tsx`
- Modify: `viewer/components/surfaceome/IsoformsCard/TopologyBar.module.css`
- Test: `viewer/tests/topology_bar_pins.test.tsx`

- [ ] **Step 1: Write the failing render test**

```tsx
// viewer/tests/topology_bar_pins.test.tsx
/*
 * Render test: TopologyBar draws one pin per provided pin, positioned by
 * leftPct and classed by provenance. Runs via run_render_tests.sh.
 */
import { renderToStaticMarkup } from "react-dom/server";
import { test } from "node:test";
import assert from "node:assert/strict";
import { TopologyBar } from "../components/surfaceome/IsoformsCard/TopologyBar";

test("renders a pin per pin with provenance class + left%", () => {
  const html = renderToStaticMarkup(
    <TopologyBar
      topology={"O".repeat(100)}
      pins={[
        { siteId: "a", leftPct: 25, provenance: "literature_retrieved", tagType: "ALFA" },
        { siteId: "b", leftPct: 75, provenance: "deterministic_computed", tagType: "ALFA" },
      ]}
    />,
  );
  assert.equal((html.match(/data-provenance=/g) ?? []).length, 2);
  assert.match(html, /data-provenance="literature_retrieved"/);
  assert.match(html, /data-provenance="deterministic_computed"/);
  assert.match(html, /left:\s*25%/);
});

test("no pins prop -> no pin markup (unchanged bar)", () => {
  const html = renderToStaticMarkup(<TopologyBar topology={"O".repeat(10)} />);
  assert.equal((html.match(/data-provenance=/g) ?? []).length, 0);
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd viewer && npx --yes tsx --import ./tests/helpers/register.mjs --test tests/topology_bar_pins.test.tsx`
Expected: FAIL — `pins` prop not supported (no `data-provenance` in output).

- [ ] **Step 3: Add the `pins` prop + wrapper**

In `TopologyBar.tsx`, extend `Props` (currently `topology`, `ariaLabel?`, `maxResidues?`, `canonicalFrame?`) with:

```tsx
export interface TopologyPin {
  siteId: string;
  leftPct: number; // 0..100
  provenance: "literature_retrieved" | "deterministic_computed";
  tagType: string;
}
// add to Props:
//   pins?: TopologyPin[];
```

Wrap the existing `<div className={styles.bar} ...>` return in a relative wrapper and render pins as siblings *after* the bar (so `.bar`'s `overflow:hidden` doesn't clip them). Replace the existing `return ( <div className={styles.bar} ...> {segments...} </div> );` with:

```tsx
return (
  <div className={styles.barWrap} style={{ width: widthPct }}>
    <div
      className={styles.bar}
      role="img"
      aria-label={ariaLabel ?? "Per-residue topology bar"}
    >
      {segments.map((seg, i) => {
        const isGap = aligned && seg.state === CANONICAL_FRAME_GAP;
        return (
          <div
            key={i}
            className={styles.seg}
            style={{
              flexGrow: seg.length,
              background: isGap ? "transparent" : (TOPOLOGY_COLORS[seg.state] ?? "transparent"),
            }}
          />
        );
      })}
    </div>
    {(pins ?? []).map((pin) => (
      <span
        key={pin.siteId}
        className={styles.pin}
        data-provenance={pin.provenance}
        style={{ left: `${pin.leftPct}%`, background: `var(--tag-site-${pin.provenance === "literature_retrieved" ? "literature" : "deterministic"})` }}
        title={`${pin.tagType} (${pin.provenance === "literature_retrieved" ? "literature" : "deterministic"})`}
      />
    ))}
  </div>
);
```

> NOTE: the original `.bar` carried `style={{ width: widthPct }}`; that moves to `.barWrap`. Preserve the segment `title` attribute the original had if present (re-add it inside the seg map if the current code sets one — check before deleting).

In `TopologyBar.module.css` add:

```css
.barWrap { position: relative; }
.pin {
  position: absolute;
  top: -3px;
  width: 3px;
  height: 20px;
  border-radius: 2px;
  transform: translateX(-50%);
  box-shadow: 0 0 0 1px var(--bg, #fff);
  pointer-events: auto;
}
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd viewer && npx --yes tsx --import ./tests/helpers/register.mjs --test tests/topology_bar_pins.test.tsx`
Expected: PASS (2 subtests).

- [ ] **Step 5: Register in the render harness + full check**

Add `topology_bar_pins.test.tsx` to the `tests=(...)` array in `viewer/tests/run_render_tests.sh`. Then:
Run: `cd viewer && bash tests/run_render_tests.sh && npm run check`
Expected: render suite PASS; `tsc` 0 errors.

- [ ] **Step 6: Commit**

```bash
git add viewer/components/surfaceome/IsoformsCard/TopologyBar.tsx viewer/components/surfaceome/IsoformsCard/TopologyBar.module.css viewer/tests/topology_bar_pins.test.tsx viewer/tests/run_render_tests.sh
git commit -m "feat(viewer): tag-site pin overlay on TopologyBar"
```

---

### Task 4: StructureViewer `tagSites` spheres

Add a `tagSites` prop and a sphere loop mirroring the `surfaceBindAnchors` loop (`StructureViewer.tsx:1960-2019`), colored by provenance via `PROVENANCE_HEX`. The WebGL draw itself isn't unit-testable, so the residue/color resolution is already covered by Task 2's pure mapper; this task wires the prop and draws.

**Files:**
- Modify: `viewer/components/surfaceome/StructureViewerCard/StructureViewer.tsx`

- [ ] **Step 1: Add the prop type + destructure**

Near `SurfaceBindAnchor` (34-38) add:

```tsx
export interface TagSiteSphere {
  siteId: string;
  residue: number;
  provenance: "literature_retrieved" | "deterministic_computed";
  tagType: string;
}
```

Add `tagSites?: TagSiteSphere[];` to `StructureViewerProps` (beside `surfaceBindAnchors?` at ~387) and destructure with a default `tagSites = []` (beside `surfaceBindAnchors = []` at ~1047-1055).

- [ ] **Step 2: Gate + draw**

Import `PROVENANCE_HEX` from `../../../lib/tag-sites-types` at the top. Add a `hasTagSites` gate beside `hasAnchors` (~1367):

```tsx
const hasTagSites = tagSites.length > 0 && isCanonicalActive;
```

Immediately after the `surfaceBindAnchors` sphere loop (ends ~2019), add a parallel loop that draws in the SAME `viewMode === "sites"` mode:

```tsx
const shouldRenderTagSites = viewMode === "sites" && hasTagSites && !schwekeVariant;
for (let i = 0; shouldRenderTagSites && i < tagSites.length; i += 1) {
  const { siteId, residue, provenance, tagType } = tagSites[i];
  const color = PROVENANCE_HEX[provenance];
  const sel = { resi: residue, atom: "CA" };
  if (typeof viewerExt.addStyle === "function") {
    viewerExt.addStyle(sel, { sphere: { color, radius: SPHERE_RADIUS, opacity: 0.94 } });
  } else {
    viewer.setStyle(sel, { sphere: { color, radius: SPHERE_RADIUS, opacity: 0.94 } });
  }
  if (typeof viewerExt.addLabel === "function") {
    viewerExt.addLabel(`${tagType}`, {
      position: { resi: residue, atom: "CA" },
      backgroundColor: color, backgroundOpacity: 0.94, fontColor: "white",
      fontSize: 12, borderThickness: 0, inFront: true, screenOffset: { x: 16, y: 16 },
    });
  }
}
```

Update the render effect's dependency array (~2171-2172) to include `JSON.stringify(tagSites)` (mirroring the `surfaceBindAnchors` stringify) and `hasTagSites`.

- [ ] **Step 3: Make the toggle appear when only tag sites exist**

The "Topology / sites" toggle currently renders only when `hasAnchors` (2360). Change the gate for showing the toggle to `hasAnchors || hasTagSites` so tag-only proteins still get the sites view. Relabel the "SURFACE-Bind sites" button to "Sites" when tag sites are present but anchors aren't (leave existing label logic intact when `hasAnchors`). Keep changes minimal and localized to the toggle JSX (2360-2391).

- [ ] **Step 4: Typecheck**

Run: `cd viewer && npm run check`
Expected: 0 errors. (No render test here — 3Dmol needs WebGL; residue/color logic is covered by `tag_sites_overlay.test.ts`.)

- [ ] **Step 5: Commit**

```bash
git add viewer/components/surfaceome/StructureViewerCard/StructureViewer.tsx
git commit -m "feat(viewer): tag-site spheres on StructureViewer, colored by provenance"
```

---

### Task 5: Thread tag sites through GeneHeader → StructureViewer + TopologyBar

**Files:**
- Modify: `viewer/components/surfaceome/GeneHeader/GeneHeader.tsx`

- [ ] **Step 1: Add the prop**

Add `taggedSites?: TaggedSitesFile | null;` to `GeneHeader`'s props (beside `structureData?` at ~81); import `TaggedSitesFile` from `../../../lib/tag-sites-types` and `renderableTagSites` from `../../../lib/tag-sites-overlay`.

- [ ] **Step 2: Compute the rendered list once**

Inside the component, after `structureData` is known:

```tsx
const tagSiteRows =
  taggedSites?.has_data && structureData
    ? renderableTagSites(taggedSites.sites, structureData.topology.length)
    : [];
```

- [ ] **Step 3: Pass spheres to StructureViewer**

Add to the `<StructureViewer ... />` element (beside `surfaceBindAnchors={...}` at 636-658):

```tsx
tagSites={tagSiteRows.map((r) => ({
  siteId: r.siteId, residue: r.residue, provenance: r.provenance, tagType: r.tagType,
}))}
```

- [ ] **Step 4: Pass pins to the canonical TopologyBar**

Find where GeneHeader renders the canonical protein's `<TopologyBar ...>` (if none is rendered directly in GeneHeader, render one under the structure slot). Pass:

```tsx
pins={tagSiteRows.map((r) => ({
  siteId: r.siteId, leftPct: r.leftPct, provenance: r.provenance, tagType: r.tagType,
}))}
```

> If GeneHeader has no canonical `TopologyBar`, add a labelled one beneath the 3D viewer using `structureData.topology`, mirroring the `IsoformsCard` usage; keep it inside the existing `structureSlot` aside.

- [ ] **Step 5: Typecheck**

Run: `cd viewer && npm run check`
Expected: 0 errors.

- [ ] **Step 6: Commit**

```bash
git add viewer/components/surfaceome/GeneHeader/GeneHeader.tsx
git commit -m "feat(viewer): thread tag sites into StructureViewer spheres + TopologyBar pins"
```

---

### Task 6: Client-fetch the static tag-sites JSON in the gene shell

**Files:**
- Create: `viewer/lib/tag-sites-client.ts` (client-safe fetch+parse; no node:fs)
- Modify: `viewer/app/gene/page.tsx` (add to `Promise.all`, `ReadyData`, and the `<GeneDetail>`/`<GeneHeader>` threading)
- Modify: `viewer/components/surfaceome/GeneDetail/GeneDetail.tsx` (thread `taggedSites` to `<GeneHeader>`)
- Test: `viewer/tests/tag_sites_client.test.ts`

- [ ] **Step 1: Write the failing test (pure parse/guard helper)**

```ts
// viewer/tests/tag_sites_client.test.ts
/*
 * Pins the client parse guard: only accepts a well-formed TaggedSitesFile,
 * returns null otherwise (so a 404 / HTML error page never crashes the shell).
 *   npx --yes tsx tests/tag_sites_client.test.ts
 */
import { parseTaggedSitesFile } from "../lib/tag-sites-client";

let failures = 0;
function expect(label: string, got: unknown, want: unknown): void {
  const ok = JSON.stringify(got) === JSON.stringify(want);
  if (!ok) { failures++; console.error(`FAIL ${label}\n  got:  ${JSON.stringify(got)}\n  want: ${JSON.stringify(want)}`); }
  else { console.log(`ok   ${label}`); }
}

expect("valid file parses", parseTaggedSitesFile({ has_data: true, gene_symbol: "TFRC", uniprot_acc: "P02786", sites: [] })?.gene_symbol, "TFRC");
expect("missing sites -> null", parseTaggedSitesFile({ has_data: true, gene_symbol: "X", uniprot_acc: "Y" }), null);
expect("non-object -> null", parseTaggedSitesFile("<html>404</html>"), null);
expect("null -> null", parseTaggedSitesFile(null), null);

if (failures > 0) { console.error(`\n${failures} assertion(s) failed`); process.exit(1); }
console.log("\nall assertions passed");
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd viewer && npx --yes tsx tests/tag_sites_client.test.ts`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement the client helper**

```ts
// viewer/lib/tag-sites-client.ts
/*
 * Client-safe access to the static tag-sites JSON (no node:fs). The gene
 * route is a client shell, so it fetches /tag-sites/{SYMBOL}.json as a static
 * asset rather than using the server-only lib/tag-sites.ts loader.
 */
import type { TaggedSitesFile } from "./tag-sites-types";

/** Narrow an unknown payload to TaggedSitesFile, or null. Guards against a
 *  404 HTML page or malformed JSON silently becoming a "record". */
export function parseTaggedSitesFile(raw: unknown): TaggedSitesFile | null {
  if (!raw || typeof raw !== "object") return null;
  const o = raw as Record<string, unknown>;
  if (typeof o.gene_symbol !== "string") return null;
  if (typeof o.uniprot_acc !== "string") return null;
  if (typeof o.has_data !== "boolean") return null;
  if (!Array.isArray(o.sites)) return null;
  return o as unknown as TaggedSitesFile;
}

/** Fetch + parse the static tag-sites asset for a symbol. Returns null on any
 *  failure (missing file, network, bad JSON) so the shell degrades gracefully. */
export async function fetchTaggedSites(symbol: string): Promise<TaggedSitesFile | null> {
  try {
    const res = await fetch(`/tag-sites/${encodeURIComponent(symbol)}.json`, { cache: "force-cache" });
    if (!res.ok) return null;
    return parseTaggedSitesFile(await res.json());
  } catch {
    return null;
  }
}
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd viewer && npx --yes tsx tests/tag_sites_client.test.ts`
Expected: PASS. Then add it to `run_tag_sites_tests.sh` and run the runner.

- [ ] **Step 5: Wire into the gene shell**

In `viewer/app/gene/page.tsx`:
- import `fetchTaggedSites` from `../../lib/tag-sites-client` and `TaggedSitesFile`.
- add `taggedSites: TaggedSitesFile | null` to the `ReadyData` type (~134-143).
- add `fetchTaggedSites(symbol)` to the parallel `Promise.all` (~192-197) and put its result on `ReadyData.taggedSites` where the object is assembled (~215-218), e.g. `taggedSites: taggedSitesResult`.

In `viewer/components/surfaceome/GeneDetail/GeneDetail.tsx`:
- accept `taggedSites` from the spread props and pass it to `<GeneHeader ... taggedSites={taggedSites} />` (~241-248).

- [ ] **Step 6: Typecheck + full suites**

Run: `cd viewer && npm run check && bash tests/run_tag_sites_tests.sh && bash tests/run_render_tests.sh`
Expected: 0 type errors; both suites PASS.

- [ ] **Step 7: Commit**

```bash
git add viewer/lib/tag-sites-client.ts viewer/tests/tag_sites_client.test.ts viewer/tests/run_tag_sites_tests.sh viewer/app/gene/page.tsx viewer/components/surfaceome/GeneDetail/GeneDetail.tsx
git commit -m "feat(viewer): client-fetch static tag-sites JSON and thread to overlay"
```

---

### Task 7: Manual visual verification (TFRC)

- [ ] **Step 1:** `cd viewer && npm run dev`, open the gene route for **TFRC**.
- [ ] **Step 2:** Confirm the 3D viewer shows a "Sites" toggle; in Sites mode, spheres appear at ~residue 290 (internal) and the C-terminus, colored lavender (literature) / teal (deterministic).
- [ ] **Step 3:** Confirm the linear topology bar shows pins at the same positions with matching colors.
- [ ] **Step 4:** Capture a screenshot for the PR. No commit (verification only).

---

## Self-Review

**Spec coverage (Plan 2 slice):**
- Overlay on 3D structure (§5.1) → Tasks 4, 5. ✓
- Overlay on linear topology bar (§5.1) → Tasks 3, 5. ✓
- Colored by method, two rendered provenances (§3, §5.1) → Tasks 1, 2. ✓
- Client-fetch data path (§6 correction) → Task 6. ✓
- `validated_literature` never rendered (§3) → Task 2 mapper drops it (tested). ✓
- terminal_c → C-terminus residue (TFRC F760) → Task 2 (tested). ✓
- EC emphasis / non-EC dimming + toggle (§5.1): **partially deferred** — this plan draws all rendered sites; EC-emphasis styling is a follow-up polish task (note below), since the mapper already carries enough to add it.

**Deferred (documented):** EC-emphasis/dimming + non-EC toggle (§5.1) is a small styling follow-up on top of Task 3/4 output. §08 internalization tab → Plan 3. Sortable table card → out of scope (spec says overlay, not table).

**Placeholder scan:** none — pure-helper tasks carry full code; component tasks carry the exact edit against real line numbers from the code, with `tsc`/render-test verification.

**Type consistency:** `RenderableTagSite`, `renderableTagSites`, `TopologyPin`/`pins`, `TagSiteSphere`/`tagSites`, `PROVENANCE_HEX`, `parseTaggedSitesFile`/`fetchTaggedSites`, `taggedSites` prop are used consistently across Tasks 1–6. Provenance union is the same `"literature_retrieved" | "deterministic_computed"` everywhere.

**Risk note:** Task 3 rewrites TopologyBar's return JSX — preserve any existing segment `title` attribute and the `maxResidues`/`canonicalFrame` width logic exactly (moved onto `.barWrap`); the "no pins → unchanged output" render test guards against regressions to the four existing IsoformsCard call sites.
