"""Back the literature cache up to R2, split by what may be redistributed.

The discovery cache is ~350 MB of derived data that lives on exactly one
laptop, is in no backup, and is what makes a rescue analysis free: `build_pool`
is deterministic over it, so the exact clip pool a run saw rebuilds with no
model calls. Losing it means re-paying for every answer it could have given.

It is uploaded in TWO halves, because the two halves carry different rights:

* **public** (`surfaceome-litcache`) — papers flagged ``is_pmc_oa``. The PMC
  Open Access subset exists to be redistributed in bulk; that is its purpose.
  78,898 papers, ~117 MB.
* **private** (`surfaceome-litcache-private`) — everything else. 46,043 papers,
  ~62 MB of publisher full text that we are licensed to READ, not to republish.
  Durable, backed up, not public.

The split is on the flag the fetcher already recorded, so it cannot drift from
what was actually fetched. Bibliographic metadata for BOTH halves is already
public in D1's ``tag_site_paper_public`` — the accession travels even when the
body does not, which is what keeps the private half re-fetchable by anyone who
has their own access.

    uv run python scripts/cloud/upload_litcache_to_r2.py            # dry run
    uv run python scripts/cloud/upload_litcache_to_r2.py --execute
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from accessible_surfaceome.env import load_env

load_env()

from accessible_surfaceome.cloud.r2_client import R2Config, put_object  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DISCOVERY = ROOT / "data/external/tag_site_discovery"
TRIAGE = ROOT / "data/external/tag_site_triage"

PUBLIC_BUCKET = "surfaceome-litcache"
PRIVATE_BUCKET = "surfaceome-litcache-private"

log = logging.getLogger("litcache")

#: Transport faults under concurrency are common enough here to need a retry;
#: four attempts with exponential backoff cleared them.
_ATTEMPTS = 4
_BACKOFF_S = 1.5

_README = """# surfaceome-litcache

Per-gene literature cache for the tag-site literature agent
(github.com/Deliverome-Project/accessible-surfaceome).

`{GENE}.json` holds the papers discovered for that gene, each with its
accession, bibliography, triage verdict, and cached text.

**This bucket contains only papers in the PMC Open Access subset**
(`is_pmc_oa = true`), which is distributed for bulk reuse. Papers outside it
are held privately and are NOT here; their bibliography and triage verdict are
still public in the API's `tag_site_paper_public` table, so the citation is
always resolvable even when the body is not included.

Regenerate or extend with `scripts/cloud/upload_litcache_to_r2.py`.
"""


def split_gene(gene: str) -> tuple[dict, dict]:
    """(oa_papers, closed_papers) for one gene, verdicts folded in."""
    try:
        papers = json.loads((DISCOVERY / f"{gene}.json").read_text())
    except Exception:  # noqa: BLE001
        return {}, {}
    try:
        verdicts = json.loads((TRIAGE / f"{gene}.json").read_text())
    except Exception:  # noqa: BLE001
        verdicts = {}
    oa: dict = {}
    closed: dict = {}
    for sid, p in papers.items():
        rec = dict(p)
        v = verdicts.get(sid) or {}
        rec["triage_decision"] = v.get("decision")
        rec["triage_reason"] = v.get("reason")
        (oa if p.get("is_pmc_oa") else closed)[sid] = rec
    return oa, closed


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--parallel", type=int, default=8)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    genes = sorted(p.stem for p in DISCOVERY.glob("*.json"))
    jobs: list[tuple[str, str, bytes]] = []
    oa_n = cl_n = 0
    for g in genes:
        oa, closed = split_gene(g)
        if oa:
            body = json.dumps(oa, separators=(",", ":")).encode()
            jobs.append((PUBLIC_BUCKET, f"{g}.json", body))
            oa_n += len(oa)
        if closed:
            body = json.dumps(closed, separators=(",", ":")).encode()
            jobs.append((PRIVATE_BUCKET, f"{g}.json", body))
            cl_n += len(closed)

    pub = [j for j in jobs if j[0] == PUBLIC_BUCKET]
    prv = [j for j in jobs if j[0] == PRIVATE_BUCKET]
    log.info(
        "public  %s: %d objects, %d papers, %.0f MB",
        PUBLIC_BUCKET,
        len(pub),
        oa_n,
        sum(len(j[2]) for j in pub) / 1e6,
    )
    log.info(
        "private %s: %d objects, %d papers, %.0f MB",
        PRIVATE_BUCKET,
        len(prv),
        cl_n,
        sum(len(j[2]) for j in prv) / 1e6,
    )
    if not args.execute:
        log.info("dry run — nothing uploaded (pass --execute)")
        return 0

    jobs.append((PUBLIC_BUCKET, "README.md", _README.encode()))

    cfgs = {
        PUBLIC_BUCKET: R2Config.from_env(bucket=PUBLIC_BUCKET),
        PRIVATE_BUCKET: R2Config.from_env(bucket=PRIVATE_BUCKET),
    }

    def up(job: tuple[str, str, bytes]) -> bool:
        """One object, retried. A PUT is idempotent on its key, so a retry can
        only overwrite with identical bytes.

        The first run lost 1,450 of 3,674 objects to
        SSLV3_ALERT_BAD_RECORD_MAC — transport flakiness from opening many TLS
        connections at once, not a bad payload. put_object swallows the error
        and returns False, so without a retry here a transient fault became a
        permanent hole in the backup."""
        bucket, key, body = job
        ct = "text/markdown" if key.endswith(".md") else "application/json"
        for attempt in range(_ATTEMPTS):
            if put_object(key=key, body=body, content_type=ct, cfg=cfgs[bucket]):
                return True
            if attempt + 1 < _ATTEMPTS:
                time.sleep(_BACKOFF_S * (2**attempt))
        log.warning("  giving up on %s/%s after %d attempts", bucket, key, _ATTEMPTS)
        return False

    ok = fail = 0
    with ThreadPoolExecutor(max_workers=args.parallel) as pool:
        futs = [pool.submit(up, j) for j in jobs]
        for i, f in enumerate(as_completed(futs), 1):
            if f.result():
                ok += 1
            else:
                fail += 1
            if i % 400 == 0:
                log.info("  %d/%d objects (ok=%d fail=%d)", i, len(jobs), ok, fail)
    log.info("uploaded %d objects, %d failed", ok, fail)
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
