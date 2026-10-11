"""Sweep the tag-site literature agent across a gene list, resumably.

One process per gene, N at a time. The unit of work is deliberately the
existing single-gene driver (`regenerate_tag_site_lit.py`) rather than an
in-process loop: a gene that dies — a parse failure, a publisher timeout, an
OOM — takes its own process with it and nothing else, and the sweep keeps its
place. A 2,000-gene run is long enough that this matters more than the startup
cost of a fresh interpreter.

RESUME IS SHA-AWARE, which is the repo's rule for any pipeline that persists an
LLM record (CLAUDE.md): a gene already archived under the CURRENT prompt_sha is
skipped, and a gene archived under a DIFFERENT one is re-run. So editing the
prompt mid-sweep does not silently leave half the cohort on the old text — it
re-runs exactly the genes that need it, with no flag to remember. The skip set
is read from private D1's `tag_site_run`, which is the same place the archive
lands, so "done" means "durably recorded", not "a file exists locally".

    uv run python scripts/sweep_tag_site_lit.py --run-id tag_site_library_v1
    uv run python scripts/sweep_tag_site_lit.py --run-id ... --parallel 8
    uv run python scripts/sweep_tag_site_lit.py --run-id ... --limit 5 --dry-run
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from accessible_surfaceome.env import load_env

load_env()

from accessible_surfaceome.agents.tag_site.prompt import (  # noqa: E402
    TAG_SITE_PROMPT_VERSION,
    prompt_sha,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GENES = ROOT / "viewer/public/data/fg-library.json"
DRIVER = ROOT / "scripts/regenerate_tag_site_lit.py"

log = logging.getLogger("sweep")
_COST = re.compile(r"COST: \$([0-9.]+)")


def load_genes(path: Path) -> list[str]:
    """Gene symbols from the FG-library JSON, or a plain one-per-line file."""
    if path.suffix == ".json":
        return sorted(json.loads(path.read_text())["genes"])
    return sorted({ln.strip() for ln in path.read_text().splitlines() if ln.strip()})


def already_done(run_id: str, sha: str) -> set[str]:
    """Genes archived under THIS prompt_sha — the sha-aware skip set.

    Scoped by prompt_sha and not by run_id: a gene correctly annotated under
    this exact prompt in an earlier sweep does not need paying for twice, and
    the provenance stamped on its record is identical either way."""
    try:
        from accessible_surfaceome.cloud.d1_client import D1Client

        with D1Client() as d1:
            rows = d1.query(
                "SELECT DISTINCT gene_symbol FROM tag_site_run WHERE prompt_sha = ?;",
                [sha],
            )
        return {r["gene_symbol"] for r in rows}
    except Exception as exc:  # noqa: BLE001 - no D1 just means nothing to skip
        log.warning("could not read the skip set from D1 (%s); running every gene", exc)
        return set()


def run_gene(
    symbol: str, *, run_id: str, log_dir: Path, env_extra: dict[str, str]
) -> dict:
    """One gene in its own process. Never raises."""
    import os

    started = time.monotonic()
    env = {**os.environ, "TAG_SITE_RUN_ID": run_id, **env_extra}
    try:
        proc = subprocess.run(
            [sys.executable, str(DRIVER), "--gene", symbol],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(ROOT),
            timeout=3600,
        )
        out, code = proc.stdout + proc.stderr, proc.returncode
    except subprocess.TimeoutExpired:
        out, code = "TIMEOUT after 3600s", 124
    except Exception as exc:  # noqa: BLE001
        out, code = f"{type(exc).__name__}: {exc}", 1
    (log_dir / f"{symbol}.log").write_text(out)
    m = _COST.search(out)
    return {
        "symbol": symbol,
        "ok": code == 0,
        "code": code,
        "cost": float(m.group(1)) if m else 0.0,
        "secs": time.monotonic() - started,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--run-id", required=True, help="groups this sweep in `tag_site_run`"
    )
    ap.add_argument("--genes-file", type=Path, default=DEFAULT_GENES)
    ap.add_argument("--parallel", type=int, default=8)
    ap.add_argument("--limit", type=int, default=0, help="first N of the pending set")
    ap.add_argument("--log-dir", type=Path, default=None)
    ap.add_argument(
        "--no-resume", action="store_true", help="re-run even archived genes"
    )
    ap.add_argument("--dry-run", action="store_true", help="print the plan and stop")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S"
    )

    sha = prompt_sha()
    genes = load_genes(args.genes_file)
    done = set() if args.no_resume else already_done(args.run_id, sha)
    pending = [g for g in genes if g not in done]
    if args.limit:
        pending = pending[: args.limit]

    log_dir = args.log_dir or (ROOT / f"data/external/tag_site_sweeps/{args.run_id}")
    log_dir.mkdir(parents=True, exist_ok=True)

    log.info("prompt %s  sha %s", TAG_SITE_PROMPT_VERSION, sha[:12])
    log.info(
        "%d genes in %s; %d already archived under this sha; %d pending",
        len(genes),
        args.genes_file.name,
        len(done),
        len(pending),
    )
    log.info("logs -> %s", log_dir)
    if args.dry_run:
        log.info("dry run; first 10 pending: %s", pending[:10])
        return 0
    if not pending:
        log.info("nothing to do")
        return 0

    lock = threading.Lock()
    tally = {"ok": 0, "fail": 0, "cost": 0.0, "n": 0}
    t0 = time.monotonic()

    with ThreadPoolExecutor(max_workers=args.parallel) as pool:
        futures = {
            pool.submit(
                run_gene, g, run_id=args.run_id, log_dir=log_dir, env_extra={}
            ): g
            for g in pending
        }
        for fut in as_completed(futures):
            r = fut.result()
            with lock:
                tally["n"] += 1
                tally["ok" if r["ok"] else "fail"] += 1
                tally["cost"] += r["cost"]
                n, total = tally["n"], len(pending)
                rate = (time.monotonic() - t0) / max(n, 1)
                eta_h = rate * (total - n) / 3600
                log.info(
                    "[%4d/%d] %-14s %-4s $%.4f %5.0fs | ok=%d fail=%d  spent=$%.2f  eta=%.1fh",
                    n,
                    total,
                    r["symbol"],
                    "ok" if r["ok"] else f"E{r['code']}",
                    r["cost"],
                    r["secs"],
                    tally["ok"],
                    tally["fail"],
                    tally["cost"],
                    eta_h,
                )

    log.info(
        "DONE %d genes: ok=%d fail=%d  total=$%.2f  wall=%.1fh",
        tally["n"],
        tally["ok"],
        tally["fail"],
        tally["cost"],
        (time.monotonic() - t0) / 3600,
    )
    return 0 if tally["fail"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
