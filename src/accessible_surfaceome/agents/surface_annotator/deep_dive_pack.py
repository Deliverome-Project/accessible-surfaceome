"""Per-gene "deep-dive pack": isoform + ortholog topology precompute.

This module joins the precomputed DeepTMHMM cohorts and Ensembl Compara
ortholog table into a per-gene block injected into the agent's task prompt.
The agent reads it directly — no extra tool calls — and uses it to emit
``isoform_accessibility`` + ``orthology`` fields on the ``SurfaceomeRecord``.

Failure mode: any missing input table degrades gracefully to an empty block.
The agent still gets the rest of its context; the corresponding output
fields stay empty.
"""

from __future__ import annotations

import csv
import logging
from dataclasses import dataclass, field
from pathlib import Path

from accessible_surfaceome.paths import REPO_ROOT

logger = logging.getLogger(__name__)


# ---- defaults -------------------------------------------------------------

DEEPTMHMM_DIR = REPO_ROOT / "data" / "processed" / "deeptmhmm"
DEEPTMHMM_INPUTS_DIR = REPO_ROOT / "data" / "external" / "deeptmhmm_surfaceome_inputs"
COMPARA_DIR = REPO_ROOT / "data" / "external" / "ensembl_compara_surfaceome_expressed"
CANDIDATE_UNIVERSE_DIR = REPO_ROOT / "data" / "processed" / "candidate_universe"

ISOFORM_TSV = DEEPTMHMM_DIR / "deeptmhmm_human_isoforms.tsv"
MOUSE_ORTHOLOG_TSV = DEEPTMHMM_DIR / "deeptmhmm_mouse_ortholog.tsv"
CYNO_ORTHOLOG_TSV = DEEPTMHMM_DIR / "deeptmhmm_cyno_ortholog.tsv"
MOUSE_ORTHOLOG_METADATA = DEEPTMHMM_INPUTS_DIR / "mouse_ortholog_one2one_highconf_non_hla_metadata.csv"
CYNO_ORTHOLOG_METADATA = DEEPTMHMM_INPUTS_DIR / "cyno_ortholog_one2one_highconf_non_hla_metadata.csv"
COMPARA_QUERY_CSV = COMPARA_DIR / "compara_mouse_cyno_one2one_highconf_by_ensembl_query.csv"
CANDIDATE_UNIVERSE_TSV = CANDIDATE_UNIVERSE_DIR / "candidate_universe.tsv"


# ---- pack shapes ----------------------------------------------------------


@dataclass(frozen=True)
class IsoformTopology:
    """One human isoform's DeepTMHMM topology row.

    Mirrors ``data/processed/deeptmhmm/deeptmhmm_human_isoforms.tsv`` rows
    (which carry the ``-N`` suffix in ``uniprot_accession_full``).
    """

    isoform_id: str  # e.g. "P04626-1" or "P04626" for canonical
    entry_name: str
    deeptmhmm_label: str  # TM | SP | SP+TM | BETA | GLOB
    protein_length: int
    tm_helix_count: int
    has_signal_peptide: bool
    signal_peptide_length: int
    n_term_side: str
    c_term_side: str
    predicted_surface_membrane: bool
    predicted_secreted: bool


@dataclass(frozen=True)
class OrthologTopology:
    """One ortholog with DeepTMHMM topology + identity metadata."""

    species: str  # "mouse" | "cynomolgus"
    ortholog_uniprot_acc: str
    ortholog_gene_symbol: str
    ortholog_ensembl_gene_id: str
    entry_name: str
    deeptmhmm_label: str
    protein_length: int
    tm_helix_count: int
    has_signal_peptide: bool
    signal_peptide_length: int
    predicted_surface_membrane: bool
    predicted_secreted: bool
    percent_identity: float | None = None


@dataclass(frozen=True)
class DeepDivePack:
    """Per-gene deep-dive precompute."""

    hgnc_symbol: str
    uniprot_acc: str
    isoforms: list[IsoformTopology] = field(default_factory=list)
    mouse_ortholog: OrthologTopology | None = None
    cyno_ortholog: OrthologTopology | None = None


# ---- TSV helpers ----------------------------------------------------------


def _read_dict_rows(path: Path, delimiter: str) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter=delimiter)
        return list(reader)


def _to_bool(value: str) -> bool:
    return (value or "").strip() in {"1", "True", "true", "TRUE"}


def _to_int(value: str) -> int:
    try:
        return int((value or "").strip())
    except ValueError:
        return 0


def _to_optional_float(value: str) -> float | None:
    try:
        return float((value or "").strip())
    except (TypeError, ValueError):
        return None


# ---- loader ---------------------------------------------------------------


class DeepDivePackLoader:
    """Loads the four precompute tables once; queries cheaply per gene.

    Pass ``base_dir`` overrides for tests; defaults point at the standard
    repo paths under ``data/``.
    """

    def __init__(
        self,
        *,
        isoform_tsv: Path = ISOFORM_TSV,
        mouse_ortholog_tsv: Path = MOUSE_ORTHOLOG_TSV,
        cyno_ortholog_tsv: Path = CYNO_ORTHOLOG_TSV,
        mouse_metadata_csv: Path = MOUSE_ORTHOLOG_METADATA,
        cyno_metadata_csv: Path = CYNO_ORTHOLOG_METADATA,
        compara_query_csv: Path = COMPARA_QUERY_CSV,
        candidate_universe_tsv: Path = CANDIDATE_UNIVERSE_TSV,
    ) -> None:
        # Symbol → UniProt accession (used when caller only has the gene symbol).
        self._symbol_to_acc: dict[str, str] = {}
        for row in _read_dict_rows(candidate_universe_tsv, "\t"):
            acc = (row.get("uniprot_accession") or "").strip().upper()
            if not acc:
                continue
            for col in ("gene_symbol", "gene_symbol_resolved", "gene_symbol_input"):
                key = (row.get(col) or "").strip().upper()
                if key and key not in self._symbol_to_acc:
                    self._symbol_to_acc[key] = acc

        # Isoforms grouped by base UniProt accession.
        self._isoforms: dict[str, list[IsoformTopology]] = {}
        for row in _read_dict_rows(isoform_tsv, "\t"):
            base_acc = (row.get("uniprot_accession") or "").strip().upper()
            iso_id = (row.get("uniprot_accession_full") or "").strip().upper() or base_acc
            if not base_acc:
                continue
            self._isoforms.setdefault(base_acc, []).append(
                IsoformTopology(
                    isoform_id=iso_id,
                    entry_name=(row.get("uniprot_entry_name") or "").strip(),
                    deeptmhmm_label=(row.get("deeptmhmm_label") or "").strip(),
                    protein_length=_to_int(row.get("protein_length") or ""),
                    tm_helix_count=_to_int(row.get("tm_helix_count") or ""),
                    has_signal_peptide=_to_bool(row.get("has_signal_peptide") or ""),
                    signal_peptide_length=_to_int(row.get("signal_peptide_length") or ""),
                    n_term_side=(row.get("n_term_side") or "").strip(),
                    c_term_side=(row.get("c_term_side") or "").strip(),
                    predicted_surface_membrane=_to_bool(
                        row.get("predicted_surface_membrane") or ""
                    ),
                    predicted_secreted=_to_bool(row.get("predicted_secreted") or ""),
                )
            )
        for entries in self._isoforms.values():
            entries.sort(key=lambda iso: iso.isoform_id)

        # Topology rows keyed by ortholog's own UniProt accession.
        self._mouse_by_acc = self._index_topology(mouse_ortholog_tsv)
        self._cyno_by_acc = self._index_topology(cyno_ortholog_tsv)

        # Human-gene-symbol → ortholog identity (from DeepTMHMM-input metadata).
        # We use the metadata CSV (not the Compara CSV) because the metadata
        # records the *resolved* UniProt accession that actually made it into
        # the DeepTMHMM cohort.
        self._mouse_lookup_by_symbol = self._index_metadata(mouse_metadata_csv)
        self._cyno_lookup_by_symbol = self._index_metadata(cyno_metadata_csv)

        # Compara percent-identity layered on by ortholog ENSG.
        self._mouse_pid_by_target_ensg, self._cyno_pid_by_target_ensg = (
            self._index_compara_percent_identity(compara_query_csv)
        )

        logger.info(
            "DeepDivePackLoader: %d isoform groups, %d mouse / %d cyno orthologs",
            len(self._isoforms),
            len(self._mouse_by_acc),
            len(self._cyno_by_acc),
        )

    @staticmethod
    def _index_topology(path: Path) -> dict[str, dict[str, str]]:
        rows = _read_dict_rows(path, "\t")
        return {(row.get("uniprot_accession") or "").strip().upper(): row for row in rows if row.get("uniprot_accession")}

    @staticmethod
    def _index_metadata(path: Path) -> dict[str, dict[str, str]]:
        """Human-gene-symbol → first ortholog metadata row (status=ok)."""
        index: dict[str, dict[str, str]] = {}
        for row in _read_dict_rows(path, ","):
            if (row.get("status") or "").strip() != "ok":
                continue
            input_symbols = (row.get("query_input_gene_symbols") or "").strip()
            if not input_symbols:
                continue
            for token in input_symbols.split("|"):
                key = token.strip().upper()
                if key and key not in index:
                    index[key] = row
        return index

    @staticmethod
    def _index_compara_percent_identity(
        path: Path,
    ) -> tuple[dict[str, float], dict[str, float]]:
        """Build ortholog-ENSG → percent-identity maps for mouse and cyno."""
        mouse_map: dict[str, float] = {}
        cyno_map: dict[str, float] = {}
        for row in _read_dict_rows(path, ","):
            mouse_ensg = (row.get("mouse_target_ensembl_gene_id") or "").strip().upper()
            mouse_pid = _to_optional_float(row.get("mouse_target_percent_identity") or "")
            if mouse_ensg and mouse_pid is not None:
                mouse_map[mouse_ensg] = mouse_pid
            cyno_ensg = (row.get("cyno_target_ensembl_gene_id") or "").strip().upper()
            cyno_pid = _to_optional_float(row.get("cyno_target_percent_identity") or "")
            if cyno_ensg and cyno_pid is not None:
                cyno_map[cyno_ensg] = cyno_pid
        return mouse_map, cyno_map

    def for_gene(self, *, hgnc_symbol: str, uniprot_acc: str | None = None) -> DeepDivePack:
        """Build the per-gene pack. Always returns; empty fields when no data.

        When ``uniprot_acc`` is None, falls back to the candidate-universe
        symbol→accession map. If the symbol is unknown there too, the
        isoform lookup will be empty but ortholog metadata (keyed by gene
        symbol) may still resolve.
        """
        symbol_key = (hgnc_symbol or "").strip().upper()
        acc_key = (uniprot_acc or "").strip().upper()
        if not acc_key:
            acc_key = self._symbol_to_acc.get(symbol_key, "")

        isoforms = list(self._isoforms.get(acc_key, []))

        mouse = self._build_ortholog(
            species="mouse",
            symbol_key=symbol_key,
            metadata_index=self._mouse_lookup_by_symbol,
            topology_index=self._mouse_by_acc,
            pid_by_ensg=self._mouse_pid_by_target_ensg,
        )
        cyno = self._build_ortholog(
            species="cynomolgus",
            symbol_key=symbol_key,
            metadata_index=self._cyno_lookup_by_symbol,
            topology_index=self._cyno_by_acc,
            pid_by_ensg=self._cyno_pid_by_target_ensg,
        )

        return DeepDivePack(
            hgnc_symbol=symbol_key,
            uniprot_acc=acc_key,
            isoforms=isoforms,
            mouse_ortholog=mouse,
            cyno_ortholog=cyno,
        )

    @staticmethod
    def _build_ortholog(
        *,
        species: str,
        symbol_key: str,
        metadata_index: dict[str, dict[str, str]],
        topology_index: dict[str, dict[str, str]],
        pid_by_ensg: dict[str, float],
    ) -> OrthologTopology | None:
        meta = metadata_index.get(symbol_key)
        if not meta:
            return None
        ortholog_acc = (meta.get("selected_uniprot_accession") or "").strip().upper()
        if not ortholog_acc:
            return None
        topo = topology_index.get(ortholog_acc)
        if not topo:
            return None
        target_ensg = (meta.get("target_ensembl_gene_id") or "").strip().upper()
        return OrthologTopology(
            species=species,
            ortholog_uniprot_acc=ortholog_acc,
            ortholog_gene_symbol=(meta.get("target_gene_symbol") or "").strip(),
            ortholog_ensembl_gene_id=target_ensg,
            entry_name=(topo.get("uniprot_entry_name") or "").strip(),
            deeptmhmm_label=(topo.get("deeptmhmm_label") or "").strip(),
            protein_length=_to_int(topo.get("protein_length") or ""),
            tm_helix_count=_to_int(topo.get("tm_helix_count") or ""),
            has_signal_peptide=_to_bool(topo.get("has_signal_peptide") or ""),
            signal_peptide_length=_to_int(topo.get("signal_peptide_length") or ""),
            predicted_surface_membrane=_to_bool(topo.get("predicted_surface_membrane") or ""),
            predicted_secreted=_to_bool(topo.get("predicted_secreted") or ""),
            percent_identity=pid_by_ensg.get(target_ensg),
        )


# ---- markdown rendering ---------------------------------------------------


def _ortholog_block(label: str, ortholog: OrthologTopology | None) -> str:
    if ortholog is None:
        return f"### {label} ortholog\n\nNo one-to-one high-confidence ortholog with DeepTMHMM topology available.\n"
    pid = (
        f"{ortholog.percent_identity:.1f}%"
        if ortholog.percent_identity is not None
        else "n/a"
    )
    return (
        f"### {label} ortholog\n\n"
        f"- gene symbol: `{ortholog.ortholog_gene_symbol}` "
        f"(UniProt `{ortholog.ortholog_uniprot_acc}`, Ensembl `{ortholog.ortholog_ensembl_gene_id}`)\n"
        f"- percent identity to human: {pid}\n"
        f"- DeepTMHMM label: `{ortholog.deeptmhmm_label}` "
        f"(length {ortholog.protein_length} aa, "
        f"TM helices {ortholog.tm_helix_count}, "
        f"signal peptide {'yes' if ortholog.has_signal_peptide else 'no'})\n"
        f"- predicted surface membrane: "
        f"{'yes' if ortholog.predicted_surface_membrane else 'no'}; "
        f"predicted secreted: {'yes' if ortholog.predicted_secreted else 'no'}\n"
    )


def render_markdown(pack: DeepDivePack) -> str:
    """Render the per-gene pack as the markdown block injected into the task prompt.

    Returns ``""`` when there's nothing to inject (no isoforms, no orthologs).
    The task template should fall back to an empty section in that case.
    """
    has_any = bool(pack.isoforms or pack.mouse_ortholog or pack.cyno_ortholog)
    if not has_any:
        return (
            "## Pre-loaded deep-dive context\n\n"
            "No precomputed isoform or ortholog topology data was available "
            f"for `{pack.hgnc_symbol}` (UniProt `{pack.uniprot_acc}`). "
            "Emit `isoform_accessibility` / `orthology` as empty lists unless "
            "you have evidence from another source.\n"
        )

    lines: list[str] = [
        "## Pre-loaded deep-dive context",
        "",
        "These rows come from deterministic precompute (DeepTMHMM + Ensembl",
        "Compara). Cite them as `evidence_type: \"computational_prediction\"`",
        "with `source_id: \"UniProt:<acc>\"` only when you've fetched that",
        "UniProt entry; otherwise leave `cited_evidence_ids` empty and note the",
        "limitation in `confidence_reasoning`.",
        "",
        "### Human isoform topology (DeepTMHMM)",
        "",
    ]

    if pack.isoforms:
        lines.append("| isoform_id | label | length | TM helices | signal peptide | surface? |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for iso in pack.isoforms:
            lines.append(
                f"| `{iso.isoform_id}` | {iso.deeptmhmm_label} | "
                f"{iso.protein_length} | {iso.tm_helix_count} | "
                f"{'yes' if iso.has_signal_peptide else 'no'} | "
                f"{'yes' if iso.predicted_surface_membrane else 'no'} |"
            )
    else:
        lines.append(
            "No isoform-resolved topology in the human_isoforms cohort for "
            f"`{pack.uniprot_acc}`. Use the canonical UniProt isoform for "
            "the gene-level call; emit a single `isoform_accessibility` entry "
            "for the canonical isoform."
        )

    lines.append("")
    lines.append(_ortholog_block("Mouse", pack.mouse_ortholog))
    lines.append(_ortholog_block("Cynomolgus", pack.cyno_ortholog))

    return "\n".join(lines).rstrip() + "\n"
