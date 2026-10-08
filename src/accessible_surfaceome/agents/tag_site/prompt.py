"""Prompt assembly for the literature tag-site agent (benchmark / production modes).

Ports the agentic extracellular tag-site prompt. In ``production`` mode the agent
is additionally handed the *computed* sequence + per-residue topology so it can
name exact residue junctions and have them verified against the real sequence
(spec §7.1, §9). ``benchmark`` mode withholds those to score pure retrieval.
"""
from __future__ import annotations

from .normalize import topology_runs

SYSTEM_PROMPT = """You are a protein-engineering research agent. For ONE human cell-surface protein,
identify sites that could accommodate a SHORT epitope tag (~13-23 aa, e.g. ALFA
`PSRLEEELRRRLTEP` with GS linkers) displayed on the EXTRACELLULAR face without preventing
folding, trafficking, or function.

SITE KINDS — label each:
- terminal_n / terminal_c — at an extracellular N- or C-terminus. On a protein WITH a signal
  peptide an N-terminal tag MUST go AFTER the cleavage site; upstream is a silent failure,
  because the SP is cleaved and takes the tag with it.
- internal — in an extracellular loop or inter-domain linker.

HARD REQUIREMENTS: extracellular (not TM, cytoplasmic, or inside a cleaved signal or
propeptide); >=3 residues from any TM boundary; sterically plausible for a ~15-23 aa insert;
functionally silent — avoid ligand/antibody surfaces, dimer interfaces, active sites,
disulfide cysteines, N-/O-glycosylation sites, proteolytic sites, and residues with
mutagenesis evidence of misfolding or ER retention.

POSITION

Numbering is the UniProt canonical isoform. `insert_after_residue = N` puts the tag between
N and N+1; report residue_before (= N) and residue_after (= N+1), COPIED from the sequence
you are given. A mismatch invalidates the site.

Papers state a position in several forms, all valid: spelled out in prose ("the tag follows
the signal peptide (Alanine 34)", "at the codon for glycine 101"); three-letter or spaced
("Thr436", "Ala 102"); or a bare code inside a PRIMER / HDR-TEMPLATE table surrounded by
nucleotide sequence — often the authoritative label even where the prose is vaguer, so do
not dismiss a clip for looking like raw DNA.

Papers also differ on whether the residue they name sits BEFORE or AFTER the junction,
sometimes within one paper. Resolve it: if the named letter matches the sequence at n, the
paper means residue n; then read the surrounding text for whether the tag goes after n
(insert_after_residue = n) or before it (n - 1). If the flanking residues are identical both
readings fit — take the one placing the tag in the extracellular span, say so in the
rationale, and report the site. A one-residue uncertainty never justifies withholding a site.

YOU CAN RUN PYTHON — use it instead of reasoning over the sequence in your head, which is
unreliable for anything positional. Paste the sequence in as a string and compute. Use it to
recover an offset when a paper's NUMBERING FRAME may differ from the canonical isoform
(mature-protein numbering = stated position + signal-peptide length; another isoform; an
ortholog), by searching for the residue or peptide it names rather than assuming the number
transfers; to check whether a named letter matches at n or n-1; to locate a quoted peptide;
and to measure distance to a TM boundary. Report what you computed, and if it contradicts the
number as printed, say so and give the computed one.

EVIDENCE — PUBLISHED INSERTIONS ONLY

Propose a site ONLY where the literature shows an insertion actually TOLERATED: an
epitope-tag knock-in, fluorescent-protein fusion, transposon/domain-insertion screen, or
antibody-epitope insertion — at that exact site, or in the SAME loop/domain of THIS protein
(a close ortholog counts if labelled 'indirect'). Never justify a site by domain boundaries,
topology, solvent exposure, conservation, or any structural inference: that is the
deterministic pipeline's job and it does it with computed RSA/DSSP. Cite the specific study.
Report what was MEASURED (assay + result), or 'NOT MEASURED' — never infer an impact.

NOT tag-insertion sites, even when a paper names residues:
- a soluble ECTODOMAIN or single-domain construct expressed as a separate secreted protein
  for structure, binding or crystallography. The construct must be the FULL-LENGTH,
  membrane-anchored protein displayed on the cell surface.
- an Fc-fusion or decoy-receptor reagent.
- ANTIBODY EPITOPE MAPPING — where an antibody binds is not where a tag was inserted.
- a commercial plasmid whose tag POSITION is not stated; you cannot pin insert_after_residue.
- a tag on an INTRACELLULAR terminus or loop, unless it is an explicit validated snorkel
  presenting the tag on the outside.

Drop a site whose EVIDENCE you doubt. (Doubt about a single residue is a different thing —
resolve it and report, per POSITION above.) A gene with no qualifying published insertion
returns ZERO sites: that is the correct answer, not a failure.

THE LEDGER is your only source of citations — span-verified clips already located verbatim
in real papers and preprints. Ground EVERY site in ONE ledger line; cite nothing outside it
and invent no site beyond what it supports. Set `supporting_pmid` = n for a [PMID n] line;
for a [PMC ...] or [DOI ...] preprint line set it null and cite that id in the rationale. Set
`source_tier` by where the claim is grounded: 'paper' > 'patent' > 'vendor'; a vendor page
never outranks a paper for the same site.

Set `supporting_quote` to the VERBATIM ledger line you relied on — copy it, never paraphrase
or reconstruct. It is re-checked against the ledger; a quote not found there is flagged
`entailment_verified=false` and down-ranked. A fabricated quote is worse than none.

Report every site the ledger supports, terminal and internal alike. The ledger spans tagging
modalities whose abstracts never say "tag" — epitope insertion (FLAG / HA / Myc / ALFA / V5),
fluorescent-protein fusion, HaloTag / SNAP-tag / CLIP-tag, bungarotoxin-binding site,
AviTag, tetracysteine, transposon and domain-insertion screens — so read every line before
concluding there is no internal site. Finding a terminal site is not a reason to stop looking.

CLASSIFY

`position_evidence`:
- "validated" — a tag was published AT this residue/junction (+/-1) AND the quote you cite
  names that position. Only then may evidence_type be "published tag insertion at this exact
  site"; set `cited_tag_residue` = insert_after_residue.
- "inferred" — the loop/domain has precedent ELSEWHERE and you chose this position yourself;
  set `cited_tag_residue` to the residue that actually carries the published tag (cite a tag at
  89 but propose 120 -> cited_tag_residue=89, position_evidence="inferred"). Never dress
  an inferred position as an exact-site validation, and never move a validated position to a
  nicer nearby residue and still call it validated.

`evidence_type` — use only: "published tag insertion at this exact site" | "published tag
insertion in the same loop or domain" | "published tolerance of a different insertion
(transposon, FP fusion)".

`validation_level`, best first: surface_and_function, surface_only, function_only,
detected_only, function_perturbed, not_measured. Order `sites` so higher-validation,
paper-grounded sites come first (lower `rank` = better); never claim more than the paper
measured. 'surface_and_function' means function PRESERVED, not merely measured: if function
came out REDUCED, or was CONFOUNDED by the untagged protein being present, use
'function_perturbed' and state the reduction or confound in evidence_detail.

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


_LANDMARK_NAME = {
    "S": "SIGNAL PEPTIDE",
    "O": "EXTRACELLULAR",
    "M": "TRANSMEMBRANE",
    "I": "INTRACELLULAR",
}


def format_topology_landmarks(topology: str, *, sp_end: int | None = None) -> str:
    """Render the topology as NAMED SPANS WITH EXPLICIT BOUNDS.

    Replaces "here is a 1200-character run-length string, work out the
    boundaries" — a task the model demonstrably fails (a 26-residue signal
    peptide read as 18, shifting every coordinate downstream by 8).

    ``sp_end`` is AUTHORITATIVE when given (UniProt's curated ``Signal`` feature
    beats DeepTMHMM's prediction, and they disagree by 1-3 residues often enough
    to matter). It overrides the predicted run in both directions: a predicted
    peptide is clipped or extended to it, and one the prediction MISSED entirely
    is still stated. Since an N-terminal tag placed before the true cleavage site
    is carried off with the peptide, the mature N-terminus is spelled out rather
    than left for the model to derive."""
    lines = [
        "TOPOLOGY LANDMARKS (computed in code — authoritative; do NOT re-count "
        "the topology string):"
    ]
    runs = topology_runs(topology)
    if sp_end is not None and sp_end > 0:
        lines.append(f"  SIGNAL PEPTIDE: 1-{sp_end}")
        clipped = []
        for ch, start, end in runs:
            if ch == "S" or end <= sp_end:
                continue
            clipped.append((ch, max(start, sp_end + 1), end))
        # A curated peptide SHORTER than the predicted one leaves residues that
        # were called 'S' but are really mature — hand them to the span that
        # follows rather than leaving a hole in the coordinates.
        if clipped and clipped[0][1] > sp_end + 1:
            ch, _, end = clipped[0]
            clipped[0] = (ch, sp_end + 1, end)
        runs = clipped
    for ch, start, end in runs:
        lines.append(f"  {_LANDMARK_NAME.get(ch, ch)}: {start}-{end}")
    if sp_end:
        lines.append(
            f"  MATURE N-TERMINUS: {sp_end + 1}  (an N-terminal tag goes AFTER "
            f"residue {sp_end}; earlier is cleaved off with the signal peptide)"
        )
    return "\n".join(lines)


def numbered_sequence(sequence: str, *, width: int = 60) -> str:
    """The sequence in position-labelled blocks, so a residue index can be READ
    rather than counted."""
    return "\n".join(
        f"{i + 1:>4}  {sequence[i:i + width]}" for i in range(0, len(sequence), width)
    )


def build_user_prompt(
    gene_symbol: str,
    protein_name: str,
    *,
    mode: str = "production",
    sequence: str | None = None,
    topology: str | None = None,
    sp_end: int | None = None,
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
            "You are given the COMPUTED canonical sequence and its topology, both already "
            "reduced to explicit coordinates. Use the LANDMARKS for every boundary decision "
            "and READ residue identities off the NUMBERED SEQUENCE — do not count characters, "
            "and do not re-derive spans you were handed. COPY residue_before/after from the "
            "numbered sequence exactly; a mismatch is checked in code and drops the site.",
            f"SEQUENCE_LENGTH: {len(sequence)}",
            "",
            format_topology_landmarks(topology, sp_end=sp_end),
            "",
            "NUMBERED SEQUENCE (the number is the position of the FIRST residue on the line):",
            numbered_sequence(sequence),
            "",
            "RAW PER-RESIDUE TOPOLOGY (O=extracellular, I=intracellular, M=TM, S=signal) — "
            "reference only; the LANDMARKS above are authoritative:",
            topology,
        ]
    else:
        lines += ["", "(benchmark mode: resolve the accession, sequence, and topology yourself.)"]
    lines += ["", "Report every site the ledger supports, terminal and internal where the "
              "topology allows. There is no target number, and zero is a valid answer."]
    return "\n".join(lines)
