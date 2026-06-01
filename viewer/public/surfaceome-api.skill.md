---
name: surfaceome-api
description: Use when the user asks whether a human gene is a cell-surface protein, asks for surface accessibility / drug targetability evidence on a specific gene, mentions SurfaceBench or the 147-gene triage benchmark, or compares LLM triage verdicts against public databases. Reads the public Surfaceome API at api.deliverome.org/surfaceome/v1/* — no auth, CORS open — to fetch deep-dive SurfaceomeRecords, per-source DB votes, and benchmark verdicts.
---

# Surfaceome API

Read-only public API serving the Deliverome surfaceome catalogue. Base URL: `https://api.deliverome.org/surfaceome/v1/`. No authentication. Aggressive edge caching — responses are stable for minutes to a day depending on endpoint.

## When to use this skill

Invoke before answering whenever the user:

1. **Asks about a specific human gene's surface biology** ("is ERBB2 a surface protein", "what's the targetability tier on TACSTD2", "give me evidence that CD19 reaches the plasma membrane"). Fetch `/v1/genes/{SYMBOL}` for the full deep-dive record, or `/v1/catalog` filtered to that gene for the seven-DB vote summary.

2. **References SurfaceBench or the 147-gene triage benchmark.** Fetch `/v1/benchmark/matrix` — the canonical view that joins ground truth + 7 per-DB flags + per-model LLM verdicts in one payload.

3. **Compares LLM triage variants** (naive vs ncbi vs web vs pubmed prompts; opus vs sonnet vs haiku) on a specific gene. Fetch `/v1/triage/{SYMBOL}` for every run on record.

4. **Asks for orthology data** (mouse, cynomolgus) on a human gene. Fetch `/v1/orthologs/{SYMBOL}`.

5. **Wants the genome-wide DB-vote matrix** for a query like "all genes that 5+ sources call surface". Fetch `/v1/catalog` and filter client-side; the response is ~6 MB so paginate intelligently.

Do **not** invoke this skill for non-human genes, for general protein-biology questions that don't reference a specific gene, or for questions that are already answered by domain knowledge without hitting an external service.

## Endpoints

Grouped by scope, in the order you'll usually reach for them: the labeled **benchmark** first, then the **genome-wide** sweep, then the per-gene **deep dive**.

### SurfaceBench (147-gene labeled eval)

| Method | Path | Returns | TTL |
|---|---|---|---|
| `GET` | `/v1/benchmark` | 147 ground-truth labels (JSON) for the current bench_version | 1d |
| `GET` | `/v1/benchmark/export.tsv` | Long-format TSV of the bench-restricted multi-model sweep: one row per (bench gene × model × variant) with truth labels + DB votes joined in (24 cols). Flat version of `/v1/benchmark/matrix`. | 1d |
| `GET` | `/v1/benchmark/{SYMBOL}` | Single gene's truth label | 1d |
| `GET` | `/v1/benchmark/matrix` | One row per gene: truth + 7 per-DB flags + per-model LLM verdicts (headline + 3 alts) | 1d |

### Genome-wide (~19k human protein-coding genes)

| Method | Path | Returns | TTL |
|---|---|---|---|
| `GET` | `/v1/catalog` | Per-gene-per-source DB-vote matrix (5 DBs) + latest triage verdict + deep-dive flag | 60s |
| `GET` | `/v1/triage/{SYMBOL}` | Every triage run for one gene — model × variant × replicate, with cost + token counts | 60s |
| `GET` | `/v1/triage/export.tsv` | Long-format TSV of every triage run for one `run_id`, with per-source DB votes + `uniprot_acc` joined in server-side (21 cols). Default `mainbench_canonical_v1` (~1.5k bench rows × Haiku/Sonnet/Opus × 4 variants); pass `run_id=genome_full_sonnet_ncbi_v1` for the full ~19k-gene Sonnet sweep. | 1d |

### Deep dive (per-gene)

| Method | Path | Returns | TTL |
|---|---|---|---|
| `GET` | `/v1/genes/{SYMBOL}` | Full SurfaceomeRecord JSON (see schema below) | 1d |
| `GET` | `/v1/orthologs/{SYMBOL}` | Mouse + cyno orthologs for any gene from the latest Ensembl Compara release (genome-wide raw Compara — see note) | 1d |
| `GET` | `/v1/genes` | List of genes with a deep-dive record (summary fields) | 60s |
| `GET` | `/v1/health` | `{ ok, n_annotations }` — liveness | 60s |

`/v1/orthologs/{SYMBOL}` is the **broad** ortholog view — latest Ensembl Compara for any of ~5k genes with a mouse/cyno ortholog (~90% of the surfaceome), carrying full-length % identity + orthology type + high-confidence flag. The deep-dive record's `deterministic_features.orthologs` is the **deep** view — mouse/cyno canonical only, ECD % identity + projected topology + sequence, but only for genes that have been deep-dived. Use the endpoint for breadth, the record for depth.

Gene symbols are case-insensitive on the wire (the Worker uppercases them) but the canonical HGNC form is upper-case.

## SurfaceomeRecord shape (per-gene deep-dive)

`schema_version` is `1.1.x` (the record was fully restructured from the
legacy `v0.5` `targetability`/`surface_biology`/`risk_flags` shape — those
keys no longer exist). Top-level structure:

- `gene` — `hgnc_symbol`, `hgnc_id`, `uniprot_acc`, `ncbi_gene_id`, `ensembl_gene`. Key every downstream lookup on these stable IDs, not the symbol.
- `triage_signal` / `triage_reasoning` — the first-pass Sonnet triage verdict (`likely_accessible` | `possibly_accessible` | `unlikely` | `unknown`) + its prose.
- `executive_summary` — `one_paragraph` (human TL;DR), `surface_accessibility` (`high`|`moderate`|`low`|`no`|`uncertain`), `confidence`, `evidence_grade_summary`, `state_dependence`, `subcategory`, `surface_call_reason`, `headline_risks[]`, `accessibility_context_summary`, plus family tags `uniprot_family` / `hgnc_gene_groups[]` / `llm_family`.
- `filters` — ~35 flat catalog facets for filtering, several paired with a `*_rationale` (e.g. `expression_level`+`expression_level_rationale`, `surface_specificity`+`_rationale`, `has_known_ligand`+`_rationale`): `co_receptor_dependency`, `has_{shed,secreted,epitope_masking,restricted_subdomain}*`, `ecd_accessibility_class`, `evidence_grade`, `evidence_density`, `{mouse,cyno}_ortholog_ecd_pct_identity`, `max_paralog_ecd_pct_identity`, `tumor_associated`, `induction_trigger`, `has_live_cell_surface_evidence`, …
- `surface_evidence` — `evidence_grade` + `grade_rationale`, `claim_stances[]` (per-claim supports/contradicts + weight), `methods[]` (per-assay: `method_family`, `antibodies[]` with clonality + validation strategy/strength, `expression_observations[]`, `overexpression` construct, `surface_claim_type`, `accessibility_relevance`), `non_surface_expression[]`, `contradicting_evidence[]`.
- `biological_context` — `tissues[]` (tissue × `disease_context` × level × cell types/states), `cell_types[]`, `cell_states[]`, `subcellular_localization` (`primary_compartment`, `dual_localization[]`, `membrane_subdomains[]`), `anatomical_accessibility[]`, `accessibility_modulation[]`.
- `accessibility_risks` — `shed_form`, `secreted_form`, `epitope_masking`, `ecd_size_assessment`, `restricted_subdomain`, `co_receptor_requirements`; each with `severity` / `evidence_strength` / `rationale` / `cited_evidence_ids`.
- `deterministic_features` — tool output, never LLM-written (see below).
- `evidence[]` — the primary/secondary chain: `evidence_id`, `claim`, `claim_type`, `direction`, `evidence_tier`, `assay_context` (species / cell / permeabilization), and `spans[]` with verbatim `quote` + `source` (`pmid` / `pmc_id` / `doi` / `url`).
- `confidence` / `confidence_reasoning`, `model_path`, `record_generated_at`.

### `deterministic_features` — sequences, topology, structure, homology

Populated deterministically (UniProt + DeepTMHMM + Ensembl Compara +
AlphaFold DB + PDBe SIFTS + SURFACE-Bind), never by the model. Every
topology entity carries its full amino-acid `sequence` aligned 1:1 with its
`per_residue_topology` string — so a consumer can index the topology without
a second fetch:

- `canonical_topology` — `uniprot_acc`, `per_residue_topology` (`M`/`O`/`I`/`S`/`B` per residue), **`sequence`**, `tm_helix_count`, `signal_peptide_length`, `ecd_length_residues`, `icd_length_residues`, `n_/c_terminal_orientation`.
- `isoform_topologies[]` — same shape per alternative isoform + `{full_length,ecd}_pct_identity_to_canonical` + **`sequence`**.
- `orthologs.{mouse,cynomolgus}[]` — `ortholog_uniprot_acc`, `ortholog_symbol`, `{full_length,ecd}_pct_identity_to_human_canonical`, projected `per_residue_topology` + **`sequence`**.
- `paralogs[]` — `paralog_symbol`, `paralog_uniprot_acc`, `{full_length,ecd}_pct_identity`; close paralogs (>80%) additionally carry topology + **`sequence`**.
- `structure` — `afdb_id`, `afdb_version`, `ecd_mean_plddt`, `ecd_disordered_fraction`, AlphaFold download links **`model_cif_url`** / **`model_pdb_url`** / **`model_pae_url`**, and **`representative_experimental_structure`** (PDBe SIFTS best: `pdb_id`, `chain_id`, `unp_start`/`unp_end`, `resolution_a`, `experimental_method`, `n_experimental_structures`; `null` when no deposited structure).
- `surface_bind` — SURFACE-Bind MaSIF scoring (Balbi et al. 2026, PMID 41604262): `has_data`, `n_sites`, per-site `sites[]` (`anchor_residue`, `area_a2` BSA, α/β seed counts, `hydrophobicity`), `pdbs[]`.

Older records may lack newer fields — use optional-chaining / `?? null` when reading. A markdown mirror of the full record (with the sequences + per-residue topology embedded) is at `https://surfaceome.deliverome.org/data/surfaceome/{SYMBOL}.md`.

## SurfaceBench matrix shape

`/v1/benchmark/matrix` returns:

```jsonc
{
  "bench_version": "<sha>",
  "universe_version": "cu_2026_05_12",
  "sources": ["uniprot", "go", "surfy", "cspa", "hpa", "deeptmhmm", "compartments"],
  "models": ["claude-opus-4-7", "claude-sonnet-4-6", "claude-haiku-4-5-20251001"],
  "headline_variant": "ncbi",
  "alt_variants": ["naive", "web_ncbi", "pubmed_ncbi"],
  "n_genes": 147,
  "rows": [
    {
      "gene_symbol": "ERBB2",
      "uniprot_acc": "P04626",
      "class": "validated_positive",
      "truth_verdict": "yes" | "contextual" | "no",
      "truth_reason": "classical_surface_receptor",
      "db": { "uniprot": 1, "go": 1, "surfy": 1, "cspa": 1, "hpa": 1, "deeptmhmm": 1, "compartments": 1 },
      "n_db_surface": 7,
      "headline": { "claude-opus-4-7": { "verdict": "yes", "reason": "...", "correct": 1, ... }, ... },
      "alts":     { "claude-opus-4-7": { "naive": {...}, "web_ncbi": {...}, "pubmed_ncbi": {...} }, ... }
    }
  ]
}
```

`correct` is 1/0 with `yes ≡ contextual` collapsed (matching D1's `correct` semantics).

## Conventions

- **Use `cache: "force-cache"` or equivalent** when fetching from a build system (Next.js SSG, etc.). The Worker's caching is on the read path; the client should cooperate.
- **Verdict-pill colors** in any UI: `yes` → success-green, `contextual` → amber, `no` → maroon. Mirrors the convention used on the surfaceome.deliverome.org site.
- **Capitalisation:** `verdict` values are lowercase strings (`"yes"`, `"contextual"`, `"no"`), not enums — string-compare exactly.
- **Missing data:** prefer `?? null` over `?? ""` when a field is absent. `null` is the canonical "no value" in this API.

## Example: fetch a per-gene record

```bash
curl -s https://api.deliverome.org/surfaceome/v1/genes/ERBB2 \
  | jq '.gene.hgnc_symbol, .executive_summary.surface_accessibility, .confidence, .executive_summary.one_paragraph'
```

```javascript
const res = await fetch(
  "https://api.deliverome.org/surfaceome/v1/genes/ERBB2",
  { cache: "force-cache" },
);
const record = await res.json();
console.log(record.executive_summary.one_paragraph);
// canonical sequence + its per-residue topology travel together:
const ct = record.deterministic_features.canonical_topology;
console.log(ct.sequence?.length, ct.per_residue_topology?.length); // equal
```

```python
import httpx
r = httpx.get("https://api.deliverome.org/surfaceome/v1/genes/ERBB2", timeout=15)
record = r.json()
print(record["executive_summary"]["surface_accessibility"])
```

## Example: rebuild the canonical predictions table

`/v1/triage/export.tsv` returns a 21-column long-format TSV — the public source of truth for every published figure. Each row carries the per-source DB votes (uniprot/go/surfy/cspa/hpa) and `uniprot_acc` joined from the latest candidate-universe snapshot, so figure scripts don't need a second fetch to compare model verdicts against DB consensus.

```bash
curl -s 'https://api.deliverome.org/surfaceome/v1/triage/export.tsv?run_id=mainbench_canonical_v1&replicate=1' \
  | head -5
```

```python
import pandas as pd
preds = pd.read_csv(
    "https://api.deliverome.org/surfaceome/v1/triage/export.tsv"
    "?run_id=mainbench_canonical_v1&replicate=1",
    sep="\t",
)
# 1,470 rows = 147 genes × {2 Opus + 4 Sonnet + 4 Haiku} cells
print(preds.groupby(["model", "prompt_variant"]).size())
```

## Example: SurfaceBench accuracy

```python
import httpx, collections
m = httpx.get("https://api.deliverome.org/surfaceome/v1/benchmark/matrix", timeout=30).json()
for model in m["models"]:
    correct = sum(
        1 for r in m["rows"]
        if r["headline"].get(model, {}).get("correct") == 1
    )
    total = sum(1 for r in m["rows"] if r["headline"].get(model, {}).get("verdict"))
    print(f"{model}: {correct}/{total} = {correct/total:.1%}")
```

## Error responses

- `400 invalid_symbol` — gene symbol didn't match `[A-Za-z0-9._-]{1,30}` shape
- `404 gene_not_annotated` — the gene is not in the deep-dive set; fall back to `/v1/triage/{SYMBOL}` for the triage verdict, or `/v1/catalog` for the DB-vote summary
- `404 not_in_benchmark` — gene isn't one of the 147 benchmark proteins
- `405 method_not_allowed` — non-GET on a GET endpoint

## Provenance

- Source repo: `https://github.com/Deliverome-Project/accessible-surfaceome`
- Worker source: `cloudflare/workers/surfaceome_api/src/index.js`
- D1 schema: `cloudflare/d1_public_schema.sql`
- Per-gene records validate against the `SurfaceomeRecord` Pydantic schema at `src/accessible_surfaceome/tools/_shared/models.py`. The viewer at https://surfaceome.deliverome.org renders the same records as HTML pages.
