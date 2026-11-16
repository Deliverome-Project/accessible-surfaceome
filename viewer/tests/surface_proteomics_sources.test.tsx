/*
 *   npx --yes tsx --import ./tests/helpers/register.mjs --test tests/surface_proteomics_sources.test.tsx
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { ArmSources } from "../components/StudiesExplorer/StudiesExplorer";
import { tooltips } from "../lib/tooltips";
import type { StudyArm } from "../lib/surface-proteomics";

const LIST = { name: "Deliverome_surface_proteomics_studies_sweep-v12.xlsx", url: "https://drive.google.com/file/d/X/view" };
const arm = (o: Partial<StudyArm>) => ({ repository: null, repository_ids: [], ...o }) as unknown as StudyArm;

test("a dataset links its workbook tab and its raw-data deposit", () => {
  const html = renderToStaticMarkup(
    <ArmSources
      arm={arm({
        sheet_tab: "sucam-2026",
        raw_data: {
          flag: "raw_public",
          repository: "PRIDE",
          accessions: ["PXD068779"],
          url: "https://www.ebi.ac.uk/pride/archive/projects/PXD068779",
        },
      })}
      studyList={LIST}
    />,
  );
  assert.match(html, /href="https:\/\/drive.google.com\/file\/d\/X\/view"/);
  assert.match(html, /tab “sucam-2026”/);
  assert.match(html, /href="https:\/\/www.ebi.ac.uk\/pride\/archive\/projects\/PXD068779"/);
  assert.match(html, /raw files/);
});

test("no deposit reads as not deposited, without a link", () => {
  const html = renderToStaticMarkup(
    <ArmSources arm={arm({ sheet_tab: null, raw_data: { flag: "raw_not_deposited" } })} studyList={LIST} />,
  );
  assert.match(html, /raw data not deposited/);
  assert.doesNotMatch(html, /<a /);
});

test("surface overlap and reference are defined", () => {
  const ov = renderToStaticMarkup(<>{tooltips.surface_overlap}</>);
  assert.match(ov, /Canonical or Likely/);
  assert.match(ov, /20%/);
  assert.match(renderToStaticMarkup(<>{tooltips.reference}</>), /Canonical and Likely/);
});
