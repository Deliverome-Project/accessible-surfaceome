"""Per-gene "deep-dive pack": ortholog identity precompute.

v0.4.0 refocus: dropped the DeepTMHMM topology join (added a third
source of topology calls without clarifying the human accessibility
call — UniProt features already cover this). What remains is the
Ensembl Compara mouse + cyno ortholog identity table: one-to-one,
high-confidence pairs only, keyed by human UniProt accession or HGNC
symbol.

Runtime source order:

1. **Cloudflare D1 `compara_ortholog` table** (production). Uses the
   active release stamped at
   `data/external/ensembl_compara_surfaceome_expressed/.last_refresh`,
   or the most recent release row when the marker is absent.
2. **Local CSV fallback** at
   ``data/external/ensembl_compara_surfaceome_expressed/compara_mouse_cyno_one2one_highconf_by_ensembl_query.csv``
   when D1 is unreachable or the env vars aren't set (dev / CI).

Failure mode: every loader returns ``DeepDivePack`` with empty
ortholog slots if no source is available. The agent still gets the
rest of its context; ``orthology`` stays empty.
"""

from __future__ import annotations

import csv
import logging
from dataclasses import dataclass, field
from pathlib import Path

from accessible_surfaceome.paths import REPO_ROOT

logger = logging.getLogger(__name__)


# ---- defaults -------------------------------------------------------------

COMPARA_DIR = REPO_ROOT / "data" / "external" / "ensembl_compara_surfaceome_expressed"
COMPARA_QUERY_CSV = COMPARA_DIR / "compara_mouse_cyno_one2one_highconf_by_ensembl_query.csv"
COMPARA_LAST_REFRESH = COMPARA_DIR / ".last_refresh"


# ---- pack shapes ----------------------------------------------------------


@dataclass(frozen=True)
class OrthologIdentity:
    """One mouse / cyno ortholog: identity + Compara metadata.

    No topology — the agent fetches that from UniProt directly when
    it wants a concordance call. The pack is intentionally identity-only.
    """

    species: str  # "mouse" | "cynomolgus"
    ortholog_uniprot_acc: str | None
    ortholog_gene_symbol: str | None
    ortholog_ensembl_gene_id: str
    orthology_type: str  # one_to_one | one_to_many | many_to_many | no_ortholog | unknown
    percent_identity: float | None
    is_high_confidence: bool


@dataclass(frozen=True)
class DeepDivePack:
    """Per-gene deep-dive precompute. Identity-only after v0.4.0 refocus."""

    hgnc_symbol: str
    uniprot_acc: str | None
    mouse_ortholog: OrthologIdentity | None = None
    cyno_ortholog: OrthologIdentity | None = None
    release_version: str | None = None
    source: str = "unknown"  # "d1" | "csv" | "unknown"
    extras: dict[str, object] = field(default_factory=dict)


# ---- CSV reader -----------------------------------------------------------


def _read_dict_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open() as fh:
        return list(csv.DictReader(fh))


def _ortholog_from_row(row: dict[str, str]) -> OrthologIdentity | None:
    species = (row.get("species") or "").strip().lower()
    if species not in {"mouse", "cynomolgus"}:
        return None
    ensembl = (row.get("ortholog_ensembl_gene") or "").strip()
    if not ensembl:
        return None
    try:
        pid_str = (row.get("percent_identity") or "").strip()
        pid: float | None = float(pid_str) if pid_str else None
    except ValueError:
        pid = None
    hc_raw = (row.get("is_high_confidence") or "").strip().lower()
    is_hc = hc_raw in {"1", "true", "yes", "y", "t"}
    return OrthologIdentity(
        species=species,
        ortholog_uniprot_acc=(row.get("ortholog_uniprot_acc") or "").strip() or None,
        ortholog_gene_symbol=(row.get("ortholog_gene_symbol") or "").strip() or None,
        ortholog_ensembl_gene_id=ensembl,
        orthology_type=(row.get("orthology_type") or "unknown").strip() or "unknown",
        percent_identity=pid,
        is_high_confidence=is_hc,
    )


# ---- D1 + CSV loaders -----------------------------------------------------


def _active_release_version() -> str | None:
    """Read the release-version marker stamped by scripts/refresh_compara.sh."""
    if not COMPARA_LAST_REFRESH.exists():
        return None
    try:
        return COMPARA_LAST_REFRESH.read_text().strip() or None
    except OSError as exc:
        logger.warning("failed to read %s: %s", COMPARA_LAST_REFRESH, exc)
        return None


def _from_d1(
    *, hgnc_symbol: str, uniprot_acc: str | None,
) -> tuple[OrthologIdentity | None, OrthologIdentity | None, str | None]:
    """Query the D1 ``compara_ortholog`` table for this gene's orthologs.

    Returns ``(mouse, cyno, release_version)`` or ``(None, None, None)``
    if D1 isn't reachable or env vars aren't set.
    """
    try:
        from accessible_surfaceome.cloud.d1_client import D1Client, D1Error
    except ImportError:
        return None, None, None

    release = _active_release_version()
    try:
        with D1Client() as client:
            if release is None:
                # Fall back to the most recent release.
                rows = client.query(
                    "SELECT release_version FROM compara_release "
                    "ORDER BY fetched_at DESC LIMIT 1"
                )
                if not rows:
                    return None, None, None
                release = str(rows[0].get("release_version") or "") or None
                if release is None:
                    return None, None, None
            # Prefer the UniProt-acc join when available; fall back to symbol.
            if uniprot_acc:
                rows = client.query(
                    "SELECT * FROM compara_ortholog "
                    "WHERE release_version = ? AND human_uniprot_acc = ?",
                    [release, uniprot_acc],
                )
            else:
                rows = []
            if not rows:
                rows = client.query(
                    "SELECT * FROM compara_ortholog "
                    "WHERE release_version = ? AND human_gene_symbol = ?",
                    [release, hgnc_symbol],
                )
    except D1Error as exc:
        logger.info("D1 lookup failed; will fall back to CSV: %s", exc)
        return None, None, None
    except Exception as exc:  # noqa: BLE001
        # Defensive: any unexpected error in the D1 path falls back.
        logger.warning("unexpected D1 error in deep_dive_pack: %s", exc)
        return None, None, None

    mouse: OrthologIdentity | None = None
    cyno: OrthologIdentity | None = None
    for row in rows:
        # D1 returns SQLite values as strings/numbers/None
        identity = _ortholog_from_row({k: ("" if v is None else str(v)) for k, v in row.items()})
        if identity is None:
            continue
        if identity.species == "mouse" and mouse is None:
            mouse = identity
        elif identity.species == "cynomolgus" and cyno is None:
            cyno = identity
    return mouse, cyno, release


def _from_csv(
    *, hgnc_symbol: str, uniprot_acc: str | None,
) -> tuple[OrthologIdentity | None, OrthologIdentity | None]:
    """Read the local Compara CSV for this gene's orthologs."""
    rows = _read_dict_rows(COMPARA_QUERY_CSV)
    if not rows:
        return None, None
    mouse: OrthologIdentity | None = None
    cyno: OrthologIdentity | None = None
    target_acc = (uniprot_acc or "").strip()
    target_sym = hgnc_symbol.strip().upper()
    for row in rows:
        row_acc = (row.get("human_uniprot_acc") or "").strip()
        row_sym = (row.get("human_gene_symbol") or "").strip().upper()
        if target_acc and row_acc != target_acc:
            if target_sym and row_sym != target_sym:
                continue
        elif row_sym != target_sym:
            continue
        identity = _ortholog_from_row(row)
        if identity is None:
            continue
        if identity.species == "mouse" and mouse is None:
            mouse = identity
        elif identity.species == "cynomolgus" and cyno is None:
            cyno = identity
    return mouse, cyno


# ---- public loader --------------------------------------------------------


class DeepDivePackLoader:
    """Loads the per-gene deep-dive pack. D1 first; CSV fallback.

    Stateless — instantiate once per orchestrator run and call
    ``for_gene`` per gene.
    """

    def for_gene(
        self, *, hgnc_symbol: str, uniprot_acc: str | None = None,
    ) -> DeepDivePack:
        # Try D1 first (production source).
        mouse, cyno, release = _from_d1(hgnc_symbol=hgnc_symbol, uniprot_acc=uniprot_acc)
        source = "d1" if (mouse or cyno) else "unknown"
        # Fall back to CSV if D1 returned nothing.
        if mouse is None and cyno is None:
            csv_mouse, csv_cyno = _from_csv(hgnc_symbol=hgnc_symbol, uniprot_acc=uniprot_acc)
            if csv_mouse or csv_cyno:
                mouse, cyno = csv_mouse, csv_cyno
                source = "csv"
                release = _active_release_version()
        return DeepDivePack(
            hgnc_symbol=hgnc_symbol,
            uniprot_acc=uniprot_acc,
            mouse_ortholog=mouse,
            cyno_ortholog=cyno,
            release_version=release,
            source=source,
        )


# ---- markdown rendering ---------------------------------------------------


def render_markdown(pack: DeepDivePack) -> str:
    """Render the pack as the markdown block injected into the task prompt.

    Returns an explanatory placeholder when no ortholog data is
    available so the agent emits an empty ``orthology`` list rather than
    fabricating one.
    """
    if pack.mouse_ortholog is None and pack.cyno_ortholog is None:
        return (
            "## Pre-loaded deep-dive context (orthologs)\n\n"
            f"No Ensembl Compara one-to-one + high-confidence ortholog was "
            f"available for `{pack.hgnc_symbol}` (release: "
            f"{pack.release_version or 'unknown'}). Emit `orthology` as an "
            "empty list unless you have direct literature evidence for a "
            "mouse / cyno surface call.\n"
        )

    lines = [
        "## Pre-loaded deep-dive context (orthologs)\n",
        f"Release: `{pack.release_version or 'unknown'}` "
        f"(source: `{pack.source}`). Ortholog identity comes from Ensembl "
        "Compara one-to-one + high-confidence pairs. Topology is NOT "
        "precomputed — fetch the ortholog UniProt entry via "
        "`gene_lookup uniprot_summary` if you need a concordance call.\n",
    ]

    def _render(o: OrthologIdentity) -> str:
        return (
            f"### {o.species.capitalize()} ortholog\n\n"
            f"- UniProt: `{o.ortholog_uniprot_acc or '—'}`\n"
            f"- Gene symbol: `{o.ortholog_gene_symbol or '—'}`\n"
            f"- Ensembl gene: `{o.ortholog_ensembl_gene_id}`\n"
            f"- Orthology type: `{o.orthology_type}`\n"
            f"- Percent identity: "
            f"{o.percent_identity:.2f}%" if o.percent_identity is not None
            else "- Percent identity: —"
        ) + (
            "\n- High confidence (Compara): "
            f"{'yes' if o.is_high_confidence else 'no'}\n"
        )

    if pack.mouse_ortholog:
        lines.append(_render(pack.mouse_ortholog))
    if pack.cyno_ortholog:
        lines.append(_render(pack.cyno_ortholog))
    return "\n".join(lines)
