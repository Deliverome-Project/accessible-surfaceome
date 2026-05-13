"""Agent prompts must describe mechanisms, not name specific proteins.

A specific protein name in the prompt anchors the agent on that
protein's canonical biology instead of teaching it to recognize the
mechanism class more generally. The triage agent prompt was tripped
up by exactly this — naming CRISP1, TGF-β1, GARP, etc. in examples
biased the agent toward those proteins while harming generalization.

This test scans every agent prompt file for a denylist of known
specific protein names (HGNC symbols and the common protein-name
spellings). New violations require either:

1. Rewriting the prompt example as a mechanism class (preferred), or
2. Adding the new gene symbol to the denylist (if it's a specific
   protein leaking through a previously-uncovered route).

The denylist is intentionally permissive of mechanism-class
abbreviations (GPCR, SLC, ADAM, MMP, BACE, etc.) — those describe a
family or biochemistry, not a single protein. Specific proteins
within those families (e.g. SLC34A2, ADAM10) are on the denylist.
"""

from __future__ import annotations

import re
from pathlib import Path

# Every prompt file the triage agent consumes. Add new prompt files
# here as they're introduced. All active + variant prompts are guarded.
PROMPT_FILES = [
    Path("src/accessible_surfaceome/agents/surface_triage/prompts/system.md"),
    Path("src/accessible_surfaceome/agents/surface_triage/prompts/system_naive.md"),
    Path("src/accessible_surfaceome/agents/surface_triage/prompts/system_web.md"),
    Path("src/accessible_surfaceome/agents/surface_triage/prompts/system_web_naive.md"),
    Path("src/accessible_surfaceome/agents/surface_triage/prompts/task_template.md"),
]


# Specific gene / protein names that MUST NOT appear in any agent prompt.
# Curated against the triage benchmark and known-clinical-target list;
# extend this when new specific names creep in.
FORBIDDEN_TOKENS: frozenset[str] = frozenset({
    # === HGNC symbols (uppercase, may include digits) ===
    # Clinical-stage validated surface antigens
    "ERBB2", "HER2", "EGFR", "CD19", "CD20", "CD22", "CD33", "CD38",
    "CD52", "CD63", "CD68", "CD74", "CD79A", "CD79B", "CD117", "CD123",
    "MSLN", "FOLR1", "PSCA", "GFRA1", "CEACAM5", "BST2", "DPEP1",
    "CD24", "BCMA", "TNFRSF17", "NECTIN4", "TACSTD2", "SLITRK6",
    "ROR1", "ROR2", "LRRC15", "TFRC", "MUC1", "MUC16", "TROP2",
    "AXL", "MERTK", "TYRO3", "CLDN6", "CLDN18", "DLL3", "GPRC5D",
    "STEAP1", "STEAP2", "SLC34A2", "SLC39A6", "FZD7", "FZD10",
    "LGR5", "FLT3", "GUCY2C", "GPNMB", "EFNA4", "EREG", "ROS1",
    "CCR8", "EPHB4", "SEZ6", "GYPA", "DSG3", "DSG4", "GIPR", "GCGR",
    "ADORA3", "HTR2C", "MC1R", "GPBAR1", "BDKRB1", "HRH2", "NPY5R",
    "GRM4", "AVPR1A", "OR1A1", "KLK2", "AMHR2",
    # Reproductive niche
    "IZUMO1", "IZUMO2", "IZUMO3", "IZUMO4", "ZP1", "ZP2", "ZP3", "ZP4",
    "ZPBP", "ZPBP2", "CRISP1", "CRISP2", "ACRBP", "SPAG4", "SPACA1",
    # Contextual / induced / pMHC benchmark targets
    "TGFB1", "TGFB2", "TGFB3", "GDF8", "GDF11", "INHBA", "GARP",
    "LRRC32", "LRRC33", "NRROS", "B2M", "KAAG1", "PMEL", "CTAG1B",
    "PRAME", "MAGE", "MAGEA1", "MAGEA3", "MAGEA4", "SSX2", "WT1",
    "AFP", "MLANA", "TYR", "TARP", "CT83", "CTAG2", "CXorf61",
    "BORIS", "CTCFL", "HPV", "MR1",
    "CALR", "HSPA1A", "HSPA5", "HSPD1", "GRP78", "HSP60", "HSP70",
    "LAMP1", "LAMP2", "LAMP3", "CD107A", "CD107B", "CD208", "CD230",
    "SCARB2", "LIMP2",
    "STIM1", "TGOLN2", "B4GALT1", "BAX", "VDAC1", "TMED9", "TMED10",
    "SRC", "LYN", "HCK", "FYN",
    # Negatives (wrong compartment / side / secreted)
    "KRAS", "NRAS", "HRAS", "RHOA", "RAC1", "GNAQ", "GNB1", "GNAS",
    "ARF1", "RAB5A", "RAB7A",
    "RPN1", "RPN2", "SCAP", "ITPR1", "ITPR3", "SEC61G", "STING1",
    "TMEM173", "ABCB9", "APPL1", "ATG9A", "GORASP2", "GALNT1",
    "NUP210", "SUN1", "SUN2", "SYNE1", "SYNE2", "LMNB1", "LMNA",
    "ATP5F1A", "ATP5F1B", "ACO2", "IDH2", "TFAM", "MRPS5",
    "MUC5AC", "F2", "FN1", "C3", "C5", "TF", "IL6", "IL2", "IGF1",
    "APOB", "VEGFA", "A2M", "ALB", "SERPINA1",
    "HMGB1", "HMGB2", "HNRNPK", "HNRNPA1", "HDAC6", "JAK1", "JAK2",
    "JAK3", "SYK", "BRAF", "BTK", "TYK2", "AKT2", "MAP2K1", "MAP2K2",
    "IKBKB", "LRRK2", "TP53", "BRCA1", "BRCA2", "MKI67", "MYC", "RB1",
    "ESR1", "AR", "FOXP3", "STAT3", "PRNP", "PRNP-prion",
    # === Greek-letter cytokines + lowercase protein names ===
    "TGF-β", "TGFβ", "TGF-beta",
    "TNF-α", "TNFα", "TNF-alpha",
    "IFN-γ", "IFNγ", "IFN-gamma",
    "IL-2", "IL-6", "IL-10",
    # Lowercase / common-name spellings
    "prothrombin", "fibronectin", "epiregulin", "mesothelin",
    "tetherin", "perforin", "annexin", "calreticulin", "calnexin",
    "amyloid", "huntingtin", "albumin", "alpha-fetoprotein",
    "synuclein", "tyrosinase", "mammaglobin", "gp100",
})


# Mechanism abbreviations that are LEGAL in the prompt because they
# describe a biochemistry or a topology class, not a specific protein.
# This list isn't enforced — it's documentation for future editors so
# they don't accidentally add a specific protein under one of these
# categories.
ALLOWED_MECHANISM_ABBREVIATIONS: frozenset[str] = frozenset({
    "TM", "GPI", "PM", "ER", "ICD", "EV", "MVB", "ECM",
    "MHC", "MHC-I", "MHC-II", "HLA",  # HLA *class* references OK; "HLA-A*02" or "HLA-B7" should NOT appear
    "GPCR", "SLC", "ABC", "ADAM", "MMP", "BACE", "NTR",
    "ADC", "CAR-T", "CAR", "TCR-T", "TCR-mimic", "TCR", "BCR", "BiTE",
    "NK", "DC", "PBMC",
    "HGNC", "NCBI", "JSON", "TSV",
    "RNA", "DNA",
    "Ca²⁺", "Gla",  # biochemistry mentions
})


def _scan_text(text: str, path_name: str) -> list[str]:
    """Return formatted violation messages for any forbidden token found."""
    violations: list[str] = []
    for token in FORBIDDEN_TOKENS:
        # Word-boundary regex; case-sensitive for HGNC symbols but
        # case-insensitive only matters for lowercase spellings like
        # "prothrombin" which are already lowercase.
        pattern = r"(?<![A-Za-z0-9])" + re.escape(token) + r"(?![A-Za-z0-9])"
        for match in re.finditer(pattern, text):
            line_no = text[: match.start()].count("\n") + 1
            violations.append(
                f"{path_name}:{line_no}  forbidden token {token!r}"
            )
    return violations


def test_prompt_files_contain_no_specific_protein_names() -> None:
    """Fail if any agent prompt file names a specific protein.

    To fix a failure: rewrite the example using mechanism language
    (e.g. "epididymal-fluid proteins stably deposited onto sperm
    surface" instead of "CRISP1"). The denylist is a safety net,
    not a license to add new specific names.
    """

    all_violations: list[str] = []
    for path in PROMPT_FILES:
        if not path.exists():
            continue
        text = path.read_text()
        all_violations.extend(_scan_text(text, path.name))

    if all_violations:
        formatted = "\n  ".join(all_violations)
        raise AssertionError(
            "Agent prompt(s) name specific proteins — rewrite as mechanism "
            "language or amend the denylist with justification:\n  " + formatted
        )
