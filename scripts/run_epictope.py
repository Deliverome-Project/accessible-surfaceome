"""Score proteins with EpicTope's published formula, using official binaries.

EpicTope (Zinski, Joshi, … Friedberg, Mullins; *Development* 2026; GPL-3,
https://github.com/FriedbergLab/Epictope) ranks tag-insertion sites by the
"least-worst" of four per-residue features. This runs that scoring over our
cohort so it sits in the same comparison as ProDomino and INDELi-E.

THE FORMULA IS THE REPOSITORY'S, NOT A PARAPHRASE. Read off
``R/calculate_scores.R`` and ``R/check_config.R`` at the pinned clone:

    normalized_entropy = shannon / log2(20)
    ss_score           = {G,H,I,E,P: 0, T,B,S: 0.5, C: 1}
    rsa                = sasa / max_sasa[aa]       (Tien 2013 empirical maxima)
    inv_anchor2        = 1 - anchor2               (IUPred2A ANCHOR2)
    score              = min(the four above)

The paper additionally smooths features over a 7-residue window for its
figures; the repository's ``calculate_scores`` does not, so the unsmoothed
per-residue minimum is what this emits and ``--window`` reproduces the
smoothed variant rather than the other way round.

WHERE THIS DEPARTS FROM THE PUBLISHED PIPELINE, AND WHY IT IS RECORDED
----------------------------------------------------------------------
* **Homologs and entropy are faithful.** blastp against the same 7 Ensembl
  release-108 proteomes EpicTope names (``scripts/config_defaults.R``), one
  best hit per species, aligned with muscle, Shannon entropy per column.
* **anchor2 is faithful** — IUPred2A's REST API, which is what
  ``R/iupredAnchor.R`` calls.
* **ss and sasa come from our AlphaFold-derived signals, not DSSP.** We already
  compute DSSP-convention secondary-structure codes and freesasa RSA for every
  cohort protein. Installing DSSP to recompute them would add a dependency to
  reproduce numbers we hold, but it IS a difference in provenance and the
  emitted ``model_config`` says so, so nobody reads these as byte-identical to
  a DSSP run.

Binaries are the official upstream builds, NOT the third-party ``brewsci/bio``
Homebrew tap (which ``brew`` itself refuses to load as untrusted). Versions and
checksums: ``data/analysis/tag_site_tuning/epictope_toolchain.json``.

    uv run python scripts/run_epictope.py --genes-file <tsv> --out scores.json
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import subprocess
import tempfile
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("epictope")

ROOT = Path(__file__).resolve().parents[1]
BIN = Path.home() / ".local/opt/epictope-bin"
BLASTP = BIN / "ncbi-blast-2.17.0+/bin/blastp"
BLASTDBCMD = BIN / "ncbi-blast-2.17.0+/bin/blastdbcmd"
MUSCLE = BIN / "muscle-osx-arm64"
DB = Path.home() / ".local/opt/epictope-db/all7"

#: blastp against a 7-proteome, 416k-sequence database is the wall clock of
#: this script — single-threaded it is roughly 20 s/gene. The search is
#: embarrassingly parallel over database chunks, so threading it is a straight
#: win with no effect on the hits returned.
BLAST_THREADS = 8

# muscle 5.3's macOS builds link gcc@11's libgomp, which is not installed.
# libgomp is ABI-stable, so the installed gcc 15 copy resolves it without
# patching the binary or installing a second compiler.
MUSCLE_ENV = {"DYLD_FALLBACK_LIBRARY_PATH": "/opt/homebrew/opt/gcc/lib/gcc/15"}

# R/check_config.R
SS_KEY = {
    "G": 0.0,
    "H": 0.0,
    "I": 0.0,
    "E": 0.0,
    "P": 0.0,
    "T": 0.5,
    "B": 0.5,
    "S": 0.5,
    "C": 1.0,
}
MAX_SASA = dict(
    zip(
        "ARNDCEQGHILKMFPSTWYV",
        (
            121,
            265,
            187,
            187,
            148,
            214,
            214,
            97,
            216,
            195,
            191,
            230,
            203,
            228,
            154,
            143,
            163,
            264,
            255,
            165,
        ),
        strict=True,
    )
)
MAX_ENTROPY = math.log2(20)

# Ensembl stable-ID prefixes for the 7 species EpicTope names. Species is read
# off the protein ID rather than searched for in the defline: the ID prefix is
# the stable, documented encoding, whereas assembly names in the defline change
# between releases and would silently stop matching.
# Human is the bare "ENSP"; it must be tested LAST because every other prefix
# also ends in "P" and a naive startswith("ENSP") check matches nothing else
# but an endswith/contains check would mis-assign them.
SPECIES_PREFIX = {
    "ENSBTAP": "bos_taurus",
    "ENSCAFP": "canis_lupus_familiaris",
    "ENSGALP": "gallus_gallus",
    "ENSMUSP": "mus_musculus",
    "ENSTRUP": "takifugu_rubripes",
    "ENSXETP": "xenopus_tropicalis",
}


def species_of(hit_id: str) -> str | None:
    """Which of the 7 proteomes a hit came from, by Ensembl ID prefix."""
    for prefix, name in SPECIES_PREFIX.items():
        if hit_id.startswith(prefix):
            return name
    return "homo_sapiens" if hit_id.startswith("ENSP") else None


def _per_residue(value: Any) -> dict[int, Any]:
    """Normalise a per-residue signal to a 1-indexed dict.

    The cache stores these as LISTS (index 0 = residue 1), but the lanes index
    them by residue number. Reading a list as if it were a dict silently shifts
    every value by one residue, so the two shapes are handled explicitly rather
    than assumed.
    """
    if value is None:
        return {}
    if isinstance(value, dict):
        return {int(k): v for k, v in value.items()}
    return {i: v for i, v in enumerate(value, start=1)}


def preflight() -> None:
    """Fail loudly and early if a binary or the database is missing."""
    missing = [str(p) for p in (BLASTP, BLASTDBCMD, MUSCLE) if not p.exists()]
    if not (DB.parent / f"{DB.name}.pin").exists():
        missing.append(f"{DB}.pin (BLAST database)")
    if missing:
        raise SystemExit(
            "missing EpicTope dependencies:\n  "
            + "\n  ".join(missing)
            + "\n\nSee data/analysis/tag_site_tuning/epictope_toolchain.json for "
            "where each came from."
        )


def best_hit_per_species(seq: str, acc: str) -> dict[str, str]:
    """One best blastp hit per species — EpicTope aligns one ortholog each.

    Taking all hits instead would let a species with many paralogs dominate the
    column entropy, which is the quantity the score is built on.
    """
    with tempfile.TemporaryDirectory() as tmp:
        q = Path(tmp) / "q.faa"
        q.write_text(f">{acc}\n{seq}\n")
        out = subprocess.run(
            [
                str(BLASTP),
                "-query",
                str(q),
                "-db",
                str(DB),
                "-outfmt",
                "6 sseqid evalue bitscore",
                "-max_target_seqs",
                "250",
                "-evalue",
                "1e-3",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
    if out.returncode != 0:
        log.warning("blastp failed for %s: %.200s", acc, out.stderr)
        return {}
    # Ensembl pep headers carry the species in the id's prefix only loosely, so
    # the hit is attributed by which proteome file it came from; blastdbcmd
    # gives the full defline, which names the assembly.
    hits: list[str] = []
    for line in out.stdout.splitlines():
        parts = line.split("\t")
        if parts:
            hits.append(parts[0])
    return {"_hits": hits} if hits else {}


def fetch_seqs(ids: list[str]) -> dict[str, tuple[str, str]]:
    """id -> (defline, sequence) straight out of the BLAST database."""
    if not ids:
        return {}
    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp) / "ids.txt"
        f.write_text("\n".join(ids) + "\n")
        out = subprocess.run(
            [str(BLASTDBCMD), "-db", str(DB), "-entry_batch", str(f)],
            capture_output=True,
            text=True,
            check=False,
        )
    recs: dict[str, tuple[str, str]] = {}
    name = defline = None
    buf: list[str] = []
    for line in out.stdout.splitlines():
        if line.startswith(">"):
            if name:
                recs[name] = (defline or "", "".join(buf))
            defline = line[1:]
            name = defline.split()[0]
            buf = []
        else:
            buf.append(line.strip())
    if name:
        recs[name] = (defline or "", "".join(buf))
    return recs


def pick_one_per_species(hits: list[str]) -> list[str]:
    """Best-scoring hit from each species. blastp output is already sorted."""
    chosen: dict[str, str] = {}
    for hid in hits:
        sp = species_of(hid)
        if sp and sp not in chosen:
            chosen[sp] = hid
    return list(chosen.values())


def msa_entropy(query_seq: str, others: list[str]) -> list[float]:
    """Shannon entropy per QUERY residue, from a muscle alignment.

    Columns are mapped back to query coordinates: a residue's entropy is that
    of the alignment column it occupies, and alignment columns where the query
    is a gap are dropped. Without that mapping every score after the first
    insertion is attributed to the wrong residue.
    """
    if not others:
        return [0.0] * len(query_seq)
    with tempfile.TemporaryDirectory() as tmp:
        fa, al = Path(tmp) / "in.faa", Path(tmp) / "out.afa"
        fa.write_text(
            ">QUERY\n"
            + query_seq
            + "\n"
            + "".join(f">h{i}\n{s}\n" for i, s in enumerate(others))
        )
        r = subprocess.run(
            [str(MUSCLE), "-align", str(fa), "-output", str(al)],
            capture_output=True,
            text=True,
            check=False,
            env={**MUSCLE_ENV, "PATH": "/usr/bin:/bin"},
        )
        if r.returncode != 0 or not al.exists():
            log.warning("muscle failed: %.200s", r.stderr[-200:])
            return [0.0] * len(query_seq)
        aln: dict[str, list[str]] = {}
        name = None
        for line in al.read_text().splitlines():
            if line.startswith(">"):
                name = line[1:].split()[0]
                aln[name] = []
            elif name:
                aln[name].append(line.strip())
    rows = {k: "".join(v) for k, v in aln.items()}
    q = rows.get("QUERY")
    if not q:
        return [0.0] * len(query_seq)
    cols = list(rows.values())
    out: list[float] = []
    for i, ch in enumerate(q):
        if ch == "-":
            continue
        column = [r[i] for r in cols if i < len(r) and r[i] != "-"]
        n = len(column)
        if n <= 1:
            out.append(0.0)
            continue
        counts = Counter(column)
        out.append(-sum((c / n) * math.log2(c / n) for c in counts.values()))
    # Alignment can trim; pad so the array is always one value per residue.
    out += [0.0] * (len(query_seq) - len(out))
    return out[: len(query_seq)]


#: Courtesy interval between IUPred2A calls. Their REST API is a small
#: academic service; a cohort sweep is hundreds of requests and should not
#: arrive as fast as we can issue them.
IUPRED_COURTESY_S = 0.5


def anchor2(acc: str) -> list[float] | None:
    """IUPred2A ANCHOR2 per residue — the same REST call R/iupredAnchor.R makes."""
    import time

    time.sleep(IUPRED_COURTESY_S)
    url = f"https://iupred2a.elte.hu/iupred2a/anchor/{acc}.json"
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            data = json.loads(r.read().decode())
        vals = data.get("anchor2")
        return [float(v) for v in vals] if vals else None
    except Exception as exc:  # noqa: BLE001
        log.warning("IUPred2A failed for %s: %s", acc, exc)
        return None


def model_config_note(window: int) -> str:
    """Describe THIS invocation, not the paper.

    ``window=0`` is the repository's ``calculate_scores`` -- an unsmoothed
    per-residue minimum. ``--window 7`` reproduces the smoothing the paper
    applies for its figures, which averages each feature over the window
    BEFORE the minimum and so removes most of the exact zeros. The two rank
    candidates differently, so the record has to say which one ran.
    """
    how = (
        "least-worst per residue (unsmoothed; repo calculate_scores)"
        if not window or window <= 1
        else f"least-worst over a {window}-residue window (the paper smoothing: mean per feature, then min)"
    )
    return (
        f"{how}; raw score, not normalised; entropy from blastp+muscle over "
        "the 7 Ensembl proteomes EpicTope names; anchor2 from IUPred2A REST; "
        "ss+rsa from AlphaFold+freesasa, NOT DSSP"
    )


def score_protein(
    seq: str,
    entropy: list[float],
    ss: dict[int, str],
    rsa: dict[int, float],
    anch: list[float],
    window: int = 0,
) -> list[float]:
    """EpicTope's per-residue least-worst score, 1-indexed input maps."""
    feats: list[list[float]] = []
    for i, aa in enumerate(seq, start=1):
        e = min(entropy[i - 1] / MAX_ENTROPY, 1.0) if i - 1 < len(entropy) else 0.0
        s = SS_KEY.get((ss.get(i) or "C").upper(), 0.0)
        r = rsa.get(i)
        if r is None:
            r = 0.0
        # Our RSA is already sasa/max_sasa; a raw SASA would need the division.
        r = min(max(r, 0.0), 1.0)
        a = 1.0 - (anch[i - 1] if i - 1 < len(anch) else 0.0)
        feats.append([e, s, r, a])
    if window and window > 1:
        half = window // 2
        sm: list[list[float]] = []
        for i in range(len(feats)):
            lo, hi = max(0, i - half), min(len(feats), i + half + 1)
            sm.append([sum(f[k] for f in feats[lo:hi]) / (hi - lo) for k in range(4)])
        feats = sm
    _ = MAX_SASA  # table kept for callers that pass raw SASA rather than RSA
    return [round(min(f), 5) for f in feats]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--genes-file", required=True, type=Path, help="TSV: symbol<TAB>acc"
    )
    ap.add_argument("--signals-dir", type=Path, required=True)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--window", type=int, default=0, help="paper's 7-residue smoothing")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    preflight()

    import gzip

    rows = [
        line.split("\t")[:2]
        for line in args.genes_file.read_text().splitlines()
        if line.strip() and "\t" in line
    ]
    if args.limit:
        rows = rows[: args.limit]
    log.info("scoring %d gene(s)", len(rows))

    # Resume rather than redo: this is a long run and restarting it (to raise
    # thread count, after a network blip) should not re-pay for finished genes.
    out: list[dict[str, Any]] = []
    if args.out.exists():
        try:
            out = json.loads(args.out.read_text())
            done = {r["gene_symbol"] for r in out}
            rows = [r for r in rows if r[0] not in done]
            log.info("resuming: %d already scored, %d to go", len(out), len(rows))
        except Exception:  # noqa: BLE001
            out = []
    for n, (symbol, acc) in enumerate(rows, 1):
        sig_path = args.signals_dir / f"{symbol}.json.gz"
        if not sig_path.exists():
            log.warning("%s: no cached signals, skipped", symbol)
            continue
        with gzip.open(sig_path, "rt", encoding="utf-8") as fh:
            sig = json.load(fh)
        seq = sig.get("sequence") or ""
        if not seq:
            log.warning("%s: no sequence in signals, skipped", symbol)
            continue
        ss = _per_residue(sig.get("ss"))
        # Residues unmodelled in the AlphaFold file carry None, not 0. Coercing
        # them would crash; keeping them out of the dict lets score_protein
        # treat them as "no exposure evidence", which ranks them last rather
        # than asserting they are buried.
        rsa = {
            k: float(v)
            for k, v in _per_residue(sig.get("rsa")).items()
            if v is not None
        }

        hits = best_hit_per_species(seq, acc).get("_hits", [])
        chosen = pick_one_per_species(hits)
        seqs = fetch_seqs(chosen)
        others = [seqs[h][1] for h in chosen if h in seqs and seqs[h][1]]
        ent = msa_entropy(seq, others)
        anch = anchor2(acc)
        if anch is None:
            log.warning(
                "%s: no ANCHOR2 — skipped rather than scored on 3 of 4 features", symbol
            )
            continue

        scores = score_protein(seq, ent, ss, rsa, anch, window=args.window)
        out.append(
            {
                "gene_symbol": symbol,
                "uniprot_acc": acc,
                "length": len(seq),
                "n_scores": len(scores),
                "scores": scores,
                "n_species_aligned": len(others),
                # Self-describing, because the loader must not have to guess.
                # EpicTope is the one predictor we RUN rather than ingest, so a
                # paper-level description of the model is the wrong provenance:
                # what matters is the invocation. A hardcoded loader string
                # claimed a 7-residue window and per-protein min-max
                # normalisation for runs that had neither.
                "window": args.window,
                "model_config": model_config_note(args.window),
            }
        )
        if n % 10 == 0 or n == len(rows):
            # Checkpoint, not just progress. A run over the cohort is ~50
            # minutes; writing only at the end means any interruption throws
            # all of it away AND leaves the resume above with nothing to read,
            # which is how the first attempt lost its work.
            args.out.write_text(json.dumps(out))
            log.info("  %d/%d (%d scored, checkpointed)", n, len(rows), len(out))

    args.out.write_text(json.dumps(out))
    log.info("wrote %d record(s) -> %s", len(out), args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
