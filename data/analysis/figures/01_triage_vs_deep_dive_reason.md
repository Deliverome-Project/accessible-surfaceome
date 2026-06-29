# `triage_vs_deep_dive_reason` — MOCK / placeholder

**MOCK figure.** Appendix Figure 10. For each gene in the deep-dive
cohort there are two reason calls drawn from the SAME closed enum
``TriageReason`` (in `src/accessible_surfaceome/tools/_shared/models.py`):

- One emitted by the triage agent
  (`triage_run.reason` in D1).
- One emitted by the deep-dive agent
  (`filters.surface_call_reason` in the per-gene record).

The figure is a confusion matrix with both axes drawn from the same
19-value enum. The 19 reasons collapse into 3 triage buckets:

- **_YES_REASONS** — classical_surface_receptor, gpi_anchored,
  multipass_with_exposed_loops, extracellular_face_protein,
  stable_complex_partner
- **_CONTEXTUAL_REASONS** — cell_state_induced,
  tissue_restricted_surface, lysosomal_exocytosis, dual_localization,
  stable_surface_attachment
- **_NO_REASONS** — cytoplasmic, nuclear, mitochondrial_internal,
  endomembrane_resident, nuclear_envelope, secreted_only,
  pmhc_only_intracellular

Visualisation:

- **Rows** = triage reason (top → bottom: yes-bucket, contextual-bucket,
  no-bucket; ordered within bucket by display frequency).
- **Cols** = deep-dive reason (same ordering left → right).
- **Cell** = number of genes with that (triage, deep-dive) pair,
  annotated inline; greyscale-sequential intensity by count.
- **Axis ticks** coloured by their reason's bucket (yes=green,
  contextual=amber, no=neutral).
- **Diagonal** (perfect reason-level agreement) outlined in maroon.
- **Thick bucket-boundary lines** between yes/contextual/no on each axis.

Counts are **placeholder estimates** pending the v2 deep-dive sweep
joining onto the `triage_run` table. Heavy diagonal + small
off-diagonal spread is the expected shape (deep-dive mostly confirms
the triage reason; within-bucket reassignments outnumber cross-bucket
flips). Swap `_MOCK_COUNTS` for a public-D1 SELECT once the v2 sweep
lands:

```sql
SELECT t.reason AS triage_reason,
       json_extract(a.annotation_json, '$.filters.surface_call_reason')
         AS dd_reason,
       COUNT(*) AS n
FROM triage_run_public t
JOIN surface_annotation a ON a.gene_symbol = t.gene_symbol
WHERE t.run_id = 'genome_full_sonnet_ncbi_v1'
GROUP BY 1, 2;
```

## Run

```sh
uv run make_triage_vs_deep_dive_reason.py
```

Schema source (closed enums for the bucket assignment):
[`src/accessible_surfaceome/tools/_shared/models.py`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/src/accessible_surfaceome/tools/_shared/models.py)
(`TriageReason`, `_YES_REASONS`, `_CONTEXTUAL_REASONS`,
`_NO_REASONS`).

Canonical in-repo generator:
[`scripts/triage_vs_deep_dive_reason.py`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/scripts/triage_vs_deep_dive_reason.py).
