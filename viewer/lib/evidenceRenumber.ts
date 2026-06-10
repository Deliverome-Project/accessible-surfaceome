import type { SurfaceomeRecord } from "./surfaceome-types";

/**
 * Renumber every `aN_evi_NN` evidence id in a record into a single
 * per-record `evi_N` sequence, dedup-aware.
 *
 *  Why: the orchestrator splits its evidence ledger into two lanes
 *  (`a1_evi_*` from the surface-evidence agent, `a2_evi_*` from the
 *  biology agent), and the trailing index counts WITHIN each lane —
 *  so `a1_evi_01` and `a2_evi_01` regularly coexist as DIFFERENT
 *  papers in the same record. A spot-check of 14 records found
 *  cross-lane collisions in 13 of them (236 collision groups total),
 *  meaning the trailing-number-only chip label was ambiguous on
 *  effectively every gene page.
 *
 *  This helper builds a single `1..N` sequence over the merged
 *  ledger, in `rec.evidence[]` order (the canonical order the
 *  orchestrator already stabilises), and pre-emptively folds
 *  duplicates onto their canonical's number via the `duplicate_of`
 *  pointer. The walk rewrites every string in the record — top-level
 *  `evidence_id`, every `cited_evidence_ids[]` element, every inline
 *  `aN_evi_NN` token embedded in rationale prose — so the rendered
 *  chip can simply strip the `evi_` prefix and show the bare number.
 *
 *  Chosen the `evi_N` form (not bare `N`) so :func:`linkifyEvidenceRefs`
 *  still has a distinctive token to find inside freeform prose —
 *  bare digits would be ambiguous with paragraph numbers, percentages,
 *  fig refs, etc.
 */
export function renumberEvidenceIds(
  rec: SurfaceomeRecord,
): SurfaceomeRecord {
  const ev = rec.evidence ?? [];
  if (ev.length === 0) return rec;

  // Pass 1: assign sequential numbers to non-duplicate canonicals in
  // ledger order. Skip duplicates so two entries that point to the
  // same source quote share a single number.
  type EvidenceLite = { evidence_id: string; duplicate_of?: string | null };
  const idToNumber = new Map<string, number>();
  let nextNum = 1;
  for (const e of ev as EvidenceLite[]) {
    if (!e.duplicate_of) {
      idToNumber.set(e.evidence_id, nextNum++);
    }
  }

  // Pass 2: duplicates inherit their canonical's number. A duplicate
  // whose canonical is missing (shouldn't happen, but be defensive)
  // gets its own fresh number rather than dropping out of the map.
  for (const e of ev as EvidenceLite[]) {
    if (e.duplicate_of) {
      const canonNum = idToNumber.get(e.duplicate_of);
      idToNumber.set(e.evidence_id, canonNum ?? nextNum++);
    }
  }

  // Build the string-replace map: each old id → its `evi_N` form.
  const renameMap = new Map<string, string>();
  for (const [oldId, n] of idToNumber) {
    renameMap.set(oldId, `evi_${n}`);
  }

  // Single regex captures every legacy token form, walked over every
  // string in the record.
  const tokenRe = /a[12]_evi_\d+/g;
  const rewriteString = (s: string): string =>
    s.replace(tokenRe, (m) => renameMap.get(m) ?? m);

  return rewriteNode(rec, rewriteString) as SurfaceomeRecord;
}

/** Recursive deep-walker over plain JSON. Rewrites every string leaf
 *  via the supplied transform; arrays + objects are reconstructed
 *  immutably so the caller's input record is not mutated.
 *
 *  Special case: when an object key is ``cited_evidence_ids`` and its
 *  value is a string array, dedupe the result preserving the first
 *  occurrence's order. Without this, a list that cites both a
 *  canonical and its cross-planner duplicate (e.g. ``a1_evi_18`` plus
 *  the ``a2_evi_03`` that's ``duplicate_of`` it) collapses to two
 *  identical ``evi_18`` strings after renumber — and React throws on
 *  the duplicate key in the chip list. Dedup is the right behavior
 *  semantically too: two chips pointing to the same canonical entry
 *  is reader noise, not signal. */
function rewriteNode(node: unknown, rewriteString: (s: string) => string): unknown {
  if (typeof node === "string") return rewriteString(node);
  if (Array.isArray(node)) {
    return node.map((child) => rewriteNode(child, rewriteString));
  }
  if (node && typeof node === "object") {
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(node)) {
      const rewritten = rewriteNode(v, rewriteString);
      if (
        k === "cited_evidence_ids" &&
        Array.isArray(rewritten) &&
        rewritten.every((x) => typeof x === "string")
      ) {
        out[k] = Array.from(new Set(rewritten as string[]));
      } else {
        out[k] = rewritten;
      }
    }
    return out;
  }
  return node;
}
