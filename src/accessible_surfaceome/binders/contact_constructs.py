"""Conservative construct equivalence from deposited chemistry, never site overlap."""

import hashlib
import json
from pathlib import Path

from accessible_surfaceome.binders.contact_identity import digest


def construct_fingerprint(record):
    """Return a key only when sequence, chemistry, and reference spans are known.

    Unknown covalent attachments and ambiguous polymer alternatives prohibit
    automatic merging. Equality concerns deposited constructs, not native forms.
    """
    required = ("parent_accessions", "monomers", "mapped_spans")
    if not all(record.get(key) for key in required):
        return None
    if (
        record.get("unresolved_chemistry")
        or not record.get("chemistry_checked")
        or "internal_covalent_links" not in record
    ):
        return None
    return digest(
        {key: record.get(key, []) for key in (*required, "internal_covalent_links")}
    )


def equivalent_construct_groups(records):
    groups = {}
    for record in records:
        fingerprint = construct_fingerprint(record)
        if fingerprint:
            groups.setdefault(fingerprint, []).append(record)
    return [
        dict(fingerprint=key, records=values)
        for key, values in groups.items()
        if len(values) > 1
    ]


def load_accepted_constructs(accepted_path: Path, suggestions_path: Path) -> dict:
    """Verify manual acceptance against a pinned suggestion snapshot, once per build.

    The accepted file is an explicit allowlist, not an instruction to accept every
    matching fingerprint in the suggestions. Coordinate/mapping hashes pin the
    source inputs recorded in that snapshot; this loader does not download them.
    """
    accepted = json.loads(Path(accepted_path).read_text())
    suggestion_bytes = Path(suggestions_path).read_bytes()
    if (
        accepted.get("suggestions_sha256")
        != hashlib.sha256(suggestion_bytes).hexdigest()
    ):
        raise ValueError(
            "Accepted constructs suggestion SHA256 mismatch; re-review changed evidence"
        )
    if accepted.get("schema_version") != 1:
        raise ValueError("Unsupported accepted construct schema")
    suggestions = json.loads(suggestion_bytes)
    records = {}
    for record in suggestions["records"]:
        scope = (record["target"], record["partner"], record["pdb"])
        records.setdefault(scope, []).append(record)
    index = {}
    for group in accepted["groups"]:
        members = group["members"]
        if (
            len(members) < 2
            or not group.get("canonical_partner_label")
            or not group.get("identity_note")
        ):
            raise ValueError(
                "Accepted construct needs at least two members, a label and review note"
            )
        for member in members:
            scope = (member["target"], member["partner"], member["pdb"])
            matches = records.get(scope, [])
            if len(matches) != 1:
                raise ValueError(
                    f"Accepted construct scope missing or ambiguous: {scope}"
                )
            record = matches[0]
            fingerprint = construct_fingerprint(record)
            if (
                record.get("status") != "complete"
                or not fingerprint
                or fingerprint != group["construct_fingerprint"]
            ):
                raise ValueError(
                    f"Accepted construct fingerprint or chemistry changed: {scope}"
                )
            for field in ("coordinate_sha256", "mapping_sha256"):
                if not member.get(field) or member[field] != record.get(field):
                    raise ValueError(f"Accepted construct {field} mismatch: {scope}")
            if scope in index:
                raise ValueError(f"Duplicate accepted construct scope: {scope}")
            index[scope] = {
                "canonical_partner_label": group["canonical_partner_label"],
                "construct_fingerprint": fingerprint,
                "identity_note": group["identity_note"],
            }
    return index


def accepted_construct_updates(
    site: dict, target_acc: str, accepted_index: dict
) -> dict:
    """Return only reviewed identity fields for an exact raw partner/PDB/target.

    No normalized aliases, display-label matching, transitive equivalence or
    footprint matching is used. The input site and its target state are untouched.
    """
    scope = (target_acc, site.get("partner"), site.get("pdb"))
    return dict(accepted_index.get(scope, {}))
