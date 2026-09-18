"""Conservative evidence identity: display names never establish global identity."""

import hashlib
import json
import re
from collections import defaultdict


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def contact_identity(site, target):
    """Use chemical IDs, reviewed target aliases, or scoped source observations.

    Reviewed aliases remain target-specific because a reused clone name does not
    prove the same molecule across targets. Sequence/chemistry identity requires
    an explicit validated construct fingerprint, never footprint similarity.
    """
    partner = site["partner"]
    if re.fullmatch(r"CCD:[A-Za-z0-9]+", partner):
        return "ccd:" + partner[4:].upper(), "chemical_component"
    if site.get("construct_fingerprint"):
        return "construct:" + site["construct_fingerprint"], "verified_construct"
    if site.get("canonical_partner_label"):
        return (
            "reviewed-target-alias:"
            + digest([target, site["canonical_partner_label"].casefold()]),
            "reviewed_target_alias",
        )
    if site.get("catalogue_identity_key"):
        return "catalogue:" + site["catalogue_identity_key"], "catalogue_identity"
    if site.get("reviewed_identity_label"):
        return "reviewed-target-alias:" + digest(
            [target, site["reviewed_identity_label"]]
        ), "reviewed_target_alias"
    if re.fullmatch(
        r"(?:[OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9][A-Z][A-Z0-9]{2}[0-9](?:[A-Z][A-Z0-9]{2}[0-9])?)(?:-\d+)?",
        partner,
    ):
        # Parent-protein identity is useful but does not certify full construct,
        # glycoform or peptide equivalence. Curated constructs take precedence.
        return "uniprot-parent:" + partner, "protein_parent_group"
    if re.fullmatch(r"GTOPDB:\d+", partner):
        return "iuphar-ligand:" + partner.split(":")[1], "catalogue_identity"
    if site["source"] == "IEDB" and re.fullmatch(r"\d+(?:;\d+)*", partner):
        return "iedb-receptor-group:" + partner, "source_receptor_group"
    if site["source"] == "AACDB" and not re.fullmatch(
        r"(?:Fab|Fv|VHH|antibody|nanobody|peptide)(?:\s+fragment)?", partner, re.I
    ):
        return "aacdb-target-clone:" + digest(
            [target, partner.casefold()]
        ), "source_target_clone_group"
    # Names without stable identifiers remain scoped until entities are resolved.
    scope = [target, site["source"], site.get("pdb", ""), partner]
    if site.get("partner_entity_id"):
        scope.append(site["partner_entity_id"])
    else:
        scope += [site.get("reference", ""), site["positions"]]
    return "source-observation:" + digest(scope), "unresolved_scoped_observation"


def display_name(site):
    if site.get("canonical_partner_label"):
        return site["canonical_partner_label"].strip()
    label = site.get("partner_label") or site["partner"]
    if re.match(r"cetuximab(?:\s|$)", label, re.I):
        return "Cetuximab"
    name = re.sub(r"\s*\([^)]*\)\s*$", "", label)
    name = re.sub(r"\s+(Fab|Fv|VHH)$", "", name, flags=re.I).strip()
    return "necitumumab" if re.fullmatch(r"(?:IMC-)?11F8", name, re.I) else name


def annotate_identities(genes):
    """Keep source labels intact; disambiguate only ambiguous display labels."""
    for acc, gene in genes.items():
        by_name = defaultdict(list)
        reviewed = {
            display_name(site).casefold(): contact_identity(site, acc)
            for site in gene["sites"]
            if site.get("canonical_partner_label")
        }
        for site in gene["sites"]:
            key, basis = contact_identity(site, acc)
            if site.get("catalogue_identity_key") and not site.get(
                "canonical_partner_label"
            ):
                key, basis = reviewed.get(display_name(site).casefold(), (key, basis))
            site["ligand_identity_key"] = key
            site["identity_basis"] = basis
            name = display_name(site)
            by_name[name.casefold()].append(site)
        for sites in by_name.values():
            identities = sorted({site["ligand_identity_key"] for site in sites})
            if len(identities) < 2:
                continue
            for site in sites:
                name = display_name(site)
                # A source-scoped display suffix distinguishes uncertain entries;
                # the raw source label and any reviewed canonical name are intact.
                scope = site.get("pdb", "").upper() or site["source"]
                index = identities.index(site["ligand_identity_key"]) + 1
                site["identity_display_label"] = f"{name} · {scope} · {index}"
