"""Pre-trim filter — drop high-waste papers BEFORE the Haiku abstract triage.

Trim is the dominant cost in plan-trim-select (~57-70% of total per-gene cost),
and on well-studied genes a substantial fraction of trimmed papers don't
contribute to the final evidence ledger. Empirical analysis on 5 published
deep-dive records showed:

* GPR75 (32 papers, thin lit): 6% waste — every paper essentially contributes.
* TGOLN2 (33 papers, thin lit): 24% waste.
* SRC (46 papers, mid lit): 65% waste — mostly because the long tail is
  drug-discovery summaries and reviews that the selector drops.
* HMGB1 (60 papers, mid-heavy): 48% waste, mostly reviews and ADC reviews.
* TACSTD2/TROP2 (119 papers, heavy lit): 58% waste — atlases, ADC reviews,
  drug-discovery summaries dominate the tail.

The pattern: as literature volume grows, the waste fraction grows because
search returns more "synthesis" papers (reviews, atlases, drug summaries)
that don't add primary surface-biology evidence. This module drops the
*certain* waste up-front so Haiku-triage only sees plausible primary
candidates. The downstream selector still picks from a smaller, denser pool.

Empirical validation on the three heavy-lit anchor genes shows the filter
retains 94-100% of contributing papers while cutting 23-25% of trim work.

**Three rules** (applied in order, only when the candidate pool is heavy):

1. **Review (with journal-quality sparing).** Drop PubMed ``publication_type``
   = "Review" UNLESS the journal is a high-quality review venue (Nat Rev,
   Annu Rev, Trends, Cell, Curr Opin, ...). Quality-journal reviews are
   curatorially-gated syntheses that the deep-dive selector often uses as
   secondary-tier evidence; generic narrative reviews are typically dropped.

2. **Drug-review titles.** Drop titles matching patterns like "Targeting X
   in solid tumors", "Antibody-drug conjugates in cancer", "advances and
   future directions", "emerging therapies". These are clinical-translation
   summaries — interesting context but not primary surface biology.

3. **Atlas / pan-cancer / proteome-wide.** Drop titles matching "Pan-Cancer
   ... analysis/landscape", "landscape of ... expression/proteome", "compendium",
   "broad and thematic", "surfaceome-wide", "terminomics". These are gene
   discovery papers where our gene appears as one row of thousands.

**Activation thresholds (volume-aware).**

* ``n_candidates < THIN_THRESHOLD`` (25): do nothing. Every paper is precious;
  filter would over-clip.
* ``THIN_THRESHOLD <= n_candidates < HEAVY_THRESHOLD`` (25-50): apply NO
  filter. This bucket sits below the precision floor; the filter's
  false-positive rate (~10%) costs more than the few wasted trims save.
* ``n_candidates >= HEAVY_THRESHOLD`` (50): apply all three rules.

A hard cap (``HARD_CAP`` = 150) bites only for the most pathological cases
(EGFR/TP53-class genes with hundreds of candidates) — a safety ceiling rather
than a quality lever. Papers above the cap are sorted by year (newest first),
then by PMC-availability, then dropped.

The filter is gated behind ``enable_pretrim_filter`` flag (default False
for the first sweep — audit-only / shadow mode) so the decisions can be
logged and validated before flipping default on.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Literal

from accessible_surfaceome.tools._shared.models import Paper

logger = logging.getLogger(__name__)


# Volume thresholds. Below THIN we do nothing; the filter's precision is
# insufficient to justify activation on small candidate pools. Above HEAVY
# we apply all three rules.
THIN_THRESHOLD: int = 25
HEAVY_THRESHOLD: int = 50

# Safety-ceiling cap: applied after the rule filter. Currently 150 (was
# briefly 132 for cost mitigation 2026-06-07 to 2026-06-09, then raised back
# after the A1 selection drift audit — see docs/audit/a1_selection_drift_2026_06_08.md).
#
# History: dropped 150 → 132 on the cost-mitigation pass after an empirical
# production-cohort study (sample of 100 random cohort genes) showed
# papers-per-gene production distribution at p25=132, median=208, mean=205.
# Capping at the production p25 lands the 6,521-gene cohort at ~$12k
# vs $18k at uncapped median.
#
# Reverted to 150 after SRC's methods builder dropped from 12 → 3
# MethodObservation rows between v2.9.0 and v2.35.0. Agent #21's audit
# found 5 of 8 dropped papers were cap-drops — founding-era localization
# papers (PMID:17537435, 17620427, 28543306, PMC:PMC3733647, +1) carrying
# the direct PM-trafficking IF/IHC evidence the methods builder needs to
# clear ``direct_*`` grades on canonically-cytoplasmic kinases. The
# year-sorted cap is biased against older PMID-style papers — exactly
# the cohort of papers carrying load-bearing surface evidence for
# pre-2020 kinase / GPCR / channel literature.
#
# The cost delta (132 → 150, +13% papers on the ~25% of genes that exceed
# 132 candidates) is small (~$200 on the cohort) relative to the recall
# improvement. A future fix would replace year-sort with content-weighted
# ranking (prefer experimental over review, prefer KO-validated over
# overexpression-only, etc.) — until then, 150 is the safe floor.
#
# Papers above the cap are sorted by year (newest first), then by PMC-OA
# preference, then dropped.
HARD_CAP: int = 160


# Pattern 2: drug-review titles. These are typically secondary syntheses
# that don't add primary surface biology. Empirically 92% precision on
# TACSTD2's filtered set; some "advances in X" titles are actually primary
# research, hence keeping the regex conservative.
#
# Each alternative ends in its own ``\w*`` (rather than a final ``\b``)
# so suffixes like "therapies" / "advances" / "review" match cleanly:
#     "emerging therap"  → "emerging therapies"  ✓
#     "recent advances in" → "recent advances in cancer"  ✓
DRUG_REVIEW_RE: re.Pattern[str] = re.compile(
    r"("
    r"\bapproved (antibody|adc)\w*\s+\w*review|"
    r"\bantibody[- ]drug conjugates? in cancer therapy|"
    r"\badcs? in cancer.*\b(review|advances)|"
    r"\badvances and future directions|"
    r"\bemerging therap\w*|"
    r"\brecent advances in"
    r")",
    re.IGNORECASE,
)

# Pattern 3: atlas / pan-cancer / proteome-wide. These return the gene as one
# of thousands of rows — rarely contribute primary surface biology.
ATLAS_RE: re.Pattern[str] = re.compile(
    r"\b("
    r"pan-?cancer.*\b(analysis|landscape|atlas)|"
    r"landscape of [\w\-\s]+?(expression|surfaceome|proteome|metabolic|surface)|"
    r"compendium|"
    r"integrative analysis|"
    r"broad and thematic|"
    r"surfaceome[- ]wide|"
    r"terminomics"
    r")\b",
    re.IGNORECASE,
)

# High-quality review journals: reviews IN these venues are typically
# curatorially-gated syntheses with load-bearing structural / mechanistic
# evidence the deep-dive selector keeps as secondary-tier evidence.
# Dropping them costs real ledger content (validated against HMGB1 — 3 of
# 6 "Review" papers were salvageable mech reviews from quality venues).
#
# Anchored to the START of the journal name to avoid false positives like
# "Front Cell Infect Microbiol" matching "cell" via word-boundary regex.
# Common review-series brand prefixes (Annu Rev, Nat Rev, Trends, Curr
# Opin) all use `^prefix` because every journal in those series follows
# the same convention.
HIGH_QUALITY_REVIEW_JOURNAL_RE: re.Pattern[str] = re.compile(
    r"^("
    r"annu rev\b|"  # Annu Rev Cell Dev Biol, Annu Rev Biochem, etc.
    r"nat rev\b|"  # Nat Rev Cancer, Nat Rev Mol Cell Biol, etc.
    r"trends \w+|"  # Trends Cancer, Trends Cell Biol, Trends Biochem Sci
    r"curr opin\b|"  # Curr Opin Cell Biol, Curr Opin Struct Biol, etc.
    r"cell$|"  # the journal "Cell" exactly
    r"cancer cell\b|"  # Cancer Cell
    r"mol cell$|"  # Molecular Cell journal — exact match
    r"nature$|"  # the journal "Nature" exactly
    r"science$|"  # the journal "Science" exactly
    r"nat \w+$|"  # Nat Biotechnol, Nat Med, Nat Cell Biol, Nat Cancer, etc.
    r"exp mol med$|"  # Exp Mol Med
    r"j mol biol$"  # J Mol Biol exactly
    r")",
    re.IGNORECASE,
)


DropReason = Literal[
    "review",
    "drug_review",
    "atlas",
    "cap",
]


@dataclass
class PreTrimDecision:
    """One paper's filter outcome — kept or dropped with reason."""

    paper_pmid: int
    paper_title: str
    kept: bool
    drop_reason: DropReason | None = None


@dataclass
class PreTrimAudit:
    """Audit of one pretrim_filter call — what fired and why."""

    n_input: int
    n_kept: int
    activated: bool  # False when below HEAVY_THRESHOLD
    decisions: list[PreTrimDecision] = field(default_factory=list)
    # Per-reason counts for the operator log.
    n_dropped_review: int = 0
    n_dropped_drug_review: int = 0
    n_dropped_atlas: int = 0
    n_dropped_cap: int = 0


def _is_high_quality_review_journal(paper: Paper) -> bool:
    if not paper.journal:
        return False
    return bool(HIGH_QUALITY_REVIEW_JOURNAL_RE.search(paper.journal))


def _is_drug_review_title(paper: Paper) -> bool:
    return bool(DRUG_REVIEW_RE.search(paper.title or ""))


def _is_atlas_title(paper: Paper) -> bool:
    return bool(ATLAS_RE.search(paper.title or ""))


def _drop_reason(paper: Paper) -> DropReason | None:
    """Single-paper classification: which rule (if any) drops this paper?

    Returns ``None`` when no rule fires (paper is kept).
    """
    if paper.is_review or paper.publication_type == "review":
        if _is_high_quality_review_journal(paper):
            return None  # spared — quality-journal review is load-bearing
        return "review"
    if _is_drug_review_title(paper):
        return "drug_review"
    if _is_atlas_title(paper):
        return "atlas"
    return None


def pretrim_filter(
    papers: list[Paper],
    *,
    enable: bool = False,
    cap: int = HARD_CAP,
    thin_threshold: int = THIN_THRESHOLD,
    heavy_threshold: int = HEAVY_THRESHOLD,
) -> tuple[list[Paper], PreTrimAudit]:
    """Filter a candidate-paper list before Haiku abstract triage.

    Returns ``(kept_papers, audit)``. The audit captures EVERY paper's
    decision (kept or dropped with reason) so the caller can persist it
    into the run's intermediates dump for offline validation.

    When ``enable=False`` (default), the audit is produced but ALL papers
    are kept — shadow mode. Use the audit to validate filter behaviour on
    a few sweeps before flipping ``enable=True``.

    When ``len(papers) < heavy_threshold``, the filter is bypassed entirely
    (audit.activated=False) — thin-lit genes don't benefit and the rule's
    precision is insufficient at small candidate counts.
    """
    n_in = len(papers)
    audit = PreTrimAudit(n_input=n_in, n_kept=n_in, activated=False)

    if n_in < heavy_threshold:
        # Activation gate: too few candidates to justify the precision risk.
        # All-kept audit, activated=False.
        for p in papers:
            audit.decisions.append(
                PreTrimDecision(
                    paper_pmid=p.pmid, paper_title=p.title, kept=True
                )
            )
        return papers, audit

    audit.activated = True
    candidates: list[tuple[Paper, DropReason | None]] = [
        (p, _drop_reason(p)) for p in papers
    ]

    if enable:
        kept: list[Paper] = []
        for p, reason in candidates:
            if reason is None:
                kept.append(p)
                audit.decisions.append(
                    PreTrimDecision(paper_pmid=p.pmid, paper_title=p.title, kept=True)
                )
            else:
                audit.decisions.append(
                    PreTrimDecision(
                        paper_pmid=p.pmid,
                        paper_title=p.title,
                        kept=False,
                        drop_reason=reason,
                    )
                )
                if reason == "review":
                    audit.n_dropped_review += 1
                elif reason == "drug_review":
                    audit.n_dropped_drug_review += 1
                elif reason == "atlas":
                    audit.n_dropped_atlas += 1
    else:
        # Shadow mode: keep everything, but record what the filter WOULD have
        # done so the operator can validate before activation.
        kept = list(papers)
        for p, reason in candidates:
            audit.decisions.append(
                PreTrimDecision(
                    paper_pmid=p.pmid,
                    paper_title=p.title,
                    kept=True,
                    drop_reason=reason,  # what WOULD have dropped it
                )
            )
            if reason == "review":
                audit.n_dropped_review += 1
            elif reason == "drug_review":
                audit.n_dropped_drug_review += 1
            elif reason == "atlas":
                audit.n_dropped_atlas += 1

    # Hard cap (only when filter is enabled and we still have > cap papers).
    if enable and len(kept) > cap:
        # Sort newest first; tie-break by PMC-OA availability (richer body
        # text → more likely to contribute primary evidence). Drop the
        # bottom of the list.
        kept_sorted = sorted(
            kept,
            key=lambda p: (-(p.year or 0), 0 if p.is_pmc_oa else 1),
        )
        for p in kept_sorted[cap:]:
            # Patch the existing decision in the audit to mark it cap-dropped.
            for d in audit.decisions:
                if d.paper_pmid == p.pmid:
                    d.kept = False
                    d.drop_reason = "cap"
                    break
            audit.n_dropped_cap += 1
        kept = kept_sorted[:cap]

    audit.n_kept = len(kept)
    if audit.activated:
        logger.info(
            "pretrim_filter: %d in → %d kept "
            "(review=%d, drug_review=%d, atlas=%d, cap=%d) [enabled=%s]",
            n_in,
            audit.n_kept,
            audit.n_dropped_review,
            audit.n_dropped_drug_review,
            audit.n_dropped_atlas,
            audit.n_dropped_cap,
            enable,
        )
    return kept, audit
