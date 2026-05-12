"""``gene_lookup`` — identifier resolution, DB-vote panel, UniProt summary,
candidate-universe miss diagnosis. Four modes, one tool, called by the agent
through the Managed Agents custom-tool protocol.

Progressive-disclosure discipline:

* The four modes are themselves a disclosure ladder. ``resolve`` (~300 tok)
  anchors identifiers; ``db_panel`` (~400 tok) gives the M1 verdict;
  ``uniprot_summary`` (~500 tok) gives the canonical biology; ``miss_diagnosis``
  (~400 tok) is only useful when a control gene was *missed*. The agent picks
  the next rung; we never collapse them into a single "give me everything" call.
* Within each mode, return compact-by-default. Lists are capped, prose is
  truncated. The agent re-calls a narrower mode (or, for full text, escalates
  to ``gene_literature.fetch_fulltext``) when it needs more.
* Caches (UniProt, HGNC, NCBI) are aggressive so escalation is cheap.

See ``docs/tools-design.md`` for the protocol and ``docs/plans/2026-04-16-
surface-proteome-annotation.md`` for the surrounding annotation pipeline.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Literal

import httpx
import pandas as pd

from accessible_surfaceome.paths import DATA_PROCESSED_DIR

from ._shared.http import CachedHTTP, open_default_client
from ._shared.models import (
    AliasCollisionRisk,
    CrossReference,
    DBVotePanel,
    IdentifierBundle,
    IsoformRecord,
    MissDiagnosis,
    PTMRecord,
    PublicationStub,
    SourceName,
    SourceRuleResult,
    SourceVote,
    SubcellularLocation,
    SubcellularReliability,
    TopologyFeature,
    UniProtStatus,
    UniProtSummary,
)

Mode = Literal["resolve", "db_panel", "uniprot_summary", "miss_diagnosis"]

# Caps that enforce the compact-by-default disclosure budget. The agent escalates
# by calling a narrower mode (uniprot_summary → gene_literature.fetch_abstract)
# rather than asking us to inflate any one return.
_MAX_TOP_PUBLICATIONS = 5
_MAX_CROSS_REFERENCES = 12
_MAX_PTMS = 20
_MAX_SUBCELLULAR_LOCATIONS = 12
_MAX_TOPOLOGY_FEATURES = 30
_MAX_ISOFORMS = 8
_FUNCTION_TEXT_CHARS = 800
_TISSUE_TEXT_CHARS = 600
_NCBI_SUMMARY_CHARS = 600

_XrefKind = Literal["pdb", "interpro", "pfam", "antibodypedia", "alphafold", "ensembl", "other"]

# Whitelisted cross-reference databases — surface biology decisions hinge on
# these; the rest of UniProt's xref list is deliberately dropped.
_KEEP_XREF_DBS: dict[str, _XrefKind] = {
    "PDB": "pdb",
    "InterPro": "interpro",
    "Pfam": "pfam",
    "Antibodypedia": "antibodypedia",
    "AlphaFoldDB": "alphafold",
    "Ensembl": "ensembl",
}

_UNIPROT_ACC_RE = re.compile(r"^[OPQ][0-9][A-Z0-9]{3}[0-9]$|^[A-NR-Z][0-9](?:[A-Z][A-Z0-9]{2}[0-9]){1,2}$")

_TTL = {
    "uniprot": 30,
    "hgnc": 90,
    "ncbi": 30,
    "open_targets": 30,
}


def looks_like_uniprot_acc(text: str) -> bool:
    return bool(_UNIPROT_ACC_RE.match(text.strip()))


# ---------------------------------------------------------------------------
# Public entry: dispatches by mode. Used by the orchestrator's tool registry.
# ---------------------------------------------------------------------------


def gene_lookup(
    *,
    mode: Mode,
    symbol_or_acc: str,
    http: CachedHTTP | None = None,
) -> IdentifierBundle | DBVotePanel | UniProtSummary | MissDiagnosis:
    """Single-entry dispatcher mirroring the registered tool schema.

    Construction of ``CachedHTTP`` is hidden by default for one-off scripts.
    Long-lived processes (orchestrator, batch jobs) should pass an explicit
    client so cache + connection pool are reused across calls.
    """

    own_client = http is None
    client = http or open_default_client()
    try:
        if mode == "resolve":
            return resolve(symbol_or_acc, http=client)
        # Tools-design.md says the agent should call ``resolve`` first to get the
        # acc, but accepting either keeps the tool robust to off-script use and
        # the cache means the implicit resolve is free on the second call.
        acc = _ensure_acc(symbol_or_acc, http=client)
        if mode == "db_panel":
            return db_panel(acc, http=client)
        if mode == "uniprot_summary":
            return uniprot_summary(acc, http=client)
        if mode == "miss_diagnosis":
            return miss_diagnosis(acc, http=client)
        raise ValueError(f"unknown mode: {mode!r}")
    finally:
        if own_client:
            client.close()


def _ensure_acc(symbol_or_acc: str, *, http: CachedHTTP) -> str:
    text = symbol_or_acc.strip()
    if looks_like_uniprot_acc(text):
        return text.upper()
    acc = _uniprot_search_by_symbol(text, http=http)
    if acc is None:
        raise LookupError(
            f"no reviewed human UniProt accession for symbol {symbol_or_acc!r} — out of study scope"
        )
    return acc


# ---------------------------------------------------------------------------
# resolve
# ---------------------------------------------------------------------------


def resolve(symbol_or_acc: str, *, http: CachedHTTP) -> IdentifierBundle:
    """Resolve a symbol or accession into a canonical identifier bundle.

    UniProt is the study's primary identifier. If we can't reach a reviewed
    human UniProt accession from the input, we raise — the gene is out of scope
    rather than a record with a null acc.
    """

    # The UniProt-accession regex is structurally permissive — it accepts
    # any string of the right shape, so gene symbols that happen to match
    # the pattern (P2RY10-14, B3GNT3-9, H2BC12, etc.) get misrouted to the
    # accession path and 404 on UniProt. When the accession lookup 404s,
    # fall back to the symbol search before giving up.
    raw = symbol_or_acc.strip()
    if looks_like_uniprot_acc(raw):
        uniprot_acc = raw.upper()
        try:
            entry = _uniprot_entry(uniprot_acc, http=http)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 404:
                raise
            # Coincidental regex match — try symbol search instead.
            uniprot_acc = _uniprot_search_by_symbol(raw, http=http)
            if uniprot_acc is None:
                raise LookupError(
                    f"no reviewed human UniProt accession for symbol {symbol_or_acc!r} — "
                    "out of study scope (initial accession-shape lookup 404'd, "
                    "symbol search also failed)"
                )
            entry = _uniprot_entry(uniprot_acc, http=http)
    else:
        uniprot_acc = _uniprot_search_by_symbol(raw, http=http)
        if uniprot_acc is None:
            # UniProt's symbol search misses newly-registered HGNC
            # entries whose gene_name field hasn't propagated to
            # UniProt's index yet (SACK1A-H series, MIMS1/2, MISO1,
            # ZBED8L/11, etc. — confirmed against HGNC 2026-05). HGNC
            # carries an explicit ``uniprot_ids`` cross-reference for
            # these; consult it before giving up.
            hgnc_xref = _hgnc_record(raw, http=http) or {}
            xref_ids = hgnc_xref.get("uniprot_ids") or []
            if xref_ids:
                uniprot_acc = xref_ids[0]
            else:
                raise LookupError(
                    f"no reviewed human UniProt accession for symbol {symbol_or_acc!r} — out of study scope"
                )
        entry = _uniprot_entry(uniprot_acc, http=http)
    status, merged_into = _entry_status(entry)

    primary_symbol = _entry_primary_symbol(entry) or symbol_or_acc.strip()
    xrefs = _index_xrefs(entry)
    ensembl_canonical_protein = _ensembl_canonical_protein(entry)

    # HGNC is the canonical mapper from symbol → entrez_id / ensembl_gene_id.
    # UniProt's GeneID/Ensembl xrefs are sometimes stripped (e.g. KAAG1's
    # uniprot_obsolete-flagged entry has neither), so we pin off HGNC instead.
    hgnc = _hgnc_record(primary_symbol, http=http) or {}
    hgnc_id = hgnc.get("hgnc_id") or (xrefs.get("HGNC") or [""])[0]
    approved_name = hgnc.get("name")
    hgnc_aliases = list(hgnc.get("alias_symbol") or [])
    alias_names = list(hgnc.get("alias_name") or [])
    previous_symbols = list(hgnc.get("prev_symbol") or [])
    previous_names = list(hgnc.get("prev_name") or [])
    hgnc_gene_groups = list(hgnc.get("gene_group") or [])
    cd_designation_raw = hgnc.get("cd")
    cd_designation = cd_designation_raw if isinstance(cd_designation_raw, str) and cd_designation_raw else None
    entrez_id_raw = hgnc.get("entrez_id")
    ensembl_gene = hgnc.get("ensembl_gene_id")
    ncbi_gene_id = int(entrez_id_raw) if entrez_id_raw else None

    ncbi = _ncbi_gene_summary(ncbi_gene_id, http=http) if ncbi_gene_id else None
    ncbi_aliases = _parse_ncbi_aliases(ncbi)
    aliases = _merge_aliases(
        current=hgnc_aliases,
        extras=[ncbi_aliases],
        exclude={primary_symbol, *previous_symbols},
    )

    sequence_block = entry.get("sequence") or {}
    length_aa = sequence_block.get("length")
    isoform_count = _entry_isoform_count(entry)
    alias_collision_risk = _alias_collision_risk(primary_symbol, aliases, previous_symbols, http=http)
    ncbi_summary = _truncate(ncbi.get("summary") if ncbi else None, _NCBI_SUMMARY_CHARS)

    return IdentifierBundle(
        hgnc_symbol=primary_symbol,
        hgnc_id=hgnc_id,
        approved_name=approved_name,
        aliases=aliases,
        alias_names=alias_names,
        previous_symbols=previous_symbols,
        previous_names=previous_names,
        hgnc_gene_groups=hgnc_gene_groups,
        cd_designation=cd_designation,
        uniprot_acc=uniprot_acc,
        uniprot_status=status,
        uniprot_merged_into=merged_into,
        ncbi_gene_id=ncbi_gene_id,
        ensembl_gene=ensembl_gene,
        ensembl_canonical_protein=ensembl_canonical_protein,
        length_aa=length_aa,
        isoform_count=isoform_count,
        alias_collision_risk=alias_collision_risk,
        open_targets_status=None,  # add when an OT call lands; deliberately deferred for v0
        ncbi_summary=ncbi_summary,
    )


# ---------------------------------------------------------------------------
# db_panel
# ---------------------------------------------------------------------------

_DB_SOURCES: dict[SourceName, tuple[str, list[str]]] = {
    # source → (flag column, evidence columns to include from candidate_universe.tsv)
    "surfy": ("surfy_surface_flag", ["surfy_almen_class", "surfy_signal_peptide", "surfy_tm_count"]),
    "cspa": ("cspa_surface_flag", ["cspa_n_high", "cspa_n_putative"]),
    "uniprot_query": (
        "uniprot_surface_flag",
        ["uniprot_subcellular_location_text", "uniprot_topology_features"],
    ),
    "go": ("go_surface_flag", ["go_evidence_codes", "go_terms"]),
    "hpa": ("hpa_surface_flag", ["hpa_main_location", "hpa_reliability_subcell"]),
    "deeptmhmm": ("deeptmhmm_surface_flag", ["deeptmhmm_topology"]),
    "compartments": (
        "compartments_surface_flag",
        ["compartments_predictions_stars_max", "compartments_knowledge_stars_max"],
    ),
}


def _candidate_universe_path() -> Path:
    return DATA_PROCESSED_DIR / "candidate_universe" / "candidate_universe.tsv"


def _zero_support_path() -> Path:
    return DATA_PROCESSED_DIR / "candidate_universe" / "candidate_universe_zero_support.tsv"


_PATENT_NUMBER_RE = re.compile(r"\b(?:WO|EP|US)\d{4,}[A-Z]?\d*\b")


def _str_or_empty(value: Any) -> str:
    """Coerce a pandas cell value to a string. NaN floats and None → ""."""

    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    return str(value)


def _controls_panel_path() -> Path:
    return DATA_PROCESSED_DIR / "controls" / "surfaceome_control_panel.tsv"


# Module-level cache so we don't re-read the controls TSV on every db_panel call.
_PATENT_HANDLES_CACHE: dict[str, dict[str, list[dict[str, Any]]]] | None = None


def _load_patent_handles() -> dict[str, dict[str, list[dict[str, Any]]]]:
    """Lazy-load the patent-handle lookup tables.

    Returns ``{"by_acc": {acc: [records]}, "by_symbol": {SYMBOL: [records]}}``
    where each record carries ``{"gene_symbol", "uniprot_id", "wo_numbers",
    "source_note"}``. ``by_symbol`` is keyed in uppercase for case-insensitive
    matching.
    """

    global _PATENT_HANDLES_CACHE
    if _PATENT_HANDLES_CACHE is not None:
        return _PATENT_HANDLES_CACHE

    path = _controls_panel_path()
    by_acc: dict[str, list[dict[str, Any]]] = {}
    by_symbol: dict[str, list[dict[str, Any]]] = {}
    if path.exists():
        # ``keep_default_na=False`` keeps NaN out of string cells (otherwise
        # pandas serves a float, breaking ``.strip()`` etc.). Empty strings
        # are what we actually want to mean "no value".
        df = pd.read_csv(path, sep="\t", dtype=str, keep_default_na=False, na_values=[""])
        if "control_group" in df.columns:
            handles = df.loc[df["control_group"] == "patent_delivery_handles"]
            for _, row in handles.iterrows():
                note = _str_or_empty(row.get("source_note"))
                wo_numbers = sorted(set(_PATENT_NUMBER_RE.findall(note)))
                acc = _str_or_empty(row.get("uniprot_id")).strip()
                symbol_raw = _str_or_empty(row.get("gene_symbol")).strip()
                record = {
                    "gene_symbol": symbol_raw,
                    "uniprot_id": acc,
                    "wo_numbers": wo_numbers,
                    "source_note": note,
                }
                if acc:
                    by_acc.setdefault(acc, []).append(record)
                if symbol_raw:
                    by_symbol.setdefault(symbol_raw.upper(), []).append(record)
    _PATENT_HANDLES_CACHE = {"by_acc": by_acc, "by_symbol": by_symbol}
    return _PATENT_HANDLES_CACHE


def _patent_handle_records(*, uniprot_acc: str, hgnc_symbol: str) -> list[dict[str, Any]]:
    handles = _load_patent_handles()
    out = list(handles["by_acc"].get(uniprot_acc, []))
    if not out and hgnc_symbol:
        out = list(handles["by_symbol"].get(hgnc_symbol.upper(), []))
    return out


def _load_universe_row(uniprot_acc: str) -> tuple[pd.Series | None, str]:
    """Return (row, where) for the given accession.

    ``where`` is one of "universe", "zero_support", "absent".
    """

    for path, where in [
        (_candidate_universe_path(), "universe"),
        (_zero_support_path(), "zero_support"),
    ]:
        if not path.exists():
            continue
        df = pd.read_csv(path, sep="\t", dtype=str)
        if "uniprot_accession" not in df.columns:
            continue
        match = df.loc[df["uniprot_accession"] == uniprot_acc]
        if not match.empty:
            return match.iloc[0], where
    return None, "absent"


def db_panel(uniprot_acc: str, *, http: CachedHTTP) -> DBVotePanel:
    row, _where = _load_universe_row(uniprot_acc)

    # Resolve the gene symbol so the patent-handle lookup can fall back to it
    # when the controls TSV row has an empty uniprot_id (KAAG1 is the canonical
    # example). UniProt entry is already cached → effectively free.
    hgnc_symbol = ""
    if row is not None:
        hgnc_symbol = row.get("gene_symbol_resolved") or row.get("gene_symbol") or ""
    if not hgnc_symbol:
        try:
            entry = _uniprot_entry(uniprot_acc, http=http)
            hgnc_symbol = _entry_primary_symbol(entry) or ""
        except Exception:
            hgnc_symbol = ""

    patent_records = _patent_handle_records(uniprot_acc=uniprot_acc, hgnc_symbol=hgnc_symbol)

    sources: list[SourceVote] = []
    n_voting = 0
    in_db_union = False

    if row is not None:
        for source_name, (flag_col, evidence_cols) in _DB_SOURCES.items():
            vote = _truthy_flag(row.get(flag_col))
            if vote:
                n_voting += 1
            evidence = {
                col: row.get(col) for col in evidence_cols if row.get(col) not in (None, "", "nan")
            }
            sources.append(SourceVote(source=source_name, vote=vote, evidence=evidence))
        in_db_union = _truthy_flag(row.get("in_db_union"))
    else:
        # Not in candidate_universe.tsv or zero_support — every M1 source misses.
        for source_name in _DB_SOURCES:
            sources.append(SourceVote(source=source_name, vote=False))

    patent_vote = bool(patent_records)
    patent_evidence: dict[str, Any] = {}
    if patent_records:
        wo_numbers: list[str] = []
        notes: list[str] = []
        for rec in patent_records:
            wo_numbers.extend(rec.get("wo_numbers", []))
            if rec.get("source_note"):
                notes.append(rec["source_note"])
        # Dedupe WO numbers preserving order
        seen: set[str] = set()
        wo_numbers = [w for w in wo_numbers if not (w in seen or seen.add(w))]
        patent_evidence = {
            "wo_numbers": wo_numbers,
            "source_notes": notes,
            "n_records": len(patent_records),
        }
    sources.append(
        SourceVote(source="patent_handle", vote=patent_vote, evidence=patent_evidence)
    )

    return DBVotePanel(
        hgnc_symbol=hgnc_symbol,
        uniprot_acc=uniprot_acc,
        sources=sources,
        n_sources_voting_surface=n_voting,
        in_db_union=in_db_union,
        in_patent_handles=patent_vote,
    )


# ---------------------------------------------------------------------------
# uniprot_summary
# ---------------------------------------------------------------------------


def uniprot_summary(uniprot_acc: str, *, http: CachedHTTP) -> UniProtSummary:
    entry = _uniprot_entry(uniprot_acc, http=http)
    return _distill_uniprot_entry(uniprot_acc, entry)


def _distill_uniprot_entry(uniprot_acc: str, entry: dict[str, Any]) -> UniProtSummary:
    entry_name = entry.get("uniProtkbId")
    protein_name = (
        ((entry.get("proteinDescription") or {}).get("recommendedName") or {}).get("fullName") or {}
    ).get("value")

    subcellular_locations = _extract_subcellular_locations(entry)
    topology_features = _extract_topology_features(entry)
    ptms = _extract_ptms(entry)
    function_text = _truncate(_first_comment_text(entry, "FUNCTION"), _FUNCTION_TEXT_CHARS)
    tissue_text = _truncate(_first_comment_text(entry, "TISSUE SPECIFICITY"), _TISSUE_TEXT_CHARS)
    isoforms = _extract_isoforms(entry)
    n_publications, top_publications = _extract_publications(entry)
    cross_references = _extract_cross_references(entry)

    return UniProtSummary(
        uniprot_acc=uniprot_acc,
        entry_name=entry_name,
        protein_name=protein_name,
        subcellular_locations=subcellular_locations[:_MAX_SUBCELLULAR_LOCATIONS],
        topology_features=topology_features[:_MAX_TOPOLOGY_FEATURES],
        ptms=ptms[:_MAX_PTMS],
        function_text=function_text,
        tissue_specificity_text=tissue_text,
        isoforms=isoforms[:_MAX_ISOFORMS],
        n_publications=n_publications,
        top_publications=top_publications[:_MAX_TOP_PUBLICATIONS],
        cross_references=cross_references[:_MAX_CROSS_REFERENCES],
    )


# ---------------------------------------------------------------------------
# miss_diagnosis
# ---------------------------------------------------------------------------


_MISS_RULE_EXPLANATIONS: dict[SourceName, str] = {
    "uniprot_query": (
        "UniProt-query rule fires when the entry has at least one subcellular-location "
        "term in the surface set OR a Topological domain feature labelled Extracellular."
    ),
    "go": (
        "GO rule fires on any non-IEA annotation to GO:0009986 (cell surface), "
        "GO:0009897 (external side of plasma membrane), or GO:0005887 (integral component "
        "of plasma membrane), including descendants via is_a + part_of closure."
    ),
    "surfy": "SURFY rule fires when the SURFY ML class predicts surface (surfy_is_surface == 1).",
    "cspa": "CSPA rule fires when the protein appears in the Wollscheid mass-spec surfaceome.",
    "hpa": (
        "HPA rule fires when the entry has Plasma membrane or Cell Junctions main-location "
        "with at least Approved reliability."
    ),
    "deeptmhmm": (
        "DeepTMHMM rule fires when the predicted topology has ≥1 transmembrane helix and "
        "an extracellular segment. Note: DeepTMHMM was run on a 22.8% subset; absence ≠ negative."
    ),
    "compartments": (
        "JensenLab COMPARTMENTS rule fires when max(experiments_stars, textmining_stars) ≥ 3 "
        "for any term in the surface-term set."
    ),
    "patent_handle": "Patent-handle lane fires when the gene is cited as a delivery target in our patent corpus.",
}


def miss_diagnosis(uniprot_acc: str, *, http: CachedHTTP) -> MissDiagnosis:
    row, where = _load_universe_row(uniprot_acc)
    in_universe = where == "universe"

    # Resolve the symbol so we can fall back to the patent-handle by-symbol
    # lookup when the controls TSV row has an empty uniprot_id.
    hgnc_symbol = ""
    if row is not None:
        hgnc_symbol = row.get("gene_symbol_resolved") or row.get("gene_symbol") or ""
    if not hgnc_symbol:
        try:
            entry = _uniprot_entry(uniprot_acc, http=http)
            hgnc_symbol = _entry_primary_symbol(entry) or ""
        except Exception:
            hgnc_symbol = ""

    patent_records = _patent_handle_records(uniprot_acc=uniprot_acc, hgnc_symbol=hgnc_symbol)
    patent_fired = bool(patent_records)
    patent_missing = [] if patent_fired else ["no patent-handle record for this accession or symbol"]
    patent_wo_numbers: list[str] = []
    for rec in patent_records:
        patent_wo_numbers.extend(rec.get("wo_numbers", []))

    per_source: list[SourceRuleResult] = []
    candidate_lanes: list[str] = []

    if row is None:
        if patent_fired:
            summary = (
                f"{uniprot_acc} ({hgnc_symbol or '?'}) is not in candidate_universe.tsv or "
                f"zero_support, but IS listed in the patent-delivery-handle lane "
                f"({', '.join(patent_wo_numbers) or 'unspecified WO'}). This is the "
                f"canonical out-of-conventional-sources case (e.g. KAAG1 / RU2AS); follow "
                f"up with patent_lookup for the disclosure details."
            )
            candidate_lanes.append("patent_handle")
        else:
            summary = (
                f"{uniprot_acc} is not present in candidate_universe.tsv, zero_support, or "
                f"the patent-handle lane. Check that the accession is reviewed and human, "
                f"and that the M1 build has been re-run since the accession was added."
            )
        for source_name, explanation in _MISS_RULE_EXPLANATIONS.items():
            per_source.append(
                SourceRuleResult(
                    source=source_name,
                    rule_fired=False,
                    missing_features=["accession not in any source's processed snapshot"],
                    rule_explanation=explanation,
                )
            )
        per_source.append(
            SourceRuleResult(
                source="patent_handle",
                rule_fired=patent_fired,
                missing_features=patent_missing,
                rule_explanation=_MISS_RULE_EXPLANATIONS["patent_handle"]
                + (f" Found WO numbers: {', '.join(patent_wo_numbers)}." if patent_fired else ""),
            )
        )
        return MissDiagnosis(
            hgnc_symbol=hgnc_symbol,
            uniprot_acc=uniprot_acc,
            in_candidate_universe=False,
            per_source=per_source,
            candidate_lanes=candidate_lanes,
            summary=summary,
        )

    for source_name, (flag_col, evidence_cols) in _DB_SOURCES.items():
        vote = _truthy_flag(row.get(flag_col))
        missing = []
        if not vote:
            for col in evidence_cols:
                value = row.get(col)
                if value in (None, "", "nan"):
                    missing.append(f"{col}: empty")
        per_source.append(
            SourceRuleResult(
                source=source_name,
                rule_fired=vote,
                missing_features=missing,
                rule_explanation=_MISS_RULE_EXPLANATIONS[source_name],
            )
        )
    per_source.append(
        SourceRuleResult(
            source="patent_handle",
            rule_fired=patent_fired,
            missing_features=patent_missing,
            rule_explanation=_MISS_RULE_EXPLANATIONS["patent_handle"]
            + (f" Found WO numbers: {', '.join(patent_wo_numbers)}." if patent_fired else ""),
        )
    )

    if in_universe:
        summary = (
            f"{uniprot_acc} IS in the candidate universe (in_db_union=1, "
            f"n_sources_surface={row.get('n_sources_surface', '?')}). "
            f"miss_diagnosis is not the right tool here — call db_panel for the per-source vote summary."
        )
    else:
        summary = (
            f"{uniprot_acc} is in zero-support (no surface rule fired). "
            f"Common reasons: only-IEA GO annotations; intracellular UniProt subcellular-location calls; "
            f"absent from SURFY/CSPA mass-spec snapshots; HPA below approved reliability."
        )
        if patent_fired:
            summary += f" PATENT HANDLE: {', '.join(patent_wo_numbers)} — call patent_lookup."
            candidate_lanes.append("patent_handle")
        else:
            summary += " If this is a known surface gene, check the MHC-presentation edge case."
            candidate_lanes.append("mhc_presentation_edge_case")

    return MissDiagnosis(
        hgnc_symbol=hgnc_symbol,
        uniprot_acc=uniprot_acc,
        in_candidate_universe=in_universe,
        per_source=per_source,
        candidate_lanes=candidate_lanes,
        summary=summary,
    )


# ---------------------------------------------------------------------------
# UniProt helpers
# ---------------------------------------------------------------------------


def _uniprot_entry(acc: str, *, http: CachedHTTP) -> dict[str, Any]:
    url = f"https://rest.uniprot.org/uniprotkb/{acc}.json"
    return http.get_json(url, source="uniprot", ttl_days=_TTL["uniprot"])


def _uniprot_search_by_symbol(symbol: str, *, http: CachedHTTP) -> str | None:
    url = "https://rest.uniprot.org/uniprotkb/search"
    params = {
        "query": f"gene_exact:{symbol} AND organism_id:9606 AND reviewed:true",
        "fields": "accession",
        "format": "json",
        "size": "1",
    }
    payload = http.get_json(url, source="uniprot", ttl_days=_TTL["uniprot"], params=params)
    results = (payload or {}).get("results") or []
    return results[0]["primaryAccession"] if results else None


def _entry_status(entry: dict[str, Any]) -> tuple[UniProtStatus, str | None]:
    inactive = entry.get("inactiveReason")
    if inactive:
        reason = (inactive.get("inactiveReasonType") or "").lower()
        merged_into = (inactive.get("mergeDemergeTo") or [None])[0]
        if reason == "merged":
            return "merged", merged_into
        if reason == "demerged":
            return "demerged", merged_into
        if reason == "deleted":
            return "deleted", None
        return "obsolete", merged_into
    return "active", None


def _entry_primary_symbol(entry: dict[str, Any]) -> str | None:
    for gene in entry.get("genes") or []:
        name = (gene.get("geneName") or {}).get("value")
        if name:
            return name
    return None


def _index_xrefs(entry: dict[str, Any]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for xref in entry.get("uniProtKBCrossReferences") or []:
        db = xref.get("database")
        ident = xref.get("id")
        if db and ident:
            out.setdefault(db, []).append(ident)
    return out


def _ensembl_canonical_protein(entry: dict[str, Any]) -> str | None:
    """Pull the canonical Ensembl protein ID from UniProt's Ensembl xref properties.

    UniProt stores Ensembl xrefs as ``id=ENST...`` with ``properties=[{key: ProteinId,
    value: ENSP...}, {key: GeneId, value: ENSG...}]``. We want the first ProteinId
    bound to the canonical isoform, or any ENSP if none is marked canonical.
    """

    fallback: str | None = None
    for xref in entry.get("uniProtKBCrossReferences") or []:
        if xref.get("database") != "Ensembl":
            continue
        protein_id: str | None = None
        for prop in xref.get("properties") or []:
            if prop.get("key") == "ProteinId":
                protein_id = prop.get("value")
                break
        if not protein_id:
            continue
        if fallback is None:
            fallback = protein_id
        # An xref without an ``isoformId`` qualifier binds to the default UniProt
        # canonical isoform — prefer it over isoform-specific xrefs.
        if not xref.get("isoformId"):
            return protein_id
    return fallback


def _entry_isoform_count(entry: dict[str, Any]) -> int:
    for comment in entry.get("comments") or []:
        if comment.get("commentType") == "ALTERNATIVE PRODUCTS":
            return len(comment.get("isoforms") or []) or 1
    return 1


def _extract_subcellular_locations(entry: dict[str, Any]) -> list[SubcellularLocation]:
    out: list[SubcellularLocation] = []
    for comment in entry.get("comments") or []:
        if comment.get("commentType") != "SUBCELLULAR LOCATION":
            continue
        molecule = comment.get("molecule")
        for sl in comment.get("subcellularLocations") or []:
            location_text = ((sl.get("location") or {}).get("value")) or ""
            if not location_text:
                continue
            out.append(
                SubcellularLocation(
                    location=location_text,
                    is_isoform_specific=bool(molecule),
                    isoform=molecule,
                    reliability="unknown",
                )
            )
    return out


_TopologyKind = Literal[
    "signal_peptide",
    "transmembrane",
    "topological_domain",
    "intramembrane",
    "lipidation",
    "gpi_anchor",
    "glycosylation",
    "disulfide_bond",
]

_TOPOLOGY_FEATURE_TYPES: dict[str, _TopologyKind] = {
    "Signal": "signal_peptide",
    "Transmembrane": "transmembrane",
    "Topological domain": "topological_domain",
    "Intramembrane": "intramembrane",
    "Lipidation": "lipidation",
    "Glycosylation": "glycosylation",
    "Disulfide bond": "disulfide_bond",
}


def _extract_topology_features(entry: dict[str, Any]) -> list[TopologyFeature]:
    out: list[TopologyFeature] = []
    for feature in entry.get("features") or []:
        ft_type = feature.get("type")
        mapped = _TOPOLOGY_FEATURE_TYPES.get(ft_type or "")
        if mapped is None:
            continue
        description = feature.get("description")
        # Promote GPI anchors out of "Lipidation" so the agent can spot them
        # without parsing prose.
        if mapped == "lipidation" and description and "GPI" in description.upper():
            mapped = "gpi_anchor"
        location = feature.get("location") or {}
        start = (location.get("start") or {}).get("value")
        end = (location.get("end") or {}).get("value")
        out.append(
            TopologyFeature(
                feature_type=mapped,
                description=description,
                start=start,
                end=end,
            )
        )
    return out


def _extract_ptms(entry: dict[str, Any]) -> list[PTMRecord]:
    """Modification features that aren't already counted as topology."""

    out: list[PTMRecord] = []
    for feature in entry.get("features") or []:
        ft_type = (feature.get("type") or "").lower()
        if ft_type in {"modified residue", "phosphoprotein", "cross-link"}:
            location = feature.get("location") or {}
            position = (location.get("start") or {}).get("value")
            out.append(
                PTMRecord(
                    ptm_type=ft_type,
                    description=feature.get("description"),
                    position=position,
                )
            )
    return out


def _extract_isoforms(entry: dict[str, Any]) -> list[IsoformRecord]:
    out: list[IsoformRecord] = []
    for comment in entry.get("comments") or []:
        if comment.get("commentType") != "ALTERNATIVE PRODUCTS":
            continue
        for isoform in comment.get("isoforms") or []:
            iso_ids = isoform.get("isoformIds") or []
            if not iso_ids:
                continue
            name = ((isoform.get("name") or {}).get("value")) or None
            sequence_status = isoform.get("isoformSequenceStatus") or ""
            out.append(
                IsoformRecord(
                    isoform_id=iso_ids[0],
                    name=name,
                    is_canonical=sequence_status.lower() == "displayed",
                )
            )
    return out


def _first_comment_text(entry: dict[str, Any], comment_type: str) -> str | None:
    for comment in entry.get("comments") or []:
        if comment.get("commentType") != comment_type:
            continue
        texts = comment.get("texts") or []
        if texts:
            return texts[0].get("value")
    return None


def _extract_publications(entry: dict[str, Any]) -> tuple[int, list[PublicationStub]]:
    pubs: list[PublicationStub] = []
    references = entry.get("references") or []
    for ref in references:
        citation = ref.get("citation") or {}
        cross_refs = citation.get("citationCrossReferences") or []
        pmid: int | None = None
        for cr in cross_refs:
            if cr.get("database") == "PubMed":
                try:
                    pmid = int(cr.get("id"))
                except (TypeError, ValueError):
                    pmid = None
                break
        if pmid is None:
            continue
        title = citation.get("title") or ""
        year = None
        publication_date = citation.get("publicationDate")
        if publication_date and len(publication_date) >= 4:
            try:
                year = int(publication_date[:4])
            except ValueError:
                year = None
        pubs.append(PublicationStub(pmid=pmid, title=title, year=year))
    return len(pubs), pubs


def _extract_cross_references(entry: dict[str, Any]) -> list[CrossReference]:
    """Return whitelisted xrefs ordered by priority (PDB → InterPro → Pfam → ...).

    The priority order matches ``_KEEP_XREF_DBS`` insertion order: structure-of-record
    DBs first because they're load-bearing for topology calls.
    """

    by_kind: dict[str, list[CrossReference]] = {kind: [] for kind in _KEEP_XREF_DBS.values()}
    seen: set[tuple[str, str]] = set()
    for xref in entry.get("uniProtKBCrossReferences") or []:
        db = xref.get("database")
        ident = xref.get("id")
        if not db or not ident:
            continue
        mapped = _KEEP_XREF_DBS.get(db)
        if mapped is None:
            continue
        if (mapped, ident) in seen:
            continue
        seen.add((mapped, ident))
        by_kind[mapped].append(CrossReference(db=mapped, identifier=ident))
    out: list[CrossReference] = []
    for kind in _KEEP_XREF_DBS.values():
        out.extend(by_kind[kind])
    return out


# ---------------------------------------------------------------------------
# HGNC + NCBI helpers
# ---------------------------------------------------------------------------


def _hgnc_record(symbol: str, *, http: CachedHTTP) -> dict[str, Any] | None:
    url = f"https://rest.genenames.org/fetch/symbol/{symbol}"
    payload = http.get_json(
        url, source="hgnc", ttl_days=_TTL["hgnc"], headers={"Accept": "application/json"}
    )
    docs = ((payload or {}).get("response") or {}).get("docs") or []
    return docs[0] if docs else None


def _ncbi_gene_summary(gene_id: int, *, http: CachedHTTP) -> dict[str, Any] | None:
    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
    params: dict[str, str] = {"db": "gene", "id": str(gene_id), "retmode": "json"}
    api_key = os.environ.get("NCBI_API_KEY")
    if api_key:
        params["api_key"] = api_key
    payload = http.get_json(url, source="ncbi", ttl_days=_TTL["ncbi"], params=params)
    result = (payload or {}).get("result") or {}
    record = result.get(str(gene_id))
    return record if isinstance(record, dict) else None


def _parse_ncbi_aliases(ncbi: dict[str, Any] | None) -> list[str]:
    """NCBI esummary returns ``otheraliases`` as a comma-separated string."""

    if not ncbi:
        return []
    raw = ncbi.get("otheraliases") or ""
    return [tok.strip() for tok in raw.split(",") if tok.strip()]


def _merge_aliases(
    *,
    current: list[str],
    extras: list[list[str]],
    exclude: set[str],
) -> list[str]:
    """Union ``current`` with each list in ``extras``, drop ``exclude`` matches,
    dedupe case-insensitively while preserving the original casing of the first
    occurrence. Order: ``current`` first (HGNC), then each extra in turn.
    """

    blocked = {x.upper() for x in exclude if x}
    seen: set[str] = set()
    out: list[str] = []
    for source in (current, *extras):
        for symbol in source:
            if not symbol:
                continue
            up = symbol.upper()
            if up in blocked or up in seen:
                continue
            seen.add(up)
            out.append(symbol)
    return out


def _alias_collision_risk(
    primary_symbol: str,
    aliases: list[str],
    previous_symbols: list[str],
    *,
    http: CachedHTTP,  # noqa: ARG001 — placeholder for future HGNC search; deliberately not yet wired
) -> AliasCollisionRisk:
    """Heuristic: many aliases / previous symbols → higher collision risk.

    A proper implementation would HGNC-search each alias and count distinct hits.
    For v0 we approximate from the lengths — the M3 plan accepts a heuristic here
    and we revisit when an actual collision case bites us.
    """

    n = len(aliases) + len(previous_symbols)
    if n >= 4:
        return "high"
    if n >= 2:
        return "medium"
    return "low"


# ---------------------------------------------------------------------------
# Small utilities
# ---------------------------------------------------------------------------


def _truncate(text: str | None, max_chars: int) -> str | None:
    if text is None:
        return None
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


def _truthy_flag(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0 and not (isinstance(value, float) and pd.isna(value))
    text = str(value).strip().lower()
    return text in {"1", "true", "yes", "t"}


# ---------------------------------------------------------------------------
# SubcellularReliability is referenced through the model's Literal; importing it
# here keeps it in module scope for downstream type-checking and re-export.
# ---------------------------------------------------------------------------

__all__ = [
    "Mode",
    "gene_lookup",
    "resolve",
    "db_panel",
    "uniprot_summary",
    "miss_diagnosis",
    "looks_like_uniprot_acc",
    "SubcellularReliability",
]
