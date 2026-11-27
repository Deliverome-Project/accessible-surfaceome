"""Curated benchmark and deterministic scorer for the internalization literature track.

Evaluates ``InternalizationRecord`` outputs against ``data/eval/internalization_benchmark_v1.tsv``
across six biological cohorts (fast constitutive, ligand-switch, therapeutic anchors,
preprint/integrin, measured low/negative, and zero-evidence abstention), measuring:

* overall & per-mode grade accuracy
* quantitative rate recall on targets with known published kinetics
* bogus-quant rate (non-uptake metrics or bare time points stuffed into ``rate_value``)
* mode-hygiene violations (e.g. ADC/antibody assays misfiled into ``basal``)
* species fidelity, abstention accuracy, reference-PMID recall, and true $/gene cost.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from accessible_surfaceome.agents.internalization.models import (
    InternalizationObservation,
    InternalizationRecord,
)
from accessible_surfaceome.env import REPO_ROOT

DEFAULT_BENCHMARK_PATH = REPO_ROOT / "data" / "eval" / "internalization_benchmark_v1.tsv"

# Units that indicate a bare incubation duration rather than a kinetic rate when
# paired with rate_metric == "other" (e.g. rate_value=30, rate_unit="min", time_point="30 min").
_BARE_TIME_UNIT_RE = re.compile(
    r"^(?:s|sec|secs|second|seconds|min|mins|minute|minutes|h|hr|hrs|hour|hours|d|day|days)$",
    re.IGNORECASE,
)
# Non-internalization readout words that should never sit in quant.rate_unit / quant_summary
# as a numeric rate_value (observed in live v0.1.9 D1 records: cAMP fold, peptide matches).
_BOGUS_QUANT_UNIT_RE = re.compile(
    r"\b(?:camp|peptide\s+match|unique\s+peptide|ic50|ec50|kd|ki|nm|um|μm|mg/kg|da|kda|aa)\b",
    re.IGNORECASE,
)
_EXOGENOUS_BINDER_ASSAYS = frozenset({"adc_internalization", "antibody_uptake"})
_EXOGENOUS_BINDER_RE = re.compile(
    r"\b(?:adc|mab|antibody|trastuzumab|cetuximab|belantamab|enfortumab|inotuzumab|"
    r"rituximab|gemtuzumab|mmae|mmaf|dm1|scfv|nanobody|immunotoxin|conjugate)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class BenchmarkRow:
    gene_symbol: str
    category: str
    overall_allowed: frozenset[str]
    basal_allowed: frozenset[str] | None
    native_ligand_allowed: frozenset[str] | None
    therapeutic_allowed: frozenset[str] | None
    expect_quant: bool
    expected_species: str
    key_pmids: tuple[str, ...]
    notes: str


@dataclass(frozen=True)
class GeneScore:
    gene_symbol: str
    category: str
    overall_grade: str
    overall_confidence: str
    overall_ok: bool
    mode_results: dict[str, tuple[str, bool]]  # mode -> (actual_grade, passed)
    n_observations: int
    n_quant_valid: int
    n_quant_bogus: int
    bogus_quant_reasons: tuple[str, ...]
    n_mode_violations: int
    mode_violation_reasons: tuple[str, ...]
    expect_quant: bool
    quant_ok: bool | None  # None when expect_quant is False
    species_scope: str
    species_ok: bool | None  # None when expected_species == "any"
    abstention_ok: bool | None  # None unless category == "abstention"
    ref_pmids_hit: tuple[str, ...]
    ref_pmids_total: int
    cost_usd: float | None
    n_refusals: int
    n_papers_discovered: int
    n_papers_fetched: int


@dataclass
class BenchmarkSummary:
    scores: list[GeneScore] = field(default_factory=list)

    @property
    def n_genes(self) -> int:
        return len(self.scores)

    @property
    def overall_accuracy(self) -> float:
        return (
            sum(1 for s in self.scores if s.overall_ok) / len(self.scores)
            if self.scores
            else 0.0
        )

    @property
    def mode_accuracy(self) -> float:
        checks = [ok for s in self.scores for _, ok in s.mode_results.values()]
        return sum(1 for ok in checks if ok) / len(checks) if checks else 0.0

    @property
    def quant_recall(self) -> float:
        q = [s for s in self.scores if s.quant_ok is not None]
        return sum(1 for s in q if s.quant_ok) / len(q) if q else 0.0

    @property
    def total_valid_quant(self) -> int:
        return sum(s.n_quant_valid for s in self.scores)

    @property
    def total_bogus_quant(self) -> int:
        return sum(s.n_quant_bogus for s in self.scores)

    @property
    def total_mode_violations(self) -> int:
        return sum(s.n_mode_violations for s in self.scores)

    @property
    def species_accuracy(self) -> float:
        sp = [s for s in self.scores if s.species_ok is not None]
        return sum(1 for s in sp if s.species_ok) / len(sp) if sp else 0.0

    @property
    def abstention_accuracy(self) -> float:
        ab = [s for s in self.scores if s.abstention_ok is not None]
        return sum(1 for s in ab if s.abstention_ok) / len(ab) if ab else 0.0

    @property
    def mean_cost_usd(self) -> float | None:
        costs = [s.cost_usd for s in self.scores if s.cost_usd is not None and s.cost_usd > 0]
        return sum(costs) / len(costs) if costs else None

    @property
    def total_refusals(self) -> int:
        return sum(s.n_refusals for s in self.scores)

    @property
    def total_cost_usd(self) -> float:
        return sum(s.cost_usd for s in self.scores if s.cost_usd is not None)


def _parse_allowed(val: str) -> frozenset[str] | None:
    s = (val or "").strip()
    if not s or s == "*":
        return None
    return frozenset(p.strip().lower() for p in s.split("|") if p.strip())


def load_benchmark(path: Path | None = None) -> list[BenchmarkRow]:
    p = path or DEFAULT_BENCHMARK_PATH
    rows: list[BenchmarkRow] = []
    with p.open(newline="", encoding="utf-8") as fh:
        for raw in csv.DictReader(fh, delimiter="\t"):
            rows.append(
                BenchmarkRow(
                    gene_symbol=raw["gene_symbol"].strip().upper(),
                    category=raw["category"].strip(),
                    overall_allowed=_parse_allowed(raw["overall_allowed"]) or frozenset(),
                    basal_allowed=_parse_allowed(raw["basal_allowed"]),
                    native_ligand_allowed=_parse_allowed(raw["native_ligand_allowed"]),
                    therapeutic_allowed=_parse_allowed(raw["therapeutic_allowed"]),
                    expect_quant=raw["expect_quant"].strip().lower() == "yes",
                    expected_species=raw["expected_species"].strip().lower() or "any",
                    key_pmids=tuple(
                        x.strip() for x in (raw.get("key_pmids") or "").split("|") if x.strip()
                    ),
                    notes=(raw.get("notes") or "").strip(),
                )
            )
    return rows


def check_observation_quant_issue(obs: InternalizationObservation | dict[str, Any]) -> str | None:
    """Return a short reason string if a populated ``rate_value`` is bogus, else None."""
    q = obs.quant if isinstance(obs, InternalizationObservation) else (obs.get("quant") or {})
    metric = q.rate_metric if not isinstance(q, dict) else q.get("rate_metric")
    val = q.rate_value if not isinstance(q, dict) else q.get("rate_value")
    unit = (q.rate_unit if not isinstance(q, dict) else q.get("rate_unit")) or ""
    tp = (q.time_point if not isinstance(q, dict) else q.get("time_point")) or ""
    summary = (q.quant_summary if not isinstance(q, dict) else q.get("quant_summary")) or ""

    if val is None:
        return None
    if _BOGUS_QUANT_UNIT_RE.search(unit):
        return f"non-uptake unit in rate_unit: {unit!r}"
    if metric == "other" and _BARE_TIME_UNIT_RE.match(unit.strip()):
        # Distinguish "time_point=30 min" misfiled as rate_value=30 vs real half-life
        if not re.search(r"half[-\s]?(?:life|time)|t\s*1/2|t½|per\s|/", summary, re.IGNORECASE):
            return f"bare time point stuffed into rate_value ({val} {unit}, time_point={tp!r})"
    if metric == "fold_change" and len(summary.strip().split()) < 3:
        return f"fold_change missing comparator in quant_summary: {summary!r}"
    return None


def check_observation_mode_issue(obs: InternalizationObservation | dict[str, Any]) -> str | None:
    """Return a reason if an observation's mode contradicts its assay/ligand."""
    if isinstance(obs, InternalizationObservation):
        mode = obs.internalization_mode
        assay = obs.assay_type
        ligand = obs.ligand_name or ""
    else:
        mode = obs.get("internalization_mode", "unknown")
        assay = obs.get("assay_type", "unknown")
        ligand = obs.get("ligand_name") or ""
    if mode == "basal":
        if assay == "adc_internalization":
            return f"adc_internalization filed under basal (ligand={ligand!r})"
        if assay == "antibody_uptake" and _EXOGENOUS_BINDER_RE.search(ligand):
            # Allow explicitly labelled non-crosslinking monovalent Fab tracers
            if not re.search(r"\b(?:monovalent|fab|tracer|constitutive|basal)\b", ligand, re.IGNORECASE):
                return f"therapeutic antibody {ligand!r} filed under basal"
    return None


def _source_tokens(record: InternalizationRecord | dict[str, Any]) -> set[str]:
    lit = record.literature if isinstance(record, InternalizationRecord) else record.get("literature")
    if not lit:
        return set()
    sources = lit.sources if not isinstance(lit, dict) else (lit.get("sources") or [])
    tokens: set[str] = set()
    for s in sources:
        spans = s.spans if not isinstance(s, dict) else (s.get("spans") or [])
        for sp in spans:
            src = sp.source if not isinstance(sp, dict) else (sp.get("source") or {})
            sid = (src.source_id if not isinstance(src, dict) else src.get("source_id")) or ""
            url = (src.url if not isinstance(src, dict) else src.get("url")) or ""
            for raw in (sid, url):
                if raw:
                    raw_s = str(raw)
                    tokens.add(raw_s.lower())
                    if ":" in raw_s:
                        tokens.add(raw_s.split(":", 1)[1].lower())
    return tokens


def score_record(
    record: InternalizationRecord | dict[str, Any],
    row: BenchmarkRow,
) -> GeneScore:
    lit = record.literature if isinstance(record, InternalizationRecord) else record.get("literature")
    if lit is None:
        raise ValueError(f"{row.gene_symbol}: record has no literature track")

    def _get(obj: Any, key: str, default: Any = None) -> Any:
        return obj.get(key, default) if isinstance(obj, dict) else getattr(obj, key, default)

    overall_grade = str(_get(lit, "overall_grade", "unknown"))
    overall_conf = str(_get(lit, "overall_confidence", "low"))
    gbm = _get(lit, "grades_by_mode", {})
    mode_results: dict[str, tuple[str, bool]] = {}
    for mode_name, allowed in (
        ("basal", row.basal_allowed),
        ("native_ligand", row.native_ligand_allowed),
        ("therapeutic", row.therapeutic_allowed),
    ):
        if allowed is None:
            continue
        mg = _get(gbm, mode_name, {})
        actual = str(_get(mg, "grade", "unknown"))
        mode_results[mode_name] = (actual, actual in allowed)

    obs_list = _get(lit, "observations", []) or []
    n_quant_valid = 0
    bogus_reasons: list[str] = []
    mode_reasons: list[str] = []
    for o in obs_list:
        q = _get(o, "quant", {}) or {}
        val = _get(q, "rate_value", None)
        if val is not None:
            issue = check_observation_quant_issue(o)
            if issue:
                bogus_reasons.append(issue)
            else:
                n_quant_valid += 1
        m_issue = check_observation_mode_issue(o)
        if m_issue:
            mode_reasons.append(m_issue)

    species_scope = str(_get(lit, "species_scope", "unspecified"))
    species_ok: bool | None = None
    if row.expected_species == "human":
        species_ok = species_scope in ("human", "mixed")

    abstention_ok: bool | None = None
    if row.category == "abstention":
        abstention_ok = overall_grade == "unknown" and len(obs_list) == 0

    src_tokens = _source_tokens(record)
    hits = tuple(
        ref for ref in row.key_pmids if any(ref.lower() in tok for tok in src_tokens)
    )

    raw_cost = _get(lit, "cost_usd", None)
    cost_usd = float(raw_cost) if raw_cost is not None else None

    return GeneScore(
        gene_symbol=row.gene_symbol,
        category=row.category,
        overall_grade=overall_grade,
        overall_confidence=overall_conf,
        overall_ok=overall_grade in row.overall_allowed,
        mode_results=mode_results,
        n_observations=len(obs_list),
        n_quant_valid=n_quant_valid,
        n_quant_bogus=len(bogus_reasons),
        bogus_quant_reasons=tuple(bogus_reasons),
        n_mode_violations=len(mode_reasons),
        mode_violation_reasons=tuple(mode_reasons),
        expect_quant=row.expect_quant,
        quant_ok=(n_quant_valid > 0) if row.expect_quant else None,
        species_scope=species_scope,
        species_ok=species_ok,
        abstention_ok=abstention_ok,
        ref_pmids_hit=hits,
        ref_pmids_total=len(row.key_pmids),
        cost_usd=cost_usd,
        n_refusals=int(_get(lit, "n_refusals", 0) or 0),
        n_papers_discovered=int(_get(lit, "n_papers_discovered", 0) or 0),
        n_papers_fetched=int(_get(lit, "n_papers_fetched", 0) or 0),
    )


def format_report(summary: BenchmarkSummary, *, cohort_size: int = 3011) -> str:
    lines: list[str] = []
    lines.append(
        f"{'Gene':10s} {'Cat':18s} {'Overall':12s} {'OK':3s} "
        f"{'Modes':24s} {'Obs':>3s} {'Q+':>3s} {'Q!':>3s} {'MV':>2s} {'Rf':>2s} "
        f"{'Sp':>7s} {'Ref':>5s} {'Cost':>7s}"
    )
    lines.append("-" * 112)
    for s in summary.scores:
        modes_str = " ".join(
            f"{m[0].upper()}:{g[:3]}{'✓' if ok else '✗'}"
            for m, (g, ok) in s.mode_results.items()
        )
        cost_str = f"${s.cost_usd:.3f}" if s.cost_usd is not None else "n/a"
        ref_str = f"{len(s.ref_pmids_hit)}/{s.ref_pmids_total}" if s.ref_pmids_total else "-"
        lines.append(
            f"{s.gene_symbol:10s} {s.category[:18]:18s} "
            f"{s.overall_grade + '(' + s.overall_confidence[:3] + ')':12s} "
            f"{'✓' if s.overall_ok else '✗':3s} "
            f"{modes_str:24s} {s.n_observations:3d} {s.n_quant_valid:3d} "
            f"{s.n_quant_bogus:3d} {s.n_mode_violations:2d} {s.n_refusals:2d} "
            f"{s.species_scope[:7]:>7s} {ref_str:>5s} {cost_str:>7s}"
        )
    lines.append("-" * 112)
    lines.append(
        f"Overall grade accuracy : {summary.overall_accuracy:.1%} "
        f"({sum(1 for s in summary.scores if s.overall_ok)}/{summary.n_genes})"
    )
    n_mode_ok = sum(1 for s in summary.scores for _, ok in s.mode_results.values() if ok)
    n_mode_tot = sum(len(s.mode_results) for s in summary.scores)
    lines.append(f"Mode grade accuracy    : {summary.mode_accuracy:.1%} ({n_mode_ok}/{n_mode_tot})")
    n_q_ok = sum(1 for s in summary.scores if s.quant_ok is True)
    n_q_tot = sum(1 for s in summary.scores if s.quant_ok is not None)
    lines.append(
        f"Quantitative recall    : {summary.quant_recall:.1%} ({n_q_ok}/{n_q_tot} quant-expected genes; "
        f"{summary.total_valid_quant} valid rates, {summary.total_bogus_quant} bogus)"
    )
    lines.append(f"Mode-hygiene violations: {summary.total_mode_violations}")
    lines.append(f"Model refusals         : {summary.total_refusals}")
    n_sp_ok = sum(1 for s in summary.scores if s.species_ok is True)
    n_sp_tot = sum(1 for s in summary.scores if s.species_ok is not None)
    lines.append(f"Species accuracy       : {summary.species_accuracy:.1%} ({n_sp_ok}/{n_sp_tot})")
    n_ab_ok = sum(1 for s in summary.scores if s.abstention_ok is True)
    n_ab_tot = sum(1 for s in summary.scores if s.abstention_ok is not None)
    if n_ab_tot:
        lines.append(f"Abstention accuracy    : {summary.abstention_accuracy:.1%} ({n_ab_ok}/{n_ab_tot})")
    if summary.mean_cost_usd is not None:
        proj = summary.mean_cost_usd * cohort_size
        lines.append(
            f"Cost                   : total=${summary.total_cost_usd:.3f} | "
            f"mean=${summary.mean_cost_usd:.3f}/gene | "
            f"projected {cohort_size} genes = ${proj:,.0f}"
        )
    return "\n".join(lines)
