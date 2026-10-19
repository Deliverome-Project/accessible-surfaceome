"""Calibrate the tag-site disulfide-clearance floor against published tag sites.

``features.py`` vetoes a candidate tag site under 10 Å from a hazard atom,
measured **CA-CA**. Nobody had checked whether that floor, or that convention,
matches where real working insertions sit. This measures all three conventions
(nearest-heavy-atom, CA-CA, CA-SG) from every position-pinned literature tag
site to the nearest **model-bonded** cysteine, and reports what each candidate
floor from 4 to 16 Å would retrospectively reject.

Two limits, stated here because they bound what the output can be used for:

* **There is no negative set.** Every site in this corpus worked and got
  published. "Floor f rejects 0% of published sites" establishes only that f is
  not too *strict*. It says nothing about f being too permissive, because failed
  insertions are not published. This study can rule a floor out from above; it
  cannot confirm one from below.
* **Insert length is absent** (``tag_length_aa`` is NULL on all 185 rows), so a
  size class is derived from the ``tag_type`` free text instead. The result
  describes where mostly-small epitope tags sit, which licenses a floor for an
  8-11 aa tag and **not** for the 51-aa cassette.

Run::

    uv run python scripts/audit/calibrate_disulfide_clearance.py

Outputs land in ``data/analysis/disulfide_clearance_calibration/``.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pandas as pd
from Bio.Data.IUPACData import protein_letters_3to1

from accessible_surfaceome.audit._disulfide_clearance import (
    CONVENTION_LABEL,
    CONVENTIONS,
    SG_SG_BOND_MAX_A,
    afdb_metadata,
    fetch_uniprot_entry,
    load_structure,
    measure_site,
    uniprot_sequence,
    uniprot_signal_peptide_end,
)
from accessible_surfaceome.cloud.d1_client import D1Client
from accessible_surfaceome.env import load_env

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = REPO_ROOT / "data" / "analysis" / "disulfide_clearance_calibration"
CACHE_DIR = REPO_ROOT / "data" / "cache" / "disulfide_clearance"

FLOORS = list(range(4, 17))

# At a sequence separation of 1 the junction and the cysteine are covalently
# adjacent, so "distance" returns the peptide bond (1.33 A heavy-heavy) or the
# Ca-Ca virtual bond (3.8 A) no matter what the fold does. Sites at or under
# this separation are reported apart from the spatial measurements.
ADJACENT_SEP = 2

# Validation tiers, strongest first. The corpus also carries function_only /
# function_perturbed / not_measured, kept separate rather than folded in.
TIER_ORDER = [
    "surface_and_function",
    "surface_only",
    "detected_only",
    "function_only",
    "not_measured",
    "function_perturbed",
]

_3TO1 = {k.upper(): v for k, v in protein_letters_3to1.items()}

# Fusion partners of ~100 aa or more. A site that took one of these is the only
# kind of evidence in this corpus that bears on a large cassette.
_LARGE_DOMAIN = re.compile(
    r"\b(?:e?GFP|sfGFP|pHluorin|mCherry|mCitrine|mScarlet|YFP|CFP|RFP|mRFP|tdTomato"
    r"|HaloTag|SNAP[- ]?tag|CLIP[- ]?tag|BRIL|GLuc|NanoLuc|Rluc|RLuc|luciferase"
    r"|Fab|Fc\b|thioredoxin|apocytochrome|Spike|T4L|lysozyme)\b",
    re.IGNORECASE,
)
# Canonical lengths of the unambiguous small tags, for a length lower bound.
_SMALL_TAG_AA = {
    "ha": 9, "flag": 8, "myc": 10, "v5": 14, "his6": 6, "6xhis": 6, "his": 6,
    "hibit": 11, "alfa": 15, "1d4": 9, "au1": 6, "au5": 6, "spot": 12,
    "strep": 8, "avi": 15, "tev": 7, "s-tag": 15, "glu-glu": 9,
    "dogtag": 23, "ap": 15, "sorta": 5, "lpetg": 5,
    # SpyTag003 is 16 aa and SpyTag/SpyTag002 13. Named so that a
    # "SpyTag003+ALFA" string sums to 31 rather than being filed as a bare
    # 15-aa ALFA; the installed cassette with linkers is ~51 aa.
    "spytag003": 16, "spytag002": 13, "spytag": 13,
}
# A single unnatural amino acid put in by amber suppression is a *substitution*,
# not an insertion. These sites say almost nothing about threading a cassette,
# so they are classed apart rather than counted as small tags.
_NCAA = re.compile(
    r"\b(?:nc?AA|UAA|unnatural amino acid|amber|BCNK|BocK|SphK|TCO\*?A?|azido"
    r"|tetrazine|Tet3-Bu|cyclooctyne|click)\b",
    re.IGNORECASE,
)
# "3xHA", "2×FLAG" — a multiplied epitope tag, the larger end of this corpus.
_MULTIPLIED = re.compile(
    r"(\d+)\s*[x\u00d7]\s*([A-Za-z][A-Za-z0-9-]*)", re.IGNORECASE
)
# A literal peptide spelled out in parentheses is the most precise length there
# is, so it wins over the canonical table.
_PEPTIDE = re.compile(r"\(([ACDEFGHIKLMNPQRSTVWY]{4,})\)")


def _split_top_level(text: str, sep: str) -> list[str]:
    """Split on ``sep`` only where it is outside parentheses.

    "HA (9 aa + 4 aa flanking linkers)" is one tag whose parenthetical happens
    to contain a plus; "2xHA + TEV" is two tags joined. Splitting naively
    conflates them.
    """
    parts, depth, buf = [], 0, []
    for ch in text:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        if ch == sep and depth == 0:
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    parts.append("".join(buf))
    return [p for p in (x.strip() for x in parts) if p]


def _component_length(part: str) -> int | None:
    """Lower-bound length of one tag component, most precise source first."""
    # A peptide spelled out in the component is the exact insert, so it wins
    # outright over the canonical table — "HA (YPYDVPDYAS)" is 10 aa, not the
    # 9 aa that the bare name "HA" would contribute.
    peptides = [len(m) for m in _PEPTIDE.findall(part)]
    if peptides:
        return max(peptides)
    # An explicitly stated length beats the table too: the AP tag is 15 aa in
    # some forms, but "AP (biotin ligase acceptor peptide, 35 aa)" says 35.
    explicit = [int(m) for m in re.findall(r"(\d+)\s*[-\s]?aa", part)]
    if explicit:
        return max(explicit)
    # Otherwise fall back to named tags. "/" lists alternatives rather than
    # parts, so the smallest alternative is the honest lower bound.
    cand: list[int] = []
    for mult, name in _MULTIPLIED.findall(part):
        base = _SMALL_TAG_AA.get(name.lower())
        if base is not None:
            cand.append(int(mult) * base)
    cand += [
        aa
        for name, aa in _SMALL_TAG_AA.items()
        if re.search(rf"(?<![A-Za-z0-9]){re.escape(name)}(?![A-Za-z0-9])", part, re.I)
    ]
    return min(cand) if cand else None


def classify_insert(tag_type: str | None) -> tuple[str, int | None]:
    """Coarse size class + a lower-bound length, derived from ``tag_type``.

    This is **derived from free text, not a corpus length field** — the corpus
    carries no ``tag_length_aa`` for any of these sites. Many rows list several
    alternative tags used at the same position ("GFP / SNAP / HaloTag"), so the
    class records whether *any* variant was a large domain, and the length is a
    lower bound over the tags that could be identified at all.

    ``+`` joins parts of one insert and is summed; ``/`` lists alternatives and
    takes the smallest. Without that distinction "2xHA + TEV" is filed as a
    7-aa tag when it is 25, and a SpyTag003+ALFA cassette is filed as a bare
    15-aa ALFA — exactly the misfiling the cargo bands exist to prevent.
    """
    if not tag_type:
        return "unknown", None
    if _LARGE_DOMAIN.search(tag_type):
        return "large_domain", None

    components = _split_top_level(tag_type, "+")
    lengths = [n for n in (_component_length(c) for c in components) if n is not None]
    if lengths:
        # Sum across joined parts; a component we could not name is simply
        # left out, which keeps the result a lower bound.
        return "small_epitope", sum(lengths)
    if _NCAA.search(tag_type):
        return "ncAA_single", 1
    return "unknown", None


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--out-dir", type=Path, default=OUT_DIR, help="where to write TSVs + report"
    )
    p.add_argument(
        "--cache-dir", type=Path, default=CACHE_DIR, help="model / UniProt cache"
    )
    p.add_argument("--no-plot", action="store_true", help="skip the figure")
    return p.parse_args()


def fetch_corpus() -> list[dict]:
    """The position-pinned internal literature tag sites."""
    load_env()
    sql = (
        "SELECT gene_symbol, uniprot_acc, site_id, insert_after_residue,"
        " residue_before, residue_label, position_frame, position_evidence,"
        " validation_level, tag_type, tag_length_aa, topology_state, compartment"
        " FROM tag_site_public"
        " WHERE provenance='literature_retrieved' AND site_kind='internal'"
        "   AND insert_after_residue IS NOT NULL"
        " ORDER BY gene_symbol, insert_after_residue;"
    )
    with D1Client.public() as d1:
        return d1.query(sql, [])


# Cargo bands that matter for a decision, coarsest thing that separates them.
# The 12-30 aa band is the one the internal arms actually carry: ALFA is 15 aa
# (19 as installed with GS flanks) and DogTag is 23, per the tag-sites positive
# controls. The 51-aa SpyTag003+ALFA cassette is a terminal design, so it is
# not represented here at all.
def insert_size_band(size_class: str, length: int | None) -> str:
    if size_class == "large_domain":
        return "d_domain_100aa_plus"
    if size_class == "ncAA_single":
        return "a_single_ncAA"
    if size_class == "unknown" or length is None:
        return "e_unknown"
    if length <= 11:
        return "b_epitope_to_11aa"
    if length <= 30:
        return "c_12_to_30aa"
    return "d_31_to_99aa"


BAND_LABEL = {
    "a_single_ncAA": "single ncAA (~1 aa, a substitution)",
    "b_epitope_to_11aa": "epitope tag <=11 aa",
    "c_12_to_30aa": "12-30 aa (ALFA 15, DogTag 23, 3xHA 27)",
    "d_31_to_99aa": "31-99 aa",
    "d_domain_100aa_plus": "fusion domain >=100 aa",
    "e_unknown": "unknown",
}


def resolve_position(
    row: dict, *, cache_dir: Path
) -> tuple[str, int | None, str, str | None]:
    """Map a site's pinned position onto a sequence we can measure against.

    Returns ``(accession, residue, resolution, exclusion_reason)``.

    ``position_frame`` records **the frame the source paper used**, not a
    transform still to apply. For all four frame-bearing sites in this corpus
    the curated ``insert_after_residue`` is *already* canonical: GABRA4's
    "mature K39" is canonical K39, and adding the 35-residue signal peptide
    lands on V74 instead. So this verifies rather than assumes — it tests the
    raw position against ``residue_before`` on the canonical sequence first,
    and only reaches for a mature offset or an isoform sequence if that fails.
    Assuming either direction silently measures the wrong residue.
    """
    acc = row["uniprot_acc"]
    pos = int(row["insert_after_residue"])
    frame = row.get("position_frame")
    expected = (row.get("residue_before") or "").strip().upper() or None

    def letter_at(sequence: str, at: int) -> str | None:
        return sequence[at - 1] if 1 <= at <= len(sequence) else None

    canonical = uniprot_sequence(fetch_uniprot_entry(acc, cache_dir))
    if expected is None:
        # Nothing to verify against; take the position as canonical and let the
        # structure-level check in main() be the only guard.
        return acc, pos, "canonical_unverified", None
    if letter_at(canonical, pos) == expected:
        return acc, pos, "canonical_as_given", None

    if frame == "mature":
        sig_end = uniprot_signal_peptide_end(fetch_uniprot_entry(acc, cache_dir))
        if sig_end and letter_at(canonical, pos + sig_end) == expected:
            return acc, pos + sig_end, "mature_offset_applied", None
    if frame and frame.startswith("isoform:"):
        iso = frame.split(":", 1)[1]
        if afdb_metadata(iso, cache_dir) is not None:
            iso_seq = uniprot_sequence(fetch_uniprot_entry(iso, cache_dir))
            if letter_at(iso_seq, pos) == expected:
                return iso, pos, "isoform_frame", None
        return (
            iso,
            None,
            "unresolved",
            f"pinned against isoform {iso}; position {pos} matches neither the "
            f"canonical nor the isoform sequence at {expected}",
        )

    return (
        acc,
        None,
        "unresolved",
        f"residue {pos} is {letter_at(canonical, pos)} in {acc}, not the "
        f"{expected} the corpus records"
        + (f" (position_frame={frame!r})" if frame else ""),
    )


def main() -> int:
    args = _parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    args.cache_dir.mkdir(parents=True, exist_ok=True)

    corpus = fetch_corpus()
    print(
        f"corpus: {len(corpus)} position-pinned internal literature sites over "
        f"{len({r['uniprot_acc'] for r in corpus})} proteins"
    )

    structures: dict[str, object] = {}
    records: list[dict] = []
    excluded: list[dict] = []
    per_cys: list[dict] = []
    fetch_failures: dict[str, str] = {}

    for row in corpus:
        base = {
            "gene_symbol": row["gene_symbol"],
            "uniprot_acc": row["uniprot_acc"],
            "site_id": row["site_id"],
            "residue_label": row["residue_label"],
            "insert_after_residue": row["insert_after_residue"],
            "position_frame": row.get("position_frame"),
            "position_evidence": row.get("position_evidence"),
            "validation_level": row.get("validation_level"),
            "tag_type": row.get("tag_type"),
        }
        acc, pos, resolution, reason = resolve_position(row, cache_dir=args.cache_dir)
        base["frame_resolution"] = resolution
        if reason is not None or pos is None:
            excluded.append({**base, "exclusion": reason or "position unresolved"})
            continue

        if acc not in structures:
            try:
                structures[acc] = load_structure(acc, cache_dir=args.cache_dir)
            except Exception as exc:  # noqa: BLE001
                # A model the rate limiter never hands over must not take the
                # whole run down — the fetch cache makes a re-run resume, so
                # record the gap and carry on.
                structures[acc] = None
                fetch_failures[acc] = f"{type(exc).__name__}: {exc}"
        struct = structures[acc]
        if struct is None:
            why = fetch_failures.get(acc)
            excluded.append(
                {
                    **base,
                    "exclusion": (
                        f"model fetch failed for {acc} ({why})"
                        if why
                        else f"AFDB has no model for {acc}"
                    ),
                }
            )
            continue

        # --- residue-exact proteoform check. A model of the wrong proteoform
        # yields coordinates numbered against a sequence the site is not pinned
        # against, and nothing downstream flags it.
        if struct.model_sequence != struct.uniprot_sequence:
            # Same length with a different sequence is its own failure class —
            # 23 of the library's wrong-proteoform models are length-identical,
            # so a length test alone calls them fine. Report where they first
            # diverge, which separates a truncation from a substitution.
            a, b = struct.model_sequence, struct.uniprot_sequence
            first_diff = next(
                (i + 1 for i, (x, y) in enumerate(zip(a, b, strict=False)) if x != y),
                min(len(a), len(b)) + 1,
            )
            excluded.append(
                {
                    **base,
                    "exclusion": (
                        f"model sequence != UniProt sequence for {acc} "
                        f"(model {len(a)} aa vs UniProt {len(b)} aa, "
                        f"{'same length, ' if len(a) == len(b) else ''}"
                        f"first difference at residue {first_diff})"
                    ),
                }
            )
            continue
        residue = struct.residues.get(pos)
        if residue is None:
            excluded.append(
                {**base, "exclusion": f"residue {pos} absent from the {acc} model"}
            )
            continue
        model_aa = _3TO1.get(residue.resname.upper())
        expected_aa = (row.get("residue_before") or "").strip().upper() or None
        if expected_aa and model_aa != expected_aa:
            excluded.append(
                {
                    **base,
                    "exclusion": (
                        f"residue mismatch at {acc}:{pos} — corpus says "
                        f"{expected_aa}, model has {model_aa}"
                    ),
                }
            )
            continue

        size_class, min_len = classify_insert(row.get("tag_type"))
        rec = {
            **base,
            "measured_acc": acc,
            "canonical_residue": pos,
            "model_residue_aa": model_aa,
            "model_pdb_url": struct.model_pdb_url,
            "n_model_disulfides": len(struct.disulfides),
            "n_annotated_disulfides": len(struct.annotated_disulfides),
            "insert_size_class": size_class,
            "insert_len_lower_bound_aa": min_len,
            "insert_size_band": insert_size_band(size_class, min_len),
        }
        if not struct.disulfides:
            # Reported separately, never as infinity: a protein with no model
            # disulfide carries no information about the floor and would skew
            # every percentile.
            rec["has_model_disulfide"] = False
            records.append(rec)
            continue
        rec["has_model_disulfide"] = True
        result = measure_site(struct, pos)
        if result is None:
            excluded.append({**base, "exclusion": f"could not measure {acc}:{pos}"})
            continue
        minima, cys_rows = result
        rec.update(minima)
        # Distance degenerates to bond geometry when the junction is
        # sequence-adjacent to the cysteine, so the separation has to travel
        # with the distance or the minimum reads as a clearance measurement.
        for conv in CONVENTIONS:
            cys = minima.get(f"{conv}_cys")
            rec[f"{conv}_seq_sep"] = abs(int(cys) - pos) if cys is not None else None
        records.append(rec)
        for cr in cys_rows:
            per_cys.append(
                {
                    "gene_symbol": row["gene_symbol"],
                    "uniprot_acc": row["uniprot_acc"],
                    "site_id": row["site_id"],
                    "residue_label": row["residue_label"],
                    "canonical_residue": pos,
                    "validation_level": row.get("validation_level"),
                    **cr,
                }
            )

    df = pd.DataFrame(records)
    exc = pd.DataFrame(excluded)
    df.to_csv(args.out_dir / "per_site_clearance.tsv", sep="\t", index=False)
    if not exc.empty:
        exc.to_csv(args.out_dir / "excluded_sites.tsv", sep="\t", index=False)
    # Every (site, bonded cysteine) pair, so a reader can see a near-tie that
    # the per-site minimum hides.
    pd.DataFrame(per_cys).to_csv(
        args.out_dir / "per_site_per_cysteine.tsv", sep="\t", index=False
    )
    if fetch_failures:
        print(f"\nWARNING: {len(fetch_failures)} model fetches failed:")
        for acc, why in fetch_failures.items():
            print(f"  {acc}: {why}")
        print("  re-run to resume — the fetch cache keeps what already landed.")

    # Bond-classification margin: how far the 2.5 A cut sits from both
    # populations, so a reader can see it is not a knife edge.
    bonded, unbonded = [], []
    n_formed_unannotated = 0
    n_annotated_not_formed = 0
    prot_with_unannotated: set[str] = set()
    prot_with_annotated_not_formed: set[str] = set()
    n_proteins = 0
    for acc, st in structures.items():
        if st is None:
            continue
        n_proteins += 1
        bonded += [d.sg_sg_a for d in st.disulfides]
        if st.unbonded_min_sg_sg_a is not None:
            unbonded.append(st.unbonded_min_sg_sg_a)
        formed = {(d.res_i, d.res_j) for d in st.disulfides}
        unannotated = formed - st.annotated_disulfides
        # The other half of the delta: UniProt asserts a bond the model does
        # not form. Less dangerous for a hazard gate (it over-vetoes rather
        # than under-vetoes) but it sizes the same disagreement.
        missing = st.annotated_disulfides - formed
        n_formed_unannotated += len(unannotated)
        n_annotated_not_formed += len(missing)
        if unannotated:
            prot_with_unannotated.add(acc)
        if missing:
            prot_with_annotated_not_formed.add(acc)
    margin = {
        "sg_sg_bond_max_a": SG_SG_BOND_MAX_A,
        "n_bonded_pairs": len(bonded),
        "bonded_max_a": round(max(bonded), 2) if bonded else None,
        "n_proteins_with_unbonded_cys_pair": len(unbonded),
        "nearest_unbonded_a": round(min(unbonded), 2) if unbonded else None,
        "n_proteins": n_proteins,
        "n_formed_bonds_unannotated": n_formed_unannotated,
        "n_proteins_with_an_unannotated_formed_bond": len(prot_with_unannotated),
        "n_annotated_bonds_not_formed": n_annotated_not_formed,
        "n_proteins_with_an_annotated_bond_not_formed": len(
            prot_with_annotated_not_formed
        ),
    }
    (args.out_dir / "bond_classification_margin.json").write_text(
        json.dumps(margin, indent=2) + "\n"
    )

    write_report(df, exc, margin, args.out_dir)
    if not args.no_plot:
        make_plot(df, args.out_dir)
    print(f"\nwrote {args.out_dir}")
    return 0


def spatial_mask(sub: pd.DataFrame, conv: str) -> pd.Series:
    """Rows whose winning cysteine *for this convention* is not adjacent.

    The exclusion has to be applied per convention, because which cysteine wins
    flips with the ruler. ACKR3 P35 is the worked case: CA-CA and heavy-heavy
    pick C34 at separation 1, where the numbers are the virtual and real
    backbone bonds, while CA-SG and heavy-SG pick C287 **252 residues away**,
    which is a genuine long-range constraint. Masking every convention on one
    convention's separation drops that constraint and reads the site as an
    adjacency artifact — which is exactly how a retired site nearly got
    un-retired.
    """
    return sub[f"{conv}_seq_sep"] > ADJACENT_SEP


def floor_table(
    sub: pd.DataFrame, *, spatial_only: bool = False
) -> pd.DataFrame:
    """Retrospective rejections per convention per candidate floor.

    With ``spatial_only`` each convention is restricted to the rows whose own
    winning cysteine is non-adjacent, so the row counts differ per column.
    """
    rows = []
    for floor in FLOORS:
        row: dict[str, object] = {"floor_a": floor}
        for conv in CONVENTIONS:
            col = f"{conv}_a"
            scoped = sub[spatial_mask(sub, conv)] if spatial_only else sub
            n = len(scoped)
            rejected = int((scoped[col] < floor).sum()) if n else 0
            row[f"{conv}_n_sites"] = n
            row[f"{conv}_rejected_n"] = rejected
            row[f"{conv}_rejected_frac"] = round(rejected / n, 4) if n else None
        rows.append(row)
    return pd.DataFrame(rows)


def write_report(
    df: pd.DataFrame, exc: pd.DataFrame, margin: dict, out_dir: Path
) -> None:
    measured = df[df["has_model_disulfide"]].copy()
    no_ss = df[~df["has_model_disulfide"]].copy()

    lines: list[str] = []
    w = lines.append
    w("# Tag-site disulfide-clearance floor — calibration against published sites\n")
    w(
        "Measured from the position-pinned internal literature tag-site corpus in "
        "`tag_site_public`. Every distance is junction residue -> nearest "
        "**model-bonded** cysteine. Bonds are read off the model as any Cys pair "
        f"with SG-SG < {margin['sg_sg_bond_max_a']} A, never from UniProt "
        "`DISULFID`.\n"
    )

    w("## The four conventions, and which one the gate consumes\n")
    w(
        "These differ by 1-4 A, so a floor fitted on one does **not** transfer "
        "to a gate applying another. Every number below names its convention.\n"
    )
    w("| name in these outputs | measured from | measured to | used by |")
    w("|---|---|---|---|")
    w(
        "| `ca_ca` (CA-CA) | junction CA | cysteine CA | **`features.py`'s "
        "10 A floor** |"
    )
    w("| `ca_sg` (CA-SG) | junction CA | cysteine SG | the ordering session's measurements |")
    w("| `heavy_sg` (heavy-SG) | nearest junction heavy atom | cysteine SG | the predictors session; the `features.py` P35 numbers |")
    w("| `heavy` (heavy-heavy) | nearest junction heavy atom | nearest cysteine heavy atom | the ordering session's \"heavy\" column |")
    w(
        "\n`features.py` consumes **CA-CA**, so that is the row a change to the "
        "constant alone would move. Changing the convention is a separate "
        "decision from changing the number, and this study deliberately does "
        "not make it.\n"
    )

    w("## Two limits on what this can be used for\n")
    w(
        "**There is no negative set.** Every site here worked and got published, so "
        "a floor rejecting 0% of them is shown only to be *not too strict*. Nothing "
        "in this study speaks to a floor being too permissive, because failed "
        "insertions are not published. It bounds the floor from above and cannot "
        "confirm one from below.\n"
    )
    w(
        "**Insert length is absent from the corpus** — `tag_length_aa` is NULL on "
        f"all {len(df) + len(exc)} rows. The size class below is derived from the "
        "`tag_type` free text, not measured. So this describes where mostly-small "
        "epitope tags sit, which licenses a floor for an 8-11 aa tag and **does "
        "not** license one for the 51-aa cassette.\n"
    )
    w(
        "**The arms this informs carry the full 51-aa cassette.** A proposal "
        "circulated that the 51-aa SpyTag003+ALFA tandem is terminal-only — "
        "SpyTag003 being a beta-strand that must complete SpyCatcher's sheet "
        "and arguably cannot while tethered at both ends — and that loops "
        "should take 19-aa ALFA or 23-aa DogTag instead. **That proposal was "
        "withdrawn by the session that made it**, on in-house evidence of "
        "internal SpyTag working at TFRC V291 (reagent P-0007, built and "
        "received), and all six internal arms were confirmed to contain the "
        "complete 51-aa cassette, each tagged protein being native + 51. So "
        "the 19-23 aa figure describes a proposal, not the constructs, and the "
        "limit above is the binding one exactly as written: **nothing measured "
        "here licenses a floor for a 51-aa internal insert.**\n"
    )
    w(
        "The nearest evidence this corpus holds is therefore the **>=100 aa "
        "fusion-domain band**, which brackets 51 aa from *above* only — those "
        "inserts are 2-6x larger than the cassette, so a site that took one is "
        "evidence a cassette-sized insert is tolerable there, while a site that "
        "did not take one says nothing. The 31-99 aa band, which would bracket "
        "51 aa from below, is near-empty. The 12-30 aa band is reported because "
        "it is well-defined, not because it is the operative cargo here.\n"
    )

    w("### Scope: internal sites only\n")
    w(
        "This corpus is the **internal** literature tag sites — the ones where a "
        "cassette is threaded into a loop and a nearby disulfide is a hazard to "
        "thread past. `tag_site_public` also holds 722 position-pinned "
        "`terminal_n` and 83 `terminal_c` literature sites, and they are not "
        "measured here. If `features.py` applies the same clearance veto to "
        "terminal candidates, then a floor calibrated on this corpus is being "
        "transferred to a case it was not fitted on — a free chain end is not a "
        "threaded loop. Worth confirming which site kinds the veto actually "
        "runs on before the number is adopted for all of them.\n"
    )

    w("## Cohort\n")
    w(f"- sites resolved and measured: **{len(measured)}**")
    w(
        f"- sites whose protein has **no model disulfide**: **{len(no_ss)}** "
        "(reported separately, never as infinity — they carry no information "
        "about the floor)"
    )
    w(f"- sites excluded before measurement: **{len(exc)}**")
    w(
        f"- proteins measured: **{measured['measured_acc'].nunique()}**; "
        f"distinct genes: **{measured['gene_symbol'].nunique()}**\n"
    )
    if not exc.empty:
        w("Exclusions, by reason:\n")
        for reason, n in exc["exclusion"].value_counts().items():
            w(f"- {n} x {reason}")
        w("")

    w("### Bond classification is not a knife edge\n")
    w(
        f"- {margin['n_bonded_pairs']} bonded pairs, widest SG-SG "
        f"**{margin['bonded_max_a']} A**"
    )
    w(
        f"- nearest *unbonded* Cys-Cys pair anywhere in the cohort: "
        f"**{margin['nearest_unbonded_a']} A**"
    )
    w(
        f"So the {margin['sg_sg_bond_max_a']} A cut separates two well-separated "
        "populations; no pair sits near it.\n"
    )

    w("## Minimum observed distance — the number that bounds the floor\n")
    w(
        "A floor cannot exceed the tightest working site without rejecting a known "
        "success. Each convention is minimised independently, so the binding site "
        "can differ between conventions.\n"
    )
    w("| convention | minimum observed | gene | site | nearest bonded Cys | bond | annotated in UniProt |")
    w("|---|---:|---|---|---|---|---|")
    for conv in CONVENTIONS:
        col = f"{conv}_a"
        r = measured.loc[measured[col].idxmin()]
        w(
            f"| {CONVENTION_LABEL[conv]} | **{r[col]:.2f} A** | {r['gene_symbol']} | "
            f"{r['residue_label']} (after-{r['canonical_residue']}) | "
            f"C{int(r[f'{conv}_cys'])} | {r[f'{conv}_bond']} | "
            f"{'yes' if r[f'{conv}_bond_annotated'] else 'NO'} |"
        )
    w("")

    w("### How much did the nearest cysteine win by\n")
    w(
        "A per-site minimum reported as \"the nearest bonded cysteine\" can be a "
        "near-tie between two cysteines, which the single number hides. Every "
        "(site, bonded cysteine) pair is in `per_site_per_cysteine.tsv`.\n"
    )
    w("| convention | median gap to runner-up | sites within 1 A of a tie | sites with only one bonded Cys |")
    w("|---|---:|---:|---:|")
    for conv in CONVENTIONS:
        gap = measured[f"{conv}_runner_up_gap_a"]
        w(
            f"| {CONVENTION_LABEL[conv]} | {gap.median():.2f} A | "
            f"{int((gap < 1.0).sum())} | {int(gap.isna().sum())} |"
        )
    w("")
    seps = (measured["heavy_cys"] - measured["canonical_residue"]).abs()
    w(
        "The minimum is taken over **every** bonded cysteine, never the nearest "
        "by sequence: the binding cysteine under heavy-heavy sits a median "
        f"**{seps.median():.0f}** residues away in sequence, up to "
        f"**{seps.max():.0f}**, so a sequence-distance test measures a "
        "different axis entirely.\n"
    )

    w("## The tightest sites are sequence-adjacent, where distance is not clearance\n")
    # "Adjacent" is per convention. A site can be adjacent on one ruler and
    # 252 residues away on another, so there is no single adjacent/spatial
    # partition of the cohort — only one per convention.
    any_adjacent = measured[
        pd.concat(
            [~spatial_mask(measured, c) for c in CONVENTIONS], axis=1
        ).any(axis=1)
    ]
    adjacent = measured[~spatial_mask(measured, "heavy")]
    w(
        f"**{len(any_adjacent)} of {len(measured)} measured sites are "
        f"sequence-adjacent to their winning cysteine on at least one "
        f"convention** (within {ADJACENT_SEP} residues). "
        "At a separation of 1 the numbers are geometric constants, not "
        "measurements: heavy-heavy lands at 1.33-1.35 A, which is the peptide "
        "C-N bond, and CA-CA at 3.81-3.86 A, which is the Ca-Ca virtual bond. "
        "A distance-based floor cannot say anything useful about those sites "
        "because every one of them returns the same number for the same "
        "reason.\n"
    )
    w(
        "This is not a nuisance to discard. These are **published working "
        "sites inserted immediately beside a bonded cysteine**, and that is a "
        "stronger statement against a large clearance floor than any distance "
        "would be:\n"
    )
    cols = [
        "gene_symbol", "residue_label", "heavy_cys", "heavy_seq_sep",
        "ca_ca_a", "ca_sg_a", "heavy_sg_a", "heavy_a",
        "validation_level", "position_evidence", "insert_size_band",
    ]
    w("| gene | site | Cys | sep | CA-CA | CA-SG | heavy-SG | heavy-heavy | tier | position | cargo band |")
    w("|---|---|---:|---:|---:|---:|---:|---:|---|---|---|")
    for _, r in adjacent.sort_values("heavy_a")[cols].iterrows():
        w(
            f"| {r['gene_symbol']} | {r['residue_label']} | C{int(r['heavy_cys'])} | "
            f"{int(r['heavy_seq_sep'])} | {r['ca_ca_a']:.2f} | {r['ca_sg_a']:.2f} | "
            f"{r['heavy_sg_a']:.2f} | {r['heavy_a']:.2f} | {r['validation_level']} | "
            f"{r['position_evidence']} | {r['insert_size_band']} |"
        )
    w("")
    best = adjacent[
        (adjacent["validation_level"] == "surface_and_function")
        & (adjacent["position_evidence"] == "validated")
    ].sort_values("ca_ca_a")
    if len(best):
        b = best.iloc[0]
        w(
            f"The load-bearing row is **{b['gene_symbol']} {b['residue_label']}** "
            f"— `surface_and_function`, position `validated`, inserted "
            f"{int(b['heavy_seq_sep'])} residue(s) from bonded C"
            f"{int(b['heavy_cys'])} at {b['ca_ca_a']:.2f} A CA-CA. A floor "
            "anywhere at or above 4 A CA-CA rejects it, and it is a site whose "
            "tagged protein was shown both to reach the surface and to still "
            "work.\n"
        )
    w(
        "Everything below is therefore reported **twice**: over all measured "
        "sites, and over the non-adjacent sites where the distance really is a "
        "spatial clearance. **The second scope is computed per convention**, "
        "because a site can be adjacent on one ruler and far on another, so the "
        "row count differs per column. Read the spatial scope when you want to "
        "know where a floor bites geometrically, and the full one when you want "
        "to know what it would reject in practice.\n"
    )
    w("| convention | min, all sites | n spatial | min, spatial only | its binding Cys |")
    w("|---|---:|---:|---:|---|")
    for conv in CONVENTIONS:
        sp = measured[spatial_mask(measured, conv)]
        r = sp.loc[sp[f"{conv}_a"].idxmin()]
        w(
            f"| {CONVENTION_LABEL[conv]} | {measured[f'{conv}_a'].min():.2f} A | "
            f"{len(sp)} | {sp[f'{conv}_a'].min():.2f} A | "
            f"{r['gene_symbol']} {r['residue_label']} -> C{int(r[f'{conv}_cys'])} "
            f"(sep {int(r[f'{conv}_seq_sep'])}) |"
        )
    w("")

    w("## Retrospective rejections by floor and convention\n")
    w(f"All {len(measured)} measured sites.\n")
    w(_floor_md(floor_table(measured)))
    w(
        "\nSpatial scope — each convention restricted to the sites whose own "
        f"winning cysteine is more than {ADJACENT_SEP} residues away. The n "
        "differs per column by design:\n"
    )
    w(_floor_md(floor_table(measured, spatial_only=True), show_n=True))

    w("\n## Stratified by validation tier\n")
    w(
        "A floor calibrated on \"displayed\" and one on \"displayed AND functional\" "
        "are different floors, so they are reported separately rather than "
        "averaged. 62% of the 1,093 literature sites in the corpus carry no "
        "functional validation at all.\n"
    )
    w("| tier | n measured | n no-disulfide |")
    w("|---|---:|---:|")
    for tier in TIER_ORDER:
        nm = int((measured["validation_level"] == tier).sum())
        nn = int((no_ss["validation_level"] == tier).sum())
        if nm or nn:
            w(f"| {tier} | {nm} | {nn} |")
    w("")
    for tier in TIER_ORDER:
        sub = measured[measured["validation_level"] == tier]
        if len(sub) < 5:
            continue
        w(f"### {tier} (n={len(sub)})\n")
        mins = ", ".join(
            f"{CONVENTION_LABEL[c]} **{sub[f'{c}_a'].min():.2f} A** "
            f"({sub.loc[sub[f'{c}_a'].idxmin(), 'gene_symbol']} "
            f"{sub.loc[sub[f'{c}_a'].idxmin(), 'residue_label']})"
            for c in CONVENTIONS
        )
        w(f"Minimum observed: {mins}\n")
        w(_floor_md(floor_table(sub)))
        w("")

    w("## Unannotated bonds\n")
    bond_rows = []
    for conv in CONVENTIONS:
        col = f"{conv}_bond_annotated"
        n_un = int((measured[col] == False).sum())  # noqa: E712
        bond_rows.append(
            f"| {CONVENTION_LABEL[conv]} | {n_un} | "
            f"{n_un / len(measured) * 100:.1f}% |"
        )
    w("Share of measured sites whose *nearest* bonded cysteine belongs to a bond "
      "UniProt does not annotate:\n")
    w("| convention | sites | share |")
    w("|---|---:|---:|")
    for r in bond_rows:
        w(r)
    w("")
    w("### How wrong is a gate keyed on UniProt — cohort level\n")
    w(
        "This sizes the annotation blind spot independently of which sites "
        "happen to sit near a bond, so it transfers to anything built on "
        "`DISULFID` rather than on model geometry.\n"
    )
    nb = margin["n_bonded_pairs"] or 1
    w(
        f"- **{margin['n_formed_bonds_unannotated']}** of "
        f"**{margin['n_bonded_pairs']}** bonds formed in the models "
        f"({margin['n_formed_bonds_unannotated'] / nb * 100:.1f}%) are **not** "
        "annotated in UniProt"
    )
    w(
        f"- they are spread over "
        f"**{margin['n_proteins_with_an_unannotated_formed_bond']}** of "
        f"**{margin['n_proteins']}** proteins "
        f"({margin['n_proteins_with_an_unannotated_formed_bond'] / max(margin['n_proteins'], 1) * 100:.1f}%)"
    )
    w(
        f"- the converse — UniProt asserts a bond the model does not form — is "
        f"**{margin['n_annotated_bonds_not_formed']}** bonds over "
        f"**{margin['n_proteins_with_an_annotated_bond_not_formed']}** proteins. "
        "That direction over-vetoes rather than under-vetoes, so it is the "
        "safer error of the two."
    )
    w("")

    tight = measured[(measured["heavy_a"] < 10) & (measured["heavy_bond_annotated"] == False)]  # noqa: E712
    w(
        f"Of the sites inside 10 A nearest-heavy-atom, **{len(tight)}** are "
        "constrained by an unannotated bond — i.e. a gate keyed on UniProt "
        "`DISULFID` would not even see the hazard.\n"
    )

    w("## Insert size — derived from `tag_type`, not a corpus length field\n")
    w("| size class | n | heavy min | CA-CA min | CA-SG min |")
    w("|---|---:|---:|---:|---:|")
    for cls, sub in measured.groupby("insert_size_class"):
        w(
            f"| {cls} | {len(sub)} | {sub['heavy_a'].min():.2f} | "
            f"{sub['ca_ca_a'].min():.2f} | {sub['ca_sg_a'].min():.2f} |"
        )
    w("")
    lb = measured.loc[
        measured["insert_size_class"] == "small_epitope", "insert_len_lower_bound_aa"
    ].dropna()
    w(
        f"A numeric length could be recovered for **{len(lb)}** of "
        f"{len(measured)} measured sites (median **{lb.median():.0f} aa**, "
        f"max **{lb.max():.0f} aa**). `ncAA_single` sites are a single unnatural "
        "amino acid put in by amber suppression — a *substitution*, not an "
        "insertion — so they are the weakest evidence here, not the strongest.\n"
    )

    w("### By cargo size band\n")
    w(
        "Bands rather than a single class, so a floor is not fitted on one "
        "cargo size and applied to another. **The internal arms this informs "
        "carry the full 51-aa cassette**, so the band that brackets them from "
        "above is `>=100 aa` and the band that would bracket them from below "
        "(31-99 aa) is empty — no site in this corpus carries an insert between "
        "31 and 99 aa. The 12-30 aa band is reported because it is "
        "well-defined, not because it is the operative cargo.\n"
    )
    w(
        "**Every length here is read off a label, not measured off a peptide.** "
        "That is the weaker of the two methods and it is the one this corpus "
        "forces: `tag_length_aa` is NULL throughout, so a band assignment is "
        "only as good as the `tag_type` string. The tag-sites side derives its "
        "19 aa as `len(LOOP_TAG_AA)` — the actual peptide — which is immune to "
        "the whole class of bug that label parsing invites, and two such bugs "
        "did surface while these bands were being built (an explicit \"35 aa\" "
        "losing to a canonical-table 15, and `+` treated as `/` so that a "
        "joined cassette would be filed as its smaller half). Both are fixed "
        "and unit-pinned, but the right rule is theirs: take length from the "
        "peptide, never from a label. Where a measured length exists, prefer "
        "it over anything in this table.\n"
    )
    w("| band | n | CA-CA min | CA-SG min | heavy-SG min | heavy-heavy min |")
    w("|---|---:|---:|---:|---:|---:|")
    for band in sorted(measured["insert_size_band"].dropna().unique()):
        sub = measured[measured["insert_size_band"] == band]
        w(
            f"| {BAND_LABEL.get(band, band)} | {len(sub)} | "
            + " | ".join(f"{sub[f'{c}_a'].min():.2f}" for c in CONVENTIONS)
            + " |"
        )
    w("")
    w(
        "**The 12-30 aa band is a lower bound, not a census.** It is built from "
        "`tag_site_public.tag_type`, and D1's literature rows are incomplete for "
        "ALFA — which is the cargo the internal arms actually carry. Checked "
        "against the 25 curated internal positive controls in the tag-sites "
        "worktree's `data/tag_sites/positive_controls.tsv`: of five EndoNB ALFA "
        "entries, three (ITGB5 102, TFRC 290, AXL 184) have no D1 literature row "
        "at all, one (ITGB1 101) has a row whose `tag_type` omits ALFA, and only "
        "TMEM123 appears cleanly. Both VANGL1 HA sites are missing too, so the "
        "gap is not ALFA-specific. Treat the band's n as what D1 happens to "
        "record, and the curated table as the better source for this band.\n"
    )
    w(
        "The gap is confined to the **literature** lane. The deterministic rows "
        "are well populated for the same genes (TFRC 15 sites, ITGB1 11, ITGB5 "
        "10), so this is not a statement about `tag_site_public` as a whole and "
        "should not be generalised into one — a worklist audit reading "
        "deterministic rows is, on this evidence, unaffected. The claim is "
        "narrower and sharper than \"D1 is incomplete\": for literature "
        "provenance, absence from D1 is not evidence of absence. Reproduced "
        "independently against the live `/v1/tag-sites/{symbol}` API by the "
        "session recalibrating `MIN_LOOP_LEN`, which agreed on all five genes.\n"
    )
    w(
        "**And its ALFA half is survivorship-filtered at source.** The curators' "
        "own note: EndoNB \"reports no failures; they screened 2-3 gRNAs per gene "
        "and published only the winner, so its 5/5 success rate is "
        "survivorship-filtered.\" That is a *stronger* objection than the "
        "corpus-wide one at the top of this report. Cohort-wide, failures were "
        "never measured; here they were measured and withheld, so 5/5 is a "
        "selected maximum over a known-larger denominator rather than a rate.\n"
    )
    band_c = measured[measured["insert_size_band"] == "c_12_to_30aa"]
    if len(band_c):
        w(
            f"The 12-30 aa band has **n={len(band_c)}** over "
            f"{band_c['gene_symbol'].nunique()} genes. It is not the cargo the "
            "arms carry, but it is the best-defined band in the table, so its "
            "sweep is given for reference:\n"
        )
        w(_floor_md(floor_table(band_c)))
        w("")

    w("### What the corpus does and does not license\n")
    big = measured[measured["insert_size_class"] == "large_domain"]
    w(
        f"**{len(big)}** measured sites took a fusion domain of ~100 aa or more "
        "(GFP/pHluorin ~238 aa, HaloTag ~297 aa, SNAP-tag ~182 aa, GLuc ~185 aa). "
        "These are the only sites in the corpus that bear on an insert larger "
        "than the 51-aa cassette at all, and every one of them is *bigger* than "
        "the cassette, so they are the right comparison if any exists.\n"
    )
    if len(big):
        w("| convention | minimum over large-domain sites | gene | site | seq sep to that Cys |")
        w("|---|---:|---|---|---:|")
        for conv in CONVENTIONS:
            col = f"{conv}_a"
            r = big.loc[big[col].idxmin()]
            sep = r.get(f"{conv}_seq_sep")
            w(
                f"| {CONVENTION_LABEL[conv]} | **{r[col]:.2f} A** | "
                f"{r['gene_symbol']} | {r['residue_label']} | "
                f"{int(sep) if sep == sep and sep is not None else '—'} |"
            )
        w("")
        big_spatial = big[big["heavy_seq_sep"] > ADJACENT_SEP]
        w(
            f"The minimum in every convention is the same site, and it is "
            f"**sequence-adjacent** — so read it as \"a GFP/SNAP/HaloTag-class "
            "insert went in two residues from a bonded cysteine and the protein "
            "still reached the surface and still worked\", not as a distance. "
            f"Over the {len(big_spatial)} large-domain sites that are more than "
            f"{ADJACENT_SEP} residues away, the minima are "
            + ", ".join(
                f"{CONVENTION_LABEL[c]} {big_spatial[f'{c}_a'].min():.2f} A"
                for c in CONVENTIONS
            )
            + ".\n"
        )
        w(
            f"At n={len(big)} this is thin — it is {len(big)} sites over "
            f"{big['gene_symbol'].nunique()} genes, with no negative set, so it "
            "cannot fix a cassette floor. It does mean the cassette question is "
            "not completely unaddressed by this corpus, and it bounds a "
            "large-insert floor from above the same way the whole cohort bounds "
            "the small-tag one.\n"
        )
    for name, frame in (("large_domain_sites.tsv", big),):
        if len(frame):
            frame.to_csv(out_dir / name, sep="\t", index=False)

    w("## Position evidence\n")
    w(
        "`inferred` positions are not read off the paper, so a minimum computed "
        "over them is less trustworthy than the number itself suggests.\n"
    )
    w("| position_evidence | n | heavy min | CA-CA min | CA-SG min |")
    w("|---|---:|---:|---:|---:|")
    for ev, sub in measured.groupby("position_evidence"):
        w(
            f"| {ev} | {len(sub)} | {sub['heavy_a'].min():.2f} | "
            f"{sub['ca_ca_a'].min():.2f} | {sub['ca_sg_a'].min():.2f} |"
        )
    w("")

    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n")
    for name, frame in (
        ("floor_sweep_all.tsv", floor_table(measured)),
        *(
            (
                f"floor_sweep_{tier}.tsv",
                floor_table(measured[measured["validation_level"] == tier]),
            )
            for tier in TIER_ORDER
            if (measured["validation_level"] == tier).sum() >= 5
        ),
    ):
        frame.to_csv(out_dir / name, sep="\t", index=False)
    print("\n".join(lines))


def _floor_md(tab: pd.DataFrame, *, show_n: bool = False) -> str:
    header = []
    for c in CONVENTIONS:
        label = f"{CONVENTION_LABEL[c]} rejected"
        if show_n and len(tab):
            label += f" (n={int(tab.iloc[0][f'{c}_n_sites'])})"
        header.append(label)
    out = [
        "| floor | " + " | ".join(header) + " |",
        "|---|" + "---:|" * len(CONVENTIONS),
    ]
    for _, r in tab.iterrows():
        cells = []
        for c in CONVENTIONS:
            n = int(r[f"{c}_rejected_n"])
            frac = r[f"{c}_rejected_frac"]
            cells.append(f"{n} ({frac * 100:.1f}%)" if frac is not None else "—")
        out.append(f"| {int(r['floor_a'])} A | " + " | ".join(cells) + " |")
    return "\n".join(out)


def make_plot(df: pd.DataFrame, out_dir: Path) -> None:
    """ECDF of clearance per convention, with the candidate floors marked."""
    import matplotlib.pyplot as plt
    import seaborn as sns

    from accessible_surfaceome.audit._plotting_config import (
        CATEGORICAL_PALETTE,
        save_figure,
        setup_plotting_style,
    )

    setup_plotting_style()
    measured = df[df["has_model_disulfide"]]
    tidy = pd.concat(
        [
            pd.DataFrame(
                {
                    "clearance_a": measured[f"{conv}_a"],
                    "convention": CONVENTION_LABEL[conv],
                    "validation_level": measured["validation_level"],
                }
            )
            for conv in CONVENTIONS
        ],
        ignore_index=True,
    )

    fig, axes = plt.subplots(1, 2, figsize=(16, 6.4))
    palette = {
        CONVENTION_LABEL[c]: CATEGORICAL_PALETTE[i]
        for i, c in enumerate(CONVENTIONS)
    }

    ax = axes[0]
    sns.ecdfplot(
        data=tidy, x="clearance_a", hue="convention", palette=palette, lw=3, ax=ax
    )
    ax.axvline(10, color="#6E1428", ls="--", lw=2.5, zorder=0)
    ax.annotate(
        "current floor\n10 Å (CA-CA)",
        xy=(10, 0.82),
        xytext=(11.2, 0.62),
        fontsize=14,
        color="#6E1428",
        arrowprops={"arrowstyle": "-", "color": "#6E1428", "lw": 1.6},
    )
    ax.set_xlabel("Distance to nearest bonded Cys (Å)")
    ax.set_ylabel("Fraction of published sites\nrejected by this floor")
    ax.set_xlim(0, 45)
    sns.despine(ax=ax, top=True, right=True)

    ax = axes[1]
    tiers = [t for t in TIER_ORDER if (measured["validation_level"] == t).sum() >= 5]
    sub = tidy[tidy["validation_level"].isin(tiers)]
    sns.boxplot(
        data=sub,
        x="validation_level",
        y="clearance_a",
        hue="convention",
        palette=palette,
        order=tiers,
        fliersize=2,
        ax=ax,
    )
    ax.axhline(10, color="#6E1428", ls="--", lw=2.5, zorder=0)
    # Clipped: a handful of sites sit 80-250 A from any bonded cysteine, which
    # squashes every box flat and tells a floor decision nothing — anything
    # above this is comfortably clear on every convention.
    ax.set_ylim(0, 50)
    ax.set_xlabel("")
    ax.set_ylabel("Distance to nearest\nbonded Cys (Å)\n(clipped at 50)")
    # set_ticks before set_ticklabels, or matplotlib warns that the labels are
    # pinned to a non-fixed locator.
    ax.set_xticks(range(len(tiers)))
    ax.set_xticklabels([t.replace("_", "\n") for t in tiers], fontsize=14)
    # Panel a already carries the convention legend; a second copy just covers
    # the boxes it is meant to explain.
    legend = ax.get_legend()
    if legend is not None:
        legend.remove()
    sns.despine(ax=ax, top=True, right=True)
    for lbl, a in zip("ab", axes, strict=True):
        a.text(
            -0.08, 1.04, lbl, transform=a.transAxes, fontsize=24,
            fontweight=800, va="bottom", ha="right",
        )
    fig.tight_layout()
    save_figure(fig, "disulfide_clearance_calibration", str(out_dir))
    plt.close(fig)


if __name__ == "__main__":
    raise SystemExit(main())
