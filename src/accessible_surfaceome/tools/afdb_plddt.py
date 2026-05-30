"""AlphaFold DB per-residue pLDDT fetcher.

Resolves an UniProt accession to a :class:`StructureFeatures` record by
reading AlphaFold DB's prediction metadata + structure file. When a
DeepTMHMM ``per_residue_topology`` string is provided, the metrics are
restricted to extracellular-domain (ECD) residues — matching the schema
field name ``ecd_mean_plddt``. Otherwise the whole-protein
``globalMetricValue`` is used and the source label flags the fallback
so a reader knows it's not ECD-restricted.

This is the Tier 1.5 fetcher PR #29 left unbuilt — see
[PR #35](https://github.com/Deliverome-Project/accessible-surfaceome/pull/35)
"Deferred from this PR" list.

Caching layout (per [PR #29](https://github.com/Deliverome-Project/accessible-surfaceome/pull/29)
viewer SRC structure work)::

    data/cache/afdb_prediction/{uniprot_acc}.json  # API metadata
    data/cache/afdb_prediction/{uniprot_acc}.cif   # structure model

Both are read cache-first; HTTP fetch + write happens only on miss.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import httpx

from accessible_surfaceome.tools._shared.models import AFDBVersion, StructureFeatures

logger = logging.getLogger(__name__)

# Resolves relative to the repo root rather than the package, because
# the cache is repo-data not package-data. PR #29 created the dir.
AFDB_CACHE_DIR = (
    Path(__file__).resolve().parents[3] / "data" / "cache" / "afdb_prediction"
)

# AFDB's confidence buckets: residues with pLDDT < 70 are "low
# confidence" (often disordered / flexible regions). The schema field
# ``ecd_disordered_fraction`` uses this threshold so downstream filters
# can flag epitope masking by intrinsically-disordered ECD content.
PLDDT_DISORDERED_THRESHOLD = 70.0

# AlphaFold DB JSON metadata endpoint. Returns a list with the canonical
# entry first; the fetcher reads only [0].
AFDB_API_BASE = "https://alphafold.ebi.ac.uk/api/prediction"

# Common citations the StructureFeatures attribution carries through to
# the viewer's Data Sources footer. AlphaFold2 paper + AlphaFold DB
# 2024 update.
_AFDB_CITATIONS = [
    "10.1038/s41586-021-03819-2",
    "10.1093/nar/gkad1011",
]


_VALID_AFDB_VERSIONS: frozenset[str] = frozenset(
    {"v1", "v2", "v3", "v4", "v5", "v6", "v7", "v8", "v9"}
)


def _afdb_version_string(latest_version: object) -> AFDBVersion:
    """Render AFDB's ``latestVersion`` (numeric) as a ``"vN"`` string.

    AFDB metadata returns an ``int`` (typically ``4`` through ``6`` as
    of 2026-05); the on-disk afdb_id + the viewer's display use
    ``"v{N}"`` shape. Returns ``"v4"`` as a last-resort fallback when
    the field is missing / non-numeric — that was the historical
    hardcoded value, and matches the historical link shape so existing
    consumers don't change behavior.

    Return type is the narrow :data:`AFDBVersion` Literal so the
    ``StructureFeatures`` constructor's strict literal field doesn't
    require a ``ty:ignore`` at the call sites.
    """
    candidate: str
    if isinstance(latest_version, int) and latest_version > 0:
        candidate = f"v{latest_version}"
    elif isinstance(latest_version, str):
        s = latest_version.strip()
        if s.startswith("v"):
            candidate = s
        else:
            try:
                n = int(s)
                candidate = f"v{n}" if n > 0 else "v4"
            except ValueError:
                candidate = "v4"
    else:
        candidate = "v4"
    if candidate in _VALID_AFDB_VERSIONS:
        return candidate  # ty:ignore[invalid-return-type]
    # Beyond v9: log + clamp so the schema doesn't reject the record.
    # Widening _VALID_AFDB_VERSIONS is the right fix when this fires.
    logger.warning(
        "AFDB returned latestVersion=%r outside the schema's "
        "v1-v9 range; defaulting to v4 — widen AFDBVersion in "
        "tools._shared.models and _VALID_AFDB_VERSIONS here.",
        latest_version,
    )
    return "v4"


def _coerce_float(value: object, default: float = 0.0) -> float:
    """Best-effort float coercion for AFDB metadata fields.

    ``dict.get`` returns ``object`` to the type checker; collapsing the
    None / wrong-type case here keeps the call sites readable.
    """
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return default
    return default


def fetch_afdb_plddt(
    uniprot_acc: str,
    per_residue_topology: str | None = None,
) -> StructureFeatures:
    """Resolve ``uniprot_acc`` to AFDB pLDDT metrics.

    When ``per_residue_topology`` is provided and contains at least one
    ``O`` character (DeepTMHMM extracellular marker), ECD-restricted
    metrics are computed from the per-residue pLDDT array parsed out of
    the CIF model. Otherwise the whole-protein metrics from the API
    metadata stand in for the ECD measurements (labeled in ``source``).

    Returns a :class:`StructureFeatures` record. Failures (network
    error, 404, malformed CIF) return a labeled-placeholder record so
    the v1/v2 orchestrators can still assemble a SurfaceomeRecord.
    """

    AFDB_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    meta_path = AFDB_CACHE_DIR / f"{uniprot_acc}.json"
    cif_path = AFDB_CACHE_DIR / f"{uniprot_acc}.cif"

    try:
        metadata = _load_or_fetch_metadata(uniprot_acc, meta_path)
    except Exception as exc:  # noqa: BLE001 — keep the orchestrator running
        logger.warning(
            "AFDB metadata fetch failed for %s (%s); returning placeholder",
            uniprot_acc,
            exc,
        )
        return _placeholder(uniprot_acc, reason=str(exc))

    afdb_id_raw = metadata.get("entryId")
    afdb_id: str = (
        afdb_id_raw if isinstance(afdb_id_raw, str) and afdb_id_raw
        else f"AF-{uniprot_acc}-F1"
    )
    # AFDB has been bumping model versions over time (SRC = v6 as of
    # 2026-05; earlier versions are removed from the file server, so
    # "v4" is now a 404 link for many entries). Read the real version
    # from the API's `latestVersion` rather than hardcoding "v4".
    # The fallback is "v4" only because that's what every
    # placeholder path historically emitted — once the API responds
    # this code path is always taken.
    afdb_version: str = _afdb_version_string(metadata.get("latestVersion"))

    # Whole-protein values from the API metadata. These are always
    # available even when the CIF isn't reachable.
    global_metric = _coerce_float(metadata.get("globalMetricValue"))
    frac_low = _coerce_float(metadata.get("fractionPlddtLow"))
    frac_very_low = _coerce_float(metadata.get("fractionPlddtVeryLow"))
    whole_disordered = frac_low + frac_very_low

    has_ecd = bool(per_residue_topology and "O" in per_residue_topology)

    if not has_ecd:
        return StructureFeatures(
            afdb_id=afdb_id,
            afdb_version=afdb_version,
            ecd_mean_plddt=global_metric,
            ecd_disordered_fraction=whole_disordered,
            source=(
                "AlphaFold DB (whole-protein pLDDT — no ECD residues in topology)"
            ),
            license="CC BY 4.0",
            attribution="© DeepMind / EMBL-EBI",
            citations=list(_AFDB_CITATIONS),
        )

    # ECD path — needs the CIF for per-residue pLDDT.
    cif_url_raw = metadata.get("cifUrl")
    cif_url: str | None = cif_url_raw if isinstance(cif_url_raw, str) else None
    if not cif_url:
        logger.warning(
            "AFDB metadata for %s lacks cifUrl; falling back to globalMetric",
            uniprot_acc,
        )
        return StructureFeatures(
            afdb_id=afdb_id,
            afdb_version=afdb_version,
            ecd_mean_plddt=global_metric,
            ecd_disordered_fraction=whole_disordered,
            source="AlphaFold DB (whole-protein pLDDT — no cifUrl in metadata)",
            license="CC BY 4.0",
            attribution="© DeepMind / EMBL-EBI",
            citations=list(_AFDB_CITATIONS),
        )

    try:
        plddt_per_residue = _load_or_fetch_cif(cif_url, cif_path)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "AFDB CIF fetch / parse failed for %s (%s); using globalMetric",
            uniprot_acc,
            exc,
        )
        return StructureFeatures(
            afdb_id=afdb_id,
            afdb_version=afdb_version,
            ecd_mean_plddt=global_metric,
            ecd_disordered_fraction=whole_disordered,
            source=f"AlphaFold DB (whole-protein pLDDT — CIF unavailable: {exc})",
            license="CC BY 4.0",
            attribution="© DeepMind / EMBL-EBI",
            citations=list(_AFDB_CITATIONS),
        )

    # Length mismatch can happen when DeepTMHMM is run on one isoform
    # but AFDB only has the canonical. Be defensive and fall back to
    # whole-protein rather than mis-aligning residues.
    if len(plddt_per_residue) != len(per_residue_topology):
        logger.warning(
            "AFDB CIF length (%d) != topology length (%d) for %s; "
            "using globalMetric",
            len(plddt_per_residue),
            len(per_residue_topology),
            uniprot_acc,
        )
        return StructureFeatures(
            afdb_id=afdb_id,
            afdb_version=afdb_version,
            ecd_mean_plddt=global_metric,
            ecd_disordered_fraction=whole_disordered,
            source=(
                f"AlphaFold DB (whole-protein pLDDT — "
                f"len mismatch: CIF={len(plddt_per_residue)} "
                f"vs topology={len(per_residue_topology)})"
            ),
            license="CC BY 4.0",
            attribution="© DeepMind / EMBL-EBI",
            citations=list(_AFDB_CITATIONS),
        )

    ecd_plddts = [
        p
        for p, ch in zip(plddt_per_residue, per_residue_topology, strict=True)
        if ch == "O"
    ]
    n_ecd = len(ecd_plddts)
    ecd_mean = sum(ecd_plddts) / n_ecd
    disordered = sum(1 for p in ecd_plddts if p < PLDDT_DISORDERED_THRESHOLD)
    ecd_disordered = disordered / n_ecd

    return StructureFeatures(
        afdb_id=afdb_id,
        afdb_version=afdb_version,
        ecd_mean_plddt=ecd_mean,
        ecd_disordered_fraction=ecd_disordered,
        source=f"AlphaFold DB (ECD-restricted pLDDT, n={n_ecd})",
        license="CC BY 4.0",
        attribution="© DeepMind / EMBL-EBI",
        citations=list(_AFDB_CITATIONS),
    )


def _load_or_fetch_metadata(
    uniprot_acc: str, meta_path: Path
) -> dict[str, object]:
    """Return the canonical AFDB metadata entry for ``uniprot_acc``.

    Reads ``meta_path`` (a JSON list as returned by AFDB's API) if it
    exists, otherwise GETs ``{AFDB_API_BASE}/{uniprot_acc}``, writes the
    response body to ``meta_path``, and returns the parsed [0] entry.
    """

    if meta_path.exists():
        payload = json.loads(meta_path.read_text())
    else:
        url = f"{AFDB_API_BASE}/{uniprot_acc}"
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(url)
            resp.raise_for_status()
            payload = resp.json()
            meta_path.write_text(json.dumps(payload, indent=2))
    if not payload:
        raise ValueError(f"AFDB metadata for {uniprot_acc} is empty")
    entry = payload[0] if isinstance(payload, list) else payload
    if not isinstance(entry, dict):
        raise ValueError(
            f"AFDB metadata for {uniprot_acc} has unexpected shape: "
            f"{type(entry).__name__}"
        )
    return entry


def _load_or_fetch_cif(cif_url: str, cif_path: Path) -> list[float]:
    """Read CIF from cache or fetch from AFDB; return per-residue pLDDT.

    AFDB CIFs store pLDDT in the B-factor column of each atom. We pick
    one value per residue (the CA atom's B-factor), so the returned
    list has length == protein length.
    """

    if cif_path.exists():
        cif_text = cif_path.read_text()
    else:
        with httpx.Client(timeout=60.0) as client:
            resp = client.get(cif_url)
            resp.raise_for_status()
            cif_text = resp.text
            cif_path.write_text(cif_text)
    return _parse_ca_plddt(cif_text)


def _parse_ca_plddt(cif_text: str) -> list[float]:
    """Extract per-residue pLDDT from an AFDB CIF.

    AFDB CIFs use a single-model, single-chain, single-atom-set layout
    so we don't need full mmCIF parsing — a line-based scan picks up
    the CA B-factor per residue. This avoids pulling biopython into the
    hot path even though it's a project dep.

    Falls back to scanning all CA records and keeping one per residue
    when the layout deviates from canonical AFDB.
    """

    plddts: list[float] = []
    seen_residue_ids: set[int] = set()
    in_atom_loop = False
    column_index: dict[str, int] = {}
    columns: list[str] = []

    for raw_line in cif_text.splitlines():
        line = raw_line.strip()
        if line.startswith("_atom_site."):
            columns.append(line.split(".", 1)[1])
            in_atom_loop = True
            continue
        if in_atom_loop and not column_index:
            column_index = {name: i for i, name in enumerate(columns)}
        if not line or line.startswith("#") or line.startswith("loop_"):
            # End of the atom loop is the next loop_ / blank / comment.
            if in_atom_loop and plddts:
                # We've already collected data — stop at next section
                break
            continue
        if not in_atom_loop or not column_index:
            continue
        if not (line.startswith("ATOM") or line.startswith("HETATM")):
            # Hit a non-data row inside the loop → done.
            if plddts:
                break
            continue
        fields = line.split()
        atom_id_col = column_index.get("label_atom_id")
        seq_id_col = column_index.get("label_seq_id")
        b_col = column_index.get("B_iso_or_equiv")
        if atom_id_col is None or seq_id_col is None or b_col is None:
            raise ValueError("CIF _atom_site loop missing required columns")
        if len(fields) <= max(atom_id_col, seq_id_col, b_col):
            continue
        if fields[atom_id_col] != "CA":
            continue
        try:
            res_id = int(fields[seq_id_col])
        except ValueError:
            continue
        if res_id in seen_residue_ids:
            continue
        try:
            plddts.append(float(fields[b_col]))
        except ValueError:
            continue
        seen_residue_ids.add(res_id)

    if not plddts:
        raise ValueError("no CA pLDDT values parsed from CIF")
    return plddts


def _placeholder(uniprot_acc: str, *, reason: str) -> StructureFeatures:
    """Schema-valid placeholder when AFDB fetch fails entirely.

    Mirrors :func:`accessible_surfaceome.agents.surfaceome_v1.d1_deterministic._stub_structure`
    so v1 and v2 see the same shape when AFDB is unreachable.
    """

    return StructureFeatures(
        afdb_id=f"AF-{uniprot_acc}-F1",
        # Placeholder path doesn't know the real version — leave a
        # sentinel so the viewer doesn't claim a wrong number, and
        # the `structPlaceholder` check on `source` hides the value
        # anyway.
        afdb_version="unknown",
        ecd_mean_plddt=0.0,
        ecd_disordered_fraction=0.0,
        source=f"AlphaFold DB (placeholder — fetch failed: {reason})",
        license="CC BY 4.0",
        attribution="© DeepMind / EMBL-EBI",
        citations=list(_AFDB_CITATIONS),
    )
