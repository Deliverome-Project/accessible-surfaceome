import { describe, it, expect } from "vitest";
import { tagSiteCategory, CATEGORY_LABEL, CATEGORY_HEX } from "../lib/tag-sites-types";

describe("screen_validated", () => {
  it("maps to its own category", () => {
    const cat = tagSiteCategory({ provenance: "screen_validated", det_path: null, site_kind: "terminal_n" });
    expect(cat).toBe("screen_validated");
    expect(CATEGORY_LABEL[cat]).toBe("Screen-validated");
    expect(CATEGORY_HEX[cat]).toMatch(/^#/);
  });
});
