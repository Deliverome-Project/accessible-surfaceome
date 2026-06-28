# scripts/probes/

Validation probes that touch the network but make no model calls (`$0` to
run). Use these to debug the triage body-fetch chain (Unpaywall + PMC +
PDF fallback), the Open Access coverage bucketing, or the on-disk cache
engagement of the agent runs. Each probe writes a short diagnostic report
to stdout / `data/external/` — no D1 writes.
