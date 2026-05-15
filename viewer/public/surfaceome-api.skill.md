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

### Discovery

| Method | Path | Returns | TTL |
|---|---|---|---|
| `GET` | `/v1/health` | `{ ok, n_annotations }` | 60s |
| `GET` | `/v1/genes` | List of genes with a deep-dive record (summary fields) | 60s |
| `GET` | `/v1/genes/{SYMBOL}` | Full SurfaceomeRecord JSON (see schema below) | 1d |
| `GET` | `/v1/orthologs/{SYMBOL}` | Mouse + cyno orthologs from latest Ensembl Compara release | 1d |

### Genome-wide (~19k human protein-coding genes)

| Method | Path | Returns | TTL |
|---|---|---|---|
| `GET` | `/v1/catalog` | Per-gene-per-source DB-vote matrix (5 DBs) + latest triage verdict + deep-dive flag | 60s |
| `GET` | `/v1/triage/{SYMBOL}` | Every triage run for one gene — model × variant × replicate, with cost + token counts | 60s |
| `GET` | `/v1/triage/export.tsv` | Long-format TSV of every triage run for one `run_id`. Default `mainbench_canonical_v1` (1,470 SurfaceBench rows); pass `run_id=genome_full_sonnet_ncbi_v1` for the full ~19k-gene sweep. | 1d |

### SurfaceBench (147-gene labeled eval)

| Method | Path | Returns | TTL |
|---|---|---|---|
| `GET` | `/v1/benchmark` | 147 ground-truth labels (JSON) for the current bench_version | 1d |
| `GET` | `/v1/benchmark/export.tsv` | Same 147 labels in 7-column TSV shape | 1d |
| `GET` | `/v1/benchmark/{SYMBOL}` | Single gene's truth label | 1d |
| `GET` | `/v1/benchmark/matrix` | One row per gene: truth + 7 per-DB flags + per-model LLM verdicts (headline + 3 alts) | 1d |

Gene symbols are case-insensitive on the wire (the Worker uppercases them) but the canonical HGNC form is upper-case.

## SurfaceomeRecord shape (per-gene deep-dive)

Top-level fields most agents care about:

- `gene.hgnc_symbol`, `gene.uniprot_acc`, `gene.ensembl_gene` — identity
- `targetability.tier` — `validated` | `preclinical` | `discovery` | `edge_case` | `not_recommended`
- `targetability.tldr` — one-paragraph human summary
- `surface_biology.surface_status`, `.topology`, `.anchor_type`
- `surface_biology.db_comparison` — seven booleans: `surfy`, `cspa`, `uniprot_query`, `go`, `hpa`, `deeptmhmm`, `compartments`, plus `n_sources_voting_surface`
- `surface_engagement_validation.preclinical_evidence[]` — drug/Ab programs with citations
- `risk_flags[]` — secretion, shedding, contradictions, etc., each with `severity`
- `evidence[]` — full primary/secondary evidence chain (verbatim spans + source URLs)
- `rationale` — ≤1800-char synthesis
- `confidence` — `high` | `medium` | `low`
- `triage_signal` — `likely_accessible` | `possibly_accessible` | `unlikely` | `unknown`
- `model_path` — `sonnet_only` | `opus_light` | `opus_heavy` (which agent path produced this record)

Schema version is in `schema_version` (currently `v0.5.x`). Fields not present in older records are absent (use optional-chaining when reading).

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
  | jq '.gene.hgnc_symbol, .targetability.tier, .confidence, .rationale'
```

```javascript
const res = await fetch(
  "https://api.deliverome.org/surfaceome/v1/genes/ERBB2",
  { cache: "force-cache" },
);
const record = await res.json();
console.log(record.targetability.tldr);
```

```python
import httpx
r = httpx.get("https://api.deliverome.org/surfaceome/v1/genes/ERBB2", timeout=15)
record = r.json()
print(record["targetability"]["tier"])
```

## Example: rebuild the canonical predictions table

`/v1/triage/export.tsv` returns the same 14-column long-format TSV that the figure scripts and gists consume — the public source of truth for every published figure.

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
