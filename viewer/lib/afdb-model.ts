/*
 * Which AlphaFold DB model does a gene page actually render, and how much of
 * the protein does it cover?
 * ---------------------------------------------------------------------------
 * Two things used to be assumed here, and both can silently truncate what the
 * reader sees:
 *
 *   1. **One fragment.** Every AFDB URL was built as
 *      ``AF-{acc}-F1-model_{v}.pdb``. AFDB splits an entry that exceeds its
 *      per-model residue cap (2,700 aa) into overlapping fragments
 *      ``F1``/``F2``/… of ~1,400 residues each (Tunyasuvunakool et al. 2021,
 *      PMID 34293799), so an ``-F1-`` URL for such an entry renders only the
 *      first slice. The fragment set is a property of the AFDB entry, not of
 *      our sequence length, so {@link selectAfdbModel} reads it off the
 *      prediction API's own response rather than inferring it from a length
 *      rule that is AFDB's policy to change.
 *
 *   2. **``entries[0]`` is the model we asked for.** It is not. For a base
 *      accession the prediction API returns the canonical model *plus* every
 *      modelled alternative isoform, and (since AFDB began federating
 *      third-party predictions — Varadi et al. 2024, PMID 37933859) *plus*
 *      externally contributed models that reuse the same bare accession with
 *      an opaque entry id such as ``AF-0000000015138413``. Position in that
 *      array is not a contract. {@link selectAfdbModel} selects explicitly.
 *
 * What this module does NOT do is decide whether the rendered model is
 * complete. AFDB builds a model from the UniProt sequence version current at
 * model-build time, which can be shorter than the sequence our records
 * resolved — MUC3B (Q9H195) is the extreme case in this cohort: the record's
 * canonical sequence is 13,477 aa and ``AF-Q9H195-F1`` covers residues
 * 1–1,237. No API field announces that; only the coordinates do. So the
 * viewer measures coverage from the residues actually present in the fetched
 * file (see {@link pdbResidueSpan}) and shows the reader the span.
 *
 * Pure module — no ``node:`` imports — so the ``"use client"`` structure
 * viewer can import it without dragging fs/path into the browser bundle
 * (same constraint as ``./structure-viewer-types``).
 */

import { LATEST_KNOWN_AFDB_VERSION } from "./structure-viewer-types";

/** The subset of a prediction-API entry this module reads. The endpoint
 *  returns many more fields; see ``AlphafoldPredictionEntry``. */
export interface AfdbEntryLike {
  uniprotAccession?: string;
  entryId?: string;
  pdbUrl?: string;
  latestVersion?: number;
  uniprotStart?: number;
  uniprotEnd?: number;
  isComplex?: boolean;
  providerId?: string;
}

/** One fragment of the model AFDB serves for an accession. Single-fragment
 *  entries — every gene in this cohort as of 2026-11 — yield exactly one. */
export interface AfdbFragment {
  /** AFDB entry id, e.g. ``AF-P00533-F1``. */
  entryId: string;
  /** Fragment ordinal parsed off the entry id (1 for ``-F1``). */
  fragment: number;
  pdbUrl: string;
  /** 1-based, end-inclusive UniProt span, as AFDB reports it. Null when the
   *  entry omits ``uniprotStart``/``uniprotEnd`` (never observed, but the
   *  fields are optional in the response schema). */
  start: number | null;
  end: number | null;
}

export interface AfdbModelSelection<T extends AfdbEntryLike = AfdbEntryLike> {
  /** The accession this selection was made for. */
  acc: string;
  /** Fragments in ascending fragment order. Always non-empty. */
  fragments: AfdbFragment[];
  /** True when AFDB splits this entry — i.e. more than one fragment. */
  isMultiFragment: boolean;
  /** Union span across fragments, from AFDB's own metadata. Null when the
   *  entry carries no span fields. */
  reportedStart: number | null;
  reportedEnd: number | null;
  /** The representative entry (fragment 1), for pLDDT / version / entry-page
   *  metadata. AFDB reports those per fragment; fragment 1 is the one the
   *  caption has always shown. Generic so a caller passing the full
   *  prediction-API shape gets that shape back, not this module's subset. */
  entry: T;
}

/** ``AF-{acc}-F{n}`` → n. Null for an entry id that is not AFDB's own
 *  accession-keyed form (a federated third-party model, or a complex). */
export function afdbFragmentNumber(
  entryId: string | undefined,
  acc: string,
): number | null {
  if (!entryId) return null;
  // Escape the accession: it can carry an isoform suffix ("P00533-2"), and a
  // bare "-" in a RegExp character-free context is literal, but an accession
  // is interpolated here so keep it strict about shape instead of trusting it.
  if (!/^[A-Za-z0-9-]+$/.test(acc)) return null;
  const m = new RegExp(`^AF-${acc}-F(\\d+)$`).exec(entryId);
  if (!m) return null;
  const n = Number.parseInt(m[1], 10);
  return Number.isFinite(n) && n >= 1 ? n : null;
}

/**
 * Pick the model AFDB serves for exactly ``acc``, with every fragment it is
 * split into.
 *
 * Returns null when AFDB has no first-party model for this exact accession —
 * which includes the case that trips readers up most: a 200 response whose
 * only entries are alternative isoforms. LRP1 (Q07954) is the canonical
 * example; ``/api/prediction/Q07954`` answers 200 with a single entry
 * ``AF-Q07954-2-F1`` (isoform 2, residues 1–292) and no canonical model at
 * all. Rendering that under "Canonical" substitutes a 292-aa sequence for a
 * 4,544-aa protein, which is how an external reviewer read it as a
 * truncation. Null here means "say no model", not "render something".
 *
 * Selection order:
 *   1. Entries whose ``uniprotAccession`` equals ``acc`` exactly — never an
 *      isoform-suffixed sibling.
 *   2. Monomers only (``isComplex`` entries describe a different thing and
 *      carry multiple chains the topology coloring does not expect).
 *   3. AFDB's own accession-keyed entries (``AF-{acc}-F{n}``) in preference to
 *      federated third-party models with opaque ids, which are predictions
 *      from other pipelines rather than the AFDB model the caption names.
 *   4. Ascending fragment number.
 */
export function selectAfdbModel<T extends AfdbEntryLike>(
  entries: readonly T[] | null | undefined,
  acc: string,
): AfdbModelSelection<T> | null {
  if (!Array.isArray(entries) || entries.length === 0) return null;
  const mine = entries.filter(
    (e) => e.uniprotAccession === acc && !e.isComplex && !!e.pdbUrl,
  );
  if (mine.length === 0) return null;

  const firstParty = mine
    .map((e) => ({ e, fragment: afdbFragmentNumber(e.entryId, acc) }))
    .filter((x): x is { e: T; fragment: number } => x.fragment !== null)
    .sort((a, b) => a.fragment - b.fragment);

  // Fall back to whatever matched when AFDB serves this accession only as a
  // federated model: better to render a labelled third-party prediction than
  // to claim no model exists. Treated as a single fragment.
  const picked =
    firstParty.length > 0
      ? firstParty
      : [{ e: mine[0], fragment: 1 }];

  const fragments: AfdbFragment[] = picked.map(({ e, fragment }) => ({
    entryId: e.entryId ?? `AF-${acc}-F${fragment}`,
    fragment,
    pdbUrl: e.pdbUrl as string,
    start: typeof e.uniprotStart === "number" ? e.uniprotStart : null,
    end: typeof e.uniprotEnd === "number" ? e.uniprotEnd : null,
  }));

  const starts = fragments
    .map((f) => f.start)
    .filter((v): v is number => v !== null);
  const ends = fragments
    .map((f) => f.end)
    .filter((v): v is number => v !== null);

  return {
    acc,
    fragments,
    isMultiFragment: fragments.length > 1,
    reportedStart: starts.length > 0 ? Math.min(...starts) : null,
    reportedEnd: ends.length > 0 ? Math.max(...ends) : null,
    entry: picked[0].e,
  };
}

/** AFDB coordinate URL for one fragment. Prefer resolving the URL from the
 *  prediction API (which also tells you how many fragments there are); this
 *  is the offline fallback for when that endpoint is unreachable. */
export function alphafoldFragmentPdbUrl(
  uniprotAcc: string,
  fragment = 1,
  version: string = LATEST_KNOWN_AFDB_VERSION,
): string {
  const n = Number.isFinite(fragment) && fragment >= 1 ? Math.trunc(fragment) : 1;
  return `https://alphafold.ebi.ac.uk/files/AF-${uniprotAcc}-F${n}-model_${version}.pdb`;
}

/** Min/max residue number over the ATOM/HETATM records of a PDB — i.e. the
 *  span the reader is actually looking at. Returns null for a file with no
 *  atoms. Columns 23–26 are ``resSeq`` in the PDB format. */
export function pdbResidueSpan(
  pdbText: string,
): { min: number; max: number } | null {
  let min = Number.POSITIVE_INFINITY;
  let max = Number.NEGATIVE_INFINITY;
  for (const line of pdbText.split(/\r?\n/)) {
    if (!line.startsWith("ATOM") && !line.startsWith("HETATM")) continue;
    if (line.length < 26) continue;
    const resi = Number.parseInt(line.slice(22, 26).trim(), 10);
    if (!Number.isFinite(resi)) continue;
    if (resi < min) min = resi;
    if (resi > max) max = resi;
  }
  if (!Number.isFinite(min) || !Number.isFinite(max)) return null;
  return { min, max };
}

/**
 * Join AFDB fragments into one single-chain PDB in UniProt residue numbering,
 * which is the coordinate frame the rest of the pipeline already assumes (the
 * topology string, the 3Dmol ``resi`` selections, the tag-site pins).
 *
 * The one thing that cannot be read off the API is whether a fragment file
 * numbers its residues from 1 or from its UniProt start, so this does not
 * assume either: it measures each file's own first residue and offsets only
 * when the file restarts at 1 while AFDB says the fragment begins later. A
 * file already in UniProt numbering is passed through untouched.
 *
 * Overlap (AFDB fragments overlap by design) is resolved first-fragment-wins:
 * a residue already contributed by an earlier fragment is dropped, so the
 * seam does not produce two copies of the same residue at two positions.
 *
 * Atom serial numbers are renumbered sequentially; a single ``TER``/``END``
 * closes the result.
 */
export function stitchAfdbFragments(
  parts: readonly { text: string; start: number | null }[],
): string {
  const usable = parts.filter((p) => p.text.trim().length > 0);
  if (usable.length === 0) return "";
  if (usable.length === 1) return usable[0].text;

  const out: string[] = [];
  const seen = new Set<number>();
  let serial = 0;

  for (const part of usable) {
    const span = pdbResidueSpan(part.text);
    if (!span) continue;
    // Align the file onto the UniProt axis, recognising only the two
    // conventions a fragment file can plausibly use, and leaving anything
    // else alone rather than shifting coordinates by an amount we cannot
    // explain:
    //   - already UniProt-numbered (``span.min === start``) → no shift;
    //   - numbered from 1 within the fragment → shift by ``start - 1``.
    // AFDB models every residue of a fragment, so under either convention
    // the file's first modelled residue is the fragment's first residue.
    const offset =
      part.start !== null && part.start > 1 && span.min === 1
        ? part.start - 1
        : 0;
    const contributed = new Set<number>();
    for (const line of part.text.split(/\r?\n/)) {
      if (!line.startsWith("ATOM") && !line.startsWith("HETATM")) continue;
      if (line.length < 26) continue;
      const resi = Number.parseInt(line.slice(22, 26).trim(), 10);
      if (!Number.isFinite(resi)) continue;
      const mapped = resi + offset;
      // Overlap is first-fragment-wins, decided per RESIDUE: once an earlier
      // fragment has contributed a residue, every atom of that residue here
      // is dropped, so a residue is never half from one fragment and half
      // from the next.
      if (seen.has(mapped)) continue;
      contributed.add(mapped);
      serial += 1;
      out.push(renumber(line, serial, mapped));
    }
    for (const resi of contributed) seen.add(resi);
  }
  if (out.length === 0) return "";
  out.push("TER");
  out.push("END");
  return `${out.join("\n")}\n`;
}

/** Rewrite a PDB ATOM/HETATM line's serial (cols 7–11) and resSeq
 *  (cols 23–26), preserving every other fixed-width column. */
function renumber(line: string, serial: number, resi: number): string {
  const padded = line.length < 80 ? line.padEnd(80, " ") : line;
  const serialStr = String(serial).slice(-5).padStart(5, " ");
  const resiStr = String(resi).slice(-4).padStart(4, " ");
  return (
    padded.slice(0, 6) +
    serialStr +
    padded.slice(11, 22) +
    resiStr +
    padded.slice(26)
  ).trimEnd();
}
