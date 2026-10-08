"""SignalP 6.0 output -> ``signalp_public`` row values.

A run writes several files; two carry information the others do not:

* ``prediction_results.txt`` — the call, both class probabilities, and the cleavage site
  with its own probability.
* ``region_output.gff3`` — the n / h / c decomposition of the signal peptide. The h-region
  is the hydrophobic core an N-terminal tag must not disrupt, and it cannot be re-derived
  from the cleavage site, so it is parsed rather than discarded.

``output.gff3`` and ``output.json`` are redundant with these. ``processed_entries.fasta``
holds SP-trimmed sequences, which are derivable from the cleavage site.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CS_RE = re.compile(r"CS pos: (\d+)-(\d+)\. Pr: ([\d.]+)")
REGIONS = ("n-region", "h-region", "c-region")


class SignalP6Error(ValueError):
    """Raised when a SignalP record cannot be projected onto the schema."""


@dataclass(frozen=True)
class Call:
    """One proteoform's SignalP 6 result."""

    accession: str
    prediction: str  # 'SP' | 'OTHER'
    sp_probability: float
    other_probability: float
    cleavage_site: int | None
    cleavage_probability: float | None
    regions: dict[str, tuple[int, int]]

    def columns(self) -> dict[str, Any]:
        r = self.regions
        return {
            "prediction": self.prediction,
            "sp_probability": self.sp_probability,
            "other_probability": self.other_probability,
            "cleavage_site": self.cleavage_site,
            "cleavage_probability": self.cleavage_probability,
            "n_region_start": r.get("n-region", (None, None))[0],
            "n_region_end": r.get("n-region", (None, None))[1],
            "h_region_start": r.get("h-region", (None, None))[0],
            "h_region_end": r.get("h-region", (None, None))[1],
            "c_region_start": r.get("c-region", (None, None))[0],
            "c_region_end": r.get("c-region", (None, None))[1],
        }


def _parse_results(path: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for line in path.read_text().splitlines():
        if line.startswith("#") or not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 4:
            raise SignalP6Error(f"{path}: malformed line {line!r}")
        acc, call, other, sp = parts[0], parts[1], float(parts[2]), float(parts[3])
        cs = cs_pr = None
        if len(parts) > 4 and parts[4].strip():
            m = CS_RE.search(parts[4])
            if not m:
                raise SignalP6Error(f"{acc}: unparsable cleavage field {parts[4]!r}")
            # "CS pos: 24-25" means cleavage between 24 and 25, so 24 is the last residue
            # of the signal peptide. Store that, matching topology_public's
            # signal_peptide_length convention rather than SignalP's display.
            cs, cs_pr = int(m.group(1)), float(m.group(3))
            if int(m.group(2)) != cs + 1:
                raise SignalP6Error(f"{acc}: non-adjacent cleavage bounds {parts[4]!r}")
        if call == "SP" and cs is None:
            raise SignalP6Error(f"{acc}: called SP with no cleavage site")
        if call != "SP" and cs is not None:
            raise SignalP6Error(f"{acc}: called {call} but carries a cleavage site")
        out[acc] = {
            "prediction": call,
            "other": other,
            "sp": sp,
            "cs": cs,
            "cs_pr": cs_pr,
        }
    return out


def _parse_regions(path: Path) -> dict[str, dict[str, tuple[int, int]]]:
    out: dict[str, dict[str, tuple[int, int]]] = {}
    if not path.exists():
        return out
    for line in path.read_text().splitlines():
        if line.startswith("#") or not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 5 or parts[2] not in REGIONS:
            continue
        out.setdefault(parts[0], {})[parts[2]] = (int(parts[3]), int(parts[4]))
    return out


def parse_shard(shard_dir: Path) -> list[Call]:
    """Read one shard directory into Call objects."""
    results = _parse_results(shard_dir / "prediction_results.txt")
    regions = _parse_regions(shard_dir / "region_output.gff3")
    calls = []
    for acc, r in results.items():
        reg = regions.get(acc, {})
        if r["prediction"] == "SP" and set(reg) != set(REGIONS):
            raise SignalP6Error(
                f"{acc}: SP call missing region decomposition {sorted(reg)}"
            )
        if r["prediction"] == "SP" and reg["c-region"][1] != r["cs"]:
            raise SignalP6Error(
                f"{acc}: c-region ends at {reg['c-region'][1]} but cleavage site is {r['cs']}"
            )
        calls.append(
            Call(
                accession=acc,
                prediction=r["prediction"],
                sp_probability=r["sp"],
                other_probability=r["other"],
                cleavage_site=r["cs"],
                cleavage_probability=r["cs_pr"],
                regions=reg,
            )
        )
    return calls


def parse_run(run_dir: Path) -> dict[str, Call]:
    """Read every shard under a run directory, refusing any accession seen twice."""
    calls: dict[str, Call] = {}
    shards = sorted(p.parent for p in Path(run_dir).rglob("prediction_results.txt"))
    if not shards:
        raise SignalP6Error(f"no prediction_results.txt under {run_dir}")
    for shard in shards:
        for c in parse_shard(shard):
            if c.accession in calls:
                raise SignalP6Error(f"{c.accession} predicted twice — shards overlap")
            calls[c.accession] = c
    return calls
