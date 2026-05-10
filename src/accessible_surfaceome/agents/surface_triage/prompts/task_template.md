Triage the human gene **{gene}**.

Emit one JSON object matching the `TriageRecordDraft` schema as your **entire** response — no prose around it, no markdown code fences, no commentary. Required keys: `verdict`, `verdict_reasoning`, `reason`. Include `reason_other_label` only when `reason: "other"`.
