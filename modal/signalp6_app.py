"""Modal app — SignalP 6.0 (slow-sequential) over the human proteoform set.

SignalP 6 gives a cleavage site and a signal-peptide *type* (Sec/SPI, Sec/SPII,
Tat/SPI, ...) that DeepTMHMM does not: DeepTMHMM says "there is a signal peptide and it
ends here", SignalP says which secretion pathway it belongs to and how confident each
position is. Run in ``slow-sequential`` mode, which is the full six-model ensemble
evaluated one model at a time.

STAGE FIRST -- ``scripts/cloud/stage_signalp6.sh`` splits the DTU tarball and uploads the
checkpoints, then ``convert_models`` prepares them for GPU. Neither happens here.

    uv run modal run modal/signalp6_app.py::convert_models     # one-time
    uv run modal run modal/signalp6_app.py::canary --n 200     # measure, writes no D1
    uv run modal run modal/signalp6_app.py::full_sweep --run-id sp6_...

**Cost does not scale with protein length.** ``signalp/utils.py`` truncates every input to
its first 70 residues and pads to a fixed 73 tokens, because the traced model was built at
that fixed length. A 14,507-aa titin isoform costs exactly what a 100-aa peptide costs.
That is why there is no length banding here, unlike deeptmhmm2_app.py -- one uniform band
with large batches is correct, and the only thing that drives cost is how many sequences
are submitted.

Like the DeepTMHMM2 app, nothing here writes to D1. Output streams to the
``signalp6-runs`` Volume and publishing is a separate reviewed step.
"""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

import modal

# --------------------------------------------------------------------------- #
# image
# --------------------------------------------------------------------------- #

PKG_DIR = Path(__file__).parent / ".signalp6-pkg"

if not PKG_DIR.is_dir():
    # Checked here rather than left to add_local_dir, which only raises after Modal has
    # already built the torch image -- a slow way to be told to run one script.
    raise SystemExit(
        f"SignalP 6 is not staged: {PKG_DIR} does not exist.\n"
        "The package is gitignored because it is DTU-licensed and must not be committed.\n"
        "Stage it first:\n"
        "    scripts/cloud/stage_signalp6.sh /path/to/signalp-6.0i.slow_sequential.tar.gz"
    )

# SignalP 6 pins ``torch>1.7.0,<2``; DeepTMHMM2 pins ``torch==2.10.0``. The two tools
# cannot share an image, and this is not a version range worth fighting -- the SignalP
# checkpoints are TorchScript traces made under torch 1.x.
image = (
    modal.Image.debian_slim(python_version="3.10")
    .pip_install(
        "torch==1.13.1+cu117",
        extra_index_url="https://download.pytorch.org/whl/cu117",
    )
    .pip_install("matplotlib>3.3.2", "numpy>1.19.2,<2", "tqdm>4.46.1")
    .add_local_dir(PKG_DIR, "/opt/signalp6-package", copy=True)
    .run_commands("pip install --no-deps /opt/signalp6-package")
)

app = modal.App("surfaceome-signalp6")
models = modal.Volume.from_name("signalp6-models", create_if_missing=True)
runs = modal.Volume.from_name("signalp6-runs", create_if_missing=True)
MODELS_MOUNT = "/models"
RUNS_MOUNT = "/runs"

# 73 fixed tokens per sequence, so batches are bounded by count, not by residues.
SHARD_SIZE = 2_000
BATCH_SIZE = 64
USD_PER_GPU_SECOND = {"T4": 0.000164}

# DeepTMHMM v1 labels that mean "this sequence has a signal peptide".
SP_LABELS = ("SP", "SP+TM")


# --------------------------------------------------------------------------- #
# input
# --------------------------------------------------------------------------- #


def _fetch_sequences(*, cohorts: tuple[str, ...], gate: str) -> list[dict]:
    """Human proteoforms to submit, keyed on ``uniprot_acc_full``.

    ``gate='deeptmhmm_sp'`` restricts to sequences DeepTMHMM v1 already called SP-positive.
    That inherits v1's false negatives -- SignalP never sees a protein v1 called GLOB or
    TM, so it cannot overturn one. ``gate='all'`` submits everything; given the fixed
    73-token cost the difference is roughly 3.5x of a very small number, so prefer 'all'
    unless there is a reason beyond cost.

    ``gene_symbol`` is denormalized in topology_public and is not a join key.
    """
    from accessible_surfaceome.cloud.d1_client import D1Client
    from accessible_surfaceome.env import load_env

    load_env()
    placeholders = ", ".join(["?"] * len(cohorts))
    where = f"cohort IN ({placeholders})"
    params = list(cohorts)
    if gate == "deeptmhmm_sp":
        where += f" AND deeptmhmm_label IN ({', '.join(['?'] * len(SP_LABELS))})"
        params += list(SP_LABELS)
    elif gate != "all":
        raise ValueError(f"unknown gate {gate!r}; use 'deeptmhmm_sp' or 'all'")
    sql = (
        "SELECT uniprot_acc_full, uniprot_acc, hgnc_id, cohort, is_canonical, "
        "       sequence, protein_length, deeptmhmm_label "
        f"FROM topology_public WHERE {where} "
        "GROUP BY uniprot_acc_full ORDER BY uniprot_acc_full"
    )
    with D1Client.public() as d1:
        return d1.query(sql, params)


def _shard(records: list[dict], size: int) -> list[list[dict]]:
    return [records[i : i + size] for i in range(0, len(records), size)]


# --------------------------------------------------------------------------- #
# one-time model preparation
# --------------------------------------------------------------------------- #


@app.function(
    image=image,
    gpu="T4",
    timeout=60 * 60,
    volumes={MODELS_MOUNT: models},
)
def convert_models(force: bool = False) -> str:
    """Copy the CPU checkpoints to ``/models/gpu`` and convert them there, once.

    ``signalp6_convert_models`` rewrites checkpoints **in place**, and GPU-converted
    weights cannot be run on CPU. So the CPU originals are never touched: they stay under
    ``/models/cpu`` as the thing the staging script uploaded, and the conversion works on
    a copy. Re-running with ``--force`` re-copies from the originals, which is what makes
    a failed conversion recoverable without another 9.8 GB upload.
    """
    import subprocess

    src = Path(MODELS_MOUNT) / "cpu/sequential_models_signalp6"
    dst = Path(MODELS_MOUNT) / "gpu/sequential_models_signalp6"
    if not src.exists():
        raise RuntimeError(
            f"{src} is empty — run scripts/cloud/stage_signalp6.sh first"
        )
    if dst.exists():
        if not force:
            return (
                f"already converted: {dst} ({len(list(dst.glob('*.pt')))} checkpoints)"
            )
        shutil.rmtree(dst)

    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst)
    proc = subprocess.run(
        ["signalp6_convert_models", "gpu", str(dst)],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        shutil.rmtree(dst, ignore_errors=True)
        raise RuntimeError(
            f"conversion failed, /models/gpu removed:\n{proc.stderr[-2000:]}"
        )
    models.commit()
    return f"converted {len(list(dst.glob('*.pt')))} checkpoints -> {dst}"


# --------------------------------------------------------------------------- #
# worker
# --------------------------------------------------------------------------- #


@app.function(
    image=image,
    gpu="T4",
    timeout=60 * 60,
    retries=modal.Retries(max_retries=2, backoff_coefficient=2.0),
    volumes={MODELS_MOUNT: models, RUNS_MOUNT: runs},
    max_containers=20,
)
def predict_shard(payload: dict) -> dict:
    """Run SignalP 6 slow-sequential over one shard."""
    import subprocess
    import tempfile

    records, run_id, shard_id = (
        payload["records"],
        payload["run_id"],
        payload["shard_id"],
    )
    started = time.time()
    out_dir = Path(RUNS_MOUNT) / run_id / shard_id
    out_dir.mkdir(parents=True, exist_ok=True)
    model_dir = Path(MODELS_MOUNT) / "gpu"
    if not model_dir.exists():
        raise RuntimeError("no GPU checkpoints — run convert_models first")

    with tempfile.TemporaryDirectory() as tmp:
        fasta = Path(tmp) / "in.fasta"
        with fasta.open("w") as handle:
            for r in records:
                # Only the first 70 residues are read, but writing the whole sequence
                # keeps the input honest and lets the output be re-derived if the
                # truncation length ever changes upstream.
                seq = r["sequence"]
                handle.write(f">{r['uniprot_acc_full']}\n")
                handle.write(
                    "\n".join(seq[i : i + 60] for i in range(0, len(seq), 60)) + "\n"
                )
        raw = Path(tmp) / "out"
        proc = subprocess.run(
            [
                "signalp6",
                "--fastafile",
                str(fasta),
                "--output_dir",
                str(raw),
                "--model_dir",
                str(model_dir),
                "--mode",
                "slow-sequential",
                # 'eukarya' post-processes to Sec/SPI only, which is correct for human and
                # suppresses the bacterial SP types the model can otherwise emit.
                "--organism",
                "eukarya",
                # 'none' writes only the summary tables. Per-sequence plots or .gff would
                # be one file per protein on a network volume, which dominates the run.
                "--format",
                "none",
                "--bsize",
                str(BATCH_SIZE),
                "--write_procs",
                "1",
            ],
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
                "mode": "slow-sequential",
                "organism": "eukarya",
                "seconds": time.time() - started,
            },
            indent=2,
        )
    )
    runs.commit()
    return {
        "shard": shard_id,
        "ok": True,
        "n": len(records),
        "seconds": time.time() - started,
    }


# --------------------------------------------------------------------------- #
# entrypoints
# --------------------------------------------------------------------------- #


def _payloads(records: list[dict], run_id: str, size: int) -> list[dict]:
    return [
        {"records": s, "run_id": run_id, "shard_id": f"s{i:04d}"}
        for i, s in enumerate(_shard(records, size))
    ]


def _report(results: list[dict], submitted: int, wall: float) -> tuple[int, float]:
    ok = [r for r in results if r.get("ok")]
    for f in (r for r in results if not r.get("ok")):
        print(f"  FAILED {f['shard']}: {f.get('error', '')[:300]}")
    gpu_s = sum(r.get("seconds", 0) for r in ok)
    done = sum(r["n"] for r in ok)
    print(
        f"\nwall {wall:.0f}s   GPU-seconds {gpu_s:.0f}   "
        f"{len(ok)}/{len(results)} shards ok   {done:,}/{submitted:,} sequences"
    )
    return done, gpu_s


@app.local_entrypoint()
def canary(
    n: int = 200,
    gate: str = "deeptmhmm_sp",
    cohorts: str = "human_canonical,human_isoforms",
) -> None:
    """Measure throughput on a sample and project both gates. Writes no D1."""
    cohort_tuple = tuple(c.strip() for c in cohorts.split(","))
    gated = _fetch_sequences(cohorts=cohort_tuple, gate="deeptmhmm_sp")
    everything = _fetch_sequences(cohorts=cohort_tuple, gate="all")
    print(f"gate 'deeptmhmm_sp': {len(gated):,} sequences")
    print(f"gate 'all'         : {len(everything):,} sequences")

    pool = gated if gate == "deeptmhmm_sp" else everything
    sample = pool[:: max(1, len(pool) // n)][:n]
    run_id = f"canary_{int(time.time())}"
    print(f"\ncanary: {len(sample)} sequences from gate {gate!r}, run_id={run_id}")

    started = time.time()
    results = list(predict_shard.map(_payloads(sample, run_id, SHARD_SIZE)))
    done, gpu_s = _report(results, len(sample), time.time() - started)
    if not done:
        print("\nno sequences completed — not projecting a cost from nothing")
        return

    per_seq = gpu_s / done
    print(f"\nmeasured   {per_seq * 1000:.1f} GPU-ms per sequence")
    for label, pool_ in (("deeptmhmm_sp", gated), ("all", everything)):
        proj = per_seq * len(pool_)
        print(
            f"projection {label:<13} {len(pool_):>6,} seq -> {proj / 3600:5.2f} GPU-hours"
            f"  ~${proj * USD_PER_GPU_SECOND['T4']:,.2f}"
        )
    print("\nreview then: modal run modal/signalp6_app.py::full_sweep --run-id <id>")


@app.local_entrypoint()
def full_sweep(
    run_id: str,
    gate: str = "deeptmhmm_sp",
    cohorts: str = "human_canonical,human_isoforms",
) -> None:
    """Predict every gated sequence. Writes to the volume only; D1 is a separate step."""
    cohort_tuple = tuple(c.strip() for c in cohorts.split(","))
    records = _fetch_sequences(cohorts=cohort_tuple, gate=gate)
    print(f"{len(records):,} sequences, gate={gate!r}, run_id={run_id}")

    started = time.time()
    results = list(predict_shard.map(_payloads(records, run_id, SHARD_SIZE)))
    _report(results, len(records), time.time() - started)
    print(f"\npull with: modal volume get signalp6-runs {run_id}")
    print("nothing was written to D1 — publish as a separate, reviewed step")
