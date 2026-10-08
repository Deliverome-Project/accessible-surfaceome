"""Score tag-site predictions against the curated positive controls.

Diffing a run against the pipeline's own prior output measures churn, not
correctness: it scores a gene going 3 sites -> 0 as an improvement while the one
真 answer is missed by both. ``data/tag_sites/positive_controls.tsv`` carries
per-gene junctions that were read off the source papers by hand, so it is the
only thing here that can answer "did the agent find the known site".
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Control:
    """One curated row: a published tag insertion at a known junction."""

    id: str
    gene_symbol: str
    accession: str
    site_kind: str
    junction: int | None
    expected_residue: str | None
    source_key: str


@dataclass
class Report:
    outcomes: dict[str, str] = field(default_factory=dict)  # control id -> exact|near|miss

    @property
    def n_exact(self) -> int:
        return sum(1 for v in self.outcomes.values() if v == "exact")

    @property
    def n_near(self) -> int:
        return sum(1 for v in self.outcomes.values() if v == "near")

    @property
    def n_miss(self) -> int:
        return sum(1 for v in self.outcomes.values() if v == "miss")

    @property
    def n_total(self) -> int:
        return len(self.outcomes)


def load_controls(path: str | Path) -> list[Control]:
    """Parse the controls TSV. Rows without an integer junction are skipped —
    a control with no pinned residue cannot score a prediction."""
    out: list[Control] = []
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            raw = (row.get("junction_after_residue") or "").strip()
            try:
                junction = int(raw)
            except ValueError:
                continue
            out.append(
                Control(
                    id=(row.get("id") or "").strip(),
                    gene_symbol=(row.get("gene_symbol") or "").strip(),
                    accession=(row.get("accession") or "").strip(),
                    site_kind=(row.get("site_kind") or "").strip(),
                    junction=junction,
                    expected_residue=(row.get("expected_residue") or "").strip() or None,
                    source_key=(row.get("source_key") or "").strip(),
                )
            )
    return out


def score_predictions(
    predicted_by_gene: dict[str, list[int]],
    controls: list[Control],
    *,
    tolerance: int = 0,
) -> Report:
    """Score each control as ``exact`` / ``near`` (within ``tolerance``) / ``miss``.

    Scored per CONTROL, not per prediction: a gene carrying four controls at one
    junction (ITGB1's ALFA / eGFP / pHluorin / HaloTag rows) is satisfied four
    times by one correct call, and a gene with no prediction at all is a miss
    rather than an error."""
    rep = Report()
    for c in controls:
        preds = predicted_by_gene.get(c.gene_symbol) or []
        if c.junction in preds:
            rep.outcomes[c.id] = "exact"
        elif any(abs(p - c.junction) <= tolerance for p in preds):
            rep.outcomes[c.id] = "near"
        else:
            rep.outcomes[c.id] = "miss"
    return rep
