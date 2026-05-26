import type { ReactNode } from "react";

/**
 * Field-provenance tooltip text — one place to edit, shared across
 * cards. Reader-facing prose: avoids internal field names, internal
 * data-source names, and pipeline jargon. Two registers in use:
 *
 *   1. "Deterministic" lines — pulled from a versioned scientific tool
 *      (DeepTMHMM, AlphaFold, SURFACE-Bind). The tooltip names the
 *      tool + version when relevant.
 *
 *   2. "Deep-dive agent" lines — the agent synthesizes from the
 *      evidence it retrieves via web search. The tooltip says what
 *      the agent's job was, not which tables it touched.
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
      The deep-dive agent&apos;s call on whether the protein is on the
      cell surface. Synthesized from per-method evidence (mass-spec,
      IHC, antibody-validated surface stains, etc.). One of{" "}
      <code>high · moderate · low · no · uncertain</code>.
    </>
  ),

  experimental_surface_evidence: (
    <>
      The agent&apos;s grade on how strong the experimental surface
      evidence is across all methods seen. Five tiers:{" "}
      <code>
        direct_multi_method · direct_single_method ·
        supportive_but_indirect · conflicting · weak
      </code>
      .
    </>
  ),

  confidence: (
    <>
      The deep-dive agent&apos;s confidence in its own surface call.
      Tracks evidence breadth × per-method strength × consistency.{" "}
      <code>high</code> is rare; <code>moderate</code> is the default
      for well-supported calls.
    </>
  ),

  state_dependence: (
    <>
      How much the surface call depends on cell state.{" "}
      <code>low</code> = constitutive (always present),{" "}
      <code>moderate</code> = varies with context but generally holds,{" "}
      <code>high</code> = present only in specific states (cancer-only,
      stress-only, EMT-only), <code>unclear</code> = evidence too
      thin.
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
      Risks to surface accessibility that an antibody campaign would
      need to plan around. Five categories:{" "}
      <code>
        shed_form · secreted_form · co_receptor · epitope_masked ·
        isoform_decoy
      </code>
      .
    </>
  ),

  // --------------------------------------------------------------
  // Architecture / family / topology
  // --------------------------------------------------------------

  architecture_chip: (
    <>
      How the protein sits in the membrane. The deep-dive agent picks
      one of:{" "}
      <code>
        single_pass_T1 · single_pass_T2 · multi_pass · GPCR ·
        GPI_anchored · tetraspanin · other
      </code>
      . Informed by DeepTMHMM topology, but the agent can override
      (e.g. known GPCRs with partial predictions).
    </>
  ),

  family_chip: (
    <>
      The protein&apos;s functional class. Aligned with SURFACE-Bind&apos;s
      four categories (Balbi et al. 2026, PMID:{" "}
      <a
        href="https://pubmed.ncbi.nlm.nih.gov/41604262/"
        target="_blank"
        rel="noopener noreferrer"
      >
        41604262
      </a>
      ): <code>receptor · enzyme · transporter · miscellaneous</code>.
      Orthogonal to the Architecture axis above (function vs.
      topology).
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
      The deep-dive agent&apos;s synthesis of where the protein is
      expressed. The agent searches the web for tissue-expression
      evidence and picks one of{" "}
      <code>high · moderate · low · absent</code>. See §Biology for the
      per-tissue rows + cited evidence.
    </>
  ),

  expression_breadth: (
    <>
      How broadly the protein is expressed across tissues. The agent
      synthesizes from the per-tissue evidence into:{" "}
      <code>pan_tissue · broad · restricted · rare</code>.
    </>
  ),

  surface_specificity: (
    <>
      Whether the protein is dominantly on the cell surface or mostly
      intracellular with some surface exposure. The deep-dive agent
      picks:{" "}
      <code>surface_dominant · mixed · mostly_intracellular</code>.
    </>
  ),
};
