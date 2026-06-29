"""Fetch DeterministicFeatures for the v1 orchestrator from public D1.

The DeepTMHMM / Compara / Compara-ortholog-ECD sweep
(``scripts/build/run_topology_sweep.py``) lands the three deterministic-side
tables in D1:

* ``topology_public`` — per-isoform topology (per-residue string,
  TM/SP counts, terminal orientations) for human canonical + isoforms +
  mouse/cyno orthologs.
* ``compara_paralog`` — within-species paralog pairs with BLOSUM62
  ECD identity.
* ``compara_ortholog_ecd`` — cross-species ortholog ECD identity
  (mouse, cynomolgus).

This module reads those rows and assembles them into a
:class:`DeterministicFeatures` Pydantic model that the orchestrator can
slot directly into the ``SurfaceomeRecord`` it builds for a gene.

Falls back to a stub for ``StructureFeatures`` because AFDB pLDDT
extraction is not yet wired (its fetcher will land in a follow-up). The
``source`` field is labeled explicitly so a reader doesn't mistake the
zero-pLDDT placeholder for a real measurement.

The reader-side D1 client is the same ``D1Client`` the rest of the
codebase uses; auth comes from ``.env`` (see ``CLAUDE.md``).
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime
from typing import Any

import httpx

from accessible_surfaceome.merge.ortholog_topology_projection import (
    project_human_topology_onto_ortholog,
)
from accessible_surfaceome.tools._shared.models import (
    DeterministicFeatures,
    IsoformTopology,
    OrthologEntry,
    Orthologs,
    ParalogEntry,
    StructureFeatures,
    TerminalOrientation,
)

logger = logging.getLogger(__name__)

# Cap how many paralogs we materialize per gene — Compara families like
# IG / olfactory receptors have hundreds; the agent doesn't need them all
# and the rendered record would explode. Matches the per-gene cap in
# scripts/upload/upload_paralogs_to_d1.py.
PARALOG_TOP_N = 50


def _query_public(sql: str, params: list[Any]) -> list[dict[str, Any]]:
    """Single-statement query against the public D1.

    Mirrors the helper used by ``scripts/cloud/export_mainbench_to_tsv.py`` —
    pulls credentials from the environment so the orchestrator doesn't
    need a D1Config object passed in.
    """
    acct = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
    token = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
    db = os.environ.get("CLOUDFLARE_D1_SURFACEOME_PUBLIC_ID", "").strip()
    if not (acct and token and db):
        raise RuntimeError(
            "Missing CLOUDFLARE_* env vars; add them to .env "
            "(CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_API_TOKEN, "
            "CLOUDFLARE_D1_SURFACEOME_PUBLIC_ID)."
        )
    url = (
        f"https://api.cloudflare.com/client/v4/accounts/{acct}"
        f"/d1/database/{db}/query"
    )
    resp = httpx.post(
        url,
        json={"sql": sql, "params": params},
        headers={"Authorization": f"Bearer {token}"},
        timeout=30.0,
    )
    data = resp.json()
    if not data.get("success"):
        raise RuntimeError(f"D1 error: {data}")
    result = data.get("result")
    if isinstance(result, list) and result:
        return list(result[0].get("results") or [])
    if isinstance(result, dict):
        return list(result.get("results") or [])
    return []


# ---------------------------------------------------------------------
# Per-table fetchers
# ---------------------------------------------------------------------

def _latest_topology_version() -> str:
    """Resolve the freshest topology_version pointer from topology_release.

    Used to gate every query so we don't accidentally merge multiple
    historical versions for the same gene (e.g. test runs left in D1
    pre-prod).

    **Prefer ``_latest_topology_version_for_cohort(cohort)`` for any
    new code.** When a topology sweep is run for some cohorts but not
    others (e.g. the 2026-05-25 isoforms-only run that left the
    human_canonical / mouse_ortholog / cyno_ortholog cohorts under the
    older topo_2026_05_16), this all-cohorts-share-one-version
    function returns the newest release entry — which may not have
    rows for the cohort you're about to JOIN against, silently
    nulling out topology fields.
    """
    rows = _query_public(
        "SELECT topology_version FROM topology_release "
        "ORDER BY loaded_at DESC LIMIT 1",
        [],
    )
    return rows[0]["topology_version"] if rows else ""


def _latest_topology_version_for_cohort(cohort: str) -> str:
    """Resolve the freshest topology_version that has rows for the
    given cohort.

    Replaces the all-cohorts-share-one-version assumption of
    :func:`_latest_topology_version`. When a topology sweep was run
    for some cohorts but not others, this picks the right version for
    each cohort's JOIN target — so a paralog query against
    ``human_canonical`` finds rows even if the latest release was an
    isoforms-only sweep that doesn't carry that cohort.

    Strategy: take the set of versions that have rows for ``cohort``
    in ``topology_public``, intersect with ``topology_release``
    ordered by ``loaded_at DESC``, return the first match. Falls back
    to any version with rows for the cohort if no release-table entry
    matches (defensive — shouldn't happen in production).
    """
    rows = _query_public(
        "SELECT DISTINCT topology_version FROM topology_public WHERE cohort = ?",
        [cohort],
    )
    versions = {r["topology_version"] for r in rows if r.get("topology_version")}
    if not versions:
        return ""
    # Prefer the topology_release row that's most recently loaded AND
    # has rows for this cohort. Two-step rather than one JOIN because
    # D1's SQL planner is small and the LEFT JOIN on the release table
    # is unreliable for "ordered by NULLS LAST" cases.
    rel_rows = _query_public(
        "SELECT topology_version FROM topology_release "
        "ORDER BY loaded_at DESC",
        [],
    )
    for r in rel_rows:
        if r["topology_version"] in versions:
            return r["topology_version"]
    # Defensive fallback — no release-table match. Pick the version
    # with the highest row count for this cohort (stable across runs).
    return sorted(versions)[-1]


def _latest_paralog_version() -> str:
    rows = _query_public(
        "SELECT paralog_version FROM compara_paralog_release "
        "ORDER BY fetched_at DESC LIMIT 1",
        [],
    )
    return rows[0]["paralog_version"] if rows else ""


def _latest_ortholog_ecd_version() -> str:
    rows = _query_public(
        "SELECT ortholog_ecd_version FROM compara_ortholog_ecd_release "
        "ORDER BY computed_at DESC LIMIT 1",
        [],
    )
    return rows[0]["ortholog_ecd_version"] if rows else ""


def _fetch_canonical_topology(uniprot_acc: str, topology_version: str) -> IsoformTopology | None:
    """The single ``human_canonical`` row for this UniProt acc.

    Returns None if absent — the caller falls back to a clearly-labeled
    stub so the record still validates while a follow-up fetcher fills
    in coverage for the giants (MUC16-class).
    """
    rows = _query_public(
        "SELECT uniprot_acc_full, isoform_id, tm_helix_count, "
        "n_terminal_orientation, c_terminal_orientation, "
        "signal_peptide_length, ecd_length_residues, icd_length_residues, "
        "per_residue_topology, tool_version, retrieved_at "
        "FROM topology_public "
        "WHERE uniprot_acc = ? AND cohort = 'human_canonical' "
        "  AND topology_version = ? "
        "LIMIT 1",
        [uniprot_acc, topology_version],
    )
    if not rows:
        return None
    r = rows[0]
    return IsoformTopology(
        isoform_id=r.get("isoform_id") or f"{uniprot_acc}-1",
        uniprot_acc=r["uniprot_acc_full"] or uniprot_acc,
        tm_helix_count=int(r["tm_helix_count"] or 0),
        n_terminal_orientation=_coerce_orientation(r["n_terminal_orientation"]),
        c_terminal_orientation=_coerce_orientation(r["c_terminal_orientation"]),
        signal_peptide_length=int(r["signal_peptide_length"] or 0),
        ecd_length_residues=int(r["ecd_length_residues"] or 0),
        icd_length_residues=int(r["icd_length_residues"] or 0),
        per_residue_topology=r["per_residue_topology"] or "",
        tool_version=r["tool_version"] or "deeptmhmm-1.0.24",
        retrieved_at=_parse_iso(r["retrieved_at"]),
    )


def _fetch_canonical_sequence(uniprot_acc: str, topology_version: str) -> str:
    """The human canonical row's input FASTA sequence.

    Serves two callers: isoform %identity (``_fetch_isoform_topologies``)
    and projecting the human topology onto orthologs (``_fetch_orthologs``
    via ``merge.ortholog_topology_projection``). Returns ``""`` when absent
    — both callers then degrade gracefully (isoform identity → None,
    ortholog projection skipped) rather than raising.
    """
    rows = _query_public(
        "SELECT sequence FROM topology_public "
        "WHERE uniprot_acc = ? AND cohort = 'human_canonical' "
        "  AND topology_version = ? LIMIT 1",
        [uniprot_acc, topology_version],
    )
    return (rows[0].get("sequence") or "") if rows else ""


def _fetch_isoform_topologies(
    uniprot_acc: str,
    topology_version: str,
    *,
    canonical_topology: str = "",
    canonical_sequence: str = "",
) -> list[IsoformTopology]:
    """Non-canonical isoform topology rows (cohort = ``human_isoforms``).

    Returns [] if no isoforms predicted — that's the common case today
    since the v1 sweep didn't run the isoforms cohort.

    When the canonical topology + sequence are supplied, each isoform's
    full-length and ECD %identity to the canonical are computed inline
    (BLOSUM62 global alignment; see ``merge/isoform_identity.py``).
    Isoforms aren't in Ensembl Compara (same gene, splice variants), so —
    unlike orthologs/paralogs — the identity has to be computed here from
    the sequences the topology sweep already landed in ``topology_public``.
    """
    rows = _query_public(
        "SELECT uniprot_acc_full, isoform_id, tm_helix_count, "
        "n_terminal_orientation, c_terminal_orientation, "
        "signal_peptide_length, ecd_length_residues, icd_length_residues, "
        "per_residue_topology, sequence, tool_version, retrieved_at "
        "FROM topology_public "
        "WHERE uniprot_acc = ? AND cohort = 'human_isoforms' "
        "  AND topology_version = ? "
        "ORDER BY uniprot_acc_full ASC",
        [uniprot_acc, topology_version],
    )
    out: list[IsoformTopology] = []
    for r in rows:
        iso_topo = r["per_residue_topology"] or ""
        iso_seq = r.get("sequence") or ""
        full_pct: float | None = None
        ecd_pct: float | None = None
        ecd_sim: float | None = None
        if canonical_sequence and iso_seq:
            from accessible_surfaceome.merge.isoform_identity import (
                compute_isoform_identity,
            )

            ident = compute_isoform_identity(
                canonical_topology=canonical_topology,
                canonical_sequence=canonical_sequence,
                isoform_topology=iso_topo,
                isoform_sequence=iso_seq,
            )
            full_pct = ident.full_length_pct_identity
            ecd_pct = ident.ecd_pct_identity
            ecd_sim = ident.ecd_pct_similarity
        out.append(
            IsoformTopology(
                isoform_id=r.get("isoform_id") or r["uniprot_acc_full"],
                uniprot_acc=r["uniprot_acc_full"] or uniprot_acc,
                tm_helix_count=int(r["tm_helix_count"] or 0),
                n_terminal_orientation=_coerce_orientation(r["n_terminal_orientation"]),
                c_terminal_orientation=_coerce_orientation(r["c_terminal_orientation"]),
                signal_peptide_length=int(r["signal_peptide_length"] or 0),
                ecd_length_residues=int(r["ecd_length_residues"] or 0),
                icd_length_residues=int(r["icd_length_residues"] or 0),
                per_residue_topology=iso_topo,
                tool_version=r["tool_version"] or "deeptmhmm-1.0.24",
                retrieved_at=_parse_iso(r["retrieved_at"]),
                full_length_pct_identity_to_canonical=full_pct,
                ecd_pct_identity_to_canonical=ecd_pct,
                ecd_pct_similarity_to_canonical=ecd_sim,
                sequence=iso_seq or None,
            )
        )
    return out


# Full-length identity floor above which a paralog is "close" — it gets its
# ECD similarity (computed by scripts/build/compute_paralog_ecd_similarity.py) and
# its real DeepTMHMM topology threaded on so the viewer can render a full
# topology row, like the ortholog rows.
CLOSE_PARALOG_THRESHOLD = 80.0


def _fetch_paralogs(
    uniprot_acc: str,
    paralog_version: str,
    *,
    topology_version: str = "",
) -> list[ParalogEntry]:
    """Top-N paralogs by ECD identity. NULLs sort last via
    ``rank_by_ecd_identity`` so the head is the most-similar pairs.

    Paralogs with NULL ``ecd_pct_identity`` (ECD-less proteins like
    inner-leaflet SRC-family kinases) are INCLUDED in the result —
    family membership is still cross-reactivity signal for
    antibody-derived evidence even when an identity number isn't
    computable.

    Close paralogs (>=80% full-length identity) additionally carry
    ``ecd_pct_similarity`` and their real DeepTMHMM topology (LEFT JOIN
    against ``topology_public`` on the paralog's UniProt acc — same
    pattern the orthologs loader uses). Below-threshold paralogs keep the
    lean chip-only shape (no topology) to avoid bloating records with up
    to 50 per-residue strings per gene.
    """
    rows = _query_public(
        "SELECT cp.paralog_gene_symbol, cp.paralog_uniprot_acc, cp.ecd_pct_identity, "
        "cp.ecd_pct_similarity, cp.biomart_percent_identity, cp.family_id, "
        "cp.compara_version, cp.rank_by_ecd_identity, "
        "tp.per_residue_topology, tp.deeptmhmm_label, tp.tm_helix_count, "
        "tp.ecd_length_residues, tp.icd_length_residues, "
        "tp.n_terminal_orientation, tp.c_terminal_orientation, "
        "tp.signal_peptide_length, tp.sequence "
        "FROM compara_paralog cp "
        "LEFT JOIN topology_public tp "
        "  ON tp.uniprot_acc = cp.paralog_uniprot_acc "
        "  AND tp.cohort = 'human_canonical' AND tp.topology_version = ? "
        "WHERE cp.human_uniprot_acc = ? AND cp.paralog_version = ? "
        "  AND cp.paralog_gene_symbol IS NOT NULL "
        "  AND cp.paralog_uniprot_acc IS NOT NULL "
        "ORDER BY cp.rank_by_ecd_identity ASC NULLS LAST LIMIT ?",
        [topology_version, uniprot_acc, paralog_version, PARALOG_TOP_N],
    )
    out: list[ParalogEntry] = []
    for r in rows:
        try:
            ecd_raw = r.get("ecd_pct_identity")
            ecd_id = float(ecd_raw) if ecd_raw is not None else None
            full_raw = r.get("biomart_percent_identity")
            full_id = float(full_raw) if full_raw is not None else None
            is_close = full_id is not None and full_id >= CLOSE_PARALOG_THRESHOLD
            # Topology + sequence are surfaced only for close paralogs
            # (the ones that get a full topology row).
            topo = tmc = ecdl = seq = None
            if is_close:
                topo = r.get("per_residue_topology") or None
                if topo:
                    seq = r.get("sequence") or None
                    tmc = int(r["tm_helix_count"]) if r.get("tm_helix_count") is not None else None
                    ecdl = int(r["ecd_length_residues"]) if r.get("ecd_length_residues") is not None else None
            out.append(
                ParalogEntry(
                    paralog_symbol=r["paralog_gene_symbol"],
                    paralog_uniprot_acc=r["paralog_uniprot_acc"],
                    ecd_pct_identity=ecd_id,
                    full_length_pct_identity=full_id,
                    family_id=r.get("family_id") or "",
                    compara_version=r.get("compara_version") or "",
                    per_residue_topology=topo,
                    tm_helix_count=tmc,
                    ecd_length_residues=ecdl,
                    sequence=seq,
                )
            )
        except (TypeError, ValueError) as exc:
            logger.warning(
                "skipping malformed paralog row for %s: %s (%s)",
                uniprot_acc, r, exc,
            )
    return out


def _fetch_orthologs(uniprot_acc: str, *, topology_version: str,
                     ortholog_ecd_version: str,
                     human_topology: str = "", human_sequence: str = "") -> Orthologs:
    """Mouse + cyno ortholog entries.

    Reads from ``compara_ortholog_ecd`` (which carries both the full-length
    BioMart % identity and the per-loop BLOSUM62 ECD % identity). Joins
    ``topology_public`` on the ortholog UniProt (filtered to the same
    ``topology_version`` + matching species cohort) to populate
    ``ecd_length`` + ``tm_helix_count``.

    Returns one entry per ortholog. ECD %identity is left None when the
    human protein has no ECD to compare (inner-leaflet, soluble,
    GPI-anchored without surface loops); the full-length identity from
    BioMart is always populated so the reader can still see how conserved
    the ortholog is.
    """
    # Full-length BioMart % identity lives in compara_ortholog.percent_identity,
    # not in compara_ortholog_ecd.biomart_percent_identity (the latter is
    # intentionally NULL — see compute_ortholog_ecd_records in
    # scripts/build/run_topology_sweep.py). Join on the proper composite FK:
    # (release_version, human_ensembl_gene, species, ortholog_ensembl_gene).
    rows = _query_public(
        "SELECT eo.species, eo.ortholog_uniprot_acc, eo.ortholog_ensembl_gene, "
        "eo.ortholog_gene_symbol, eo.ecd_pct_identity, "
        "co.percent_identity AS full_length_pct_identity, "
        "tp.tm_helix_count, tp.ecd_length_residues, "
        "tp.per_residue_topology, tp.deeptmhmm_label, "
        "tp.sequence AS ortholog_sequence, "
        "eo.compara_release "
        "FROM compara_ortholog_ecd eo "
        "LEFT JOIN topology_public tp "
        "  ON tp.uniprot_acc = eo.ortholog_uniprot_acc "
        "  AND tp.topology_version = ? "
        "  AND ( "
        "    (eo.species = 'mouse' AND tp.cohort = 'mouse_ortholog') OR "
        "    (eo.species IN ('cynomolgus','cyno') AND tp.cohort = 'cyno_ortholog') "
        "  ) "
        "LEFT JOIN compara_ortholog co "
        "  ON co.release_version = eo.compara_release "
        "  AND co.human_ensembl_gene = eo.human_ensembl_gene "
        "  AND co.species = eo.species "
        "  AND co.ortholog_ensembl_gene = eo.ortholog_ensembl_gene "
        "WHERE eo.human_uniprot_acc = ? "
        "  AND eo.ortholog_ecd_version = ? "
        "ORDER BY eo.species ASC",
        [topology_version, uniprot_acc, ortholog_ecd_version],
    )
    mouse: list[OrthologEntry] = []
    cyno: list[OrthologEntry] = []
    for r in rows:
        species = (r.get("species") or "").lower()
        ecd_raw = r.get("ecd_pct_identity")
        full_raw = r.get("full_length_pct_identity")
        per_res = r.get("per_residue_topology")
        label = r.get("deeptmhmm_label")
        ortholog_seq = r.get("ortholog_sequence")
        try:
            ecd_pct = float(ecd_raw) if ecd_raw is not None else None
            full_pct = float(full_raw) if full_raw is not None else None
            # Default to the raw DeepTMHMM-on-ortholog values…
            topo: str | None = str(per_res) if per_res is not None else None
            tm_count = int(r.get("tm_helix_count") or 0)
            ecd_len = int(r.get("ecd_length_residues") or 0)
            proj_source: str | None = None
            tm_absent = False
            n_absent = 0
            # …then override with the human canonical topology projected onto
            # this ortholog when both sequences are available. Restores the
            # conserved topology on truncated / padded ortholog models (esp.
            # cyno TrEMBL); falls back to the raw values when projection
            # returns None (no human ECD/topology, empty ortholog sequence).
            if human_topology and human_sequence and ortholog_seq:
                projected = project_human_topology_onto_ortholog(
                    human_topology=human_topology,
                    human_sequence=human_sequence,
                    ortholog_sequence=str(ortholog_seq),
                )
                if projected is not None:
                    topo = projected.per_residue_topology
                    tm_count = projected.tm_helix_count
                    ecd_len = projected.ecd_length_residues
                    tm_absent = projected.tm_absent_from_model
                    n_absent = projected.n_tm_regions_absent
                    proj_source = projected.source
            entry = OrthologEntry(
                is_canonical=True,
                isoform_id=r.get("ortholog_uniprot_acc") or "",
                ensembl_id=r.get("ortholog_ensembl_gene") or "",
                ortholog_uniprot_acc=r.get("ortholog_uniprot_acc") or "",
                ortholog_symbol=r.get("ortholog_gene_symbol") or "",
                type="one2one",
                ecd_pct_identity_to_human_canonical=ecd_pct,
                # Similarity not yet wired — mirror identity when present.
                ecd_pct_similarity_to_human_canonical=ecd_pct,
                full_length_pct_identity_to_human_canonical=full_pct,
                ecd_length_residues=ecd_len,
                tm_helix_count=tm_count,
                compara_version=r.get("compara_release") or "",
                retrieved_at=datetime.now(UTC),
                per_residue_topology=topo,
                deeptmhmm_label=str(label) if label is not None else None,
                topology_projection_source=proj_source,
                tm_absent_from_model=tm_absent,
                n_tm_regions_absent=n_absent,
                sequence=str(ortholog_seq) if ortholog_seq else None,
            )
        except (TypeError, ValueError) as exc:
            logger.warning(
                "skipping malformed ortholog row for %s: %s (%s)",
                uniprot_acc, r, exc,
            )
            continue
        if species == "mouse":
            mouse.append(entry)
        elif species in ("cynomolgus", "cyno"):
            cyno.append(entry)
    # checked=True: this function only runs when the ortholog versions resolved,
    # so an empty result is a genuine "no one2one ortholog", not "not checked".
    return Orthologs(mouse=mouse, cynomolgus=cyno, checked=True)


def _stub_structure(uniprot_acc: str) -> StructureFeatures:
    """AlphaFold DB pLDDT extraction is not yet wired into this pipeline.

    Returns a schema-valid placeholder with ``source`` labeled explicitly
    so a downstream consumer (viewer card, agent prompt) can tell the
    difference between "we haven't measured it yet" and "we measured zero".
    """
    return StructureFeatures(
        # Placeholders track LATEST_KNOWN_AFDB_VERSION (viewer/lib/
        # structure-viewer-types.ts). Bumped v4 → v6 in 2025-08 when
        # v1–v5 retired from the AFDB file server. When the real
        # fetcher runs these get overwritten; the cosmetic default
        # just shouldn't lie.
        afdb_id=f"AF-{uniprot_acc}-F1-model_v6",
        afdb_version="v6",
        ecd_mean_plddt=0.0,
        ecd_disordered_fraction=0.0,
        source="AlphaFold DB (placeholder — pLDDT fetcher not yet wired)",
        license="CC BY 4.0",
        attribution="© DeepMind / EMBL-EBI",
        citations=["10.1038/s41586-021-03819-2", "10.1093/nar/gkad1011"],
    )


def _parse_iso(s: str | None) -> datetime:
    """Parse a SQLite-stored ISO-8601 timestamp; falls back to now()."""
    if not s:
        return datetime.now(UTC)
    s = s.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return datetime.now(UTC)


def _coerce_orientation(s: str | None) -> TerminalOrientation:
    """Map DB orientation strings onto the TerminalOrientation Literal.

    The schema only allows ``extracellular`` / ``cytoplasmic``. The DB
    additionally carries ``indeterminate`` for 2 of 20,102 rows (GLOB
    proteins where neither end is membrane-resident — DeepTMHMM has no
    clear side call). Map those + NULL to ``cytoplasmic`` (the
    conservative default for soluble / non-membrane proteins).
    """
    if s == "extracellular":
        return "extracellular"
    return "cytoplasmic"


# ---------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------

def fetch_deterministic_features(uniprot_acc: str) -> DeterministicFeatures:
    """Assemble the orchestrator's ``DeterministicFeatures`` from public D1.

    Always returns a schema-valid model:
      * Canonical topology — real data if a row exists in
        ``topology_public``; otherwise a labeled placeholder so the
        record still validates.
      * Isoform topologies — empty list if the human_isoforms cohort
        wasn't run for this gene.
      * Orthologs — real mouse + cyno entries where ``compara_ortholog_ecd``
        has a row; empty species lists otherwise.
      * Paralogs — top-50 by ECD identity rank.
      * Structure — labeled placeholder (AFDB fetcher pending).

    The DB-fetched fields override every previous stub; the
    ``tool_version`` on the canonical topology carries the real
    ``deeptmhmm-1.0.24`` tag from the upload (or whatever version the
    sweep was run against).
    """
    # Per-cohort version resolution — each cohort's JOIN target may
    # live under a different topology_version when sweeps are run
    # partially (e.g. an isoforms-only refresh that doesn't re-run
    # human_canonical or the ortholog cohorts). `_latest_topology_version`
    # returned the newest release entry regardless of which cohort it
    # carried — that silently nulled paralog/ortholog topology fields
    # after the 2026-05-25 isoforms-only sweep. The per-cohort variant
    # picks the right version for each fetcher's JOIN.
    canonical_topo_version = _latest_topology_version_for_cohort("human_canonical")
    isoform_topo_version = _latest_topology_version_for_cohort("human_isoforms")
    mouse_topo_version = _latest_topology_version_for_cohort("mouse_ortholog")
    paralog_version = _latest_paralog_version()
    ortholog_ecd_version = _latest_ortholog_ecd_version()
    if not canonical_topo_version:
        logger.warning(
            "no human_canonical rows in topology_public; falling back to "
            "placeholder for %s",
            uniprot_acc,
        )
    canonical = _fetch_canonical_topology(uniprot_acc, canonical_topo_version) if canonical_topo_version else None
    if canonical is None:
        # Schema requires a canonical_topology; emit a clearly-labeled
        # placeholder. Examples of when this fires: the 3 length-skipped
        # giants (Q7Z5P9, Q8NF91, Q9H195), or any acc not in this sweep's
        # cohort.
        logger.warning(
            "no canonical topology row in D1 for %s; using placeholder",
            uniprot_acc,
        )
        canonical = IsoformTopology(
            isoform_id=f"{uniprot_acc}-1",
            uniprot_acc=uniprot_acc,
            tm_helix_count=0,
            n_terminal_orientation="cytoplasmic",
            c_terminal_orientation="cytoplasmic",
            signal_peptide_length=0,
            ecd_length_residues=0,
            icd_length_residues=0,
            per_residue_topology="",
            tool_version="placeholder-no-d1-row",
            retrieved_at=datetime.now(UTC),
        )
    # Per-cohort version threading — see the comment block above where
    # the cohort-specific versions are resolved. Isoforms JOIN against
    # human_isoforms (newest sweep), paralogs JOIN against
    # human_canonical (which the paralog uniprots live under), orthologs
    # JOIN against mouse_ortholog / cyno_ortholog (which share a version
    # in practice — mouse_topo_version covers both).
    # Canonical sequence, fetched once and reused by two callers:
    #   * isoform %identity (_fetch_isoform_topologies), and
    #   * projecting the canonical topology onto each ortholog
    #     (_fetch_orthologs via merge.ortholog_topology_projection).
    # It lives under the canonical cohort's version, which can differ from
    # the isoforms / ortholog cohort versions after a partial sweep.
    canonical_sequence = (
        _fetch_canonical_sequence(uniprot_acc, canonical_topo_version)
        if canonical_topo_version else ""
    )
    # Pair the canonical sequence onto the topology it indexes (1:1 length).
    # The placeholder-canonical path (no D1 row) leaves it None.
    if canonical_sequence and not canonical.sequence:
        canonical.sequence = canonical_sequence
    isoforms = (
        _fetch_isoform_topologies(
            uniprot_acc,
            isoform_topo_version,
            canonical_topology=canonical.per_residue_topology,
            canonical_sequence=canonical_sequence,
        )
        if isoform_topo_version else []
    )
    orthologs = (
        _fetch_orthologs(
            uniprot_acc,
            topology_version=mouse_topo_version,
            ortholog_ecd_version=ortholog_ecd_version,
            human_topology=canonical.per_residue_topology or "",
            human_sequence=canonical_sequence,
        )
        if mouse_topo_version and ortholog_ecd_version
        else Orthologs()
    )
    paralogs = (
        _fetch_paralogs(
            uniprot_acc, paralog_version, topology_version=canonical_topo_version
        )
        if paralog_version else []
    )
    # Pull real AFDB pLDDT — ECD-restricted when the canonical isoform
    # has a per-residue topology with extracellular residues, otherwise
    # falls back to the whole-protein metric with a labeled source so
    # downstream readers don't conflate it with the ECD-restricted
    # measurement. ``fetch_afdb_plddt`` never raises — on network /
    # parse failure it returns its own labeled placeholder.
    from accessible_surfaceome.tools.afdb_plddt import (
        fetch_afdb_plddt,
        read_afdb_model_links,
    )
    from accessible_surfaceome.tools.surface_bind import lookup as lookup_surface_bind

    structure = fetch_afdb_plddt(
        uniprot_acc,
        per_residue_topology=canonical.per_residue_topology or None,
    )
    # Enrich with the AFDB model download links (cache warm from the fetch
    # above) + the representative experimental (PDB) structure from PDBe
    # SIFTS. Both are best-effort — None/empty on failure, leaving the
    # corresponding fields unset rather than failing the record.
    _links = read_afdb_model_links(uniprot_acc)
    structure.model_cif_url = _links["model_cif_url"]
    structure.model_pdb_url = _links["model_pdb_url"]
    structure.model_pae_url = _links["model_pae_url"]
    # The representative experimental (PDB) structure pointer lives under
    # ``surface_bind.representative_structure`` (see PR #54). The v1
    # loader doesn't populate that side here; SURFACE-Bind's own loader
    # fills it from PDBe SIFTS at lookup time.

    # SURFACE-Bind summary — in-memory lookup against the checked-in
    # JSON ``data/external/surface_bind/surface_bind_summary.json``.
    # ``has_data=False`` is the explicit "not scored" signal for the
    # ~12% of surfaceome proteins SURFACE-Bind omitted.
    surface_bind = lookup_surface_bind(uniprot_acc)

    # Schweke 2024 homo-oligomer prediction (PMID 38325366). Tries the
    # public D1 ``schweke_homomer`` table first; falls back to the small
    # viewer manifest (8 sample entries) while D1 is being populated;
    # default is ``is_homo_oligomer=False`` for everything else. Positives-
    # only refset, so False is "not in Schweke's positives" not "AF2
    # disagrees" — the synthesizer treats this as a lower-bound prior.
    from accessible_surfaceome.tools.schweke_homomer import lookup as lookup_schweke
    homo_oligomerization = lookup_schweke(uniprot_acc)

    return DeterministicFeatures(
        canonical_topology=canonical,
        isoform_topologies=isoforms,
        orthologs=orthologs,
        paralogs=paralogs,
        # checked=True only when the cohort's version resolved (we actually
        # queried D1); an empty list under a resolved version is a genuine
        # singleton / single-isoform gene, not an un-run sweep.
        paralogs_checked=bool(paralog_version),
        isoform_topologies_checked=bool(isoform_topo_version),
        structure=structure,
        surface_bind=surface_bind,
        homo_oligomerization=homo_oligomerization,
    )
