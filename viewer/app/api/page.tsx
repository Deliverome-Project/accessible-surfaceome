import path from "node:path";
import { readFileSync, statSync } from "node:fs";
import type { Metadata } from "next";
import { Shell } from "../../components/Shell/Shell";
import styles from "./page.module.css";

export const metadata: Metadata = {
  title: "API — Surfaceome",
  description:
    "Public read-only HTTP API at api.deliverome.org/surfaceome/v1/* " +
    "plus a downloadable agent skill that documents the endpoints.",
};

interface Endpoint {
  method: "GET";
  path: string;
  summary: string;
  curl?: string;
  /** Optional URL-fragment anchor so other pages can deep-link
   *  (e.g. /api/#triage from the CatalogTable's "Full reasoning"
   *  hint). Defaults to a slug derived from the path. */
  anchor?: string;
  /** Key into the Worker's /v1/meta/sizes response, used to render an
   *  approximate-size badge. Distinct from `path` because some
   *  endpoints share a path but differ by query string (the triage
   *  exports). Omit to show no size badge. */
  sizeKey?: string;
}

interface SizeEntry {
  bytes: number;
  approx?: boolean;
  note?: string;
}

const DEFAULT_API_BASE = "https://api.deliverome.org/surfaceome";

/**
 * Fetches approximate per-endpoint response sizes from the Worker's
 * /v1/meta/sizes (which derives them from live D1 row counts + LENGTH
 * sums) AT BUILD TIME. The page is statically exported, so these bake
 * into the HTML and refresh on each deploy — no client runtime needed.
 * Mirrors the loader's base-resolution convention: `local`/empty
 * SURFACEOME_API_BASE (offline CI smoke) skips the fetch and the badges
 * are simply omitted. Any network/parse failure degrades the same way.
 */
async function loadEndpointSizes(): Promise<Record<string, SizeEntry>> {
  const base = (process.env.SURFACEOME_API_BASE ?? DEFAULT_API_BASE).trim();
  if (!base || base.toLowerCase() === "local") return {};
  try {
    const res = await fetch(`${base}/v1/meta/sizes`, { cache: "force-cache" });
    if (!res.ok) return {};
    const data = (await res.json()) as { endpoints?: Record<string, SizeEntry> };
    return data.endpoints ?? {};
  } catch {
    return {};
  }
}

function formatBytes(n: number): string {
  if (!Number.isFinite(n) || n <= 0) return "";
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) {
    const kb = n / 1024;
    return `${kb < 10 ? kb.toFixed(1) : Math.round(kb)} KB`;
  }
  const mb = n / (1024 * 1024);
  return `${mb < 10 ? mb.toFixed(1) : Math.round(mb)} MB`;
}

interface EndpointGroup {
  label: string;
  blurb: string;
  endpoints: Endpoint[];
}

const ENDPOINT_GROUPS: EndpointGroup[] = [
  {
    label: "SurfaceBench",
    blurb:
      "147 curated proteins with ground-truth surface verdicts — the eval set behind the cost / accuracy figures.",
    endpoints: [
      {
        method: "GET",
        path: "/v1/benchmark",
        sizeKey: "/v1/benchmark",
        summary:
          "147 ground-truth labels (gene, UniProt, class, verdict, signal, reason, rationale) for the current bench_version.",
        curl:
          "curl -s https://api.deliverome.org/surfaceome/v1/benchmark | jq '.count, .bench_version'",
      },
      {
        method: "GET",
        path: "/v1/benchmark/export.tsv",
        sizeKey: "/v1/benchmark/export.tsv",
        summary:
          "Long-format TSV of the bench-restricted multi-model sweep: one row per (bench gene × model × variant) for the canonical bench_version. Adds the 5-DB vote vector and truth_verdict / truth_signal / truth_reason to the triage export shape.",
        curl:
          "curl -s https://api.deliverome.org/surfaceome/v1/benchmark/export.tsv | head -3",
      },
      {
        method: "GET",
        path: "/v1/benchmark/{SYMBOL}",
        sizeKey: "/v1/benchmark/{SYMBOL}",
        summary:
          "Single gene's ground-truth label and rationale for the latest bench_version.",
        curl:
          "curl -s https://api.deliverome.org/surfaceome/v1/benchmark/ERBB2 | jq '.truth_verdict, .truth_reason'",
      },
      {
        method: "GET",
        path: "/v1/benchmark/matrix",
        anchor: "benchmark-matrix",
        sizeKey: "/v1/benchmark/matrix",
        summary:
          "Full SurfaceBench matrix in one round-trip: per-gene truth label, 5-DB vote vector, and per-(model, variant) verdicts with the agent's free-text reasoning on each cell. Drives the SurfaceBench page's side-drawer.",
        curl:
          "curl -s https://api.deliverome.org/surfaceome/v1/benchmark/matrix | jq '.n_genes, .models, .headline_variant, .alt_variants'",
      },
    ],
  },
  {
    label: "Genome-wide",
    blurb:
      "All ~19,300 protein-coding human genes with their 5-DB surface-vote vector and the latest Sonnet/NCBI triage verdict.",
    endpoints: [
      {
        method: "GET",
        path: "/v1/catalog",
        sizeKey: "/v1/catalog",
        summary:
          "Per-gene-per-source surface-vote matrix (5 gating DBs: UniProt / GO / SURFY / CSPA / HPA) plus the latest triage verdict, short reason code, and deep-dive flag. One row per protein-coding gene (~19k). Free-text reasoning per run is on GET /v1/triage/{SYMBOL}; the full deep-dive SurfaceomeRecord is on GET /v1/genes/{SYMBOL}.",
        curl:
          "curl -s https://api.deliverome.org/surfaceome/v1/catalog | jq '.universe_version, .n_rows, .n_with_triage'",
      },
      {
        method: "GET",
        path: "/v1/triage/{SYMBOL}",
        anchor: "triage",
        sizeKey: "/v1/triage/{SYMBOL}",
        summary:
          "Every triage run on file for one gene — model × prompt-variant × replicate — with verdict, reason code, confidence, latency, per-call token counts, and the agent's free-text verdict_reasoning paragraph.",
        curl:
          "curl -s https://api.deliverome.org/surfaceome/v1/triage/ERBB2 | jq '.count, .runs[0]'",
      },
      {
        method: "GET",
        path: "/v1/triage/export.tsv",
        sizeKey: "/v1/triage/export.tsv",
        summary:
          "Long-format TSV of every triage run for one run_id. Each row is (gene × model × variant × replicate) with the 5-DB votes and uniprot_acc joined in server-side. Default run_id is mainbench_canonical_v2 (the bench sweep); pass run_id=genome_full_sonnet_ncbi_v1 for the full ~19k-gene Sonnet sweep. Reasoning columns are omitted by default to keep figure-input exports prose-free — add with_reasoning=1 for the full export below.",
        curl:
          "curl -s 'https://api.deliverome.org/surfaceome/v1/triage/export.tsv?run_id=genome_full_sonnet_ncbi_v1&replicate=1' | head -3",
      },
      {
        method: "GET",
        path: "/v1/triage/export.tsv?run_id=genome_full_sonnet_ncbi_v1&with_reasoning=1",
        anchor: "triage-full-export",
        sizeKey:
          "/v1/triage/export.tsv?run_id=genome_full_sonnet_ncbi_v1&with_reasoning=1",
        summary:
          "Full genome-wide triage export WITH agent reasoning: the ~19k-gene Sonnet/NCBI sweep with predicted_key_uncertainty and the agent's free-text verdict_reasoning paragraph appended as the trailing columns. with_reasoning=1 works on any run_id; this is the bulk counterpart to the per-gene /v1/triage/{SYMBOL} reasoning.",
        curl:
          "curl -s 'https://api.deliverome.org/surfaceome/v1/triage/export.tsv?run_id=genome_full_sonnet_ncbi_v1&replicate=1&with_reasoning=1' | head -3",
      },
    ],
  },
  {
    label: "Deep dive",
    blurb:
      "Per-gene deep-dive SurfaceomeRecords, plus the broad genome-wide ortholog lookup and a liveness check.",
    endpoints: [
      {
        method: "GET",
        path: "/v1/health",
        sizeKey: "/v1/health",
        summary:
          "Liveness check. Returns the count of deep-dive SurfaceomeRecords on file.",
        curl: "curl -s https://api.deliverome.org/surfaceome/v1/health",
      },
      {
        method: "GET",
        path: "/v1/genes",
        sizeKey: "/v1/genes",
        summary:
          "Index of genes with a deep-dive SurfaceomeRecord on file. Summary fields only: gene_symbol, uniprot_acc, schema_version, triage_signal, surface_status, annotated_at.",
        curl: "curl -s https://api.deliverome.org/surfaceome/v1/genes | jq '.count'",
      },
      {
        method: "GET",
        path: "/v1/genes/{SYMBOL}",
        sizeKey: "/v1/genes/{SYMBOL}",
        summary:
          "Full SurfaceomeRecord JSON for one gene. Contains the executive summary, evidence-grade rationale, per-method observations, deterministic features, accessibility risks, and the full evidence ledger with citations.",
        curl:
          "curl -s https://api.deliverome.org/surfaceome/v1/genes/ERBB2 | jq '.executive_summary.surface_accessibility, .confidence'",
      },
      {
        method: "GET",
        path: "/v1/orthologs/{SYMBOL}",
        sizeKey: "/v1/orthologs/{SYMBOL}",
        summary:
          "Mouse and cynomolgus orthologs for any human gene from the latest Ensembl Compara release (broad genome-wide raw Compara — full-length % identity + orthology type, ~5k genes). The per-gene record's deterministic_features.orthologs is the deeper view: mouse/cyno canonical, ECD % identity + projected topology + sequence, for deep-dived genes only.",
        curl:
          "curl -s https://api.deliverome.org/surfaceome/v1/orthologs/ERBB2 | jq '.release_version, (.orthologs | length)'",
      },
    ],
  },
  {
    label: "Discovery & utility",
    blurb:
      "Self-describing entry points for agents and tooling. Start at /v1 to walk the whole surface without scraping this page; the site root also serves an llms.txt that points here.",
    endpoints: [
      {
        method: "GET",
        path: "/v1",
        summary:
          "Self-describing index: the full endpoint catalogue with path templates, links to these docs / the downloadable skill / llms.txt / the SurfaceomeRecord schema, and the live dataset versions (bench_version, universe_version, n_annotations). Also served at the bare service root. Hit this first to discover the API.",
        curl:
          "curl -s https://api.deliverome.org/surfaceome/v1 | jq '.endpoints[].path, .versions'",
      },
      {
        method: "GET",
        path: "/v1/meta/sizes",
        summary:
          "Approximate response size for every endpoint, computed live from D1 row counts + LENGTH(...) sums — budget a fetch before making it. Drives the ~size badges on this page.",
        curl:
          "curl -s https://api.deliverome.org/surfaceome/v1/meta/sizes | jq '.endpoints'",
      },
    ],
  },
];

/**
 * Loads the skill markdown that ships under viewer/public/ so the
 * page can show its frontmatter (name + description) alongside the
 * download button. Reading at build time keeps the page server-only
 * and gives us file size + line count for the meta strip.
 */
function loadSkillMeta(): { name: string; description: string; size_bytes: number; line_count: number } | null {
  const abs = path.join(process.cwd(), "public", "surfaceome-api.skill.md");
  try {
    const body = readFileSync(abs, "utf-8");
    const stat = statSync(abs);
    const frontmatter = body.match(/^---\n([\s\S]*?)\n---/);
    let name = "surfaceome-api";
    let description = "";
    if (frontmatter) {
      const nameMatch = frontmatter[1].match(/^name:\s*(.+)$/m);
      const descMatch = frontmatter[1].match(/^description:\s*(.+(?:\n  .+)*)/m);
      if (nameMatch) name = nameMatch[1].trim();
      if (descMatch) description = descMatch[1].replace(/\n\s+/g, " ").trim();
    }
    return {
      name,
      description,
      size_bytes: stat.size,
      line_count: body.split("\n").length,
    };
  } catch {
    return null;
  }
}

export default async function ApiPage() {
  const skill = loadSkillMeta();
  const sizes = await loadEndpointSizes();

  return (
    <Shell>
      <section className={`${styles.page} page-width`}>
        <header className={styles.head}>
          <h1 className={`h-data ${styles.title}`}>
            Public read-only HTTP API
          </h1>
          <p className={styles.lede}>
            Every page on this site reads from{" "}
            <code className={styles.code}>
              api.deliverome.org/surfaceome/v1/*
            </code>
            , a Cloudflare Worker backed by a public D1 mirror of the
            project&apos;s annotation database. No authentication,
            CORS open to all origins, no rate limits.
          </p>
        </header>

        <section className={styles.skill}>
          <h2 className="h-data-section">Agent skill</h2>
          <p className={styles.skillBody}>
            A Markdown skill file documents the endpoints in the
            Anthropic skill format (
            <code className={styles.code}>name</code>{" "}
            /{" "}
            <code className={styles.code}>description</code>{" "}
            frontmatter plus instructions). Drop it into{" "}
            <code className={styles.code}>~/.claude/skills/</code> and
            an agent can call the API without further prompting.
          </p>
          {skill ? (
            <div className={styles.skillCard}>
              <div className={styles.skillMeta}>
                <p className={styles.skillName}>{skill.name}</p>
                <p className={styles.skillSize}>
                  {skill.line_count.toLocaleString()} lines ·{" "}
                  {(skill.size_bytes / 1024).toFixed(1)} KB · Markdown
                </p>
              </div>
              <p className={styles.skillDesc}>{skill.description}</p>
              <a
                className={styles.downloadBtn}
                href="/surfaceome-api.skill.md"
                download
              >
                Download skill ↓
              </a>
            </div>
          ) : (
            <p className={styles.empty}>
              Skill file is missing from the build — file an issue.
            </p>
          )}
        </section>

        <section className={styles.endpoints}>
          <h2 className="h-data-section">Endpoints</h2>
          {ENDPOINT_GROUPS.map((group) => (
            <div key={group.label} className={styles.endpointGroup}>
              <h3 className={styles.groupLabel}>{group.label}</h3>
              <p className={styles.groupBlurb}>{group.blurb}</p>
              <ul className={styles.endpointList}>
                {group.endpoints.map((e) => (
                  <li
                    key={e.path}
                    id={e.anchor}
                    className={styles.endpoint}
                  >
                    <p className={styles.endpointLine}>
                      <span className={styles.method}>{e.method}</span>
                      <code className={styles.endpointPath}>{e.path}</code>
                      {(() => {
                        const s = e.sizeKey ? sizes[e.sizeKey] : undefined;
                        const label = s ? formatBytes(s.bytes) : "";
                        if (!label) return null;
                        return (
                          <span
                            className={styles.endpointSize}
                            title={`Approx response size${s?.note ? ` (${s.note})` : ""} · computed from D1 at build`}
                          >
                            {s?.approx ? "~" : ""}
                            {label}
                          </span>
                        );
                      })()}
                    </p>
                    <p className={styles.endpointSummary}>{e.summary}</p>
                    {e.curl ? (
                      <pre className={styles.curl}>
                        <code>{e.curl}</code>
                      </pre>
                    ) : null}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </section>

        <footer className={styles.footnotes}>
          <p>
            <span className="label-mono">Caching ·</span> List endpoints
            (<code className={styles.code}>/v1/health</code>,{" "}
            <code className={styles.code}>/v1/genes</code>,{" "}
            <code className={styles.code}>/v1/catalog</code>,{" "}
            <code className={styles.code}>/v1/triage/*</code>) ship{" "}
            <code className={styles.code}>Cache-Control: max-age=60</code>;
            per-gene records, benchmark, and ortholog endpoints ship{" "}
            <code className={styles.code}>max-age=86400</code> (one day).
            Build-time consumers should use{" "}
            <code className={styles.code}>cache: &quot;force-cache&quot;</code>{" "}
            so the response is baked into the static artifact.
          </p>
          <p>
            <span className="label-mono">Schema ·</span> Per-gene records
            validate against the{" "}
            <code className={styles.code}>SurfaceomeRecord</code>{" "}
            Pydantic schema at{" "}
            <code className={styles.code}>
              src/accessible_surfaceome/tools/_shared/models.py
            </code>{" "}
            in the source repo. Fields not present in older records are
            absent on the wire — use optional-chaining when reading.
          </p>
          <p>
            <span className="label-mono">Sizes ·</span> The{" "}
            <code className={styles.code}>~size</code> on each endpoint is an
            approximate response size computed from live D1 row counts and{" "}
            <code className={styles.code}>LENGTH(...)</code> sums (
            <code className={styles.code}>/v1/meta/sizes</code>), baked in at
            build time so it refreshes on each deploy rather than being
            hand-maintained. Variable-length text is summed exactly; JSON/TSV
            structural overhead is estimated.
          </p>
          <p>
            <span className="label-mono">For agents ·</span> Start at{" "}
            <code className={styles.code}>/v1</code> (a self-describing
            index of every endpoint) or download the skill above. The site
            root also serves an{" "}
            <a className={styles.code} href="/llms.txt">
              llms.txt
            </a>{" "}
            that links the API, the skill, and the per-gene record + Markdown
            mirror.
          </p>
          <p>
            <span className="label-mono">Source ·</span> Worker code at{" "}
            <code className={styles.code}>
              cloudflare/workers/surfaceome_api/src/index.js
            </code>
            ; D1 schema at{" "}
            <code className={styles.code}>
              cloudflare/d1_public_schema.sql
            </code>
            .
          </p>
        </footer>
      </section>
    </Shell>
  );
}
