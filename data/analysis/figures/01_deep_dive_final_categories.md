# Deep-dive final categorization — MOCK / placeholder

**MOCK figure.** Distribution of the ~5k surface candidates across the
five final-classification buckets the v2 deep-dive emits:

- **canonical** — `filters.surface_call_reason` ∈
  *classical_surface_receptor* / *multipass_with_exposed_loops* /
  *gpi_anchored* / *extracellular_face_protein* /
  *stable_complex_partner*
- **likely** — soft-contextual reasons: *stable_surface_attachment* /
  *lysosomal_exocytosis* / *dual_localization*
- **cell-state induced** — `surface_call_reason == 'cell_state_induced'`,
  broken out by `filters.induction_trigger` (oncogenic / immune /
  stress_hypoxia / cell_death / infection / other)
- **cell-type restricted** — `surface_call_reason ==
  'tissue_restricted_surface'`
- **below threshold** — *cytoplasmic* / *nuclear* /
  *mitochondrial_internal* / *endomembrane_resident* / *secreted_only* /
  *nuclear_envelope* / *pmhc_only_intracellular*

Counts are placeholder estimates eyeballed from the 14 committed
deep-dive records under `viewer/public/data/surfaceome/` plus typical
surfaceome literature. The figure will be regenerated against real D1
counts once the v2 sweep
(`scripts/surfaceome_v2_annotate.py`) completes over the ~5k
Sonnet-triage YES cohort. The bucket boundaries themselves are pinned
by the closed enums in `models.py` (`TriageReason` and
`InductionTrigger`) and will not change between MOCK and real.

Run:

```
uv run make_deep_dive_final_categories.py
```

Schema source (closed enums for the bucket assignment):
[`src/accessible_surfaceome/tools/_shared/models.py`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/src/accessible_surfaceome/tools/_shared/models.py)
(`TriageReason`, `InductionTrigger`, `_YES_REASONS`,
`_CONTEXTUAL_REASONS`, `_NO_REASONS`).

Canonical in-repo generator:
[`scripts/deep_dive_final_categories.py`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/scripts/deep_dive_final_categories.py).
