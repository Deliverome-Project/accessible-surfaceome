# PRD — Evidence Retrieval & Localization Subsystem

**Status:** draft
**Scope:** the searching, retrieving, and passage-localization layer that
feeds the deep-dive annotator. This document does **not** cover the
deep-dive agent's reasoning, classification, or record assembly.

---

## 1. Purpose

Given a protein and a category of experimental evidence, the subsystem
must find the published experiments that bear on that protein's
cell-surface localization, and pinpoint **the exact passage in each
paper where the experiment and its result are stated** — returned as
verbatim, location-anchored, independently verifiable text.

The deliverable of this subsystem is not a judgement. It is a set of
*candidate evidence passages with provenance*, precise enough that a
downstream consumer can quote them directly and a reviewer can audit
them without re-reading the source.

## 2. Background & problem

The project's core promise is "classification you can trust, with full
provenance." Every load-bearing surface-localization claim in a
per-protein record must be anchored to a verbatim quote from a source
that was actually retrieved. The subsystem described here is what makes
that anchoring possible.

The current retrieval approach has three recurring failure modes,
observed directly on well-characterized proteins:

- **F1 — Subject drift.** Keyword search surfaces papers that *mention*
  the protein incidentally (e.g. a methods paper that lists it among
  hundreds of detected proteins) rather than papers that *study* it.
- **F2 — Recency / authority bias.** Result ordering favours the newest
  publications, burying the canonical primary literature.
- **F3 — Wrong-passage selection.** Even within a relevant paper, the
  extracted passage is often methodology boilerplate or an off-target
  sentence rather than the sentence stating the experiment's result.

F3 is the most damaging and the least addressed: better *paper*
retrieval does not fix *passage* selection. Identifying the exact place
where the experiment and result live is the headline requirement of
this subsystem.

## 3. Goals

1. For a `(protein, evidence category)` pair, find the papers that
   contain primary experimental evidence about that protein's surface
   localization.
2. Within each paper, localize the specific passage(s) where the
   experiment **and** its result are described.
3. Return those passages verbatim, each bound to a precise,
   re-resolvable locator, with enough provenance to verify them later.
4. Distinguish "no such evidence exists in the literature" from
   "evidence was not retrieved."
5. Surface evidence on **both sides** of the question — supporting and
   refuting — not only evidence that confirms surface localization.
6. Operate economically across the full target panel (~4,000 proteins).

## 4. Non-goals

- Making the surface-localization call, or any classification beyond
  what is needed to route a passage to a category. That is the
  deep-dive agent's job.
- Resolving contradictions. The subsystem must *surface* conflicting
  evidence; adjudicating it is downstream.
- Assembling or persisting the per-protein record.
- Guaranteeing any single discovery source is canonical or complete.
- Summarizing, paraphrasing, or rewriting source text. Output is
  verbatim.

## 5. Consumers

- **Primary:** the deep-dive annotator agent, which selects passages
  returned here and emits anchored evidence claims.
- **Secondary:** human reviewers auditing a record's provenance, who
  need to confirm a cited passage exists, is verbatim, and was actually
  consulted.
- **Tertiary:** comprehensiveness audits that ask "was category X
  checked for protein Y?"

## 6. Definitions

- **Evidence category** — a class of experiment that can demonstrate
  surface localization (e.g. immunohistochemistry, immunofluorescence
  on intact cells, flow cytometry, surface biotinylation, surface
  mass spectrometry, paired western blot, ectodomain structure,
  curated-atlas localization). The category set is an input to this
  subsystem, not defined by it.
- **Experiment passage** — a contiguous span of source text that
  states an experimental observation: what was assayed and what was
  found.
- **Method passage** — a span describing how an assay was performed,
  without itself stating the result.
- **Locator** — an addressable position in a source: the source
  identifier, the section, the figure or table identifier when
  applicable, and the character span. A locator must be stable enough
  to re-resolve the same passage later.
- **Verbatim** — character-for-character identical to the retrieved
  source body, modulo a documented, deterministic normalization.
- **Primary vs. secondary** — primary evidence is an experimental
  observation in a research report; secondary evidence is a
  database/atlas annotation or a review assertion.
- **Coverage record** — the log of every `(protein, category)`
  consultation, including those that returned nothing.

## 7. Functional requirements

### 7.1 Discovery

- **FR-D1** Given a `(protein, category)` pair, the subsystem produces
  a set of candidate papers plausibly containing primary evidence of
  that category for that protein.
- **FR-D2 (subject grounding)** Candidate papers must be *about* the
  protein, not merely contain its name or an alias. Incidental mentions
  must be excludable.
- **FR-D3 (alias safety)** Protein name resolution must not let
  generic or ambiguous aliases pull in unrelated literature.
- **FR-D4 (multi-source)** Discovery must not depend on a single
  source. Results from multiple discovery sources are unioned and
  de-duplicated by stable publication identity.
- **FR-D5 (seed ingestion)** The subsystem may accept externally
  proposed candidate papers (e.g. from prior-knowledge enumeration).
  Seed papers receive **no special trust** — they enter the same
  verification path as discovered papers and are dropped if they fail
  it.
- **FR-D6 (authority balance)** Discovery ordering must not be biased
  toward the most recent publications; canonical primary literature
  must be reachable.
- **FR-D7 (direction neutrality)** Discovery must be capable of
  surfacing evidence that *refutes* surface localization, not only
  evidence that supports it.

### 7.2 Retrieval

- **FR-R1** For each candidate paper, the subsystem retrieves the
  richest source content available — full text when accessible,
  otherwise the most complete abstract-level content.
- **FR-R2 (graceful degradation)** When full text is unavailable, the
  subsystem still returns what it has and records the limitation; it
  does not silently drop the paper.
- **FR-R3 (structure preservation)** Retrieved content must preserve
  enough document structure (sections, figure/table captions) to
  support localization in §7.3.
- **FR-R4 (stable source body)** The exact body used for localization
  and later verification must be retained or re-resolvable unchanged.

### 7.3 Localization — the core requirement

- **FR-L1** Within a retrieved paper, the subsystem identifies the
  specific passage(s) where the experiment and its result are stated,
  not merely the paper as a whole.
- **FR-L2 (result vs. method)** The subsystem must distinguish
  experiment/result passages from method-only passages. Result-bearing
  passages are preferred; method passages may also be returned when
  assay detail is itself the evidence, but the two must be labelled
  distinctly.
- **FR-L3 (experiment + result pairing)** When the experiment and its
  result are stated in different passages (e.g. assay described in one
  section, outcome in a figure caption), the subsystem should return
  both and indicate that they belong together.
- **FR-L4 (on-subject passages)** A returned passage must concern the
  target protein. A passage describing the same assay applied to a
  different protein in the same paper must not be returned for the
  target.
- **FR-L5 (bounded, verbatim spans)** Returned passages are verbatim
  and bounded to a quotable length — sentence to short-paragraph
  granularity — not whole sections.
- **FR-L6 (precise locator)** Every returned passage carries a locator
  precise enough to re-resolve it and to tell a reviewer where to look
  (source, section, figure/table identifier, character span).

### 7.4 Verification & provenance

- **FR-V1** Every returned passage is confirmed to be an exact
  substring of the retained source body under the documented
  normalization.
- **FR-V2** Every returned passage carries provenance sufficient to
  reconstruct its origin and to detect later drift of the source
  (source identity, access path, content fingerprint, retrieval time).
- **FR-V3** Passages that cannot be verified are not returned as
  evidence; if surfaced at all, they are clearly marked unverified and
  excluded from the evidence set.
- **FR-V4 (no fabrication)** The subsystem never returns a passage that
  is not present in a retrieved source. Absence of evidence is reported
  as absence, never filled in.

### 7.5 Coverage & auditability

- **FR-C1** Every `(protein, category)` consultation produces a
  coverage record, **including consultations that return nothing.**
- **FR-C2** An empty result must state *why* it is empty (no candidate
  papers, candidates found but no on-subject experiment passage, full
  text unavailable, etc.) so that "absent" is distinguishable from
  "not retrieved."
- **FR-C3** The coverage record is sufficient to answer, for any
  protein, which categories were searched and what each returned.

### 7.6 Scale & adaptivity

- **FR-S1** The subsystem operates across the full panel (~4,000
  proteins) at a per-protein cost that is small relative to the
  downstream annotation cost.
- **FR-S2 (shared-literature reuse)** Work on overlapping literature
  (e.g. protein families sharing papers) is reused rather than
  repeated.
- **FR-S3 (tier-adaptive behaviour)** The subsystem adapts to how much
  literature a protein has:
  - *Data-sparse proteins* — be exhaustive; process the whole result
    set; ranking sophistication is unnecessary.
  - *Data-rich proteins* — be selective; rank and sample; authority
    balancing matters most here.
  The same pipeline serves all tiers; only its configuration changes.

## 8. Quality requirements (anti-requirements)

The subsystem is considered to be regressing if any of the three
failure modes recur at scale:

- **No subject drift (vs. F1).** Returned passages must come from
  papers that study the target protein.
- **No authority blindness (vs. F2).** The strongest available
  evidence must be reachable regardless of publication date.
- **No wrong-passage selection (vs. F3).** A returned passage must
  genuinely state an experiment and result about the target protein's
  surface localization — not methodology boilerplate, not an
  off-target sentence.

Precision (a returned passage is real, on-subject, and result-bearing)
is weighted above recall: a missed passage is recoverable downstream; a
plausible-but-wrong passage corrupts a record that claims full
provenance.

## 9. Output contract (abstract)

For each `(protein, category)` consultation the subsystem returns:

- **A set of candidate passages**, each with:
  - the verbatim passage text, bounded in length;
  - a precise locator (source, section, figure/table id, span);
  - a result-vs-method label;
  - a direction indicator (supports / refutes / ambiguous);
  - a primary-vs-secondary indicator;
  - a provenance handle sufficient for later verification;
  - a relevance/confidence score for ordering.
- **A coverage record**: the consultation happened, what was searched,
  how many papers were examined, and — if empty — why.
- **The retained source bodies** (or stable handles to them) for every
  passage returned, so downstream verification and reviewer audit do
  not require re-retrieval.

The contract is deliberately about *structure and guarantees*, not
representation.

## 10. Success metrics

- **Verification pass rate** — fraction of returned passages that pass
  independent substring/provenance verification downstream. Target:
  near-total; a failure here is a correctness bug.
- **Passage precision** — fraction of returned passages that a human
  judge agrees state an on-subject experiment + result for the
  category. Measured against a hand-labelled gold set.
- **Category coverage completeness** — fraction of non-absent proteins
  for which every applicable category has a coverage record.
- **Failure-mode incidence** — measured rates of F1/F2/F3 against the
  gold set, trended over time; all should fall toward zero.
- **Absent-vs-missing accuracy** — on proteins where a category truly
  has no evidence, the subsystem reports a justified empty result
  rather than a false passage or an ambiguous silence.
- **Per-protein cost** — held to a small fraction of downstream
  annotation cost across the full panel.

## 11. Open questions & risks

- **Full-text availability.** A meaningful share of relevant
  literature — especially older or lower-tier-journal papers common in
  the long tail — may not be openly retrievable in full text. The
  subsystem must degrade gracefully, but localization quality is
  bounded by what can be retrieved.
- **Result-vs-method discrimination across domains.** Distinguishing a
  result statement from a method statement is harder in primary
  cell-biology literature than in structured clinical abstracts; the
  discriminator must be evaluated on the actual corpus, not assumed.
- **The middle tier is the hard tier.** Proteins with moderate
  literature — enough to be noisy, not famous enough to be
  well-known — stress the subsystem most. Evaluation sets should
  over-sample this tier.
- **Verification is the true cost centre.** Discovery is cheap;
  confirming that a passage genuinely states the experiment and result
  is where effort concentrates. Cost and quality targets should be set
  against the verification step, not the search step.
- **Category set evolution.** The evidence-category list is an input
  and will change; the subsystem must absorb new categories without
  redesign.
