"""Generate docs/eval/surface_annotator_reference.html.

Self-contained HTML reference for the surface_annotator (deep-dive) agent —
mirrors `docs/eval/triage_agent_reference.html` for the triage agent. Renders
the system prompt + task template + Pydantic schema + JSON schema +
side-by-side Opus / Sonnet example outputs for ERBB2.

Usage:
    uv run python scripts/render_surface_annotator_reference.py
"""

from __future__ import annotations

import json
import re

from accessible_surfaceome.paths import REPO_ROOT
from accessible_surfaceome.tools._shared.models import SurfaceomeRecordDraft

PROMPTS_DIR = (
    REPO_ROOT / "src" / "accessible_surfaceome" / "agents" / "surface_annotator" / "prompts"
)
MODELS_PATH = REPO_ROOT / "src" / "accessible_surfaceome" / "tools" / "_shared" / "models.py"
OUTPUT_HTML = REPO_ROOT / "docs" / "eval" / "surface_annotator_reference.html"


# -- Pydantic source extraction --------------------------------------------

# Classes / aliases we want to show inline. Order matters for readability.
_PYDANTIC_NAMES = [
    "GeneIdentifier",
    "SCHEMA_VERSION",
    "SurfaceStatus",
    "Topology",
    "AnchorType",
    "ExposureClass",
    "InducedContextKind",
    "InducedPresentation",
    "ExtracellularDomainSummary",
    "DBComparison",
    "SurfaceBiology",
    "TargetabilityTier",
    "ModalityKind",
    "ModalityRecommendation",
    "TargetabilityVerdict",
    "RiskFlagKind",
    "RiskSeverity",
    "RiskFlag",
    "ClinicalPhase",
    "ApprovedDrug",
    "ClinicalTrial",
    "PatentDisclosure",
    "PreclinicalEvidence",
    "TherapeuticLandscape",
    "AssayContext",
    "EvidenceClaim",
    "DeepTMHMMLabel",
    "OrthologSpecies",
    "OrthologyType",
    "CoreceptorRequirementKind",
    "IsoformAccessibility",
    "CoreceptorRequirement",
    "OrthologRecord",
    "SurfaceomeRecordDraft",
]


def _extract_pydantic_source(models_text: str, names: list[str]) -> str:
    """Pull selected class / type-alias blocks out of models.py in source order."""
    lines = models_text.splitlines()
    # Build an ordered map: name -> (start_line, end_line) inclusive.
    spans: dict[str, tuple[int, int]] = {}

    # class blocks
    class_starts = {}
    for i, line in enumerate(lines):
        m = re.match(r"^class (\w+)\(", line)
        if m and m.group(1) in names:
            class_starts[m.group(1)] = i

    for name, start in class_starts.items():
        end = len(lines) - 1
        for j in range(start + 1, len(lines)):
            stripped = lines[j].lstrip()
            if not lines[j].strip():
                continue
            indent = len(lines[j]) - len(stripped)
            if indent == 0 and not stripped.startswith("#"):
                end = j - 1
                break
        # trim trailing blank lines
        while end > start and not lines[end].strip():
            end -= 1
        spans[name] = (start, end)

    # module-level assignments (Literals, constants)
    for i, line in enumerate(lines):
        m = re.match(r"^(\w+)\s*[:=]", line)
        if m and m.group(1) in names and m.group(1) not in spans:
            end = i
            # Multi-line Literal[...] expressions span until the closing ]
            if "[" in line and "]" not in line:
                for j in range(i + 1, len(lines)):
                    if "]" in lines[j]:
                        end = j
                        break
            spans[m.group(1)] = (i, end)

    ordered = sorted(spans.values())
    blocks: list[str] = []
    for start, end in ordered:
        blocks.append("\n".join(lines[start : end + 1]))
    return "\n\n\n".join(blocks)


# -- Sample task message ----------------------------------------------------

SAMPLE_DEEP_DIVE_BLOCK = """## Pre-loaded deep-dive context

These rows come from deterministic precompute (DeepTMHMM + Ensembl
Compara). Cite them as `evidence_type: "computational_prediction"`
with `source_id: "UniProt:<acc>"` only when you've fetched that
UniProt entry; otherwise leave `cited_evidence_ids` empty and note the
limitation in `confidence_reasoning`.

### Human isoform topology (DeepTMHMM)

| isoform_id | label | length | TM helices | signal peptide | surface? |
| --- | --- | --- | --- | --- | --- |
| `P04626-1` | SP+TM | 1255 | 1 | yes | yes |
| `P04626-2` | SP+TM | 1240 | 1 | yes | yes |
| `P04626-3` | SP | 631 | 0 | yes | no |
| `P04626-4` | SP | 419 | 0 | yes | no |

### Mouse ortholog

- gene symbol: `Erbb2` (UniProt `P70424`, Ensembl `ENSMUSG00000062312`)
- percent identity to human: 89.7%
- DeepTMHMM label: `SP+TM` (length 1256 aa, TM helices 1, signal peptide yes)
- predicted surface membrane: yes; predicted secreted: no

### Cynomolgus ortholog

- gene symbol: `ERBB2` (UniProt `A0A2K5W6F1`, Ensembl `ENSMFAG00000031281`)
- percent identity to human: 99.1%
- DeepTMHMM label: `SP+TM` (length 1255 aa, TM helices 1, signal peptide yes)
- predicted surface membrane: yes; predicted secreted: no
"""

SAMPLE_TASK = (
    "Annotate the gene `ERBB2`. Walk the `gene_lookup` cascade as described in the system prompt: "
    "resolve → db_panel → (uniprot_summary if needed) → (miss_diagnosis if a control gene was missed). "
    "Emit one `GeneAnnotation` JSON block as your final response.\n\n"
    + SAMPLE_DEEP_DIVE_BLOCK
)


# -- Example outputs (hand-crafted, reference shape) ------------------------
#
# These are illustrative reference outputs showing the SurfaceomeRecordDraft
# shape with the new deep-dive fields populated. They are NOT live agent
# runs — quotes / patent details / trial IDs are realistic for ERBB2 but the
# orchestrator's substring-anchor / promotion pipeline hasn't validated
# them. Real runs land under `data/annotations/{gene}.json`.

EXAMPLE_OPUS = {
    "schema_version": "v0.4.0",
    "gene": {
        "hgnc_symbol": "ERBB2",
        "hgnc_id": "HGNC:3430",
        "uniprot_acc": "P04626",
        "ncbi_gene_id": 2064,
        "ensembl_gene": "ENSG00000141736",
    },
    "canonical_isoform": "P04626-1",
    "isoform_flattened": False,
    "targetability": {
        "tier": "validated_target",
        "recommended_modalities": [
            {"kind": "adc", "rationale": "Trastuzumab emtansine and trastuzumab deruxtecan are approved ADCs against ERBB2; high-density extracellular ECD enables payload internalization."},
            {"kind": "naked_mab", "rationale": "Trastuzumab and pertuzumab are approved naked mAbs targeting distinct ECD epitopes."},
            {"kind": "bispecific", "rationale": "Zanidatamab (ERBB2 biparatopic) approved; T-cell engagers in late clinical development."},
            {"kind": "car_t", "rationale": "Multiple anti-ERBB2 CAR-T programs in early clinical trials for solid tumors."},
            {"kind": "radioligand", "rationale": "Anti-ERBB2 radioligand conjugates in clinical development for HER2-low tumors."},
        ],
        "tldr": "Validated ERBB2/HER2 surface target with multiple approved binders (trastuzumab, T-DM1, T-DXd, pertuzumab, zanidatamab); >100k aa-accessible ECD on the canonical isoform.",
        "cited_evidence_ids": ["evi_001", "evi_002"],
    },
    "surface_biology": {
        "surface_status": "strong_surface",
        "topology": "transmembrane_single_pass",
        "anchor_type": "transmembrane_single",
        "exposure_class": "exposed_ecd",
        "extracellular_domain": {
            "size_aa": 631,
            "domains": ["L1", "S1 (cysteine-rich)", "L2", "S2 (cysteine-rich)"],
            "accessibility": "accessible",
            "notes": "ECD comprises four subdomains (I/L1, II/S1, III/L2, IV/S2); residues ~23-652 reside extracellularly before the single transmembrane helix.",
        },
        "glycosylation": "N-glycosylated on multiple ECD asparagines",
        "shedding_documented": True,
        "induced_presentation": [],
        "db_comparison": {
            "surfy": True,
            "cspa": True,
            "uniprot_query": True,
            "go": True,
            "hpa": True,
            "deeptmhmm": True,
            "compartments": True,
            "patent_handle": True,
            "n_sources_voting_surface": 8,
        },
        "cited_evidence_ids": ["evi_003", "evi_004"],
    },
    "therapeutic_landscape": {
        "approved_drugs": [
            {"name": "Trastuzumab (Herceptin)", "modality": "naked_mab", "indication": "HER2+ breast cancer, gastric cancer", "sponsor": "Genentech/Roche", "approval_year": 1998, "cited_evidence_ids": ["evi_005"]},
            {"name": "Trastuzumab emtansine (Kadcyla)", "modality": "adc", "indication": "HER2+ metastatic breast cancer", "sponsor": "Genentech/Roche", "approval_year": 2013, "cited_evidence_ids": ["evi_006"]},
            {"name": "Trastuzumab deruxtecan (Enhertu)", "modality": "adc", "indication": "HER2-low/positive breast, gastric, NSCLC", "sponsor": "Daiichi Sankyo/AstraZeneca", "approval_year": 2019, "cited_evidence_ids": ["evi_007"]},
            {"name": "Pertuzumab (Perjeta)", "modality": "naked_mab", "indication": "HER2+ breast cancer (combination)", "sponsor": "Genentech/Roche", "approval_year": 2012, "cited_evidence_ids": []},
            {"name": "Zanidatamab (Ziihera)", "modality": "bispecific", "indication": "HER2+ biliary tract cancer", "sponsor": "Jazz/Zymeworks", "approval_year": 2024, "cited_evidence_ids": []},
        ],
        "clinical_trials": [],
        "patent_disclosures": [],
        "preclinical_evidence": [],
    },
    "risk_flags": [
        {"kind": "soluble_shedding", "severity": "medium", "description": "ERBB2 ECD is proteolytically shed by ADAM10/ADAM17 into circulation (serum HER2 ECD); levels rise in metastatic disease but rarely high enough to sequester clinical anti-HER2 binders.", "cited_evidence_ids": ["evi_008"]},
        {"kind": "secreted_form", "severity": "low", "description": "Splice isoforms P04626-3 / P04626-4 lack the transmembrane domain and produce a secreted form (p105); abundance is generally low relative to the membrane-bound canonical isoform.", "cited_evidence_ids": ["evi_009"]},
    ],
    "isoform_accessibility": [
        {
            "isoform_id": "P04626-1",
            "name": "Isoform 1 (canonical, p185)",
            "is_canonical": True,
            "length_aa": 1255,
            "surface_status": "strong_surface",
            "exposure_class": "exposed_ecd",
            "deeptmhmm_label": "SP+TM",
            "tm_helix_count": 1,
            "has_signal_peptide": True,
            "uniprot_isoform_specific_locations": [],
            "differential_from_canonical": False,
            "rationale": "Canonical single-pass TM with ~630 aa ECD; the binder-targetable form referenced by every approved HER2 program.",
            "cited_evidence_ids": ["evi_003"],
        },
        {
            "isoform_id": "P04626-2",
            "name": "Isoform 2 (Delta-16)",
            "is_canonical": False,
            "length_aa": 1240,
            "surface_status": "strong_surface",
            "exposure_class": "exposed_ecd",
            "deeptmhmm_label": "SP+TM",
            "tm_helix_count": 1,
            "has_signal_peptide": True,
            "uniprot_isoform_specific_locations": ["Cell membrane"],
            "differential_from_canonical": False,
            "rationale": "Delta-16 isoform lacks 16 aa from exon 16 in the juxtamembrane region but retains the TM helix and the full ECD. Behaves as a constitutively active oncogenic variant; surface accessible.",
            "cited_evidence_ids": ["evi_010"],
        },
        {
            "isoform_id": "P04626-3",
            "name": "Isoform 3 (secreted p105)",
            "is_canonical": False,
            "length_aa": 631,
            "surface_status": "absent",
            "exposure_class": "none",
            "deeptmhmm_label": "SP",
            "tm_helix_count": 0,
            "has_signal_peptide": True,
            "uniprot_isoform_specific_locations": ["Secreted"],
            "differential_from_canonical": True,
            "rationale": "Lacks TM and intracellular domains; predicted secreted by DeepTMHMM (SP only, no TM). Anti-HER2 mAbs may bind this circulating form (decoy effect) but it is not a surface target itself.",
            "cited_evidence_ids": ["evi_011"],
        },
        {
            "isoform_id": "P04626-4",
            "name": "Isoform 4",
            "is_canonical": False,
            "length_aa": 419,
            "surface_status": "absent",
            "exposure_class": "none",
            "deeptmhmm_label": "SP",
            "tm_helix_count": 0,
            "has_signal_peptide": True,
            "uniprot_isoform_specific_locations": ["Secreted"],
            "differential_from_canonical": True,
            "rationale": "N-terminal ECD fragment without TM; predicted secreted. Contributes to the soluble HER2 ECD pool quantified in serum assays.",
            "cited_evidence_ids": [],
        },
    ],
    "coreceptor_requirements": [],
    "orthology": [
        {
            "species": "mouse",
            "ortholog_uniprot_acc": "P70424",
            "ortholog_gene_symbol": "Erbb2",
            "ensembl_gene_id": "ENSMUSG00000062312",
            "orthology_type": "one_to_one",
            "percent_identity": 89.7,
            "deeptmhmm_label": "SP+TM",
            "tm_helix_count": 1,
            "has_signal_peptide": True,
            "surface_status": "strong_surface",
            "surface_concordant_with_human": True,
            "notes": "Murine Erbb2 retains single-pass TM topology and the full ECD; preclinical PDX and syngeneic HER2-transgenic models recapitulate the human surface call.",
            "cited_evidence_ids": [],
        },
        {
            "species": "cynomolgus",
            "ortholog_uniprot_acc": "A0A2K5W6F1",
            "ortholog_gene_symbol": "ERBB2",
            "ensembl_gene_id": "ENSMFAG00000031281",
            "orthology_type": "one_to_one",
            "percent_identity": 99.1,
            "deeptmhmm_label": "SP+TM",
            "tm_helix_count": 1,
            "has_signal_peptide": True,
            "surface_status": "strong_surface",
            "surface_concordant_with_human": True,
            "notes": "Cyno ERBB2 is near-identical to human (99.1% identity); cross-reactivity of clinical anti-HER2 antibodies is well-documented and supports cyno as the primary tox species for HER2-targeted programs.",
            "cited_evidence_ids": [],
        },
    ],
    "evidence_claims": [
        {
            "evidence_id": "evi_001",
            "claim": "Trastuzumab is approved for the treatment of HER2-overexpressing breast cancer.",
            "claim_type": "surface_expression",
            "direction": "supports",
            "evidence_type": "review_assertion",
            "evidence_tier": "secondary",
            "confidence": "strong",
            "assay_context": {"species": "human", "cell_type_or_line": "breast carcinoma", "permeabilized": False, "fixation": "live", "isoform": "P04626-1"},
            "source_id": "PMID:11248153",
            "quote": "Trastuzumab, a humanized monoclonal antibody against the extracellular domain of HER2",
            "section": "abstract",
            "figure_or_table_id": None,
        },
        {
            "evidence_id": "evi_003",
            "claim": "HER2 is a single-pass type I transmembrane receptor tyrosine kinase.",
            "claim_type": "topology",
            "direction": "supports",
            "evidence_type": "db_annotation",
            "evidence_tier": "secondary",
            "confidence": "strong",
            "assay_context": {"species": "human", "cell_type_or_line": None, "permeabilized": None, "fixation": "unspecified", "isoform": "P04626-1"},
            "source_id": "UniProt:P04626",
            "quote": "Transmembrane domain at residues 653-675 (Helical)",
            "section": "other",
            "figure_or_table_id": None,
        },
        {
            "evidence_id": "evi_008",
            "claim": "ADAM proteases cleave HER2 ECD into circulation.",
            "claim_type": "methodological",
            "direction": "supports",
            "evidence_type": "review_assertion",
            "evidence_tier": "secondary",
            "confidence": "strong",
            "assay_context": {"species": "human", "cell_type_or_line": "breast cancer cell lines", "permeabilized": False, "fixation": "live", "isoform": None},
            "source_id": "PMID:16959975",
            "quote": "ADAM10 mediates the shedding of HER2 extracellular domain",
            "section": "abstract",
            "figure_or_table_id": None,
        },
    ],
    "primary_evidence_count": 0,
    "secondary_evidence_count": 3,
    "evidence_count": 3,
    "confidence": "high",
    "confidence_reasoning": "Validated_target with multiple approved cell-surface binders across ADC, naked mAb, and bispecific modalities. UniProt + 8/8 M1 sources concur on single-pass TM topology. Isoform divergence (P04626-3/-4 secreted) is well-documented. Mouse and cyno orthologs are concordant; cyno is near-identical and is the primary tox species.",
    "contradiction_flag": False,
    "rationale": "ERBB2 is the canonical HER2 surface validated target: a single-pass type I transmembrane receptor with a ~630-residue extracellular domain that is engaged by trastuzumab, pertuzumab, T-DM1, T-DXd, and zanidatamab. Four UniProt isoforms exist; P04626-1 and P04626-2 (Delta-16) are both membrane-anchored and surface-accessible, while P04626-3 (p105) and P04626-4 lack the TM and contribute to the soluble HER2 ECD pool. ECD shedding by ADAM10/17 produces a circulating decoy at levels that rise with metastatic burden but are not clinically blocking for current programs. Mouse Erbb2 (89.7% identity) and cyno ERBB2 (99.1% identity) both retain the SP+TM topology; cyno is the preferred tox species. No obligate co-receptor is required for surface delivery — ERBB2 homodimers exist at the cell surface independent of ERBB1/3/4 dimerization partners, though heterodimers are functional.",
    "model_path": "opus_heavy",
}


EXAMPLE_SONNET = {
    "schema_version": "v0.4.0",
    "gene": {
        "hgnc_symbol": "ERBB2",
        "hgnc_id": "HGNC:3430",
        "uniprot_acc": "P04626",
        "ncbi_gene_id": 2064,
        "ensembl_gene": "ENSG00000141736",
    },
    "canonical_isoform": "P04626-1",
    "isoform_flattened": False,
    "targetability": {
        "tier": "validated_target",
        "recommended_modalities": [
            {"kind": "adc", "rationale": "T-DM1 and T-DXd are approved HER2 ADCs."},
            {"kind": "naked_mab", "rationale": "Trastuzumab and pertuzumab are approved naked mAbs."},
            {"kind": "bispecific", "rationale": "Zanidatamab approved for biliary tract cancer."},
        ],
        "tldr": "HER2 (ERBB2) is a validated surface target with multiple approved binders across ADC, naked mAb, and bispecific modalities.",
        "cited_evidence_ids": ["evi_001"],
    },
    "surface_biology": {
        "surface_status": "strong_surface",
        "topology": "transmembrane_single_pass",
        "anchor_type": "transmembrane_single",
        "exposure_class": "exposed_ecd",
        "extracellular_domain": {
            "size_aa": 631,
            "domains": ["L1", "S1", "L2", "S2"],
            "accessibility": "accessible",
            "notes": None,
        },
        "glycosylation": None,
        "shedding_documented": True,
        "induced_presentation": [],
        "db_comparison": {
            "surfy": True,
            "cspa": True,
            "uniprot_query": True,
            "go": True,
            "hpa": True,
            "deeptmhmm": True,
            "compartments": True,
            "patent_handle": True,
            "n_sources_voting_surface": 8,
        },
        "cited_evidence_ids": ["evi_002"],
    },
    "therapeutic_landscape": {
        "approved_drugs": [
            {"name": "Trastuzumab", "modality": "naked_mab", "indication": "HER2+ breast/gastric cancer", "sponsor": "Genentech/Roche", "approval_year": 1998, "cited_evidence_ids": []},
            {"name": "Trastuzumab emtansine (T-DM1)", "modality": "adc", "indication": "HER2+ metastatic breast cancer", "sponsor": "Genentech/Roche", "approval_year": 2013, "cited_evidence_ids": []},
            {"name": "Trastuzumab deruxtecan (T-DXd)", "modality": "adc", "indication": "HER2-low/positive breast/gastric/NSCLC", "sponsor": "Daiichi Sankyo", "approval_year": 2019, "cited_evidence_ids": []},
        ],
        "clinical_trials": [],
        "patent_disclosures": [],
        "preclinical_evidence": [],
    },
    "risk_flags": [
        {"kind": "soluble_shedding", "severity": "medium", "description": "HER2 ECD is shed into serum by ADAM10/17 proteases. Rarely high enough to interfere with clinical anti-HER2 binders.", "cited_evidence_ids": []},
    ],
    "isoform_accessibility": [
        {
            "isoform_id": "P04626-1",
            "name": "Isoform 1 (canonical)",
            "is_canonical": True,
            "length_aa": 1255,
            "surface_status": "strong_surface",
            "exposure_class": "exposed_ecd",
            "deeptmhmm_label": "SP+TM",
            "tm_helix_count": 1,
            "has_signal_peptide": True,
            "uniprot_isoform_specific_locations": [],
            "differential_from_canonical": False,
            "rationale": "Canonical TM isoform targeted by all approved HER2 therapeutics.",
            "cited_evidence_ids": [],
        },
        {
            "isoform_id": "P04626-3",
            "name": "Isoform 3 (secreted)",
            "is_canonical": False,
            "length_aa": 631,
            "surface_status": "absent",
            "exposure_class": "none",
            "deeptmhmm_label": "SP",
            "tm_helix_count": 0,
            "has_signal_peptide": True,
            "uniprot_isoform_specific_locations": ["Secreted"],
            "differential_from_canonical": True,
            "rationale": "Lacks TM; secreted ECD fragment, contributes to soluble HER2 pool.",
            "cited_evidence_ids": [],
        },
    ],
    "coreceptor_requirements": [],
    "orthology": [
        {
            "species": "mouse",
            "ortholog_uniprot_acc": "P70424",
            "ortholog_gene_symbol": "Erbb2",
            "ensembl_gene_id": "ENSMUSG00000062312",
            "orthology_type": "one_to_one",
            "percent_identity": 89.7,
            "deeptmhmm_label": "SP+TM",
            "tm_helix_count": 1,
            "has_signal_peptide": True,
            "surface_status": "strong_surface",
            "surface_concordant_with_human": True,
            "notes": "Mouse ortholog retains single-pass TM topology.",
            "cited_evidence_ids": [],
        },
        {
            "species": "cynomolgus",
            "ortholog_uniprot_acc": "A0A2K5W6F1",
            "ortholog_gene_symbol": "ERBB2",
            "ensembl_gene_id": "ENSMFAG00000031281",
            "orthology_type": "one_to_one",
            "percent_identity": 99.1,
            "deeptmhmm_label": "SP+TM",
            "tm_helix_count": 1,
            "has_signal_peptide": True,
            "surface_status": "strong_surface",
            "surface_concordant_with_human": True,
            "notes": "Near-identical to human; standard tox species for HER2 programs.",
            "cited_evidence_ids": [],
        },
    ],
    "evidence_claims": [
        {
            "evidence_id": "evi_001",
            "claim": "Trastuzumab targets the HER2 extracellular domain.",
            "claim_type": "surface_expression",
            "direction": "supports",
            "evidence_type": "review_assertion",
            "evidence_tier": "secondary",
            "confidence": "strong",
            "assay_context": {"species": "human", "cell_type_or_line": "breast carcinoma", "permeabilized": False, "fixation": "live", "isoform": None},
            "source_id": "PMID:11248153",
            "quote": "Trastuzumab, a humanized monoclonal antibody against the extracellular domain of HER2",
            "section": "abstract",
            "figure_or_table_id": None,
        },
        {
            "evidence_id": "evi_002",
            "claim": "HER2 is a single-pass transmembrane receptor.",
            "claim_type": "topology",
            "direction": "supports",
            "evidence_type": "db_annotation",
            "evidence_tier": "secondary",
            "confidence": "strong",
            "assay_context": {"species": "human", "cell_type_or_line": None, "permeabilized": None, "fixation": "unspecified", "isoform": "P04626-1"},
            "source_id": "UniProt:P04626",
            "quote": "Transmembrane domain at residues 653-675 (Helical)",
            "section": "other",
            "figure_or_table_id": None,
        },
    ],
    "primary_evidence_count": 0,
    "secondary_evidence_count": 2,
    "evidence_count": 2,
    "confidence": "high",
    "confidence_reasoning": "Validated target with multiple approved cell-surface binders; 8/8 M1 sources concur on TM topology; orthologs concordant.",
    "contradiction_flag": False,
    "rationale": "HER2 is the canonical validated surface target — single-pass TM receptor with a ~630-aa ECD engaged by trastuzumab, T-DM1, T-DXd, pertuzumab, and zanidatamab. Two UniProt isoforms are surface-accessible (canonical, Delta-16); two (P04626-3, -4) lack the TM and are secreted. ECD shedding by ADAM10/17 produces a soluble pool but is not blocking. Mouse (89.7%) and cyno (99.1%) orthologs are topologically concordant; cyno is the standard tox species.",
    "model_path": "sonnet_only",
}


# -- HTML --------------------------------------------------------------------


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>surface_annotator agent — reference</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Manrope:wght@300;400;500;600;700;800&family=Playfair+Display:ital,wght@0,400..700;1,400..600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/atom-one-light.min.css">
<script src="https://cdnjs.cloudflare.com/ajax/libs/marked/12.0.0/marked.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"></script>
<style>
:root { --primary: #BC3C4C; --secondary: #3D6B60; --accent: #F4AA28;
  --bg: #FBF7F2; --bg-warm: #F3ECE5; --ink: #1F1718; --line: #E6DAD4; --neutral: #6F5D5A;
  --code-bg: #F5EFE8; --code-line: #E6DAD4; }
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; background: var(--bg); }
body { font-family: "Manrope", -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
  font-size: 15.5px; line-height: 1.6; color: var(--ink); font-weight: 400; }
header { background: linear-gradient(135deg, #F3ECE5 0%, #FBF7F2 100%);
  border-bottom: 1px solid var(--line); padding: 36px 48px 28px; }
header .eyebrow { font-size: 11px; font-weight: 700; letter-spacing: 0.12em;
  text-transform: uppercase; color: var(--primary); margin: 0 0 8px 0; }
header h1 { font-family: "Playfair Display", Georgia, serif; font-weight: 600;
  font-size: 34px; letter-spacing: -0.02em; margin: 0 0 12px 0; color: var(--ink); }
header .meta-row { display: flex; flex-wrap: wrap; gap: 12px; font-size: 13px; }
header .meta-row .chip { display: inline-flex; align-items: center; gap: 6px;
  background: white; border: 1px solid var(--line); padding: 4px 12px;
  border-radius: 999px; color: var(--neutral); font-weight: 500; }
header .meta-row .chip strong { color: var(--ink); font-weight: 600; }
nav { position: sticky; top: 0; background: rgba(251, 247, 242, 0.95);
  backdrop-filter: blur(8px); -webkit-backdrop-filter: blur(8px);
  border-bottom: 1px solid var(--line); padding: 14px 48px;
  display: flex; gap: 8px; z-index: 10; flex-wrap: wrap; }
nav a { color: var(--neutral); text-decoration: none; font-size: 13.5px;
  font-weight: 500; padding: 6px 14px; border-radius: 999px; transition: all 0.15s ease; }
nav a:hover { background: var(--bg-warm); color: var(--primary); }
main { max-width: 1040px; margin: 0 auto; padding: 40px 48px 96px; }
section { margin-bottom: 64px; }
section h2 { font-family: "Playfair Display", Georgia, serif; font-weight: 600;
  font-size: 26px; letter-spacing: -0.01em; margin: 0 0 8px 0; color: var(--ink); }
section .lede { color: var(--neutral); font-size: 14px; margin: 0 0 20px 0; }
section h2::after { content: ""; display: block; width: 48px; height: 3px;
  margin-top: 12px; background: var(--primary); border-radius: 2px; }
pre { background: var(--code-bg); border: 1px solid var(--code-line);
  border-radius: 8px; padding: 18px 22px; overflow-x: auto; font-size: 12.5px;
  line-height: 1.55; font-family: "JetBrains Mono", "SF Mono", Menlo, Consolas, monospace; }
code { font-family: "JetBrains Mono", "SF Mono", Menlo, Consolas, monospace; font-size: 12.5px; }
.prompt-rendered, .task-rendered { background: white; border: 1px solid var(--line);
  border-left: 4px solid var(--primary); border-radius: 8px; padding: 28px 32px; }
.task-rendered { border-left-color: var(--secondary); }
.prompt-rendered h1, .prompt-rendered h2, .prompt-rendered h3 {
  font-family: "Playfair Display", Georgia, serif; font-weight: 600; color: var(--ink); }
.prompt-rendered h1 { font-size: 24px; border-bottom: none; margin-top: 16px; }
.prompt-rendered h2 { font-size: 19px; margin-top: 28px; color: var(--primary); }
.prompt-rendered h2::after { display: none; }
.prompt-rendered h3 { font-size: 16px; margin-top: 20px; color: var(--secondary); }
.prompt-rendered ul, .prompt-rendered ol { padding-left: 28px; }
.prompt-rendered li { margin-bottom: 6px; }
.prompt-rendered strong { color: var(--ink); font-weight: 700; }
.prompt-rendered code { background: var(--code-bg); padding: 2px 6px;
  border-radius: 4px; color: var(--primary); font-weight: 500; }
.prompt-rendered pre code { background: transparent; padding: 0; color: var(--ink); font-weight: 400; }
.prompt-rendered pre { font-size: 12px; }
.prompt-rendered table { border-collapse: collapse; margin: 12px 0; font-size: 13px; }
.prompt-rendered th, .prompt-rendered td { border: 1px solid var(--line); padding: 6px 10px; text-align: left; }
.prompt-rendered th { background: var(--bg-warm); font-weight: 600; }
.prompt-rendered hr { border: none; border-top: 1px solid var(--line); margin: 24px 0; }
details { border: 1px solid var(--line); border-radius: 8px; margin: 16px 0; background: white; }
details summary { cursor: pointer; padding: 12px 18px; font-weight: 500;
  font-size: 13.5px; color: var(--neutral); list-style: none; }
details summary::-webkit-details-marker { display: none; }
details summary::before { content: "▸ "; color: var(--primary); display: inline-block;
  margin-right: 6px; transition: transform 0.15s ease; }
details[open] summary::before { transform: rotate(90deg); }
details[open] summary { border-bottom: 1px solid var(--line); color: var(--ink); }
details > div { padding: 4px 18px 14px 18px; }
.pill { display: inline-block; background: var(--bg-warm); color: var(--primary);
  border: 1px solid var(--line); border-radius: 999px; padding: 3px 12px;
  font-size: 11px; font-weight: 600; letter-spacing: 0.04em; margin-left: 10px;
  vertical-align: middle; }
.pill.opus { background: #ECE2F0; color: #6C3E92; border-color: #DDD0E3; }
.pill.sonnet { background: #E0EFEA; color: var(--secondary); border-color: #CCE2DA; }
.example-tabs { display: flex; gap: 8px; margin-bottom: 16px; }
.example-tabs button { background: white; border: 1px solid var(--line); border-radius: 999px;
  padding: 6px 18px; font-family: inherit; font-size: 13px; font-weight: 600;
  color: var(--neutral); cursor: pointer; transition: all 0.15s ease; }
.example-tabs button:hover { color: var(--primary); border-color: var(--primary); }
.example-tabs button.active { background: var(--primary); color: white; border-color: var(--primary); }
.example-tabs button.active.opus { background: #6C3E92; border-color: #6C3E92; }
.example-tabs button.active.sonnet { background: var(--secondary); border-color: var(--secondary); }
.example-pane { display: none; }
.example-pane.active { display: block; }
.example-note { background: var(--bg-warm); border-left: 3px solid var(--accent); padding: 12px 16px;
  margin-bottom: 16px; font-size: 13px; color: var(--neutral); border-radius: 6px; }
</style>
</head>
<body>
<header>
  <p class="eyebrow">Deliverome · accessible-surfaceome</p>
  <h1>surface_annotator agent reference</h1>
  <div class="meta-row">
    <span class="chip">Model · <strong>opus-heavy / sonnet</strong></span>
    <span class="chip">Tools · <strong>gene_lookup · gene_literature · patent_lookup</strong></span>
    <span class="chip">Schema · <strong>SurfaceomeRecordDraft v0.4.0</strong></span>
    <span class="chip">Deep-dive · <strong>isoforms · co-receptors · orthology</strong></span>
  </div>
</header>

<nav>
  <a href="#system-prompt">System prompt</a>
  <a href="#task-context">Task context</a>
  <a href="#pydantic">Pydantic schema</a>
  <a href="#jsonschema">JSON schema</a>
  <a href="#example">Example output</a>
</nav>

<main>

<section id="system-prompt">
  <h2>System prompt <span class="pill">__SYSTEM_LINES__ lines</span></h2>
  <p class="lede">Active default. Identical for every surface_annotator run. The deep-dive sections — isoforms, co-receptor requirements, orthology — extend the v0.4.0 accessibility framing.</p>
  <div class="prompt-rendered" id="prompt-rendered-content"></div>
  <details>
    <summary>Raw markdown source</summary>
    <div><pre><code class="language-markdown" id="prompt-raw"></code></pre></div>
  </details>
</section>

<section id="task-context">
  <h2>Task context (per-gene) <span class="pill">ERBB2 sample</span></h2>
  <p class="lede">Each run gets a per-gene <strong>task message</strong> with two halves: a one-line annotate-the-gene instruction, then the <code>## Pre-loaded deep-dive context</code> block injected by the orchestrator from <code>deep_dive_pack.render_markdown</code>. The injected block carries DeepTMHMM topology for human isoforms and mouse/cyno orthologs, plus Ensembl Compara identity — so the agent never needs to call a tool just to populate the deep-dive fields.</p>
  <div class="task-rendered prompt-rendered" id="task-rendered-content"></div>
</section>

<section id="pydantic">
  <h2>Pydantic schema</h2>
  <p class="lede">The agent emits a <code>SurfaceomeRecordDraft</code> JSON; the orchestrator promotes each <code>EvidenceClaim</code> to a full <code>Evidence</code> record (substring-anchored against cached source bodies) and persists a canonical <code>SurfaceomeRecord</code>. The deep-dive additions (<code>IsoformAccessibility</code>, <code>CoreceptorRequirement</code>, <code>OrthologRecord</code>) are additive — empty lists are valid for genes without isoform / co-receptor / ortholog data.</p>
  <pre><code class="language-python" id="pydantic-src"></code></pre>
</section>

<section id="jsonschema">
  <h2>JSON schema</h2>
  <p class="lede">Auto-generated from <code>SurfaceomeRecordDraft.model_json_schema()</code>.</p>
  <pre><code class="language-json" id="json-schema"></code></pre>
</section>

<section id="example">
  <h2>Example output <span class="pill">ERBB2</span></h2>
  <p class="lede">Reference shape of a <code>SurfaceomeRecordDraft</code> for ERBB2 / HER2 with the new deep-dive fields populated. Two reference variants illustrate the verbosity / coverage difference between opus-heavy and sonnet model paths.</p>
  <div class="example-note">These are <strong>illustrative reference outputs</strong>, hand-shaped to match the schema and known ERBB2 biology — not the result of a live agent run. Real runs land in <code>data/annotations/ERBB2.json</code> after the orchestrator's substring-anchor promotion pipeline validates each quote against a fetched source.</div>
  <div class="example-tabs">
    <button class="active opus" data-target="example-opus">Opus heavy <span class="pill opus">opus_heavy</span></button>
    <button class="sonnet" data-target="example-sonnet">Sonnet <span class="pill sonnet">sonnet_only</span></button>
  </div>
  <div id="example-opus" class="example-pane active">
    <pre><code class="language-json" id="example-opus-content"></code></pre>
  </div>
  <div id="example-sonnet" class="example-pane">
    <pre><code class="language-json" id="example-sonnet-content"></code></pre>
  </div>
</section>

</main>

<script>
const promptSource = __PROMPT_JSON__;
const taskSource = __TASK_JSON__;
document.getElementById("prompt-rendered-content").innerHTML = marked.parse(promptSource);
document.getElementById("prompt-raw").textContent = promptSource;
document.getElementById("task-rendered-content").innerHTML = marked.parse(taskSource);
document.getElementById("pydantic-src").textContent = __PYDANTIC_JSON__;
document.getElementById("json-schema").textContent = __JSONSCHEMA_JSON__;
document.getElementById("example-opus-content").textContent = __EXAMPLE_OPUS_JSON__;
document.getElementById("example-sonnet-content").textContent = __EXAMPLE_SONNET_JSON__;
document.querySelectorAll(".example-tabs button").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".example-tabs button").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".example-pane").forEach((p) => p.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById(btn.dataset.target).classList.add("active");
    hljs.highlightAll();
  });
});
hljs.highlightAll();
</script>
</body>
</html>
"""


def main() -> None:
    system_md = (PROMPTS_DIR / "system.md").read_text()
    models_text = MODELS_PATH.read_text()
    pydantic_src = _extract_pydantic_source(models_text, _PYDANTIC_NAMES)
    json_schema = json.dumps(
        SurfaceomeRecordDraft.model_json_schema(), indent=2, sort_keys=True
    )

    rendered = (
        HTML_TEMPLATE.replace("__SYSTEM_LINES__", str(len(system_md.splitlines())))
        .replace("__PROMPT_JSON__", json.dumps(system_md))
        .replace("__TASK_JSON__", json.dumps(SAMPLE_TASK))
        .replace("__PYDANTIC_JSON__", json.dumps(pydantic_src))
        .replace("__JSONSCHEMA_JSON__", json.dumps(json_schema))
        .replace("__EXAMPLE_OPUS_JSON__", json.dumps(json.dumps(EXAMPLE_OPUS, indent=2)))
        .replace("__EXAMPLE_SONNET_JSON__", json.dumps(json.dumps(EXAMPLE_SONNET, indent=2)))
    )

    OUTPUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_HTML.write_text(rendered, encoding="utf-8")
    print(f"wrote {OUTPUT_HTML.relative_to(REPO_ROOT)} ({len(rendered):,} chars)")


if __name__ == "__main__":
    main()
