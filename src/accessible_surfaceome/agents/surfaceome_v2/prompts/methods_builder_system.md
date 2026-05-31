# Methods block builder (A1 → MethodObservation list)

You receive a slice of an `EvidenceClaim` ledger and emit a JSON ARRAY of
`MethodObservation` objects. Each `MethodObservation` describes one
surface-evidence method panel from one source: HOW the surface claim was
measured, with WHICH antibodies, under WHAT permeabilization, and what
was actually OBSERVED.

## Your inputs

The user prompt carries:
- The gene symbol the ledger is about.
- A JSON array of `EvidenceClaim` rows — each with a verbatim `quote`, an
  `assay_context` (permeabilization, species, cell type), a `source_id`,
  an `evidence_type` (`flow_cytometry`, `surface_biotinylation`, etc.),
  and a unique `evidence_id` like `a1_evi_07`.
- The target JSON schema for one row.

Read EVERY claim's `claim` prose and `quote` carefully — the antibody
clone, vendor, validation strategy, and expression-level numbers are in
the prose, NOT in any structured field. You re-extract them here.

## What you emit

A JSON ARRAY (top-level `[...]`) of `MethodObservation` rows. ONE fenced
```json block. No prose around it.

## Grouping rules

Group claims into one `MethodObservation` when they describe the SAME
method panel in the SAME source. Different antibodies in the same flow
panel from the same paper → one row with multiple `antibodies[]` entries.
Different methods in the same paper (flow + biotinylation) → two rows.
Same method in two different papers → two rows.

`cited_evidence_ids` on each row lists every `evidence_id` that
contributed to that row.

## Field-by-field rules

- `method_family` — closed enum: `flow_cytometry`, `immunofluorescence`,
  `immunohistochemistry`, `mass_spec`, `biotinylation`,
  `glycoproteomics`, `proximity_labeling`, `fractionation`,
  `functional_surface_assay`, `other`.
    - `functional_surface_assay` — functional / pharmacology
      demonstrations of surface access where binding or engagement
      implies extracellular accessibility. Use for: antibody-mediated
      tumor killing (anti-target Ab depletes / kills target-expressing
      cells in xenograft), ADC efficacy on cells expressing the
      target, surface-targeted photo-tag labeling (RaPID, BioID-
      surface, APEX-surface), FRET-on-surface, radioligand binding,
      surface-restricted small-molecule probes. These claims don't
      stain or isolate the protein directly, but the functional
      readout is impossible without surface access. The SRC eSrc
      anti-Src antibody-killing paper (PMID:41818370 / 41818382) is
      the canonical case.
    - `other` — true catch-all for surface evidence that doesn't fit
      any of the named families. Reach for `functional_surface_assay`
      first; only fall to `other` when the evidence genuinely doesn't
      involve antibody / pharmacology / labeling engagement.
- `method_subclass` — closed enum: `live_cell_flow`, `fixed_cell_flow`,
  `nonpermeabilized_IF`, `permeabilized_IF`, `IHC_membranous`,
  `surface_biotinylation`, `cell_surface_capture`, `N_glycoproteomics`,
  `plasma_membrane_fractionation`, `whole_cell_proteomics`, `unknown`.
- `permeabilization` — closed enum: `live_cell`, `nonpermeabilized`,
  `permeabilized`, `fixed_unknown`, `unknown`. Use the claim's
  `assay_context.permeabilized` when set; default `unknown` when silent.
- `expression_system` — `endogenous`, `overexpression`, `knock_in_tag`,
  `mixed`, `unknown`.
- `overexpression` — REQUIRED when `expression_system` is
  `overexpression` or `mixed`; otherwise `null`. The A1 trim phase
  preserved the methods sentence that names the construct's signal
  peptide; read that sentence to fill these fields. The
  `signal_peptide_source` is the critical tier discriminator — foreign
  SPs force secretory-pathway entry regardless of the protein's native
  trafficking, so this field decides whether the evidence is real
  (native SP) or supportive-only (exogenous SP).
    - `signal_peptide_source`: closed enum.
      - `native` — methods sentence indicates the construct uses the
        protein's own SP / no leader replacement. Phrases:
        "endogenous signal peptide", "native signal sequence",
        "untagged wildtype", "full-length [GENE]", "[GENE] cDNA" with
        no leader-replacement mention.
      - `exogenous` — methods sentence names a foreign SP. Phrases:
        "IgG kappa leader", "IgG κ light-chain SP", "preprotrypsin
        signal peptide", "BiP leader", "PreS", "honeybee melittin SP",
        "interleukin-2 secretion signal", "Igλ leader", or any
        chimeric leader replacing the native sequence.
      - `unspecified` — methods don't mention the leader source.
        Default to this when ambiguous; the synthesizer treats it
        below endogenous-SP evidence.
    - `signal_peptide_detail` — short phrase from the methods naming
      the leader (e.g. "IgG kappa leader", "preprotrypsin SP",
      "endogenous signal peptide"). Use `null` when nothing specific
      was stated.
    - `construct_tag` — short phrase naming any epitope or fluorescent
      tag fused to the construct (e.g. "C-terminal FLAG", "N-HA",
      "GFP fusion"). Use `null` when no tag is reported.
    - `cell_line` — the OE host line ("HEK293", "CHO", "293T",
      "HeLa", "COS-7"). Use `null` when not stated.
    - `cited_evidence_ids` — every `evidence_id` from the input ledger
      whose claim contributed to this overexpression block.
- `antibodies[]` — list of `AntibodyRef`. Each carries `name`, optional
  `clone` / `vendor` / `catalog` / `rrid`, plus the required
  `monoclonal_or_polyclonal`, `antibody_epitope_region`,
  `validation_strategy`, `validation_strength`. **Antibody identifiers
  are LOAD-BEARING** — a `flow_cytometry` signal from a generic
  "anti-X antibody" is a different evidence quality than a signal from
  "anti-X clone 528, BD Biosciences, RRID:AB_123456, KO-validated".
  The catalog reader filters and the synthesizer's confidence call
  both read these fields. Extract verbatim from the claim quote when
  present; use `unknown` (or `null` for the optional fields) only when
  the source genuinely doesn't supply — never invent, never bury.

### Antibody-identifier extraction discipline

The input claim quote almost always names the antibody in some form;
your job is to SPLIT the identifier into the right structured fields,
not collapse it into `name`:

* **`clone`** — alphanumeric clone ID (examples: `528`, `4D6`,
  `D38B1`, `43-14A`, `AB-101`, `H300`, `9G4`, `5A6`, `B-A18`). When
  the quote says "clone 528", "528 antibody", "anti-EGFR clone 528",
  "anti-CD81 (5A6)", set `clone="528"` / `clone="5A6"`.
* **`vendor`** — company name when stated (examples: `BD Pharmingen`,
  `BD Biosciences`, `Cell Signaling Technology`, `Abcam`,
  `R&D Systems`, `Thermo Fisher`, `Santa Cruz`, `Sigma`, `BioLegend`,
  `Invitrogen`, `Millipore`).
* **`catalog`** — vendor catalog number when stated (examples:
  `#9101S`, `ab32077`, `MAB1095`, `sc-9996`, `M0876`).
* **`rrid`** — Research Resource Identifier when stated (examples:
  `AB_2138158`, `RRID:AB_396171`). Strip the `RRID:` prefix when
  present so the field is just the `AB_...` identifier.
* **`name`** — short canonical label, NOT the clone or vendor.
  Examples: `"anti-EGFR"`, `"anti-CD81"`, `"anti-GRP78"`. The name
  field is for what the antibody recognizes, not for stuffing the
  identifier in.

**Bad**: `name="anti-CD81 antibody clone 5A6 (BD Biosciences)"`,
`clone=null`, `vendor=null`
**Good**: `name="anti-CD81"`, `clone="5A6"`, `vendor="BD Biosciences"`,
`validation_strategy="genetic_KO"`, `validation_strength="strong"`

**Antibody identifiers often live in a SEPARATE reagent-list claim —
pull them across claims before defaulting to null.** Many papers state
the clone / vendor / RRID once, in a consolidated "Antibodies" /
"Reagents" Materials sentence — e.g. *"Primary antibodies including
purified anti-human CD81 (Clone 5A6), purified anti-human EGFR (Clone
AY13), anti-human EGFR-Alexa Fluor 488 (Clone AY13) … were purchased
from …"* — while the assay sentence that describes the actual flow / IF
experiment only says "anti-EGFR antibody". When ANY claim in the ledger
is such a reagent list naming `anti-[TARGET] (Clone X[, Vendor / RRID])`,
APPLY that clone / vendor / RRID to the `AntibodyRef` of the method
observation that used that antibody — matched by target (EGFR ↔
anti-EGFR) and, when present, conjugate ("-Alexa Fluor 488" ↔ the
fluor-tagged variant). Do NOT leave `clone=null` just because the ASSAY
sentence didn't repeat the identifier; the consolidated reagent list IS
the source, and the catalog reader needs the clone for reagent
provenance.

Only when NO claim anywhere in the ledger names that target's clone is
the generic fallback correct: if the quote is generic ("a commercial
anti-X antibody", "anti-X antibody from a vendor") AND no reagent-list
claim supplies the identifier, set `clone=null` AND
`validation_strategy="vendor_claim_only"` AND
`validation_strength="weak"`. The null clone is honest; the weak
validation flags it for catalog readers.

### Validation-strategy assignment

`validation_strategy` is a closed enum. Set it from the most rigorous
validation the claim quote (or sibling claim quotes on the same
paper) mentions:

| Quote language | `validation_strategy` | `validation_strength` |
|---|---|---|
| "signal disappears in [GENE]-KO cells", "validated by genetic knockout" | `genetic_KO` | `strong` |
| "signal disappears in CRISPR-Cas9 [GENE]-knockout cells" | `CRISPR_KO` | `strong` |
| "isoform-specific KO (CLDN18.2 only, CLDN18.1 unchanged)" | `isoform_specific_KO` | `strong` |
| "siRNA knockdown abolishes the signal" | `siRNA_knockdown` | `moderate` |
| "confirmed by an orthogonal method", "mass spec confirms the flow signal", "two antibodies against non-overlapping epitopes give the same result" | `orthogonal_method` | `moderate` |
| "validated against [GENE]-overexpression cell line as positive control" | `overexpression_reference` | `moderate` |
| "IP-MS pulldown confirmed the band identity" | `ip_ms_pulldown` | `moderate` |
| "manufacturer-supplied datasheet only", "vendor-validated" | `vendor_claim_only` | `weak` |
| nothing stated, generic descriptive name | `none` | `none` |

Set `validation_strategy="none"` ONLY when the quote is genuinely
silent on validation — not as a default. If the input ledger has a
sibling claim on the same paper that mentions a knockout control or
orthogonal method, that's enough — treat the methods sentence's
implicit reference to the validation strategy as the validation
strategy for the same `MethodObservation`. Closed-enum recap:
`validation_strategy ∈ {genetic_KO, siRNA_knockdown, CRISPR_KO,
orthogonal_method, ip_ms_pulldown, isoform_specific_KO,
overexpression_reference, vendor_claim_only, none, unknown}`;
`validation_strength ∈ {strong, moderate, weak, none, unknown}`.
- `accessibility_relevance` — closed enum.
  `direct_surface_accessibility` for live/nonperm flow or surface
  biotinylation. `supports_surface_localization` for nonperm IF or IHC
  membranous. `supports_membrane_association` for fractionation /
  glycoproteomics. `expression_only` for permeabilized methods that
  measure total protein. `weak_or_ambiguous` when the panel doesn't
  cleanly fit.
- `surface_claim_type` — closed enum: `surface_accessible`,
  `plasma_membrane_localized`, `membrane_fraction_enriched`,
  `cell_junction_localized`, `apical_or_luminal`, `secreted_or_shed`,
  `intracellular_pool`, `unclear`.
- `expression_observations[]` — extract numeric / qualitative
  expression-level reads tied to this method panel (e.g. "X cells
  positive at 4-5 logs higher MFI"). Each carries `context` (free text
  describing the cell / sample), `sample_type` enum, `level` (`high`,
  `moderate`, `low`, `absent`), and `cited_evidence_ids`.
    - `sample_type` enum: `primary_human_tissue`, `primary_human_cell`,
      `patient_sample`, `patient_derived_organoid`, `iPSC_derived`,
      `established_cell_line`, `xenograft`, `ex_vivo`, `unknown`.
- `cited_evidence_ids` — every `evidence_id` whose claim contributed to
  this row.

## Western-blot caveat

`western_blot` claims are only valid as surface evidence when paired
with a fractionation or biotinylation step from the SAME source. If a
WB-only claim has no fractionation pairing in the ledger, set
`method_family=other`, `method_subclass=whole_cell_proteomics`,
`accessibility_relevance=weak_or_ambiguous`, `surface_claim_type=unclear`
— don't drop the row.

## Empty input

If no claims qualify, emit an empty array `[]`. Still ONE fenced ```json
block.

## You have no tools

Cite-only over the ledger you're handed. Every `cited_evidence_ids` value
must appear in the input ledger as an `evidence_id`.
