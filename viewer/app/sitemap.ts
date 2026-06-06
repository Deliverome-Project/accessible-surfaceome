import type { MetadataRoute } from "next";
import { listSurfaceomeGenes } from "../lib/surfaceome";

/**
 * /sitemap.xml — emitted as a static file at build time (`output: "export"`).
 *
 * Lists the top-level pages plus every SSG'd gene page so crawlers can
 * discover the full ~19k-gene catalogue without walking links. Gene
 * symbols come from the same source as `generateStaticParams`
 * (`listSurfaceomeGenes`). Under `SURFACEOME_API_BASE=local` (the CI smoke
 * build) that list is empty, so the sitemap degrades gracefully to just the
 * static pages; the production deploy (real API base) emits the full set.
 */
export const dynamic = "force-static";

const SITE = "https://surfaceome.deliverome.org";

// Top-level app/ routes (trailingSlash: true → URLs end with "/").
// "" is the root catalogue page; the rest mirror app/<route>/page.tsx.
const STATIC_PATHS = ["", "benchmark", "api", "prompts", "compare", "reproducibility"];

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const staticEntries: MetadataRoute.Sitemap = STATIC_PATHS.map((p) => ({
    url: p ? `${SITE}/${p}/` : `${SITE}/`,
    changeFrequency: "weekly" as const,
    priority: p === "" ? 1.0 : 0.7,
  }));

  let genes: string[] = [];
  try {
    genes = await listSurfaceomeGenes();
  } catch {
    genes = [];
  }
  const geneEntries: MetadataRoute.Sitemap = genes.map((sym) => ({
    url: `${SITE}/${sym}/`,
    changeFrequency: "monthly" as const,
    priority: 0.5,
  }));

  return [...staticEntries, ...geneEntries];
}
