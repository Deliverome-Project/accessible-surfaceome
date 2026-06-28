# Licensing & redistribution

This repository is MIT-licensed (see [LICENSE](LICENSE)). The MIT grant covers
the **code** in this repository. Data derived from third-party sources retains
the license of its origin; see [NOTICE.md](NOTICE.md) for the full source list.

## CC-BY-4.0 attribution requirements

UniProt, Gene Ontology, Human Protein Atlas, HGNC, AlphaFold DB are
CC-BY-4.0. Downstream users must attribute the source per the license URL.
Attribution is satisfied by the per-gene DataSourcesFooter in the viewer
and the NOTICE.md file.

## Academic / non-commercial use sources

The following sources permit academic research use; commercial use
requires permission from the upstream authors:

- CSPA (Bausch-Fluck et al. 2015, 2018)
- SURFY (Bausch-Fluck et al. 2018)
- DeepTMHMM (Hansen et al. 2022) — predictions are redistributed under
  this academic-use understanding
- SURFACE-Bind (Khakzad et al. 2024)

The derived `candidate_universe.tsv` is a composite incorporating
academic-use sources, so the composite inherits the academic-only
restriction for any field that is downstream of those sources. If your
use is commercial, contact the upstream authors for clarification.

## Fair use of evidence snippets

`viewer/public/data/surfaceome/*.json` records contain verbatim quotes
(20–100 words each) drawn from primary literature. Each is attributed to
its source publication (PubMed ID, author, year). Reproduction is
intended as scholarly annotation under fair use; quotes are short, used
for the purpose of commentary, and do not substitute for the original.

## Fonts

Manrope and Playfair Display are bundled under the SIL Open Font License
1.1 — see https://openfontlicense.org for terms.
