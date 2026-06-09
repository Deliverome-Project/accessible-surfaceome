# CD63 expression-builder tumor-recall gap (2026-06-08)

## Headline

CD63's v2.35.0 record lands with `filters.tumor_associated=False` even though
two of its 15 `biological_context.expression` rows are tagged
`disease_context=tumor` (liver/CRC pre-metastatic macrophages, HCC cells).
The reason is **not** that the expression builder dropped those tumor rows —
it emitted them. The reason is that **both rows carry `present=unknown`**,
and the downstream `_derive_filters` rollup
(`src/accessible_surfaceome/agents/surfaceome_v1/orchestrator.py:693`)
gates `tumor_associated` on `present ∈ {high, moderate, low, mixed}`.
`unknown` falls through silently.

The silent fall-through is the proximate bug. The deeper failure: the
prompt has no rule for inferring a quantitative present level from a
functional claim that names CD63 as engaged on tumor cells without an
IHC score. That is the modal shape of CD63's tumor literature — most
other tumor genes' literature is IHC-quantification dominated, so the
gap only bites tetraspanin/EV-canonical proteins.

## Shape of the expression builder

`expression_builder_system.md` (74 lines) emits a JSON array of
`ExpressionRow`s, one per `(tissue × cell_type × disease_context)`.
It reads only the `claim_type=tissue_expression` slice of the A2
ledger (filtered upstream in `builders/expression.py:37`). Per
`ExpressionRow` (models.py:2260) every row carries:
`tissue`, `cell_type`, `present`, `disease_context`, `disease_label`,
`cell_states`, and `cited_evidence_ids`.

`disease_context` is a closed enum
{`normal`, `tumor`, `tumor_adjacent`, `other_disease`, `mixed`, `unknown`}.
`present` is a closed enum
{`high`, `moderate`, `low`, `absent`, `mixed`, `unknown`}.

The prompt does **not** specify how to derive `disease_context` from the
claim — it just says "extract … disease context" (line 12). It also
does **not** specify what to do with `present` when the source describes
CD63 as functionally present but unquantified — the schema field says
"closed enum" and the obvious safe answer is `unknown`. The builder is
doing the right thing on a per-claim basis; the prompt just never tells
it that `present=unknown` makes the row invisible to downstream gates.

## CD63 ledger evidence

A2 ledger for CD63 (v2.35.0): 32 claims, split 16/16
`surface_expression`/`tissue_expression`. Keyword scan for
cancer/tumor/EV/exosome hits **25 of 32 claims** — confirming that the
upstream PTS selection saw CD63's EV+tumor literature. But the slice
that reaches the *expression* builder is only `tissue_expression` (16),
and only **two** of those 16 are tumor-tissue claims:

- **a2_evi_16** (PMC12785128): "TIMP1 engages CD63/β1-integrin on liver
  macrophages to activate AKT/mTOR signaling and stabilize the M2
  (pro-tumorigenic) phenotype, establishing a hepatic pre-metastatic
  niche in CRC." `assay_context.disease_state =
  "colorectal cancer (CRC) pre-metastatic niche"`. No level reported.
- **a2_evi_22** (PMC12914813): "In HCC cells, ANXA2 loss reduces CD63
  protein levels without a corresponding decrease in mRNA …" Regulation,
  not baseline level.

The other 14 `tissue_expression` claims describe non-tumor disease
(asthma, COPD, NPC, allergy, stroke), normal corneal/limbal tissue, or
generic EV/exosome biology. The cancer-rich claims (CTL granules,
exosome-mediated PD-L1 release, tetraspanin biology) are all tagged
`surface_expression` upstream, so the expression builder never sees
them as candidates for a tumor expression row.

Result: builder emits exactly 2 tumor rows, both `present=unknown`,
both faithfully reflecting the source. Gate excludes both.

## Compare: TACSTD2 / PVRIG vs CD63

| Gene    | tissue_exp | tumor tissue_exp | tumor rows | present-unknown tumor rows | passes gate |
|---------|-----------:|-----------------:|-----------:|---------------------------:|------------:|
| TACSTD2 | 24         | 20               | 22         | 0                          | 21 / 22     |
| PVRIG   | 25         | 13               | 31         | 6                          | 25 / 31     |
| CD63    | 16         | 2                | 2          | 2                          | **0 / 2**   |

TACSTD2 and PVRIG don't do anything different in the prompt — they
benefit from a literature corpus that **already speaks the builder's
language**:

- TACSTD2: "TROP2 shows high expression in esophagus … low in pancreas,
  breast, cervix" → IHC-scored normal baseline + IHC-scored tumor reads
  pull through as `present=high/low` straight from the quote.
- PVRIG: "BM-derived CD8+ T cells co-express TIGIT with PVRIG", "PVRIG
  expression on T cells is increased relative to normal tissue" → flow
  cytometry + "increased" phrasing maps to `moderate`/`high`. PVRIG
  still has 6 `present=unknown` tumor rows where the claim is
  qualitative (functional engagement), so it loses ~20% of its tumor
  rows to the same gate — but still passes because it has 25 quantified
  ones too.

CD63 has the opposite literature shape: the EV literature is
*functional* and *qualitative* ("CD63 is the exosome marker"; "TIMP1
engages CD63"; "lysosome-dependent turnover"). The 2 tumor claims that
do survive A2 selection both describe engagement / regulation, not an
IHC score. Two rows × two `unknown` = full recall loss.

## Recommended prompt edits

Two complementary fixes. The first is the high-leverage one — the
second is a guardrail for the EV-biology gap.

### 1. Add a `present` derivation rule for qualitative-evidence claims

The prompt currently lets the builder choose `unknown` whenever the
claim doesn't state a level. That is *technically* correct but it makes
the row invisible to every downstream level-keyed gate
(`tumor_associated`, `expression_level_rationale`, etc.). Add an
explicit "minimum-level inference" rule in the
**Schema fields → `present`** subsection (lines 43–45 of
`expression_builder_system.md`):

> When the source asserts that the protein is *functionally present*
> on a cell/tissue but does not name an IHC tier (e.g. "engages
> CD63 on macrophages", "marker of activated cells", "CD63 is a
> conserved host factor on T cells"), use `low` — not `unknown`.
> `unknown` is reserved for claims where the source itself disclaims
> ability to say (e.g. "level not assessed", "below detection
> threshold ambiguous").

This is conservative (no upgrade to `moderate`/`high` without textual
support) and unambiguous (the inference rule fires on a name-check of
the protein at the cell, not on speculation). It preserves the
`unknown` semantic for genuinely-unmeasured claims.

### 2. Add a worked example for functional-engagement claims

The prompt currently does not show how a "ligand engages protein X on
tumor macrophages" or "protein X regulates exosome release in HCC"
claim maps to an `ExpressionRow`. Add a short worked example after
**Grouping (CRITICAL)** (after line 70):

> A claim that names a protein as functionally engaged on a tissue/cell
> (e.g. "ligand Y engages protein X on tumor-microenvironment
> macrophages", "protein X loss in disease-state cells reduces
> downstream signaling") still maps to an `ExpressionRow`, with
> `disease_context` taken from the cell context's disease state and
> `present` at minimum `low` per the rule above. Do not skip the row
> on the basis that the claim is "about function, not expression" —
> functional engagement implies presence.

### 3. (Smaller) Tighten the `disease_context` derivation rule

Lines 11-13 say "extract … disease context" without specifying the
source. Promote `assay_context.cell_context.disease_state` (which both
CD63 tumor claims carry verbatim: `"colorectal cancer (CRC) pre-
metastatic niche"`, `"hepatocellular carcinoma (HCC)"`) to the canonical
input. This is implicit today and works in practice — both CD63 rows
correctly hit `disease_context=tumor` — but making it explicit prevents
drift on a future model upgrade.

### Safety + scope

The fix targets `present=unknown`-in-disease rows — a minority case in
genes whose literature is IHC-quantification-dense. TACSTD2 is
unaffected (0 unknown-tumor rows today). PVRIG's 6 unknown-tumor rows
upgrade to `low`, marginally raising rationale weight. The change
pulls EV/tetraspanin tumor recall in line with oncology-Ab-drug recall.

Out of scope: PTS A2's tagging of CD63 exosome/EV biology as
`surface_expression` rather than `tissue_expression` is the other half
of the gap. The expression builder can't recover from claims it never
sees. The prompt fixes above raise CD63's tumor recall from 0 to 2
before that work lands, which is the right step today.
