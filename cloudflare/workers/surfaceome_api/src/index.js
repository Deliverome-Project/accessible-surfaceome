// Cloudflare Worker — public read-only Surfaceome API (thin route dispatcher).
//
// Domain handlers live under ./routes/ and shared helpers under ./lib/.
// Schema: cloudflare/d1_public_schema.sql.

import { handleContactSites } from "./contact-sites.js";
import { CORS_HEADERS, databaseBusy, isD1Busy, json, notFound } from "./lib/http.js";
import { checkRate, withEdgeCache } from "./lib/cache.js";
import {
  bareVersionRedirect,
  handleGeneReplicate,
  handleGeneReplicates,
  handleRelease,
  handleReleaseGene,
  handleReleaseList,
  handleReplicateIndex,
  handleRevisionBody,
  handleRevisionList,
} from "./routes/history.js";
import {
  handleGene,
  handleGeneEvidence,
  handleGeneMarkdown,
  handleOrthologs,
  handleTagSites,
} from "./routes/gene.js";
import { handleCatalog, handleCatalogOne } from "./routes/catalog.js";
import {
  handleBenchmarkExport,
  handleBenchmarkList,
  handleBenchmarkMatrix,
  handleBenchmarkOne,
} from "./routes/benchmark.js";
import {
  handleInternalization,
  handleTriage,
  handleTriageCell,
  handleTriageExport,
} from "./routes/triage.js";
import {
  handleGeneList,
  handleHealth,
  handleMetaSizes,
  handleV1Index,
} from "./routes/meta.js";
import {
  handleFeedbackModerate,
  handleFeedbackModeratePost,
  handleFeedbackPublic,
  handleFeedbackSubmit,
} from "./routes/feedback.js";
import { handleL1Design, handleL1DesignIndex } from "./routes/l1_design.js";
import {
  handleL1ReviewExport,
  handleL1ReviewList,
  handleL1ReviewSubmit,
  handleL1ReviewWhoami,
} from "./routes/l1_review.js";
import {
  classifyUsagePage,
  cleanUsageLabel,
  handleUsageEvent,
  usageVisitorHash,
} from "./routes/usage.js";

export { classifyUsagePage, cleanUsageLabel, usageVisitorHash };

export default {
  async fetch(request, env, ctx) {
    try {
      return await routeRequest(request, env, ctx);
    } catch (e) {
      if (isD1Busy(e)) {
        console.warn("d1_busy", e?.message);
        return databaseBusy();
      }
      throw e;
    }
  },
};

async function routeRequest(request, env, ctx) {
    if (request.method === "OPTIONS") {
      return new Response(null, {
        status: 204,
        headers: {
          ...CORS_HEADERS,
          "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        },
      });
    }
    const url = new URL(request.url);
    // Strip the `/surfaceome` route prefix when present so the
    // same router handles both production
    // (`api.deliverome.org/surfaceome/v1/...`) and the workers.dev
    // fallback (`surfaceome-api.<sub>.workers.dev/v1/...`). Trailing
    // slashes are normalized so `/v1/health/` and `/v1/health` both
    // resolve.
    let path = url.pathname.replace(/\/+$/, "");
    if (path.startsWith("/surfaceome/")) {
      path = path.slice("/surfaceome".length);
    } else if (path === "/surfaceome") {
      path = "";
    }

    // Per-IP rate limiting on reads (GET), before any handler / D1 work so
    // an over-limit caller is rejected cheaply. POST (feedback submit) has
    // its own Turnstile + KV limiter downstream, so it's excluded here.
    if (request.method === "GET") {
      const limited = await checkRate(env, request, path);
      if (limited) return limited;
    }

    // POST is allowed ONLY on feedback submit/moderate, usage events, and L1 review.
    if (request.method === "POST") {
      if (path === "/v1/feedback/submit") {
        return handleFeedbackSubmit(request, env, url);
      }
      if (path === "/v1/feedback/moderate") {
        return handleFeedbackModeratePost(request, env, url);
      }
      if (path === "/v1/events") {
        const limited = await checkRate(env, request, path);
        if (limited) return limited;
        return handleUsageEvent(request, env);
      }
      if (path === "/v1/l1-review") return handleL1ReviewSubmit(request, env);
      return json({ error: "method_not_allowed" }, { status: 405, ttl: 0 });
    }
    if (request.method !== "GET") {
      return json({ error: "method_not_allowed" }, { status: 405, ttl: 0 });
    }

    if (path.startsWith("/v1/contact-sites/")) return handleContactSites(request, env, path);
    if (path === "/v1" || path === "") return handleV1Index(env);
    // Cacheable static / list endpoints — wrapped in withEdgeCache so the
    // second-and-subsequent hits per POP serve from caches.default rather
    // than re-running the D1 query. handleCatalog stays untouched because
    // it already has its own caches.default logic inline (with a bespoke
    // cache key on universe_version).
    if (path === "/v1/health") return withEdgeCache(request, env, ctx, () => handleHealth(env));
    if (path === "/v1/genes") return withEdgeCache(request, env, ctx, () => handleGeneList(env));
    if (path === "/v1/catalog") return handleCatalog(env, request);
    if (path === "/v1/benchmark") return withEdgeCache(request, env, ctx, () => handleBenchmarkList(env));
    if (path === "/v1/benchmark/matrix") return withEdgeCache(request, env, ctx, () => handleBenchmarkMatrix(env));
    if (path === "/v1/benchmark/export.tsv") return withEdgeCache(request, env, ctx, () => handleBenchmarkExport(env));
    // ?run_id=X actually parameterizes the response, so the query has to
    // be in the cache key here (unlike the other endpoints whose query
    // params are cache-busting noise the zone Cache Rule already strips).
    if (path === "/v1/triage/export.tsv") return withEdgeCache(request, env, ctx, () => handleTriageExport(env, url), { includeQuery: true });
    if (path === "/v1/meta/sizes") return withEdgeCache(request, env, ctx, () => handleMetaSizes(env));
    if (path === "/v1/releases") return withEdgeCache(request, env, ctx, () => handleReleaseList(env));
    if (path === "/v1/replicates") return withEdgeCache(request, env, ctx, () => handleReplicateIndex(env));
    // Feedback endpoints are user-specific / write-adjacent — never cache.
    if (path === "/v1/feedback/moderate") return handleFeedbackModerate(env, url);
    if (path === "/v1/feedback/public") return handleFeedbackPublic(env, url);

    let m;
    // Reproducibility replicates (API-only) — more specific than /v1/genes/{sym}.
    if ((m = path.match(/^\/v1\/genes\/([^/]+)\/replicates$/))) return withEdgeCache(request, env, ctx, () => handleGeneReplicates(env, m[1]));
    if ((m = path.match(/^\/v1\/genes\/([^/]+)\/replicates\/([^/]+)\/([^/]+)$/))) return withEdgeCache(request, env, ctx, () => handleGeneReplicate(env, m[1], m[2], m[3]));
    // Record history — more specific than every /v1/genes/{sym}… route below.
    if ((m = path.match(/^\/v1\/genes\/([^/]+)\/revisions$/))) return withEdgeCache(request, env, ctx, () => handleRevisionList(env, m[1]));
    if ((m = path.match(/^\/v1\/genes\/([^/]+)\/revisions\/([^/]+)\.md$/))) return handleRevisionBody(env, m[1], m[2], "md");
    if ((m = path.match(/^\/v1\/genes\/([^/]+)\/revisions\/([^/]+)\/evidence$/))) return handleRevisionBody(env, m[1], m[2], "evidence");
    if ((m = path.match(/^\/v1\/genes\/([^/]+)\/revisions\/([^/]+)$/))) return handleRevisionBody(env, m[1], m[2], "record");
    // Each /v1/releases/{version}... match checks bareVersionRedirect first
    // (301 to the bare form on a `v`-prefixed version) before dispatching —
    // see bareVersionRedirect's comment for why that has to happen BEFORE
    // withEdgeCache/handler, not inside the handler.
    if ((m = path.match(/^\/v1\/releases\/([^/]+)\/genes\/([^/]+)\.md$/))) {
      return bareVersionRedirect(m[1], `/genes/${m[2]}.md`) || handleReleaseGene(env, m[1], m[2], "md");
    }
    if ((m = path.match(/^\/v1\/releases\/([^/]+)\/genes\/([^/]+)\/evidence$/))) {
      return bareVersionRedirect(m[1], `/genes/${m[2]}/evidence`) || handleReleaseGene(env, m[1], m[2], "evidence");
    }
    if ((m = path.match(/^\/v1\/releases\/([^/]+)\/genes\/([^/]+)$/))) {
      return bareVersionRedirect(m[1], `/genes/${m[2]}`) || handleReleaseGene(env, m[1], m[2], "record");
    }
    if ((m = path.match(/^\/v1\/releases\/([^/]+)$/))) {
      return bareVersionRedirect(m[1]) || withEdgeCache(request, env, ctx, () => handleRelease(env, m[1]));
    }
    // `.md` must be tested before the bare record route: `([^/]+)` would
    // otherwise swallow the `.md` suffix and route to handleGene.
    if ((m = path.match(/^\/v1\/genes\/([^/]+)\.md$/))) return withEdgeCache(request, env, ctx, () => handleGeneMarkdown(env, m[1]));
    // Evidence ledger split out of the per-gene record. Must be tested
    // before the bare record route: `([^/]+)` there would otherwise never
    // match the trailing `/evidence` segment, but keeping it adjacent is
    // clearer about the pair.
    if ((m = path.match(/^\/v1\/genes\/([^/]+)\/evidence$/))) return withEdgeCache(request, env, ctx, () => handleGeneEvidence(env, m[1]));
    if ((m = path.match(/^\/v1\/genes\/([^/]+)$/))) return withEdgeCache(request, env, ctx, () => handleGene(env, m[1]));
    // Single-gene catalog row (DB-vote strip on the gene page). `/v1/catalog`
    // (exact) is matched above; this is the per-symbol variant.
    if ((m = path.match(/^\/v1\/catalog\/([^/]+)$/))) return withEdgeCache(request, env, ctx, () => handleCatalogOne(env, m[1]));
    if ((m = path.match(/^\/v1\/internalization\/([^/]+)$/))) return withEdgeCache(request, env, ctx, () => handleInternalization(env, m[1]));
    if ((m = path.match(/^\/v1\/tag-sites\/([^/]+)$/))) return withEdgeCache(request, env, ctx, () => handleTagSites(env, m[1]));
    if (path === "/v1/l1-review") return handleL1ReviewList(request, env);
    if (path === "/v1/l1-review/whoami") return handleL1ReviewWhoami(request, env);
    if (path === "/v1/l1-review/export.tsv") return handleL1ReviewExport(request, env);
    // Not behind withEdgeCache: its KV tier holds a read for up to an hour, and a new
    // L1 load must show within a minute (overnight reloads). Indexed, small queries.
    if (path === "/v1/l1-design") return handleL1DesignIndex(env);
    if ((m = path.match(/^\/v1\/l1-design\/([^/]+)$/))) return handleL1Design(env, m[1]);
    if ((m = path.match(/^\/v1\/l1-design\/([^/]+)\/([^/]+)$/))) return withEdgeCache(request, env, ctx, () => handleL1Design(env, m[1], m[2]));
    if ((m = path.match(/^\/v1\/orthologs\/([^/]+)$/))) return withEdgeCache(request, env, ctx, () => handleOrthologs(env, m[1]));
    if ((m = path.match(/^\/v1\/benchmark\/([^/]+)$/))) return withEdgeCache(request, env, ctx, () => handleBenchmarkOne(env, m[1]));
    // Per-cell replicate detail (more specific — match before the bare
    // /v1/triage/:symbol route). model = claude-<name>-<n>[-<n>]; variant
    // = naive|ncbi|web_ncbi|pubmed_ncbi|ncbi_effort_low.
    if ((m = path.match(/^\/v1\/triage\/([^/]+)\/([A-Za-z0-9._-]+)\/([a-z_]+)$/))) {
      return withEdgeCache(request, env, ctx, () => handleTriageCell(env, m[1], m[2], m[3]));
    }
    if ((m = path.match(/^\/v1\/triage\/([^/]+)$/))) return withEdgeCache(request, env, ctx, () => handleTriage(env, m[1]));

    return notFound("route_not_found");
}
