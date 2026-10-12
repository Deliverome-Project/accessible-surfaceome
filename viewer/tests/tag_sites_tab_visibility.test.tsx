/*
 * The §Tag sites TAB must appear for a gene the agent SEARCHED, even when it
 * found nothing.
 *
 * This is the condition the "Literature-validated (0)" state exists to serve,
 * and it was unreachable: the tab was gated on `has_data && sites.some(...)`,
 * so it disappeared exactly when the card had the "we looked and found nothing"
 * message to show. 1,415 searched-and-empty genes (SLC9A8 among them) were
 * therefore indistinguishable from genes nobody had got to — the opposite of
 * what publishing their gene rows was for.
 *
 * `prompt_sha` is the claim that a search ran: the agent stamps it on every
 * result INCLUDING an empty one. So it, not the site count, decides whether
 * there is something to say.
 *
 * The tab predicate is duplicated here rather than imported because it lives
 * inline in GeneDetail's section list, which needs a full SurfaceomeRecord to
 * render. Duplication is the thing to watch: if the predicate in GeneDetail
 * changes, this test keeps passing while the UI regresses. It is pinned to the
 * exact field names so a rename breaks it loudly.
 *
 *   npx --yes tsx --import ./tests/helpers/register.mjs \
 *       --test tests/tag_sites_tab_visibility.test.tsx
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import type { TaggedSite, TaggedSitesFile } from "../lib/tag-sites-types";

/** Mirrors the `...(taggedSites && (...))` guard in GeneDetail.tsx. */
function tabShown(taggedSites: TaggedSitesFile | null): boolean {
  return Boolean(
    taggedSites &&
      (taggedSites.sites.some(
        (s) =>
          s.provenance === "literature_retrieved" ||
          s.provenance === "deterministic_computed" ||
          s.provenance === "screen_validated",
      ) ||
        Boolean(taggedSites.prompt_sha)),
  );
}

function file(over: Partial<TaggedSitesFile>): TaggedSitesFile {
  return {
    has_data: false,
    gene_symbol: "SLC9A8",
    uniprot_acc: "Q9Y2E8",
    sites: [],
    ...over,
  };
}

function site(provenance: TaggedSite["provenance"]): TaggedSite {
  return {
    site_id: "S1",
    gene_symbol: "SLC6A8",
    uniprot_acc: "P48029",
    provenance,
    det_path: "surface_loop",
    site_kind: "internal",
    insert_after_residue: 165,
    residue_before: "G",
    residue_after: "K",
    topology_state: "O",
    extracellular: true,
    compartment: "extracellular",
    tag_type: "ALFA",
    tag_length_aa: 15,
    linker: null,
    evidence_type: null,
    functional_impact_measured: null,
    confidence: "medium",
    rationale: null,
    sources: [],
    plddt: 80,
    conservation_rank: null,
    median_conservation: null,
  };
}

test("searched but EMPTY still shows the tab — the zero state must be reachable", () => {
  // SLC9A8: 74 papers triaged, no published tag site, no deterministic site.
  const empty = file({ prompt_sha: "db34c960a2f5", prompt_version: "1.4.0" });
  assert.equal(empty.sites.length, 0, "fixture must have no sites");
  assert.equal(empty.has_data, false, "fixture must have has_data false");
  assert.ok(
    tabShown(empty),
    "a gene the agent searched must get a Tag sites tab even with zero sites, " +
      "otherwise 'Literature-validated (0)' can never be seen",
  );
});

test("never searched and no sites shows NO tab", () => {
  // No prompt_sha means no search ran: there is genuinely nothing to say, and
  // offering an empty tab would imply a negative result we do not have.
  assert.equal(tabShown(file({})), false);
});

test("deterministic-only genes still show the tab", () => {
  // SLC6A8 has 7 deterministic sites and no published one.
  assert.ok(tabShown(file({ has_data: true, sites: [site("deterministic_computed")] })));
});

test("validated_literature alone does NOT show the tab", () => {
  // That provenance is validation-only and never rendered, so a tab carrying
  // only those sites would open an empty section. Without a prompt_sha there
  // is also no searched-but-empty claim to fall back on.
  assert.equal(
    tabShown(file({ has_data: true, sites: [site("validated_literature")] })),
    false,
  );
});

test("null taggedSites shows no tab", () => {
  assert.equal(tabShown(null), false);
});
