import type { MetadataRoute } from "next";

/**
 * /robots.txt — emitted as a static file at build time (the app uses
 * `output: "export"`).
 *
 * We explicitly **welcome all crawlers**: the catalogue is public,
 * read-only, CORS-open, and `public/llms.txt` already invites AI agents.
 * The only access guard is per-IP RATE limiting on the API Worker (a
 * cost/CPU cap that returns 429 under abusive bursts — NOT a bot ban),
 * so a well-behaved crawler is never blocked. The Sitemap pointer lets a
 * crawler discover all ~19k SSG'd gene pages without walking links.
 */
export const dynamic = "force-static";

const SITE = "https://surfaceome.deliverome.org";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [{ userAgent: "*", allow: "/" }],
    sitemap: `${SITE}/sitemap.xml`,
    host: SITE,
  };
}
