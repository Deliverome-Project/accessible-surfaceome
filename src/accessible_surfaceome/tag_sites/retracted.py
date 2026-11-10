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

**The literature audit of 2026-11-05.** Every live ``literature_retrieved``
internal row (191) was checked by hand against its cited paper
(deliverome-analysis PR 236; the audit TSV is committed under
``data/analysis/tag_site_corpus_audit/``). Eighteen rows were withdrawn from
the served table because the paper does not support them: it is about a
different gene (ABCC2-163/574 cite the ABCC1 paper, TMEM225-125 is a PMP22
construct, KCNK5-214 is KCNK3, TMPRSS9-270 is polyserase-3, GABRP is excluded
by its own paper), the construct is numbered on another species with no human
equivalent (ADGRG6, GABRA2 x2, TRIL, ZP4), a terminal tag was filed as
internal (CDH13, CFC1, TEK, ZP2 x2), the paper shows the loop intracellular
(TLCD1-201) or the construct is an N-terminal fusion (CNR1-25). They are
listed here so no sweep output or snapshot can re-emit them; the corrected
rows that survive are served under ``tag_sites_version 2026-11-05-lit-audit``.

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
    # --- literature audit 2026-11-05 (deliverome-analysis PR 236) -----------
    ("Q92887", "ABCC2-internal-163-lit"): (
        "Literature audit 2026-11-05 (deliverome-analysis PR 236), verdict "
        "not_supported against PMID 9334225: Paper studies MRP (MRP1/ABCC1), not "
        "MRP2/ABCC2; the position-163 result belongs to ABCC1 (loop 158-172) and "
        "ABCC2 is never tagged."
    ),
    ("Q92887", "ABCC2-internal-574-lit"): (
        "Literature audit 2026-11-05 (deliverome-analysis PR 236), verdict "
        "not_supported against PMID 9334225: Paper studies MRP (MRP1/ABCC1), not "
        "ABCC2; position 574 refers to ABCC1."
    ),
    ("Q86SQ4", "ADGRG6-internal-550-lit"): (
        "Literature audit 2026-11-05 (deliverome-analysis PR 236), verdict "
        "wrong_species_numbering against PMID 42599991: The paper's constructs are "
        "zebrafish ADGRG6 (UniProt C6KFA3), and residue 551 there is Tyr (Y551), not "
        "the human Lys551 the row cites."
    ),
    ("P55290", "CDH13-internal-138-lit"): (
        "Literature audit 2026-11-05 (deliverome-analysis PR 236), verdict "
        "terminal_misfiled against PMID 42200830: This is an N-terminal tag on a "
        "construct deleted for aa 1-138 (signal peptide and prodomain), i.e. the tag "
        "is the new N-terminus of mature CDH13 (S139 onward), not an internal "
        "insertion; the vector must supply a signal peptide."
    ),
    ("P0CG37", "CFC1-internal-191-lit"): (
        "Literature audit 2026-11-05 (deliverome-analysis PR 236), verdict "
        "terminal_misfiled against PMID 18930707: V5-His is appended at the "
        "C-terminus of a truncated CR-1/CFC1 chimera ending at CFC1 L191 (the GPI "
        "signal), not an internal insertion; the tag is removed on GPI processing and "
        "the paper states only perinuclear trans-Golgi but not plasma membrane "
        "detection was observed using the anti-V5 antibody."
    ),
    ("P21554", "CNR1-internal-25-lit"): (
        "Literature audit 2026-11-05 (deliverome-analysis PR 236), verdict "
        "not_supported against PMID 33097803: The paper's construct is GLuc-(GLEG or "
        "FLAG linker)-full-length CB1: an N-terminal fusion that uses GLuc's own "
        "signal peptide, not an insertion at S25|N26."
    ),
    ("P47869", "GABRA2-internal-212-lit"): (
        "Literature audit 2026-11-05 (deliverome-analysis PR 236), verdict "
        "wrong_species_numbering against PMID 34899260: Secondary source Addgene "
        "#49169 (alpha2-pHluorin) full and partial sequences "
        "(https://www.addgene.org/49169/sequences/ and /browse/sequence/72495/) "
        "require an Addgene login ('Please log in to download or copy sequence "
        "data'); the GenBank file URL on sequences.addgene.org returns 404 without a "
        "ses..."
    ),
    ("P47869", "GABRA2-internal-232-lit"): (
        "Literature audit 2026-11-05 (deliverome-analysis PR 236), verdict "
        "wrong_species_numbering against PMID 34899260: Same secondary source as "
        "GABRA2-internal-212-lit: Addgene #49169 sequences are login-walled (not "
        "accessible), so the construct ORF could not be translated to find the frame "
        "giving Ser at 181 and 201; canonical S233 remains the row's inferred +32 "
        "offset."
    ),
    ("O00591", "GABRP-internal-27-lit"): (
        "Literature audit 2026-11-05 (deliverome-analysis PR 236), verdict "
        "not_supported against PMID 27622563: The paper explicitly excludes GABRP and "
        "lists cDNAs only for alpha1, alpha4-6, beta1-3, gamma1-3; no pi-subunit "
        "construct was made or tagged."
    ),
    ("O95279", "KCNK5-internal-214-lit"): (
        "Literature audit 2026-11-05 (deliverome-analysis PR 236), verdict "
        "not_supported against PMID 26794006: Wrong gene: the HA construct is human "
        "TASK-1 (KCNK3) Δi20 (the paper's HeLa and oocyte work is all TASK-1-Δi20, "
        "TASK-3 and TWIK-1);"
    ),
    ("Q02763", "TEK-internal-442-lit"): (
        "Literature audit 2026-11-05 (deliverome-analysis PR 236), verdict "
        "terminal_misfiled against PMID 34153320: FLAG is C-terminal to a truncated "
        "Tie2 ectodomain (1-442) fused to the PDGFRbeta TM domain for DT40 display; "
        "residues 443-1124 of TEK are absent, so this is not an insertion into full- "
        "length TEK."
    ),
    ("Q96CP7", "TLCD1-internal-201-lit"): (
        "Literature audit 2026-11-05 (deliverome-analysis PR 236), verdict "
        "not_supported against PMID 23673622: myc6 is the sixth construct = tag after "
        "chicken residue 201 (order 3,42,74,107,163,201,252); it gave NO staining "
        "without detergent, i.e. the paper places this loop INSIDE the cell (loop 5 "
        "of an N-out/C-out 6-TM topology)."
    ),
    ("Q6GV28", "TMEM225-internal-125-lit"): (
        "Literature audit 2026-11-05 (deliverome-analysis PR 236), verdict "
        "not_supported against PMID 42320627: Paper tags PMP22 (Q01453;"
    ),
    ("Q7Z410", "TMPRSS9-internal-270-lit"): (
        "Literature audit 2026-11-05 (deliverome-analysis PR 236), verdict "
        "not_supported against PMID 16566820: The FLAG-tagged construct is "
        "polyserase-3 (a secreted two-domain protease, a different gene), not "
        "TMPRSS9/polyserase-1; the paper states polyserase-3 lacks a TM motif and "
        "showed no cell-surface immunostaining."
    ),
    ("Q7L0X0", "TRIL-internal-499-lit"): (
        "Literature audit 2026-11-05 (deliverome-analysis PR 236), verdict "
        "wrong_species_numbering against PMID 29298840: Position is in Xenopus tril.S "
        "(854-867 aa UniProt entries) and the row copied 499 onto human TRIL (811 "
        "aa)."
    ),
    ("Q05996", "ZP2-internal-641-lit"): (
        "Literature audit 2026-11-05 (deliverome-analysis PR 236), verdict "
        "terminal_misfiled against PMID 31784633: Constructs are secreted porcine ZP2 "
        "(UniProt P42099) ectodomain variants expressed in CHO cells and conjugated "
        "to beads;"
    ),
    ("Q05996", "ZP2-internal-643-lit"): (
        "Literature audit 2026-11-05 (deliverome-analysis PR 236), verdict "
        "terminal_misfiled against PMID 31784633: Porcine ZP2C (P42099 numbering, "
        "construct coordinates with an N-terminal FLAG at 38-45) is a secreted "
        "ectodomain ending at 643 with 6xHis as its C-terminal tag; the paper itself "
        "calls it 'the C-terminus of ZP2C'."
    ),
    ("Q12836", "ZP4-internal-468-lit"): (
        "Literature audit 2026-11-05 (deliverome-analysis PR 236), verdict "
        "wrong_species_numbering against PMID 31784633: Porcine ZP4 (UniProt Q07287), "
        "secreted from CHO cells, detected by anti-V5 immunoblot; the same construct "
        "carries a 6xHis at construct positions 22-27, so 469-482 are construct "
        "coordinates shifted by 6 and fall right after the furin site RRRR(463-466)."
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
