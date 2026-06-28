# Positive-control database coverage — three orthogonal target lists

Three-panel bar chart showing how the five gating surface databases and the
Sonnet triage agent cover three orthogonal positive-control target lists.
Each panel is one target list; each bar is one source. Y-axis ceiling is the
panel's own n_total.

* **Panel a — ADC targets** (n = 62). Union of TheraSAbDab antibody-drug
  conjugates ([opig.stats.ox.ac.uk/webapps/sabdab-sabpred/therasabdab](https://opig.stats.ox.ac.uk/webapps/sabdab-sabpred/therasabdab/))
  and Open Targets 26.06 antibody-drug-conjugate MoA targets, HGNC-resolved,
  with non-cytotoxic conjugates (tedromer / celmoleukin / cafraglutide) and
  Open Targets family-expansion attributions filtered out.
* **Panel b — TCE targets** (n = 34). TheraSAbDab CD3-binding bispecifics +
  BiTE/DART platform-tagged therapeutics, HGNC-resolved.
* **Panel c — ViralZone entry receptors** (n = 62). Human cell-surface viral
  entry receptors from [ViralZone](https://viralzone.expasy.org/5356) (Expasy),
  UniProt-resolved.

Sonnet bar = positive in the combined dual NCBI triage (runs
`genome_full_sonnet_ncbi_v1` ∪ `_v2`, verdict `yes` OR `contextual`).
The PubMed-augmented variant is a separate exploration, not part of the
combined axis.

Run:

```
uv run make_positive_control_db_coverage_bars.py
```

Sources:

- Input TSVs (augmented with HGNC IDs + 5-DB flags + Sonnet flag, fetched
  from raw GitHub when the gist runs standalone, sibling-files when bundled
  in the gist):
  - [data/processed/positive_controls/positive_control_ADC.tsv](https://raw.githubusercontent.com/Deliverome-Project/accessible-surfaceome/main/data/processed/positive_controls/positive_control_ADC.tsv)
  - [data/processed/positive_controls/positive_control_TCE.tsv](https://raw.githubusercontent.com/Deliverome-Project/accessible-surfaceome/main/data/processed/positive_controls/positive_control_TCE.tsv)
  - [data/processed/positive_controls/positive_control_VZ.tsv](https://raw.githubusercontent.com/Deliverome-Project/accessible-surfaceome/main/data/processed/positive_controls/positive_control_VZ.tsv)
- Permanent data archive (Zenodo): [10.5281/zenodo.20805384](https://doi.org/10.5281/zenodo.20805384)

Canonical in-repo generator:
[`scripts/positive_control_db_coverage_bars.py`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/scripts/positive_control_db_coverage_bars.py)

Upstream list builder (refreshes the input TSVs from TheraSAbDab + Open
Targets + ViralZone):
[`scripts/build_positive_control_lists.py`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/scripts/build_positive_control_lists.py)
