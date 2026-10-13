"""Run DeepTMHMM **1.0.24** (v1) on Modal.

Same predictor as every topology row this project serves (``tool_version =
deeptmhmm-1.0.24``) — a TM-helix count or ECD length is only comparable to
another call from the same model, so this is the runner to use for any
accession the topology sweep has not covered (e.g. orthologs that are new in
a Compara release). DeepTMHMM2 (``deeptmhmm2_app.py`` on ``dev``) is a
different model.

The package is license-gated (CC BY-NC-SA 4.0) and is **not** committed. It
lives on the ``deeptmhmm-v1`` Modal volume, uploaded once from a local copy::

    modal volume create deeptmhmm-v1
    modal volume put deeptmhmm-v1 <path>/DeepTMHMM-Academic-License-v1.0 /DeepTMHMM-Academic-License-v1.0

Dependencies are a pinned modern stack; the upstream README's
``torch 1.5.0+cu92`` is a legacy wheel that no longer installs.

Input is a UniProt-style FASTA (``>sp|ACC|ENTRY ...``), which is what
``sources.deeptmhmm.parse_3line`` expects back in the 3-line output::

    modal run modal/deeptmhmm_v1_app.py::canary --fasta in.fasta --n 2
    modal run modal/deeptmhmm_v1_app.py::sweep --fasta in.fasta --out out.3line

Ported from deliverome-analysis (appris-principal shortlist), unchanged apart
from this docstring.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import modal

# A path the base image definitely does not already populate: Modal refuses to
# mount a volume over a non-empty directory, and /pkg collided.
MOUNT = "/deeptmhmm"
PACKAGE = f"{MOUNT}/DeepTMHMM-Academic-License-v1.0"
# DeepTMHMM holds every sequence's ESM embedding in memory, so a shard is kept small enough
# that a long protein cannot push the worker into swap.
SHARD_RESIDUES = 60_000
LONG_SEQUENCE = 3_000

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("libhdf5-dev", "build-essential")
    .pip_install(
        "biopython==1.79",
        "fair-esm==0.4.0",
        "h5py==3.12.1",
        "PeptideBuilder==1.1.0",
        "matplotlib==3.9.2",
        "numpy==1.26.4",
        "requests==2.32.5",
        "tqdm==4.67.1",
        "torch==2.5.1",
    )
)

app = modal.App("surfaceome-deeptmhmm-v1")
package_volume = modal.Volume.from_name("deeptmhmm-v1", create_if_missing=True)
out_volume = modal.Volume.from_name("deeptmhmm-v1-runs", create_if_missing=True)


def _read_fasta(text: str) -> list[tuple[str, str]]:
    out, name, buf = [], None, []
    for line in text.splitlines():
        if line.startswith(">"):
            if name:
                out.append((name, "".join(buf)))
            name, buf = line[1:].strip(), []
        elif name:
            buf.append(line.strip())
    if name:
        out.append((name, "".join(buf)))
    return out


def _shard(records: list[tuple[str, str]], budget: int) -> list[list[tuple[str, str]]]:
    shards, cur, total = [], [], 0
    for rec in records:
        if cur and total + len(rec[1]) > budget:
            shards.append(cur)
            cur, total = [], 0
        cur.append(rec)
        total += len(rec[1])
    if cur:
        shards.append(cur)
    return shards


def _run_predict(records: list[tuple[str, str]], tag: str) -> dict:
    """Invoke the vendored predict.py and return its 3-line topology output."""
    import subprocess
    import sys
    import tempfile

    started = time.time()
    with tempfile.TemporaryDirectory() as tmp:
        fasta = Path(tmp) / "in.fasta"
        fasta.write_text("".join(f">{n}\n{s}\n" for n, s in records))
        outdir = Path(tmp) / "out"  # predict.py refuses a directory that already exists
        proc = subprocess.run(
            [sys.executable, "predict.py", "--fasta", str(fasta), "--output-dir", str(outdir)],
            cwd=PACKAGE,
            capture_output=True,
            text=True,
        )
        three = outdir / "predicted_topologies.3line"
        if proc.returncode != 0 or not three.exists():
            return {
                "tag": tag,
                "n": len(records),
                "ok": False,
                "error": (proc.stderr or proc.stdout)[-2000:],
            }
        return {
            "tag": tag,
            "n": len(records),
            "ok": True,
            "seconds": round(time.time() - started, 1),
            "three_line": three.read_text(),
        }


@app.function(
    image=image,
    gpu="T4",
    timeout=60 * 60,
    volumes={MOUNT: package_volume},
)
def predict_shard(payload: dict) -> dict:
    return _run_predict([tuple(r) for r in payload["records"]], payload["tag"])


@app.function(
    image=image,
    gpu="A10G",
    timeout=120 * 60,
    volumes={MOUNT: package_volume},
)
def predict_long(payload: dict) -> dict:
    """Long sequences get more memory; v1's ESM step is what OOMs, not the CRF."""
    return _run_predict([tuple(r) for r in payload["records"]], payload["tag"])


@app.local_entrypoint()
def canary(n: int = 8, fasta: str = "../topology_shortlist.fasta") -> None:
    """Prove the image and the volume before paying for the full sweep."""
    records = _read_fasta(Path(fasta).read_text())[:n]
    res = predict_shard.remote({"records": records, "tag": "canary"})
    print(json.dumps({k: v for k, v in res.items() if k != "three_line"}, indent=2))
    if res.get("ok"):
        print(res["three_line"][:600])


@app.local_entrypoint()
def sweep(fasta: str = "../topology_shortlist.fasta", out: str = "../topology_shortlist.3line") -> None:
    records = _read_fasta(Path(fasta).read_text())
    short = [r for r in records if len(r[1]) <= LONG_SEQUENCE]
    long_ = [r for r in records if len(r[1]) > LONG_SEQUENCE]
    shards = [{"records": s, "tag": f"s{i}"} for i, s in enumerate(_shard(short, SHARD_RESIDUES))]
    longs = [{"records": [r], "tag": f"L{i}"} for i, r in enumerate(long_)]
    print(f"{len(records)} sequences -> {len(shards)} shards + {len(longs)} long singletons")

    results = list(predict_shard.map(shards)) + (
        list(predict_long.map(longs)) if longs else []
    )
    ok = [r for r in results if r.get("ok")]
    bad = [r for r in results if not r.get("ok")]
    Path(out).write_text("".join(r["three_line"] for r in ok))
    Path(out + ".failures.json").write_text(json.dumps(bad, indent=2))
    print(f"wrote {out}: {len(ok)} shards ok, {len(bad)} failed")
