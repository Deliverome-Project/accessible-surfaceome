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

EVIDENCE — VALIDATED TAGGING EXAMPLES ONLY. Propose a site ONLY when web_search finds a
PUBLISHED example of a tag or other insertion actually TOLERATED there: an epitope-tag
knock-in, a fluorescent-protein fusion, a transposon/domain insertion screen, or an
antibody-epitope insertion — AT that exact site, OR in the SAME loop/domain of THIS protein
(a close ortholog is allowed if labelled 'indirect'). Do NOT propose sites justified only by
domain boundaries, topology, solvent exposure, conservation, or any general structural
inference — that is the deterministic pipeline's job, not yours, and it does it with computed
RSA/DSSP. Every site MUST cite the specific study. Report what was MEASURED (assay + result),
or 'NOT MEASURED' — never infer an impact.

allowed evidence_type values (use ONLY these — never 'structural inference' or 'topology
inference only'):
- "published tag insertion at this exact site"
- "published tag insertion in the same loop or domain"
- "published tolerance of a different insertion (transposon, FP fusion)"

SEARCH THOROUGHLY FOR INTERNAL SITES. If the protein has ANY extracellular loop (an `O`
stretch between TM helices, or a large ectodomain), you MUST make a real attempt to find at
least one INTERNAL insertion with published precedent — do not settle for terminal sites
alone. Run a GENERIC search (e.g. "<gene> tag", "<gene> epitope tag insertion") AND, because
many surface-labeling constructs are never called "tags" in the abstract, separate searches
for specific tagging modalities by NAME:
  FLAG / HA / Myc / ALFA / V5 epitope insertion; GFP / fluorescent-protein fusion insertion;
  HaloTag / SNAP-tag / CLIP-tag; **bungarotoxin-binding site (BBS)**; biotin-acceptor / AviTag;
  tetracysteine (FlAsH); transposon / domain-insertion screens.
The generic query alone often misses the niche modalities, so run those too. Do not stop at
the first hit; a terminal site does not excuse skipping the internal search.

POSITION HONESTY (required). For EVERY site set `position_evidence`:
- "validated" — a tag was published AT this exact residue/junction (or +/-1). Only then may
  evidence_type be "published tag insertion at this exact site". Set `cited_tag_residue` =
  insert_after_residue.
- "inferred" — the loop/domain has tagging precedent ELSEWHERE and you chose this specific
  position by structural reasoning. Set `cited_tag_residue` to the residue that actually
  carries the published tag (e.g. cite a tag at 89 but propose 120 -> cited_tag_residue=89,
  position_evidence="inferred"). Do NOT dress an inferred position as an exact-site validation.
Do not move a validated position to a "nicer" nearby residue and call it validated — if you
relocate it, it is inferred.

If you cannot find a validated tagging example, return FEWER sites — or an EMPTY sites list
with a rationale. A well-argued empty result is CORRECT and beats a structural-inference guess.

Return JSON only, matching the provided schema."""

# evidence_type values that represent an actual validated tagging example (not inference).
VALIDATED_EVIDENCE_TYPES = frozenset(
    {
        "published tag insertion at this exact site",
        "published tag insertion in the same loop or domain",
        "published tolerance of a different insertion (transposon, fp fusion)",
        "published tolerance of a different insertion (transposon, fp-fusion)",
    }
)


def keep_validated_sites(result):
    """Drop any proposed site whose evidence is structural/topology inference rather
    than a validated tagging example (defence-in-depth behind the prompt constraint).
    Mutates ``result.sites`` in place and returns it."""
    def _is_validated(evidence_type: str) -> bool:
        e = (evidence_type or "").strip().lower()
        if e in VALIDATED_EVIDENCE_TYPES:
            return True
        # tolerant match: an actual insertion is described, not mere inference
        return "insertion" in e and "inference" not in e and "topology" not in e

    result.sites = [s for s in result.sites if _is_validated(s.evidence_type)]
    return result


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
