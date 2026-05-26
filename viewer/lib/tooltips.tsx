import type { ReactNode } from "react";

/**
 * Field-provenance tooltip text — one place to edit, shared across
 * cards. The renderable values (mostly `<>` fragments with inline
 * code / links) are imported by `<InfoTip>` consumers.
 *
 * Two broad classes:
 *
 *   1. **Deterministic** — pulled from a versioned dataset (DeepTMHMM,
 *      AlphaFold DB, Ensembl Compara, SURFACE-Bind, the 5-DB
 *      candidate-universe build). The tooltip names the source +
 *      version.
 *
 *   2. **LLM-derived** — synthesized by the deep-dive agent over the
 *      A2 evidence-claim ledger. The agent retrieves via web search
 *      (not direct API), so the tooltip is honest that the data
 *      ultimately came from whatever HPA / GTEx / literature snippets
 *      surfaced for the planner's queries.
 *
 * Keep the prose under ~3 sentences per tooltip — the popover is small
 * and the reader is hovering, not reading a paper.
 */
export const tooltips: Record<string, ReactNode> = {
  // --------------------------------------------------------------
  // GeneHeader vitals
  // --------------------------------------------------------------

  surface_accessibility: (
    <>
      <strong>LLM-derived.</strong> Synthesizer&apos;s rollup of the per-method{" "}
      <em>MethodObservation</em> blocks in §Surface evidence. Picks one of{" "}
      <code>high · moderate · low · no · uncertain</code>. See{" "}
      <em>surface_call_reason</em> + the cited evidence chips for the
      underlying reasoning.
    </>
  ),

  experimental_surface_evidence: (
    <>
      <strong>LLM-derived.</strong> Five-tier rollup over the per-method
      observations:{" "}
      <code>
        direct_multi_method · direct_single_method · supportive_but_indirect ·
        conflicting · weak
      </code>
      . Reader-facing relabel of <code>evidence_grade_summary</code>.
    </>
  ),

  confidence: (
    <>
      <strong>LLM-derived.</strong> Synthesizer&apos;s self-rating of the
      surface call. Tracks evidence breadth × per-method strength ×
      consistency. <code>high</code> is rare; <code>moderate</code> is the
      default for well-supported calls.
    </>
  ),

  state_dependence: (
    <>
      <strong>LLM-derived.</strong> How much the surface call depends on
      cell state. <code>low</code> = constitutive (always present),{" "}
      <code>moderate</code> = varies with context but generally holds,{" "}
      <code>high</code> = present only in specific states (cancer-only,
      stress-only, EMT-only), <code>unclear</code> = evidence too thin.
    </>
  ),

  triage_signal: (
    <>
      <strong>Sonnet first-pass triage prior</strong> — pre-deep-dive
      sanity check. No web search, no per-method evidence — just
      gene-symbol-keyed heuristics over the cohort. Stored in public D1{" "}
      <code>triage_run_public</code>. When it conflicts with the deep-dive
      verdict, the deep dive wins (it has the evidence).
    </>
  ),

  headline_risks: (
    <>
      <strong>LLM-derived.</strong> Five-value enum (slimmed from 11
      post-redundancy audit):{" "}
      <code>
        shed_form · secreted_form · co_receptor · epitope_masked ·
        isoform_decoy
      </code>
      . Each names a load-bearing risk not easily reconstructed from
      another structured field.
    </>
  ),

  // --------------------------------------------------------------
  // Architecture / family / topology
  // --------------------------------------------------------------

  architecture_chip: (
    <>
      <strong>LLM-derived.</strong> Synthesizer picks how the protein sits
      in the membrane:{" "}
      <code>
        single_pass_T1 · single_pass_T2 · multi_pass · GPCR · GPI_anchored ·
        tetraspanin · other
      </code>
      . Heavily informed by DeepTMHMM topology but the call is the
      agent&apos;s — sometimes overrides topology (e.g. known GPCRs with
      partial predictions).
    </>
  ),

  family_chip: (
    <>
      <strong>LLM-derived.</strong> Aligned with SURFACE-Bind&apos;s four
      functional classes (Balbi et al. 2026 (PMID:{" "}
      <a
        href="https://pubmed.ncbi.nlm.nih.gov/41604262/"
        target="_blank"
        rel="noopener noreferrer"
      >
        41604262
      </a>
      )
      ): <code>receptor · enzyme · transporter · miscellaneous</code>.
      Orthogonal to the Architecture axis (function vs. topology).
    </>
  ),

  topology_pills: (
    <>
      <strong>Deterministic.</strong> DeepTMHMM{" "}
      <code>deeptmhmm-1.0.24</code> per-residue prediction over the
      canonical UniProt sequence. TM helix count + N-term / C-term
      orientation read straight off the topology string.
    </>
  ),

  // --------------------------------------------------------------
  // Structure / SURFACE-Bind
  // --------------------------------------------------------------

  afdb_plddt: (
    <>
      <strong>Deterministic.</strong> Mean per-residue AlphaFold pLDDT
      over extracellular-domain residues (DeepTMHMM &quot;O&quot;
      positions). AlphaFold DB v4. For GLOB / soluble-cytoplasmic
      proteins the label switches to <em>Whole pLDDT</em> (no ECD subset
      meaningful).
    </>
  ),

  surface_bind: (
    <>
      <strong>Deterministic.</strong> MaSIF patch-based targetability
      scoring from the Correia lab (Balbi et al. 2026 (PMID:{" "}
      <a
        href="https://pubmed.ncbi.nlm.nih.gov/41604262/"
        target="_blank"
        rel="noopener noreferrer"
      >
        41604262
      </a>
      )
      ). The chip says whether the UniProt has a row in the published
      SURFACE-Bind table; the §SURFACE-Bind card breaks out per-patch
      scores when present.
    </>
  ),

  cross_species_conservation: (
    <>
      <strong>Deterministic.</strong> Ensembl Compara pairwise
      %-identity over the canonical full-length sequence (mouse · rat ·
      cyno). The §Orthologs card shows the per-species rows + the
      ECD-restricted variant when topology is known.
    </>
  ),

  // --------------------------------------------------------------
  // Other LLM-derived enums (Filters card)
  // --------------------------------------------------------------

  expression_level: (
    <>
      <strong>LLM-derived.</strong> Rolled up from the A2 evidence-claim
      ledger. A2&apos;s planner targets HPA snapshots, GTEx, Tabula
      Sapiens, the Human Cell Atlas, and the published literature — but
      retrieves via Claude + web search, not direct API queries against
      those resources. See §Biology for the per-tissue rows + cited
      evidence.
    </>
  ),

  expression_breadth: (
    <>
      <strong>LLM-derived.</strong> Synthesizer rollup over the per-tissue
      ledger. Four values:{" "}
      <code>pan_tissue · broad · restricted · rare</code>. Same A2
      web-search provenance as <em>expression_level</em>.
    </>
  ),

  surface_specificity: (
    <>
      <strong>LLM-derived.</strong> Whether the protein is dominantly on
      the cell surface or mostly intracellular with some surface
      exposure. <code>surface_dominant · mixed · mostly_intracellular</code>.
    </>
  ),

  // --------------------------------------------------------------
  // DB-presence (deterministic) — kept here for re-use but the
  // gene-page tooltip target is currently off per user request.
  // --------------------------------------------------------------

  db_presence: (
    <>
      <strong>Deterministic.</strong> Per-database surface vote from the
      candidate-universe build. Five sources: UniProt subcellular
      annotation, GO <code>cell_surface</code>, SURFY, CSPA, HPA{" "}
      <em>Cell Atlas — Plasma Membrane</em>. A dot means the database
      independently calls this gene surface.
    </>
  ),
};
