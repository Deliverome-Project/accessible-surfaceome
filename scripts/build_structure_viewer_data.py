#!/usr/bin/env python3
"""Build per-UniProt structure-viewer JSONs from DeepTMHMM ``.3line`` output.

Reads canonical-isoform DeepTMHMM predictions at
``data/external/deeptmhmm_surfaceome_predictions/human_canonical_non_hla/predicted_topologies.3line``
and emits ``viewer/public/structure-viewer/{UNIPROT}.json`` per protein.
The Next.js per-gene page at ``viewer/app/[symbol]/page.tsx`` loads the
matching file via ``fs`` at SSG time, passes it as props to
``<StructureViewerCard>``, and the client-side 3Dmol viewer colors the
AlphaFold DB structure by these topology ranges.

The ``.3line`` format is three lines per entry:

    >sp|UNIPROT|SHORT_NAME | TYPE      (TYPE ∈ {TM, SP, SP+TM, BETA, GLOB})
    MSRWSRA...                          (one-letter sequence)
    IIIIIMMMM...OOOO...                 (per-residue topology: S/O/M/I/B)

Output schema (per UniProt) — must stay in sync with the TypeScript
type ``StructureViewerData`` in ``viewer/lib/structure-viewer.ts``::

    {
      "uniprot_acc": "O43493",
      "deeptmhmm_type": "SP+TM",
      "sequence_length": 437,
      "topology": "SSSSS...OOOOO...MMMMM...IIIII",
      "topology_ranges": {
        "M": [[start, end], ...],
        "O": [[start, end], ...],
        "I": [[start, end], ...],
        "S": [[start, end], ...],
        "B": [[start, end], ...]
      },
      "tm_helix_count": 1,
      "signal_peptide_length": 17,
      "source_cohort": "human_canonical_non_hla",
      "source_tool": "deeptmhmm-1.0.24"
    }

Residue indices are 1-based, end-inclusive — same convention 3Dmol uses
for ``viewer.setStyle({resi: "1-21"})``.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import TypedDict

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_TOPOLOGY_FILE = (
    ROOT
    / "data"
    / "external"
    / "deeptmhmm_surfaceome_predictions"
    / "human_canonical_non_hla"
    / "predicted_topologies.3line"
)
DEFAULT_OUTPUT_DIR = ROOT / "viewer" / "public" / "structure-viewer"
DEFAULT_SOURCE_COHORT = "human_canonical_non_hla"
DEFAULT_SOURCE_TOOL = "deeptmhmm-1.0.24"

# AFDB prediction API + on-disk cache. Bake-once semantics: if the
# cache file exists, we use it verbatim and never re-fetch — pass
# ``--refresh-afdb`` (or ``--refresh-afdb-acc {ACC}``) to force a
# re-fetch when AFDB has bumped a version.
AFDB_PREDICTION_URL = "https://alphafold.ebi.ac.uk/api/prediction/{acc}"
AFDB_CACHE_DIR = ROOT / "data" / "cache" / "afdb_prediction"


class TopologyRecord(TypedDict):
    uniprot_acc: str
    deeptmhmm_type: str
    sequence_length: int
    topology: str
    topology_ranges: dict[str, list[list[int]]]
    tm_helix_count: int
    signal_peptide_length: int
    source_cohort: str
    source_tool: str
    pdb_url: str | None
    bcif_url: str | None
    latest_version: int | None


_HEADER_RE = re.compile(r"^>(?:sp|tr)\|([A-Z0-9-]+)\|\S+\s*\|\s*(\S+)\s*$")


def parse_three_line(path: Path) -> list[tuple[str, str, str, str]]:
    """Yield (uniprot, deeptmhmm_type, sequence, topology) tuples.

    ``deeptmhmm_type`` is one of TM / SP+TM / SP / BETA / GLOB.
    """
    out: list[tuple[str, str, str, str]] = []
    with path.open() as f:
        lines = [ln.rstrip("\n") for ln in f]
    i = 0
    while i < len(lines):
        if not lines[i].startswith(">"):
            i += 1
            continue
        m = _HEADER_RE.match(lines[i])
        if not m:
            i += 1
            continue
        uniprot, dtype = m.group(1), m.group(2)
        if i + 2 >= len(lines):
            break
        sequence = lines[i + 1].strip()
        topology = lines[i + 2].strip()
        if len(sequence) != len(topology):
            i += 3
            continue
        out.append((uniprot, dtype, sequence, topology))
        i += 3
    return out


def topology_ranges(topology: str) -> dict[str, list[list[int]]]:
    """Collapse a per-residue topology string into [start, end] spans per state.

    1-based, end-inclusive (same convention 3Dmol uses for ``resi``).
    Empty list per state if the state never appears.
    """
    states = ("M", "O", "I", "S", "B")
    ranges: dict[str, list[list[int]]] = {s: [] for s in states}
    if not topology:
        return ranges
    cur_state = topology[0]
    cur_start = 1
    for idx, ch in enumerate(topology[1:], start=2):
        if ch != cur_state:
            if cur_state in ranges:
                ranges[cur_state].append([cur_start, idx - 1])
            cur_state = ch
            cur_start = idx
    if cur_state in ranges:
        ranges[cur_state].append([cur_start, len(topology)])
    return ranges


def fetch_afdb_prediction(
    uniprot: str,
    *,
    cache_dir: Path = AFDB_CACHE_DIR,
    refresh: bool = False,
    timeout_s: float = 10.0,
) -> tuple[str | None, str | None, int | None]:
    """Return ``(pdb_url, bcif_url, latest_version)`` for ``uniprot`` from AFDB.

    Bake-once cache: if ``{cache_dir}/{uniprot}.json`` exists and
    ``refresh`` is False, the cached response is used verbatim — no
    network call. On a cache miss (or ``refresh=True``), GET the AFDB
    prediction API, store the raw JSON to disk, and return the fields
    we care about.

    On any network / parse failure with no cached fallback, returns
    ``(None, None, None)`` and logs a warning to stderr. The runtime
    StructureViewer falls back to the legacy ``v4`` URL if the baked
    URLs are null.
    """
    cache_path = cache_dir / f"{uniprot}.json"
    if cache_path.exists() and not refresh:
        try:
            payload = json.loads(cache_path.read_text())
            return _extract_pdb_url(payload)
        except (OSError, json.JSONDecodeError):
            # Corrupt cache → fall through to a fresh fetch.
            pass

    url = AFDB_PREDICTION_URL.format(acc=uniprot)
    try:
        with urllib.request.urlopen(url, timeout=timeout_s) as resp:
            raw = resp.read().decode("utf-8")
        payload = json.loads(raw)
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
        print(
            f"[afdb] WARN: prediction fetch failed for {uniprot}: {exc}",
            file=sys.stderr,
        )
        return (None, None, None)

    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(payload, indent=2) + "\n")
    return _extract_pdb_url(payload)


def _extract_pdb_url(
    payload: object,
) -> tuple[str | None, str | None, int | None]:
    """AFDB returns an array; pull the first entry's pdbUrl/bcifUrl/latestVersion."""
    if not isinstance(payload, list) or not payload:
        return (None, None, None)
    first = payload[0]
    if not isinstance(first, dict):
        return (None, None, None)
    pdb_url = first.get("pdbUrl")
    bcif_url = first.get("bcifUrl")
    latest_version = first.get("latestVersion")
    if pdb_url is not None and not isinstance(pdb_url, str):
        pdb_url = None
    if bcif_url is not None and not isinstance(bcif_url, str):
        bcif_url = None
    if latest_version is not None and not isinstance(latest_version, int):
        latest_version = None
    return (pdb_url, bcif_url, latest_version)


def build_record(
    uniprot: str,
    deeptmhmm_type: str,
    sequence: str,
    topology: str,
    *,
    source_cohort: str,
    source_tool: str,
    pdb_url: str | None = None,
    bcif_url: str | None = None,
    latest_version: int | None = None,
) -> TopologyRecord:
    ranges = topology_ranges(topology)
    signal_peptide_length = sum(end - start + 1 for start, end in ranges["S"])
    return {
        "uniprot_acc": uniprot,
        "deeptmhmm_type": deeptmhmm_type,
        "sequence_length": len(sequence),
        "topology": topology,
        "topology_ranges": ranges,
        "tm_helix_count": len(ranges["M"]),
        "signal_peptide_length": signal_peptide_length,
        "source_cohort": source_cohort,
        "source_tool": source_tool,
        "pdb_url": pdb_url,
        "bcif_url": bcif_url,
        "latest_version": latest_version,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--topology-file", type=Path, default=DEFAULT_TOPOLOGY_FILE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--source-cohort", default=DEFAULT_SOURCE_COHORT)
    parser.add_argument("--source-tool", default=DEFAULT_SOURCE_TOOL)
    parser.add_argument(
        "--only-uniprot",
        nargs="*",
        default=None,
        help="If provided, only emit JSONs for these UniProt accessions.",
    )
    parser.add_argument(
        "--refresh-afdb",
        action="store_true",
        help=(
            "Force a fresh AFDB prediction-API fetch for every UniProt, "
            "ignoring the on-disk cache. Use after AFDB version bumps."
        ),
    )
    parser.add_argument(
        "--refresh-afdb-acc",
        nargs="*",
        default=None,
        help="Force re-fetch only for these UniProt accessions.",
    )
    parser.add_argument(
        "--skip-afdb",
        action="store_true",
        help=(
            "Skip the AFDB enrichment entirely (pdb_url + latest_version "
            "left null). Useful for offline dev; the viewer's legacy v4 "
            "URL fallback handles the missing field at runtime."
        ),
    )
    args = parser.parse_args()

    if not args.topology_file.exists():
        raise SystemExit(f"Topology file not found: {args.topology_file}")

    args.output_dir.mkdir(parents=True, exist_ok=True)

    only = set(args.only_uniprot) if args.only_uniprot else None
    refresh_set = (
        set(args.refresh_afdb_acc) if args.refresh_afdb_acc else None
    )
    entries = parse_three_line(args.topology_file)
    written = 0
    skipped_no_tm = 0
    enriched = 0
    enrichment_missing = 0
    for uniprot, dtype, sequence, topology in entries:
        if only is not None and uniprot not in only:
            continue
        # Soluble proteins (GLOB) carry no membrane topology — emitting a
        # record for them would mislead the viewer. Skip.
        if dtype == "GLOB":
            skipped_no_tm += 1
            continue

        pdb_url: str | None = None
        bcif_url: str | None = None
        latest_version: int | None = None
        if not args.skip_afdb:
            refresh = args.refresh_afdb or (
                refresh_set is not None and uniprot in refresh_set
            )
            pdb_url, bcif_url, latest_version = fetch_afdb_prediction(
                uniprot, refresh=refresh
            )
            if pdb_url is not None:
                enriched += 1
            else:
                enrichment_missing += 1

        record = build_record(
            uniprot,
            dtype,
            sequence,
            topology,
            source_cohort=args.source_cohort,
            source_tool=args.source_tool,
            pdb_url=pdb_url,
            bcif_url=bcif_url,
            latest_version=latest_version,
        )
        out_path = args.output_dir / f"{uniprot}.json"
        out_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
        written += 1

    summary = {
        "generated_from": str(args.topology_file.relative_to(ROOT)),
        "output_dir": str(args.output_dir.relative_to(ROOT)),
        "records_written": written,
        "skipped_globular": skipped_no_tm,
        "afdb_enriched": enriched,
        "afdb_missing": enrichment_missing,
        "source_cohort": args.source_cohort,
        "source_tool": args.source_tool,
    }
    summary_path = args.output_dir / "_index.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
