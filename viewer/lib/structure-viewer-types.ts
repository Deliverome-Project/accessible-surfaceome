/*
 * Structure-viewer data shape.
 * ------------------------------------------------------------
 * Mirrors the JSON emitted by ``scripts/build/build_structure_viewer_data.py``.
 * One file per UniProt accession under
 * ``viewer/public/structure-viewer/{UNIPROT}.json`` — loaded at SSG
 * time on the per-gene page and passed as props to
 * ``<StructureViewerCard>``.
 *
 * Indices are 1-based, end-inclusive — same convention 3Dmol uses
 * for ``viewer.setStyle({resi: "start-end"})``.
 */

export type DeepTMHMMState = "M" | "O" | "I" | "S" | "B";

export type DeepTMHMMType = "TM" | "SP+TM" | "SP" | "BETA" | "GLOB";

export interface StructureViewerData {
  uniprot_acc: string;
  deeptmhmm_type: DeepTMHMMType;
  sequence_length: number;
  /** Per-residue topology string. One character per residue, alphabet M/O/I/S/B. */
  topology: string;
  /** Collapsed [start, end] spans per state. Empty list if state never appears. */
  topology_ranges: Record<DeepTMHMMState, [number, number][]>;
  tm_helix_count: number;
  signal_peptide_length: number;
  source_cohort: string;
  source_tool: string;
  /** AlphaFold DB pdbUrl baked in at build time via the prediction API.
   *  Saves a round-trip vs. re-querying at runtime; the runtime falls
   *  back to a fresh prediction-API call if this URL ever 404s. */
  pdb_url?: string | null;
  /** AFDB model version at the time `pdb_url` was baked. Informational. */
  latest_version?: number | null;

  // -- Library-member fields. Present only when this card is showing the protein a
  //    library member actually encodes, rather than the gene's canonical sequence.
  /** The library candidate this structure + topology belongs to, e.g. ``l1-p0031``. */
  library_candidate_id?: string | null;
  /** Library tranche: ``l1`` / ``l2``. NOT a DeepTMHMM tool version. */
  library_tranche?: string | null;
  library_candidate_set?: string | null;
  /** ``colabfold`` = we folded the ordered sequence; ``alphafold_db`` = AFDB's model is
   *  the ordered protein, or contains it. */
  library_model_source?: string | null;
  /** identical | contained | ours_by_construction | … */
  library_proteoform_match?: string | null;
  /** construct residue i == model residue i + offset. MUST be applied when rendering:
   *  offsets run to 134, and ignoring one draws a plausible-looking frame shift. */
  library_residue_offset?: number;
  /** Inclusive 1-based model residues the construct covers. The renderer clips to this
   *  so a longer model does not silently show protein the construct does not contain. */
  library_display_range?: [number, number] | null;
  /** Why an alternate was not chosen, for the "not the ordered protein" label. */
  library_note?: string | null;
}

/**
 * The DeepTMHMM topology color palette — kept in sync with the original
 * deliverome-internal structure-site viewer (see
 * ``cloudflare/surfaceome_structure_site_viewer/deploy_static/index.html``
 * in that repo, ``TOPOLOGY_COLORS``).
 *
 * Lives in the types file (no ``node:`` imports) so the client-side
 * 3Dmol component can import it without dragging in fs/path. Server-side
 * loader logic stays in ``./structure-viewer.ts``.
 */
export const TOPOLOGY_COLORS: Record<string, string> = {
  M: "#FFD579", // TM helix
  O: "#8878C8", // extracellular — brand lavender-bright (purple)
  I: "#A9CFA8", // intracellular (inside)
  S: "#DD5955", // signal peptide — red
  B: "#C7CED6", // beta-strand (rare in this dataset)
};

/**
 * Neutral slate-gray for the translucent bilayer slab. Reads as
 * "membrane the TM helix is embedded in" while leaving the purple
 * extracellular cartoon as the page's high-saturation accent.
 * Shared with the legend so the swatch matches the rendered slab.
 */
export const MEMBRANE_COLOR = "#A0A4AB";

/**
 * Latest AFDB model version we know about. Bumped manually when
 * AFDB rolls a new release across the predominant model set (v4 →
 * v6 in 2025-08; v1–v5 were retired from the file server at that
 * time, which is why `alphafoldPdbUrl(acc, "v4")` started 404ing).
 *
 * Most code paths should NOT consume this directly — they should
 * resolve the canonical URL through {@link alphafoldPredictionApiUrl}
 * so the version always matches what AFDB is currently serving.
 * `LATEST_KNOWN_AFDB_VERSION` is the *fallback* used when the
 * prediction API itself is unreachable; keep it pinned to the
 * latest stable so the offline-fallback path lands as close to a
 * real URL as possible.
 *
 * When you bump this past `vN`: also bump the v4 fallbacks in
 * `src/accessible_surfaceome/agents/surfaceome_v1/_stub_structure`
 * + `orchestrator.py` (they're cosmetic placeholders but should
 * track) and re-run `scripts/build/build_structure_viewer_data.py` to
 * refresh any baked URLs in `viewer/public/structure-viewer/*.json`.
 */
export const LATEST_KNOWN_AFDB_VERSION = "v6";

export function alphafoldPdbUrl(
  uniprotAcc: string,
  version: string = LATEST_KNOWN_AFDB_VERSION,
): string {
  return `https://alphafold.ebi.ac.uk/files/AF-${uniprotAcc}-F1-model_${version}.pdb`;
}

/**
 * AFDB serves a single API endpoint per UniProt that returns the
 * current latest model + a ready-to-use ``pdbUrl``. Querying this
 * before fetching the PDB lets the viewer auto-track AFDB version
 * bumps without us having to keep {@link LATEST_KNOWN_AFDB_VERSION}
 * in lockstep with every minor release.
 */
export function alphafoldPredictionApiUrl(uniprotAcc: string): string {
  return `https://alphafold.ebi.ac.uk/api/prediction/${uniprotAcc}`;
}

/** Shape of one entry returned by ``alphafoldPredictionApiUrl``. The
 *  endpoint returns an array (typically length 1 for a single UniProt).
 *  We only need ``pdbUrl`` + ``latestVersion``; the API has many other
 *  fields we don't depend on. */
export interface AlphafoldPredictionEntry {
  pdbUrl: string;
  cifUrl?: string;
  bcifUrl?: string;
  latestVersion?: number;
  entryId?: string;
  modelEntityId?: string;
}

// ---------------------------------------------------------------------------
// Browser-safe structure derivation.
// ---------------------------------------------------------------------------
// `structureViewerDataFromRecord` + `loadSchwekeHomomer` were previously in
// `./structure-viewer.ts`, but that module's top-level `node:fs` import
// (needed only by the file-reading `loadStructureViewerData`) can't be
// tree-shaken across a `"use client"` boundary — importing either pure
// function from a client component would drag `node:fs` into the browser
// bundle and fail the build with `UnhandledSchemeError`. They're pure (no
// fs / path), so they live here in the types leaf — same pattern as the
// enum helpers in `./enums` — and `./structure-viewer.ts` re-exports them
// for existing server-side importers. The client gene shell imports them
// straight from here.

// Schweke coordinate PDBs are served from the PUBLIC R2 bucket
// ``surfaceome-structures`` (keys ``schweke/{filename}``). Override the
// base via ``NEXT_PUBLIC_STRUCTURES_BASE`` without touching code; the
// client fetch is 404-tolerant, so a not-yet-ingested PDB just shows the
// tab's graceful "unavailable" state.
export const STRUCTURES_BASE = (
  process.env.NEXT_PUBLIC_STRUCTURES_BASE ||
  "https://pub-94415fd52d394bc18219b3957a97b823.r2.dev"
).replace(/\/+$/, "");

/** A subset of the full Schweke homomer variant the StructureViewer
 *  consumes — the caller (GeneHeader) assembles the rest (``source``,
 *  ``id``, ``label``, ``topology``, ``deeptmhmm_type``) at the call site
 *  where the canonical topology / type is already in hand. */
export interface SchwekeHomomerLoaderRow {
  uniprot_acc: string;
  pdb_url: string;
  af_model_num: number;
  ecd_only: boolean;
  /** Cyclic-symmetry order N of the rendered model (homo-N-mer). 2 for a
   *  plain dimer; 3..13 for an AnAnaS-reconstructed full complex. */
  stoichiometry: number;
}

/** Build a Schweke loader row from the ``deterministic_features
 *  .homo_oligomerization`` block served on the per-gene record. Returns
 *  ``null`` when the protein isn't a Schweke positive OR when the served
 *  block lacks the PDB filename needed to construct the asset URL. Pure —
 *  no filesystem reads; ``pdb_url`` points at the public R2 bucket (see
 *  ``STRUCTURES_BASE``) and the client fetch is 404-tolerant. */
export function loadSchwekeHomomer(
  uniprotAcc: string | null | undefined,
  homo_oligomerization?:
    | {
        is_homo_oligomer: boolean;
        stoichiometry?: number | null;
        af_model_num?: number | null;
        is_ecd_only: boolean;
        dimer_pdb_filename?: string | null;
        complex_pdb_filename?: string | null;
      }
    | null,
): SchwekeHomomerLoaderRow | null {
  if (!uniprotAcc) return null;
  if (!/^[A-Z0-9-]+$/i.test(uniprotAcc)) return null;
  if (!homo_oligomerization || !homo_oligomerization.is_homo_oligomer) {
    return null;
  }
  const acc = uniprotAcc.toUpperCase();
  const stoichiometry =
    typeof homo_oligomerization.stoichiometry === "number" &&
    homo_oligomerization.stoichiometry >= 2
      ? homo_oligomerization.stoichiometry
      : 2;
  // File-naming convention: dimers (c2) come from AF_dimer_models_core
  // and live at ``{ACC}_V1_{N}.pdb``; higher-order complexes (c≥3) come
  // from full_complexes_bigbang and live at ``{ACC}_V1_{N}_c{N}.pdb``.
  // Prefer the D1-served filename when present.
  const rawFilename =
    stoichiometry > 2
      ? homo_oligomerization.complex_pdb_filename
      : homo_oligomerization.dimer_pdb_filename;
  // Strip the trailing ``_model_<n>_rank_<n>`` the full_complexes_bigbang
  // export appends, so older baked records still resolve.
  const filename =
    rawFilename?.replace(/_model_\d+_rank_\d+(?=\.pdb$)/i, "") ?? rawFilename;
  if (!filename && homo_oligomerization.af_model_num == null) {
    return null;
  }
  const base = `${STRUCTURES_BASE}/schweke`;
  const pdb_url = filename
    ? `${base}/${filename}`
    : stoichiometry > 2
      ? `${base}/${acc}_V1_${homo_oligomerization.af_model_num}_c${stoichiometry}.pdb`
      : `${base}/${acc}_V1_${homo_oligomerization.af_model_num}.pdb`;
  return {
    uniprot_acc: acc,
    pdb_url,
    af_model_num: homo_oligomerization.af_model_num ?? 1,
    ecd_only: homo_oligomerization.is_ecd_only,
    stoichiometry,
  };
}

/** Collapse a per-residue topology string into 1-based, end-inclusive
 *  [start, end] spans per DeepTMHMM state. */
function topologyRanges(
  topology: string,
): Record<DeepTMHMMState, [number, number][]> {
  const ranges: Record<DeepTMHMMState, [number, number][]> = {
    M: [],
    O: [],
    I: [],
    S: [],
    B: [],
  };
  let i = 0;
  while (i < topology.length) {
    const ch = topology[i] as DeepTMHMMState;
    let j = i;
    while (j + 1 < topology.length && topology[j + 1] === ch) j += 1;
    if (ch in ranges) ranges[ch].push([i + 1, j + 1]);
    i = j + 1;
  }
  return ranges;
}

function deepTMHMMType(topology: string): DeepTMHMMType {
  const hasM = topology.includes("M");
  const hasS = topology.includes("S");
  if (hasM && hasS) return "SP+TM";
  if (hasM) return "TM";
  if (topology.includes("B")) return "BETA";
  if (hasS) return "SP";
  return "GLOB";
}

/**
 * Derive structure-viewer data from a deep-dive record's canonical
 * topology (which comes from D1 via the Worker). This is the primary
 * structure-data path for the client gene shell — the deep-dive record
 * carries `canonical_topology` for every gene, so it renders the 3D
 * viewer without any per-gene static file.
 *
 * Returns null only when there is no UniProt accession. An empty
 * per-residue topology falls through as GLOB (whole-protein gray) rather
 * than hiding the viewer — the AFDB model still exists and is worth
 * rendering. `pdb_url` is left null so the client routes the first fetch
 * through the AFDB prediction API (auto-tracks version bumps instead of
 * 404ing on a stale baked URL).
 */
export function structureViewerDataFromRecord(
  uniprotAcc: string | null | undefined,
  canonicalTopology:
    | {
        per_residue_topology?: string | null;
        tm_helix_count?: number;
        signal_peptide_length?: number;
        tool_version?: string;
      }
    | null
    | undefined,
): StructureViewerData | null {
  if (!uniprotAcc) return null;
  if (!/^[A-Z0-9-]+$/i.test(uniprotAcc)) return null;
  const topology = canonicalTopology?.per_residue_topology ?? "";
  const type = deepTMHMMType(topology);
  return {
    uniprot_acc: uniprotAcc,
    deeptmhmm_type: type,
    sequence_length: topology.length,
    topology,
    topology_ranges: topologyRanges(topology),
    tm_helix_count: canonicalTopology?.tm_helix_count ?? 0,
    signal_peptide_length: canonicalTopology?.signal_peptide_length ?? 0,
    source_cohort: "deep_dive_record",
    source_tool: canonicalTopology?.tool_version ?? "deeptmhmm",
    pdb_url: null,
    latest_version: null,
  };
}

/**
 * Build viewer data for the protein a LIBRARY MEMBER encodes, rather than the gene's
 * canonical sequence.
 *
 * Returns null unless both halves are present and agree, because a half-answer here is
 * worse than none: colouring a library model with canonical topology offsets the overlay
 * silently, and renumbering a model without its topology does the same in reverse. The
 * caller falls back to {@link structureViewerDataFromRecord}, which is explicitly about
 * the canonical protein.
 *
 * The topology string is the v1 (`per_residue_topology`) one — the alphabet
 * {@link TOPOLOGY_COLORS} is keyed on. The v2 string uses a different alphabet and must
 * never be substituted.
 */
export function structureViewerDataFromLibraryMember(
  topology:
    | {
        candidate_id?: string | null;
        library?: string | null;
        candidate_set?: string | null;
        per_residue_topology?: string | null;
        tm_helix_count?: number;
        signal_peptide_length?: number;
        cohort?: string | null;
        tool?: string | null;
        topology_version?: string | null;
        topology_acc?: string | null;
      }
    | null
    | undefined,
  structure:
    | {
        candidate_id?: string | null;
        source?: string | null;
        r2_key?: string | null;
        model_url?: string | null;
        proteoform_match?: string | null;
        residue_offset?: number;
        ordered_length_aa?: number | null;
        display_first_model_residue?: number | null;
        display_last_model_residue?: number | null;
        is_chosen?: boolean;
        note?: string | null;
      }
    | null
    | undefined,
): StructureViewerData | null {
  const topo = topology?.per_residue_topology ?? "";
  if (!topo || !structure?.is_chosen) return null;
  // Both halves must describe the SAME member, or we would be colouring one member's
  // model with another's topology — the precise failure this module exists to prevent.
  if (
    !topology?.candidate_id ||
    !structure.candidate_id ||
    topology.candidate_id !== structure.candidate_id
  ) {
    return null;
  }
  // The topology was computed on the ordered sequence, so its length IS the construct
  // length. A disagreement means one of the two is about a different protein.
  const orderedLen = structure.ordered_length_aa ?? null;
  if (orderedLen != null && orderedLen !== topo.length) return null;

  const url = structure.r2_key
    ? `${STRUCTURES_BASE}/${structure.r2_key.replace(/^\/+/, "")}`
    : (structure.model_url ?? null);
  if (!url) return null;

  const first = structure.display_first_model_residue ?? null;
  const last = structure.display_last_model_residue ?? null;

  return {
    uniprot_acc: topology.topology_acc ?? topology.candidate_id,
    deeptmhmm_type: deepTMHMMType(topo),
    sequence_length: topo.length,
    topology: topo,
    topology_ranges: topologyRanges(topo),
    tm_helix_count: topology.tm_helix_count ?? 0,
    signal_peptide_length: topology.signal_peptide_length ?? 0,
    source_cohort: topology.cohort ?? "library_designed_orf",
    source_tool: topology.tool ?? "deeptmhmm_v1",
    pdb_url: url,
    latest_version: null,
    library_candidate_id: topology.candidate_id,
    library_tranche: topology.library ?? null,
    library_candidate_set: topology.candidate_set ?? null,
    library_model_source: structure.source ?? null,
    library_proteoform_match: structure.proteoform_match ?? null,
    library_residue_offset: structure.residue_offset ?? 0,
    library_display_range: first != null && last != null ? [first, last] : null,
    library_note: structure.note ?? null,
  };
}

/** The per-member rows the Worker serves, as this module needs them. Structural subset
 *  of `deterministic_features.library_designed_topology` / `_structure` so the viewer
 *  does not have to import the whole record type here. */
export interface LibraryTopologyRow {
  candidate_id?: string | null;
  library?: string | null;
  candidate_set?: string | null;
  per_residue_topology?: string | null;
  tm_helix_count?: number;
  signal_peptide_length?: number;
  cohort?: string | null;
  tool?: string | null;
  topology_version?: string | null;
  topology_acc?: string | null;
}

export interface LibraryStructureRow {
  candidate_id?: string | null;
  candidate_set?: string | null;
  source?: string | null;
  r2_key?: string | null;
  model_url?: string | null;
  proteoform_match?: string | null;
  residue_offset?: number;
  ordered_length_aa?: number | null;
  display_first_model_residue?: number | null;
  display_last_model_residue?: number | null;
  is_chosen?: boolean;
  note?: string | null;
}

/** A readable tab label for a library member, e.g. "Ordered (l1-p0031)". */
function libraryVariantLabel(row: LibraryTopologyRow): string {
  const set = row.candidate_set ?? "";
  if (set === "isoform") return "Ordered isoform";
  if (set === "ortholog") return "Ordered ortholog";
  if (set === "expression_rescue") return "Ordered rescue arm";
  return "Ordered";
}

/**
 * One viewer tab per library member that has BOTH a chosen structure and a v1 topology
 * for its exact ordered sequence.
 *
 * Pairs the two halves by `candidate_id` and drops any member where they disagree,
 * because the failure mode is silent: a model paired with another proteoform's topology
 * renders as a perfectly plausible topology diagram. Members without a chosen structure
 * -- 26 of L1, the never-comparable ones and TPO -- get no tab, rather than falling back
 * to the gene's canonical model, which is a different protein.
 */
export function libraryStructureVariants(
  record: {
    deterministic_features?: {
      library_designed_topology?: LibraryTopologyRow[] | null;
      library_designed_structure?: LibraryStructureRow[] | null;
    } | null;
  },
  /**
   * Accessions already shown as their own tab (canonical, isoforms, orthologs). A member
   * whose chosen structure IS one of those models gets no tab of its own: it would load
   * byte-identical coordinates under a second name. SLC6A8 is the case — its library
   * construct is `l1-p2010`, whose chosen structure is AFDB's `AF-P48029-F1`, and P48029
   * is the gene's canonical accession. Use {@link libraryConstructByAccession} to badge
   * the existing tab instead, which is also the more useful answer: "Canonical IS the
   * library construct" says more than a duplicate tab does.
   */
  shownAccessions: Iterable<string> = [],
): StructureVariantLibraryInput[] {
  const shown = new Set(
    Array.from(shownAccessions, (a) => String(a).toUpperCase()).filter(Boolean),
  );
  const topo = record?.deterministic_features?.library_designed_topology ?? [];
  const struct = record?.deterministic_features?.library_designed_structure ?? [];
  if (!topo.length || !struct.length) return [];

  const chosenByCandidate = new Map<string, LibraryStructureRow>();
  for (const srow of struct) {
    if (!srow.is_chosen || !srow.candidate_id) continue;
    chosenByCandidate.set(srow.candidate_id, srow);
  }

  const out: StructureVariantLibraryInput[] = [];
  for (const trow of topo) {
    const cid = trow.candidate_id;
    if (!cid) continue;
    const srow = chosenByCandidate.get(cid);
    if (!srow) continue;
    const built = structureViewerDataFromLibraryMember(trow, srow);
    if (!built) continue; // the builder already refuses every mismatch
    // Skip a member whose model is already on screen under another tab. Only AFDB-served
    // members can collide: our own ColabFold models live at an R2 key nothing else loads.
    if (!srow.r2_key && built.uniprot_acc && shown.has(built.uniprot_acc.toUpperCase())) {
      continue;
    }
    out.push({
      source: "library",
      id: `library-${cid}`,
      label: libraryVariantLabel(trow),
      sublabel: cid,
      topology: built.topology,
      deeptmhmm_type: built.deeptmhmm_type,
      pdb_url: built.pdb_url as string,
      candidate_id: cid,
      tranche: trow.library ?? null,
      candidate_set: trow.candidate_set ?? null,
      model_source: srow.source ?? null,
      proteoform_match: srow.proteoform_match ?? null,
      residue_offset: built.library_residue_offset ?? 0,
      display_range: built.library_display_range ?? null,
      note: srow.note ?? null,
    });
  }
  return out;
}

/**
 * Accession -> the library member whose chosen structure is that exact model.
 *
 * Lets the card mark an existing tab as the library construct rather than duplicating it.
 * Two genes make the point in opposite directions: SLC6A8's library construct IS its
 * canonical (`l1-p2010` -> `AF-P48029-F1`), so Canonical should read as the library
 * construct; MUC1's is a 273-aa form we folded ourselves, so its canonical — the 1,255-aa
 * model whose length is mostly low-pLDDT strand — is explicitly NOT in the library, which
 * is worth saying on a card where that model is what opens by default.
 *
 * Only members served from AlphaFold DB appear. Ours live at an R2 key no other tab loads,
 * so they are never a duplicate and get their own tab from
 * {@link libraryStructureVariants}.
 */
export function libraryConstructByAccession(record: {
  deterministic_features?: {
    library_designed_topology?: LibraryTopologyRow[] | null;
    library_designed_structure?: LibraryStructureRow[] | null;
  } | null;
}): Map<string, { candidate_id: string; library: string | null; candidate_set: string | null }> {
  const topo = record?.deterministic_features?.library_designed_topology ?? [];
  const struct = record?.deterministic_features?.library_designed_structure ?? [];
  const chosen = new Map<string, LibraryStructureRow>();
  for (const srow of struct) {
    if (srow.is_chosen && srow.candidate_id) chosen.set(srow.candidate_id, srow);
  }
  const out = new Map<
    string,
    { candidate_id: string; library: string | null; candidate_set: string | null }
  >();
  for (const trow of topo) {
    const cid = trow.candidate_id;
    if (!cid) continue;
    const srow = chosen.get(cid);
    // r2_key means it is our own model, which is never an existing tab.
    if (!srow || srow.r2_key) continue;
    const acc = trow.topology_acc;
    if (!acc) continue;
    out.set(acc.toUpperCase(), {
      candidate_id: cid,
      library: trow.library ?? null,
      candidate_set: trow.candidate_set ?? null,
    });
  }
  return out;
}

/** The shape {@link libraryStructureVariants} emits — structurally the component's
 *  `StructureVariantLibrary`, declared here to avoid a types/component import cycle. */
export interface StructureVariantLibraryInput {
  source: "library";
  id: string;
  label: string;
  sublabel?: string;
  topology: string;
  deeptmhmm_type: StructureViewerData["deeptmhmm_type"];
  pdb_url: string;
  candidate_id: string;
  tranche: string | null;
  candidate_set: string | null;
  model_source: string | null;
  proteoform_match: string | null;
  residue_offset: number;
  display_range: [number, number] | null;
  note: string | null;
}

/** Highlight color for a reader-selected residue (the 3D viewer's
 *  "Highlight residue" box and the topology strip's marker). Hot pink,
 *  which no topology / tag-site / contact palette uses — yellow vanished
 *  into the TM helices. */
export const RESIDUE_HIGHLIGHT_COLOR = "#FF1F8F";
