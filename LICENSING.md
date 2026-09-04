# Licensing and redistribution

This project integrates ~15 public data sources into a derived catalogue of
human cell-surface proteins. The **code** is MIT (see `LICENSE`). The **derived
data** shipped in this repository (candidate-universe TSVs, per-gene deep-dive
records, figure TSVs) is distributed under CC BY 4.0 via the Zenodo deposit
(concept DOI `10.5281/zenodo.20805383`).

This file records the upstream license for each source, what we use it for, and
whether any upstream payload is redistributed here. Attribution strings shown to
end users are generated per-record by
`viewer/components/surfaceome/DataSourcesFooter/DataSourcesFooter.tsx` and the
recurring-citation registry `viewer/lib/citations.ts`.

> **License-verification status.** Entries marked **verify** below have a
> redistribution term this review has **not** independently confirmed against
> the source's current terms. Do not treat a **verify** row as a cleared
> redistribution until it is checked. We ship **derived values**, not bulk
> upstream dumps, for every source; that reduces but does not eliminate the
> obligation to honor each source's terms (notably HPA's share-alike).

## What we redistribute vs. what we don't

- **Redistributed (derived):** per-gene flags, scores, identifiers, topology
  predictions, and short coded reasons — computed from the sources below and
  committed under `data/processed/**`, `data/annotations/**`, and the figure
  TSVs. These are transformations, not verbatim copies of upstream databases.
- **NOT redistributed (gitignored, never committed):** the copyright-risky
  retrieval caches —
  - `data/external/blob_cache/` — publisher / OA PDFs fetched during triage.
  - `tool_cache/` — Serper / Google search payloads.
  - PubTator3 and other full-text retrieval caches.
  These are `.gitignore`d and excluded from every published artifact and Zenodo
  deposit. Full model reasoning prose likewise stays in private D1, not in the
  shipped TSVs.

## Per-source table

| Source | Used for | Upstream license | Redistributed here? | Attribution |
|---|---|---|---|---|
| **UniProt** | Sequences, xrefs, ECD features, protein families, canonical isoform | CC BY 4.0 | Derived values only (identifiers, feature-derived flags) | UniProt Consortium |
| **Gene Ontology (GO)** | Localization / surface GO-term evidence | CC BY 4.0 | Derived flags only | GO Consortium (Ashburner et al. 2000; GO Consortium 2023) |
| **HGNC** | Gene-symbol ↔ stable-ID resolution (the `gene_identifier` table) | Free to use, EMBL-EBI/HGNC terms — **verify** redistribution specifics | Identifiers only (hgnc_id, symbol, prev/alias) | HGNC (Seal et al. 2023) |
| **Ensembl Compara** | Ortholog / paralog relationships + ortholog ECD identity | Open (EMBL-EBI, "no restrictions" + citation requested) — **verify** exact redistribution term | Derived ortholog/paralog tables | EMBL-EBI (Howe et al. 2024; Vilella et al. 2009) |
| **Human Protein Atlas (HPA)** | Subcellular localization + expression → surface & tumor evidence | **CC BY-SA 4.0 — share-alike** ⚠️ | Derived flags | Human Protein Atlas (Uhlén et al. 2015; Thul et al. 2017) |
| **Cell Surface Protein Atlas (CSPA)** | Experimental cell-surface membership evidence | Academic-use terms — **verify** | Membership flags | Bausch-Fluck et al. 2015 (Wollscheid lab) |
| **SURFY** | Machine-learning surfaceome prediction (SURFY score) | Published as **PNAS supplementary data** — reuse terms **verify (confirm)** | SURFY scores/flags in the candidate universe | Bausch-Fluck et al. 2018 (PNAS) |
| **JensenLab COMPARTMENTS** | Subcellular-localization confidence | CC BY 4.0 — **verify** | Derived flags | Binder et al. 2014 (JensenLab) |
| **DeepTMHMM** | Transmembrane-topology predictions (`canonical_topology`) | **DeepTMHMM academic license v1.0 (DTU Health Tech)** — we run the tool; predictions are derived — **verify** redistribution of derived predictions | Derived topology records (tool pinned `deeptmhmm-1.0.24`) | Hallgren et al. 2022 (bioRxiv 10.1101/2022.04.08.487609) |
| **AlphaFold DB** | 3D structures → pLDDT, ECD geometry, structure viewer | CC BY 4.0 | Derived values; cached structures live in R2 (not git) | AlphaFold DB (Jumper et al. 2021; Varadi et al. 2022) |
| **Schweke homo-oligomer atlas** | Homo-oligomer assembly predictions | **figshare deposit (private-share link)** — likely CC BY but **verify (confirm)** | Derived flags; ingested PDBs live in R2 (not git) | Schweke et al. 2024, Cell (PMID 38325366) |
| **SURFACE-Bind** | MaSIF-based binding-site patch scoring on the AlphaFold model | Resource terms (INRIA, surface-bind.inria.fr) — **verify** | Derived patch scores | Balbi et al. 2026, PNAS (PMID 41604262) |
| **ADCdb** | ADC-target positive-control list | Database terms — **verify (confirm)** | Gene-list membership only | ADCdb (Shen et al. 2024, NAR) |
| **OpenCell** | Localization / expression evidence | CC BY 4.0 — **verify (confirm)** | Derived flags | OpenCell / CZ Biohub (Cho et al. 2022, Science) |
| **ViralZone** | Viral-receptor positive-control list | SIB / Expasy terms — **verify (confirm)** | Gene-list membership only | ViralZone / SIB (Hulo et al. 2011) |

## Before publishing a new cached corpus or export

1. Confirm the current redistribution terms for each source touched by the new
   artifact (the **verify** rows above are unresolved).
2. For **HPA** specifically: its **CC BY-SA 4.0** share-alike term can attach to
   derivatives that substantially incorporate HPA data — confirm whether a given
   export triggers share-alike before shipping it under CC BY 4.0.
3. Never add any `data/external/blob_cache/`, `tool_cache/`, or PubTator payload
   to a committed or deposited artifact.
