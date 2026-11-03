"""Published tag sites withdrawn by measurement, suppressed on every surface.

A site reaches readers through two surfaces -- public D1's ``tag_site_public``
(what the Worker serves at ``/v1/tag-sites/:symbol``) and the static
``viewer/public/tag-sites/{SYMBOL}.json`` asset the viewer falls back to. A row
withdrawn from one and not the other is still being recommended, so the list here
is applied at both chokepoints: :func:`accessible_surfaceome.cloud.tag_sites.rows_for_file`
on the way into D1, and :func:`accessible_surfaceome.tag_sites.emit.emit_tag_sites_json`
on the way into the JSON.

**Why a list and not a gate.** The generator that proposed these sites does not
reject them, and the veto that would is not a property of a site: it is
``insert_aa >= span`` (:func:`accessible_surfaceome.tag_sites.features.insert_exceeds_closure`),
which depends on the cargo. Landing a second run-length definition while that one
is being settled is what this file avoids. It suppresses exactly the rows a
measurement names, so a published recommendation that three independent analyses
rejected stops being served now, and the gate work lands later without having to
agree with a guess made here.

**What is deliberately NOT retracted, and what this list does NOT assert.**
Enclosure by a disulfide is not on its own disqualifying: a pass over 176
published internal sites found 27 sitting strictly inside a span, 12 of them
functionally validated -- a HIGHER enclosure rate than among display-only sites
-- at spans from 9 to 655. Retracting on enclosure would have withdrawn working
reagents.

Nor does either entry here assert a general insert-length rule. A separate
measurement found that cargo-length matching cannot serve as a gate at all:
applied to the quantity that actually limits an insertion (the coil run rather
than the topological run) it removes almost the whole internal rung, and
published large-cargo insertions sit in host loops far shorter than their cargo,
with the measured cargo-size penalty against small tags only a few residues. So
these two rows are withdrawn on what was measured about *them* -- a specific
disulfide closure each, one annotated and one visible only in the model -- and a
reader should not generalize from them to a length cutoff.

Keys are ``(uniprot_acc, site_id)``. The accession, never the bare symbol: a
symbol silently resolves to the wrong protein for ~0.2% of human genes (the COX1
/ WAS class), and a retraction that misfires suppresses a good site.
"""
from __future__ import annotations

from typing import Any

# (uniprot_acc, site_id) -> why it was withdrawn. The reason is the record; it is
# what a reader who finds the site missing, or re-derives it, needs in order to
# know the omission was deliberate.
RETRACTED: dict[tuple[str, str], str] = {
    ("P11836", "MS4A1-surface_loop-171"): (
        "The insert is longer than the disulfide closure it has to fit inside. "
        "N171 sits four residues inside the annotated C167-C183 bond, which spans "
        "16 residues, while the cassette is 51 aa -- three times the residues the "
        "loop contains. The 10 A feature_dist veto passes it legitimately at "
        "~12.9 A from both cysteines, because hazard_residues reduces a bond to its "
        "two cysteine positions and so cannot express enclosure at all. The test "
        "that rejects it is insert_aa >= span (features.insert_exceeds_closure), "
        "which is cargo-dependent and therefore not yet wired into the gate."
    ),
    ("P25106", "ACKR3-surface_loop-35"): (
        "The site is inside a disulfide the gate could not see. P35 measures 3.81 A "
        "from C287's SG and 4.54 A from C34's SG; the C34-C287 bond is formed in "
        "AF-P25106-F1-model_v6 at 2.03 A but is NOT annotated in UniProt, which "
        "records only 117-196 for P25106. So the existing 10 A clearance veto "
        "reported 12.1 A and passed the site -- a missing input, not a missing "
        "concept. Reading bonds off the model (features.hazard_residues_with_model) "
        "drops feature_dist(35) to 3.8 A and empties the candidate list."
    ),
}


def is_retracted(*, uniprot_acc: str | None, site_id: str) -> bool:
    """Whether this protein's site has been withdrawn."""
    return (uniprot_acc or "", site_id) in RETRACTED


def retraction_reason(*, uniprot_acc: str | None, site_id: str) -> str | None:
    """Why the site was withdrawn, or ``None`` if it was not."""
    return RETRACTED.get((uniprot_acc or "", site_id))


def drop_retracted(
    sites: list[dict[str, Any]], *, uniprot_acc: str | None = None
) -> list[dict[str, Any]]:
    """``sites`` minus the withdrawn ones, logging each omission with its reason.

    A site's own ``uniprot_acc`` wins over the file-level one when it carries it,
    because one file can hold sites numbered against different library members.
    """
    import logging

    log = logging.getLogger(__name__)
    kept: list[dict[str, Any]] = []
    for site in sites:
        site_id = site.get("site_id")
        acc = site.get("uniprot_acc") or uniprot_acc
        reason = retraction_reason(uniprot_acc=acc, site_id=site_id) if site_id else None
        if reason is None:
            kept.append(site)
            continue
        log.warning("retracted %s (%s): %s", site_id, acc, reason)
    return kept
