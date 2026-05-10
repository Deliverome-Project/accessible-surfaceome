Triage the human gene **{gene}**.

Canonical identifiers and gene summary (machine-resolved from HGNC and NCBI; no further lookups available — judge from the context below plus your trained knowledge):

- HGNC approved name: {approved_name}
- HGNC symbol: {hgnc_symbol}
- UniProt accession: {uniprot_acc}
- Aliases: {aliases}
- Previous symbols: {previous_symbols}
- NCBI summary: {ncbi_summary}

Emit one JSON object matching the `TriageRecordDraft` schema as your **entire** response — no prose around it, no markdown code fences, no commentary. Required keys: `verdict`, `verdict_reasoning`, `reason`.
