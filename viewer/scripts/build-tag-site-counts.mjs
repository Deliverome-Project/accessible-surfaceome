// Build a per-gene tag-site category-count overlay for the catalog filters.
// Reads the committed public/tag-sites/{SYMBOL}.json files and writes
// public/data/tag-site-counts.json: { SYMBOL: { nterm_ec, cterm_ec, internal,
// disorder, lit_ec } }. Deterministic vs literature split so the catalog can
// filter "has >=1 / >=3 <category>" sites. Mirrors the fg-library.json overlay.
import { readdirSync, readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const SITES_DIR = join(here, "..", "public", "tag-sites");
const OUT = join(here, "..", "public", "data", "tag-site-counts.json");

function countsFor(sites) {
  const c = { nterm_ec: 0, cterm_ec: 0, internal: 0, disorder: 0, lit_ec: 0 };
  for (const s of sites) {
    if (s.provenance === "deterministic_computed") {
      if (s.det_path === "disorder") c.disorder += 1;
      else if (s.det_path === "surface_loop") c.internal += 1;
      else if (s.det_path === "terminal") {
        if (s.site_kind === "terminal_n") c.nterm_ec += 1;
        else if (s.site_kind === "terminal_c") c.cterm_ec += 1;
      }
      // det_path === "snorkel" is an intracellular C-term fallback — not a filter facet.
    } else if (s.provenance === "literature_retrieved") {
      // Surface-accessible literature sites (N-term tags are ecto after SP cleavage).
      if (s.extracellular || s.site_kind === "terminal_n") c.lit_ec += 1;
    }
  }
  return c;
}

const out = {};
let files = [];
try { files = readdirSync(SITES_DIR).filter((f) => f.endsWith(".json")); } catch { files = []; }
for (const f of files) {
  try {
    const d = JSON.parse(readFileSync(join(SITES_DIR, f), "utf-8"));
    if (!d?.gene_symbol || !Array.isArray(d.sites)) continue;
    const c = countsFor(d.sites);
    // Only emit genes that actually have >=1 tag site in some category.
    if (Object.values(c).some((n) => n > 0)) out[d.gene_symbol] = c;
  } catch { /* skip malformed */ }
}
mkdirSync(dirname(OUT), { recursive: true });
writeFileSync(OUT, JSON.stringify(out, null, 2) + "\n");
console.log(`wrote ${OUT} — ${Object.keys(out).length} genes with tag sites`);
