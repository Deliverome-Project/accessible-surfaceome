"""UniProt-feature veto for the deterministic tag-site gates.

Fetches the reviewed UniProt entry (reusing the repo's rate-limited
``CachedHTTP``), extracts hazard residues (disulfides, glycosylation,
binding/active/processing sites), and computes each residue's 3D distance to the
nearest hazard atom on the AlphaFold model — the ``feature_dist`` signal the
gates use for their spatial clearance veto.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# UniProt feature types whose residues a tag insertion must stay clear of.
HAZARD_FEATURE_TYPES = {
    "Disulfide bond",
    "Glycosylation",
    "Binding site",
    "Active site",
    "Site",
    "Modified residue",
    "Cross-link",
    "Lipidation",
}


def hazard_residues(features: list[dict[str, Any]]) -> set[int]:
    """Residue positions (1-indexed) covered by hazard features. A disulfide's
    two partners are its ``start`` and ``end`` endpoints; spans (binding sites)
    contribute every residue start..end. Non-hazard types are ignored."""
    out: set[int] = set()
    for feat in features:
        if feat.get("type") not in HAZARD_FEATURE_TYPES:
            continue
        loc = feat.get("location", {})
        start = (loc.get("start") or {}).get("value")
        end = (loc.get("end") or {}).get("value")
        if start is None and end is None:
            continue
        if feat.get("type") == "Disulfide bond":
            # start & end are the two bonded cysteines, not a contiguous span.
            for v in (start, end):
                if isinstance(v, int):
                    out.add(v)
            continue
        s = start if isinstance(start, int) else end
        e = end if isinstance(end, int) else start
        if isinstance(s, int) and isinstance(e, int):
            out.update(range(min(s, e), max(s, e) + 1))
    return out


#: Upper bound on an S-S bond's SG-SG distance. A formed disulfide is ~2.05 A;
#: 2.5 A admits modelling slack without admitting two merely nearby cysteines.
SG_BOND_MAX_A = 2.5


@dataclass(frozen=True)
class Bond:
    """One disulfide, and which source found it.

    The source matters because the two differ in practice. UniProt annotates
    P25106 with a single bond (117-196) while its AlphaFold model also has
    C34-C287 at 2.03 A — and that unannotated one is the bond that constrains
    ECL3. A veto keyed on annotations alone is blind to exactly the population
    it exists to protect: our published ACKR3 P35 reports 12.1 A of clearance
    while sitting 3.81 A from C287's SG.
    """

    first: int
    second: int
    #: ``"annotated"`` (in UniProt, and in the model when one was given),
    #: ``"model"`` (formed in the model, absent from UniProt), or
    #: ``"annotated_not_in_model"`` (asserted by UniProt, not formed in the
    #: model). The last is reported rather than dropped: the annotation is
    #: experimental and the model is a prediction, so a disagreement is a fact
    #: about the inputs, not something to resolve by discarding one of them.
    source: str
    #: SG-SG distance in the model, or None when no model was available.
    sg_distance: float | None = None

    @property
    def span(self) -> int:
        """Residues between the two cysteines — the size of the closed loop."""
        return abs(self.second - self.first)

    def encloses(self, residue: int) -> bool:
        """Strictly inside. The cysteines themselves are hazard POINTS, already
        covered by the distance veto; counting them as enclosed double-counts."""
        return min(self.first, self.second) < residue < max(self.first, self.second)


def model_disulfides(pdb_path: str) -> list[Bond]:
    """Disulfides actually FORMED in the model, by SG-SG distance.

    Read from geometry rather than annotation so an uncurated bond cannot hide.
    """
    from Bio.PDB import PDBParser

    struct = PDBParser(QUIET=True).get_structure("m", str(pdb_path))
    sg = {
        res.id[1]: res["SG"].coord
        for res in struct.get_residues()
        if res.get_resname() == "CYS" and "SG" in res
    }
    out: list[Bond] = []
    seen = sorted(sg)
    for i, a in enumerate(seen):
        for b in seen[i + 1 :]:
            d = float((((sg[a] - sg[b]) ** 2).sum()) ** 0.5)
            if d <= SG_BOND_MAX_A:
                out.append(Bond(a, b, source="model", sg_distance=d))
    return out


def disulfide_bonds(
    features: list[dict[str, Any]], pdb_path: str | None
) -> list[Bond]:
    """Every disulfide either source knows about, each labelled by its source."""
    annotated = {
        (min(s, e), max(s, e))
        for s, e in (
            (
                (f.get("location") or {}).get("start", {}).get("value"),
                (f.get("location") or {}).get("end", {}).get("value"),
            )
            for f in features
            if f.get("type") == "Disulfide bond"
        )
        if isinstance(s, int) and isinstance(e, int)
    }
    formed = {(b.first, b.second): b for b in model_disulfides(pdb_path)} if pdb_path else {}

    out: list[Bond] = []
    for pair in sorted(annotated | set(formed)):
        in_model = formed.get(pair)
        if pair in annotated:
            # No model is a reason to trust the annotation unverified, not to
            # claim the bond is absent.
            source = (
                "annotated"
                if in_model is not None or not pdb_path
                else "annotated_not_in_model"
            )
        else:
            source = "model"
        out.append(
            Bond(
                pair[0],
                pair[1],
                source=source,
                sg_distance=in_model.sg_distance if in_model else None,
            )
        )
    return out


def hazard_residues_with_model(
    features: list[dict[str, Any]], pdb_path: str | None
) -> set[int]:
    """``hazard_residues`` plus the cysteines of bonds only the model knows.

    This alone fixes the ACKR3 class of defect: once C34/C287 are hazard
    residues, the existing 10 A clearance veto rejects P35 on its own. Nothing
    was wrong with that veto — it had never seen the bond.
    """
    out = hazard_residues(features)
    for bond in disulfide_bonds(features, pdb_path):
        out.update((bond.first, bond.second))
    return out


def enclosing_bonds(bonds: list[Bond], residue: int) -> list[Bond]:
    """The bonds whose closed loop strictly contains ``residue``."""
    return [b for b in bonds if b.encloses(residue)]


def insert_exceeds_closure(*, insert_aa: int, span: int) -> bool:
    """Whether an insert is at least as long as the closure it is going into.

    This is the veto; enclosure on its own is NOT. A published-corpus pass over
    176 internal sites found 27 strictly inside a disulfide span — 12 of them
    functionally validated, a HIGHER enclosure rate than among display-only
    sites — at spans from 9 to 655. So no span cutoff separates our MS4A1 case
    from published precedent, because span is not the variable that differs.
    What differs is the cargo: those precedents are ~8-11 aa epitope tags,
    while a 51-aa cassette into a 16-residue closure adds three times the
    residues the loop contains. (That 27/176 is a LOWER bound — it was measured
    from UniProt annotations, which ACKR3 shows to be incomplete.)

    Because the verdict depends on the cargo, it cannot be a static boolean on
    a site record: the same site is fatal for a 51-aa cassette and fine for an
    11-aa HA.
    """
    return insert_aa >= span


def ca_coords(pdb_path: str) -> dict[int, tuple[float, float, float]]:
    """Per-residue CA coordinate (x, y, z) on the model — for 3D distance filters
    (e.g. terminus-proximity). Tuples (not numpy) so callers stay numpy-free."""
    from Bio.PDB import PDBParser

    struct = PDBParser(QUIET=True).get_structure("m", str(pdb_path))
    out: dict[int, tuple[float, float, float]] = {}
    for res in struct.get_residues():
        if "CA" in res:
            c = res["CA"].coord
            out[res.id[1]] = (float(c[0]), float(c[1]), float(c[2]))
    return out


def feature_distances(pdb_path: str, hazard_res: set[int]) -> dict[int, float]:
    """Per-residue minimum CA-CA distance (Å) to any hazard residue on the
    model. Residues with no hazard in the structure get ``inf`` (fully clear)."""
    from Bio.PDB import PDBParser

    struct = PDBParser(QUIET=True).get_structure("m", str(pdb_path))
    ca: dict[int, Any] = {}
    for res in struct.get_residues():
        if "CA" in res:
            ca[res.id[1]] = res["CA"].coord
    hazard_coords = [ca[h] for h in hazard_res if h in ca]
    out: dict[int, float] = {}
    for r, coord in ca.items():
        if not hazard_coords:
            out[r] = float("inf")
            continue
        out[r] = min(float(((coord - h) ** 2).sum() ** 0.5) for h in hazard_coords)
    return out


def fetch_uniprot_features(acc: str, http: Any | None = None) -> list[dict[str, Any]]:
    """Fetch the reviewed UniProt entry and return its ``features`` list. Uses
    the repo's default rate-limited cached client when ``http`` is None."""
    from accessible_surfaceome.tools._shared.http import open_default_client

    close = False
    if http is None:
        http = open_default_client()
        close = True
    try:
        data = http.get_json(
            f"https://rest.uniprot.org/uniprotkb/{acc}.json",
            source="uniprot",
            ttl_days=30,
        )
    finally:
        if close:
            http.__exit__(None, None, None)
    return data.get("features", []) if isinstance(data, dict) else []
