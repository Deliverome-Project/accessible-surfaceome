/*
 * lib/canonical-frame — one canonical residue number read across a
 * protein's isoforms and orthologs.
 *
 *   npx --yes tsx --test tests/canonical_frame.test.ts
 *
 * A residue number only means something against the sequence it was read
 * off. Typing MS4A1's recommended tag site, 161, on the Mouse tab asks
 * for mouse residue 161, which is a different residue; on the truncated
 * isoform the site does not exist at all. The alignment needed to say so
 * is already in the record as
 * ``per_residue_topology_canonical_frame`` — one character per canonical
 * residue, ``'-'`` where the proteoform does not reach.
 *
 * Fixture provenance: api.deliverome.org/surfaceome/v1/genes/MS4A1,
 * canonical sequence and the three proteoform frames verbatim.
 */
import assert from "node:assert/strict";
import { test } from "node:test";
import {
  projectAcrossProteoforms,
  projectCanonicalResidue,
} from "../lib/canonical-frame";

const CANON =
  "MTTPRNSVNGTFPAEPMKGPIAMQSGPKPLFRRMSSLVGPTQSFFMRESKTLGAVQIMNG" +
  "LFHIALGGLLMIPAGIYAPICVTVWYPLWGGIMYIISGSLLAATEKNSRKCLVKGKMIMN" +
  "SLSLFAAISGMILSIMDILNIKISHFLKMESLNFIRAHTPYINIYNCEPANPSEKNSPST" +
  "QYCYSIQSLFLGILSVMLIFAFFQELVIAGIVENEWKRTCSRPKSNIVLLSAEEKKEQTI" +
  "EIKEEVVGLTETSSQPKNEEDIEIIPIQEEEEEETETNFPEPPQDQESSPIENDSSP";

const ISO2_FRAME =
  "IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII-----------------------" +
  "------------------------------------------------------------" +
  "------------------------------------------------------------" +
  "------------------------IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII" +
  "IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII";

const ISO2_SEQ =
  "MTTPRNSVNGTFPAEPMKGPIAMQSGPKPLFRRMSSLELVIAGIVENEWKRTCSRPKSNI" +
  "VLLSAEEKKEQTIEIKEEVVGLTETSSQPKNEEDIEIIPIQEEEEEETETNFPEPPQDQE" +
  "SSPIENDSSP";

const MOUSE_FRAME =
  "I-------IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIMMMM" +
  "MMMMMMMMMMMMMMMMMMOOOOOOMMMMMMMMMMMMMMMMMMMMMIIIIIIIIIIIIIII" +
  "MMMMMMMMMMMMMMMMMMMMMOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO" +
  "OOOOOOOOMMMMMMMMMMMMMMMMMMMMMIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII" +
  "IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII";

const MOUSE_SEQ =
  "MSGPFPAEPTKGPLAMQPAPKVNLKRTSSLVGPTQSFFMRESKALGAVQIMNGLFHITLG" +
  "GLLMIPTGVFAPICLSVWYPLWGGIMYIISGSLLAAAAEKTSRKSLVKAKVIMSSLSLFA" +
  "AISGIILSIMDILNMTLSHFLKMRRLELIQTSKPYVDIYDCEPSNSSEKNSPSTQYCNSI" +
  "QSVFLGILSAMLISAFFQKLVTAGIVENEWKRMCTRSKSNVVLLSAGEKNEQTIKMKEEI" +
  "IELSGVSSQPKNEEEIEIIPVQEEEEEEAEINFPAPPQEQESLPVENEIAP";

const CYNO_FRAME =
  "IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIMMMM" +
  "MMMMMMMMMMMMMMMMMMOOOOOOMMMMMMMMMMMMMMMMMMMMMIIIIIIIIIIIIIII" +
  "MMMMMMMMMMMMMMMMMMMMMOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO" +
  "OOOOOOOOMMMMMMMMMMMMMMMMMMMMMIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII" +
  "IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII";

const CYNO_SEQ =
  "MTTPRNSVNGTFPAEPMKGPIAMQPGPKPLLRRMSSLVGPTQSFFMRESKALGAVQIMNG" +
  "LFHIALGGLLMIPAGIYAPICVTVWYPLWGGIMYIISGSLLAATEKNSRKCLVKGKMIMN" +
  "SLSLFAAISGMILSIMDILNIKISHFLKMESLNFIRVHTPYINIYNCEPANPSEKNSPST" +
  "QYCYSIQSLFLGILSVMLIFAFFQELVIAGIVENEWRRTCSRPKSSVVLLSAEEKKEQVI" +
  "EIKEEVVGLTETSSQPKNEEDIEIIPIQEEEEEETETNFPEPPQDQESSPIENDSSP";

const SITE = 161;

test("the canonical site is a tyrosine", () => {
  assert.equal(CANON[SITE - 1], "Y");
});

test("cyno conserves it, at the same number", () => {
  const r = projectCanonicalResidue(SITE, CYNO_FRAME, CYNO_SEQ, CANON);
  assert.deepEqual(r, { residue: 161, aa: "Y", conserved: true });
});

test("mouse has the position but not the residue", () => {
  // 73% identical full length, 66% across the ECD — and still a
  // substitution at the site. The number alone would have hidden it.
  const r = projectCanonicalResidue(SITE, MOUSE_FRAME, MOUSE_SEQ, CANON);
  assert.deepEqual(r, { residue: 154, aa: "P", conserved: false });
});

test("the truncated isoform does not carry the site at all", () => {
  const r = projectCanonicalResidue(SITE, ISO2_FRAME, ISO2_SEQ, CANON);
  assert.deepEqual(r, { residue: null, aa: null, conserved: null });
});

test("coverage is per position, not a global identity threshold", () => {
  // The isoform is 44% identical overall and still covers its own
  // N-terminal residues exactly; the ortholog is 73% identical and
  // misses nothing. Neither number predicts the site.
  const early = projectCanonicalResidue(10, ISO2_FRAME, ISO2_SEQ, CANON);
  assert.equal(early.residue, 10);
  assert.equal(early.aa, CANON[9]);
});

test("a missing frame, a short frame and a bad number all read uncovered", () => {
  for (const r of [
    projectCanonicalResidue(SITE, null, MOUSE_SEQ, CANON),
    projectCanonicalResidue(SITE, undefined),
    projectCanonicalResidue(9999, MOUSE_FRAME, MOUSE_SEQ, CANON),
    projectCanonicalResidue(0, MOUSE_FRAME, MOUSE_SEQ, CANON),
    projectCanonicalResidue(1.5, MOUSE_FRAME, MOUSE_SEQ, CANON),
  ]) {
    assert.deepEqual(r, { residue: null, aa: null, conserved: null });
  }
});

test("without sequences it still gives the number, and claims nothing more", () => {
  const r = projectCanonicalResidue(SITE, MOUSE_FRAME);
  assert.deepEqual(r, { residue: 154, aa: null, conserved: null });
});

test("one call reads the site across every proteoform", () => {
  const rows = projectAcrossProteoforms(
    SITE,
    [
      { label: "Isoform 2", frame: ISO2_FRAME, sequence: ISO2_SEQ, pctIdentity: 44 },
      { label: "Mouse", frame: MOUSE_FRAME, sequence: MOUSE_SEQ, pctIdentity: 73 },
      { label: "Cyno", frame: CYNO_FRAME, sequence: CYNO_SEQ, pctIdentity: 97 },
    ],
    CANON,
  );
  assert.deepEqual(
    rows.map((r) => [r.label, r.residue, r.aa, r.conserved]),
    [
      ["Isoform 2", null, null, null],
      ["Mouse", 154, "P", false],
      ["Cyno", 161, "Y", true],
    ],
  );
});
