"""Prompt assembly for the literature tag-site agent (benchmark / production modes).

Ports the agentic extracellular tag-site prompt. In ``production`` mode the agent
is additionally handed the *computed* sequence + per-residue topology so it can
name exact residue junctions and have them verified against the real sequence
(spec §7.1, §9). ``benchmark`` mode withholds those to score pure retrieval.
"""
from __future__ import annotations

import hashlib
import logging

from .normalize import topology_runs
from .schema import SOURCE_TIERS, TagSiteProposal, TagSiteResult

_log = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a protein-engineering research agent. For ONE human cell-surface protein, find sites
that can carry a SHORT epitope tag (~13-23 aa, e.g. ALFA `PSRLEEELRRRLTEP` + GS linkers) on the
EXTRACELLULAR face without breaking folding, trafficking, or function.

Work in this order: find the evidence, pin the position, check the constraints, classify.

1. EVIDENCE — PUBLISHED INSERTIONS ONLY

The LEDGER — span-verified clips from real papers and preprints — is your only source of
citations. Ground EVERY site in ONE ledger line; cite nothing outside it, propose nothing it
does not support.

A line qualifies only if it reports an insertion actually TOLERATED — epitope-tag knock-in,
fluorescent-protein fusion, transposon/domain-insertion screen, or antibody-epitope insertion —
at the site itself, or in the SAME loop/domain of THIS protein (a close ortholog counts,
labelled 'indirect').

These do NOT qualify, however precisely they name residues:
- a soluble ECTODOMAIN or single-domain construct secreted as a separate protein for structure,
  binding or crystallography. The construct must be full-length and membrane-anchored.
- an Fc-fusion or decoy-receptor reagent.
- ANTIBODY EPITOPE MAPPING — where an antibody binds is not where a tag was inserted.
- a commercial plasmid whose tag POSITION is unstated; you cannot pin insert_after_residue.
- a tag on an INTRACELLULAR terminus or loop, unless it is an explicit validated snorkel.

Never justify a site by domain boundaries, topology, solvent exposure, conservation, or any
structural inference — that is the deterministic pipeline's job, done with computed RSA/DSSP.

Doubt the evidence -> drop the site. No qualifying insertion -> ZERO sites, which is the right
answer, not a failure. (Doubt about a single RESIDUE is a different thing — see 2.)

REPORT EVERY SITE THE LEDGER SUPPORTS, not only the best-evidenced one. Two papers pinning two
different junctions in the same loop are TWO sites, and the weaker-validated one is still a site
— rank it lower, do not drop it. A well-evidenced site is no reason to stop reading, and neither
is a terminal one when the ledger also grounds an internal.

Read every ledger line before you conclude a site is not there: the modalities it spans rarely
say "tag" in the abstract — FLAG / HA / Myc / ALFA / V5, fluorescent-protein fusion, HaloTag /
SNAP-tag / CLIP-tag, bungarotoxin-binding site, AviTag, tetracysteine, transposon and
domain-insertion screens.

Per site:
- `supporting_quote` — the VERBATIM ledger line, copied, never paraphrased. It is re-checked
  against the ledger; not found -> `entailment_verified=false` and down-ranked. A fabricated
  quote is worse than none.
- `source_tier` — 'paper' > 'patent' > 'vendor'. A vendor page never outranks a paper.

2. POSITION

UniProt canonical numbering. `insert_after_residue = N` puts the tag between N and N+1; report
residue_before (= N) and residue_after (= N+1) COPIED from the sequence given. A mismatch
invalidates the site.

Papers state a position three ways, all valid:
- spelled out in prose — "the tag follows the signal peptide (Alanine 34)", "at the codon for
  glycine 101";
- three-letter or spaced — "Thr436", "Ala 102";
- a bare code in a PRIMER / HDR-TEMPLATE table amid nucleotide sequence — often the authoritative
  label where the prose is vague, so never dismiss a clip for looking like raw DNA.

Papers also differ, sometimes internally, on whether the named residue sits BEFORE or AFTER the
junction. Resolve it: if the named letter matches the sequence at n, the paper means residue n;
the surrounding text says whether the tag goes after n (insert_after_residue = n) or before it
(n - 1). If the flanking residues are identical both readings fit — take the one putting the tag
in the extracellular span, say so in the rationale, and report the site. A one-residue
uncertainty never justifies withholding one.

RUN PYTHON rather than reasoning over the sequence in your head, which is unreliable for anything
positional. Paste the sequence in as a string. Use it to:
- recover an offset when the paper's NUMBERING FRAME may not be the canonical isoform
  (mature-protein numbering = stated position + signal-peptide length; another isoform; an
  ortholog) — search for the residue or peptide it names instead of assuming the number carries;
- check whether a named letter matches at n or n-1;
- locate a quoted peptide;
- measure the distance to a TM boundary.
Report what you computed; if it contradicts the printed number, say so and give the computed one.

3. CONSTRAINTS

Label each site:
- terminal_n / terminal_c — at an extracellular terminus. With a signal peptide an N-terminal tag
  MUST go AFTER the cleavage site: upstream is a silent failure, cleaved off with the SP.
- internal — in an extracellular loop or inter-domain linker.

Every site must be:
- extracellular — not TM, cytoplasmic, or inside a cleaved signal or propeptide;
- >=3 residues from any TM boundary;
- sterically plausible for a ~15-23 aa insert;
- functionally silent — clear of ligand/antibody surfaces, dimer interfaces, active sites,
  disulfide cysteines, N-/O-glycosylation sites, proteolytic sites, and residues with mutagenesis
  evidence of misfolding or ER retention.

4. CLASSIFY

`position_evidence`
- "validated" — a tag was published AT this residue/junction (+/-1) AND your quote names that
  position. Only then may `evidence_type` be "published tag insertion at this exact site"; set
  `cited_tag_residue` = insert_after_residue.
- "inferred" — precedent is ELSEWHERE in the loop/domain and you picked this position yourself;
  `cited_tag_residue` = the residue that actually carries the published tag (tag cited at 89,
  site proposed at 120 -> cited_tag_residue=89). Never dress an inferred position as an
  exact-site validation, and never move a validated position to a nicer nearby residue and keep
  calling it validated.

`evidence_type` — only: "published tag insertion at this exact site" | "published tag insertion
in the same loop or domain" | "published tolerance of a different insertion (transposon, FP
fusion)".

`validation_level`, best first: surface_and_function, surface_only, function_only, detected_only,
function_perturbed, not_measured. Order `sites` so higher-validation, paper-grounded ones come
first (lower `rank` = better). Never claim more than the paper measured: give the assay and
result, or 'NOT MEASURED' — never infer an impact. 'surface_and_function' means function
PRESERVED, not merely measured — REDUCED function, or function CONFOUNDED by the untagged protein
being present, is 'function_perturbed', with the reduction or confound in evidence_detail.

Return JSON only, in exactly the shape below."""

# evidence_type values that represent an actual validated tagging example (not inference).
VALIDATED_EVIDENCE_TYPES = frozenset(
    {
        "published tag insertion at this exact site",
        "published tag insertion in the same loop or domain",
        "published tolerance of a different insertion (transposon, fp fusion)",
        "published tolerance of a different insertion (transposon, fp-fusion)",
    }
)



# ---------------------------------------------------------------------------
# Output contract — GENERATED from the Pydantic models, never hand-maintained.
#
# `call_builder` validates the reply against `TagSiteResult` but never sends the
# schema to the API: the `messages.create` call passes system/messages/tools and
# nothing else. So every field the model must emit has to be stated in the
# prompt itself. Hand-listing them is what failed before — `uniprot_accession`
# and `sequence_length` were required and named nowhere, so EVERY run burned its
# repair budget rediscovering them, and `functional_or_expression_impact_measured`
# came back as a bool because the name reads boolean. Deriving the list from the
# model means adding a field updates the prompt in the same commit, by construction.
# ---------------------------------------------------------------------------

#: Fields the PIPELINE sets after the model replies. Asking the model for these
#: invites it to assert its own quote was verified, which is the one thing the
#: entailment gate exists to decide.
_PIPELINE_SET = ("entailment_verified", "quote_probative", "position_repaired", "rank")

#: Top-level identity the RUNNER stamps from its own arguments. Asking the model
#: to echo these back cost a repair round on every run and bought nothing.
_CODE_SET = (
    "gene_symbol", "uniprot_accession", "sequence_length", "topology_state",
    "supporting_pmid",
)

#: Short type tokens; the long semantics stay in the prose above rather than
#: being duplicated here.
_HINTS = {
    "rank": "1 = best",
    "insert_after_residue": "the junction",
    "residue_before": "1-letter, AT insert_after_residue",
    "residue_after": "1-letter, AT insert_after_residue+1",
    "tag_type": 'e.g. "short epitope, ALFA 15 aa, GS linkers"',
    "evidence_type": "one of the three in 4",
    "position_evidence": '"validated" | "inferred"',
    "cited_tag_residue": "null unless the cited tag is a point tag",
    "evidence_detail": "what was measured/observed, in what system",
    "functional_or_expression_impact_measured": (
        'assay + result, or "NOT MEASURED" -- a STRING, never true/false'
    ),
    "validation_level": "one of the six in 4",
    "source_tier": " | ".join(f'"{t}"' for t in SOURCE_TIERS),
    "supporting_pmid": "null for a preprint",
    "supporting_quote": "the VERBATIM ledger line",
    "rationale": "why this site, and what you computed",
}



def _enumerated(description: str | None) -> str:
    """The description itself when it is a short list of allowed values, else ""."""
    if not description:
        return ""
    text = description.strip()
    return text if "|" in text and len(text) <= 80 else ""


def _type_token(annotation: object) -> str:
    """`int | None` -> "int|null"; `str` -> "str"; `list[...]` -> "list"."""
    name = getattr(annotation, "__name__", None)
    if name in {"int", "str", "bool", "float"}:
        return name
    text = str(annotation)
    if "None" in text:
        inner = next((t for t in ("int", "str", "bool", "float") if t in text), "str")
        return f"{inner}|null"
    return "list" if text.startswith("list") else "str"


def format_output_contract() -> str:
    """The exact JSON shape, rendered from `TagSiteResult` + `TagSiteProposal`."""
    top = TagSiteResult.model_fields
    lines = ["OUTPUT — ONE JSON object with exactly these keys:", ""]
    lines.append(f"  {'sites':<10} {'list':<6} required — [] when nothing qualifies, which is a valid answer")
    for name, f in top.items():
        if name == "sites" or name in _CODE_SET:
            continue
        req = "required" if f.is_required() else f"optional, default {f.default!r}"
        lines.append(f"  {name:<10} {_type_token(f.annotation):<6} {req} — anything that did not fit a site")
    lines += ["", "Each entry of `sites`:", ""]
    for name, f in TagSiteProposal.model_fields.items():
        if name in _PIPELINE_SET or name in _CODE_SET:
            continue
        req = "required" if f.is_required() else f"default {f.default!r}"
        # Fall back to the schema's own description when it already enumerates the
        # allowed values ('"a" | "b"'), so a new closed-value field documents itself.
        hint = _HINTS.get(name) or _enumerated(f.description)
        lines.append(f"  {name:<42} {_type_token(f.annotation):<9} {req}{' — ' + hint if hint else ''}")
    lines += [
        "",
        f"Emit nothing else. {', '.join(_CODE_SET)} and "
        f"{', '.join(_PIPELINE_SET)} are set by the pipeline from what it already knows.",
    ]
    return "\n".join(lines)


SYSTEM_PROMPT = f"{SYSTEM_PROMPT}\n\n{format_output_contract()}"

#: Bump in the SAME commit as any edit to SYSTEM_PROMPT or the user turn.
#: `prompt_sha` fingerprints the text automatically; this is the human-readable
#: half, so a reviewer can tell a deliberate revision from an incidental one.
TAG_SITE_PROMPT_VERSION = "1.0.0"


def prompt_sha() -> str:
    """sha256 of the exact system prompt that produced a record."""
    return hashlib.sha256(SYSTEM_PROMPT.encode("utf-8")).hexdigest()

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

    dropped = [s for s in result.sites if not _is_validated(s.evidence_type)]
    for s in dropped:
        _log.info("  dropped %s — evidence_type %r is not a validated tagging example",
                  getattr(s, "residue_label", "?"), s.evidence_type)
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
    lines += ["", "There is no target number: zero is a valid answer, and so is five. Report "
              "every site the ledger supports — terminal and internal where the topology "
              "allows, and several in the same loop when separate papers pin separate "
              "junctions."]
    return "\n".join(lines)
