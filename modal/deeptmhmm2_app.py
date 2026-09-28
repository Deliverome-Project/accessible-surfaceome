"""Modal app — DeepTMHMM2 topology prediction across the human proteoform set.

DeepTMHMM2 (``dtm2``) predicts signal peptides, transmembrane helices, beta barrels,
reentrant loops, interfacial helices and membrane type in one pass. This app runs it on
GPU over the proteoforms already in ``topology_public``, so v1 and v2 can be compared
row-for-row on identical input.

Canary first — 50 proteoforms, reports GPU-seconds and a projected cost, writes nothing
to D1::

    modal run modal/deeptmhmm2_app.py::canary --n 50

Full sweep, only after reviewing the canary::

    modal run modal/deeptmhmm2_app.py::full_sweep --run-id dtm2_2026_09_28

Both stream per-shard output to the ``surfaceome-topology2`` Modal Volume. **Neither
writes to D1.** Publishing is a separate, deliberate step: pull the volume back with
``modal volume get``, review, then run the upload script. That separation is on purpose —
a sweep that silently mutated the public database would be very hard to undo.

Input comes from ``topology_public`` itself: the table stores each proteoform's input
sequence precisely so consumers need not re-fetch FASTAs. Reusing those exact sequences is
what makes the v1/v2 comparison like-for-like rather than approximate.

**v1 rows cannot be touched.** ``topology_public``'s primary key is
``(topology_version, cohort, uniprot_acc_full)`` and the uploader uses ``INSERT OR
IGNORE``, so a fresh ``topology_version`` is a disjoint namespace. The upload step asserts
the v1 row count is unchanged before and after regardless.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import modal

# --------------------------------------------------------------------------- #
# image
# --------------------------------------------------------------------------- #

# The distribution is named ``deeptmhmm2_predictor``; ``dtm2`` is only the console
# script it installs. A PEP 508 direct reference has to carry the distribution name or
# the install fails on a metadata name mismatch.
DTM2_COMMIT = "b05e27adf50738405e1de0b4a6b7072bb145fd3a"  # upstream main, 2026-08-28
DTM2_SPEC = f"deeptmhmm2_predictor @ git+https://github.com/fteufel/DeepTMHMM2.git@{DTM2_COMMIT}"

# Weights live where deeptmhmm2_predictor.weights.get_cache_dir() looks: $XDG_CACHE_HOME
# (or ~/.cache) / deeptmhmm2. Pinning XDG_CACHE_HOME keeps that path stable no matter
# what HOME a container gets.
WEIGHTS_DIR = "/opt/cache/deeptmhmm2"

# Model weights are baked into the image rather than downloaded at runtime: the
# ensemble is 5 topology heads + 5 membrane-type heads on ESM2-650M, and fetching
# that per container would dominate the run and hammer the upstream hosts.
#
# Baking also pins them. Upstream's weights.py sets ``_WEIGHTS_REF = "main"`` with the
# author's own "ideally pin to a tag/SHA" note still attached, so the checkpoints behind
# a given package version can change under us. The image freezes whatever ``main`` served
# at build time, and ``weights_fingerprint`` digests it so the published rows record
# which checkpoints actually produced them.
image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("git", "ca-certificates")
    .pip_install("uv>=0.5")
    .env({"XDG_CACHE_HOME": "/opt/cache"})
    .run_commands(f"uv pip install --system --no-cache '{DTM2_SPEC}'")
    # Warm the caches so every container starts with weights on disk.
    .run_commands(
        'python -c "import pathlib; '
        "pathlib.Path('/tmp/warm.fasta').write_text('>warm\\nMKTIIALSYIFCLVFADYKDDDDK\\n')\" "
        "&& dtm2 /tmp/warm.fasta /tmp/warm_out --device cpu --batch-size 1"
    )
    .env({"HF_HOME": "/opt/cache/huggingface", "TORCH_HOME": "/opt/cache/torch"})
)

app = modal.App("surfaceome-deeptmhmm2")
volume = modal.Volume.from_name("surfaceome-topology2", create_if_missing=True)
# Only the local entrypoint reads D1 (from the local .env); the GPU workers are given
# their sequences in the payload and need no credentials at all.
OUT_MOUNT = "/topology2"

# ESM2 attention is quadratic in sequence length, so one very long proteoform can OOM a
# GPU that handles everything else comfortably. Three bands, sized from the actual length
# distribution of the 20,224 human proteoforms in topology_public (p50 456 aa, p90 1,187,
# p99 3,038, max 14,507):
#
#   <= 2,500 aa   19,882 forms, 11.2M residues   T4,   shards of 200
#   <= 6,000 aa      329 forms,  1.2M residues   A10G, shards of 20
#   >  6,000 aa       13 forms,  110k residues   A10G, one per container
#
# The middle band matters: routing all 342 over-2,500 forms to their own container would
# burn 342 A10G starts for sequences a shared container handles fine. Only the 13 genuine
# outliers need isolation. Thresholds are a starting point — the canary reports measured
# throughput per band so they can be retuned from evidence.
LONG_SEQ_AA = 2_500
HUGE_SEQ_AA = 6_000
SHARD_SIZE = 200
LONG_SHARD_SIZE = 20


# --------------------------------------------------------------------------- #
# input
# --------------------------------------------------------------------------- #


def _fetch_proteoforms(
    limit: int | None = None, *, cohorts: tuple[str, ...]
) -> list[dict]:
    """Every distinct human proteoform in topology_public, with its v1 input sequence.

    One row per accession, not per (cohort, accession): the prediction depends only on
    the sequence, so a proteoform present in both cohorts is predicted once. Fanning the
    result back out to every (cohort, accession) pair is the publish step's job.

    Keyed on ``uniprot_acc_full`` — the stable ID. ``gene_symbol`` is denormalized in this
    table and is explicitly not a join key; joining on it produces false misses whenever
    paralogs share an accession (OR4F3 / OR4F16 / OR4F29 all resolve to Q6IEY1).
    """
    from accessible_surfaceome.cloud.d1_client import D1Client
    from accessible_surfaceome.env import load_env

    load_env()
    placeholders = ", ".join(["?"] * len(cohorts))
    sql = (
        "SELECT uniprot_acc_full, uniprot_acc, cohort, gene_symbol, hgnc_id, isoform_id, "
        "       species, is_canonical, sequence, protein_length "
        "FROM topology_public WHERE cohort IN (" + placeholders + ") "
        "GROUP BY uniprot_acc_full "
        "ORDER BY protein_length ASC"
    )
    if limit:
        sql += f" LIMIT {int(limit)}"
    with D1Client.public() as d1:
        return d1.query(sql, list(cohorts))


def _shard(records: list[dict], size: int) -> list[list[dict]]:
    return [records[i : i + size] for i in range(0, len(records), size)]


# --------------------------------------------------------------------------- #
# worker
# --------------------------------------------------------------------------- #


def _predict(records: list[dict], run_id: str, shard_id: str) -> dict:
    """Run dtm2 over one shard and write its raw outputs to the volume."""
    import subprocess
    import tempfile

    started = time.time()
    out_dir = Path(OUT_MOUNT) / run_id / shard_id
    out_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        fasta = Path(tmp) / "in.fasta"
        with fasta.open("w") as handle:
            for r in records:
                seq = r["sequence"]
                handle.write(f">{r['uniprot_acc_full']}\n")
                handle.write(
                    "\n".join(seq[i : i + 60] for i in range(0, len(seq), 60)) + "\n"
                )
        raw = Path(tmp) / "out"
        # No --simplify-io: keep the full v2 alphabet. The v1-comparable string is
        # derived downstream, so the richer call is never thrown away at source.
        proc = subprocess.run(
            ["dtm2", str(fasta), str(raw), "--batch-size", "1"],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            return {
                "shard": shard_id,
                "ok": False,
                "n": len(records),
                "error": proc.stderr[-2000:],
                "seconds": time.time() - started,
            }
        for produced in raw.iterdir():
            if produced.is_file():
                (out_dir / produced.name).write_bytes(produced.read_bytes())

    (out_dir / "manifest.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "shard": shard_id,
                "n": len(records),
                "accessions": [r["uniprot_acc_full"] for r in records],
                "residues": sum(r["protein_length"] for r in records),
                "seconds": time.time() - started,
            },
            indent=2,
        )
    )
    volume.commit()
    return {
        "shard": shard_id,
        "ok": True,
        "n": len(records),
        "residues": sum(r["protein_length"] for r in records),
        "seconds": time.time() - started,
    }


@app.function(
    image=image,
    gpu="T4",
    timeout=60 * 60,
    retries=modal.Retries(max_retries=2, backoff_coefficient=2.0),
    volumes={OUT_MOUNT: volume},
    max_containers=50,
)
def predict_shard(payload: dict) -> dict:
    return _predict(payload["records"], payload["run_id"], payload["shard_id"])


@app.function(
    image=image,
    gpu="A10G",
    timeout=90 * 60,
    retries=modal.Retries(max_retries=1),
    volumes={OUT_MOUNT: volume},
    max_containers=4,
)
def predict_long(payload: dict) -> dict:
    """The two long bands: 2.5-6 kaa in shards of 20, and the >6 kaa outliers alone."""
    return _predict(payload["records"], payload["run_id"], payload["shard_id"])


@app.function(image=image, timeout=300)
def weights_fingerprint() -> str:
    """``deeptmhmm2_predictor-<version>+ckpt.<12 hex>`` — the value published as
    ``tool_version``.

    The checkpoint digest is not decoration. Upstream resolves weights from a moving
    branch, so the package version alone does not identify what ran; two sweeps tagged
    ``deeptmhmm2_predictor-0.1.0`` could disagree. The digest covers all ten checkpoints
    in build order, so a weights change is visible as a different ``tool_version``.
    """
    import hashlib
    from importlib.metadata import version

    digest = hashlib.sha256()
    for ckpt in sorted(Path(WEIGHTS_DIR).glob("*.ckpt")):
        digest.update(ckpt.name.encode())
        with ckpt.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1 << 20), b""):
                digest.update(chunk)
    n = len(list(Path(WEIGHTS_DIR).glob("*.ckpt")))
    if n != 10:
        raise RuntimeError(f"expected 10 checkpoints in {WEIGHTS_DIR}, found {n}")
    return f"deeptmhmm2_predictor-{version('deeptmhmm2_predictor')}+ckpt.{digest.hexdigest()[:12]}"


# --------------------------------------------------------------------------- #
# entrypoints
# --------------------------------------------------------------------------- #

# Modal's published T4 and A10G rates. Update if Modal's pricing changes; the canary
# reports the arithmetic so a stale constant is visible rather than silent.
USD_PER_GPU_SECOND = {"T4": 0.000164, "A10G": 0.000306}


def _plan(records: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    """Split into the three GPU bands described at LONG_SEQ_AA."""
    short = [r for r in records if r["protein_length"] <= LONG_SEQ_AA]
    long_ = [r for r in records if LONG_SEQ_AA < r["protein_length"] <= HUGE_SEQ_AA]
    huge = [r for r in records if r["protein_length"] > HUGE_SEQ_AA]
    return short, long_, huge


def _payloads(records: list[dict], run_id: str, size: int, prefix: str) -> list[dict]:
    return [
        {"records": s, "run_id": run_id, "shard_id": f"{prefix}{i:04d}"}
        for i, s in enumerate(_shard(records, size))
    ]


@app.local_entrypoint()
def canary(n: int = 50, cohorts: str = "human_canonical,human_isoforms") -> None:
    """Run a small sample, report measured throughput and a projected full-sweep cost.

    Writes to the volume under run_id ``canary_<timestamp>`` and nothing to D1.
    """
    cohort_tuple = tuple(c.strip() for c in cohorts.split(","))
    everything = _fetch_proteoforms(cohorts=cohort_tuple)
    total_aa = sum(r["protein_length"] for r in everything)
    a_all, b_all, c_all = _plan(everything)
    print(
        f"proteoform set: {len(everything):,} across {cohort_tuple}, {total_aa:,} residues"
    )
    print(f"  <= {LONG_SEQ_AA:,} aa : {len(a_all):>6,}   T4,   shards of {SHARD_SIZE}")
    print(
        f"  <= {HUGE_SEQ_AA:,} aa : {len(b_all):>6,}   A10G, shards of {LONG_SHARD_SIZE}"
    )
    print(
        f"  >  {HUGE_SEQ_AA:,} aa : {len(c_all):>6,}   A10G, one per container "
        f"(longest {max(r['protein_length'] for r in everything):,} aa)"
    )

    # Sample across the length distribution rather than the head: the query is ordered by
    # length, so the first n would project the whole sweep from the shortest proteoforms.
    step = max(1, len(everything) // n)
    sample = everything[::step][:n]
    run_id = f"canary_{int(time.time())}"
    a, b, c = _plan(sample)
    print(
        f"\ncanary: {len(sample)} proteoforms "
        f"({len(a)}/{len(b)}/{len(c)} by band), run_id={run_id}"
    )

    started = time.time()
    results = []
    if a:
        results += list(predict_shard.map(_payloads(a, run_id, SHARD_SIZE, "s")))
    if b:
        results += list(predict_long.map(_payloads(b, run_id, LONG_SHARD_SIZE, "L")))
    if c:
        results += list(predict_long.map(_payloads(c, run_id, 1, "H")))
    wall = time.time() - started

    ok = [r for r in results if r.get("ok")]
    failed = [r for r in results if not r.get("ok")]
    done_aa = sum(r.get("residues", 0) for r in ok)
    gpu_s = sum(r.get("seconds", 0) for r in ok)
    print(
        f"\nwall {wall:.0f}s   GPU-seconds {gpu_s:.0f}   "
        f"{len(ok)}/{len(results)} shards ok"
    )
    for f in failed:
        print(f"  FAILED {f['shard']}: {f.get('error', '')[:300]}")
    if not done_aa:
        print("\nno residues completed — not projecting a cost from nothing")
        return

    per_aa = gpu_s / done_aa
    proj_s = per_aa * total_aa
    proj_usd = proj_s * USD_PER_GPU_SECOND["T4"]
    print(f"\nmeasured   {per_aa * 1000:.2f} GPU-seconds per 1k residues")
    print(f"projection {total_aa:,} residues -> {proj_s / 3600:.1f} GPU-hours")
    print(
        f"           ~${proj_usd:,.2f} at the T4 rate, before A10G time for the "
        f"{len(b_all) + len(c_all)} sequences over {LONG_SEQ_AA:,} aa"
    )
    print("\nreview then: modal run modal/deeptmhmm2_app.py::full_sweep --run-id <id>")


@app.local_entrypoint()
def full_sweep(
    run_id: str,
    cohorts: str = "human_canonical,human_isoforms",
    max_gpu_hours: float = 40.0,
) -> None:
    """Predict every proteoform. Writes to the volume only; D1 publishing is separate."""
    cohort_tuple = tuple(c.strip() for c in cohorts.split(","))
    records = _fetch_proteoforms(cohorts=cohort_tuple)
    a, b, c = _plan(records)
    print(
        f"{len(records):,} proteoforms ({len(a):,}/{len(b):,}/{len(c):,} by band), "
        f"{sum(r['protein_length'] for r in records):,} residues, run_id={run_id}"
    )

    started = time.time()
    results = list(predict_shard.map(_payloads(a, run_id, SHARD_SIZE, "s")))
    results += list(predict_long.map(_payloads(b, run_id, LONG_SHARD_SIZE, "L")))
    results += list(predict_long.map(_payloads(c, run_id, 1, "H")))

    ok = [r for r in results if r.get("ok")]
    failed = [r for r in results if not r.get("ok")]
    gpu_h = sum(r.get("seconds", 0) for r in ok) / 3600
    print(
        f"\nwall {(time.time() - started) / 60:.1f} min   GPU-hours {gpu_h:.1f}   "
        f"shards {len(ok)}/{len(results)} ok"
    )
    if gpu_h > max_gpu_hours:
        print(f"WARNING: exceeded the {max_gpu_hours} GPU-hour expectation")
    for f in failed:
        print(f"  FAILED {f['shard']} (n={f['n']}): {f.get('error', '')[:300]}")
    covered = sum(r["n"] for r in ok)
    print(f"\n{covered:,}/{len(records):,} proteoforms predicted")
    print(f"pull with: modal volume get surfaceome-topology2 {run_id}")
    print("nothing was written to D1 — publish as a separate, reviewed step")
