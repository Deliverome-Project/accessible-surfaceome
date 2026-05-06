"""JensenLab COMPARTMENTS: download channel TSVs and normalize them.

Two subcommands::

    python -m accessible_surfaceome.sources.compartments download
    python -m accessible_surfaceome.sources.compartments build

``download`` fetches the five channel TSVs (integrated, knowledge,
experiments, textmining, predictions) for taxon 9606 from
https://download.jensenlab.org/. The ``textmining`` channel is filtered
at download time to surface-relevant GO terms (the raw upstream is
~850 MB and dominated by non-surface terms). License: CC-BY-4.0.
Reference: Binder et al., Database (Oxford), 2014, 10.1093/database/bau012.

``build`` normalizes those TSVs for the M1 candidate-universe merge.

Input (all under ``data/external/jensenlab_compartments/``):

- ``human_compartment_integrated_full.tsv``   — columns
  ``ensp, symbol, go_id, go_name, stars`` (stars float 0-5)
- ``human_compartment_knowledge_full.tsv``    — columns
  ``ensp, symbol, go_id, go_name, source, evidence_code, stars``
- ``human_compartment_experiments_full.tsv``  — columns
  ``ensp, symbol, go_id, go_name, source, evidence_desc, stars``
  **rows with ``source == "HPA"`` are dropped here** to avoid
  double-counting the first-class HPA source in the candidate-universe
  merge. (First-5-row inspection on 2026-04-17 confirmed HPA rows are
  inline in this channel.)
- ``human_compartment_textmining_full.tsv``   — filter-at-download to
  surface terms; columns
  ``ensp, symbol, go_id, go_name, zscore, stars, url``
- ``human_compartment_predictions_full.tsv``  — columns
  ``ensp, symbol, go_id, go_name, method, raw, stars``

Plus the shared ENSP mapping under
``data/external/uniprot_ensembl_xrefs/ensp_to_uniprot.tsv``.

Output: ``data/processed/jensenlab_compartments/jensenlab_compartments_human_snapshot.tsv``
with one row per (UniProt primary, ENSP) pair, restricted to the
**surface-candidate pool**: ENSPs where
``max(compartments_experiments_stars_max, compartments_textmining_stars_max)
>= POOL_STARS_THRESHOLD`` (default 2, JensenLab's "low-but-meaningful"
cutoff). ENSPs that only have noise-tier stars=1 textmining hits — the
JensenLab tagger lights up on any casual abstract co-mention — or are
supported only by knowledge / predictions (both provenance-only in the
merge) are dropped before they reach the candidate-universe merge,
matching how SURFY / CSPA / DeepTMHMM pool their inputs upstream. The
flag threshold (``compartments_surface_flag``) stays at stars >= 3
within this pool.

Columns:

- identifiers: ``uniprot_accession``, ``ensembl_protein_id``,
  ``compartments_gene_symbol``
- per-channel max stars across the configured SURFACE_TERMS:
  ``compartments_integrated_stars_max``,
  ``compartments_knowledge_stars_max``,
  ``compartments_experiments_stars_max`` (HPA rows excluded),
  ``compartments_textmining_stars_max``,
  ``compartments_predictions_stars_max``
- ``compartments_surface_terms`` — comma-joined GO IDs that contributed
  any surface-term support across the flag-eligible channels
  (experiments ∖ HPA ∪ textmining)
- derived: ``compartments_low_confidence_only`` (1 iff only textmining
  stars ≤ 2 support it, with no experiments support), ``compartments_surface_flag``
  (1 iff ``max(experiments[∖HPA], textmining)`` ≥ 3)
- provenance: ``compartments_split_mapping_ambiguous``

Flag rule mirror (kept in sync with ``build_candidate_universe.py``'s
pre-publish assertion):

    compartments_surface_flag = 1 iff
      max(experiments_stars_max, textmining_stars_max) >= 3
      AND compartments_split_mapping_ambiguous == 0
      AND compartments_corroborated == 1    (set at merge time)

**The ``compartments_corroborated`` gate is applied at the merge step
in build_candidate_universe.py**, NOT here — this script emits the
flag at its pre-corroboration value (``max(experiments, textmining) >=
3 AND split_mapping_ambiguous == 0``). The corroboration requirement
suppresses ~66 text-mining-only lone-COMPARTMENTS calls on non-surface
proteins (TP53, MYC, ALB, INS, IFNG, IL1B, BCL2 etc.) that would
otherwise enter the universe. See build_candidate_universe.py and
docs/reports/2026-04-17-jensenlab-compartments-integration.md.

Note: the final split-ambiguity zero-out and the corroboration gate
are both applied in the merge. This script emits the flag at its
pre-merge value.

**Why predictions is excluded from the flag.** COMPARTMENTS's
predictions channel wraps WoLF PSORT + YLoc-HighRes — sequence-based
localization predictors in the same family as SURFY (ML surfaceome
classifier) and DeepTMHMM (TM topology predictor), both of which are
already first-class sources in the candidate-universe merge. Empirically
the predictions channel drives ~73% of the pre-filter hits at stars ≥ 3
and is 100% PSORT-on-GO:0005886 (as of 2026-04-17), so including it
would effectively give the sequence-predictor family a third vote.
``compartments_predictions_stars_max`` is preserved as a provenance
column. See ``docs/reports/2026-04-17-jensenlab-compartments-integration.md``
for the full analysis.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.request import Request, urlopen

import pandas as pd

from accessible_surfaceome.sources._support.traceability import (
    USER_AGENT,
    build_file_record,
    download_binary,
    sha256_file,
    utc_now_iso,
    write_manifest,
)
from accessible_surfaceome.sources._support.ensembl_mapping import (
    load_ensembl_mapping,
)

from accessible_surfaceome.paths import REPO_ROOT as ROOT

DATASET = "jensenlab_compartments"
INPUT_DIR = ROOT / "data" / "external" / "jensenlab_compartments"
ENSEMBL_XREF_DIR = ROOT / "data" / "external" / "uniprot_ensembl_xrefs"
DEFAULT_OUTPUT_DIR = ROOT / "data" / "processed" / "jensenlab_compartments"
OUTPUT_TSV = "jensenlab_compartments_human_snapshot.tsv"
SUMMARY_JSON = "jensenlab_compartments_build_summary.json"
MANIFEST_JSON = "jensenlab_compartments_build_traceability.json"

# Surface GO terms — strict subset, kept in lockstep with the GO source's
# pruned set in ``src/accessible_surfaceome/sources/go.py``. Dropped from an
# earlier version: ``GO:0005886`` (plasma membrane — too broad, includes
# cytoplasmic-face and lateral-PM proteins) and ``GO:0031225`` (anchored
# component of membrane — any membrane, not PM-specific). Each remaining
# term is unambiguously surface-exposed.
SURFACE_TERMS: set[str] = {
    "GO:0009986",  # cell surface
    "GO:0009897",  # external side of plasma membrane
    "GO:0005887",  # integral component of plasma membrane
}

# Pool-membership threshold. An ENSP enters the emitted snapshot iff
# max(experiments_stars_max, textmining_stars_max) >= POOL_STARS_THRESHOLD.
# Chosen to match JensenLab's "low-but-meaningful" star cutoff — stars
# of 1 are a single casual co-mention in any abstract (noise-tier for
# the tagger). stars=2 corresponds to z-score ~4, which the tagger
# considers above-background. Predictions / knowledge do NOT gate pool
# membership (both are provenance-only in the merge), so an ENSP
# supported only by PSORT or GO curation drops out here.
POOL_STARS_THRESHOLD = 2.0

# Column layouts (TSVs have no header).
INTEGRATED_COLS = ["ensp", "symbol", "go_id", "go_name", "stars"]
KNOWLEDGE_COLS = ["ensp", "symbol", "go_id", "go_name", "source", "evidence_code", "stars"]
EXPERIMENTS_COLS = ["ensp", "symbol", "go_id", "go_name", "source", "evidence_desc", "stars"]
TEXTMINING_COLS = ["ensp", "symbol", "go_id", "go_name", "zscore", "stars", "url"]
PREDICTIONS_COLS = ["ensp", "symbol", "go_id", "go_name", "method", "raw", "stars"]


def _read_channel(path: Path, columns: list[str]) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(
            f"Missing {path.relative_to(ROOT)}. Run "
            "`uv run python src/accessible_surfaceome/candidates/download_jensenlab_compartments.py` first."
        )
    df = pd.read_csv(path, sep="\t", dtype=str, header=None, names=columns).fillna("")
    return df


def _restrict_to_surface_terms(df: pd.DataFrame) -> pd.DataFrame:
    return df[df["go_id"].isin(SURFACE_TERMS)].copy()


def _per_ensp_max_stars(df: pd.DataFrame) -> pd.Series:
    """Return a Series keyed on ENSP with the max ``stars`` value."""
    if df.empty:
        return pd.Series(dtype=float)
    stars = pd.to_numeric(df["stars"], errors="coerce").fillna(0.0)
    return stars.groupby(df["ensp"]).max()


def _per_ensp_surface_terms(df: pd.DataFrame) -> pd.Series:
    """Return a Series keyed on ENSP with comma-joined surface GO IDs seen."""
    if df.empty:
        return pd.Series(dtype=str)
    return (
        df.groupby("ensp")["go_id"]
        .apply(lambda s: ",".join(sorted(set(s))))
    )


def _build_parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build COMPARTMENTS snapshot for the M1 merge.")
    p.add_argument("--input-dir", type=Path, default=INPUT_DIR)
    p.add_argument("--xref-dir", type=Path, default=ENSEMBL_XREF_DIR)
    p.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return p.parse_args(argv)


def build_main(argv: list[str] | None = None) -> None:
    args = _build_parse_args(argv)
    in_dir: Path = args.input_dir
    out_dir: Path = args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"reading COMPARTMENTS channels from {in_dir.relative_to(ROOT)} ...")
    integrated = _read_channel(in_dir / "human_compartment_integrated_full.tsv", INTEGRATED_COLS)
    knowledge = _read_channel(in_dir / "human_compartment_knowledge_full.tsv", KNOWLEDGE_COLS)
    experiments = _read_channel(in_dir / "human_compartment_experiments_full.tsv", EXPERIMENTS_COLS)
    textmining = _read_channel(in_dir / "human_compartment_textmining_full.tsv", TEXTMINING_COLS)
    predictions = _read_channel(in_dir / "human_compartment_predictions_full.tsv", PREDICTIONS_COLS)
    print(
        f"  integrated={len(integrated):,}  knowledge={len(knowledge):,}  "
        f"experiments={len(experiments):,}  textmining={len(textmining):,}  "
        f"predictions={len(predictions):,}"
    )

    # Restrict to SURFACE_TERMS. Textmining is already pre-filtered at
    # download, but re-applying here is cheap and keeps the loader
    # self-consistent.
    integrated_s = _restrict_to_surface_terms(integrated)
    knowledge_s = _restrict_to_surface_terms(knowledge)
    experiments_s = _restrict_to_surface_terms(experiments)
    textmining_s = _restrict_to_surface_terms(textmining)
    predictions_s = _restrict_to_surface_terms(predictions)

    # Drop HPA rows from the experiments channel — first-class HPA source
    # is ingested separately; retaining these would double-count HPA IF.
    n_experiments_before = len(experiments_s)
    experiments_s = experiments_s[experiments_s["source"] != "HPA"].copy()
    n_experiments_hpa_dropped = n_experiments_before - len(experiments_s)

    # Per-ENSP max stars per channel, over surface terms only.
    integrated_max = _per_ensp_max_stars(integrated_s)
    knowledge_max = _per_ensp_max_stars(knowledge_s)
    experiments_max = _per_ensp_max_stars(experiments_s)
    textmining_max = _per_ensp_max_stars(textmining_s)
    predictions_max = _per_ensp_max_stars(predictions_s)

    # Build the per-ENSP table from ENSPs whose flag-eligible channels
    # (experiments ∖ HPA, textmining) meet POOL_STARS_THRESHOLD. This
    # is the surface-candidate pool, analogous to SURFY's
    # is_surface==1 filter and DeepTMHMM's 2,360-accession run scope.
    # ENSPs supported only by knowledge / predictions (provenance-only
    # in the merge) or by noise-tier stars=1 textmining are dropped.
    eligible_ensps: set[str] = set()
    for ensp, stars in experiments_max.items():
        if float(stars or 0.0) >= POOL_STARS_THRESHOLD:
            eligible_ensps.add(str(ensp).strip())
    for ensp, stars in textmining_max.items():
        if float(stars or 0.0) >= POOL_STARS_THRESHOLD:
            eligible_ensps.add(str(ensp).strip())
    eligible_ensps.discard("")
    ensps = eligible_ensps

    n_dropped_below_pool = 0
    all_surface_term_ensps: set[str] = set()
    for s in (experiments_max, textmining_max, predictions_max,
              knowledge_max, integrated_max):
        all_surface_term_ensps.update(s.index)
    all_surface_term_ensps.discard("")
    n_dropped_below_pool = len(all_surface_term_ensps) - len(ensps)

    # Pull a gene-symbol lookup from whichever channel has the ENSP first
    # (integrated has the widest coverage).
    symbol_lookup: dict[str, str] = {}
    for channel_df in (integrated_s, knowledge_s, experiments_s,
                       textmining_s, predictions_s):
        for ensp, sym in zip(channel_df["ensp"], channel_df["symbol"]):
            if ensp and ensp not in symbol_lookup and sym:
                symbol_lookup[ensp] = sym

    # Comma-joined surface-term lists for the flag-eligible channels only
    # (experiments ∖ HPA, textmining) — these are the channels that can
    # set compartments_surface_flag, so callers can audit exactly which
    # GO term lit up the flag. Predictions is deliberately excluded
    # from the flag (see docstring); its stars are carried as a
    # provenance column only.
    flag_terms = pd.concat([experiments_s, textmining_s], ignore_index=True)
    flag_surface_terms = _per_ensp_surface_terms(flag_terms)

    rows = []
    for ensp in sorted(ensps):
        ex = float(experiments_max.get(ensp, 0.0) or 0.0)
        tm = float(textmining_max.get(ensp, 0.0) or 0.0)
        pr = float(predictions_max.get(ensp, 0.0) or 0.0)
        kn = float(knowledge_max.get(ensp, 0.0) or 0.0)
        it = float(integrated_max.get(ensp, 0.0) or 0.0)
        flag_channel_max = max(ex, tm)
        surface_flag = int(flag_channel_max >= 3)
        # low-confidence-only: only textmining stars (1-2) back this
        # ENSP; experiments contribute nothing. Predictions stars are
        # not part of this check because the predictions channel is
        # not a flag-eligible channel (see docstring). Mirrors GO
        # IEA-only semantic.
        low_conf = int(
            ex == 0
            and 1 <= tm <= 2
        )
        rows.append({
            "ensembl_protein_id": ensp,
            "compartments_gene_symbol": symbol_lookup.get(ensp, ""),
            "compartments_integrated_stars_max": it,
            "compartments_knowledge_stars_max": kn,
            "compartments_experiments_stars_max": ex,
            "compartments_textmining_stars_max": tm,
            "compartments_predictions_stars_max": pr,
            "compartments_surface_terms": flag_surface_terms.get(ensp, ""),
            "compartments_low_confidence_only": low_conf,
            "compartments_surface_flag": surface_flag,
        })
    per_ensp = pd.DataFrame(rows)

    # Map ENSP → UniProt primary.
    _ensg_map, ensp_map = load_ensembl_mapping(args.xref_dir)
    print(f"  loaded ENSP mapping ({len(ensp_map):,} ENSPs → UniProt)")

    per_ensp["_primaries"] = per_ensp["ensembl_protein_id"].map(
        lambda e: list(ensp_map.get(str(e).strip(), []))
    )
    per_ensp["_n_primaries"] = per_ensp["_primaries"].map(len)
    n_unmapped = int((per_ensp["_n_primaries"] == 0).sum())
    n_split = int((per_ensp["_n_primaries"] >= 2).sum())
    per_ensp["compartments_split_mapping_ambiguous"] = (per_ensp["_n_primaries"] >= 2).astype(int)

    per_ensp_mapped = per_ensp[per_ensp["_n_primaries"] >= 1].copy()
    per_ensp_mapped = per_ensp_mapped.explode("_primaries").reset_index(drop=True)
    per_ensp_mapped["uniprot_accession"] = per_ensp_mapped["_primaries"].astype(str)
    per_ensp_mapped = per_ensp_mapped.drop(columns=["_primaries", "_n_primaries"])

    out_cols = [
        "uniprot_accession",
        "ensembl_protein_id",
        "compartments_gene_symbol",
        "compartments_integrated_stars_max",
        "compartments_knowledge_stars_max",
        "compartments_experiments_stars_max",
        "compartments_textmining_stars_max",
        "compartments_predictions_stars_max",
        "compartments_surface_terms",
        "compartments_low_confidence_only",
        "compartments_surface_flag",
        "compartments_split_mapping_ambiguous",
    ]
    df_out = per_ensp_mapped[out_cols].sort_values(
        ["uniprot_accession", "ensembl_protein_id"]
    ).reset_index(drop=True)

    output_tsv = out_dir / OUTPUT_TSV
    df_out.to_csv(output_tsv, sep="\t", index=False)

    summary = {
        "generated_at_utc": utc_now_iso(),
        "n_input_rows_per_channel": {
            "integrated": int(len(integrated)),
            "knowledge": int(len(knowledge)),
            "experiments": int(len(experiments)),
            "textmining": int(len(textmining)),
            "predictions": int(len(predictions)),
        },
        "n_surface_term_rows_per_channel": {
            "integrated": int(len(integrated_s)),
            "knowledge": int(len(knowledge_s)),
            "experiments": int(len(experiments_s)),
            "experiments_hpa_rows_dropped": int(n_experiments_hpa_dropped),
            "textmining": int(len(textmining_s)),
            "predictions": int(len(predictions_s)),
        },
        "n_ensps_with_any_surface_term_evidence": int(len(all_surface_term_ensps)),
        "n_ensps_after_pool_filter": int(len(per_ensp)),
        "n_dropped_below_pool_threshold": int(n_dropped_below_pool),
        "pool_threshold_stars": POOL_STARS_THRESHOLD,
        "pool_filter_rule": (
            "keep ENSP iff max(experiments_stars_max, textmining_stars_max) "
            f">= {POOL_STARS_THRESHOLD}"
        ),
        "n_unmapped_ensps": int(n_unmapped),
        "n_split_ensp_rows": int(n_split),
        "n_output_rows": int(len(df_out)),
        "n_unique_primaries": int(df_out["uniprot_accession"].nunique()),
        "n_surface_flag": int(df_out["compartments_surface_flag"].sum()),
        "n_low_confidence_only": int(df_out["compartments_low_confidence_only"].sum()),
        "n_split_mapping_ambiguous": int(df_out["compartments_split_mapping_ambiguous"].sum()),
        "surface_terms": sorted(SURFACE_TERMS),
    }
    (out_dir / SUMMARY_JSON).write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    channel_source_records = {}
    for name, fname in [
        ("integrated", "human_compartment_integrated_full.tsv"),
        ("knowledge", "human_compartment_knowledge_full.tsv"),
        ("experiments", "human_compartment_experiments_full.tsv"),
        ("textmining", "human_compartment_textmining_full.tsv"),
        ("predictions", "human_compartment_predictions_full.tsv"),
    ]:
        path = in_dir / fname
        channel_source_records[name] = {
            "local_path": str(path.relative_to(ROOT)),
            "sha256": sha256_file(path),
            "size_bytes": path.stat().st_size,
        }

    manifest = {
        "dataset": DATASET,
        "generated_at_utc": utc_now_iso(),
        "script": Path(__file__).relative_to(ROOT).as_posix(),
        "source_channels": channel_source_records,
        "ensembl_xref_mapping": {
            "local_path": str((args.xref_dir / "ensp_to_uniprot.tsv").relative_to(ROOT)),
            "sha256": sha256_file(args.xref_dir / "ensp_to_uniprot.tsv"),
            "size_bytes": (args.xref_dir / "ensp_to_uniprot.tsv").stat().st_size,
        },
        "outputs": {
            OUTPUT_TSV: {
                "local_path": str(output_tsv.relative_to(ROOT)),
                "sha256": sha256_file(output_tsv),
                "size_bytes": output_tsv.stat().st_size,
                "n_rows": int(len(df_out)),
                "primary_key": "uniprot_accession + ensembl_protein_id",
            },
        },
        "surface_terms": sorted(SURFACE_TERMS),
        "derived_columns": [
            {"name": "compartments_surface_flag",
             "rule": "max(experiments_stars_max [HPA rows dropped], "
                     "textmining_stars_max) >= 3"},
            {"name": "compartments_low_confidence_only",
             "rule": "experiments_stars_max == 0 AND "
                     "textmining_stars_max in [1, 2]"},
            {"name": "compartments_split_mapping_ambiguous",
             "rule": "1 iff the source ENSP mapped to >=2 UniProt primaries"},
        ],
        "excluded_evidence": [
            {"channel": "experiments",
             "rule": "rows where source == 'HPA' are dropped to avoid "
                     "double-counting the first-class HPA source"},
            {"channel": "knowledge",
             "rule": "knowledge stars max is carried as provenance but does "
                     "NOT contribute to compartments_surface_flag — the "
                     "knowledge channel re-ingests GO and UniProt-SubCell, "
                     "and would triple-count GO evidence in the merge"},
            {"channel": "predictions",
             "rule": "predictions stars max is carried as provenance but does "
                     "NOT contribute to compartments_surface_flag — the "
                     "predictions channel wraps WoLF PSORT + YLoc, "
                     "sequence-based predictors in the same family as SURFY "
                     "and DeepTMHMM which are already first-class sources. "
                     "Including it would triple-count ML-predictor evidence."},
        ],
    }
    (out_dir / MANIFEST_JSON).write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    print(f"wrote {output_tsv.relative_to(ROOT)}  ({len(df_out):,} rows, "
          f"{df_out['uniprot_accession'].nunique():,} unique UP primaries)")
    print(f"  unmapped ENSPs: {n_unmapped:,}  split-ambiguous rows: {n_split:,}  "
          f"HPA experiments rows dropped: {n_experiments_hpa_dropped:,}")
    print(f"  n_surface_flag={summary['n_surface_flag']:,}  "
          f"n_low_confidence_only={summary['n_low_confidence_only']:,}")


# ---- download ----

DOWNLOAD_BASE_URL = "https://download.jensenlab.org/"
DOWNLOAD_DEFAULT_DIR = INPUT_DIR

# (filename, filter-mode, note). filter-mode "none" saves the raw bytes;
# "surface_terms" streams line-by-line and keeps rows whose go_id
# (TSV column 3, 0-indexed 2) is in SURFACE_TERMS.
DOWNLOAD_FILES: list[tuple[str, str, str]] = [
    ("human_compartment_integrated_full.tsv", "none",
     "Integrated score (0-5 stars) across all four channels per GO term."),
    ("human_compartment_knowledge_full.tsv", "none",
     "Knowledge channel: curated-literature + DB annotations (re-ingests GO / UniProt-SubCell)."),
    ("human_compartment_experiments_full.tsv", "none",
     "Experiments channel (human-only); includes HPA IF rows with source=='HPA'."),
    ("human_compartment_textmining_full.tsv", "surface_terms",
     "Textmining channel: filter-at-download to SURFACE_TERMS GO IDs."),
    ("human_compartment_predictions_full.tsv", "none",
     "Predictions channel: WoLF PSORT + YLoc-HighRes. Carried as "
     "provenance only — sequence-based predictors are redundant with "
     "SURFY + DeepTMHMM in the M1 merge."),
]


def _download_fetch_raw(url: str, out_path: Path, force: bool) -> tuple[str, dict[str, str]]:
    if out_path.exists() and not force:
        return "reused", {}
    data, headers = download_binary(url, timeout=600)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(data)
    return "downloaded", headers


def _download_fetch_filtered(
    url: str,
    out_path: Path,
    *,
    surface_terms: set[str],
    force: bool,
) -> tuple[str, dict[str, str], int, int]:
    """Stream ``url``, write only rows whose go_id is in ``surface_terms``.

    Returns (status, response_headers, n_upstream_rows, n_kept_rows).
    """
    if out_path.exists() and not force:
        return "reused", {}, 0, 0
    out_path.parent.mkdir(parents=True, exist_ok=True)
    req = Request(url, headers={"User-Agent": USER_AGENT})
    kept = 0
    total = 0
    with urlopen(req, timeout=1800) as response:  # noqa: S310
        headers = {
            "content_type": response.headers.get("Content-Type", ""),
            "content_length_header": response.headers.get("Content-Length", ""),
            "etag": response.headers.get("ETag", ""),
            "last_modified": response.headers.get("Last-Modified", ""),
        }
        with out_path.open("wb") as dst:
            while True:
                line_bytes = response.readline()
                if not line_bytes:
                    break
                total += 1
                try:
                    line = line_bytes.decode("utf-8")
                except UnicodeDecodeError:
                    line = line_bytes.decode("utf-8", errors="replace")
                parts = line.rstrip("\n").split("\t")
                if len(parts) < 4:
                    continue
                go_id = parts[2]
                if go_id in surface_terms:
                    dst.write(line_bytes)
                    kept += 1
    return "downloaded", headers, total, kept


def _download_parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Download JensenLab COMPARTMENTS human TSVs.")
    p.add_argument("--output-dir", type=Path, default=DOWNLOAD_DEFAULT_DIR)
    p.add_argument("--force", action="store_true")
    return p.parse_args(argv)


def download_main(argv: list[str] | None = None) -> None:
    args = _download_parse_args(argv)
    out_dir: Path = args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    records = []
    filter_stats: dict[str, dict[str, int]] = {}
    for filename, mode, note in DOWNLOAD_FILES:
        url = DOWNLOAD_BASE_URL + filename
        out_path = out_dir / filename
        if mode == "surface_terms":
            status, headers, n_upstream, n_kept = _download_fetch_filtered(
                url, out_path,
                surface_terms=SURFACE_TERMS,
                force=args.force,
            )
            if status == "downloaded":
                print(
                    f"{filename}: {status}  kept {n_kept:,} / {n_upstream:,} rows "
                    f"(surface GO terms only)"
                )
                filter_stats[filename] = {
                    "n_upstream_rows": n_upstream,
                    "n_kept_rows": n_kept,
                }
            else:
                print(f"{filename}: {status}  ({out_path.stat().st_size:,} bytes)")
        else:
            status, headers = _download_fetch_raw(url, out_path, args.force)
            print(f"{filename}: {status}  ({out_path.stat().st_size:,} bytes)")
        record = build_file_record(
            repo_root=ROOT,
            file_path=out_path,
            source_url=url,
            dataset=DATASET,
            taxid="9606",
            species="Homo sapiens",
            status=status,
            response_headers=headers or None,
            note=note,
        )
        if filename in filter_stats:
            record["filter"] = {
                "mode": "surface_terms",
                "surface_terms": sorted(SURFACE_TERMS),
                "n_upstream_rows": filter_stats[filename]["n_upstream_rows"],
                "n_kept_rows": filter_stats[filename]["n_kept_rows"],
                "rule": "keep line iff TSV column 3 (go_id) is in surface_terms",
            }
        records.append(record)

    manifest_path = out_dir / "download_traceability.json"
    write_manifest(
        manifest_path,
        dataset=DATASET,
        script=Path(__file__).relative_to(ROOT).as_posix(),
        records=records,
        extras={
            "base_url": DOWNLOAD_BASE_URL,
            "license": "CC-BY-4.0",
            "citation": "Binder et al., Database (Oxford), 2014, DOI: 10.1093/database/bau012",
            "star_scale": "integer 1-5; higher = more confident",
            "surface_terms": sorted(SURFACE_TERMS),
        },
    )
    print(f"wrote {manifest_path.relative_to(ROOT)}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("download", help="Fetch JensenLab COMPARTMENTS channel TSVs.", add_help=False)
    sub.add_parser("build", help="Normalize the COMPARTMENTS snapshot for the M1 merge.", add_help=False)
    args, remainder = parser.parse_known_args(argv)
    if args.command == "download":
        download_main(remainder)
    elif args.command == "build":
        build_main(remainder)


if __name__ == "__main__":
    main()
