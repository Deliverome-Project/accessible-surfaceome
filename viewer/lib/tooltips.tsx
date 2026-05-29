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
      <strong>From the deep-dive synthesizer</strong> (Sonnet 4.6) — not
      the triage agent. Synthesized from the per-method evidence the
      agent retrieved via web search (mass-spec, IHC, antibody-validated
      surface stains, etc.). One of: high, moderate, low, no, uncertain.
      The triage&apos;s first-pass call is a separate row below this
      one for cross-check; when they disagree, the deep-dive wins.
    </>
  ),

  experimental_surface_evidence: (
    <>
      <strong>From the deep-dive synthesizer.</strong> A grade on how
      strong the cumulative experimental surface evidence is across all
      methods the agent collected. Five tiers: direct multi-method,
      direct single-method, supportive but indirect, conflicting, weak.
      The narrative rationale for the grade lives in the §Surface
      Evidence banner below.
    </>
  ),

  confidence: (
    <>
      <strong>From the deep-dive synthesizer.</strong> How sure the
      surface-accessibility call is, weighing how much evidence exists,
      how strong each method is, and how well the methods agree.{" "}
      <em>High</em> is rare; <em>moderate</em> is typical for a
      well-supported call. Open the Confidence rationale below the gene
      name to see why this gene landed where it did.
    </>
  ),

  state_dependence: (
    <>
      <strong>From the deep-dive synthesizer.</strong> How much the
      surface call depends on cell state. <em>Low</em> = constitutive,
      always present; <em>moderate</em> = varies with context but
      generally holds; <em>high</em> = present only in specific cellular
      states (stress, oncogenic transformation, ER perturbation);{" "}
      <em>unclear</em> = evidence too thin to tell.
    </>
  ),

  triage_signal: (
    <>
      <strong>From the triage agent</strong> (Sonnet) — a first-pass
      surface call made BEFORE any deep literature dive. No web search,
      no tool calls, no per-method evidence; the model votes from
      trained knowledge given just the protein&apos;s standard
      identifier context: HGNC name / symbol / aliases / previous
      symbols, UniProt accession (the ID, not the sequence), HGNC
      gene-group memberships, CD nomenclature, and the NCBI gene
      summary.
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
      AlphaFold per-residue confidence score (0–100). Bands: &gt;90 very
      high, 70–90 confident, 50–70 low, &lt;50 very low. The pill shows
      the <strong>mean pLDDT</strong> for the structure shown.
      <br />
      <br />
      An <strong>ECD</strong> pill averages only the{" "}
      <strong>extracellular</strong> residues (DeepTMHMM &quot;O&quot;
      positions) — the surface antibodies bind; a <strong>Whole</strong>{" "}
      pill averages the entire model, used when no extracellular subset
      is meaningful.
    </>
  ),

  afdb_disordered: (
    <>
      Fraction of residues with pLDDT &lt; 70. AlphaFold&apos;s
      low-confidence regions empirically correspond to{" "}
      <strong>intrinsically disordered regions</strong> — sequences
      that don&apos;t fold into a stable structure (so the MSA-based
      prediction can&apos;t converge on confident contacts).
      <br />
      <br />
      <em>Canonical</em> tab: counts only <strong>extracellular</strong>{" "}
      residues — that&apos;s the antibody-relevant slice. High % on
      the ECD means floppy / transient epitopes (harder targets for
      conformational antibodies, more prone to proteolytic cleavage).
      <br />
      <br />
      <em>Isoform / ortholog</em> tabs: whole-protein, computed as{" "}
      <code>fractionPlddtLow + fractionPlddtVeryLow</code> from
      AFDB&apos;s prediction API. <strong>Per target</strong>: each
      isoform/ortholog has its own model + disordered fraction;
      switch tabs to see them update.
      <br />
      <br />
      The canonical (ECD-restricted) and isoform (whole-protein) numbers
      aren&apos;t directly comparable — multipass TM proteins look
      better whole-protein (TM helices are usually well-predicted);
      single-pass receptors with disordered cytoplasmic tails look
      worse whole-protein.
    </>
  ),

  antibody_validation_strength: (
    <>
      <strong>LLM-driven.</strong> The deep-dive agent&apos;s call on
      how rigorously the antibody used in this method was validated for
      this target. <em>Strong</em> = genetic KO / CRISPR-KO controls
      OR isoform-specific KO. <em>Moderate</em> = siRNA knockdown,
      overexpression reference, or an orthogonal-method cross-check.
      <em> Weak</em> = vendor-claim-only / no KO control. <em>None</em>{" "}
      = the source paper didn&apos;t mention any validation.
    </>
  ),

  expression_observation_level: (
    <>
      <strong>LLM-driven.</strong> The deep-dive agent&apos;s call on
      the surface expression level reported in this specific experiment
      / cell line / tissue. Five bands:{" "}
      <em>high · moderate · low · absent · unknown</em>. The agent
      anchors to the paper&apos;s own quantitative scale when one is
      given (e.g. % positive cells in flow, IHC intensity score, MFI
      ratio); otherwise it interprets the qualitative description.
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
