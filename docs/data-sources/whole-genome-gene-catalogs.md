# Whole-genome gene catalogs (NCBI + HGNC)

Genome-wide cost projections for the triage agent (e.g.
[`scripts/build_triageable_catalog.py`](../../scripts/build_triageable_catalog.py))
need a single denominator — the count of protein-coding human genes the
agent could be asked about. That number depends on which authority you
ask, and on how aggressively you trim. This doc records what we use,
why, and how to refresh.

## Sources

Two independent catalogs, fetched 2026-05-11:

| Source | URL | Fetch script | Counts file |
|---|---|---|---|
| NCBI Gene (`Homo_sapiens.gene_info.gz`) | <https://ftp.ncbi.nlm.nih.gov/gene/DATA/GENE_INFO/Mammalia/Homo_sapiens.gene_info.gz> | [`scripts/fetch_ncbi_human_protein_coding.py`](../../scripts/fetch_ncbi_human_protein_coding.py) | [`data/external/ncbi_gene_info/Homo_sapiens.gene_info.summary.json`](../../data/external/ncbi_gene_info/Homo_sapiens.gene_info.summary.json) |
| HGNC complete set | <https://storage.googleapis.com/public-download-files/hgnc/tsv/tsv/hgnc_complete_set.txt> | [`scripts/fetch_hgnc_complete_set.py`](../../scripts/fetch_hgnc_complete_set.py) | [`data/external/hgnc/hgnc_complete_set.summary.json`](../../data/external/hgnc/hgnc_complete_set.summary.json) |

The HGNC TSV used to live on `ftp.ebi.ac.uk`; that path returns 404 as of
2026-05. The Google Cloud Storage path above is what HGNC currently
serves.

## Counts as of 2026-05-11

| Quantity | Count |
|---|---:|
| NCBI total human gene records (all biotypes) | 193,868 |
| NCBI protein-coding genes (raw) | 20,624 |
| **NCBI protein-coding ∩ has HGNC xref** *(used as `WHOLE_GENOME_N`)* | **19,464** |
| HGNC total approved records (all locus groups) | 44,986 |
| HGNC approved protein-coding genes | 19,296 |
| Intersection (NCBI PC ∩ HGNC approved PC, by HGNC ID) | 19,264 |

The trimmed list lives at
[`data/external/ncbi_gene_info/Homo_sapiens.protein_coding.with_hgnc.tsv`](../../data/external/ncbi_gene_info/Homo_sapiens.protein_coding.with_hgnc.tsv)
(19,464 rows). A cross-reference annotating every NCBI protein-coding
row with its HGNC status is at
[`Homo_sapiens.protein_coding.with_hgnc_status.tsv`](../../data/external/ncbi_gene_info/Homo_sapiens.protein_coding.with_hgnc_status.tsv).

## Why we trim the raw 20,624

The 1,160 rows dropped between "raw protein-coding" and "with HGNC xref"
break down as:

| Bucket (NCBI description heuristic) | Count |
|---|---:|
| `other` (mostly `LOC*` placeholders, cadherin clusters) | 656 |
| `uncharacterized protein` | 439 |
| `putative / predicted` | 148 |
| `readthrough` (gene-fusion annotations like `BORCS8-MEF2B`) | 113 |
| `ORF / unnamed` | 3 |
| `novel` | 1 |

These are machine-predicted ORFs and readthrough fusions that HGNC has
not promoted to first-class approved symbols. Running the triage agent
on them would mostly cost API calls and return "no real literature" —
they don't belong in the whole-genome denominator.

## Why the two authorities disagree on the remaining ~200

`WHOLE_GENOME_N = 19,464` is the **NCBI** view. The stricter intersection
(rows that are *also* approved protein-coding in HGNC) is 19,264 — a
delta of 200 rows. Breaking those 200 down by what HGNC calls them
instead:

| HGNC locus_type | Count |
|---|---:|
| `readthrough` (HGNC tags as `other`, not protein-coding) | 90 |
| `complex locus constituent` | 63 |
| `unknown` | 21 |
| `RNA, long non-coding` | 12 |
| `pseudogene` | 10 |
| `endogenous retrovirus` | 2 |
| not in HGNC at all | 2 |

These are real biotype-classification disagreements. NCBI keeps them in
the protein-coding biotype because they have a translatable ORF; HGNC
demotes them based on additional evidence.

Conversely, HGNC has 32 entries it calls "approved protein-coding" that
NCBI demotes to pseudogene — mostly olfactory receptors at the
pseudogene/protein-coding boundary (`OR1E3`, `OR1P1`, `OR5G3`, …), plus
cluster identifiers (`PCDHB@`) and a few edge cases (`SLCO1B7`, `PRY2`).

## Further-trim options on top of 19,464

If a stricter denominator is needed, these are the meaningful next cuts
ranked by size:

| Filter | Drops | Resulting N | Rationale |
|---|---:|---:|---|
| Also approved-PC in HGNC (intersection) | 200 | 19,264 | Two-authority agreement; drops readthroughs and complex-locus constituents NCBI keeps but HGNC demotes. |
| Drop olfactory receptors (`OR*`) | 408 | 18,856* | Real surface proteins, but irrelevant for therapeutic-delivery triage — never a target. Biology call, not a quality call. |
| Drop hypothetical descriptions ("uncharacterized / putative / predicted / readthrough" — after the HGNC trim is applied) | ~35 | 19,229 | Most of these already get filtered by HGNC; only ~35 slip through. |
| Drop mtDNA-encoded (chromosome `MT`) | 13 | 19,451 | The 13 OXPHOS subunits encoded on mtDNA — not surface proteins by definition. |

*Cumulative on top of the intersection cut.

We are **not** applying these by default — they're each opinionated
decisions about what counts as a "real" gene to triage, and 19,464 is
the safer upper-bound for the `$/whole-genome` projection.

## Validation

A pytest at
[`tests/test_benchmark_in_whole_genome.py`](../../tests/test_benchmark_in_whole_genome.py)
asserts that every gene in `data/eval/triage_benchmark_v1.tsv` is
present in `Homo_sapiens.protein_coding.with_hgnc.tsv` (by primary
symbol or synonym), with alias drift reported but not fatal.

As of 2026-05-11 every benchmark gene resolves by **primary symbol** —
no synonym lookup needed. Two prior aliases were renamed to the NCBI
canonical form in the benchmark TSV:

- **LRRC33 → NRROS** (gene 375387) — the protein name LRRC33 is
  retained in the rationale as the legacy alias for searchability.
- **ALPPL2 → ALPG** (gene 251) — same treatment; clinical programs are
  still mostly published under "ALPPL2".

If a future NCBI refresh introduces new drift, the test will print the
old-symbol → new-symbol mapping; apply the rename to the benchmark TSV.

## Refreshing

Both files drift slowly — NCBI updates daily and HGNC roughly monthly,
but the protein-coding counts change by tens of genes per quarter, not
hundreds. To refresh:

```bash
uv run python scripts/fetch_ncbi_human_protein_coding.py
uv run python scripts/fetch_hgnc_complete_set.py
uv run pytest tests/test_benchmark_in_whole_genome.py
```

Each fetch script writes its own summary JSON with a `fetched_utc`
timestamp; compare against the values in the table above before
updating `WHOLE_GENOME_N`.
