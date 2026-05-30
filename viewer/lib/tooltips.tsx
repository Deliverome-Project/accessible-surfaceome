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

  family_registry_chip: (
    <>
      <strong>Registry ground truth.</strong> Curator-assigned family
      tags resolved deterministically from the identifier bundle (HGNC
      gene group + UniProt SIMILARITY line) — not model output. Shown
      beside the LLM&apos;s Family call so you can cross-check the
      model&apos;s functional class against HGNC / UniProt.
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
      Fraction of residues AlphaFold predicts with low confidence
      (pLDDT &lt; 70) — regions that are typically{" "}
      <strong>intrinsically disordered</strong>, meaning they
      don&apos;t fold into a stable shape. A high fraction over the
      extracellular region flags floppy, transient epitopes: harder
      targets for conformational antibodies and more prone to
      proteolytic cleavage.
      <br />
      <br />
      The canonical figure covers only the extracellular residues;
      isoform and ortholog figures are whole-protein, so the two
      aren&apos;t directly comparable.
    </>
  ),

  experimental_best_structure: (
    <>
      The experimental structure shown is the top hit from PDBe&apos;s{" "}
      <a
        href="https://www.ebi.ac.uk/pdbe/api/doc/sifts.html"
        target="_blank"
        rel="noopener noreferrer"
      >
        <code>best_structures</code>
      </a>{" "}
      ranking for this protein — deposited PDB entries ordered by how
      much of the sequence they resolve (coverage), then by resolution.
      We prefer the human (same-species) entry when one exists and show
      the highest-ranked hit; the chain and residue range come from the
      UniProt-to-PDB mapping in SIFTS (Dana et al. 2019,{" "}
      <a
        href="https://pubmed.ncbi.nlm.nih.gov/30445541/"
        target="_blank"
        rel="noopener noreferrer"
      >
        PMID 30445541
      </a>
      ).
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

  // --------------------------------------------------------------
  // Catalog filter-group headers — explain the two pipeline stages
  // --------------------------------------------------------------

  catalog_triage_group: (
    <>
      <strong>First-pass triage agent</strong> (Sonnet 4.6) — a pure-LLM
      classifier that scores each gene from its standard identifier
      context (HGNC name / aliases, UniProt accession, gene-group
      memberships, CD designation, NCBI summary). No web search, no
      per-paper evidence. Filters here narrow the catalog by the
      triage verdict and the triage reason code.
    </>
  ),

  catalog_deep_dive_group: (
    <>
      <strong>Multi-agent deep-dive pipeline.</strong> Retrieves and
      ranks 20–30 primary sources, parses claims into structured
      blocks via ~10 builders, then reconciles into one record with{" "}
      <code>surface_accessibility</code> + <code>confidence</code> +{" "}
      <code>evidence_grade</code> et al. Only the ~6,000 candidate-
      universe genes have been deep-dived; filters in this group
      apply only to rows where the deep-dive has run.
    </>
  ),

  // Subhead splits inside the Deep Dive group — partitions the 21
  // deep-dive filters into LLM-derived rollups vs deterministic /
  // tool-derived readouts so the reader can tell at a glance which
  // half of the pipeline a filter came from.
  catalog_deep_dive_llm_subhead: (
    <>
      Filters in this section apply to LLM-derived rollups from the
      deep-dive synthesizer — the agent&apos;s own classifications,
      re-emitted from the merged A1+A2 evidence ledger.
    </>
  ),

  catalog_deep_dive_risks_subhead: (
    <>
      Things that can make this protein hard to target even when it
      IS at the surface: a shed or secreted form that competes for
      your binder in circulation, partner proteins or surface glycans
      masking the epitope, or a co-receptor the protein needs to
      reach the surface in the first place. Filtering here narrows
      to genes that carry (or are free of) each risk.
    </>
  ),

  catalog_deep_dive_deterministic_subhead: (
    <>
      Filters in this section apply to deterministic, tool-derived
      readouts — DeepTMHMM topology, ledger-count buckets,
      SURFACE-Bind MaSIF patch scoring. No LLM involvement; values
      are reproducible by re-running the underlying tool.
    </>
  ),

  // Surface-DB votes — neither triage nor deep-dive. From the
  // candidate-universe build: each of the 5 gating databases voted
  // independently on whether this protein is at the surface.
  catalog_databases_group: (
    <>
      <strong>Surface-DB votes</strong> — independent of the agent
      pipeline. From the candidate-universe build, each of 5 gating
      databases (UniProt, GO, SURFY, CSPA, HPA) votes yes/no on
      surface localization under that source&apos;s optimized cutoff.
      AND-semantics: a row passes only when EVERY checked DB voted
      yes (intersection).
    </>
  ),

  // SURFACE-Bind targetability — MaSIF patch-based scoring from
  // the Balbi et al 2026 PNAS paper. Same source the gene-page §SURFACE-
  // Bind card cites.
  catalog_surface_bind_group: (
    <>
      <strong>SURFACE-Bind targetability</strong> — MaSIF patch-based
      scoring for de novo binder design seeds. Source:{" "}
      <a
        href="https://pubmed.ncbi.nlm.nih.gov/41604262/"
        target="_blank"
        rel="noopener noreferrer"
      >
        Balbi et al · 2026 · PMID 41604262
      </a>
      . Filters by how many surface patches cleared MaSIF scoring (≥1
      site, ≥3 sites) or whether the protein was filtered out by
      SURFACE-Bind&apos;s structural QC step.
    </>
  ),

  // --------------------------------------------------------------
  // Catalog deep-dive filter chips — reused FiltersCard tooltips
  // where one exists, plus a few new ones for fields the gene-page
  // FiltersCard renders implicitly. Keep wording in sync with
  // viewer/components/surfaceome/FiltersCard/FiltersCard.tsx
  // TT_* constants so the catalog tooltips and the gene-page
  // tooltips speak the same language.
  // --------------------------------------------------------------

  catalog_has_known_ligand: (
    <>
      Whether a validated endogenous ligand is documented for this
      protein. <strong>Yes</strong> — ligand known in the literature
      (e.g. EGFR&nbsp;←&nbsp;EGF). For kinases like SRC this also
      captures documented substrates / interaction partners, since
      the &ldquo;ligand&rdquo; framing is canonical for receptors but
      loose for cytoplasmic kinases. <strong>No</strong> — orphan:
      ligand identity is genuinely unknown (orphan GPCRs, nuclear
      hormone receptors, true orphan kinases). The specific ligand
      identity isn&apos;t on the catalog row — see the gene
      page&apos;s Biology section for partner / co-receptor evidence.
    </>
  ),

  catalog_low_endogenous_expression: (
    <>
      Whether baseline expression in normal tissues is low or absent.{" "}
      <strong>Yes</strong> — expression level is &ldquo;low&rdquo;
      or &ldquo;absent&rdquo;. These targets typically need
      overexpression-based studies (HEK293 / HeLa / U2OS transfection)
      to characterize surface biology, and antibody validation in
      endogenous tissues is harder because there&apos;s little
      protein to stain in untransfected controls.{" "}
      <strong>No</strong> — present at meaningful levels in at least
      some normal tissues.
    </>
  ),

  catalog_overexpression_precedent: (
    <>
      Whether prior overexpression studies (HEK293 / HeLa / K562 /
      U2OS transfection, stable or transient) have demonstrated this
      protein actually reaches the cell surface.{" "}
      <strong>Yes</strong> — at least one cited method observation
      reports surface localization or direct surface-accessibility
      evidence from an overexpression (or mixed endogenous + OE)
      experiment. Useful precedent when planning an OE-based
      validation campaign — you know the construct can surface in a
      heterologous cell line. <strong>No</strong> — no such
      precedent in the deep-dive ledger. Distinct from the
      orphan-receptor and low-endogenous flags above (those describe
      baseline biology; this one describes prior experimental
      precedent).
    </>
  ),

  catalog_surface_call_reason: (
    <>
      Why this protein is (or isn&apos;t) at the cell surface — the
      mechanism behind the accessibility call. Same 19-value
      taxonomy the first-pass triage uses, so the deep-dive&apos;s
      reason can be compared directly to the triage&apos;s — when
      they disagree, the deep-dive wins. Three families:{" "}
      <strong>YES</strong> — at the surface (classical receptor,
      GPI-anchored, multipass with exposed extracellular loops,
      extracellular face, stable surface-complex partner);{" "}
      <strong>CONTEXTUAL</strong> — at the surface only in certain
      states (induced by cell state, tissue-restricted, lysosomal
      exocytosis, dual localization, stable surface attachment); and{" "}
      <strong>NO</strong> — not at the surface (cytoplasmic; nuclear;
      mitochondrial (matrix or inner-membrane face); endomembrane (ER
      / Golgi / lysosomal / peroxisomal / autophagosomal membrane
      only); nuclear envelope (inner / outer); inner-leaflet
      anchored (lipidated / peripheral on the cytoplasmic face of
      the plasma membrane); secreted-only (no wash-resistant surface
      anchor); pMHC-only (the only &ldquo;surface&rdquo; story is
      MHC-presented peptides)). SRC, for example, is &ldquo;
      <code>lysosomal_exocytosis</code>&rdquo; in its cancer state —
      overriding the baseline &ldquo;
      <code>inner_leaflet_anchored</code>&rdquo;.
    </>
  ),

  catalog_subcategory: (
    <>
      Architecture — how the protein sits in the membrane. Orthogonal
      to the functional family axis; informed by DeepTMHMM topology
      but the deep-dive agent can override.
    </>
  ),

  catalog_llm_family: (
    <>
      Functional family — the model&apos;s high-level call, aligned with
      SURFACE-Bind&apos;s four classes (Balbi et al. 2026,{" "}
      <a
        href="https://pubmed.ncbi.nlm.nih.gov/41604262/"
        target="_blank"
        rel="noopener noreferrer"
      >
        PMID 41604262
      </a>
      ). Function vs. topology — orthogonal to the architecture axis.
    </>
  ),

  catalog_evidence_density: (
    <>
      How <em>much</em> supporting evidence the deep dive found —
      bucketed count of evidence rows the agent pulled and scored:{" "}
      <em>high</em> ≥ 30 supporting rows, <em>moderate</em> ≥ 10,{" "}
      <em>low</em> &lt; 10. Complements the evidence grade up top
      (which tells you how <em>strong</em> the evidence is, not how
      much there is).
    </>
  ),

  catalog_ecd_class: (
    <>
      One antibody footprint ≈ 12 ± 3 residues / 1103 ± 244 Å² buried
      (Ramaraj et al.&nbsp;2012, PMID&nbsp;
      <a
        href="https://pubmed.ncbi.nlm.nih.gov/22246133/"
        target="_blank"
        rel="noopener noreferrer"
      >
        22246133
      </a>
      ). Bands below are our heuristic for how many non-overlapping
      footprints an ECD could host (≈ residues ÷ 12, a loose upper
      bound): <em>large</em> ≥ 200 residues; <em>moderate</em> 60–199;{" "}
      <em>small</em> 30–59; <em>minimal</em> &lt; 30; <em>none</em> = no
      surface-exposed ECD (GPI / inner-leaflet).
    </>
  ),

  catalog_shed_form: (
    <>
      A soluble fragment is proteolytically released into the
      extracellular milieu (sheddase cleavage of the ectodomain),
      creating a circulating decoy that competes with the surface
      form for binder occupancy.
    </>
  ),

  catalog_secreted_form: (
    <>
      An alternative isoform is secreted as free soluble protein
      (not EV-enclosed) — present in the same compartment as the
      surface form and consumes binder.
    </>
  ),

  catalog_epitope_masking: (
    <>
      The targetable surface is shielded — partner heterodimerization,
      glycan shield, or conformational hiding obscures the epitopes a
      binder would otherwise engage.
    </>
  ),

  catalog_n_term_extracellular: (
    <>
      Does the canonical isoform&apos;s N-terminus face the extracellular
      space? True for type I single-pass receptors and most multi-pass
      topologies with extracellular N-loops; false for type II single-
      pass (cytoplasmic N-term).
    </>
  ),

  catalog_c_term_extracellular: (
    <>
      Does the canonical isoform&apos;s C-terminus face the extracellular
      space? Useful when designing C-terminal tag constructs or when
      the antibody campaign targets the C-terminal region.
    </>
  ),
};
