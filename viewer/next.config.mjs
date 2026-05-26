import { fileURLToPath } from "node:url";
import { dirname } from "node:path";
import { execSync } from "node:child_process";

const __dirname = dirname(fileURLToPath(import.meta.url));

// Resolve the git SHA at build time so the feedback modal can attach it
// to submissions (the maintainer sees which version of the site the
// submitter saw). Cloudflare Pages sets CF_PAGES_COMMIT_SHA; locally we
// fall back to `git rev-parse --short HEAD`. Sealed to 7 chars.
function resolveGitSha() {
  const fromCf = process.env.CF_PAGES_COMMIT_SHA;
  if (fromCf) return fromCf.slice(0, 7);
  if (process.env.GIT_SHA) return process.env.GIT_SHA.slice(0, 7);
  try {
    return execSync("git rev-parse --short HEAD", { stdio: ["ignore", "pipe", "ignore"] })
      .toString().trim();
  } catch {
    return "unknown";
  }
}

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: "export",
  trailingSlash: true,
  images: {
    unoptimized: true,
  },
  // Pin file-tracing root to this directory so Next stops warning
  // about the parent-repo lockfile. The viewer is its own Pages
  // project; nothing here needs to trace back into the Python tree.
  outputFileTracingRoot: __dirname,
  // Inject feedback-flow env vars at build time so the modal and
  // CommunityNotes card can read them via process.env.NEXT_PUBLIC_*.
  // process.env override allows shell / .env.local / Cloudflare Pages
  // to point at a different Turnstile site (e.g. test-mode key) or a
  // different feedback API base (e.g. a staging Worker) without
  // touching this file. The hardcoded defaults are the production
  // values; both are public — the Turnstile site key is embedded in
  // every page bundle that ships, and the API base is just a URL.
  // Hardcoding them as defaults means a fresh worktree's `npm run dev`
  // works without any `.env*` file at all.
  env: {
    NEXT_PUBLIC_TURNSTILE_SITE_KEY:
      process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY
      ?? "0x4AAAAAADWMXfjX7seRgQLJ",
    NEXT_PUBLIC_FEEDBACK_API_BASE:
      process.env.NEXT_PUBLIC_FEEDBACK_API_BASE
      ?? "https://api.deliverome.org/surfaceome",
    NEXT_PUBLIC_GIT_SHA: resolveGitSha(),
  },
};

export default nextConfig;
