# Tagged sites + internalization measurements — viewer design

**Status:** design / spec (pre-implementation)
**Date:** 2026-08-04
**Branch:** `claude/tagged-sites` (worktree off PR #130 head `a542a289`)
**Repo:** public `accessible-surfaceome`

## 1. Goal

Add to the per-protein surfaceome viewer:

1. An **overlay of potential tag-insertion sites** on each surface protein — rendered the
   way SURFACE-Bind sites are (3D structure spheres **and** linear topology-bar pins),
   colored by **sourcing method**: *deterministic* vs *literature-retrieved*.
2. A new **§08 "Internalization measurements"** section on the per-protein page — a table
   of published internalization measurements (cell type · assay · rate · ±ligand · n ·
   source).

Both are powered by new literature-retrieval work modeled on the two agentic benchmarks in
`deliverome-internal/data/analysis/` (`agentic_tag_site_benchmark`,
`agentic_internalization_benchmark`), plus a port of the existing deterministic
insertion-site pipeline.

## 2. Scope

### In scope
- Two tag-site **sourcing methods** feeding one overlay:
  - **Literature-retrieved** (primary): an agent that, given a protein's **computed
    sequence + per-residue topology**, identifies exact residue junctions, classifies each
    extracellular vs not, and prioritizes extracellular sites.
  - **Deterministic**: potential sites from AlphaFold pLDDT + KIBBY conservation, ported
    from the incumbent `surfaceome_deeptmhmm` pipeline outputs.
- One **internalization-evidence** retrieval agent producing per-protein measurement rows.
- Viewer: tag-site overlay on the 3D structure viewer + the linear topology bar; a §08
  internalization tab.
- A shared `TaggedSite` data contract and an `InternalizationMeasurement` contract, shipped
  to the viewer as static per-protein JSON.
- The 23 curated positive controls used **as a validation set only** (recall benchmark for
  the literature and deterministic methods) — **not rendered**.

### Out of scope (this effort)
- Writing tag-site data into Cloudflare D1 / the Worker projection (static JSON first;
  migrate later if it grows to surfaceome scale).
- Re-running the deterministic AF+KIBBY computation from raw inputs in the public repo
  (we port precomputed outputs; re-computation is a later option — see §7.2).
- Rendering the curated controls as their own tier in the UI.
- Snorkel/topology-reorienting constructs, guide/PAM/HDR editing constraints (the construct
  is synthesized — every residue is reachable).

## 3. Evidence model — three provenances, two rendered

Every tag site carries a `provenance`. The viewer renders two of the three; the third is
validation-only.

| Provenance | Source | Rendered? | Overlay color |
|---|---|---|---|
| `literature_retrieved` | Primary agent: literature + computed sequence/topology | **Yes** | color L |
| `deterministic_computed` | Ported AF pLDDT + KIBBY conservation pipeline | **Yes** | color D |
| `validated_literature` | 23 curated positive controls | No — validation only | — |

The curated controls (`positive_controls.tsv`, 23 rows / 18 proteins) are the ground truth
against which the two rendered methods are scored (site recall, residue-exactness,
extracellular-classification agreement). They never appear in the UI.

**Why two methods, not one.** The deterministic screen and the literature agent are
complementary, not redundant. The deterministic method encodes two sound structural priors
(flexible + non-conserved) but is *tag-agnostic*, cannot reason about loop capacity, and
treats low pLDDT as disorder even when it only means low model confidence. The literature
method contributes exactly what the screen is blind to: published insertion precedent,
measured functional impact, tag-chemistry fit, and loop-capacity judgment. Rendering both,
color-coded, lets a user see where independent evidence classes agree.

### 3.1 Tag chemistry vs site type (ALFA + SpyTag003 cassette)

Our working cassette is **SpyTag003 + ALFA**, and the two arms do **not** fit the
disorder-first approach equally:

- **ALFA** (15-aa α-helix) folds independently with no topological constraint — it tolerates
  disordered internal loops well. Every internal site in the curated controls that used
  EndoNB's tag is ALFA. **ALFA fits the low-pLDDT/disordered internal approach.**
- **SpyTag003** (β-strand) must complete a β-sheet in SpyCatcher; when tethered at *both*
  ends (internal insertion) it conjugates poorly — the controls' own cross-reference records
  ~6,000× slower reaction in loops, and the pipeline's internal `SPY003_ALFA` sites are
  likely **ALFA-detection-only in practice**. SpyTag003 works well at a **free extracellular
  terminus**. DogTag is the loop-friendly β-hairpin swap if internal Spy chemistry is needed.

Implication for this feature: an internal `deterministic_computed` site is a good **ALFA**
site but not necessarily a good **SpyTag** site. This is a concrete instance of deterministic
blind spot #3 (tag-agnostic screening), and a reason the per-site record keeps `tag_type` and
the literature method's tag-chemistry evidence. (Not a v1 UI requirement, but the schema
should not preclude surfacing an "expected Spy-arm behavior" note later.)

## 4. Data contracts

Shipped as static per-protein JSON (see §6). Keyed to the viewer's gene-symbol route via
`gene.uniprot_acc`.

### 4.1 `TaggedSite`

```jsonc
{
  "site_id": "AXL-internal-184",
  "gene_symbol": "AXL",
  "uniprot_acc": "P30530",
  "provenance": "literature_retrieved",        // | "deterministic_computed"
  "det_path": null,                              // "disorder" | "surface_loop" (deterministic only)
  "site_kind": "internal",                       // "terminal_n" | "terminal_c" | "internal"
  "insert_after_residue": 184,                   // junction: tag sits between N and N+1
  "residue_before": "P",                         // verified against canonical sequence
  "residue_after": "G",
  "topology_state": "O",                         // DeepTMHMM char at the junction
  "extracellular": true,                         // derived; drives prioritization + emphasis
  "compartment": "extracellular",                // extracellular | intracellular | tm | signal
  "tag_type": "ALFA",                            // ALFA | DogTag | FLAG | HA | HiBiT | ...
  "tag_length_aa": 15,
  "linker": "GS both sides",
  "evidence_type": "published tag insertion in the same loop or domain",
  "functional_impact_measured": "GAS6-driven internalization retained, n=4; NOT MEASURED: ligand affinity",
  "confidence": "high",                          // high | medium | low
  "rationale": "1-3 sentences incl. how disorder was weighted",
  "sources": [{ "claim": "...", "citation": "...", "url": "...", "pmid": "...", "doi": "..." }],
  // deterministic-only fields (null for literature_retrieved):
  "plddt": 79.9,
  "conservation_rank": 12,
  "median_conservation": 0.34
}
```

Junction/numbering convention matches the benchmark exactly: UniProt canonical isoform,
`insert_after_residue = N` puts the tag between residue `N` and `N+1`; `residue_before` /
`residue_after` are mechanically verified against the record's `sequence`. A residue-identity
mismatch invalidates the site (drop + log).

### 4.2 `InternalizationMeasurement`

One row **per measurement**, not per paper (matches the internalization benchmark's design):

```jsonc
{
  "gene_symbol": "TFRC",
  "uniprot_acc": "P02786",
  "cell_type": "HeLa",
  "assay": "flow cytometry, anti-tag internalization",
  "ligand_status": "constitutive",               // constitutive | ligand-driven | not stated
  "ligand": null,                                 // e.g. "GAS6"
  "rate": "t1/2 ~ 8 min",                         // or "NOT STATED (curve only, Fig 3B)"
  "rate_class": "quantified",                     // quantified | not quantified
  "n_replicates": 4,
  "source": { "citation": "...", "url": "...", "pmid": "...", "doi": "..." }
}
```

Plus a separate `qualitative_statements[]` list (weaker evidence class; never inflates the
quantitative rows), per the benchmark's rationale.

## 5. Viewer surfaces

Mirrors the existing SURFACE-Bind feature (the near-exact template).

### 5.1 Tag-site overlay (no standalone table, no controls)
- **3D structure viewer** — `viewer/components/surfaceome/StructureViewerCard/StructureViewer.tsx`
  already accepts `surfaceBindAnchors` and draws labeled α-carbon spheres with a view-mode
  toggle. Add a parallel `tagSites` prop (or a third view mode) that draws one sphere per
  rendered `TaggedSite`, **colored by `provenance`** (L vs D), labeled with tag type +
  residue. Assembly mirrors the `surfaceBindAnchors` block in `GeneHeader.tsx` (~L636–658)
  and the sphere loop in `StructureViewer.tsx` (~L1960–2019); reuse `deriveCompartment` from
  `lib/tag-sites-derive.ts`. NOTE: 3Dmol/WebGL needs concrete hex, not CSS vars — keep a small
  JS provenance→hex map in sync with the `--tag-site-*` tokens (mirrors `COMPARTMENT_COLOR`).
- **Linear topology bar** — `viewer/components/surfaceome/IsoformsCard/TopologyBar.tsx`.
  Add absolutely-positioned pins at `insert_after_residue / topology.length`, colored by
  provenance. Terminal sites pin at the corresponding terminus.
- **Emphasis**: extracellular sites drawn at full weight; non-extracellular dimmed, behind
  a toggle (not hidden), so the prioritization is visible but the rest is inspectable.
- **Color source**: two new named tokens (provenance-L, provenance-D) in the shared token
  layer (`app/design-tokens.css`), never inline hex — following repo convention.

### 5.2 §08 "Internalization measurements" tab
- New `InternalizationCard` section (copy `SurfaceBindCard.tsx` scaffold: `SectionCard` +
  sortable client table + `StatusPill` chips). Columns: cell type · assay · ±ligand · rate ·
  n · source link. A secondary panel lists `qualitative_statements`.
- Registered as one conditional entry (present when the protein has measurements) in the
  `sections[]` array in `viewer/components/surfaceome/GeneDetail/GeneDetail.tsx` (mirroring the
  SURFACE-Bind entry), taking the **§08** slot after Isoforms. Section number = 1-based array
  index passed to `render(n)`; there is no visually-rendered §NN, but ordering places it last.

## 6. Data path

Static per-protein JSON in `viewer/public/`, following the `structure-viewer/{UNIPROT}.json`
precedent and the existing `viewer/public/data/surfaceome/{SYMBOL}.json` exports.

- `viewer/public/tag-sites/{SYMBOL}.json` → `{ has_data, sites: TaggedSite[] }`
- `viewer/public/internalization/{SYMBOL}.json` → `{ has_data, measurements: [], qualitative_statements: [] }`

Loaders in `viewer/lib/` (`loadTaggedSites(symbol)`, `loadInternalization(symbol)`) mirror
`loadStructureViewerData`. Keyed by symbol to match the route param directly; `uniprot_acc`
carried inside each record. No D1/Worker/Pydantic changes in this effort.

**Architecture correction (verified against the code).** The per-gene route is **not** a
static-generated server page — it is a **client shell** at `viewer/app/gene/page.tsx`
(`"use client"`) that fetches the `SurfaceomeRecord` from the Worker at runtime and renders
`GeneDetail.tsx`. Consequence: the `node:fs` `readFileSync` loaders above are **server-only**
(usable from build-time exports and tests, not the live client shell). For the live overlay,
the static `viewer/public/tag-sites/{SYMBOL}.json` is **client-fetched** as a static asset —
added to the existing `Promise.all` in `app/gene/page.tsx` (alongside the record/triage/
benchmark fetches) and threaded `GeneDetail → GeneHeader → StructureViewer`. Same file on
disk; the loader and the client fetch are two readers of it. (A later option is to embed
tagged sites in the Worker's record response, removing the extra fetch.)

## 7. Sourcing pipelines

All new pipeline code lives under `src/accessible_surfaceome/agents/` (existing agent
framework). Each writes the static JSON in §6.

### 7.1 Literature-retrieved tag sites (primary)
- Port the `agentic_tag_site_benchmark/prompt.md` into a runnable agent, with **one
  deliberate change from the benchmark**: the production agent is **given the computed
  `sequence` and `per_residue_topology`** from the SurfaceomeRecord, so it can (a) name
  exact `insert_after_residue` junctions and (b) have `residue_before/after` verified
  against the real sequence. (The benchmark stays symbol+name-only; this is a second
  run-mode of the same code — see §9.)
- Retrieval substrate: **the project's own stack, not MCP** — `src/accessible_surfaceome/tools/evidence_retrieval.py` (`evidence_retrieval(uniprot_acc, category)`: EuropePMC + PubTator discovery, PMC-OA full-text snippet extraction, cached/rate-limited) and `tools/gene_literature.py` (NCBI elink), with the LLM step driven through `agents/surfaceome_v2/builders/_common.py:call_builder` (Anthropic SDK, `SONNET_MODEL`, optional Anthropic server-side `web_search`). This is exactly how the existing surfaceome-v2 builders retrieve evidence.
- Classifies each site extracellular vs not from the DeepTMHMM string (`O/I/M/S`), ranks
  extracellular first.
- Emits `TaggedSite[]` with `provenance: "literature_retrieved"`.

### 7.2 Deterministic tag sites (separate)

The incumbent method (verified in `workflows/surfaceome_deeptmhmm/build_structure_site_viewer.py`)
is a **screen-then-rank**, not a score-everything:

1. **Candidate spans** = contiguous runs of **AFDB per-residue pLDDT < 70, ≥ 4 aa,
   non-terminal** (`afdb_internal_low_plddt_lt70_len4_sites`) — a disorder/flexibility proxy.
2. **Topology gate** — keep only extracellular (`O`) spans, dropped near TM boundaries.
3. **UniProt veto** — drop spans hitting disulfides, N-glycosylation sequons, active/binding
   sites, processing boundaries.
4. **Rank survivors by KIBBY conservation** (`select_top_internal_insertion_spans`; each span
   carries `rank`, `conservation_rank`, `plddt_rank`, `median_conservation`). pLDDT is the
   *filter*; conservation is the *ranker* — deliberately, since ranking on low pLDDT alone is
   a known failure mode.

This method has **two candidate-generation paths**, both extracellular-gated, feature-vetoed,
and conservation-ranked, both emitting `provenance: "deterministic_computed"` (distinguished
by a `det_path` sub-field: `"disorder"` | `"surface_loop"`):

**Path 2a — disorder sites (port).** Map the precomputed
  `deliverome-internal/cloudflare/surfaceome_structure_site_viewer/deploy_static/insertion_sequence_library.csv`
  (+ `viewer_dataset.json`) rows onto `TaggedSite`. Faithful "as we did in deliverome-internal";
  no AF/KIBBY recompute. **Yields low-pLDDT sites only** — by construction it cannot contain
  ordered-surface-loop sites (see 2b).

**Path 2b — ordered surface-loop sites (new computation, catches the TFRC I290 class).**
  Verified against the EndoNB TFRC site: I290/V291 sits at **pLDDT ~94–98** (confidently
  folded), RSA up to ~88% on the flanks, in a strand→loop→helix connector ~35–45 Å from the
  Tf/HFE interface and clear of features — so the low-pLDDT screen (2a) **structurally misses
  it**, and EndoNB itself picked it by eye as a "surface loop," not by disorder. Path 2b makes
  that judgment computable. Here **pLDDT flips role**: from a disorder *gate* to a *reliability
  gate* that makes the surface metrics trustworthy. Candidate =
  `extracellular ('O')` **AND** `pLDDT ≥ 70` **AND** `DSSP = loop/turn` (up-weight
  strand↔helix connectors) **AND** `window-high RSA` **AND** `MSA indel-tolerant`
  (high per-column gap frequency) **AND** `≥10–15 Å (3D) from disulfides / N-glyc sequons /
  active-binding / interface atoms`; rank by low KIBBY conservation + high RSA + high column
  gap-frequency. Inputs are all already available (AF PDB, UniProt features, the conservation
  MSA); tools: `freesasa` (assembly-aware — compute on the biological assembly so dimer
  interfaces aren't mistaken for surface), `pydssp`/`mkdssp`, `biopython`. Optional later
  signals: ENM/NMA flexibility (ProDy) and PAE-based domain/linker parsing — noted as
  complementary, but neither is decisive for the I290 case (flat pLDDT, intra-domain).
- **Two things to confirm at port time** (do not assume):
  - **KIBBY identity + rank direction** — the per-span `rank` is produced by an *upstream*
    step not in `build_structure_site_viewer.py`; confirm the exact KIBBY tool/citation and
    that rank 1 = least-conserved/safest before trusting the ordering.
  - **Per-site pLDDT field** — the span is `<70` by construction; `average_plddt` in the data
    is *per-protein*. `TaggedSite.plddt` should carry the per-span metric (`plddt_rank`/span
    value), not the protein average.
- **Known blind spots** (feed §13 and motivate the surface-exposure enhancement below):
  (1) low pLDDT can mean low model confidence, not true disorder; (2) no loop-capacity check
  (a short ECL tripled by a ~49-aa cassette is not flagged); (3) tag-agnostic — β-strand tags
  (SpyTag) behave differently from α-helical epitopes (ALFA) in loops; (4) veto quality is
  bounded by UniProt annotation completeness.
- **Later option:** re-run the full scoring in the public repo. Deferred: the public record
  carries topology + sequence but **not** per-residue pLDDT/conservation, so recompute needs
  those inputs sourced first.

### 7.3 Internalization-evidence retrieval
- Port `agentic_internalization_benchmark/prompt.md` into a runnable agent. One row per
  measurement; `ligand_status` first-class; nulls preserved; qualitative statements kept in
  a separate, weaker list.
- Emits `InternalizationMeasurement[]` + `qualitative_statements[]`.

## 8. Validation
- Import the 23 curated controls (`positive_controls.tsv`) into a fixture used only for
  scoring — **not shipped to the viewer**.
- Metrics per rendered method: **site recall** (fraction of control sites recovered),
  **residue-exactness** (junction within ±k residues), **extracellular-classification
  agreement**, and for the literature method **fabrication rate** (proposed sites/residues
  not present in the cited source). Report per run.

## 9. Benchmark vs production (important)
Feeding the agent the computed sequence + topology means the production tag-site agent is no
longer the clean symbol-only benchmark condition. Keep both as **run-modes of one codebase**:
`benchmark` (symbol + name only, for scoring the retrieval skill) and `production`
(symbol + name + computed sequence/topology, for sourcing display data). The validation in
§8 runs the production mode against the controls.

## 10. Architecture / conventions to follow
- Viewer: Next.js App Router, React 19, TS, **CSS Modules** (no Tailwind), server components
  by default, `"use client"` only for interactive tables / the 3Dmol viewer. New components
  at `viewer/components/surfaceome/<Name>/<Name>.tsx` + `.module.css`, named exports.
- Reuse: `SectionCard`, `StatusPill`, `ChipLabelValue`, `compartmentAt`/`ecSites` from
  `viewer/lib/surface-bind.ts`, the `surfaceBindAnchors` sphere machinery, `TopologyBar`.
- Colors via shared tokens only.

## 11. Testing
- Framework: Node `node:test` via `tsx` + `renderToStaticMarkup` (mirror
  `viewer/tests/accessibility_risks_card_rationale.test.tsx`, `surface_bind_ec_sites.test.ts`).
- Component tests: overlay renders correct pin count/colors by provenance; §08 table renders
  rows + qualitative panel; non-EC dimming/toggle.
- Lib tests: residue-junction verification against `sequence`; EC classification from
  topology; deterministic-CSV → `TaggedSite` adapter.
- Pipeline tests: schema-validation of agent output; validation harness against the 23
  controls.

## 12. Phasing
- **P0** — `TaggedSite` + `InternalizationMeasurement` schemas; static-JSON loaders;
  import the 23 controls into the validation fixture.
- **P1** — Tag-site overlay (3D + topology bar) rendering from static JSON, colored by
  provenance, EC emphasis + non-EC toggle. Ship against a seed dataset.
- **P2a** — Deterministic disorder path: port `insertion_sequence_library.csv` → `TaggedSite`
  (`deterministic_computed`, `det_path: "disorder"`).
- **P2b** — Deterministic surface-loop path: compute RSA + DSSP + MSA indel-tolerance +
  3D-distance veto on AF models (`det_path: "surface_loop"`); validate it recovers the ordered
  surface-loop controls (TFRC I290, ITGB1 G101, ITGB5 A102) that Path 2a cannot see.
- **P3** — Literature tag-site agent (production mode, sequence/topology-grounded);
  validate recall vs the 23 controls; emit `literature_retrieved`.
- **P4** — §08 Internalization tab + internalization-evidence agent.
- **P5** *(optional)* — widen protein set; consider D1 migration if the dataset outgrows
  static JSON.

## 13. Open questions / risks
- **Public exposure**: RESOLVED — approved for the public viewer (all data traces to
  published papers).
- **Surface-exposure signal (TFRC I290/V291)**: RESOLVED into design — deterministic Path 2b
  (§7.2). Confirmed the low-pLDDT screen misses the ordered surface loop (pLDDT ~96 at I290).
  Remaining care items for implementation: compute SASA on the **biological assembly** (TFR is
  a homodimer) so dimer-interface loops aren't scored as surface; validate the composite gate
  recovers I290 and the other ordered-loop controls (ITGB1 G101, ITGB5 A102).
- **Control-data accuracy**: EndoNB's methods describe a GS flexible linker generally, which
  conflicts with the controls' "TFRC: no linkers" note — reconcile the specific TFR construct
  against the figure legend before treating linker fields as ground truth in scoring.
- **Overlay legibility**: many candidate sites per protein could clutter the 3D/topology
  views; may need a per-provenance visibility toggle and/or a confidence floor.
- **Deterministic input parity**: ported rows must map onto the *public* record's canonical
  numbering; verify accession/isoform alignment during the port.
- **Agent cost/latency**: three retrieval pipelines over a protein set — batch offline,
  cache to JSON, never at viewer build/request time.
