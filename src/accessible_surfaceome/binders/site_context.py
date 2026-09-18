"""Conservative mature-protein context and exact IntAct feature mapping."""

import re


EXTRACELLULAR_CONTEXTS = {"extracellular_explicit", "extracellular_gpi_mature"}
EXOPLASMIC_CONTEXTS = EXTRACELLULAR_CONTEXTS | {"secreted_mature"}


def bounds(feature):
    location = feature.get("location", {})
    start, end = location.get("start", {}), location.get("end", {})
    if (
        start.get("modifier", "EXACT") != "EXACT"
        or end.get("modifier", "EXACT") != "EXACT"
    ):
        return None
    a, b = start.get("value"), end.get("value")
    return (a, b) if isinstance(a, int) and isinstance(b, int) and 0 < a <= b else None


def site_context(positions, protein):
    """Classify site positions, never promoting precursor or intracellular sites."""
    sequence = protein.get("sequence", {}).get("value", "")
    if not positions or min(positions) < 1 or max(positions) > len(sequence):
        return "invalid_mapping"
    features = [(f, bounds(f)) for f in protein.get("features", [])]
    features = [(f, b) for f, b in features if b]
    if any(
        f["type"] in {"Signal", "Propeptide", "Transit peptide"}
        and any(b[0] <= p <= b[1] for p in positions)
        for f, b in features
    ):
        return "removed_processing_segment"
    labels = set()
    for pos in positions:
        local = set()
        for feature, (start, end) in features:
            if start <= pos <= end:
                if feature["type"] == "Transmembrane":
                    local.add("transmembrane")
                elif feature["type"] == "Topological domain":
                    local.add(feature.get("description", "unknown").lower())
        labels.update(local or {"unknown"})
    if labels == {"extracellular"}:
        return "extracellular_explicit"
    if "transmembrane" in labels:
        return "membrane_spanning_site"
    if any(
        x in labels
        for x in [
            "cytoplasmic",
            "perinuclear space",
            "mitochondrial matrix",
            "mitochondrial intermembrane",
            "lumenal",
        ]
    ):
        return "non_extracellular:" + ";".join(sorted(labels))
    locations = [
        location
        for c in protein.get("comments", [])
        if c.get("commentType") == "SUBCELLULAR LOCATION" and not c.get("molecule")
        for location in c.get("subcellularLocations", [])
    ]
    chains = [
        b
        for f, b in features
        if f["type"] == "Chain" and b[0] <= min(positions) and max(positions) <= b[1]
    ]
    gpi = [
        b[0]
        for f, b in features
        if f["type"] == "Lipidation" and "GPI-anchor" in f.get("description", "")
    ]
    at_cell_gpi = any(
        "GPI-anchor" in location.get("topology", {}).get("value", "")
        and "Cell membrane" in location.get("location", {}).get("value", "")
        for location in locations
    )
    if (
        at_cell_gpi
        and chains
        and any(
            max(positions) <= anchor and any(b[1] == anchor for b in chains)
            for anchor in gpi
        )
    ):
        return "extracellular_gpi_mature"
    secreted = any(
        location.get("location", {}).get("value", "").startswith("Secreted")
        for location in locations
    )
    signal = any(f["type"] == "Signal" for f, b in features)
    membrane = any(f["type"] == "Transmembrane" for f, b in features)
    intracellular_locations = any(
        any(
            word in location.get("location", {}).get("value", "")
            for word in ["Cytoplasm", "Nucleus", "Mitochondrion"]
        )
        for location in locations
    )
    if secreted and signal and chains and not membrane and not intracellular_locations:
        return "secreted_mature"
    return "unknown:" + ";".join(sorted(labels))


def exact_ranges(text):
    """Accept exact ranges only, including redundant x..x PSI-MI notation."""
    text = re.sub(r"(\d+)\.\.\1(?=[,-]|$)", r"\1", text)
    parts = text.split(",")
    if not all(re.fullmatch(r"\d+-\d+", p) for p in parts):
        return []
    intervals = [tuple(map(int, p.split("-"))) for p in parts]
    if any(a < 1 or b < a for a, b in intervals):
        return []
    return intervals


def validate_feature(range_text, original_sequence, canonical):
    ranges = exact_ranges(range_text)
    if not ranges:
        return [], "uncertain_range"
    if max(b for a, b in ranges) > len(canonical):
        return [], "out_of_bounds"
    expected = "".join(canonical[a - 1 : b] for a, b in ranges)
    observed = re.sub(r"\s+", "", original_sequence).strip('"').upper()
    if observed in {"", "-"}:
        return [], "missing_original_sequence"
    if observed != expected:
        return [], "sequence_mismatch"
    return sorted({p for a, b in ranges for p in range(a, b + 1)}), "exact_sequence"


def feature_records(path):
    """Read official feature TSVs, whose free-text cells may contain bare newlines."""
    current = []
    with path.open() as handle:
        header = next(handle).rstrip("\n").split("\t")
        for line in handle:
            if re.match(r"^EBI-\d+\t", line):
                if current:
                    yield header, "".join(current).rstrip("\n").split("\t")
                current = [line]
            elif current:
                current.append(line)
        if current:
            yield header, "".join(current).rstrip("\n").split("\t")
