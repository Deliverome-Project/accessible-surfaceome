"""Prompt assembly for the literature tag-site agent (benchmark / production modes).

Ports the agentic extracellular tag-site prompt. In ``production`` mode the agent
is additionally handed the *computed* sequence + per-residue topology so it can
name exact residue junctions and have them verified against the real sequence
(spec §7.1, §9). ``benchmark`` mode withholds those to score pure retrieval.
"""
from __future__ import annotations

SYSTEM_PROMPT = """You are a protein-engineering research agent. Identify sites on ONE human
cell-surface protein that could accommodate a SHORT epitope tag (~13-23 aa, e.g. ALFA
`PSRLEEELRRRLTEP`, GS linkers) displayed on the EXTRACELLULAR face, without preventing the
protein from folding, trafficking, or functioning.

Two kinds of site are in scope; label each:
1. terminal_n / terminal_c — a tag at an extracellular N- or C-terminus. For an N-terminal
   tag on a protein WITH a signal peptide, the tag MUST go AFTER the cleavage site (placing
   it upstream is a silent failure — the SP is cleaved and takes the tag with it).
2. internal — inserted into an extracellular loop or inter-domain linker.

Hard requirements: extracellular (not TM / cytoplasmic / inside a cleaved signal or
propeptide); >=3 residues from any TM boundary; functionally silent (avoid ligand/antibody
surfaces, dimer interfaces, active sites, disulfide cysteines, N-/O-glycosylation sites,
proteolytic sites, and residues with mutagenesis evidence of misfolding/ER-retention);
sterically plausible for a ~15-23 aa insert.

Numbering (strict): UniProt canonical isoform; `insert_after_residue = N` puts the tag
between residue N and N+1; report residue_before (= residue N) and residue_after (= N+1).
When a computed sequence is provided, COPY residue_before/after from it exactly — a mismatch
invalidates the site.

Evidence: prefer published precedent. Use web_search to find published tag insertions,
GFP/transposon insertion screens, and structures. Rank by structural context, conservation,
distance from the ligand-binding face, and published insertion tolerance at/near the site.
Do NOT rank on low pLDDT alone. Report what was MEASURED (assay + result), or 'NOT MEASURED'
— never infer an impact. If no site can be defended, return an empty sites list with a
rationale; a well-argued abstention beats a fabricated site.

Return JSON only, matching the provided schema."""


def build_user_prompt(
    gene_symbol: str,
    protein_name: str,
    *,
    mode: str = "production",
    sequence: str | None = None,
    topology: str | None = None,
) -> str:
    """Assemble the user turn. ``production`` injects the computed sequence +
    topology; ``benchmark`` withholds them (gene + name only)."""
    if mode not in ("production", "benchmark"):
        raise ValueError(f"unknown mode: {mode!r}")
    lines = [
        f"GENE SYMBOL: {gene_symbol}",
        f"PROTEIN NAME: {protein_name}",
    ]
    if mode == "production":
        if not sequence or not topology:
            raise ValueError("production mode requires sequence and topology")
        lines += [
            "",
            "You are given the COMPUTED canonical sequence and per-residue DeepTMHMM topology "
            "(1 char/residue: O=extracellular, I=intracellular, M=TM, S=signal). Use them to "
            "pin exact residue junctions and COPY residue_before/after from the sequence.",
            f"SEQUENCE_LENGTH: {len(sequence)}",
            "COMPUTED SEQUENCE:",
            sequence,
            "COMPUTED TOPOLOGY:",
            topology,
        ]
    else:
        lines += ["", "(benchmark mode: resolve the accession, sequence, and topology yourself.)"]
    lines += ["", "Propose 3-5 ranked sites (terminal + internal where topology allows)."]
    return "\n".join(lines)
