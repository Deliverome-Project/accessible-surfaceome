"""Sweep the tag-site literature agent across a gene list or a MEMBER list, resumably.

One process per work unit, N at a time. The unit of work is deliberately an
existing single-unit driver rather than an in-process loop: a unit that dies — a
parse failure, a publisher timeout, an OOM — takes its own process with it and
nothing else, and the sweep keeps its place. A 2,000-unit run is long enough
that this matters more than the startup cost of a fresh interpreter.

TWO KINDS OF UNIT, because the two passes are keyed differently:

* ``--genes-file`` (default) drives ``regenerate_tag_site_lit.py`` per GENE,
  numbering against the public record's canonical topology. Resume reads
  private D1's ``tag_site_run``.
* ``--members-file`` drives ``enrich_tag_site_lit.py`` per library MEMBER,
  numbering against the member's own translated sequence. Resume reads public
  D1's ``tag_site_gene_public`` on ``(gene_symbol, candidate_id)``.

The key spaces must not be mixed. 45 of the 518 internal-site genes have more
than one member, so a gene-keyed skip set applied to members would strand every
sibling — and since the first pass has already searched those genes, it would
strand essentially all of them.

RESUME IS SHA-AWARE in both modes, which is the repo's rule for any pipeline
that persists an LLM record (CLAUDE.md): a unit already archived under the
CURRENT prompt_sha is skipped, and one archived under a DIFFERENT one is
re-run. So editing the prompt mid-sweep does not silently leave half the cohort
on the old text — it re-runs exactly the units that need it, with no flag to
remember. "Done" means durably recorded in D1, not that a local file exists.

    uv run python scripts/sweep_tag_site_lit.py --run-id tag_site_library_v1
    uv run python scripts/sweep_tag_site_lit.py --run-id ... --parallel 8
    uv run python scripts/sweep_tag_site_lit.py --run-id tag_site_enrichment_v1 \
        --members-file data/tag_sites/l1_internal_members.tsv --dry-run
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
from dataclasses import dataclass, field
from pathlib import Path

from accessible_surfaceome.env import load_env

load_env()

from accessible_surfaceome.agents.tag_site.member_frames import (  # noqa: E402
    load_members,
)
from accessible_surfaceome.agents.tag_site.prompt import (  # noqa: E402
    TAG_SITE_PROMPT_VERSION,
    prompt_sha,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GENES = ROOT / "viewer/public/data/fg-library.json"
GENE_DRIVER = ROOT / "scripts/regenerate_tag_site_lit.py"
ENRICH_DRIVER = ROOT / "scripts/enrich_tag_site_lit.py"

#: The run_series each mode writes under. These are the strings that end up in
#: ``tag_site_gene_public.run_series``, so they are also what the resume reads.
FIRST_PASS_SERIES = "literature_v1"
ENRICHED_SERIES = "literature_enriched_v1"

log = logging.getLogger("sweep")
_COST = re.compile(r"COST: \$([0-9.]+)")


@dataclass(frozen=True)
class Unit:
    """One unit of work: what to run, and what "already done" means for it.

    ``key`` is the resume key and its TYPE carries the mode — a bare symbol for
    a gene, a ``(gene, candidate_id)`` pair for a member. Keeping them in one
    set would let a finished gene satisfy an unstarted member of it.
    """

    label: str  #: names the log line and the log file
    gene: str  #: for reporting only
    driver: Path
    args: list[str] = field(default_factory=list)
    key: tuple[str, str] | str = ""


def load_genes(path: Path) -> list[str]:
    """Gene symbols from the FG-library JSON, or a plain one-per-line file."""
    if path.suffix == ".json":
        return sorted(json.loads(path.read_text())["genes"])
    return sorted({ln.strip() for ln in path.read_text().splitlines() if ln.strip()})


def gene_units(path: Path) -> list[Unit]:
    return [
        Unit(label=g, gene=g, driver=GENE_DRIVER, args=["--gene", g], key=g)
        for g in load_genes(path)
    ]


def member_units(path: Path) -> list[Unit]:
    """One unit per library member, read through the driver's own loader.

    Sharing ``load_members`` with ``enrich_tag_site_lit.py`` is deliberate: a
    column added to the vendored table cannot leave the sweep enumerating a
    different set from the driver it invokes.
    """
    return [
        Unit(
            label=m.candidate_id,
            gene=m.gene_symbol,
            driver=ENRICH_DRIVER,
            args=["--candidate-id", m.candidate_id],
            key=(m.gene_symbol, m.candidate_id),
        )
        for m in sorted(load_members(path), key=lambda m: m.candidate_id)
    ]


def pending(units: list[Unit], done: set) -> list[Unit]:
    """The units whose exact resume key is not in ``done``."""
    return [u for u in units if u.key not in done]


def genes_already_done(sha: str) -> set[str]:
    """Genes archived under THIS prompt_sha — the first pass's skip set.

    Scoped by prompt_sha and not by run_id: a gene correctly annotated under
    this exact prompt in an earlier sweep does not need paying for twice, and
    the provenance stamped on its record is identical either way."""
    from accessible_surfaceome.cloud.d1_client import D1Client

    with D1Client() as d1:
        rows = d1.query(
            "SELECT DISTINCT gene_symbol FROM tag_site_run WHERE prompt_sha = ?;",
            [sha],
        )
    return {r["gene_symbol"] for r in rows}


def members_already_done(sha: str, run_series: str) -> set[tuple[str, str]]:
    """``(gene, candidate_id)`` searched in this series under THIS prompt_sha.

    Public D1 rather than the private run archive, because this table is the
    one that records a search which found NOTHING — the majority outcome, and
    the case a site-derived skip set would re-run and re-pay for every time."""
    from accessible_surfaceome.cloud.d1_client import D1Client
    from accessible_surfaceome.cloud.tag_site_genes import searched_members

    with D1Client.public() as pub:
        return searched_members(pub, run_series=run_series, prompt_sha=sha)


def done_keys(*, sha: str, run_series: str, members: bool) -> set:
    """The skip set for this mode, or an empty one if D1 cannot be read.

    A missing skip set costs money (every unit re-runs) but cannot corrupt
    anything, since every write is an UPSERT on its own key — so a warning and
    a full run is the right failure, not a refusal."""
    try:
        return (
            members_already_done(sha, run_series) if members else genes_already_done(sha)
        )
    except Exception as exc:  # noqa: BLE001 - no D1 just means nothing to skip
        log.warning("could not read the skip set from D1 (%s); running every unit", exc)
        return set()


def run_unit(
    unit: Unit,
    *,
    run_id: str,
    run_series: str,
    log_dir: Path,
    env_extra: dict[str, str],
) -> dict:
    """One unit in its own process. Never raises."""
    import os

    started = time.monotonic()
    env = {
        **os.environ,
        "TAG_SITE_RUN_ID": run_id,
        "TAG_SITE_RUN_SERIES": run_series,
        **env_extra,
    }
    try:
        proc = subprocess.run(
            [sys.executable, str(unit.driver), *unit.args],
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
    # Named for the unit, not the gene: two members of one gene would otherwise
    # overwrite each other's log, and the log is the only place a failed run's
    # reason survives.
    (log_dir / f"{unit.label}.log").write_text(out)
    m = _COST.search(out)
    return {
        "label": unit.label,
        "gene": unit.gene,
        "ok": code == 0,
        "code": code,
        "cost": float(m.group(1)) if m else 0.0,
        "secs": time.monotonic() - started,
    }


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--run-id", required=True, help="groups this sweep in `tag_site_run`"
    )
    ap.add_argument("--genes-file", type=Path, default=None)
    ap.add_argument(
        "--members-file",
        type=Path,
        default=None,
        help="sweep library MEMBERS through the enrichment driver instead of genes",
    )
    ap.add_argument(
        "--run-series",
        default=None,
        help=f"defaults to {ENRICHED_SERIES!r} with --members-file, "
        f"{FIRST_PASS_SERIES!r} otherwise",
    )
    ap.add_argument("--parallel", type=int, default=8)
    ap.add_argument("--limit", type=int, default=0, help="first N of the pending set")
    ap.add_argument("--log-dir", type=Path, default=None)
    ap.add_argument(
        "--no-resume", action="store_true", help="re-run even archived units"
    )
    ap.add_argument("--dry-run", action="store_true", help="print the plan and stop")
    return ap


def resolve_series(args: argparse.Namespace) -> str:
    """The series this sweep writes under.

    A members sweep does NOT inherit the first pass's series. The series the
    sweep hands down is the one the child writes, so inheriting it would file
    member rows into the pass this one promised not to touch — and the member
    resume, which is scoped by series, would then never match them."""
    if args.run_series:
        return args.run_series
    return ENRICHED_SERIES if args.members_file else FIRST_PASS_SERIES


def main() -> int:
    args = build_parser().parse_args()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S"
    )
    if args.members_file and args.genes_file:
        log.error("pass --genes-file or --members-file, not both")
        return 2

    sha = prompt_sha()
    series = resolve_series(args)
    members_mode = args.members_file is not None
    source = args.members_file or args.genes_file or DEFAULT_GENES
    units = member_units(source) if members_mode else gene_units(source)

    done = set() if args.no_resume else done_keys(
        sha=sha, run_series=series, members=members_mode
    )
    todo = pending(units, done)
    if args.limit:
        todo = todo[: args.limit]

    log_dir = args.log_dir or (ROOT / f"data/external/tag_site_sweeps/{args.run_id}")
    log_dir.mkdir(parents=True, exist_ok=True)

    log.info("prompt %s  sha %s  series %s", TAG_SITE_PROMPT_VERSION, sha[:12], series)
    log.info(
        "%d %s in %s; %d already archived under this sha; %d pending",
        len(units),
        "member(s)" if members_mode else "gene(s)",
        source.name,
        len(done),
        len(todo),
    )
    log.info("logs -> %s", log_dir)
    if args.dry_run:
        log.info("dry run; first 10 pending: %s", [u.label for u in todo[:10]])
        return 0
    if not todo:
        log.info("nothing to do")
        return 0

    lock = threading.Lock()
    tally = {"ok": 0, "fail": 0, "cost": 0.0, "n": 0}
    t0 = time.monotonic()

    with ThreadPoolExecutor(max_workers=args.parallel) as pool:
        futures = {
            pool.submit(
                run_unit,
                u,
                run_id=args.run_id,
                run_series=series,
                log_dir=log_dir,
                env_extra={},
            ): u
            for u in todo
        }
        for fut in as_completed(futures):
            r = fut.result()
            with lock:
                tally["n"] += 1
                tally["ok" if r["ok"] else "fail"] += 1
                tally["cost"] += r["cost"]
                n, total = tally["n"], len(todo)
                rate = (time.monotonic() - t0) / max(n, 1)
                eta_h = rate * (total - n) / 3600
                log.info(
                    "[%4d/%d] %-14s %-4s $%.4f %5.0fs | ok=%d fail=%d  spent=$%.2f  eta=%.1fh",
                    n,
                    total,
                    r["label"],
                    "ok" if r["ok"] else f"E{r['code']}",
                    r["cost"],
                    r["secs"],
                    tally["ok"],
                    tally["fail"],
                    tally["cost"],
                    eta_h,
                )

    log.info(
        "DONE %d units: ok=%d fail=%d  total=$%.2f  wall=%.1fh",
        tally["n"],
        tally["ok"],
        tally["fail"],
        tally["cost"],
        (time.monotonic() - t0) / 3600,
    )
    return 0 if tally["fail"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
