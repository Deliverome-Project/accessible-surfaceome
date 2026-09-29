"""Modal app — per-residue disorder over the human proteoform set.

The question this exists to answer is narrow: **where does structure begin after a signal
peptide?** That is the downstream boundary for an N-terminal tag — the cleavage site fixes
the upstream one, and SignalP already gives us that. Tedman used NetSurfP-2.0 for it; the
field has moved twice since (NetSurfP-3.0 dropped the MSA step for ESM-1b embeddings, and
CAID3 in 2025 was swept by protein-language-model methods), so this benchmarks rather than
reproduces his choice.

Two predictors, chosen because they are the two that actually install:

* **metapredict v3** — pLM-based, CAID3 AUROC 0.81, pip-installable, very fast.
* **AlphaFold-disorder** — the CAID baseline, from AlphaFoldDB structures. It is NOT the
  same thing as "read pLDDT": it defines two scores, ``1 - pLDDT`` and a **windowed RSA**
  computed with DSSP over +/-12 residues, and CAID found the RSA variant the more accurate
  of the two. Included as the incumbent, since our tag_sites pipeline already ranks on
  AlphaFold RSA.

Not included, and why:

* **NetSurfP-3.0** — its trained head (``model_best.pth``) is not in the GitHub repo;
  ``models/url.txt`` lists only the upstream language models. Needs sourcing from DTU or
  BioLib before it can run at all.
* **flDPnn3** — top of CAID3, but distributed as a web server. Two third-party repos exist
  and neither is the authors' release.

    modal run modal/disorder_app.py::canary --n 50
    modal run modal/disorder_app.py::full_sweep --run-id dis_2026_09_28

As with the topology and SignalP apps, nothing here writes to D1. Output streams to the
``disorder-runs`` Volume and publishing is a separate reviewed step.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import modal

metapredict_image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install("metapredict==3.0.2", "numpy<2")
    # Warm the model into the image so containers do not each fetch it.
    .run_commands(
        "python -c \"import metapredict as m; m.predict_disorder('MKTIIALSYIFCLVFADYKDDDDK')\""
    )
)

# AlphaFold-disorder is a single script; DSSP is the real dependency.
afd_image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("dssp", "wget", "ca-certificates")
    .pip_install("biopython", "pandas", "numpy<2", "requests")
    .run_commands(
        "wget -q -O /opt/alphafold_disorder.py "
        "https://raw.githubusercontent.com/BioComputingUP/AlphaFold-disorder/main/alphafold_disorder.py"
    )
)

# NetSurfP-3.0, from the DTU standalone zip. The public GitHub repo cannot run: its
# Dockerfile loads a model_best.pth that is not in the tree. This checkpoint is.
# Staged by scripts/cloud/stage_netsurfp3.sh.
NSP3_PKG = Path(__file__).parent / ".netsurfp3-pkg"
NSP3_MOUNT = "/nsp3-model"

# NetSurfP-3.0 needs torch 1.8.0 / fair-esm 0.3.1 on Python 3.8 -- its checkpoint is a
# 2021 fair-esm roberta_large. Modal's image builder no longer supports 3.8 (3.10 is the
# floor) and torch 1.8 has no wheels above 3.9, so the two cannot be reconciled in one
# interpreter. The Modal function therefore runs on 3.11 and shells out to a private 3.8
# venv that holds the old stack. A third environment either way: SignalP wants torch<2,
# DeepTMHMM2 wants 2.10, this wants exactly 1.8.
NSP3_PYTHON = "/opt/nsp3-venv/bin/python"
netsurfp_image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install("uv>=0.5")
    .env({"UV_PYTHON_DOWNLOADS": "automatic"})
    .run_commands(
        "uv python install 3.8",
        f"uv venv --python 3.8 {Path(NSP3_PYTHON).parent.parent}",
        f"uv pip install --python {NSP3_PYTHON} torch==1.8.0+cu111 torchvision==0.9.0+cu111"
        " --extra-index-url https://download.pytorch.org/whl/cu111",
        f"uv pip install --python {NSP3_PYTHON} fair-esm==0.3.1 numpy==1.20.2"
        " biopython==1.78 click==7.1.2 pyyaml==5.4.1 pandas==1.2.3 scipy==1.6.2"
        " h5py==3.2.1 matplotlib==3.4.1 typing-extensions==3.7.4.3"
        # torchvision 0.9 imports PIL symbols that Pillow 9 removed, so an
        # unpinned Pillow breaks nsp3 at import. 8.2.0 is contemporary with it.
        " pillow==8.2.0",
        # Assert the venv is what we think it is. A silently-skipped install shows up
        # only as "No module named 'torch'" inside a worker, an hour and a GPU later.
        f'{NSP3_PYTHON} -c "import sys, torch, esm, torchvision.transforms;'
        " print('nsp3 venv:', sys.version.split()[0], 'torch', torch.__version__);"
        " assert sys.version_info[:2] == (3, 8), sys.version;"
        " assert torch.__version__.startswith('1.8'), torch.__version__\"",
    )
)
if modal.is_local():
    netsurfp_image = netsurfp_image.add_local_dir(NSP3_PKG, "/opt/nsp3", copy=True)

# ESM-1b is a roberta_large with max_positions 1024, and nsp3.py does not chunk or
# truncate -- it just runs the model, so a longer sequence breaks or silently corrupts.
# That is not a problem to work around here: the question this benchmark exists to answer
# is where structure begins AFTER the signal peptide, so only the N-terminal window is
# needed. Submitting a window keeps every input legal by construction and makes the run
# cheap. Widen it deliberately if the question ever changes.
NSP3_WINDOW = 400

app = modal.App("surfaceome-disorder")
volume = modal.Volume.from_name("disorder-runs", create_if_missing=True)
nsp3_model = modal.Volume.from_name("netsurfp3-model", create_if_missing=True)
OUT = "/runs"
SHARD_SIZE = 2_000
NSP3_SHARD_SIZE = 1_000  # nsp3 config caps a run at 5,000 sequences / 10M residues
AFD_SHARD_SIZE = 200

# AlphaFold DB is on v6; the v4 file URLs 404. Anything constructing these by hand and
# pinning a version silently breaks on every release.
AFDB_URL = "https://alphafold.ebi.ac.uk/files/AF-{acc}-F1-model_v6.pdb"


def _fetch_sequences(
    *, cohorts: tuple[str, ...], limit: int | None = None
) -> list[dict]:
    """Proteoforms with their stored sequence, keyed on uniprot_acc_full (the stable ID).

    Same source as the topology and SignalP sweeps, so all three annotate identical input.
    """
    from accessible_surfaceome.cloud.d1_client import D1Client
    from accessible_surfaceome.env import load_env

    load_env()
    ph = ", ".join(["?"] * len(cohorts))
    sql = (
        "SELECT uniprot_acc_full, uniprot_acc, hgnc_id, is_canonical, sequence, protein_length "
        f"FROM topology_public WHERE cohort IN ({ph}) "
        "GROUP BY uniprot_acc_full ORDER BY protein_length ASC"
    )
    if limit:
        sql += f" LIMIT {int(limit)}"
    with D1Client.public() as d1:
        return d1.query(sql, list(cohorts))


STANDARD_AA = frozenset("ACDEFGHIKLMNPQRSTVWY")

# Mirrors accessible_surfaceome.sources.residues, which the Modal images do not install.
# tests/test_residues.py asserts the two have not drifted: a divergence would give two
# predictors in the same benchmark different sequences for the same protein.
# U (selenocysteine) -> C is biophysically sound (Se for S); X (unknown) -> A. These
# predictors reject non-standard letters outright, and dropping those proteins loses the
# human selenoproteome -- GPX3 and GPX6 are signal-peptide positive.
SUBSTITUTIONS = {"U": "C", "O": "K", "B": "N", "Z": "Q", "J": "L", "X": "A"}


def _sanitise(seq: str) -> tuple[str, bool]:
    """Return (standard-alphabet sequence, whether anything was substituted)."""
    if all(c in STANDARD_AA for c in seq):
        return seq, False
    return "".join(
        SUBSTITUTIONS.get(c, "A") if c not in STANDARD_AA else c for c in seq
    ), True


def _shard(records: list[dict], size: int) -> list[list[dict]]:
    return [records[i : i + size] for i in range(0, len(records), size)]


def _payloads(records: list[dict], run_id: str, size: int, prefix: str) -> list[dict]:
    return [
        {"records": s, "run_id": run_id, "shard_id": f"{prefix}{i:04d}"}
        for i, s in enumerate(_shard(records, size))
    ]


@app.function(
    image=metapredict_image,
    cpu=4.0,
    memory=8192,
    timeout=2 * 60 * 60,
    retries=modal.Retries(max_retries=2),
    volumes={OUT: volume},
    max_containers=15,
)
def metapredict_shard(payload: dict) -> dict:
    """Per-residue disorder for one shard.

    Scores are quantised to one byte (round(score * 255)) and hex-encoded. At full float
    precision the 12.5M residues would be ~100 MB of JSON for a signal whose useful
    resolution is about two decimal places; a byte per residue is 12.5 MB and loses
    nothing that matters. Disorder domains are stored alongside because metapredict's own
    boundary call applies smoothing we would otherwise have to reimplement.
    """
    import metapredict as meta

    records, run_id, shard_id = (
        payload["records"],
        payload["run_id"],
        payload["shard_id"],
    )
    started = time.time()
    out_dir = Path(OUT) / run_id / shard_id
    out_dir.mkdir(parents=True, exist_ok=True)

    rows, failed = [], []
    for r in records:
        seq, substituted = _sanitise(r["sequence"])
        try:
            scores = meta.predict_disorder(seq)
            domains = meta.predict_disorder_domains(seq).disordered_domain_boundaries
        except Exception as exc:  # noqa: BLE001 - one bad sequence must not lose the shard
            failed.append({"acc": r["uniprot_acc_full"], "error": str(exc)[:300]})
            continue
        if len(scores) != r["protein_length"]:
            failed.append({"acc": r["uniprot_acc_full"], "error": "length mismatch"})
            continue
        rows.append(
            {
                "uniprot_acc_full": r["uniprot_acc_full"],
                "protein_length": r["protein_length"],
                "substituted": substituted,
                "scores_hex": bytes(
                    min(255, max(0, round(s * 255))) for s in scores
                ).hex(),
                "disorder_domains": [[int(a), int(b)] for a, b in domains],
            }
        )

    (out_dir / "metapredict.json").write_text(json.dumps(rows))
    (out_dir / "manifest.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "shard": shard_id,
                "predictor": "metapredict",
                "version": getattr(meta, "__version__", "3.0.2"),
                "n": len(rows),
                "failed": failed,
                "seconds": time.time() - started,
            },
            indent=2,
        )
    )
    volume.commit()
    return {
        "shard": shard_id,
        "ok": True,
        "n": len(rows),
        "failed": len(failed),
        "seconds": time.time() - started,
    }


@app.function(
    image=afd_image,
    cpu=2.0,
    timeout=2 * 60 * 60,
    retries=modal.Retries(max_retries=2),
    volumes={OUT: volume},
    max_containers=10,
)
def alphafold_disorder_shard(payload: dict) -> dict:
    """Windowed-RSA and 1-pLDDT disorder from AlphaFoldDB models, for one shard.

    Isoforms ARE attempted. AlphaFoldDB does carry per-isoform models -- measured at 99%
    of the 8,835 isoform proteoforms in this set. An earlier version skipped them on the
    assumption that AFDB is keyed on the base accession only, which is false and silently
    discarded ~8,700 predictions.

    The isoform accession is requested as-is and never falls back to the canonical model:
    a fallback would return a structure for a different sequence under the isoform's name,
    which is the failure the original skip was trying to avoid. A 404 is recorded missing.
    """
    import urllib.request

    from Bio.PDB import PDBParser
    from Bio.PDB.DSSP import DSSP

    records, run_id, shard_id = (
        payload["records"],
        payload["run_id"],
        payload["shard_id"],
    )
    started = time.time()
    out_dir = Path(OUT) / run_id / shard_id
    out_dir.mkdir(parents=True, exist_ok=True)
    parser = PDBParser(QUIET=True)

    rows, missing = [], []
    for r in records:
        acc = r["uniprot_acc_full"]
        pdb = Path("/tmp") / f"{acc}.pdb"
        try:
            urllib.request.urlretrieve(AFDB_URL.format(acc=acc), pdb)
        except Exception:
            missing.append(acc)
            continue
        # Strip DBREF before DSSP sees the file. The PDB DBREF accession field is 8
        # columns wide and modern UniProt accessions are 10 characters
        # (A0A2K5X6C2_MACFA), so they overflow it and shift every later field right.
        # mkdssp then reads an identifier where it expects an integer and exits 1 with
        # "Not a valid integer in PDB record". This is not species-specific even though it
        # looks it: human reviewed accessions are mostly 6 characters and survive, which is
        # why an earlier ortholog run lost 5,422 of 12,634 structures while the human run
        # lost 9. DSSP reads coordinates only and has no use for DBREF.
        pdb.write_text(
            "\n".join(
                ln for ln in pdb.read_text().splitlines() if not ln.startswith("DBREF")
            )
            + "\n"
        )
        try:
            model = next(iter(parser.get_structure(acc, str(pdb))))
            dssp = DSSP(model, str(pdb), dssp="mkdssp")
            plddt, rsa = {}, {}
            for key in dssp.keys():
                idx = key[1][1]
                rsa[idx] = float(dssp[key][3])
            for res in model.get_residues():
                ca = res["CA"] if "CA" in res else None
                if ca is not None:
                    plddt[res.id[1]] = float(ca.get_bfactor())
        except Exception as exc:  # noqa: BLE001
            missing.append(f"{acc}:{str(exc)[:80]}")
            continue
        finally:
            pdb.unlink(missing_ok=True)

        n = max(plddt) if plddt else 0
        # AlphaFold-disorder's RSA score is the mean over a 25-residue window (+/-12),
        # which is the window size its authors optimised on the CAID DisProt set.
        win = 12
        rsa_smoothed = []
        for i in range(1, n + 1):
            vals = [
                rsa[j] for j in range(max(1, i - win), min(n, i + win) + 1) if j in rsa
            ]
            rsa_smoothed.append(sum(vals) / len(vals) if vals else 0.0)
        rows.append(
            {
                "uniprot_acc_full": acc,
                "model_residues": n,
                "protein_length": r["protein_length"],
                "plddt_hex": bytes(
                    min(255, max(0, round(plddt.get(i, 0.0) * 2.55)))
                    for i in range(1, n + 1)
                ).hex(),
                "rsa_window_hex": bytes(
                    min(255, max(0, round(v * 255))) for v in rsa_smoothed
                ).hex(),
            }
        )

    (out_dir / "alphafold_disorder.json").write_text(json.dumps(rows))
    (out_dir / "manifest.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "shard": shard_id,
                "predictor": "alphafold-disorder",
                "afdb_url": AFDB_URL,
                "rsa_window": 25,
                "n": len(rows),
                "missing": missing[:200],
                "n_missing": len(missing),
                "seconds": time.time() - started,
            },
            indent=2,
        )
    )
    volume.commit()
    return {
        "shard": shard_id,
        "ok": True,
        "n": len(rows),
        "missing": len(missing),
        "seconds": time.time() - started,
    }


@app.function(
    image=netsurfp_image,
    gpu="T4",
    timeout=3 * 60 * 60,
    retries=modal.Retries(max_retries=2),
    volumes={OUT: volume, NSP3_MOUNT: nsp3_model},
    max_containers=10,
)
def netsurfp_shard(payload: dict) -> dict:
    """NetSurfP-3.0 over the N-terminal window of one shard.

    Emits per-residue RSA, ASA, Q3/Q8 secondary structure with class probabilities,
    phi/psi and a disorder score. RSA and the secondary-structure onset are the signals
    this benchmark is really after -- disorder is NetSurfP's side task, and "where does
    structure begin" is closer to a secondary-structure question than an IDR one.
    """
    import subprocess
    import tempfile

    records, run_id, shard_id = (
        payload["records"],
        payload["run_id"],
        payload["shard_id"],
    )
    started = time.time()
    out_dir = Path(OUT) / run_id / shard_id
    out_dir.mkdir(parents=True, exist_ok=True)
    ckpt = Path(NSP3_MOUNT) / "nsp3.pth"
    if not ckpt.exists():
        raise RuntimeError(
            "nsp3.pth not on the volume — run scripts/cloud/stage_netsurfp3.sh"
        )

    with tempfile.TemporaryDirectory() as tmp:
        fasta = Path(tmp) / "in.fasta"
        windows = {}
        with fasta.open("w") as fh:
            for r in records:
                seq, _ = _sanitise(r["sequence"][:NSP3_WINDOW])
                windows[r["uniprot_acc_full"]] = len(seq)
                fh.write(f">{r['uniprot_acc_full']}\n{seq}\n")
        out = Path(tmp) / "out"
        out.mkdir()
        proc = subprocess.run(
            [
                # the 3.8 venv, not the container python -- nsp3 needs torch 1.8
                NSP3_PYTHON,
                "/opt/nsp3/nsp3.py",
                "-i",
                str(fasta),
                "-o",
                str(out),
                "-m",
                str(ckpt),
                "-w",
                shard_id,
                "-gpu",
                "True",
            ],
            capture_output=True,
            text=True,
            check=False,
            cwd="/opt/nsp3",
        )
        if proc.returncode != 0:
            return {
                "shard": shard_id,
                "ok": False,
                "n": len(records),
                "error": proc.stderr[-2000:],
                "seconds": time.time() - started,
            }
        for produced in (out / shard_id).rglob("*"):
            if produced.is_file() and produced.suffix in (".csv", ".json"):
                (out_dir / produced.name).write_bytes(produced.read_bytes())

    (out_dir / "manifest.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "shard": shard_id,
                "predictor": "netsurfp-3.0",
                "window": NSP3_WINDOW,
                "n": len(records),
                "submitted_lengths": windows,
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
        "seconds": time.time() - started,
    }


@app.local_entrypoint()
def netsurfp_canary(
    n: int = 40, cohorts: str = "human_canonical,human_isoforms"
) -> None:
    """NetSurfP-3.0 only, on a sample. Writes nothing to D1."""
    ct = tuple(c.strip() for c in cohorts.split(","))
    everything = _fetch_sequences(cohorts=ct)
    step = max(1, len(everything) // n)
    sample = everything[::step][:n]
    run_id = f"nsp3_canary_{int(time.time())}"
    print(
        f"{len(everything):,} proteoforms; canary on {len(sample)} "
        f"(N-terminal {NSP3_WINDOW} aa), run_id={run_id}"
    )
    started = time.time()
    res = list(netsurfp_shard.map(_payloads(sample, run_id, NSP3_SHARD_SIZE, "n")))
    _report(res, "netsurfp-3.0", time.time() - started)
    ok = [r for r in res if r.get("ok")]
    for f in (r for r in res if not r.get("ok")):
        print(f"  FAILED {f['shard']}:\n{f.get('error', '')}")
    if ok:
        per = sum(r["seconds"] for r in ok) / max(1, sum(r["n"] for r in ok))
        print(
            f"\nprojection: {per * len(everything) / 3600:.2f} GPU-hours "
            f"for {len(everything):,} proteoforms "
            f"(~${per * len(everything) * 0.000164:,.2f} at the T4 rate)"
        )


def _report(results: list[dict], label: str, wall: float) -> None:
    ok = [r for r in results if r.get("ok")]
    done = sum(r["n"] for r in ok)
    secs = sum(r.get("seconds", 0) for r in ok)
    extra = sum(r.get("missing", 0) + r.get("failed", 0) for r in ok)
    print(
        f"  {label:<22} {len(ok)}/{len(results)} shards   {done:,} proteins   "
        f"{secs / 3600:.2f} core-hours   skipped {extra:,}"
    )


@app.local_entrypoint()
def canary(n: int = 50, cohorts: str = "human_canonical,human_isoforms") -> None:
    """Small sample of both predictors. Writes nothing to D1."""
    ct = tuple(c.strip() for c in cohorts.split(","))
    everything = _fetch_sequences(cohorts=ct)
    step = max(1, len(everything) // n)
    sample = everything[::step][:n]
    run_id = f"canary_{int(time.time())}"
    print(
        f"{len(everything):,} proteoforms; canary on {len(sample)}, run_id={run_id}\n"
    )

    started = time.time()
    m = list(metapredict_shard.map(_payloads(sample, run_id, SHARD_SIZE, "m")))
    _report(m, "metapredict", time.time() - started)
    started = time.time()
    a = list(
        alphafold_disorder_shard.map(_payloads(sample, run_id, AFD_SHARD_SIZE, "a"))
    )
    _report(a, "alphafold-disorder", time.time() - started)

    mdone = sum(r["n"] for r in m if r.get("ok")) or 1
    msec = sum(r.get("seconds", 0) for r in m if r.get("ok"))
    asec = sum(r.get("seconds", 0) for r in a if r.get("ok"))
    adone = sum(r["n"] for r in a if r.get("ok")) or 1
    print(f"\nprojection to {len(everything):,} proteoforms:")
    print(
        f"  metapredict        {msec / mdone * len(everything) / 3600:6.2f} core-hours"
    )
    canon = len(everything)
    print(
        f"  alphafold-disorder {asec / adone * canon / 3600:6.2f} core-hours "
        f"over {canon:,} canonical accessions (AFDB has no isoform models)"
    )


@app.local_entrypoint()
def metapredict_sweep(
    run_id: str, cohorts: str = "human_canonical,human_isoforms"
) -> None:
    """metapredict only. Cheap enough to re-run on its own when the input rule changes."""
    ct = tuple(c.strip() for c in cohorts.split(","))
    records = _fetch_sequences(cohorts=ct)
    print(f"{len(records):,} proteoforms, run_id={run_id}")
    started = time.time()
    res = list(metapredict_shard.map(_payloads(records, run_id, SHARD_SIZE, "m")))
    _report(res, "metapredict", time.time() - started)
    print(f"\npull with: modal volume get disorder-runs {run_id}")


@app.local_entrypoint()
def netsurfp_sweep(
    run_id: str, cohorts: str = "human_canonical,human_isoforms"
) -> None:
    """NetSurfP-3.0 over every proteoform's N-terminal window. Volume only."""
    ct = tuple(c.strip() for c in cohorts.split(","))
    records = _fetch_sequences(cohorts=ct)
    print(f"{len(records):,} proteoforms, N-terminal {NSP3_WINDOW} aa, run_id={run_id}")
    started = time.time()
    res = list(netsurfp_shard.map(_payloads(records, run_id, NSP3_SHARD_SIZE, "n")))
    _report(res, "netsurfp-3.0", time.time() - started)
    for f in (r for r in res if not r.get("ok")):
        print(f"  FAILED {f['shard']}:\n{f.get('error', '')}")
    print(f"\npull with: modal volume get disorder-runs {run_id}")
    print("nothing was written to D1 — publish as a separate, reviewed step")


@app.local_entrypoint()
def full_sweep(run_id: str, cohorts: str = "human_canonical,human_isoforms") -> None:
    """Both predictors over every proteoform. Volume only; D1 is a separate step."""
    ct = tuple(c.strip() for c in cohorts.split(","))
    records = _fetch_sequences(cohorts=ct)
    print(f"{len(records):,} proteoforms, run_id={run_id}\n")

    started = time.time()
    m = list(metapredict_shard.map(_payloads(records, run_id, SHARD_SIZE, "m")))
    _report(m, "metapredict", time.time() - started)

    started = time.time()
    a = list(
        alphafold_disorder_shard.map(_payloads(records, run_id, AFD_SHARD_SIZE, "a"))
    )
    _report(a, "alphafold-disorder", time.time() - started)

    print(f"\npull with: modal volume get disorder-runs {run_id}")
    print("nothing was written to D1 — publish as a separate, reviewed step")
