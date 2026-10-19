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
 *  (clamped to >=1); terminal_c uses the last residue. Absent topology → unknown. */
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
