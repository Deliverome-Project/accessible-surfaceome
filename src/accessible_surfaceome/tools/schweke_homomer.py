"""Schweke 2024 per-UniProt homo-oligomer lookup helper.

Returns :class:`HomoOligomerizationFeatures` for any UniProt accession,
populated from Schweke et al. 2024's AF2 homomer atlas (PMID 38325366,
DOI 10.1016/j.cell.2024.01.022). Mirrors :mod:`tools.surface_bind`:
pure lookup, no network calls on the orchestrator hot path.

Data source resolution order (first one with the gene wins):

1. **Public D1** ``schweke_homomer`` table — the future canonical source
   once the user's D1 push lands. Schema expected:
   ``uniprot_acc TEXT PRIMARY KEY, is_homo_oligomer INTEGER, stoichiometry INTEGER NULL``.
   When the table doesn't exist yet (current state), the D1 query fails
   silently and we fall through.
2. **Checked-in viewer manifest**
   ``viewer/public/data/structures/schweke/manifest.json`` — the 8 sample
   entries the viewer's StructureViewer card uses for its homo-oligomer
   tab assets. Covers a tiny fraction of the atlas; mainly useful as a
   smoke-test data source while D1 is being set up.
3. **Default** :class:`HomoOligomerizationFeatures` with
   ``is_homo_oligomer=False`` — Schweke's atlas is positives-only, so
   "not found anywhere" is its own signal (matches the
   :attr:`SurfaceBindFeatures.has_data` pattern: explicit absence flag,
   never null).

Schweke's manifest entries carry a ``stoichiometry`` for higher-order
complexes (3..13) but only ``"af_model_num"`` + ``"ecd_only"`` for the
2-mer dimer subset; we read ``stoichiometry`` when present, otherwise
default to ``2`` (the AF_dimer_models_core subset is all dimers by
construction). See ``data/external/schweke_homomer_atlas/PROVENANCE.md``
(memory entry ``schweke-homomer-atlas``) for the figshare-deposit
recovery path that populates the future D1 table.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from accessible_surfaceome.tools._shared.models import HomoOligomerizationFeatures

logger = logging.getLogger(__name__)

# Resolves relative to the repo root rather than the package.
_MANIFEST_PATH = (
    Path(__file__).resolve().parents[3]
    / "viewer" / "public" / "data" / "structures" / "schweke" / "manifest.json"
)

_MANIFEST_CACHE: dict[str, dict[str, Any]] | None = None


def _load_manifest() -> dict[str, dict[str, Any]]:
    """Lazy-load the viewer's Schweke manifest into a module-level cache.

    Returns an empty dict if the manifest isn't checked in. Comment keys
    (anything starting with ``_``) are stripped so they don't shadow a
    real UniProt acc.
    """
    global _MANIFEST_CACHE
    if _MANIFEST_CACHE is not None:
        return _MANIFEST_CACHE
    if not _MANIFEST_PATH.exists():
        _MANIFEST_CACHE = {}
        return _MANIFEST_CACHE
    try:
        raw = json.loads(_MANIFEST_PATH.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning(
            "schweke_homomer: manifest read failed at %s: %s — using empty cache",
            _MANIFEST_PATH,
            exc,
        )
        _MANIFEST_CACHE = {}
        return _MANIFEST_CACHE
    _MANIFEST_CACHE = {
        k: v for k, v in raw.items()
        if not k.startswith("_") and isinstance(v, dict)
    }
    return _MANIFEST_CACHE


def _lookup_d1(uniprot_acc: str) -> HomoOligomerizationFeatures | None:
    """Try the public-D1 ``schweke_homomer_public`` table.

    Schweke's atlas is **positives-only**: each row is a protein flagged
    as a homomer; "not in Schweke" = no row. So a hit means
    ``is_homo_oligomer=True`` implicitly; we just read ``stoichiometry``
    (cyclic-symmetry order N) for the severity weight. The table is keyed
    on ``(universe_version, uniprot_acc)``; querying without the
    universe_version filter is fine until multiple snapshots coexist.

    Returns ``None`` on any failure (table missing / D1 unreachable / no
    row) so the caller falls through to the manifest path. ``None`` from
    the D1 path means "we didn't find Schweke metadata HERE" — NOT "the
    protein is not a homomer" (that's expressed as a real return value
    with ``is_homo_oligomer=False``).
    """
    try:
        from accessible_surfaceome.cloud.d1_client import D1Client
    except ImportError:  # pragma: no cover — D1 client always available in CI
        return None
    try:
        with D1Client() as d1:
            rows = d1.query(
                "SELECT stoichiometry, af_model_num, is_ecd_only, "
                "has_higher_order_complex, dimer_pdb_filename, "
                "complex_pdb_filename "
                "FROM schweke_homomer_public "
                "WHERE uniprot_acc = ? ORDER BY universe_version DESC LIMIT 1;",
                [uniprot_acc],
            )
    except Exception:  # noqa: BLE001 — table missing / network down is fine
        return None
    # A successful query with no rows means "not in Schweke's positive
    # refset" (since the table is positives-only). Materialize that
    # explicitly so the manifest fallback doesn't get to second-guess.
    if not rows:
        return HomoOligomerizationFeatures(is_homo_oligomer=False)
    r = rows[0]

    def _intornull(v: Any) -> int | None:
        return int(v) if isinstance(v, (int, float)) else None

    return HomoOligomerizationFeatures(
        is_homo_oligomer=True,
        stoichiometry=_intornull(r.get("stoichiometry")),
        af_model_num=_intornull(r.get("af_model_num")),
        is_ecd_only=bool(r.get("is_ecd_only")),
        has_higher_order_complex=bool(r.get("has_higher_order_complex")),
        dimer_pdb_filename=r.get("dimer_pdb_filename") or None,
        complex_pdb_filename=r.get("complex_pdb_filename") or None,
    )


def lookup(uniprot_acc: str) -> HomoOligomerizationFeatures:
    """Return the :class:`HomoOligomerizationFeatures` block for a UniProt acc.

    Always returns a schema-valid model — never raises. ``is_homo_oligomer
    =False`` is the explicit "not in Schweke's positive refset" signal.
    """
    d1_hit = _lookup_d1(uniprot_acc)
    if d1_hit is not None:
        return d1_hit

    manifest = _load_manifest()
    entry = manifest.get(uniprot_acc)
    if entry is None:
        return HomoOligomerizationFeatures(is_homo_oligomer=False)

    # The viewer manifest entry has either:
    #   * "stoichiometry": N  for higher-order (full_complexes_bigbang); OR
    #   * no "stoichiometry"   for plain dimers (AF_dimer_models_core).
    raw_n = entry.get("stoichiometry")
    n: int | None
    if isinstance(raw_n, int) and 2 <= raw_n <= 24:
        n = raw_n
    elif raw_n is None:
        # AF_dimer_models_core subset → all dimers by construction.
        n = 2
    else:
        # Out-of-range / unexpected type — record as homomer but leave
        # stoichiometry None rather than fabricate a value.
        n = None

    # Reconstruct PDB filenames from the same conventions documented in
    # the manifest comment so the viewer can build asset URLs even on the
    # manifest-fallback path (when D1 isn't reachable).
    af_model_num = entry.get("af_model_num")
    af_n = af_model_num if isinstance(af_model_num, int) else None
    dimer_filename = (
        f"{uniprot_acc}_V1_{af_n}.pdb" if af_n is not None else None
    )
    complex_filename = (
        f"{uniprot_acc}_V1_{af_n}_c{n}.pdb"
        if af_n is not None and n is not None and n > 2
        else None
    )
    return HomoOligomerizationFeatures(
        is_homo_oligomer=True,
        stoichiometry=n,
        af_model_num=af_n,
        is_ecd_only=bool(entry.get("ecd_only")),
        has_higher_order_complex=(n is not None and n > 2),
        dimer_pdb_filename=dimer_filename,
        complex_pdb_filename=complex_filename,
    )
