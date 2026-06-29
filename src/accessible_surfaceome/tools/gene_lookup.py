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
from ._shared.ncbi import add_ncbi_api_key_param

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
    """Resolve a **UniProt accession** into a canonical identifier bundle.

    Symbol-input resolution was removed in resolver v3 because the
    symbol-keyed lookup path silently returned the wrong protein for
    ~0.2% of human genes (45 of 19k cohort symbols — COX1 → cyclo-
    oxygenase instead of mitochondrial cytochrome c oxidase, WAS →
    an rRNA instead of the Wiskott-Aldrich protein, etc. — see
    ``scripts/audit/audit_resolver_hgnc_id_v3.py`` for the documented
    failure modes).

    What to call instead, by input shape:

      * **HGNC ID** (e.g. ``HGNC:1234``) →
        ``resolve_by_hgnc_id(hgnc_id, http=http)``. The canonical
        entry point. Cohort rows always have one (100% coverage).
      * **Gene symbol** (e.g. ``CCR4``) → first look up its HGNC ID
        from D1's ``gene_identifier_public`` table:
            ``SELECT hgnc_id FROM gene_identifier_public WHERE hgnc_symbol = ?``
        then call ``resolve_by_hgnc_id`` with the result. See
        CLAUDE.md's "Gene identifier resolution" section.
      * **UniProt accession** (e.g. ``P51679``) → this function. The
        regex check filters out gene symbols that happen to match
        the accession shape (P2RY10-14, B3GNT3-9, H2BC12, etc.) so
        they raise here rather than silently round-tripping.

    Raises ``LookupError`` with an actionable message when the input
    isn't accession-shaped — callers must migrate to one of the two
    paths above.
    """

    raw = symbol_or_acc.strip()
    if not looks_like_uniprot_acc(raw):
        raise LookupError(
            f"resolve() no longer accepts gene symbols (got {symbol_or_acc!r}). "
            "Use resolve_by_hgnc_id(hgnc_id) instead, or look up the symbol's "
            "HGNC ID via D1: SELECT hgnc_id FROM gene_identifier_public "
            "WHERE hgnc_symbol = ?. See CLAUDE.md 'Gene identifier resolution' "
            "section for the migration playbook."
        )
    uniprot_acc = raw.upper()
    try:
        entry = _uniprot_entry(uniprot_acc, http=http)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code != 404:
            raise
        # Coincidental regex match against a gene symbol that happens
        # to look like a UniProt acc. The legacy code used to fall
        # back to symbol search here — we now require the caller to
        # disambiguate by looking up the HGNC ID first.
        raise LookupError(
            f"{uniprot_acc!r} 404'd at UniProt and looks like it might be "
            "a gene symbol matching the accession regex (e.g. P2RY10-14). "
            "If so, route through resolve_by_hgnc_id — see the resolve() "
            "docstring + CLAUDE.md."
        ) from exc
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
        uniprot_family=_uniprot_family(entry),
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


def resolve_by_hgnc_id(hgnc_id: str, *, http: CachedHTTP) -> IdentifierBundle:
    """Resolve directly from a stable HGNC ID — preferred over the
    symbol-keyed ``resolve()`` whenever the cohort row carries one.

    HGNC IDs are one-per-gene and never reassigned, so the three
    residual failure modes documented in ``_uniprot_search_by_symbol``
    don't apply here:

      * **Primary-name collisions.** Two reviewed UniProt entries can
        share a primary ``geneName.value`` (e.g. across HLA / Ig / TCR
        gene-segment families); ``_uniprot_search_by_symbol`` returns
        the first such hit, which is server-rank-dependent. By
        contrast, HGNC's ``uniprot_ids`` xref is a closed set per
        gene and we explicitly pick the canonical Swiss-Prot entry
        from it.
      * **HGNC fallback's ``uniprot_ids[0]``.** The legacy fallback
        path silently took index 0 of HGNC's xref list when UniProt's
        symbol search returned nothing; this picker iterates and
        applies a canonicalization rule.
      * **Symbol-reassignment drift.** When HGNC re-assigns a symbol
        from one gene to another (rare but documented), a
        symbol-keyed query returns the new gene; an HGNC-ID-keyed
        query returns the gene the cohort actually meant.

    Raises ``LookupError`` when the HGNC record has no
    ``uniprot_ids`` xref — that gene is out of study scope (no
    reviewed human protein), same contract as ``resolve``.
    """

    raw = hgnc_id.strip()
    if not raw.upper().startswith("HGNC:"):
        raw = f"HGNC:{raw}"
    hgnc = _hgnc_record_by_id(raw, http=http)
    if not hgnc:
        raise LookupError(f"no HGNC record for {hgnc_id!r}")

    primary_symbol = (hgnc.get("symbol") or "").strip()
    uniprot_ids = list(hgnc.get("uniprot_ids") or [])
    uniprot_acc: str | None = None

    if uniprot_ids:
        # Path A — HGNC has the xref. Pick canonical with the
        # primary-name + age tiebreak.
        uniprot_acc = _pick_canonical_uniprot(
            uniprot_ids, http=http, prefer_primary_name=primary_symbol or None
        )
    elif primary_symbol:
        # Path B — HGNC curates the gene but hasn't filled the
        # UniProt xref yet (~8 of 19k cases in the audit: ABHD4,
        # C10orf90, HSD17B8, LGTN, LRTOMT, PTPRZ2, RSC1A1, UBE2O).
        # Fall back to UniProt symbol search using HGNC's primary
        # symbol — that's the canonical name UniProt indexes
        # against (more current than whatever the cohort row had).
        uniprot_acc = _uniprot_search_by_symbol(primary_symbol, http=http)
        # Path C — HGNC's primary symbol doesn't hit either (rare
        # mid-rename windows). Try HGNC's previous symbols.
        if uniprot_acc is None:
            for prev in hgnc.get("prev_symbol") or []:
                uniprot_acc = _uniprot_search_by_symbol(prev, http=http)
                if uniprot_acc:
                    break

    if uniprot_acc is None:
        raise LookupError(
            f"HGNC {hgnc_id} (primary={primary_symbol!r}) has no "
            "uniprot_ids xref and UniProt symbol search of the "
            "primary + previous symbols returned nothing — out of "
            "study scope"
        )

    entry = _uniprot_entry(uniprot_acc, http=http)
    return _bundle_from_entry(
        entry,
        uniprot_acc=uniprot_acc,
        hgnc=hgnc,
        http=http,
    )


def _hgnc_record_by_id(hgnc_id: str, *, http: CachedHTTP) -> dict[str, Any] | None:
    """Fetch an HGNC record by ID. ``hgnc_id`` must include the
    ``HGNC:`` prefix (HGNC's REST API requires it). Same TTL +
    cache-source as ``_hgnc_record`` so symbol- and ID-keyed
    lookups share the cache."""

    url = f"https://rest.genenames.org/fetch/hgnc_id/{hgnc_id}"
    payload = http.get_json(
        url, source="hgnc", ttl_days=_TTL["hgnc"], headers={"Accept": "application/json"}
    )
    docs = ((payload or {}).get("response") or {}).get("docs") or []
    return docs[0] if docs else None


def _pick_canonical_uniprot(
    uniprot_ids: list[str],
    *,
    http: CachedHTTP,
    prefer_primary_name: str | None = None,
) -> str:
    """Pick the canonical reviewed Swiss-Prot accession from an HGNC
    ``uniprot_ids`` list, with the same accession-history reconciliation
    the M1 candidate-universe merge applies (``merge/normalize.py``).

    HGNC sometimes lists multiple UniProt accs for one gene (canonical
    + isoform-specific reviewed entries; less commonly canonical +
    a TrEMBL stub). HGNC's xref is also curated manually and lags
    UniProt's monthly merges, so the list can include:

      * **Secondary accs** that UniProt has merged into a current
        primary. Mirroring ``normalize_accessions``' ``sec_ac.txt``
        rewrite, follow the merge chain to the current primary.
      * **Deleted Swiss-Prot accs**. Mirroring the ``delac_sp.txt``
        drop, skip them entirely.

    Canonical-pick tiebreak (each higher-priority field decides
    before the next is consulted):

      1. **reviewed Swiss-Prot** > unreviewed TrEMBL.
      2. **primary ``geneName.value`` matches ``prefer_primary_name``**
         > everything else. Lifts entries that name the gene as
         primary above isoform-specific / fragment / variant
         entries that share the symbol only as a synonym.
      3. **canonical-isoform** (no ``-N`` suffix) > isoform-specific.
      4. **earliest ``entryAudit.firstPublicDate``**. Swiss-Prot's
         own canonical convention — the first reviewed entry is the
         canonical record; later additions are usually variants,
         fragments, or refined-annotation duplicates. Audit found
         this consistently identifies the canonical (PRNP 1986 vs
         2012, ND4 1986 vs 2026, TSPO 1993 vs 2009, BBC3 2004 vs
         2012). The lex-sort tiebreak used previously got these all
         wrong (lex order has no relation to canonical-ness).
      5. **lexicographic accession** as final deterministic tie.

    Raises ``LookupError`` when *every* listed acc resolves to
    merged-with-no-target / deleted / 404 — same contract as the M1
    merge's "no rows surface for this gene".
    """

    if not uniprot_ids:
        raise ValueError("uniprot_ids is empty")

    target = (prefer_primary_name or "").upper().strip()
    candidates: list[tuple[int, int, int, str, str]] = []
    for acc in uniprot_ids:
        try:
            entry = _uniprot_entry(acc, http=http)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                continue
            raise

        status, merged_into = _entry_status(entry)
        # Mirror M1 ``normalize_accessions`` secondary→primary rewrite:
        # when HGNC's xref points at a merged acc, walk one hop to
        # the current primary. UniProt itself returns a single hop
        # at most (multi-hop merges are flattened to the final
        # primary), so one re-fetch is sufficient.
        if status == "merged" and merged_into:
            try:
                entry = _uniprot_entry(merged_into, http=http)
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 404:
                    continue
                raise
            status, _ = _entry_status(entry)
            acc = merged_into

        # Mirror M1's ``delac_sp.txt`` drop. Also drops any acc whose
        # merged-into target is itself deleted.
        if status == "deleted":
            continue

        reviewed_rank = (
            0 if entry.get("entryType") == "UniProtKB reviewed (Swiss-Prot)" else 1
        )
        primary_name = (_entry_primary_symbol(entry) or "").upper().strip()
        name_match_rank = 0 if (target and primary_name == target) else 1
        isoform_rank = 1 if "-" in acc else 0
        # ``firstPublicDate`` is ISO YYYY-MM-DD, so string sort is
        # chronological. Missing dates sort last (treat as "never
        # canonical" rather than "ancient").
        first_public = (
            (entry.get("entryAudit") or {}).get("firstPublicDate") or "9999-99-99"
        )
        candidates.append(
            (reviewed_rank, name_match_rank, isoform_rank, first_public, acc)
        )

    if not candidates:
        raise LookupError(
            f"every uniprot_id in HGNC xref {uniprot_ids!r} resolved to "
            "merged-with-no-target / deleted / 404 — out of study scope"
        )
    candidates.sort()
    return candidates[0][4]


def _bundle_from_entry(
    entry: dict[str, Any],
    *,
    uniprot_acc: str,
    hgnc: dict[str, Any] | None,
    http: CachedHTTP,
) -> IdentifierBundle:
    """Shared bundle-assembly logic for ``resolve`` and
    ``resolve_by_hgnc_id``. Lifted verbatim from the post-search tail
    of ``resolve()`` so behavior matches when the same UniProt entry
    is reached through either path. Caller supplies the resolved
    UniProt entry + the HGNC record (None forces a symbol-keyed HGNC
    lookup off the entry's primary symbol — same as the legacy path)."""

    status, merged_into = _entry_status(entry)
    primary_symbol = _entry_primary_symbol(entry) or ""
    xrefs = _index_xrefs(entry)
    ensembl_canonical_protein = _ensembl_canonical_protein(entry)

    if hgnc is None:
        hgnc = _hgnc_record(primary_symbol, http=http) or {}
    hgnc_id = hgnc.get("hgnc_id") or (xrefs.get("HGNC") or [""])[0]
    approved_name = hgnc.get("name")
    hgnc_aliases = list(hgnc.get("alias_symbol") or [])
    alias_names = list(hgnc.get("alias_name") or [])
    previous_symbols = list(hgnc.get("prev_symbol") or [])
    previous_names = list(hgnc.get("prev_name") or [])
    hgnc_gene_groups = list(hgnc.get("gene_group") or [])
    cd_designation_raw = hgnc.get("cd")
    cd_designation = (
        cd_designation_raw if isinstance(cd_designation_raw, str) and cd_designation_raw else None
    )
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
    alias_collision_risk = _alias_collision_risk(
        primary_symbol, aliases, previous_symbols, http=http
    )
    ncbi_summary = _truncate(ncbi.get("summary") if ncbi else None, _NCBI_SUMMARY_CHARS)

    # Use the HGNC primary symbol when available (canonical for the
    # gene), otherwise the UniProt entry's primary, otherwise empty.
    final_symbol = hgnc.get("symbol") or primary_symbol

    return IdentifierBundle(
        hgnc_symbol=final_symbol,
        hgnc_id=hgnc_id,
        approved_name=approved_name,
        aliases=aliases,
        alias_names=alias_names,
        previous_symbols=previous_symbols,
        previous_names=previous_names,
        hgnc_gene_groups=hgnc_gene_groups,
        uniprot_family=_uniprot_family(entry),
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
        open_targets_status=None,
        ncbi_summary=ncbi_summary,
    )


def _uniprot_search_by_symbol(symbol: str, *, http: CachedHTTP) -> str | None:
    """Resolve a gene symbol → reviewed UniProt accession, preferring
    entries where ``symbol`` is the primary gene name over entries
    where it is only a synonym.

    UniProt's ``gene_exact:`` operator matches both the primary gene
    name and any synonym, with no preference between them. Asking for
    ``size=1`` and trusting the first result silently picks the wrong
    entry for ~tens of HGNC-canonical symbols that also appear as
    legacy synonyms in *other* entries. Documented collisions from the
    2026-05-12 genome-wide sweep:

      - ``gene_exact:CCR4`` → Q9UK39 NOCT (CCR4 is a synonym after the
        yeast carbon-catabolite-repressor homolog); the real CCR4
        chemokine receptor is P51679.
      - ``gene_exact:SMO`` → Q9NWM0 SMOX (SMO is the legacy short
        symbol for spermine oxidase); the real Smoothened is Q99835.

    Fix: pull the top ``size=25`` candidates, return the first one
    whose primary ``geneName.value`` equals the query symbol
    (case-insensitive). Fall back to the first synonym match only when
    no primary-name match exists — that path preserves resolution for
    deprecated symbols that no entry currently uses as primary.
    """

    url = "https://rest.uniprot.org/uniprotkb/search"
    params = {
        "query": f"gene_exact:{symbol} AND organism_id:9606 AND reviewed:true",
        "fields": "accession,gene_names",
        "format": "json",
        "size": "25",
    }
    payload = http.get_json(url, source="uniprot", ttl_days=_TTL["uniprot"], params=params)
    results = (payload or {}).get("results") or []
    if not results:
        return None

    target = symbol.upper()
    synonym_fallback: str | None = None
    for entry in results:
        primary = _entry_primary_symbol(entry)
        if primary and primary.upper() == target:
            return entry["primaryAccession"]
        if synonym_fallback is None:
            synonym_fallback = entry["primaryAccession"]
    return synonym_fallback


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


_SIMILARITY_PREFIX_RE = re.compile(r"^belongs to the\s+", re.IGNORECASE)


def _uniprot_family(entry: dict[str, Any]) -> str | None:
    """Extract the curator-assigned protein family from UniProt's SIMILARITY comment.

    UniProt records family membership as a free-text SIMILARITY comment of the
    form ``"Belongs to the <family> family."`` (e.g. GPR75 O95800 →
    ``"Belongs to the G-protein coupled receptor 1 family"``). This is a
    *deterministic*, curator-assigned tag — distinct from the LLM's high-level
    functional class — so we normalize the boilerplate ``"Belongs to the "``
    prefix and trailing period and keep the rest (subfamily detail included).

    Returns ``None`` when the entry carries no SIMILARITY comment, which is
    common for poorly-characterized proteins.
    """
    raw = _first_comment_text(entry, "SIMILARITY")
    if not raw:
        return None
    cleaned = _SIMILARITY_PREFIX_RE.sub("", raw.strip()).rstrip(".").strip()
    return cleaned or None


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
    add_ncbi_api_key_param(params)
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
