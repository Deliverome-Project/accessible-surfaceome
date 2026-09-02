# Tedman GPCR HA control tag sites

Screen-validated tag-site table for GPCR N-terminal HA insertions.
Machine-readable source is `tedman_gpcr_controls.tsv`, built by
`scripts/build_tedman_gpcr_controls.py` from the two staged inputs in
`data/external/tedman_gpcr_screen/`:

```bash
uv run python scripts/build_tedman_gpcr_controls.py
```

**Provenance.** Source is the GPCR deep-receptor-scanning HA-tag screen,
Tedman et al., *Nat Commun* 2026, doi:10.1038/s41467-026-76564-7 (bioRxiv
2025.09.19.677468 = PMC12458215). The HA-insertion positions come from the
Mendeley Data plasmid-map deposit (10.17632/3b4n36z4bg, "Doc S1. GPCR Plasmid
Maps"); surface-expression values come from
`deliverome-external://tedman-gpcr-surface-screen/2025-09-19/`
(byte-identical immunostaining columns to the deposit's "Doc S2. GPCR DRS
Master Table.xlsx"). Full input provenance, checksums, and access paths are
in `data/external/tedman_gpcr_screen/PROVENANCE.md`.

**Join key.** Rows are joined between the plasmid-map index
(`GPCR_Library_Index_Final.xlsx`) and the surface-expression screen
(`tedman2025_gpcr_screen_media-2.xlsx`, sheet `Canonical`) on `Receptor Name`,
which is `SYMBOL_ENST` (e.g. `ACKR1_ENST00000368122`) — the symbol plus the
Ensembl transcript ID of the specific plasmid construct, since the screen
covers both canonical and non-canonical isoforms per gene.

**Junction convention.** Matches `positive_controls.md`: `after N` means the
tag sits between canonical residues `N` and `N+1` (UniProt numbering,
resolved via the HGNC-ID path per `resolve_by_hgnc_id`, never a bare gene
symbol). An empty `junction_after_residue` means a bare N-terminal insertion
— the HA tag sits before residue 1, upstream of the native (or absent)
signal peptide. Junctions are projected from the construct's own
`ha_insert_position` numbering onto canonical UniProt numbering and
mechanically verified against the canonical sequence
(`verified=true` iff the projected residue index falls within
`1..len(canonical_seq)` and the accession resolved).

**`surface_expression_pme`** is the HA-immunostaining plasma-membrane
expression intensity from the Tedman screen (arbitrary fluorescence units,
`Immunostaining Intensity` in the source sheet), with
`surface_expression_sd` its standard deviation. This is a functional readout
of whether the tagged construct reaches the cell surface — not itself a
verification that the tag sits at the stated residue, which is handled by
the `verified` column above.

**Separate from `positive_controls.tsv` by design.** This table is
`screen_validated` provenance (a systematic HA-insertion screen across ~950
GPCR constructs) — categorically different from the hand-curated,
one-tag-at-a-time literature evidence in `positive_controls.tsv`
(`source_key=tedman2026` here vs. per-paper source keys there). It is kept
as its own file and is **not** appended to `positive_controls.tsv`; any
downstream benchmark that wants to combine the two must do so explicitly
and should not conflate "screen-validated at scale" with "individually
published and scrutinized."
