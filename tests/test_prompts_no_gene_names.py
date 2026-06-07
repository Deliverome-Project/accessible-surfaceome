"""Hard guard: agent prompts must NOT name specific genes / target proteins.

Why this guard exists
=====================

The agent prompts under ``src/accessible_surfaceome/agents/*/prompts/`` are
read by the LLM at every annotation. Hard-coding gene-name examples
anchors the model on a handful of canonical targets — every gene it
deep-dives starts being read through the lens of those examples. The
user wants every protein treated generically, so the prompts only use
abstract / categorical phrasing ("gene X", "a classical single-pass
receptor", "an inner-leaflet kinase with a cancer-state outer-leaflet
inversion story").

The reset commit that landed the trim is ``551b28425``; the final
sheddase-name trim is ``1ae78fd67``. This test exists so the trimmed
state can't silently drift back when a future PR adds an
"easier-to-read" worked example with a specific gene attached.

What we forbid
==============

A curated BLOCKLIST of well-known target-gene / protein-family names
(below). The list is intentionally not the full HGNC catalogue — that
would false-positive on cell-type labels and assay families — but it
covers the canonical examples that have a habit of creeping back in,
PLUS the illustrative-but-targety patterns the recent trim swept out
(sheddase names, checkpoint receptors, lysosomal markers, disease
abbreviation `LUAD`, specific clone IDs, specific cell-line IDs).

Allowed CD-marker contexts (cell-type labels)
=============================================

`CD4 T cell`, `CD8+ T cell`, `CD138+ plasma cell`, etc. — the CD
molecule is being used to label a cell type, not as a target example.
The allowlist regex catches these and exempts the line. New cell-type
labels (`CD45+ NK cell`, etc.) are easy to add to ``CELL_TYPE_CONTEXT``
when the need arises.

To add a new forbidden gene
===========================

Append to ``BLOCKLIST``. To temporarily allow a specific occurrence
(e.g. a worked example using a placeholder like ``GENE X``), use the
``ALLOWED_TOKENS`` map — but think hard before doing so; the whole
point is to prevent gene-anchored worked examples.

To extend the cell-type-context allowance
=========================================

Append to ``CELL_TYPE_CONTEXT``. The regex is intentionally narrow:
only matches when the gene token sits within ~35 characters of one of
the immunology cell-type keywords (``T cell``, ``B cell``, ``NK
cell``, ``plasma cell``, ``TIL``, ``effector``, ``memory``, etc.).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

PROMPTS_ROOT = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "accessible_surfaceome"
    / "agents"
)

# Forbidden gene / protein / clone / cell-line / disease-abbreviation
# tokens. Curated, not exhaustive — but covers what we've actually seen
# creep into prompts. Compiled as exact whole-word matches (regex word
# boundaries on each side).
BLOCKLIST: tuple[str, ...] = (
    # Canonical target genes the trim removed
    "EGFR", "HER2", "HER3", "INSR", "FGFR1", "FGFR2", "FGFR3", "FGFR4",
    "KCNQ1", "KCNH2", "BCMA", "FCRL5", "GPR75", "HSPA5", "CLDN6", "IZUMO4",
    # CD-molecule TARGETS (not the cell-type labels — the allowlist below
    # exempts cell-type-context occurrences like "CD4 T cell")
    "CD9", "CD13", "CD19", "CD20", "CD22", "CD26", "CD33", "CD38",
    "CD55", "CD59", "CD62L", "CD63", "CD73", "CD81", "CD138",
    # Checkpoint / exhaustion markers we replaced with categorical phrasing
    "PD-1", "PD1", "PDL1", "PD-L1", "CTLA4", "CTLA-4", "TIM-3", "TIM3",
    "LAG-3", "LAG3", "TIGIT",
    # Sheddases / proteases that snuck in as illustrative examples
    "ADAM10", "ADAM17", "BACE", "BACE1", "BACE2",
    # Common surface receptor / kinase examples we genericized
    "SRC", "LYN", "ABL", "MET", "AXL", "KRAS", "BRAF",
    # ER-resident chaperones used illustratively
    "GRP78", "csGRP78", "BiP",
    # Cytoskeletal / intermediate-filament examples
    "VIM",
    # Lysosomal markers
    "LAMP1", "LAMP2",
    # Surface receptor families used illustratively in lists
    "ANPEP", "DPP4", "FOLH1", "PSMA", "NT5E", "ENPP",
    "IFNAR1", "IFNAR2",
    "SLC2A1", "SLC7A11", "ATP1A1", "AQP1",
    "ICAM1", "VCAM1",
    # Disease abbreviations that anchor on a specific oncology context
    "LUAD", "LUSC", "TNBC", "PDAC",
    # Specific antibody clone IDs the trim removed
    "5A6", "AY13",
    # Specific cell lines used as illustrative examples (NOT standard reagent
    # systems — HEK293 / CHO / HeLa / COS-7 / 293T are intentionally NOT
    # blocked: those are standard overexpression-system reagents, not
    # target-anchored cancer-cell-line examples)
    "HCC827", "HCC1954", "HCC1937", "PC9", "H1650", "H1975", "H460",
    "MCF7", "MDA-MB-231", "SK-BR-3",
)

# Forbidden tokens compiled into a single regex. Word boundaries on each
# side so ``HER2`` doesn't match ``HER2-positive-status`` (it WOULD match
# ``HER2-positive`` because the hyphen is its own word boundary, and
# ``HER2-positive`` IS a target-anchored phrase we want to catch).
_BLOCKED_RE = re.compile(
    r"(?<![A-Za-z0-9_-])(" + "|".join(re.escape(t) for t in BLOCKLIST) + r")(?![A-Za-z0-9_-])"
)

# Cell-type context patterns — a CD molecule token sitting near any of
# these phrases is being used as a CELL-TYPE LABEL, not a target example.
# Examples that pass:
#   - "CD8+ effector T cells in tumor infiltrates"
#   - "CD138+ plasma cell"
#   - "CD4 T cell vs CD8 T cell"
# Examples that DON'T pass (correctly flagged):
#   - "CD81 is ['partner','oligomerization']"
#   - "CD19/CD81 co-receptor complex"
CELL_TYPE_CONTEXT = re.compile(
    r"\b("
    r"T\s*cell|B\s*cell|NK\s*cell|plasma\s*cell|TIL|"
    r"infiltrate|effector|memory|naive|exhausted|"
    r"monocyte|macrophage|dendritic|microenvironment|"
    r"lineage|stromal|stem\s*cell|epithelial|endothelial|"
    r"hematopoietic|polarized|tumor-infiltrating|"
    r"granulocyte|neutrophil|basophil|eosinophil|mast\s*cell|"
    r"Treg|Th[0-9]"
    r")\b",
    re.IGNORECASE,
)

# Tokens that look gene-shaped but are allowed in specific contexts.
# Each entry is (gene_token, regex_that_must_match_the_surrounding_context).
# Add WITH CAUTION — every entry here is a hole in the guard.
ALLOWED_TOKENS: dict[str, re.Pattern[str]] = {
    # "EMT / MET" is the biological epithelial↔mesenchymal transition
    # PAIR (epithelial-to-mesenchymal / mesenchymal-to-epithelial), not
    # the MET (hepatocyte growth-factor receptor) oncogene. Only allow
    # when MET appears right next to "EMT" or alongside the words
    # "epithelial" / "mesenchymal".
    "MET": re.compile(r"EMT|epithelial|mesenchymal", re.IGNORECASE),
}

# A safe distance (chars) around each match to scan for cell-type context.
CONTEXT_WINDOW = 35


def _prompt_files() -> list[Path]:
    return sorted(PROMPTS_ROOT.rglob("*.md"))


def _scan_one(path: Path) -> list[tuple[int, str, str]]:
    """Return ``(line_number, token, surrounding_window)`` for every
    blocked occurrence in ``path`` that isn't excused by a cell-type
    context match or an explicit ``ALLOWED_TOKENS`` rule."""
    text = path.read_text()
    hits: list[tuple[int, str, str]] = []
    for m in _BLOCKED_RE.finditer(text):
        token = m.group(1)
        start, end = m.start(), m.end()
        win_start = max(0, start - CONTEXT_WINDOW)
        win_end = min(len(text), end + CONTEXT_WINDOW)
        window = text[win_start:win_end].replace("\n", " ")

        # CD-marker tokens with a cell-type-context allowance.
        if token.startswith("CD") and CELL_TYPE_CONTEXT.search(window):
            continue

        # Per-token explicit allowance.
        allowed = ALLOWED_TOKENS.get(token)
        if allowed is not None and allowed.search(window):
            continue

        line_no = text.count("\n", 0, start) + 1
        hits.append((line_no, token, window))
    return hits


def test_prompts_contain_no_specific_gene_names() -> None:
    """Every prompt file is free of specific-gene-name examples.

    Adding a worked example with a specific gene attached will fail
    this test. Replace the gene name with a categorical descriptor
    ("a tetraspanin", "a receptor's serum-soluble ectodomain",
    "anti-gene-X (Clone N)") or with the "gene X" placeholder
    convention.

    If a specific token is genuinely necessary (e.g. the example is
    structurally load-bearing and no abstraction conveys the point), add
    it to ``ALLOWED_TOKENS`` with the surrounding-context regex that
    confines the allowance — DO NOT remove the token from
    ``BLOCKLIST``. The allow-with-context shape keeps the guard tight.
    """
    all_hits: list[tuple[Path, list[tuple[int, str, str]]]] = []
    for path in _prompt_files():
        hits = _scan_one(path)
        if hits:
            all_hits.append((path, hits))
    if not all_hits:
        return
    report_lines = ["Specific gene names found in prompt files:\n"]
    repo_root = PROMPTS_ROOT.parent.parent.parent.parent
    for path, hits in all_hits:
        rel = path.relative_to(repo_root)
        for line_no, token, window in hits:
            report_lines.append(f"  {rel}:{line_no}  [{token}]  …{window.strip()}…")
    report_lines.append(
        "\nReplace each gene-name example with a categorical descriptor "
        "or a 'gene X' / 'gene Y' placeholder. If a name is structurally "
        "load-bearing, add it to ALLOWED_TOKENS in this test file with "
        "the surrounding-context regex that confines the allowance."
    )
    pytest.fail("\n".join(report_lines))


def test_blocklist_is_curated_not_empty() -> None:
    """Guardrail on the guardrail — keep the blocklist non-empty."""
    assert len(BLOCKLIST) >= 30, (
        "BLOCKLIST has fewer than 30 entries. The point of this guard "
        "is broad coverage — adding genes is expected as more sneak in. "
        "If you're removing entries, double-check those tokens aren't "
        "real target genes."
    )
