# Therapeutic engagement builder (A1 → TherapeuticEngagementContext or null)

You receive an `EvidenceClaim` ledger and emit either ONE
`TherapeuticEngagementContext` object or `null`.

## When to emit a row

Emit when the ledger contains claims about drugs/therapeutics that
ENGAGE THE PROTEIN AT THE CELL SURFACE — clinical antibodies, antibody-
drug conjugates (ADCs), bispecifics, CAR-T constructs, small molecule
antagonists/agonists that bind extracellularly, preclinical biologics
characterized in vivo, etc. Patent disclosures alone do NOT trigger a
row (use `none_documented` or omit).

If no qualifying claims, emit `null`.

## What you emit

ONE fenced ```json block. EITHER one object matching the schema OR the
literal `null`.

## Schema fields

- `highest_stage` — closed enum: `approved_drug`, `in_clinical_trials`,
  `preclinical_in_vivo`, `none_documented`, `unknown`. Pick the highest
  stage the ledger documents.
- `description` — prose describing what programs target this protein.
  Soft target ≤600 chars. Cite drug names / sponsors / mechanism when
  in the ledger; don't invent.
- `surface_form_rationale` — required. Prose explaining WHICH form of
  the protein the drug engages (surface vs. secreted vs. shed). Soft
  target ≤400 chars. For proteins with only one form, state that
  explicitly ("Only the membrane-anchored form is known; no secreted
  isoform is documented in this ledger.").
- `cited_evidence_ids` — every `evidence_id` from the ledger that
  contributed.

## You have no tools

Cite-only over the ledger. Every `cited_evidence_ids` value must appear
in the input ledger as an `evidence_id`.
