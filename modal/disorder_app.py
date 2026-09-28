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

app = modal.App("surfaceome-disorder")
volume = modal.Volume.from_name("disorder-runs", create_if_missing=True)
OUT = "/runs"
SHARD_SIZE = 2_000
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
        seq = r["sequence"]
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

    Only canonical accessions are attempted: AlphaFoldDB is keyed on the base accession and
    has no per-isoform models, so asking for O95800-2 returns the canonical structure under
    a name that implies otherwise. Isoforms are skipped rather than silently mislabelled.
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
        if "-" in acc:
            continue
        pdb = Path("/tmp") / f"{acc}.pdb"
        try:
            urllib.request.urlretrieve(AFDB_URL.format(acc=acc), pdb)
        except Exception:
            missing.append(acc)
            continue
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
    canon = sum(1 for r in everything if "-" not in r["uniprot_acc_full"])
    print(
        f"  alphafold-disorder {asec / adone * canon / 3600:6.2f} core-hours "
        f"over {canon:,} canonical accessions (AFDB has no isoform models)"
    )


@app.local_entrypoint()
def full_sweep(run_id: str, cohorts: str = "human_canonical,human_isoforms") -> None:
    """Both predictors over every proteoform. Volume only; D1 is a separate step."""
    ct = tuple(c.strip() for c in cohorts.split(","))
    records = _fetch_sequences(cohorts=ct)
    print(f"{len(records):,} proteoforms, run_id={run_id}\n")

    started = time.time()
    m = list(metapredict_shard.map(_payloads(records, run_id, SHARD_SIZE, "m")))
    _report(m, "metapredict", time.time() - started)

    canon = [r for r in records if "-" not in r["uniprot_acc_full"]]
    started = time.time()
    a = list(
        alphafold_disorder_shard.map(_payloads(canon, run_id, AFD_SHARD_SIZE, "a"))
    )
    _report(a, "alphafold-disorder", time.time() - started)

    print(f"\npull with: modal volume get disorder-runs {run_id}")
    print("nothing was written to D1 — publish as a separate, reviewed step")
