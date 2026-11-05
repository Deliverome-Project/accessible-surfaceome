import assert from "node:assert/strict";
import { readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import { test } from "node:test";

/**
 * Site-wide floor on text size: no stylesheet may set a font-size below
 * 12px (0.75rem). Tiny labels were unreadable on laptops and phones, and
 * this keeps new components from slipping under the floor. Relative `em`
 * sizes are not checked; keep them at 0.8em or more by convention.
 */
const MIN_PX = 12;

function cssFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const p = path.join(dir, name);
    if (statSync(p).isDirectory()) return cssFiles(p);
    return p.endsWith(".css") ? [p] : [];
  });
}

test(`no font-size below ${MIN_PX}px`, () => {
  const offenders: string[] = [];
  for (const root of ["app", "components"]) {
    for (const f of cssFiles(path.join(process.cwd(), root))) {
      const text = readFileSync(f, "utf8");
      for (const m of text.matchAll(/font-size:\s*([0-9.]+)(rem|px)\b/g)) {
        const px = Number(m[1]) * (m[2] === "rem" ? 16 : 1);
        if (px < MIN_PX) offenders.push(`${path.relative(process.cwd(), f)}: ${m[0]}`);
      }
    }
  }
  assert.deepEqual(offenders, [], `font sizes below ${MIN_PX}px:\n${offenders.join("\n")}`);
});
