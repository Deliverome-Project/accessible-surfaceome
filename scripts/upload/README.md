# scripts/upload/

Sync builders' outputs to D1 (Cloudflare's serverless SQL store), R2
(object storage backup target), and the published figure gists. Each
`upload_*` and `sync_*` script reads a snapshot from `data/processed/` or
the live D1 mirror and pushes to a destination.

Most are idempotent UPSERTs keyed on a stable identifier (e.g. `hgnc_id`,
`uniprot_acc`); a few `.sh` runners coordinate batched backfill sweeps.
