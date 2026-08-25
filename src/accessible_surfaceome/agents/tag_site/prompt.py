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

EVIDENCE — VALIDATED TAGGING EXAMPLES ONLY. Propose a site ONLY when the LITERATURE shows a
PUBLISHED example of a tag or other insertion actually TOLERATED there: an epitope-tag
knock-in, a fluorescent-protein fusion, a transposon/domain insertion screen, or an
antibody-epitope insertion — AT that exact site, OR in the SAME loop/domain of THIS protein
(a close ortholog is allowed if labelled 'indirect'). Do NOT propose sites justified only by
domain boundaries, topology, solvent exposure, conservation, or any general structural
inference — that is the deterministic pipeline's job, not yours, and it does it with computed
RSA/DSSP. Every site MUST cite the specific study. Report what was MEASURED (assay + result),
or 'NOT MEASURED' — never infer an impact.

OUT OF SCOPE — NOT tag-insertion sites; do NOT report these even when a paper names the
residues (they are the exact false positives to avoid):
  - Recombinant / soluble ECTODOMAIN or single-domain constructs: the ectodomain (or one
    domain) expressed as a SEPARATE secreted/soluble protein for structure, binding, or
    crystallography (e.g. "CD22 d1-d7, residues 20-687, cloned into pHLsec"). The construct
    you cite must be the FULL-LENGTH, membrane-anchored protein DISPLAYED ON THE CELL SURFACE
    — not its isolated ectodomain.
  - Fc-fusion / decoy-receptor constructs: the ectodomain fused to an Fc or other soluble
    carrier as a reagent (e.g. AXL "reformatted as an Fc fusion decoy receptor"). Not a surface tag.
  - ANTIBODY EPITOPE MAPPING: where an antibody was found to BIND a region (e.g. EGFR "epitope
    between residues 375 and 380"). An epitope is where an antibody binds, NOT an inserted tag.
  - A commercial / generic expression plasmid whose tag POSITION is not stated (e.g.
    "pGENE-HA purchased from <vendor>") — you cannot pin insert_after_residue, so drop it.
  - A tag on an INTRACELLULAR terminus/loop (cytoplasmic C-terminal fusion) UNLESS it is an
    explicit validated snorkel that presents the tag on the extracellular surface.
When in doubt, DROP the site. A gene with no qualifying PUBLISHED insertion must return ZERO
literature sites — that is the correct, expected answer, never a failure to pad.

CANDIDATE PAPERS — your ONLY source of citations. You are given a list of pre-retrieved
papers (title + abstract + PMID, or DOI for a preprint) from a curated EuropePMC + PubTator
search PLUS a web_search discovery pass (retraction-filtered; a citation-sorted pass surfaces
classic methods papers; web_search adds recent preprints and constructs whose abstracts never
say "tag" — bungarotoxin-binding-site, HiBiT, snorkel — all hydrated to real, id-anchored
papers). Read them FIRST; set `supporting_pmid` for a PMID paper, or `supporting_pmid`=null +
cite the DOI in the rationale for a [preprint]. Do NOT cite a paper that is not in this list.
Set `source_tier` by where the claim is grounded: 'paper' (journal/PMC/preprint) > 'patent' >
'vendor'; papers are STRONGLY preferred and a vendor page never outranks a paper for the same site.

QUOTE YOUR EVIDENCE (checked automatically). For every site, set `supporting_quote` to a
VERBATIM sentence copied from the cited source text shown above (abstract / METHODS / RESULTS)
that states the tag was placed at this site and/or its validation. Copy it exactly — do NOT
paraphrase, translate, or reconstruct it. The pipeline searches the source text for this exact
string; if it is not found the site is flagged `entailment_verified=false` and down-ranked. If
no quotable passage is provided above for your cited paper, leave `supporting_quote` null
rather than inventing one — a fabricated quote is worse than none.

RANK BY VALIDATION STRENGTH (`validation_level`). The best sites are those where the tag was
shown to DISPLAY on the surface (non-permeabilized staining/labeling) AND preserve
function/expression vs untagged — set 'surface_and_function' and rank these first. Then
'surface_only', 'function_only', 'detected_only', 'function_perturbed', and last 'not_measured'.
Order the `sites` list so higher-validation, paper-grounded sites come first (lower `rank` =
better). Never upgrade a validation_level beyond what the paper actually measured.

'surface_and_function' MEANS FUNCTION PRESERVED, NOT MERELY FUNCTION MEASURED. If a paper
measures function but it comes out REDUCED, or the measurement is CONFOUNDED (not cleanly
isolated from the endogenous protein), do NOT claim 'surface_and_function' — use
'function_perturbed' and state the reduction/confound in evidence_detail. Two real examples of
what does NOT qualify as validated function:
  - SLC6A4 (hSERT), HA in EL2: the tagged transporter's Vmax is only ~55% of WT — function is
    measurably PERTURBED. -> 'function_perturbed', NOT 'surface_and_function'.
  - ANO1 (TMEM16A), 3xHA in ECL1: surface display is clean, but the Cl- current was recorded
    with endogenous TMEM16A co-expressed, so the tagged channel's function is inferred, not
    isolated — CONFOUNDED. -> 'function_perturbed' (or 'surface_only'), NOT 'surface_and_function'.

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
