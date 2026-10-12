"""Retune the surface-loop lane for RECALL of published junctions. TRAIN ONLY.

The tag-site benchmark says the surface-loop lane's problem is not where it
pins a tag but how few loops it proposes. Of 197 published internal junctions
it covers 21%: when the junction IS inside a proposed loop the pin is off by a
median of 9 aa (inside the 11 aa median feature), but the lane offers a median
of only 3 loops per protein — about 7% of a 500 aa protein — and the junction
usually sits in a loop it never proposed. 46% of misses are a different loop,
nearest proposed edge a median 65 aa away.

The lane's own docstring says why: "Every clause is an AND, so the gate is
conservative." That was the right default with nothing to calibrate against.
There is something to calibrate against now.

THE HELD-OUT HALF IS NOT TOUCHED HERE, AND THE SCRIPT CANNOT BE ASKED TO.
There is no ``--half`` flag: :func:`train_genes` reads the train side of the
by-gene split and asserts the test side is disjoint from what it returns. Every
number this prints is a training number. A threshold chosen here is only worth
believing once it is evaluated ONCE on the held-out half, by the benchmark, at
the end — and if that evaluation is used to pick a different threshold, the
held-out half is spent and the honest move is to say so rather than quietly
reuse it.

Why recall is the right objective, with a stated cost ceiling: the truth set is
positive-unlabeled. A residue nobody has published a tag in is not a residue
that fails, so "precision" against it is uninterpretable and a threshold tuned
to maximise it would be optimising against absence of evidence. What IS
measurable is the cost of recall: residues claimed per protein. So the sweep
reports recall against that budget and the choice is a stated trade, not a
single score.

Two phases, because the expensive half is cacheable:

    # once: fetch structures + compute per-residue signals for the train half
    uv run python scripts/tune_surface_loop_recall.py --cache

    # cheap: sweep thresholds over the cache, no network, no structures
    uv run python scripts/tune_surface_loop_recall.py --sweep
"""

from __future__ import annotations

import argparse
import itertools
import json
import logging
from pathlib import Path
from typing import Any

from accessible_surfaceome.env import load_env

load_env()

from accessible_surfaceome.cloud.d1_client import D1Client, D1Config  # noqa: E402
from accessible_surfaceome.tag_sites import surface_loop as SL  # noqa: E402

log = logging.getLogger("tune_surface_loop")

ROOT = Path(__file__).resolve().parents[1]
SPLIT = ROOT / "data" / "analysis" / "prodomino" / "split.json"
CACHE = ROOT / "data" / "external" / "tag_site_tuning" / "signals"
OUT = ROOT / "data" / "analysis" / "tag_site_tuning"

# A published junction counts as recovered when it lands inside the proposed
# feature, widened by this much. Same tolerance the benchmark uses, and it is
# deliberately small relative to the 11 aa median feature: widening it is a way
# to manufacture recall without proposing anything new.
TOLERANCE = 5

# The grid. Current production values are PLDDT_MIN=70, RSA_MIN=0.40,
# MIN_LOOP_LEN=8 — each appears so the sweep always contains the incumbent and
# a reader can see what the change buys relative to it.
GRID: dict[str, tuple[Any, ...]] = {
    "PLDDT_MIN": (50.0, 60.0, 70.0),
    "RSA_MIN": (0.25, 0.30, 0.35, 0.40),
    "MIN_LOOP_LEN": (5, 6, 8),
}
INCUMBENT = {"PLDDT_MIN": 70.0, "RSA_MIN": 0.40, "MIN_LOOP_LEN": 8}


def train_genes() -> list[str]:
    """The TRAIN half of the by-gene split, and nothing else.

    Asserted rather than trusted: a split file edited to overlap would silently
    leak the held-out half into every number below, and the failure would look
    like a good result.
    """
    split = json.loads(SPLIT.read_text())
    train, test = list(split["train"]), set(split["test"])
    leaked = test & set(train)
    if leaked:
        raise SystemExit(
            f"split is not disjoint — {len(leaked)} gene(s) in both halves: "
            f"{sorted(leaked)[:5]}. Refusing to tune on a leaky split."
        )
    return train


def published_internal_junctions(genes: list[str]) -> dict[str, list[int]]:
    """Internal published junctions per gene, from public D1.

    Terminal junctions are excluded: the terminal lane already recovers 80% of
    them and no surface-loop threshold should be judged on sites that are not
    its job.
    """
    want = set(genes)
    with D1Client(D1Config.from_env_public()) as d1:
        rows = d1.query(
            "SELECT gene_symbol, insert_after_residue r FROM tag_site_public "
            "WHERE provenance='literature_retrieved' AND insert_after_residue IS NOT NULL;",
            [],
        )
    out: dict[str, list[int]] = {}
    for r in rows:
        if r["gene_symbol"] in want:
            out.setdefault(r["gene_symbol"], []).append(int(r["r"]))
    return out


def load_cached_signals(gene: str) -> dict[str, Any] | None:
    """Read one gene's cached signal record (gzipped, written by the pipeline)."""
    import gzip

    p = CACHE / f"{gene}.json.gz"
    if not p.exists():
        return None
    with gzip.open(p, "rt", encoding="utf-8") as fh:
        raw = json.load(fh)
    # JSON object keys are strings; the lane indexes per-residue maps by int.
    for key in ("plddt", "rsa", "ss", "feature_dist", "conservation", "gap_freq"):
        if isinstance(raw.get(key), dict):
            raw[key] = {int(k): v for k, v in raw[key].items()}
    return raw


def claimed_residues(picks: list[dict[str, Any]]) -> set[int]:
    """Every residue the lane's picks claim, widened by the tolerance.

    A pick's claim is its ``residue_range`` feature, not the single residue it
    pinned — scoring the pin alone reads a correctly identified loop as a miss.
    """
    out: set[int] = set()
    for p in picks:
        rng = p.get("residue_range")
        lo = hi = None
        if isinstance(rng, str) and "-" in rng:
            a, b = rng.split("-", 1)
            try:
                lo, hi = (
                    int("".join(c for c in a if c.isdigit())),
                    int("".join(c for c in b if c.isdigit())),
                )
            except ValueError:
                lo = hi = None
        if lo is None:
            pin = p.get("insert_after_residue")
            if pin is None:
                continue
            lo = hi = int(pin)
        out |= set(range(lo - TOLERANCE, hi + TOLERANCE + 1))
    return out


def evaluate(
    combo: dict[str, Any],
    cached: dict[str, dict[str, Any]],
    truth: dict[str, list[int]],
) -> dict[str, Any]:
    """Recall of published internal junctions, and what it costs, at one combo.

    Thresholds are module constants, so they are set and restored around the
    call rather than threaded through — the lane's signature stays the
    production one, which is the point: we are measuring the real lane.
    """
    saved = {k: getattr(SL, k) for k in combo}
    for k, v in combo.items():
        setattr(SL, k, v)
    try:
        hits = total = 0
        claimed_total = picks_total = proteins = 0
        for gene, junctions in truth.items():
            sig = cached.get(gene)
            if sig is None:
                continue
            try:
                picks = SL.surface_loop_candidates(
                    sig, gene_symbol=gene, uniprot_acc=sig.get("uniprot_acc", "")
                )
            except Exception:  # noqa: BLE001
                continue
            proteins += 1
            picks_total += len(picks)
            claimed = claimed_residues(picks)
            claimed_total += len(claimed)
            length = len(sig.get("sequence") or "") or max(
                (sig.get("plddt") or {0: 0}).keys()
            )
            for j in junctions:
                # Internal only — the terminal lane owns the rest.
                if not (30 < j < length - 30):
                    continue
                total += 1
                hits += j in claimed
    finally:
        for k, v in saved.items():
            setattr(SL, k, v)
    return {
        **combo,
        "n_junctions": total,
        "recall": round(hits / total, 4) if total else None,
        "n_hits": hits,
        "picks_per_protein": round(picks_total / proteins, 2) if proteins else None,
        "residues_claimed_per_protein": round(claimed_total / proteins, 1)
        if proteins
        else None,
        "is_incumbent": combo == INCUMBENT,
    }


def cmd_cache(genes: list[str]) -> int:
    """Print the command that fills the signal cache.

    The regeneration pipeline already dumps exactly this record as a side
    effect of ``--signals-dir``, so this does NOT reimplement the assembly of
    structures, topology, orthologs and hazard residues. A second code path
    building the same inputs is a second code path to drift: the whole point of
    the sweep is that it measures the production lane on production signals.
    """
    CACHE.mkdir(parents=True, exist_ok=True)
    done = sorted(p.name.removesuffix(".json.gz") for p in CACHE.glob("*.json.gz"))
    todo = [g for g in genes if g not in set(done)]
    log.info(
        "train genes: %d, signals cached: %d, missing: %d",
        len(genes),
        len(done),
        len(todo),
    )
    if not todo:
        log.info("cache complete — run --sweep")
        return 0
    # regenerate_tag_sites takes symbol<TAB>acc; the split's sequence file is
    # where both already live, so the accession is never re-resolved from a
    # bare symbol (see CLAUDE.md "Gene identifier resolution").
    seqs = json.loads((SPLIT.parent / "sequences_train.json").read_text())
    acc_of = {r["gene"]: r["acc"] for r in seqs}
    missing_acc = [g for g in todo if g not in acc_of]
    if missing_acc:
        log.warning(
            "%d gene(s) have no accession in the split file, skipped: %s",
            len(missing_acc),
            ", ".join(missing_acc[:5]),
        )
    manifest = OUT / "train_genes_needing_signals.tsv"
    OUT.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        "\n".join(f"{g}\t{acc_of[g]}" for g in todo if g in acc_of) + "\n"
    )
    log.info(
        "\nwrote %s\n\nFill the cache with the production pipeline:\n"
        "    uv run python scripts/regenerate_tag_sites.py \\\n"
        "        --manifest %s \\\n"
        "        --signals-dir %s\n",
        manifest,
        manifest,
        CACHE,
    )
    return 0


def cmd_sweep(genes: list[str]) -> int:
    cached = {}
    for gene in genes:
        sig = load_cached_signals(gene)
        if sig is not None:
            cached[gene] = sig
    if not cached:
        raise SystemExit(
            f"no cached signals in {CACHE} — run --cache first (it needs the "
            "AlphaFold models, so it is the slow half)."
        )
    truth = published_internal_junctions(genes)
    log.info(
        "TRAIN half: %d genes, %d with cached signals, %d with a published junction",
        len(genes),
        len(cached),
        len(truth),
    )

    rows = [
        evaluate(dict(zip(GRID, combo, strict=True)), cached, truth)
        for combo in itertools.product(*GRID.values())
    ]
    rows = [r for r in rows if r["recall"] is not None]
    rows.sort(key=lambda r: (-r["recall"], r["residues_claimed_per_protein"] or 0))

    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "surface_loop_threshold_sweep_train.tsv"
    cols = list(rows[0])
    path.write_text(
        "\t".join(cols)
        + "\n"
        + "\n".join("\t".join(str(r[c]) for c in cols) for r in rows)
        + "\n"
    )

    base = next((r for r in rows if r["is_incumbent"]), None)
    log.info(
        "\n%-8s %-8s %-6s %7s %8s %9s",
        *["pLDDT", "RSA", "loop", "recall", "picks/p", "res/prot"],
    )
    for r in rows[:12]:
        mark = "  <- incumbent" if r["is_incumbent"] else ""
        log.info(
            "%-8s %-8s %-6s %7.3f %8.2f %9.1f%s",
            r["PLDDT_MIN"],
            r["RSA_MIN"],
            r["MIN_LOOP_LEN"],
            r["recall"],
            r["picks_per_protein"],
            r["residues_claimed_per_protein"],
            mark,
        )
    if base:
        log.info(
            "\nincumbent: recall %.3f at %.1f residues/protein",
            base["recall"],
            base["residues_claimed_per_protein"],
        )
    log.info("wrote %s", path)
    log.info(
        "\nTRAINING NUMBERS. Do not pick a threshold and report its held-out "
        "score in the same breath — evaluate the chosen one ONCE, at the end."
    )
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cache", action="store_true", help="compute per-residue signals")
    ap.add_argument(
        "--sweep", action="store_true", help="sweep thresholds over the cache"
    )
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if not (args.cache or args.sweep):
        ap.error("pass --cache or --sweep")
    genes = train_genes()
    if args.cache:
        return cmd_cache(genes)
    return cmd_sweep(genes)


if __name__ == "__main__":
    raise SystemExit(main())
