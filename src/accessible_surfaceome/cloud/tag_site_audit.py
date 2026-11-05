"""Apply the tag-site literature audit to ``tag_site_public`` rows (pure logic).

Background. Rows with ``provenance = 'literature_retrieved'`` and
``site_kind = 'internal'`` were written by an LLM literature agent (prompt
1.4.0) and served unchecked. Every one of the 176 such rows used to train the
S5E13 tag-site ranker was audited by hand against its cited paper
(deliverome-analysis PR 236, ``scratch/becca/tag-site-corpus-audit/audit.tsv``).
This module turns that audit TSV plus a snapshot of the rows as served into
the corrected rows and the list of rows to withdraw. It is deliberately pure:
no D1, no network. ``scripts/cloud/apply_tag_site_audit.py`` does the I/O.

Per-verdict rule
----------------
``confirmed_exact``
    Residue unchanged. Only ``validation_level`` may change (below). A region
    row (``insert_after_residue`` NULL) whose paper the audit could read down
    to a junction gains that residue (``corrected_residue``), with flanks,
    label and topology state derived as for a shift.
``confirmed_shifted``
    ``insert_after_residue`` becomes ``corrected_residue``;
    ``residue_before`` / ``residue_after`` / ``residue_label`` are recomputed
    from the human canonical sequence; ``position_frame`` records the frame
    the paper numbered in (``ortholog:mouse``, ``mature``, ``isoform:...``).
``region_only``
    The paper names a loop or domain, not a junction. ``insert_after_residue``
    becomes NULL, ``residue_label`` names the region (the shape the existing
    ``*-internal-None-lit`` rows already have), ``residue_range`` carries the
    candidate junction span when the audit could narrow it to one.
``not_supported`` / ``wrong_species_numbering`` / ``terminal_misfiled``
    Withdrawn from the served set. The table keys on ``(uniprot_acc, site_id)``
    with no version axis, so withdrawal is a DELETE; the pre-change rows are
    kept beside the corrected ones (committed snapshot + dated S3 export).

Validation level. ``surface_shown`` / ``function_shown`` are what the paper
actually reports (``yes`` / ``no`` / ``not_reported``); anything but ``yes``
means the paper lacks the assay, and the level is lowered to what it does
support: a surface claim without a surface assay drops, a function claim
without a function assay drops, and a row left with neither becomes
``detected_only``. Levels the audit does not grade (``not_measured``,
``detected_only``) are untouched.

``site_id`` is kept on every surviving row, including shifted ones, so the
audit TSV, the ranker's training set and the served table stay joinable on
one key. The rationale prefix records the original residue.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

AUDIT_REF = "deliverome-analysis PR 236"

#: Columns of the live ``tag_site_public`` table, in the order the writer sends
#: them. Mirrors the deployed loader (``cloud/tag_sites.py::_COLS`` on ``dev``).
COLUMNS: tuple[str, ...] = (
    "gene_symbol",
    "uniprot_acc",
    "site_id",
    "provenance",
    "det_path",
    "site_kind",
    "insert_after_residue",
    "residue_before",
    "residue_after",
    "residue_label",
    "residue_range",
    "topology_state",
    "extracellular",
    "compartment",
    "tag_type",
    "tag_length_aa",
    "linker",
    "evidence_type",
    "functional_impact_measured",
    "confidence",
    "rationale",
    "sources_json",
    "plddt",
    "conservation_rank",
    "median_conservation",
    "tag_sites_version",
    "synced_at",
    "validation_level",
    "position_evidence",
    "source_tier",
    "cited_tag_residue",
    "entailment_verified",
    "position_frame",
    "candidate_id",
    "library",
    "numbered_against",
    "loop_run_position",
)

KEEP_VERDICTS = frozenset({"confirmed_exact", "confirmed_shifted", "region_only"})
DROP_VERDICTS = frozenset(
    {"not_supported", "wrong_species_numbering", "terminal_misfiled"}
)

#: ``region_only`` rows that were served WITH a residue: site_id ->
#: (residue_label, candidate insert_after span or None). A row already served
#: as a region (``*-internal-None-lit``) keeps its own label and is not listed. The label is the loop / domain the paper names, as read in the
#: audit notes; the span is the set of junctions the paper's wording leaves
#: open (e.g. "at Y113" is 112|113 or 113|114) and is omitted when the paper
#: gives no residue at all.
REGION_LABELS: dict[str, tuple[str, tuple[int, int] | None]] = {
    "AQP1-internal-120-lit": (
        "loop C at Thr-120 (junction 119|120 or 120|121 not stated)",
        (119, 120),
    ),
    "ATP1A3-internal-109-lit": (
        "ECL1 (paralog site: rat ATP1A1 A119 maps to ATP1A3 ~A109; no ATP1A3 construct)",
        None,
    ),
    "BACE1-internal-45-lit": (
        "after the propeptide cleavage site (R45|E46 by UniProt annotation; paper "
        "names only the landmark)",
        None,
    ),
    "BST2-internal-146-lit": (
        "at residue 146 (junction 145|146 or 146|147 not stated)",
        (145, 146),
    ),
    "CD1D-internal-301-lit": (
        "between the extracellular and transmembrane domains (mouse Cd1d1; "
        "~S301|M302 in human)",
        None,
    ),
    "CFTR-internal-897-lit": (
        "ECL4 at S898 in an isolated TMD2 fragment (junction 897|898 or 898|899 "
        "not stated)",
        (897, 898),
    ),
    "CLCA4-internal-594-lit": (
        "nucleotide 1782 after the start codon (codon 594 or 595)",
        (594, 595),
    ),
    "GRIA1-internal-396-lit": (
        "ATD-LBD linker at position 396 (junction 395|396 or 396|397 not stated)",
        (395, 396),
    ),
    "KCNJ1-internal-113-lit": (
        "extracellular domain at Y113 of rat ROMK (human H113; junction 112|113 or "
        "113|114 not stated)",
        (112, 113),
    ),
    "MMP14-internal-111-lit": ("between the propeptide and catalytic domain", None),
    "SLC46A2-internal-57-lit": ("first predicted extracellular loop", None),
    "SLC6A3-internal-199-lit": (
        "G199/S201 junction as written (insert after 199 or 200)",
        (199, 200),
    ),
    "TMEM123-internal-34-lit": (
        "N-terminal region following the signal peptide at A34 (junction 33|34 or "
        "34|35 not stated)",
        (33, 34),
    ),
}


@dataclass
class Correction:
    """What the audit does to one row."""

    site_id: str
    uniprot_acc: str
    gene_symbol: str
    verdict: str
    action: str  # "keep" | "update" | "delete"
    residue_before_audit: int | None
    residue_after_audit: int | None
    validation_before: str | None
    validation_after: str | None
    row: dict[str, Any] | None = field(default=None, repr=False)

    @property
    def shift(self) -> int | None:
        if self.residue_before_audit is None or self.residue_after_audit is None:
            return None
        return self.residue_after_audit - self.residue_before_audit


def read_audit(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh, delimiter="\t"))
    ids = [r["site_id"] for r in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("audit.tsv has duplicate site_id values")
    return rows


def _shown(value: str) -> bool:
    return value.strip().lower() == "yes"


def lowered_validation_level(
    level: str | None, *, surface: str, function: str
) -> str | None:
    """The validation level the paper actually supports.

    ``surface`` / ``function`` are the audit's ``surface_shown`` /
    ``function_shown`` values. A level is lowered, never raised: the audit
    found several rows understate function (e.g. a surface_only row whose
    paper also measured activity) and those are left alone, because raising
    would be a new claim the agent never made.
    """
    if level in (None, "", "not_measured", "detected_only"):
        return level
    s, f = _shown(surface), _shown(function)
    if level == "surface_and_function":
        if s and f:
            return level
        if s:
            return "surface_only"
        if f:
            return "function_only"
        return "detected_only"
    if level == "surface_only":
        if s:
            return level
        return "function_only" if f else "detected_only"
    if level in ("function_only", "function_perturbed"):
        if f:
            return level
        return "surface_only" if s else "detected_only"
    return level


def flanks(seq: str, insert_after: int) -> tuple[str, str | None, str]:
    """``(residue_before, residue_after, residue_label)`` for a 1-based junction.

    Matches the convention of the served rows: ``residue_before`` is residue
    ``insert_after`` itself, ``residue_after`` the next one (``None`` past the
    C-terminus), and the label is ``{residue_before}{insert_after}``.
    """
    if not 1 <= insert_after <= len(seq):
        raise ValueError(f"insert_after {insert_after} outside 1..{len(seq)}")
    before = seq[insert_after - 1]
    after = seq[insert_after] if insert_after < len(seq) else None
    return before, after, f"{before}{insert_after}"


def _range_label(seq: str, span: tuple[int, int]) -> str:
    a, b = span
    return f"{seq[a - 1]}{a}-{seq[b - 1]}{b}"


def _frame(basis: str) -> str | None:
    """``position_frame`` for a corrected row: the frame the paper numbered in.

    Mirrors the Worker's vocabulary (``mature``, ``isoform:...``) and extends
    it with ``ortholog:<species>``. A junction re-read from the paper's own
    flanking residues, or already in human canonical numbering, has no
    foreign frame.
    """
    b = basis.strip()
    if b in (
        "",
        "none",
        "uniprot_canonical_human",
        "flanking_residues_only",
        "loop_only",
    ):
        return None
    if b == "mature_protein":
        return "mature"
    return b


def _audit_note(a: dict[str, str], *, extra: str) -> str:
    quote = a["paper_quote"].strip().replace("\n", " ")
    return (
        f"[Literature audit 2026-11-05 ({AUDIT_REF}), verdict {a['verdict']}: {extra} "
        f'Paper (PMID {a["pmid"]}): "{quote}". Audit note: {a["notes"].strip()}]'
    )


def build_corrections(
    before_rows: list[dict[str, Any]],
    audit_rows: list[dict[str, str]],
    sequences: dict[str, str],
    *,
    version: str,
    synced_at: str,
    topologies: dict[str, str] | None = None,
) -> list[Correction]:
    """Apply the audit to ``before_rows`` (the rows as served, keyed by site_id).

    Returns one :class:`Correction` per audited row. ``action`` is ``delete``
    for withdrawn verdicts, ``update`` when any served column changes, and
    ``keep`` otherwise (``row`` is still the full row so a re-run can rewrite
    it under the new version). Raises on an audit row with no served row, a
    missing sequence, or a verdict this module does not know.

    ``topologies`` maps accession -> per-residue DeepTMHMM string (``I`` /
    ``M`` / ``O``). It is read only when a region row gains a residue: such a
    row was served with ``extracellular = 0`` / ``compartment = 'unknown'``
    (the region shape), and the pinned junction needs the topology state the
    residue rows carry.
    """
    topologies = topologies or {}
    by_id = {r["site_id"]: r for r in before_rows}
    out: list[Correction] = []
    for a in audit_rows:
        sid = a["site_id"]
        if sid not in by_id:
            raise KeyError(f"audit row {sid} has no served row in the snapshot")
        src = by_id[sid]
        verdict = a["verdict"].strip()
        orig = src.get("insert_after_residue")
        orig_i = int(orig) if orig not in (None, "") else None
        if verdict in DROP_VERDICTS:
            out.append(
                Correction(
                    site_id=sid,
                    uniprot_acc=src["uniprot_acc"],
                    gene_symbol=src["gene_symbol"],
                    verdict=verdict,
                    action="delete",
                    residue_before_audit=orig_i,
                    residue_after_audit=None,
                    validation_before=src.get("validation_level"),
                    validation_after=None,
                    row=None,
                )
            )
            continue
        if verdict not in KEEP_VERDICTS:
            raise ValueError(f"{sid}: unknown verdict {verdict!r}")

        row = {c: src.get(c) for c in COLUMNS}
        row["tag_sites_version"] = version
        row["synced_at"] = synced_at
        notes: list[str] = []

        vl_before = src.get("validation_level")
        vl_after = lowered_validation_level(
            vl_before, surface=a["surface_shown"], function=a["function_shown"]
        )
        if vl_after != vl_before:
            row["validation_level"] = vl_after
            notes.append(
                f"validation_level {vl_before} -> {vl_after} (paper reports "
                f"surface: {a['surface_shown']}, function: {a['function_shown']})."
            )

        new_residue: int | None = orig_i
        gains_residue = (
            orig_i is None
            and verdict in ("confirmed_exact", "confirmed_shifted")
            and a["corrected_residue"].strip() != ""
        )
        if verdict == "confirmed_shifted" or gains_residue:
            seq = sequences.get(src["uniprot_acc"])
            if not seq:
                raise KeyError(f"{sid}: no canonical sequence for {src['uniprot_acc']}")
            new_residue = int(a["corrected_residue"])
            before, after, label = flanks(seq, new_residue)
            row.update(
                insert_after_residue=new_residue,
                residue_before=before,
                residue_after=after,
                residue_label=label,
                position_frame=_frame(a["paper_numbering_basis"]),
            )
            if gains_residue:
                topo = topologies.get(src["uniprot_acc"], "")
                state = topo[new_residue - 1] if len(topo) >= new_residue else None
                row.update(
                    residue_range=None,
                    position_evidence="validated",
                    cited_tag_residue=None,
                    topology_state=state,
                    extracellular=1 if state == "O" else 0,
                    compartment=(
                        "extracellular"
                        if state == "O"
                        else "intracellular"
                        if state == "I"
                        else "unknown"
                    ),
                )
                notes.insert(
                    0,
                    (
                        f"insert_after_residue NULL -> {new_residue}: the paper pins the "
                        f"junction on human canonical {src['uniprot_acc']} (paper numbering: "
                        f"{a['paper_numbering_basis']}, construct species: "
                        f"{a['species_of_construct']})."
                    ),
                )
            else:
                notes.insert(
                    0,
                    (
                        f"insert_after_residue {orig_i} -> {new_residue} on human canonical "
                        f"{src['uniprot_acc']} (paper numbering: {a['paper_numbering_basis']}, "
                        f"construct species: {a['species_of_construct']})."
                    ),
                )
        elif verdict == "region_only" and orig_i is None:
            # Already served as a region row (the ``*-internal-None-lit`` shape)
            # and the audit could not pin a junction either: the shape stays,
            # only the validation level may move.
            if notes:
                notes.insert(0, "region-level site confirmed; no junction recoverable.")
        elif verdict == "region_only":
            if sid not in REGION_LABELS:
                raise KeyError(f"{sid}: region_only row has no entry in REGION_LABELS")
            label, span = REGION_LABELS[sid]
            seq = sequences.get(src["uniprot_acc"])
            new_residue = None
            row.update(
                insert_after_residue=None,
                residue_before="",
                residue_after="",
                residue_label=label,
                residue_range=_range_label(seq, span) if (span and seq) else None,
                topology_state=None,
                extracellular=0,
                compartment="unknown",
                evidence_type="published tag insertion in the same loop or domain",
                position_evidence="inferred",
                cited_tag_residue=orig_i,
                position_frame=_frame(a["paper_numbering_basis"]),
            )
            notes.insert(
                0,
                (
                    f"insert_after_residue {orig_i} -> NULL; the paper names a region, not "
                    f"a junction (region: {label})."
                ),
            )
        elif notes:
            notes.insert(0, "position confirmed at this residue.")

        if notes:
            row["rationale"] = (
                _audit_note(a, extra=" ".join(notes))
                + " "
                + (src.get("rationale") or "")
            )
        changed = any(
            row[c] != src.get(c)
            for c in COLUMNS
            if c not in ("tag_sites_version", "synced_at")
        )
        out.append(
            Correction(
                site_id=sid,
                uniprot_acc=src["uniprot_acc"],
                gene_symbol=src["gene_symbol"],
                verdict=verdict,
                action="update" if changed else "keep",
                residue_before_audit=orig_i,
                residue_after_audit=new_residue,
                validation_before=vl_before,
                validation_after=vl_after,
                row=row,
            )
        )
    return out


def summarize(corrections: list[Correction]) -> dict[str, Any]:
    """Counts a report needs: per verdict, per action, validation drops, biggest shifts."""
    by_verdict: dict[str, int] = {}
    by_action: dict[str, int] = {}
    vl_changes: dict[str, int] = {}
    for c in corrections:
        by_verdict[c.verdict] = by_verdict.get(c.verdict, 0) + 1
        by_action[c.action] = by_action.get(c.action, 0) + 1
        if c.action != "delete" and c.validation_after != c.validation_before:
            k = f"{c.validation_before} -> {c.validation_after}"
            vl_changes[k] = vl_changes.get(k, 0) + 1
    shifts = sorted(
        (c for c in corrections if c.verdict == "confirmed_shifted"),
        key=lambda c: abs(c.shift or 0),
        reverse=True,
    )
    return {
        "n_audited": len(corrections),
        "by_verdict": dict(sorted(by_verdict.items())),
        "by_action": dict(sorted(by_action.items())),
        "validation_level_changes": dict(sorted(vl_changes.items())),
        "largest_shifts": [
            {
                "site_id": c.site_id,
                "from": c.residue_before_audit,
                "to": c.residue_after_audit,
                "shift": c.shift,
            }
            for c in shifts[:5]
        ],
        "deleted": sorted(c.site_id for c in corrections if c.action == "delete"),
    }


def dump_rows(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=1, sort_keys=True) + "\n", encoding="utf-8")
