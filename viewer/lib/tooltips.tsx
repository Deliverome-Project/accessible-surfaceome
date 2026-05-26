import type { ReactNode } from "react";

/**
 * Field-provenance tooltip text — one place to edit, shared across
 * cards. Reader-facing prose: avoids internal field names, internal
 * data-source names, and pipeline jargon. Two registers in use:
 *
 *   - **LLM-driven** lines — the deep-dive agent synthesizes from
 *     the evidence it retrieves via web search. The "**LLM-driven**"
 *     prefix is the reader's cue that the value isn't a structured
 *     dataset pull.
 *
 *   - Deterministic lines — pulled from a versioned scientific tool
 *     (DeepTMHMM, AlphaFold, SURFACE-Bind). No "LLM-driven" prefix.
 *
 * Keep prose under ~3 sentences per tooltip — the popover is small
 * and the reader is hovering, not reading a paper.
 */
export const tooltips: Record<string, ReactNode> = {
  // --------------------------------------------------------------
  // GeneHeader vitals
  // --------------------------------------------------------------

  surface_accessibility: (
    <>
      <strong>LLM-driven.</strong> The deep-dive agent&apos;s call on
      whether the protein is on the cell surface. Synthesized from
      per-method evidence (mass-spec, IHC, antibody-validated surface
      stains, etc.). One of: high, moderate, low, no, uncertain.
    </>
  ),

  experimental_surface_evidence: (
    <>
      <strong>LLM-driven.</strong> The agent&apos;s grade on how
      strong the experimental surface evidence is across all methods
      seen. Five tiers: direct multi-method, direct single-method,
      supportive but indirect, conflicting, weak.
    </>
  ),

  confidence: (
    <>
      <strong>LLM-driven.</strong> The deep-dive agent&apos;s
      confidence in its own surface call. Tracks evidence breadth ×
      per-method strength × consistency. <em>High</em> is rare;{" "}
      <em>moderate</em> is the default for well-supported calls.
    </>
  ),

  state_dependence: (
    <>
      <strong>LLM-driven.</strong> How much the surface call depends
      on cell state. <em>Low</em> = constitutive, always present;{" "}
      <em>moderate</em> = varies with context but generally holds;{" "}
      <em>high</em> = present only in specific cellular states;{" "}
      <em>unclear</em> = evidence too thin.
    </>
  ),

  triage_signal: (
    <>
      A first-pass surface call made before the deep literature dive.
      No web search, no per-method evidence — just heuristics over the
      protein&apos;s standard annotation. Useful as a sanity check; the
      deep-dive verdict above is what to read.
    </>
  ),

  headline_risks: (
    <>
      <strong>LLM-driven.</strong> Risks to surface accessibility that
      an antibody campaign would need to plan around. The agent picks
      from five categories:
      <ul style={{ margin: "0.4rem 0 0", paddingLeft: "1.1rem" }}>
        <li>
          <em>shed form</em> — a soluble fragment is proteolytically
          released into the extracellular milieu, competing with the
          surface form for binder occupancy.
        </li>
        <li>
          <em>secreted form</em> — an alternative isoform is secreted
          (not membrane-bound), present in the same compartment as the
          membrane form.
        </li>
        <li>
          <em>co-receptor</em> — the protein requires a partner for
          surface presentation; binder design has to account for the
          partner.
        </li>
        <li>
          <em>epitope masked</em> — the agent found evidence that the
          targetable surface is shielded (partner heterodimerization,
          glycan shield, conformational hiding). Severity + evidence
          strength stored in the §Risks card&apos;s{" "}
          <code>epitope_masking</code> sub-block.
        </li>
        <li>
          <em>isoform decoy</em> — DeepTMHMM topology shows an
          alternative isoform with a different topology (often a
          soluble or differently-anchored isoform). If that decoy
          expresses in target tissues, it competes for binder
          occupancy.
        </li>
      </ul>
    </>
  ),

  // --------------------------------------------------------------
  // Architecture / family / topology
  // --------------------------------------------------------------

  architecture_chip: (
    <>
      <strong>LLM-driven.</strong> How the protein sits in the
      membrane. The deep-dive agent picks one of: single-pass type I,
      single-pass type II, multi-pass, GPCR, GPI-anchored, tetraspanin,
      or other. Informed by DeepTMHMM topology, but the agent can
      override (e.g. known GPCRs with partial predictions).
    </>
  ),

  family_chip: (
    <>
      <strong>LLM-driven.</strong> The protein&apos;s functional class.
      Aligned with SURFACE-Bind&apos;s four categories (Balbi et al.
      2026, PMID:{" "}
      <a
        href="https://pubmed.ncbi.nlm.nih.gov/41604262/"
        target="_blank"
        rel="noopener noreferrer"
      >
        41604262
      </a>
      ): receptor, enzyme, transporter, or miscellaneous. Orthogonal to
      the Architecture axis above (function vs. topology).
    </>
  ),

  topology_pills: (
    <>
      DeepTMHMM <code>v1.0.24</code> per-residue topology prediction on
      the canonical protein sequence. TM-helix count + N-terminus /
      C-terminus orientation read straight off the topology string.
    </>
  ),

  // --------------------------------------------------------------
  // Structure / SURFACE-Bind
  // --------------------------------------------------------------

  afdb_plddt: (
    <>
      Mean per-residue AlphaFold pLDDT over extracellular-domain
      residues (DeepTMHMM &quot;O&quot; positions). AlphaFold v4. For
      globular / soluble-cytoplasmic proteins the label switches to{" "}
      <em>Whole pLDDT</em> — no ECD subset is meaningful.
    </>
  ),

  surface_bind: (
    <>
      MaSIF patch-based targetability scoring from the Correia lab
      (Balbi et al. 2026, PMID:{" "}
      <a
        href="https://pubmed.ncbi.nlm.nih.gov/41604262/"
        target="_blank"
        rel="noopener noreferrer"
      >
        41604262
      </a>
      ). The chip shows whether SURFACE-Bind scored this protein; the
      §SURFACE-Bind card below shows per-patch scores when available.
    </>
  ),

  cross_species_conservation: (
    <>
      Sequence identity (full-length canonical) to mouse, rat, and cyno
      orthologs. The §Orthologs card shows the per-species rows plus an
      ECD-restricted variant when topology is known.
    </>
  ),

  // --------------------------------------------------------------
  // Other agent-derived enums (Filters card)
  // --------------------------------------------------------------

  expression_level: (
    <>
      <strong>LLM-driven.</strong> The deep-dive agent&apos;s
      synthesis of where the protein is expressed. The agent searches
      the web for tissue-expression evidence and picks one of: high,
      moderate, low, absent. See §Biology for the per-tissue rows +
      cited evidence.
    </>
  ),

  expression_breadth: (
    <>
      <strong>LLM-driven.</strong> How broadly the protein is expressed
      across tissues. The agent picks one of: pan-tissue, broad,
      restricted, rare.
    </>
  ),

  surface_specificity: (
    <>
      <strong>LLM-driven.</strong> Whether the protein is dominantly on
      the cell surface or mostly intracellular with some surface
      exposure. The deep-dive agent picks one of: surface-dominant,
      mixed, mostly intracellular.
    </>
  ),

  // --------------------------------------------------------------
  // Other risks / mechanisms (used by FiltersCard pills)
  // --------------------------------------------------------------

  co_receptor_dependency: (
    <>
      <strong>LLM-driven.</strong> Whether the protein needs a partner
      to reach the surface. <em>None</em> = surfaces on its own;{" "}
      <em>modulatory</em> = a partner influences but doesn&apos;t gate
      surface presence; <em>required</em> = surface presence depends on
      a partner (a bispecific or partner-aware design may be needed);{" "}
      <em>unknown</em> = the agent found no information either way.
    </>
  ),
};
