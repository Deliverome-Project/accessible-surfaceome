"""ProDomino insertion-site prediction on GPU, for comparison against our lanes.

ProDomino (Niopek Lab, Nature Methods 2025) predicts a per-position probability
that a protein tolerates a domain insertion. It is the only published method
with a relevant benchmark, and it is interesting here precisely because it works
differently from everything we do: no structure, no RSA, no pLDDT, no
conservation — ESM-2 3B embeddings and an MLP head, trained on a semi-synthetic
dataset built from naturally occurring intradomain insertion events.

That makes it a real test of our premise rather than a variation on it. Our
lanes gate on structural properties the field's own literature calls weak
("even simple constraints such as surface exposure are prone to misguided
selection of insertion sites"), so a sequence-only model disagreeing with them
is informative either way.

WHY MODAL: the embedder needs ESM-2 3B, about 11 GB of weights plus activations
for sequences up to ~1,600 residues. The dev laptop has 5.6 GB free and no CUDA.
The weights are cached in a Volume so only the first run pays the download.

LICENCE: ProDomino is CC BY-NC 4.0 — NON-COMMERCIAL. Predictions from it carry
that restriction. Keep it out of anything shipped commercially, and cite the
paper wherever its output is used.

    modal run modal/prodomino_app.py --limit 20          # smoke test
    modal run modal/prodomino_app.py::score_cohort --run-id prodomino_v1
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import modal

REPO = "https://github.com/Niopek-Lab/ProDomino.git"

image = (
    modal.Image.debian_slim(python_version="3.10")
    .apt_install("git")
    .pip_install(
        # Pinned to the environment.yml the authors validated against; the CUDA
        # build comes from the Modal base image rather than pytorch-cuda.
        "torch==2.1.0",
        "lightning==2.3.0",
        "torchmetrics==1.4.0",
        "fair-esm==2.0.0",
        "fairscale==0.4.13",
        "biopython==1.81",
        "numpy==1.26.4",
        "fsspec==2024.3.0",
        # ProDomino/__init__.py imports its plotting utilities unconditionally,
        # so these are required even though we only want the scores. Pinned to
        # the authors' environment.yml.
        "matplotlib==3.8.1",
        "seaborn==0.13.1",
        "py3Dmol==2.1.0",
    )
    .run_commands(f"git clone --depth 1 {REPO} /opt/ProDomino")
)

app = modal.App("surfaceome-prodomino")
out_volume = modal.Volume.from_name("prodomino-runs", create_if_missing=True)
# ESM-2 3B is ~11 GB; downloading it per container would dominate the run.
esm_cache = modal.Volume.from_name("esm2-weights", create_if_missing=True)

OUT = "/runs"
TORCH_HUB = "/esm"


@app.cls(
    image=image,
    # A10G (22 GB) OOMs on a 1,406-residue sequence: ESM-2 3B's activations
    # scale with length and the cohort runs to 1,651 residues, with 61 sequences
    # over 1,000. A100-40GB clears the longest of them with room to spare.
    gpu="A100-40GB",
    timeout=60 * 60,
    retries=modal.Retries(max_retries=1),
    volumes={OUT: out_volume, TORCH_HUB: esm_cache},
    max_containers=8,
)
class Scorer:
    """Model loaded ONCE per container.

    `Embedder()` initialises a fairscale distributed process group. A plain
    function re-runs that for every input, and Modal reuses containers across
    inputs, so the second shard a container saw died with "trying to initialize
    the default process group twice". A single-shard smoke test cannot catch
    this — there is no reuse with one input — which is why it only appeared on
    the full run.

    Loading once is also what makes the run affordable: ESM-2 3B takes most of a
    minute to load and about a second per sequence afterwards.
    """

    @modal.enter()
    def load(self) -> None:
        import os
        import sys

        os.environ["TORCH_HOME"] = TORCH_HUB
        sys.path.insert(0, "/opt/ProDomino/src")
        from ProDomino import Embedder, ProDomino  # ty: ignore[unresolved-import]

        self.embedder = Embedder()
        self.model = ProDomino(
            "/opt/ProDomino/checkpoints/main_checkpoint.ckpt", "mini_3b_mlp"
        )

    @modal.method()
    def score_shard(self, payload: dict) -> dict:
        """Per-position insertion-tolerance scores for one shard of sequences."""
        records = payload["records"]
        run_id = payload["run_id"]
        shard_id = payload["shard_id"]

        results, failures = [], []
        for rec in records:
            seq = (rec.get("sequence") or "").strip().upper()
            if not seq:
                failures.append({"gene": rec.get("gene"), "why": "no sequence"})
                continue
            t0 = time.monotonic()
            try:
                embed = self.embedder.predict_embedding(seq)
                pred = self.model.predict_insertion_sites(embed)
                # predict_insertion_sites returns an InsertionSitePrediction, not
                # a sequence: the per-position sigmoid is on .predicted_sites.
                import torch

                raw = pred.predicted_sites
                if isinstance(raw, torch.Tensor):
                    raw = raw.detach().float().cpu().numpy()
                scores = [round(float(x), 5) for x in list(raw.reshape(-1))]
            except Exception as exc:  # noqa: BLE001 - one bad gene must not kill a shard
                failures.append(
                    {"gene": rec.get("gene"), "why": f"{type(exc).__name__}: {exc}"[:200]}
                )
                _free_gpu()
                continue
            _free_gpu()
            results.append(
                {
                    "gene_symbol": rec.get("gene"),
                    "uniprot_acc": rec.get("acc"),
                    "length": len(seq),
                    "scores": scores,
                    "n_scores": len(scores),
                    "secs": round(time.monotonic() - t0, 1),
                }
            )

        path = Path(OUT) / run_id
        path.mkdir(parents=True, exist_ok=True)
        (path / f"shard-{shard_id:04d}.json").write_text(
            json.dumps({"results": results, "failures": failures})
        )
        out_volume.commit()
        esm_cache.commit()
        return {"shard": shard_id, "ok": len(results), "failed": len(failures)}


def _free_gpu() -> None:
    """Drop cached allocations between sequences.

    Activations scale with length, so without this a 1,600-residue protein
    leaves the allocator fragmented and the NEXT sequence OOMs on memory that
    is free but unusable — which reads as a failure of the wrong gene."""
    try:
        import gc

        import torch

        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:  # noqa: BLE001 - best effort
        pass


def _shard(records: list[dict], size: int) -> list[list[dict]]:
    return [records[i : i + size] for i in range(0, len(records), size)]


@app.local_entrypoint()
def main(sequences: str = "", limit: int = 0, run_id: str = "", shard_size: int = 5) -> None:
    """Score sequences from a JSON file of ``[{gene, acc, sequence}, ...]``.

    Sequences are passed in rather than fetched here: the viewer records do not
    carry them, and the comparison has to run on exactly the proteins our lanes
    were scored on, which the caller decides."""
    run_id = run_id or f"prodomino-{int(time.time())}"
    if not sequences:
        print("pass --sequences <path to JSON [{gene, acc, sequence}, ...]>")
        return
    recs = json.loads(Path(sequences).read_text())
    recs = [r for r in recs if (r.get("sequence") or "").strip()]
    if limit:
        recs = recs[:limit]
    if not recs:
        print("no usable sequences in", sequences)
        return

    shards = _shard(recs, shard_size)
    print(f"run {run_id}: {len(recs)} sequences in {len(shards)} shard(s)")
    payloads = [
        {"records": s, "run_id": run_id, "shard_id": i} for i, s in enumerate(shards)
    ]
    done = list(Scorer().score_shard.map(payloads))
    ok = sum(d["ok"] for d in done)
    bad = sum(d["failed"] for d in done)
    print(f"scored {ok} sequence(s), {bad} failed -> volume prodomino-runs/{run_id}")
