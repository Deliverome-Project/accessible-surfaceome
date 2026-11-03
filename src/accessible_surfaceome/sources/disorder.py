"""Disorder / solvent-accessibility sweep output -> ``disorder_public`` row values.

Three predictors, one row shape. See ``cloudflare/migrations/disorder_public.sql`` for why
they share a table where SignalP got its own.

Scores are stored as one byte per residue, hex-encoded: ``bytes.fromhex(s)[i] / 255`` for
the 0-1 scores, ``/ 2.55`` for pLDDT. Position ``i`` is residue ``i + 1``.
"""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

PREDICTORS = ("metapredict", "netsurfp-3.0", "alphafold-disorder")


class DisorderError(ValueError):
    """Raised when a sweep record cannot be projected onto the schema."""


def _quantise(values, scale: float = 255.0) -> str:
    return bytes(min(255, max(0, round(v * scale))) for v in values).hex()


@dataclass
class Row:
    accession: str
    predictor: str
    window_residues: int
    disorder_hex: str | None = None
    rsa_hex: str | None = None
    plddt_hex: str | None = None
    ss3: str | None = None
    disorder_domains: list[list[int]] | None = field(default=None)
    substituted: bool = False

    def columns(self) -> dict[str, Any]:
        return {
            "predictor": self.predictor,
            "window_residues": self.window_residues,
            "disorder_hex": self.disorder_hex,
            "rsa_hex": self.rsa_hex,
            "plddt_hex": self.plddt_hex,
            "ss3": self.ss3,
            "disorder_domains": (
                json.dumps(self.disorder_domains)
                if self.disorder_domains is not None
                else None
            ),
            "sequence_substituted": int(self.substituted),
        }


def _check(row: Row) -> Row:
    """Every stored string must be exactly window_residues long.

    A length mismatch means the scores and the sequence have drifted apart, and every
    per-residue lookup downstream would be off by an unknown offset -- silently.
    """
    for name, val, per in (
        ("disorder_hex", row.disorder_hex, 2),
        ("rsa_hex", row.rsa_hex, 2),
        ("plddt_hex", row.plddt_hex, 2),
        ("ss3", row.ss3, 1),
    ):
        if val is not None and len(val) != row.window_residues * per:
            raise DisorderError(
                f"{row.accession} [{row.predictor}]: {name} covers "
                f"{len(val) // per} residues, window_residues says {row.window_residues}"
            )
    return row


def parse_metapredict(run_dir: Path) -> dict[str, Row]:
    out: dict[str, Row] = {}
    for f in sorted(Path(run_dir).rglob("metapredict.json")):
        for r in json.loads(f.read_text()):
            acc = r["uniprot_acc_full"]
            if acc in out:
                raise DisorderError(f"{acc} appears in two metapredict shards")
            out[acc] = _check(
                Row(
                    accession=acc,
                    predictor="metapredict",
                    window_residues=r["protein_length"],
                    disorder_hex=r["scores_hex"],
                    disorder_domains=r.get("disorder_domains"),
                    substituted=bool(r.get("substituted")),
                )
            )
    return out


def parse_alphafold(run_dir: Path) -> dict[str, Row]:
    out: dict[str, Row] = {}
    for f in sorted(Path(run_dir).rglob("alphafold_disorder.json")):
        for r in json.loads(f.read_text()):
            acc = r["uniprot_acc_full"]
            if acc in out:
                raise DisorderError(f"{acc} appears in two alphafold shards")
            # The model can be shorter than the UniProt sequence; window_residues records
            # what was actually scored rather than what we asked for.
            out[acc] = _check(
                Row(
                    accession=acc,
                    predictor="alphafold-disorder",
                    window_residues=r["model_residues"],
                    plddt_hex=r["plddt_hex"],
                    rsa_hex=r["rsa_window_hex"],
                )
            )
    return out


def parse_netsurfp(run_dir: Path) -> dict[str, Row]:
    """One CSV per protein, per-residue rows: id, seq, n, rsa, asa, q3, ..., disorder.

    nsp3 writes both per-protein files (``0000_ACC.csv``) and an aggregated
    ``<shard>.csv`` holding every protein again. Globbing ``*.csv`` therefore sees each
    protein twice; only the per-protein files are read.
    """
    out: dict[str, Row] = {}
    per_protein = re.compile(r"^\d{4}_")
    for f in sorted(Path(run_dir).rglob("*.csv")):
        if not per_protein.match(f.name):
            continue
        rsa, dis, ss3, acc = [], [], [], None
        with f.open() as fh:
            for row in csv.DictReader(fh, skipinitialspace=True):
                acc = (row["id"] or "").lstrip(">") or acc
                rsa.append(float(row["rsa"]))
                dis.append(float(row["disorder"]))
                ss3.append((row["q3"] or "C").strip()[:1] or "C")
        if not acc or not rsa:
            continue
        if acc in out:
            raise DisorderError(f"{acc} appears in two netsurfp shards")
        out[acc] = _check(
            Row(
                accession=acc,
                predictor="netsurfp-3.0",
                window_residues=len(rsa),
                rsa_hex=_quantise(rsa),
                disorder_hex=_quantise(dis),
                ss3="".join(ss3),
            )
        )
    return out


PARSERS = {
    "metapredict": parse_metapredict,
    "alphafold-disorder": parse_alphafold,
    "netsurfp-3.0": parse_netsurfp,
}
