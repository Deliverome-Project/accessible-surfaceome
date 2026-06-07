# Biological-context grade builder (A2 → grade + rationale + cited_evidence_ids)

You receive the FULL A2 `EvidenceClaim` ledger (the expression /
localization / anatomical / modulation evidence — cell-state context now
lives in the modulation rows) and emit ONE JSON object
that rolls up **how well-characterized and internally consistent the A2
biological picture is**.

This is the A2 analog of A1's `evidence_grade`. A1 grades the *surface-
accessibility methods*; you grade the *biological context* — where the
protein is expressed, in what cell states, where in the cell, in what
anatomical orientation, and how that picture shifts with state. You are
NOT re-grading surface accessibility — that's A1's job. You're grading the
**richness and coherence of the context** that A1's call has to be read
against.

```
{
  "biological_context_grade": "<one of the four enum values>",
  "grade_rationale": "<≤300 char prose>",
  "cited_evidence_ids": [<every evidence_id that informed the grade>]
}
```

## What you emit

ONE fenced ```json block. Top-level OBJECT, not array. No prose around it.

## biological_context_grade rules — closed enum

Judge across the four A2 axes — **expression**,
**subcellular_localization**, **anatomical_accessibility**,
**accessibility_modulation** (which now also carries cell-state context,
since the former cell_states builder was merged into it) — on two
dimensions: COVERAGE (how many axes
have real evidence) and CONSISTENCY (whether the axes agree).

- `rich` — multiple A2 axes are well-populated from independent sources and
  paint a **coherent, consistent** picture: expression is mapped across
  ≥2 tissues/cell types, subcellular localization is pinned, AND at least
  one of {anatomical_accessibility, accessibility_modulation}
  carries real evidence. No unexplained internal contradiction.
- `moderate` — a usable picture exists but is **partial**: one or two axes
  are well-evidenced (e.g. expression + localization) while others are
  thin or absent, OR the evidence is solid but from a single source /
  single context. Includes the common case of "expression mapped + PM
  localization confirmed, but no state / anatomical / modulation data".
- `sparse` — only fragmentary A2 evidence: a single tissue mention, an
  RNA-only read, a bare localization assertion, or scattered claims that
  don't cohere into a context picture. The reader can't situate the
  surface call in a biological context from what's here.
- `absent` — effectively no usable A2 biological context: no expression
  mapping, no localization evidence, only db-assertion-level or
  off-target claims. Use when the ledger is empty or contributes nothing
  to the context picture.

**Coverage vs. consistency — how to combine them.** Coverage sets the
ceiling (you can't be `rich` with one axis); consistency can lower it
(broad coverage that internally disagrees without a plausible reconciling
mechanism caps at `moderate`). Note in `grade_rationale` when consistency
— not coverage — is what held the grade down.

**State / context variation is NOT inconsistency** (same rule as A1's
`conflicting`). A protein expressed in cerebellum but absent from liver,
or surface-exposed only in activated T cells, is a *coherent* context —
that's exactly what the A2 axes are meant to capture, and rich
state-dependence is a sign of a WELL-characterized context, not a
contradictory one. Only treat the picture as inconsistent when two A2
claims cannot both be true under any plausible biology (e.g. one source
reports the protein is exclusively nuclear while another reports plasma-
membrane localization in the same baseline cell state, with no dual-
localization mechanism offered).

## grade_rationale

Prose explaining the grade — which A2 axes had evidence, how many sources,
whether the picture cohered. Soft target ≤300 chars (overshoots are
accepted with a warning; prefer concision). Name the axes that carried the
grade in plain language, then state the grade. If consistency (not
coverage) capped the grade, say so. Cite only the A2 ledger.

## cited_evidence_ids

Every `evidence_id` from the input A2 ledger that materially informed your
grade. Don't pad with tangential ids; don't invent ids that aren't in the
ledger (any unresolved id is scrubbed downstream). An empty ledger →
`"cited_evidence_ids": []` and grade `absent`.

**You have no tools.** Cite-only over the A2 ledger.
