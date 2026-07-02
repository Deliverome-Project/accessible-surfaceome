import * as React from "react";
import type { ReactNode } from "react";
import { CITATIONS, pubmedUrl } from "./citations";
// The `React` import above is load-bearing under render-tests: this
// file lives at `lib/*.tsx`, which the tsconfig `include` glob covers
// with `lib/**/*.ts` (NOT `*.tsx`), so tsx falls back to the classic
// JSX transform when tooltips.tsx is imported outside Next's build.
// Under classic-transform, the module-top JSX fragments below compile
// to `React.createElement(React.Fragment, ...)` and need `React` in
// scope. Next.js's SWC-based build with `jsx: react-jsx` (automatic
// transform) doesn't need it — this import is a no-op there.
void React;

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
      The deep-dive&apos;s <strong>surface likelihood</strong> — does this
      protein reach the cell surface in at least one cell state? The
      levels are <strong>evidence strength for the surfaces-at-all
      call</strong>, not a steady-state magnitude. (Wire/storage name
      is still <code>surface_accessibility</code> for API consumers; the
      UI label evolved from &ldquo;Accessibility&rdquo; → &ldquo;Surface
      verdict&rdquo; → &ldquo;Surface likelihood&rdquo; because
      &ldquo;Accessibility&rdquo; read as a magnitude axis and
      &ldquo;Verdict&rdquo; overstated a call that&apos;s really a
      likelihood distribution over yes / contextual / no.)
      <ul style={{ margin: "0.4rem 0 0", paddingLeft: "1.1rem" }}>
        <li>
          <em>high</em> — direct evidence (live-cell flow, surface
          biotinylation, KO-controlled IHC); multi-method, or
          single-method + high confidence.
        </li>
        <li>
          <em>moderate</em> — direct single-method with limited
          confidence, or only supportive / indirect.
        </li>
        <li>
          <em>low</em> — weak or conflicting; can&apos;t rule in or
          out.
        </li>
        <li>
          <em>no</em> — confident negative: literature contradicts, or
          canonical cytoplasmic / mitochondrial / nuclear
          localization is multi-method corroborated.
        </li>
        <li>
          <em>uncertain</em> — neither direction has enough evidence.
        </li>
      </ul>
      <strong>Not the same as steady-state surface fraction.</strong>{" "}
      CD63 reads <em>high</em> + <em>state_dependence=high</em> + a
      primarily lysosomal localization — it surfaces (well-evidenced),
      but only on degranulation, and most of the pool sits in
      lysosomes. For &ldquo;how much sits at the surface at baseline?&rdquo;
      use <em>surface_specificity</em> (<em>surface_dominant</em> /{" "}
      <em>mixed</em> / <em>mostly_intracellular</em>) and{" "}
      <em>primary_compartment</em>.
      <br />
      <br />
      Deep-dive synthesizer (Sonnet 4.6).
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
      <strong>Triage call.</strong> A fast first-pass surface verdict
      (yes / contextual / no) from a Sonnet agent, made before any
      deep-dive literature search. Click a row for per-model detail.
    </>
  ),

  benchmark_truth: (
    <>
      <strong>Benchmark truth.</strong> This gene is in{" "}
      <a href="/benchmark">SurfaceBench</a>, the 147-protein hand-curated
      triage benchmark — so it carries a curated ground-truth surface verdict
      (yes / contextual / no). It&apos;s the reference the model calls are
      scored against, which is why it sits above the triage row.
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
          the protein&apos;s own homo-oligomerization, glycan shield, or
          conformational hiding). Severity + evidence
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
        href={pubmedUrl(CITATIONS.surfaceBind.pmid)}
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
      The experimental structure shown is drawn from PDBe&apos;s{" "}
      <a
        href="https://www.ebi.ac.uk/pdbe/api/doc/sifts.html"
        target="_blank"
        rel="noopener noreferrer"
      >
        <code>best_structures</code>
      </a>{" "}
      ranking for this protein — deposited PDB entries ordered by how
      much of the sequence they resolve (coverage), then by resolution.
      We prefer the human (same-species) entry when one exists. If the
      top hit maps to the protein in fragments (a fusion or engineered
      construct), we skip to the next structure of comparable coverage
      and resolution that maps as one clean segment; only when no such
      alternative exists do we keep the fragmented one and flag the
      coloring as approximate. The chain and residue range come from the
      UniProt-to-PDB mapping in SIFTS (Dana et al. 2019,{" "}
      <a
        href="https://pubmed.ncbi.nlm.nih.gov/30445541/"
        target="_blank"
        rel="noopener noreferrer"
      >
        PMID 30445541
      </a>
      ). Topology coloring is projected onto the deposited file&apos;s
      author residue numbering and validated against the residues
      actually present in that file, so it lands correctly even when the
      author numbering differs from the UniProt sequence position.
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

  expression_system: (
    <>
      <strong>LLM-driven.</strong> Whether this assay measured the protein
      at its native level (<em>endogenous</em>) or after forcing extra
      copies (<em>overexpression</em>). Endogenous detection is the
      stronger surface-accessibility signal; overexpression can push a
      protein to the surface where it wouldn&apos;t normally go.{" "}
      <strong>Mixed</strong> = this block pools both endogenous and
      overexpression findings, so read it as partly caveated.{" "}
      <strong>Knock-in tag</strong> = an endogenous-level tagged copy
      (strong, like endogenous).
    </>
  ),

  surface_bind: (
    <>
      MaSIF patch-based targetability scoring from the Correia lab
      (Balbi et al. 2026, PMID:{" "}
      <a
        href={pubmedUrl(CITATIONS.surfaceBind.pmid)}
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

  // Canonical ortholog / paralog tooltip bodies. Single source of truth:
  // rendered both in the §07 Isoforms·orthologs·paralogs card (subhead
  // InfoTips) AND the deterministic-summary FiltersCard (StatusPill
  // tooltips + group tips), so the cutoff bands + citations can't drift
  // between the two surfaces. Edit here only.
  ortholog_species_relevance: (
    <>
      Mouse / cyno identity to the human canonical, over the ECD. Triage
      signal, not a verdict — relevance also needs binding, expression, and
      function (ICH S6(R1)).
      <br />
      ≥85% high · 60–85% intermediate · &lt;60% higher-risk.
      <br />
      High identity ≠ conserved epitope.
    </>
  ),

  paralog_specificity: (
    <>
      Identity to the nearest human paralog, over the ECD — local epitope
      similarity matters more than global identity. Per HPA antigen-design
      practice (PMID{" "}
      <a
        href={pubmedUrl(CITATIONS.hpaAntigenDesign.pmid)}
        target="_blank"
        rel="noopener noreferrer"
      >
        {CITATIONS.hpaAntigenDesign.pmid}
      </a>
      ): ≤60% (usually &lt;40%) single-target achievable; &gt;80% defines a
      multitargeting antibody expected to bind the family.
      <br />
      &lt;60% lower risk · 60–80% caution · &gt;80% multitarget likely.
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
      your binder in circulation, partner proteins, the protein&apos;s
      own homo-oligomerization, or surface glycans masking the epitope,
      or a co-receptor the protein needs to reach the surface in the
      first place. Filtering here narrows to genes that carry (or are
      free of) each risk.
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
        href={pubmedUrl(CITATIONS.surfaceBind.pmid)}
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
        href={pubmedUrl(CITATIONS.surfaceBind.pmid)}
        target="_blank"
        rel="noopener noreferrer"
      >
        PMID 41604262
      </a>
      ). Function vs. topology — orthogonal to the architecture axis.
    </>
  ),

  catalog_primary_compartment: (
    <>
      Primary subcellular compartment — where the deep-dive agent places
      the protein&apos;s dominant steady-state pool. A coarse 10-class
      readout (<em>plasma_membrane</em>, <em>endosome</em>, <em>lysosome</em>,
      etc.) from <code>biological_context.subcellular_localization.primary_compartment</code>;
      reconciled across the merged evidence ledger and reflects the
      majority steady-state localization, not every pool the protein
      visits. Use alongside the &ldquo;Surface call&rdquo; group to find
      e.g. lysosome-resident proteins with cell-state-induced surface
      access.
    </>
  ),

  catalog_restricted_subdomain_kind: (
    <>
      <strong>Kind</strong> of polarized localization when the protein
      is restricted to a specific membrane subdomain — apical,
      junctional, ciliary, synaptic, lipid-raft, basolateral, or other.
      Sourced from <code>accessibility_risks.restricted_subdomain.domain</code>{" "}
      and only populated when <em>has_restricted_subdomain</em> is true,
      so the filter scopes to the genes where domain restriction is
      actually relevant (e.g. find all ciliary-restricted GPCRs).
    </>
  ),

  catalog_surface_bind_targetability: (
    <>
      4-way targetability bucket from{" "}
      <strong>SURFACE-Bind</strong> (Balbi et al. 2026,{" "}
      <a
        href={pubmedUrl(CITATIONS.surfaceBind.pmid)}
        target="_blank"
        rel="noopener noreferrer"
      >
        PMID {CITATIONS.surfaceBind.pmid}
      </a>
      ), based on the per-protein count of MaSIF-scored targetable
      patches on the AF2 structure:
      <ul style={{ margin: "0.4rem 0 0", paddingLeft: "1.1rem" }}>
        <li>
          <em>high</em> — ≥3 scored patches (rich epitope landscape)
        </li>
        <li>
          <em>moderate</em> — 1-2 scored patches
        </li>
        <li>
          <em>none</em> — in the SURFACE-Bind dataset but 0 patches
          cleared the targetability threshold (rare; e.g. GPR75)
        </li>
        <li>
          <em>not_scored</em> — protein omitted from SURFACE-Bind&apos;s{" "}
          <code>results_no_TM.csv</code> (~12% of surfaceome
          proteins). Different from &ldquo;none&rdquo;: no claim
          either way.
        </li>
      </ul>
      Pure structural prior; identical MaSIF run on the same AF2 model
      gives the same value — true <em>deterministic</em> filter.
    </>
  ),

  catalog_surface_bind_main_class: (
    <>
      SURFACE-Bind&apos;s native family axis — Receptors, Enzymes,
      Transporters, or Miscellaneous (Balbi et al. 2026,{" "}
      <a
        href={pubmedUrl(CITATIONS.surfaceBind.pmid)}
        target="_blank"
        rel="noopener noreferrer"
      >
        PMID {CITATIONS.surfaceBind.pmid}
      </a>
      ). Same four categories the LLM&apos;s <em>llm_family</em> rollup
      is curated against — when the two diverge, the deep-dive saw
      cell-biology evidence that overrode the structural prior. Useful
      for auditing model disagreement. Only populated when the protein
      is in the SURFACE-Bind dataset (<em>has_data=true</em>).
    </>
  ),

  catalog_is_homo_oligomer: (
    <>
      Schweke 2024 AF2 homo-oligomer prediction (PMID{" "}
      <a
        href="https://pubmed.ncbi.nlm.nih.gov/38325366/"
        target="_blank"
        rel="noopener noreferrer"
      >
        38325366
      </a>
      ). When <em>true</em>, the protein is in the predicted homomer
      refset (~1,049 surfaceome proteins). When <em>false</em>, the
      protein is <strong>not in the positive set</strong> — this is
      NOT &ldquo;AF2 explicitly disagrees&rdquo;; the atlas is
      positives-only. Known dimers like EGFR and INSR are missing per
      the Pydantic docstring, so treat <em>false</em> as a lower bound.
      Useful as a structural prior for filtering homo-oligomerization
      epitope-masking risk.
    </>
  ),

  catalog_secreted_form_source: (
    <>
      How the soluble (non-membrane-anchored) form of the protein is
      generated:
      <ul style={{ margin: "0.4rem 0 0", paddingLeft: "1.1rem" }}>
        <li>
          <em>alternative_splicing</em> — a TM-less isoform is encoded
          by alternative splicing (covers e.g. soluble FAS, sIL6R, the
          decoy IL1R2 isoform).
        </li>
        <li>
          <em>proteolytic</em> — sheddase / convertase cleavage of the
          membrane form releases the extracellular domain.
        </li>
        <li>
          <em>both</em> — both routes contribute meaningfully.
        </li>
        <li>
          <em>unknown</em> — the form is documented as soluble but the
          biogenesis isn&apos;t resolved in the evidence.
        </li>
      </ul>
      Sourced from <code>accessibility_risks.secreted_form.source</code>{" "}
      and only populated when <em>has_secreted_form</em> is true, so the
      filter scopes to genes where a soluble form actually exists. Useful
      to stratify decoy / shedding risk — proteolytic-shed targets force
      a different campaign than splice-isoform decoys.
    </>
  ),

  catalog_evidence_density: (
    <>
      How <em>much</em> supporting evidence the deep dive found —
      bucketed count of evidence rows the agent pulled and scored:{" "}
      <em>high</em> ≥ 30 supporting rows, <em>moderate</em> ≥ 10,{" "}
      <em>low</em> &lt; 10. Complements the evidence grade up top
      (which tells you how <em>strong</em> the evidence is, not how
      much there is). <em>Note:</em> for the "is this gene
      understudied?" question, prefer the{" "}
      <em>Papers selected</em> filter — it counts unique papers
      rather than citation rows (one paper can produce many rows).
    </>
  ),

  catalog_n_papers_selected: (
    <>
      Unique-paper count behind the gene's evidence list — the agent's
      literature pipeline discovered a candidate corpus, then{" "}
      <em>selected</em> a subset for full-text reading and claim
      extraction. This count is{" "}
      <code>len(unique pmids in evidence rows)</code>, banded against
      the live deep-dive cohort:{" "}
      <em>low</em> ≤ p10, <em>moderate</em> p10–p90, <em>high</em> ≥
      p90. Best signal for "is this gene's surface biology
      well-studied?" — a low value points to an understudied target
      that may be worth deeper investigation. Cohort cutoffs are
      recomputed at catalog-build time, so the bands shift as more
      genes get deep-dived. <em>Note:</em> "low" can also mean the
      agent's selection step was aggressive — check the{" "}
      <em>Papers found</em> count alongside it for the pre-selection
      corpus size.
    </>
  ),

  catalog_ecd_class: (
    <>
      One antibody footprint ≈ 12 ± 3 residues / 1103 ± 244 Å² buried
      (Ramaraj et al.&nbsp;2012, PMID&nbsp;
      <a
        href={pubmedUrl(CITATIONS.antibodyInterface.pmid)}
        target="_blank"
        rel="noopener noreferrer"
      >
        {CITATIONS.antibodyInterface.pmid}
      </a>
      ). Bands below are our heuristic for how many non-overlapping
      footprints an ECD could host (≈ residues ÷ 12, a loose upper
      bound): <em>large</em> ≥ 200 residues (≥10 non-overlapping epitopes
      possible); <em>moderate</em> 60–199 (multiple epitopes, e.g.
      tetraspanin EC2 loops); <em>small</em> 30–59 (2–5 candidate
      epitopes, harder discovery); <em>minimal</em> &lt; 30 (1–2 epitopes
      max, specialized formats needed); <em>none</em> = no surface-exposed
      ECD (GPI / inner-leaflet).
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
      the protein&apos;s own homo-oligomerization, glycan shield, or
      conformational hiding obscures the epitopes a binder would
      otherwise engage.
    </>
  ),

  catalog_restricted_subdomain: (
    <>
      The surface pool is confined to a restricted membrane subdomain
      (e.g. apical vs basolateral, or a tight-junction&ndash;bounded face),
      so part of it sits in a compartment a systemically delivered binder
      can&apos;t reach.
    </>
  ),

  catalog_cyno_ecd: (
    <>
      Cynomolgus ortholog extracellular-domain %identity to the human
      canonical, banded from the Ensembl Compara ECD alignment. High
      (&ge;90%) means a human-targeting binder likely cross-reacts with the
      cyno ortholog &mdash; enabling the same molecule for preclinical
      toxicology without a surrogate.
    </>
  ),

  catalog_mouse_ecd: (
    <>
      Mouse ortholog extracellular-domain %identity to the human canonical,
      banded from the Ensembl Compara ECD alignment. High (&ge;90%) supports
      a single surrogate-free binder for mouse efficacy models.
    </>
  ),

  catalog_paralog_ecd: (
    <>
      Highest extracellular-domain %identity to any human paralog, banded
      from the Ensembl Compara ECD alignment. High (&ge;70%) flags off-target
      cross-reactivity risk &mdash; a binder raised against this protein may
      also engage the paralog.
    </>
  ),

  catalog_tumor_associated: (
    <>
      Detected in a tumor / tumor-adjacent tissue context at a non-absent
      protein level (from the biology block&apos;s tissue rows). A quick
      oncology-target triage filter &mdash; orthogonal to expression
      breadth, which doesn&apos;t distinguish tumor from normal context.
    </>
  ),

  catalog_induction_trigger: (
    <>
      The dominant stimulus that surfaces the protein, bucketed across the
      documented accessibility-modulation rows (oncogenic transformation,
      immune activation, stress/hypoxia, cell death, infection).
      Complements the surface-call reason, which names the trafficking
      mechanism rather than the trigger.
    </>
  ),

  catalog_live_cell_evidence: (
    <>
      At least one method shows DIRECT surface accessibility on live/intact
      cells in an endogenous context &mdash; live-cell flow cytometry,
      surface biotinylation, or proximity labeling (not permeabilizable
      IF/IHC). Filters by evidence modality, not just the rolled-up grade.
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
