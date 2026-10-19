"""Shared engine for the tag-site disulfide-clearance calibration.

Measures the distance from a tag-site junction residue to the nearest *bonded*
cysteine in four conventions that are **not** interchangeable — they differ by
1-4 Å, so a floor fitted on one does not transfer to a gate that applies
another:

``ca_ca``
    CA of the junction residue to CA of the cysteine. This is what
    ``features.py`` measures, and what its 10 Å floor is calibrated on.
``ca_sg``
    CA of the junction residue to SG of the cysteine.
``heavy_sg``
    nearest non-hydrogen atom of the junction residue to the cysteine's SG.
``heavy``
    nearest non-hydrogen atom of the junction residue to the nearest
    non-hydrogen atom of the cysteine ("heavy-heavy").

Every convention is minimised over **all** bonded cysteines, never over the
nearest by sequence: MS4A1 Y161 was cleared at 11.9 Å to C167 when C183, the
other partner of the same bond, is nearer on all four. Per-cysteine distances
are reported alongside the minimum, because a "nearest" that wins by 0.2 Å
oversells itself.

"Bonded" is read off the **model**, as every Cys pair whose SG-SG separation is
under :data:`SG_SG_BOND_MAX_A`, never from UniProt ``DISULFID``. ACKR3's
C34-C287 is 2.03 Å in ``AF-P25106-F1-model_v6`` and is unannotated, so a
calibration keyed on annotations would silently drop exactly the sites most
likely to sit near a bond.
"""

from __future__ import annotations

import json
import logging
import os
import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
import numpy as np
from Bio.PDB import PDBParser

logger = logging.getLogger(__name__)

# A modelled disulfide sits at ~2.05 Å SG-SG. 2.5 Å is comfortably above the
# bonded population and far below the next-nearest unbonded Cys pair, so the
# classification is not sensitive to the exact cut (see the margin audit in
# calibrate_disulfide_clearance.py, which reports the gap either side).
SG_SG_BOND_MAX_A = 2.5

# Order matters only for presentation; the names are the contract. ``heavy`` is
# heavy-heavy (nearest heavy atom to any heavy atom), ``heavy_sg`` is nearest
# heavy atom to the sulfur specifically.
CONVENTIONS = ("ca_ca", "ca_sg", "heavy_sg", "heavy")
CONVENTION_LABEL = {
    "ca_ca": "CA-CA",
    "ca_sg": "CA-SG",
    "heavy_sg": "heavy-SG",
    "heavy": "heavy-heavy",
}

UNIPROT_REST = "https://rest.uniprot.org/uniprotkb"
AFDB_API = "https://alphafold.ebi.ac.uk/api/prediction"

_UA = {"User-Agent": "accessible-surfaceome/tag-site-calibration (becca@deliverome.org)"}

# Per-host courtesy interval. AFDB 429s a tight loop over ~130 models and then
# keeps 429ing for a cooldown window, so the interval is deliberately generous
# and the backoff is long enough to ride the cooldown out rather than fail the
# run. A polite identifiable User-Agent is only half of being a good citizen.
# AFDB's file server sits behind a rate limiter that answers 429 with no
# Retry-After and then keeps answering 429 for a cooldown window, including for
# files already served, so its interval is deliberately slow. UniProt's REST API
# is generous and does not need the same handicap.
_AFDB_INTERVAL_S = float(os.environ.get("DISULFIDE_CAL_AFDB_INTERVAL_S", "8.0"))
_DEFAULT_INTERVAL_S = float(os.environ.get("DISULFIDE_CAL_MIN_INTERVAL_S", "0.34"))
_MAX_ATTEMPTS = 12
_BACKOFF_CAP_S = 300.0


def _host_interval(host: str | None) -> float:
    return _AFDB_INTERVAL_S if host and "alphafold" in host else _DEFAULT_INTERVAL_S
_last_request_at: dict[str, float] = {}


def _throttled_get(url: str, *, params: dict | None = None, timeout: float) -> httpx.Response:
    """GET with a per-host courtesy interval and backoff on 429 / 5xx."""
    host = httpx.URL(url).host
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        wait = _host_interval(host) - (
            time.monotonic() - _last_request_at.get(host, 0.0)
        )
        if wait > 0:
            time.sleep(wait)
        _last_request_at[host] = time.monotonic()
        resp = httpx.get(
            url, params=params, headers=_UA, timeout=timeout, follow_redirects=True
        )
        if resp.status_code == 429 or resp.status_code >= 500:
            if attempt == _MAX_ATTEMPTS:
                resp.raise_for_status()
            retry_after = resp.headers.get("Retry-After")
            try:
                backoff = float(retry_after) if retry_after else 0.0
            except ValueError:
                backoff = 0.0
            backoff = max(backoff, min(2.0**attempt, _BACKOFF_CAP_S)) + random.uniform(0, 2.0)
            logger.warning(
                "%s on %s (attempt %d/%d) — sleeping %.1fs",
                resp.status_code, url, attempt, _MAX_ATTEMPTS, backoff,
            )
            time.sleep(backoff)
            continue
        return resp
    raise RuntimeError("unreachable")


@dataclass
class ModelResidue:
    """One modelled residue's heavy atoms, keyed by PDB atom name."""

    resname: str
    atoms: dict[str, np.ndarray]

    @property
    def heavy(self) -> np.ndarray:
        """``(n_atoms, 3)`` array of every heavy-atom coordinate."""
        return np.asarray(list(self.atoms.values()), dtype=float)

    def atom(self, name: str) -> np.ndarray | None:
        return self.atoms.get(name)


@dataclass
class ModelDisulfide:
    """One Cys pair found bonded in the model."""

    res_i: int
    res_j: int
    sg_sg_a: float
    uniprot_annotated: bool

    def label(self) -> str:
        return f"C{self.res_i}-C{self.res_j}"


@dataclass
class ProteinStructure:
    """An AlphaFold model whose numbering has been verified residue-exact."""

    uniprot_acc: str
    model_pdb_url: str
    model_sequence: str
    uniprot_sequence: str
    residues: dict[int, ModelResidue]
    disulfides: list[ModelDisulfide] = field(default_factory=list)
    annotated_disulfides: set[tuple[int, int]] = field(default_factory=set)
    unbonded_min_sg_sg_a: float | None = None

    @property
    def bonded_cys(self) -> set[int]:
        out: set[int] = set()
        for d in self.disulfides:
            out.add(d.res_i)
            out.add(d.res_j)
        return out


def _cache_get_json(url: str, path: Path, *, params: dict | None = None) -> dict | list:
    if path.exists():
        return json.loads(path.read_text())
    resp = _throttled_get(url, params=params, timeout=60.0)
    resp.raise_for_status()
    payload = resp.json()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))
    return payload


def _cache_get_text(url: str, path: Path) -> str:
    if path.exists():
        return path.read_text()
    resp = _throttled_get(url, timeout=120.0)
    resp.raise_for_status()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(resp.text)
    return resp.text


def fetch_uniprot_entry(acc: str, cache_dir: Path) -> dict:
    """Return the UniProt JSON entry for ``acc`` (cached)."""
    payload = _cache_get_json(
        f"{UNIPROT_REST}/{acc}.json", cache_dir / f"uniprot_{acc}.json"
    )
    assert isinstance(payload, dict)
    return payload


def uniprot_sequence(entry: dict) -> str:
    return str(entry.get("sequence", {}).get("value", ""))


def uniprot_disulfides(entry: dict) -> set[tuple[int, int]]:
    """Annotated ``DISULFID`` cross-links as sorted (i, j) residue pairs.

    Interchain bonds (no distinct end position, or a description naming a
    partner chain) are skipped — they are not an intrachain hazard pair.
    """
    out: set[tuple[int, int]] = set()
    for feat in entry.get("features", []) or []:
        if feat.get("type") != "Disulfide bond":
            continue
        loc = feat.get("location", {}) or {}
        start = (loc.get("start", {}) or {}).get("value")
        end = (loc.get("end", {}) or {}).get("value")
        if not isinstance(start, int) or not isinstance(end, int):
            continue
        if start == end:
            continue
        out.add((min(start, end), max(start, end)))
    return out


def uniprot_signal_peptide_end(entry: dict) -> int | None:
    """Last residue of the signal peptide, for a ``mature``-framed position."""
    for feat in entry.get("features", []) or []:
        if feat.get("type") != "Signal":
            continue
        end = ((feat.get("location", {}) or {}).get("end", {}) or {}).get("value")
        if isinstance(end, int):
            return end
    return None


def afdb_metadata(acc: str, cache_dir: Path) -> dict | None:
    """AFDB prediction metadata for ``acc``; ``None`` when AFDB has no model."""
    path = cache_dir / f"afdb_{acc}.json"
    try:
        payload = _cache_get_json(f"{AFDB_API}/{acc}", path)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            return None
        raise
    if isinstance(payload, list):
        return payload[0] if payload else None
    return payload if isinstance(payload, dict) else None


def _parse_model(path: Path) -> dict[int, ModelResidue]:
    """Residue number -> :class:`ModelResidue` for the first chain."""
    structure = PDBParser(QUIET=True).get_structure("m", str(path))
    model = next(iter(structure))
    chain = next(iter(model))
    out: dict[int, ModelResidue] = {}
    for residue in chain:
        het, seqid, _icode = residue.get_id()
        if het.strip():
            continue
        atoms: dict[str, np.ndarray] = {}
        for atom in residue:
            # ``element`` is authoritative. AlphaFold PDBs carry no hydrogens,
            # but a deposited or re-folded model may, and a hydrogen would make
            # every nearest-heavy-atom distance too short.
            if (atom.element or "").strip().upper() == "H":
                continue
            atoms[atom.get_id()] = np.asarray(atom.get_coord(), dtype=float)
        if atoms:
            out[int(seqid)] = ModelResidue(resname=residue.get_resname(), atoms=atoms)
    return out


def load_structure(
    acc: str,
    *,
    cache_dir: Path,
    model_pdb_url: str | None = None,
) -> ProteinStructure | None:
    """Load the AFDB model for ``acc`` with its model disulfides resolved.

    ``model_pdb_url`` is taken from the record / AFDB metadata, never
    constructed; when omitted it is read from AFDB's prediction metadata.
    Returns ``None`` when AFDB has no model for the accession.
    """
    meta = afdb_metadata(acc, cache_dir)
    if meta is None:
        return None
    url = model_pdb_url or meta.get("pdbUrl")
    if not isinstance(url, str) or not url:
        return None
    pdb_path = cache_dir / f"{acc}__{Path(url).name}"
    _cache_get_text(url, pdb_path)
    residues = _parse_model(pdb_path)

    seq_from_model = str(meta.get("uniprotSequence") or "")
    entry = fetch_uniprot_entry(acc, cache_dir)
    annotated = uniprot_disulfides(entry)

    struct = ProteinStructure(
        uniprot_acc=acc,
        model_pdb_url=url,
        model_sequence=seq_from_model,
        uniprot_sequence=uniprot_sequence(entry),
        residues=residues,
        annotated_disulfides=annotated,
    )
    _resolve_disulfides(struct)
    return struct


def _resolve_disulfides(struct: ProteinStructure) -> None:
    """Fill ``disulfides`` from SG-SG geometry, and the nearest unbonded gap."""
    sgs: list[tuple[int, np.ndarray]] = []
    for num, res in struct.residues.items():
        if res.resname != "CYS":
            continue
        sg = res.atom("SG")
        if sg is not None:
            sgs.append((num, sg))
    sgs.sort()
    unbonded: list[float] = []
    for a in range(len(sgs)):
        for b in range(a + 1, len(sgs)):
            i, ci = sgs[a]
            j, cj = sgs[b]
            d = float(np.linalg.norm(ci - cj))
            if d < SG_SG_BOND_MAX_A:
                pair = (min(i, j), max(i, j))
                struct.disulfides.append(
                    ModelDisulfide(
                        res_i=pair[0],
                        res_j=pair[1],
                        sg_sg_a=d,
                        uniprot_annotated=pair in struct.annotated_disulfides,
                    )
                )
            else:
                unbonded.append(d)
    struct.unbonded_min_sg_sg_a = min(unbonded) if unbonded else None


def measure_site(
    struct: ProteinStructure, junction_residue: int
) -> tuple[dict[str, Any], list[dict[str, Any]]] | None:
    """Distances from ``junction_residue`` to every bonded cysteine.

    Returns ``(per_site_minima, per_cysteine_rows)``. Each convention is
    minimised **independently**, because the nearest cysteine under one
    convention is not always the nearest under another — which is the whole
    reason the conventions cannot be swapped at a boundary. The partner
    cysteine is reported per convention, and ``*_runner_up_gap_a`` records how
    much the winning cysteine actually won by, so a near-tie is visible
    instead of hidden behind the word "nearest".
    """
    junction = struct.residues.get(junction_residue)
    if junction is None:
        return None
    bonded = sorted(struct.bonded_cys)
    if not bonded:
        return None

    j_heavy = junction.heavy
    j_ca = junction.atom("CA")

    bond_of: dict[int, ModelDisulfide] = {}
    for d in struct.disulfides:
        bond_of.setdefault(d.res_i, d)
        bond_of.setdefault(d.res_j, d)

    rows: list[dict[str, Any]] = []
    for cys in bonded:
        res = struct.residues.get(cys)
        if res is None:
            continue
        c_heavy = res.heavy
        c_ca = res.atom("CA")
        c_sg = res.atom("SG")
        bond = bond_of.get(cys)
        row: dict[str, Any] = {
            "cys": cys,
            "bond": bond.label() if bond else None,
            "bond_sg_sg_a": round(bond.sg_sg_a, 2) if bond else None,
            "bond_annotated": bool(bond.uniprot_annotated) if bond else None,
            "sequence_separation": abs(cys - junction_residue),
        }
        row["ca_ca_a"] = (
            round(float(np.linalg.norm(j_ca - c_ca)), 2)
            if j_ca is not None and c_ca is not None
            else None
        )
        row["ca_sg_a"] = (
            round(float(np.linalg.norm(j_ca - c_sg)), 2)
            if j_ca is not None and c_sg is not None
            else None
        )
        row["heavy_sg_a"] = (
            round(float(np.min(np.linalg.norm(j_heavy - c_sg, axis=-1))), 2)
            if len(j_heavy) and c_sg is not None
            else None
        )
        row["heavy_a"] = (
            round(
                float(
                    np.min(
                        np.linalg.norm(
                            j_heavy[:, None, :] - c_heavy[None, :, :], axis=-1
                        )
                    )
                ),
                2,
            )
            if len(j_heavy) and len(c_heavy)
            else None
        )
        rows.append(row)

    if not rows:
        return None
    out: dict[str, Any] = {}
    for conv in CONVENTIONS:
        key = f"{conv}_a"
        ranked = sorted(
            (r for r in rows if r.get(key) is not None), key=lambda r: r[key]
        )
        if not ranked:
            continue
        best = ranked[0]
        out[key] = best[key]
        out[f"{conv}_cys"] = best["cys"]
        out[f"{conv}_bond"] = best["bond"]
        out[f"{conv}_bond_annotated"] = best["bond_annotated"]
        out[f"{conv}_runner_up_gap_a"] = (
            round(float(ranked[1][key]) - float(best[key]), 2)
            if len(ranked) > 1
            else None
        )
    out["n_bonded_cys"] = len(rows)
    return out, rows
