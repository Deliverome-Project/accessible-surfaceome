"""Train-set scoreboard: 3 published predictors and our lanes, by site type.

One table, one metric, so the rows are actually comparable:

    can the scorer put the published junction inside the residues it claims,
    given the SAME residue budget?

Our lanes claim whole features (``residue_range``); a predictor is handed its
top-N residues where N is what our lanes claimed on that same protein. Budget
matching is not a nicety — comparing a lane that claims ~100 residues against a
predictor allowed 7 picks inverts the answer, which is exactly what happened
before it was fixed.

SITE TYPE IS A PROPERTY OF THE PUBLISHED JUNCTION, NOT OF THE SCORER.
Every junction is classified once, from the structure, and every scorer is then
measured on the same three buckets:

* **terminal**  — within TERMINAL_WINDOW of either end. Three quarters of the
  published set. The easy case, and the one that dominates any single overall
  number, which is why no single overall number is printed.
* **disordered** — internal, pLDDT below PLDDT_ORDERED at the junction. What
  the disorder lane is for.
* **surface**   — internal and confidently folded (pLDDT at or above
  PLDDT_ORDERED). What the surface-loop lane is for, and the hard case.

TRAIN ONLY. ``cohort()`` asserts the two halves of the by-gene split are
disjoint and returns the train side; there is no flag for the other one. Every
number here is a training number, including the published predictors' — they
are frozen and leak nothing, but mixing a train row and a test row in one table
invites reading them as the same thing.

    uv run python scripts/report_tag_site_benchmark_train.py
"""

from __future__ import annotations

import argparse
import gzip
import itertools
import json
import logging
from pathlib import Path
from typing import Any

from accessible_surfaceome.env import load_env

load_env()

from accessible_surfaceome.cloud.d1_client import D1Client, D1Config  # noqa: E402
from accessible_surfaceome.tag_sites import surface_loop as SL  # noqa: E402
from accessible_surfaceome.tag_sites.disorder import disorder_candidates  # noqa: E402
from accessible_surfaceome.tag_sites.terminal import terminal_candidates  # noqa: E402

log = logging.getLogger("scoreboard")

ROOT = Path(__file__).resolve().parents[1]
SPLIT = ROOT / "data" / "analysis" / "prodomino" / "split.json"
SIGNALS = ROOT / "data" / "external" / "tag_site_tuning" / "signals"
OUT = ROOT / "data" / "analysis" / "tag_site_tuning"

TOLERANCE = 5
TERMINAL_WINDOW = 30
#: Same pLDDT boundary the surface-loop lane uses as its reliability gate, so
#: "surface" here means the population that lane is actually asked to cover.
PLDDT_ORDERED = 70.0

#: Our lane settings to compare. "incumbent" is production; the rest widen the
#: gate the benchmark says is too tight. Train-only, so these are candidates to
#: evaluate later, not a chosen threshold.
LANE_VARIANTS: dict[str, dict[str, Any]] = {
    "incumbent (70/0.40/8)": {"PLDDT_MIN": 70.0, "RSA_MIN": 0.40, "MIN_LOOP_LEN": 8},
    "looser RSA (70/0.30/8)": {"PLDDT_MIN": 70.0, "RSA_MIN": 0.30, "MIN_LOOP_LEN": 8},
    "shorter loop (70/0.40/5)": {"PLDDT_MIN": 70.0, "RSA_MIN": 0.40, "MIN_LOOP_LEN": 5},
    "lower pLDDT (50/0.40/8)": {"PLDDT_MIN": 50.0, "RSA_MIN": 0.40, "MIN_LOOP_LEN": 8},
    "all three (50/0.30/5)": {"PLDDT_MIN": 50.0, "RSA_MIN": 0.30, "MIN_LOOP_LEN": 5},
}
PREDICTORS = ("prodomino", "indeli_e", "epictope")


def cohort() -> list[str]:
    split = json.loads(SPLIT.read_text())
    train, test = list(split["train"]), set(split["test"])
    if test & set(train):
        raise SystemExit("split halves overlap — refusing to report on a leaky split")
    return train


def load_signals(gene: str) -> dict[str, Any] | None:
    p = SIGNALS / f"{gene}.json.gz"
    if not p.exists():
        return None
    with gzip.open(p, "rt", encoding="utf-8") as fh:
        return json.load(fh)


def per_residue(value: Any) -> dict[int, Any]:
    """1-indexed dict from either a list (index 0 = residue 1) or a dict.

    The cache stores lists; the lanes index by residue number. Reading one as
    the other shifts every value by a residue and nothing downstream notices.
    """
    if value is None:
        return {}
    if isinstance(value, dict):
        return {int(k): v for k, v in value.items()}
    return dict(enumerate(value, start=1))


def decode(scores_hex: str, lo: float, hi: float) -> list[float]:
    span = hi - lo
    return [lo + b / 255.0 * span for b in bytes.fromhex(scores_hex)]


def parse_encoding(cfg: str | None) -> tuple[float, float]:
    import re

    m = re.search(r"encoding=linear:lo=(-?[\d.]+):hi=(-?[\d.]+)", cfg or "")
    return (float(m.group(1)), float(m.group(2))) if m else (0.0, 1.0)


def fetch_truth(genes: set[str]) -> dict[str, list[int]]:
    with D1Client(D1Config.from_env_public()) as d1:
        rows = d1.query(
            "SELECT gene_symbol, insert_after_residue r FROM tag_site_public "
            "WHERE provenance='literature_retrieved' AND insert_after_residue IS NOT NULL;",
            [],
        )
    out: dict[str, list[int]] = {}
    for r in rows:
        if r["gene_symbol"] in genes:
            out.setdefault(r["gene_symbol"], []).append(int(r["r"]))
    return {g: sorted(set(v)) for g, v in out.items()}


def fetch_predictions(
    genes: set[str], local_epictope: Path | None
) -> dict[str, dict[str, list[float]]]:
    """gene -> predictor -> per-residue scores."""
    out: dict[str, dict[str, list[float]]] = {}
    with D1Client(D1Config.from_env_public()) as d1:
        rows = d1.query(
            "SELECT gene_symbol, predictor, model_config, scores_hex, run_id "
            "FROM tag_site_prediction;",
            [],
        )
    for r in rows:
        g = r["gene_symbol"]
        if g not in genes or not str(r.get("run_id", "")).endswith("_train"):
            continue
        lo, hi = parse_encoding(r["model_config"])
        out.setdefault(g, {})[r["predictor"]] = decode(r["scores_hex"], lo, hi)
    # EpicTope may still be scoring; read the in-flight checkpoint so the table
    # can be produced before the full run lands, with its coverage stated.
    if local_epictope and local_epictope.exists():
        try:
            for rec in json.loads(local_epictope.read_text()):
                if rec["gene_symbol"] in genes:
                    out.setdefault(rec["gene_symbol"], {}).setdefault(
                        "epictope", [float(x) for x in rec["scores"]]
                    )
        except Exception as exc:  # noqa: BLE001
            log.warning("could not read local epictope checkpoint: %s", exc)
    return out


#: Per-residue fields the lanes index by RESIDUE NUMBER. The cache stores them
#: as lists (index 0 = residue 1), so each must be converted before the lane
#: sees them — handing the lane a list makes every gate silently fail its
#: lookups and the lane returns nothing at all, which reads as "found no sites"
#: rather than as an error.
LANE_RESIDUE_FIELDS = (
    "plddt",
    "rsa",
    "ss",
    "topology",
    "feature_dist",
    "conservation",
    "gap_freq",
    "ca",
)


def lane_ready(sig: dict[str, Any]) -> dict[str, Any]:
    """The cached record in the shape the production lane expects."""
    out = dict(sig)
    for key in LANE_RESIDUE_FIELDS:
        if key in out:
            out[key] = per_residue(out[key])
    return out


#: Each lane on its own, plus the pipeline as a whole. Per-lane rows are not
#: decoration: the combined row hides which lane is carrying a column, and the
#: first version of this table scored ONLY surface_loop, which made the whole
#: pipeline look far worse than it is on terminal sites.
LANE_SETS: dict[str, tuple[str, ...]] = {
    "all lanes": ("surface_loop", "disorder", "terminal"),
    "surface_loop only": ("surface_loop",),
    "disorder only": ("disorder",),
    "terminal only": ("terminal",),
}


def claimed_by_lane(
    sig: dict[str, Any],
    gene: str,
    acc: str,
    combo: dict[str, Any],
    lanes: tuple[str, ...] = ("surface_loop", "disorder", "terminal"),
) -> set[int]:
    """Residues the deterministic lanes claim, at one threshold setting.

    Thresholds are module constants, set and restored around the call, so the
    lane under test is the production function rather than a copy of it.
    """
    # ALL the deterministic lanes, not just the surface-loop one. Scoring only
    # surface_loop against a predictor that reasons over the whole protein is
    # not a comparison of pipelines — it is our narrowest lane against their
    # broadest output, and it makes our terminal numbers look catastrophic when
    # the terminal lane simply was not in the room.
    saved = {k: getattr(SL, k) for k in combo}
    for k, v in combo.items():
        setattr(SL, k, v)
    fns = {
        "surface_loop": SL.surface_loop_candidates,
        "disorder": disorder_candidates,
        "terminal": terminal_candidates,
    }
    picks: list[dict[str, Any]] = []
    try:
        for lane in lanes:
            try:
                picks += fns[lane](sig, gene_symbol=gene, uniprot_acc=acc) or []
            except Exception:  # noqa: BLE001
                continue
    finally:
        for k, v in saved.items():
            setattr(SL, k, v)
    claimed: set[int] = set()
    for p in picks:
        rng = p.get("residue_range")
        lo = hi = None
        if isinstance(rng, str) and "-" in rng:
            a, b = rng.split("-", 1)
            da = "".join(c for c in a if c.isdigit())
            db = "".join(c for c in b if c.isdigit())
            if da and db:
                lo, hi = int(da), int(db)
        if lo is None:
            pin = p.get("insert_after_residue")
            if pin is None:
                continue
            lo = hi = int(pin)
        claimed |= set(range(lo - TOLERANCE, hi + TOLERANCE + 1))
    return claimed


def classify(junction: int, length: int, plddt: dict[int, float]) -> str | None:
    """terminal / disordered / surface, or None when pLDDT is unknown there."""
    if junction <= TERMINAL_WINDOW or junction >= length - TERMINAL_WINDOW:
        return "terminal"
    p = plddt.get(junction)
    if p is None:
        return None
    return "disordered" if p < PLDDT_ORDERED else "surface"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--nonzero-only",
        action="store_true",
        help="a predictor may only claim residues it scored above "
        "zero, so a budget is not padded with tied zeros.",
    )
    ap.add_argument(
        "--allow-unequal",
        action="store_true",
        help="score each predictor on its own coverage. Off by "
        "default: unequal denominators make the comparison "
        "meaningless, and it is not visible in the output.",
    )
    ap.add_argument(
        "--epictope-json",
        type=Path,
        default=None,
        help="in-flight checkpoint, used when D1 does not have it yet",
    )
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    train = cohort()
    truth = fetch_truth(set(train))
    preds = fetch_predictions(set(train), args.epictope_json)
    log.info("TRAIN: %d genes, %d with a published junction", len(train), len(truth))

    # EVERY ROW MUST SHARE A DENOMINATOR. The predictors cover different gene
    # sets — one ProDomino protein OOM'd, INDELi-E skipped isoform mismatches,
    # and EpicTope may still be mid-run — so scoring each on whatever it
    # happens to have compares scorers AND gene sets at once. The scorer with
    # the smallest, easiest subset then looks best for no reason.
    if not args.allow_unequal:
        common = {g for g in train if all(preds.get(g, {}).get(p) for p in PREDICTORS)}
        dropped = {
            p: sum(1 for g in train if preds.get(g, {}).get(p)) for p in PREDICTORS
        }
        log.info(
            "restricting to genes ALL predictors cover: %d (from %s)",
            len(common),
            ", ".join(f"{p}={dropped[p]}" for p in PREDICTORS),
        )
        train = [g for g in train if g in common]

    # hits[row][type] = [n_hit, n_total]
    hits: dict[str, dict[str, list[int]]] = {}
    budgets: dict[str, list[int]] = {}
    counts = {"terminal": 0, "disordered": 0, "surface": 0}
    coverage = {p: 0 for p in PREDICTORS}
    n_genes = 0

    for gene in train:
        junctions = truth.get(gene)
        sig = load_signals(gene)
        if not junctions or sig is None:
            continue
        seq = sig.get("sequence") or ""
        length = len(seq)
        if not length:
            continue
        n_genes += 1
        # A residue with no pLDDT (unmodelled in the AF file) must not be
        # silently treated as 0 — that would class it as disordered, which is
        # the opposite of "unknown". Those residues are dropped from the
        # classification instead.
        plddt = {
            k: float(v)
            for k, v in per_residue(sig.get("plddt")).items()
            if v is not None
        }
        acc = sig.get("uniprot_acc") or ""

        ready = lane_ready(sig)
        lane_claims: dict[str, set[int]] = {}
        # Per-lane at the incumbent thresholds, so the columns show which lane
        # carries which site type.
        for lname, lset in LANE_SETS.items():
            if lname == "all lanes":
                continue
            lane_claims[f"lane: {lname}"] = claimed_by_lane(
                ready, gene, acc, LANE_VARIANTS["incumbent (70/0.40/8)"], lset
            )
        # Threshold variants, always over all lanes.
        for name, combo in LANE_VARIANTS.items():
            lane_claims[name] = claimed_by_lane(ready, gene, acc, combo)
        # Budget = what the incumbent lane claims on this protein. Every
        # predictor gets exactly that many residues, so the columns compare
        # scorers rather than list lengths.
        budget = len(lane_claims["incumbent (70/0.40/8)"]) or 1
        top: dict[str, set[int]] = {}
        for p in PREDICTORS:
            sc = preds.get(gene, {}).get(p)
            if not sc:
                continue
            coverage[p] += 1
            order = sorted(range(1, len(sc) + 1), key=lambda i: -sc[i - 1])
            if args.nonzero_only:
                # A score of exactly 0 is not a prediction, it is the absence
                # of one. EpicTope's least-worst score is 0 at any residue in a
                # helix or strand, so for most proteins FEWER residues carry a
                # nonzero score than the budget allows — and the remainder of
                # the budget is then filled by tied zeros in residue-index
                # order. That is tie-break luck being scored as skill.
                order = [i for i in order if sc[i - 1] > 1e-9]
            top[p] = set(order[:budget])

        for j in junctions:
            if not (1 <= j <= length):
                continue
            kind = classify(j, length, plddt)
            if kind is None:
                continue
            counts[kind] += 1
            window = set(range(j - TOLERANCE, j + TOLERANCE + 1))
            for name, claimed in lane_claims.items():
                row = hits.setdefault(f"OURS {name}", {})
                cell = row.setdefault(kind, [0, 0])
                cell[1] += 1
                cell[0] += j in claimed
                budgets.setdefault(f"OURS {name}", []).append(len(claimed))
            for p, tops in top.items():
                row = hits.setdefault(f"PRED {p}", {})
                cell = row.setdefault(kind, [0, 0])
                cell[1] += 1
                cell[0] += bool(window & tops)
                budgets.setdefault(f"PRED {p}", []).append(budget)

    log.info(
        "scored %d gene(s) with signals; junctions: terminal %d, disordered %d, surface %d",
        n_genes,
        counts["terminal"],
        counts["disordered"],
        counts["surface"],
    )
    log.info(
        "predictor coverage (genes): %s",
        ", ".join(f"{p}={coverage[p]}" for p in PREDICTORS),
    )

    order_rows = (
        [f"PRED {p}" for p in PREDICTORS]
        + [f"OURS lane: {n}" for n in LANE_SETS if n != "all lanes"]
        + [f"OURS {n}" for n in LANE_VARIANTS]
    )
    header = f"{'scorer':28s} {'terminal':>12s} {'disordered':>12s} {'surface':>12s} {'res/prot':>9s}"
    log.info("\n%s", header)
    log.info("-" * len(header))
    lines = ["scorer\tterminal\tdisordered\tsurface\tresidues_per_protein"]
    for row in order_rows:
        if row not in hits:
            continue
        cells = []
        for kind in ("terminal", "disordered", "surface"):
            h, t = hits[row].get(kind, [0, 0])
            cells.append(f"{100 * h / t:.1f}% ({h}/{t})" if t else "—")
        b = budgets.get(row, [])
        avg = sum(b) / len(b) if b else 0
        log.info(
            "%-28s %12s %12s %12s %9.0f", row, *[c.split(" ")[0] for c in cells], avg
        )
        lines.append("\t".join([row, *cells, f"{avg:.0f}"]))

    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "train_scoreboard_by_site_type.tsv"
    path.write_text("\n".join(lines) + "\n")
    log.info("\ndetail (with n) -> %s", path)
    log.info(
        "\nTRAIN NUMBERS. Lane variants are candidates, not a chosen threshold: "
        "pick one here, then evaluate it ONCE on the held-out half."
    )
    _ = itertools  # grid expansion lives in tune_surface_loop_recall.py
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
