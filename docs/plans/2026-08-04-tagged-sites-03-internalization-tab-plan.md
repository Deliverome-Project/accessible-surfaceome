# Tagged Sites — Plan 3: §08 Internalization measurements tab

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a new per-protein section — "Internalization measurements" — rendering the per-measurement rows (cell type · assay · ±ligand · rate · n · source) plus a separate qualitative-statements panel, fed by client-fetching `public/internalization/{SYMBOL}.json`.

**Architecture:** Mirror the SURFACE-Bind section pattern: a new `InternalizationCard` (SectionCard + table + StatusPill), registered as one conditional entry in `GeneDetail.tsx`'s `sections[]` (placed last → the §08 slot). Data client-fetched in the gene shell (like Plan 2's tag sites) and threaded `app/gene/page.tsx → GeneDetail → InternalizationCard`. Pure display helpers are unit-tested; the card is render-tested.

**Tech Stack:** TypeScript, React 19 client components, CSS Modules, `tsx` + `renderToStaticMarkup`.

**Parent spec:** `docs/plans/2026-08-04-tagged-sites-viewer-design.md` §5.2 · **Depends on:** Plan 1 (contracts). Independent of Plan 2.

**Data note:** the `InternalizationFile` shape (has_data, measurements[], qualitative_statements[]) and its `node:fs` loader `loadInternalization` already exist from Plan 1. As with tag sites, the live client shell fetches the static asset rather than using the server-only loader.

---

### Task 1: Client-fetch helper for internalization JSON

**Files:**
- Modify: `viewer/lib/tag-sites-client.ts` (add `parseInternalizationFile` + `fetchInternalization`)
- Test: `viewer/tests/internalization_client.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
// viewer/tests/internalization_client.test.ts
/*  npx --yes tsx tests/internalization_client.test.ts  */
import { parseInternalizationFile } from "../lib/tag-sites-client";

let failures = 0;
function expect(l: string, got: unknown, want: unknown): void {
  const ok = JSON.stringify(got) === JSON.stringify(want);
  if (!ok) { failures++; console.error(`FAIL ${l}\n  got:  ${JSON.stringify(got)}\n  want: ${JSON.stringify(want)}`); }
  else { console.log(`ok   ${l}`); }
}

expect("valid parses", parseInternalizationFile({ has_data: true, gene_symbol: "TFRC", uniprot_acc: "P02786", measurements: [], qualitative_statements: [] })?.gene_symbol, "TFRC");
expect("missing measurements -> null", parseInternalizationFile({ has_data: true, gene_symbol: "X", uniprot_acc: "Y", qualitative_statements: [] }), null);
expect("html error -> null", parseInternalizationFile("<html>404</html>"), null);

if (failures > 0) { console.error(`\n${failures} assertion(s) failed`); process.exit(1); }
console.log("\nall assertions passed");
```

- [ ] **Step 2: Run → FAIL** (`parseInternalizationFile` not exported).
  Run: `cd viewer && npx --yes tsx tests/internalization_client.test.ts`

- [ ] **Step 3: Append to `viewer/lib/tag-sites-client.ts`**

```ts
import type { InternalizationFile } from "./tag-sites-types";

export function parseInternalizationFile(raw: unknown): InternalizationFile | null {
  if (!raw || typeof raw !== "object") return null;
  const o = raw as Record<string, unknown>;
  if (typeof o.gene_symbol !== "string") return null;
  if (typeof o.uniprot_acc !== "string") return null;
  if (typeof o.has_data !== "boolean") return null;
  if (!Array.isArray(o.measurements)) return null;
  if (!Array.isArray(o.qualitative_statements)) return null;
  return o as unknown as InternalizationFile;
}

export async function fetchInternalization(symbol: string): Promise<InternalizationFile | null> {
  try {
    const res = await fetch(`/internalization/${encodeURIComponent(symbol)}.json`, { cache: "force-cache" });
    if (!res.ok) return null;
    return parseInternalizationFile(await res.json());
  } catch {
    return null;
  }
}
```

- [ ] **Step 4: Run → PASS.** Add `internalization_client.test.ts` to `run_tag_sites_tests.sh`; run the runner.
- [ ] **Step 5: Commit** — `feat(viewer): client fetch + parse guard for internalization JSON`

---

### Task 2: Display helpers (ligand-status tone, rate label)

**Files:**
- Create: `viewer/lib/internalization-display.ts`
- Test: `viewer/tests/internalization_display.test.ts`

- [ ] **Step 1: Failing test**

```ts
// viewer/tests/internalization_display.test.ts
/*  npx --yes tsx tests/internalization_display.test.ts  */
import { ligandTone, rateLabel } from "../lib/internalization-display";

let failures = 0;
function expect(l: string, got: unknown, want: unknown): void {
  const ok = JSON.stringify(got) === JSON.stringify(want);
  if (!ok) { failures++; console.error(`FAIL ${l}\n  got:  ${JSON.stringify(got)}\n  want: ${JSON.stringify(want)}`); }
  else { console.log(`ok   ${l}`); }
}

expect("constitutive tone", ligandTone("constitutive"), "teal");
expect("ligand-driven tone", ligandTone("ligand-driven"), "lavender");
expect("not stated tone", ligandTone("not stated"), "neutral");
expect("quantified rate passes through", rateLabel("t1/2 ~ 8 min", "quantified"), "t1/2 ~ 8 min");
expect("null rate -> not stated", rateLabel(null, "not quantified"), "not stated");

if (failures > 0) { console.error(`\n${failures} assertion(s) failed`); process.exit(1); }
console.log("\nall assertions passed");
```

- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement**

```ts
// viewer/lib/internalization-display.ts
/* Pure display helpers for the internalization table (browser-safe). */
import type { InternalizationMeasurement } from "./tag-sites-types";

type LigandStatus = InternalizationMeasurement["ligand_status"];

/** Chip tone per ligand status (StatusPill tones). */
export function ligandTone(status: LigandStatus): "teal" | "lavender" | "neutral" {
  if (status === "constitutive") return "teal";
  if (status === "ligand-driven") return "lavender";
  return "neutral";
}

/** Human rate label; null/empty renders as "not stated" rather than blank. */
export function rateLabel(rate: string | null, _cls: InternalizationMeasurement["rate_class"]): string {
  return rate && rate.trim() ? rate : "not stated";
}
```

- [ ] **Step 4: Run → PASS.** Add to `run_tag_sites_tests.sh`; run runner.
- [ ] **Step 5: Commit** — `feat(viewer): internalization display helpers (ligand tone, rate label)`

---

### Task 3: InternalizationCard component

**Files:**
- Create: `viewer/components/surfaceome/InternalizationCard/InternalizationCard.tsx`
- Create: `viewer/components/surfaceome/InternalizationCard/InternalizationCard.module.css`
- Test: `viewer/tests/internalization_card.test.tsx`

- [ ] **Step 1: Failing render test**

```tsx
// viewer/tests/internalization_card.test.tsx
import { renderToStaticMarkup } from "react-dom/server";
import { test } from "node:test";
import assert from "node:assert/strict";
import { InternalizationCard } from "../components/surfaceome/InternalizationCard/InternalizationCard";
import type { InternalizationFile } from "../lib/tag-sites-types";

const data: InternalizationFile = {
  has_data: true, gene_symbol: "TFRC", uniprot_acc: "P02786",
  measurements: [{
    gene_symbol: "TFRC", uniprot_acc: "P02786", cell_type: "HeLa",
    assay: "flow", ligand_status: "constitutive", ligand: null,
    rate: "t1/2 ~ 8 min", rate_class: "quantified", n_replicates: 4,
    source: { citation: "EndoNB", doi: "10.1101/2025.06.08.658482" },
  }],
  qualitative_statements: [{ statement: "internalizes constitutively", source: { citation: "canonical" } }],
};

test("renders a row per measurement + the qualitative panel", () => {
  const html = renderToStaticMarkup(<InternalizationCard data={data} n={8} />);
  assert.match(html, /HeLa/);
  assert.match(html, /t1\/2 ~ 8 min/);
  assert.match(html, /constitutive/);
  assert.match(html, /internalizes constitutively/);          // qualitative panel
});

test("empty measurements -> shows a checked-none state, still renders", () => {
  const empty: InternalizationFile = { ...data, measurements: [], qualitative_statements: [] };
  const html = renderToStaticMarkup(<InternalizationCard data={empty} n={8} />);
  assert.match(html, /No (quantitative )?measurements/i);
});
```

- [ ] **Step 2: Run → FAIL.**
  Run: `cd viewer && npx --yes tsx --import ./tests/helpers/register.mjs --test tests/internalization_card.test.tsx`

- [ ] **Step 3: Implement the card** (server component; no client interactivity needed for v1)

```tsx
// viewer/components/surfaceome/InternalizationCard/InternalizationCard.tsx
import { SectionCard } from "../SectionCard/SectionCard";
import { StatusPill } from "../StatusPill/StatusPill";
import { ligandTone, rateLabel } from "../../../lib/internalization-display";
import type { InternalizationFile } from "../../../lib/tag-sites-types";
import styles from "./InternalizationCard.module.css";

export function InternalizationCard({ data, n }: { data: InternalizationFile; n: number }) {
  const { measurements, qualitative_statements } = data;
  return (
    <SectionCard
      n={n}
      title="Internalization measurements"
      lede="Published internalization evidence — one row per measurement. Constitutive vs ligand-driven uptake is a first-class distinction; qualitative statements are a separate, weaker evidence class."
    >
      {measurements.length === 0 ? (
        <p className={styles.empty}>No quantitative measurements found for this protein.</p>
      ) : (
        <table className={styles.table}>
          <thead>
            <tr><th>Cell type</th><th>Assay</th><th>Ligand</th><th>Rate</th><th>n</th><th>Source</th></tr>
          </thead>
          <tbody>
            {measurements.map((m, i) => (
              <tr key={i}>
                <td>{m.cell_type ?? "—"}</td>
                <td>{m.assay ?? "—"}</td>
                <td><StatusPill tone={ligandTone(m.ligand_status)} size="sm">{m.ligand_status}{m.ligand ? ` · ${m.ligand}` : ""}</StatusPill></td>
                <td>{rateLabel(m.rate, m.rate_class)}</td>
                <td>{m.n_replicates ?? "—"}</td>
                <td>{m.source.doi ? <a href={`https://doi.org/${m.source.doi}`}>{m.source.citation}</a> : m.source.citation}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {qualitative_statements.length > 0 && (
        <div className={styles.qual}>
          <h3 className="h-sub">Qualitative statements (weaker evidence)</h3>
          <ul>
            {qualitative_statements.map((q, i) => (
              <li key={i}>{q.statement} <span className={styles.qualSrc}>— {q.source.citation}</span></li>
            ))}
          </ul>
        </div>
      )}
    </SectionCard>
  );
}
```

```css
/* viewer/components/surfaceome/InternalizationCard/InternalizationCard.module.css */
.table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
.table th, .table td { text-align: left; padding: var(--space-1) var(--space-2); border-bottom: 1px solid var(--line); vertical-align: top; }
.empty { color: var(--muted); }
.qual { margin-top: var(--space-3); }
.qualSrc { color: var(--muted); font-size: 0.85em; }
```

> Verify `h-sub` exists as a global type class (grep `globals.css`); if not, use `h-section` or a local class.

- [ ] **Step 4: Run → PASS.** Add `internalization_card.test.tsx` to `run_render_tests.sh`; run it; `npm run check`.
- [ ] **Step 5: Commit** — `feat(viewer): InternalizationCard (§08) — measurements table + qualitative panel`

---

### Task 4: Register the §08 section + thread data through the shell

**Files:**
- Modify: `viewer/app/gene/page.tsx` (fetch + ReadyData + pass to GeneDetail)
- Modify: `viewer/components/surfaceome/GeneDetail/GeneDetail.tsx` (accept prop + register conditional section, placed LAST)

- [ ] **Step 1:** In `app/gene/page.tsx`: import `fetchInternalization` + `InternalizationFile`; add `internalization: InternalizationFile | null` to `ReadyData`; add `fetchInternalization(symbol)` to the `Promise.all`; assign the result.

- [ ] **Step 2:** In `GeneDetail.tsx`: accept `internalization` from props. Append to the END of the `sections[]` array (so it takes the last / §08 slot), mirroring the SURFACE-Bind conditional entry (154-163):

```tsx
...(internalization?.has_data &&
(internalization.measurements.length > 0 || internalization.qualitative_statements.length > 0)
  ? [
      {
        kind: "internalization",
        label: "Internalization",
        render: (n: number) => <InternalizationCard data={internalization} n={n} />,
      },
    ]
  : []),
```
Import `InternalizationCard` and `InternalizationFile` at the top.

- [ ] **Step 3: Verify** — `cd viewer && npm run check && bash tests/run_render_tests.sh && bash tests/run_tag_sites_tests.sh` → 0 errors, all PASS.

- [ ] **Step 4: Manual** — `npm run dev`, open TFRC: an "Internalization" tab appears last, showing the seeded HeLa row + qualitative statement.

- [ ] **Step 5: Commit** — `feat(viewer): register §08 Internalization section + thread data through gene shell`

---

## Self-Review

**Spec coverage:** §5.2 internalization tab (measurements table + ±ligand first-class + separate qualitative list) → Tasks 3, 4. Client-fetch data path → Task 1. Section registration last/§08 → Task 4. ✓

**Placeholder scan:** none — full code in every implementation step; one grep-verify (`h-sub`) flagged inline.

**Type consistency:** `InternalizationFile`, `parseInternalizationFile`/`fetchInternalization`, `ligandTone`/`rateLabel`, `InternalizationCard({data,n})`, the `internalization` prop are consistent across tasks. Reuses `SectionCard`/`StatusPill` with their real prop shapes (Plan-2 exploration).

**Deferred:** column sorting (v1 renders in source order; a client `InternalizationTable` with sort mirrors `SurfaceBindTable` if needed later).
