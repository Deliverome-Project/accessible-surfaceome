# scripts/cloud/

Cloudflare edge configuration + exports from the public Worker. The catalog
TSV exports under here re-read from the *public* D1 mirror (not private) so
that the citable distribution channel and the API channel never drift.
