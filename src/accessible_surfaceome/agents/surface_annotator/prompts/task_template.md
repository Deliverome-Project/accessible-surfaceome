Annotate the gene `{gene}`. Walk the `gene_lookup` cascade as described in the system prompt: resolve → db_panel → (uniprot_summary if needed) → (miss_diagnosis if a control gene was missed). Emit one `SurfaceomeRecordDraft` JSON block as your final response.

{triage_key_uncertainty_block}

{protein_features_block}

{deep_dive_block}
