# scripts/tsv-export/

Augment public TSVs with stable identifiers (HGNC ID, Ensembl gene,
UniProt acc, NCBI gene ID) and denormalize the most-common reanalysis
joins so an external reader can answer typical questions in one filter
instead of a 3-way join. The augment script joins each figure-input TSV
against `gene_identifier_public` + `benchmark_version`. Per CLAUDE.md, run
this after any of the four figure TSVs are regenerated.
