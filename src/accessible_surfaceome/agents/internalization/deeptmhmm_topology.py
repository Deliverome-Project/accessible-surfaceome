"""Source extracellular/cytoplasmic (E/C) topology for the model-prior track
from the repo's precomputed DeepTMHMM predictions.

DeepTMHMM's per-residue inside/outside call (I=cytoplasmic, O=extracellular,
M=TM helix, S=signal, B=beta-strand TM) is a stronger signal for "where do
endocytic sorting motifs sit" than UniProt's sparse topology features — the
whole point of the model-prior grade is that endocytic motifs only function in
cytoplasmic regions. Canonical predictions live in the human_canonical cohort
(keyed by base accession); alternative-isoform predictions live in the
human_isoforms cohort (keyed by the isoform-suffixed accession). Access is
credential-free (local .3line files); callers fall back to UniProt features
when a protein/isoform has no DeepTMHMM prediction.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from accessible_surfaceome.env import REPO_ROOT
from accessible_surfaceome.sources.deeptmhmm import parse_3line

_PRED_DIR = REPO_ROOT / "data" / "external" / "deeptmhmm_surfaceome_predictions"
# (cohort dir, key field): canonical records keyed by base accession,
# isoform records by the isoform-suffixed `uniprot_accession_full`.
_COHORTS: tuple[tuple[str, str], ...] = (
    ("human_canonical_non_hla", "uniprot_accession"),
    ("human_isoforms_from_afdb_non_hla", "uniprot_accession_full"),
)


@lru_cache(maxsize=1)
def load_index() -> dict[str, dict[str, Any]]:
    """accession -> DeepTMHMM record. Canonical records keyed by base
    accession, isoform records by isoform-suffixed accession. Returns an empty
    dict when the prediction files aren't hydrated (callers fall back to
    UniProt topology)."""
    idx: dict[str, dict[str, Any]] = {}
    for cohort, key_field in _COHORTS:
        path = _PRED_DIR / cohort / "predicted_topologies.3line"
        if not path.exists():
            continue
        for rec in parse_3line(path):
            key = rec.get(key_field) or rec["uniprot_accession"]
            idx.setdefault(key, rec)
    return idx


def deeptmhmm_record(
    isoform_id: str,
    *,
    is_canonical: bool,
    index: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    """DeepTMHMM record for an isoform accession, or None if not predicted.

    An alternative isoform matches only its own suffixed accession — never the
    canonical's base — so we don't mislabel an isoform with the canonical
    topology. The canonical isoform is often stored under the base accession,
    so it additionally tries the base form.
    """
    idx = load_index() if index is None else index
    rec = idx.get(isoform_id)
    if rec is None and is_canonical:
        rec = idx.get(isoform_id.split("-", 1)[0])
    return rec


def summarize_deeptmhmm_topology(rec: dict[str, Any]) -> str:
    """Compact E/C topology summary from a DeepTMHMM record, for the prompt."""
    parts = [f"DeepTMHMM {rec['deeptmhmm_label']}"]
    if rec.get("has_signal_peptide"):
        parts.append(f"signal peptide {rec['signal_peptide_length']} aa")
    tm = rec.get("tm_helix_count", 0)
    if tm:
        parts.append(f"{tm} TM helix/helices")
    beta = rec.get("beta_strand_count", 0)
    if beta:
        parts.append(f"{beta} beta-strand TM(s)")
    parts.append(
        f"N-terminus {rec['n_terminal_orientation']}, "
        f"C-terminus {rec['c_terminal_orientation']}"
    )
    parts.append(
        f"extracellular {rec['ecd_length_residues']} aa, "
        f"cytoplasmic {rec['icd_length_residues']} aa"
    )
    return "; ".join(parts) + "."
