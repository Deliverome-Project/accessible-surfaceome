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


#: Sequence separation at or below which a CA-CA distance is set by backbone
#: geometry rather than by the fold. At separation 1 the Ca-Ca virtual bond
#: fixes it at 3.81-3.86 A whatever the structure does, so a residue beside a
#: hazard reads ~3.8 A and would be vetoed by peptide geometry alone.
#:
#: Calibrated, not chosen: over 185 published internal tag sites, 9 of 130
#: junctions sit within 2 residues of their cysteine, and the spatial-only
#: minima (separation > 2) are CA-CA 5.29 / CA-SG 5.04 / heavy-SG 4.13. The
#: load-bearing row is ADCYAP1R1 D24 — surface_and_function, position
#: validated, ONE residue from bonded C25 — so adjacency to a bonded cysteine
#: is a configuration that demonstrably displays and functions.
ADJACENCY_SEP = 2


def _ca_by_residue(pdb_path: str) -> dict[int, Any]:
    from Bio.PDB import PDBParser

    struct = PDBParser(QUIET=True).get_structure("m", str(pdb_path))
    return {
        res.id[1]: res["CA"].coord for res in struct.get_residues() if "CA" in res
    }


def feature_distances(pdb_path: str, hazard_res: set[int]) -> dict[int, float]:
    """Per-residue minimum CA-CA distance (Å) to a SPATIALLY distinct hazard.

    Hazards within ``ADJACENCY_SEP`` residues in sequence are excluded, because
    their distance is dictated by the backbone rather than by the fold — see
    that constant. A residue whose only hazards are its sequence neighbours
    gets ``inf``: it has no spatial hazard, and reporting 3.8 A there is what
    rejected ACKR3 P35 as a defect (its 3.83 A reading is C34 at separation 1;
    its nearest spatial bonded cysteine is C287 at 7.63 A).

    Adjacency is not discarded — ``hazard_separations`` reports it, so a gate or
    a ranking can weigh "sits beside a functional residue" on its own terms
    instead of smuggling it in as a distance.
    """
    ca = _ca_by_residue(pdb_path)
    present = sorted(h for h in hazard_res if h in ca)
    out: dict[int, float] = {}
    hazards = set(present)
    for r, coord in ca.items():
        if r in hazards:
            # The residue IS the hazard. Kept at 0.0 so the gate still refuses
            # to insert AT a functional residue — that exclusion is categorical
            # ("do not tag the glycosylation sequon"), not a threshold on a
            # continuous signal, so it is the one kind of veto worth having.
            # Without this the split reports the NEXT hazard's distance and a
            # sequon reads as clear: TFRC N251 went to 19.4 A.
            out[r] = 0.0
            continue
        spatial = [ca[h] for h in present if abs(h - r) > ADJACENCY_SEP]
        if not spatial:
            out[r] = float("inf")
            continue
        out[r] = min(float(((coord - h) ** 2).sum() ** 0.5) for h in spatial)
    return out


def hazard_separations(
    pdb_path: str, hazard_res: set[int]
) -> dict[int, int | None]:
    """Per-residue SEQUENCE separation to the nearest hazard residue.

    ``0`` means the residue IS a hazard; ``None`` means the protein has none.
    Reported alongside the spatial distance rather than folded into it, because
    the two are different claims: one says "a functional atom is close in
    space", the other says "a functional residue is adjacent in the chain", and
    only the first is a clash.
    """
    ca = _ca_by_residue(pdb_path)
    present = sorted(h for h in hazard_res if h in ca)
    return {
        r: (min(abs(h - r) for h in present) if present else None) for r in ca
    }


def c_terminal_propeptide(
    features: list[dict[str, Any]], length: int
) -> tuple[int, int] | None:
    """The Propeptide span covering the C-terminus, from UniProt features.

    A GPI-anchored protein's C-terminal propeptide is cleaved at the omega site
    and replaced by the anchor. The DeepTMHMM string ends extracellular either
    way, so without this the terminal lane proposes a tag at a residue the cell
    removes: 20 of 21 published ``terminal_c`` rows across 19 GPI proteins sat
    inside one of these spans, each at the full precursor length.

    Only a span covering ``length`` is returned — an N-terminal or internal
    propeptide says nothing about that end.

    NOTE on coverage, by analogy with disulfides: 29.9% of model-formed bonds
    carry no UniProt ``DISULFID``, and the same question applies here. "No
    Propeptide annotated" is not "no propeptide", so this is a lower bound on
    the affected population and a predicted omega site would widen it.
    """
    for feat in features:
        if feat.get("type") != "Propeptide":
            continue
        loc = feat.get("location") or {}
        start = (loc.get("start") or {}).get("value")
        end = (loc.get("end") or {}).get("value")
        if isinstance(start, int) and isinstance(end, int) and start <= length <= end:
            return (start, end)
    return None


def gpi_omega_site(features: list[dict[str, Any]]) -> int | None:
    """The GPI-anchor attachment residue from a ``Lipidation`` feature, if
    annotated. Reported for provenance: it sits one residue before the
    propeptide start in every case measured, so it corroborates the span rather
    than replacing it."""
    for feat in features:
        if feat.get("type") != "Lipidation":
            continue
        if "GPI" not in (feat.get("description") or ""):
            continue
        value = ((feat.get("location") or {}).get("start") or {}).get("value")
        if isinstance(value, int):
            return value
    return None


def cleaved_c_terminus(
    features: list[dict[str, Any]], length: int
) -> tuple[int, int] | None:
    """The span removed from the C-terminus during maturation, from either
    annotation UniProt may carry.

    A curated ``Propeptide`` covering the terminus is preferred. Failing that, a
    GPI ``Lipidation`` establishes the same cleavage: the omega residue carries
    the anchor and SURVIVES, so the removed span begins one residue after it.

    Both paths matter. Over the 115 deterministic ``terminal_c`` rows whose gene
    is GPI-anchored by NetGPI, 110 carry the Propeptide and 2 more (ACHE, MSLN)
    carry only the Lipidation — two genes for no extra request, since the caller
    already fetched this list for the hazard veto.

    The remaining 3 are annotated in neither, and NetGPI is deliberately NOT
    wired in to reach them: its omega sites are given in whichever form was
    submitted, not the canonical frame these records are numbered against, and
    it is wrong where it disagrees (GPC5 at 27 of 572 residues). Resolving a
    predicted site into this frame is the sha256-of-sequence problem, not a
    column read, and 3 genes does not pay for it.
    """
    span = c_terminal_propeptide(features, length)
    if span is not None:
        return span
    omega = gpi_omega_site(features)
    if omega is None or omega >= length:
        # omega == length is an anchor at the last residue: nothing is removed,
        # and an empty range must not read as a cleavage.
        return None
    return (omega + 1, length)


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
