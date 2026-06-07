"""Project the human canonical DeepTMHMM topology onto an ortholog.

Cross-species orthologs have evolutionarily conserved membrane topology,
but their Ensembl/UniProt sequence models — especially cynomolgus, which
are unreviewed TrEMBL auto-annotations (``A0A…`` accessions) — are often
truncated or padded. Running DeepTMHMM independently on those noisy
sequences yields the wrong topology:

* **EGFR cyno** (``A0A2K5WKD8``): a 704-of-1210-residue fragment that ends
  inside the ECD, so DeepTMHMM never sees the transmembrane helix and
  reports **0 TM** (human has 1).
* **CD81 cyno** (``A0A7N9DC29``): a padded 308-of-236-residue model where
  DeepTMHMM miscounts **3 TM** (human has 4).

This module restores the conserved topology by globally aligning the
ortholog to the human canonical (reusing the BLOSUM62 aligner already in
``merge.paralog_ecd_identity``) and copying each human residue's topology
label onto its aligned ortholog residue. Crucially it *distinguishes* a
truncated model — where a human ``'M'`` run aligns entirely to a gap in the
ortholog (``tm_absent_from_model``) — from a real topology call, instead of
silently emitting a wrong TM count.

**Orthologs only.** Do NOT project onto human isoforms: alternate-isoform
topology differences are genuine biological signal (soluble / decoy
isoforms) that the isoform-decoy detector depends on.
"""

from __future__ import annotations

from dataclasses import dataclass

from accessible_surfaceome.merge._sequence_identity import _aligner, _sanitize


@dataclass(frozen=True)
class ProjectedTopology:
    """Human topology mapped onto one ortholog's residues.

    ``per_residue_topology`` has ``len == len(ortholog_sequence)`` and only
    describes residues that physically exist in the ortholog model, so
    ``tm_helix_count`` is the number of TM helices *present in the model*.
    A human TM helix that fell into an ortholog gap (truncation) is NOT in
    the string — it's surfaced via ``tm_absent_from_model`` /
    ``n_tm_regions_absent`` so a consumer can show "conserved by homology,
    region absent from this model" rather than "topology diverged".
    """

    per_residue_topology: str
    tm_helix_count: int
    ecd_length_residues: int
    tm_absent_from_model: bool
    n_tm_regions_absent: int
    source: str = "projected_from_human_canonical"


def _count_runs(s: str, ch: str) -> int:
    """Number of maximal contiguous runs of ``ch`` in ``s``."""
    runs = 0
    prev = ""
    for c in s:
        if c == ch and prev != ch:
            runs += 1
        prev = c
    return runs


def project_human_topology_onto_ortholog(
    *,
    human_topology: str,
    human_sequence: str,
    ortholog_sequence: str,
) -> ProjectedTopology | None:
    """Map the human per-residue topology onto the ortholog via global
    BLOSUM62 alignment.

    Returns ``None`` — signalling the caller to keep the raw
    DeepTMHMM-on-ortholog values — when projection isn't meaningful:
    missing/empty inputs, a human topology/sequence length mismatch, or a
    fully soluble human protein (no ``'M'`` and no ``'O'`` to project).
    """
    if not human_topology or not human_sequence or not ortholog_sequence:
        return None
    if len(human_topology) != len(human_sequence):
        return None
    if "M" not in human_topology and "O" not in human_topology:
        # Soluble / inner-leaflet human protein — nothing membrane-topological
        # to project; the ortholog's own row is as good as any.
        return None

    h_seq = _sanitize(human_sequence)
    o_seq = _sanitize(ortholog_sequence)
    try:
        alignment = _aligner().align(h_seq, o_seq)[0]
    except (ValueError, KeyError, IndexError):
        return None

    n_o = len(ortholog_sequence)
    proj: list[str | None] = [None] * n_o
    human_aligned = [False] * len(human_topology)

    # alignment.aligned is shape (2, n_blocks, 2): equal-length, gap-free
    # blocks of [target_start,target_end] (human) / [query_start,query_end]
    # (ortholog). Copy the human label onto each aligned ortholog residue.
    aligned = alignment.aligned
    for (h_start, h_end), (o_start, o_end) in zip(aligned[0], aligned[1]):
        for k in range(int(h_end) - int(h_start)):
            hi = int(h_start) + k
            oi = int(o_start) + k
            if 0 <= oi < n_o and 0 <= hi < len(human_topology):
                proj[oi] = human_topology[hi]
                human_aligned[hi] = True

    # Ortholog-only insertions (proj[i] is None) carry the previous label
    # forward; leading insertions back-fill from the first assigned label.
    last: str | None = None
    for i in range(n_o):
        if proj[i] is not None:
            last = proj[i]
        elif last is not None:
            proj[i] = last
    if n_o and proj[0] is None:
        first = next((c for c in proj if c is not None), "I")
        for i in range(n_o):
            if proj[i] is None:
                proj[i] = first
            else:
                break
    projected = "".join(c if c is not None else "I" for c in proj)

    # A human TM helix is "absent from the model" when none of its residues
    # aligned to an ortholog residue (the ortholog sequence is truncated /
    # gapped through that helix).
    n_absent = 0
    i = 0
    h = human_topology
    while i < len(h):
        if h[i] == "M":
            j = i
            while j < len(h) and h[j] == "M":
                j += 1
            if not any(human_aligned[k] for k in range(i, j)):
                n_absent += 1
            i = j
        else:
            i += 1

    return ProjectedTopology(
        per_residue_topology=projected,
        tm_helix_count=_count_runs(projected, "M"),
        ecd_length_residues=projected.count("O"),
        tm_absent_from_model=n_absent > 0,
        n_tm_regions_absent=n_absent,
    )
