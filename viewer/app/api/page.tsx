import path from "node:path";
import { readFileSync, statSync } from "node:fs";
import type { Metadata } from "next";
import { Shell } from "../../components/Shell/Shell";
import styles from "./page.module.css";

export const metadata: Metadata = {
  title: "API usage — Surfaceome",
  description:
    "Public read-only API at api.deliverome.org/surfaceome/v1/* plus a " +
    "downloadable Claude agent skill that teaches an agent how to call it.",
};

interface Endpoint {
  method: "GET";
  path: string;
  summary: string;
  /** Optional one-line curl example. */
  curl?: string;
}

const ENDPOINTS: Endpoint[] = [
  {
    method: "GET",
    path: "/v1/health",
    summary: "Liveness check. Returns the count of deep-dive records on file.",
    curl: "curl -s https://api.deliverome.org/surfaceome/v1/health",
  },
  {
    method: "GET",
    path: "/v1/genes",
    summary:
      "List of genes that have a deep-dive SurfaceomeRecord on file (summary fields).",
    curl: "curl -s https://api.deliverome.org/surfaceome/v1/genes | jq '.count'",
  },
  {
    method: "GET",
    path: "/v1/genes/{SYMBOL}",
    summary:
      "Full SurfaceomeRecord JSON for one gene — targetability, surface biology, evidence, risk flags, rationale.",
    curl:
      "curl -s https://api.deliverome.org/surfaceome/v1/genes/ERBB2 | jq '.targetability.tier'",
  },
  {
    method: "GET",
    path: "/v1/catalog",
    summary:
      "Genome-wide table: per-gene-per-source DB votes (5 sources) + latest triage verdict + deep-dive flag. ~6 MB; drives the homepage.",
    curl:
      "curl -s https://api.deliverome.org/surfaceome/v1/catalog | jq '.n_rows'",
  },
  {
    method: "GET",
    path: "/v1/benchmark",
    summary:
      "147 SurfaceBench ground-truth labels for the current bench_version.",
    curl:
      "curl -s https://api.deliverome.org/surfaceome/v1/benchmark | jq '.count'",
  },
  {
    method: "GET",
    path: "/v1/benchmark/matrix",
    summary:
      "Full SurfaceBench matrix: truth + 7 per-DB flags + per-model LLM verdicts (headline + alts). Drives the /benchmark/ page.",
    curl:
      "curl -s https://api.deliverome.org/surfaceome/v1/benchmark/matrix | jq '.n_genes, .models'",
  },
  {
    method: "GET",
    path: "/v1/benchmark/{SYMBOL}",
    summary: "Single gene's SurfaceBench truth label and rationale.",
    curl:
      "curl -s https://api.deliverome.org/surfaceome/v1/benchmark/ERBB2 | jq '.truth_verdict'",
  },
  {
    method: "GET",
    path: "/v1/triage/{SYMBOL}",
    summary:
      "Every triage run on file for a gene (model × prompt variant × replicate) with verdict, reason, confidence, latency, cost, and token counts.",
    curl:
      "curl -s https://api.deliverome.org/surfaceome/v1/triage/ERBB2 | jq '.count'",
  },
  {
    method: "GET",
    path: "/v1/triage/export.tsv",
    summary:
      "Long-format TSV of every triage run for a given run_id (default mainbench_canonical_v1). The canonical source of truth for the figure-reproduction scripts and gists.",
    curl:
      "curl -s 'https://api.deliverome.org/surfaceome/v1/triage/export.tsv?run_id=mainbench_canonical_v1&replicate=1' | head -3",
  },
  {
    method: "GET",
    path: "/v1/orthologs/{SYMBOL}",
    summary:
      "Mouse + cynomolgus orthologs from the latest Ensembl Compara release.",
    curl:
      "curl -s https://api.deliverome.org/surfaceome/v1/orthologs/ERBB2 | jq '.release_version'",
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

export default function ApiPage() {
  const skill = loadSkillMeta();

  return (
    <Shell>
      <section className={`${styles.page} page-width`}>
        <header className={styles.head}>
          <p className="h-data-eyebrow">API · v1</p>
          <h1 className={`h-data ${styles.title}`}>
            Public read-only API.
          </h1>
          <p className={styles.lede}>
            Every page on this site is a thin renderer over{" "}
            <code className={styles.code}>
              api.deliverome.org/surfaceome/v1/*
            </code>{" "}
            — a no-auth, CORS-open Cloudflare Worker backed by a public
            D1 mirror. Hit it from a notebook, a CLI, an SPA, or an
            agent. Aggressive edge caching means responses are fast and
            cheap; nothing here is rate-limited.
          </p>
        </header>

        <section className={styles.skill}>
          <h2 className="h-data-section">Agent skill</h2>
          <p className={styles.skillBody}>
            Drop the markdown below into{" "}
            <code className={styles.code}>~/.claude/skills/</code> (or
            any agent skill loader that consumes Anthropic-style{" "}
            <code className={styles.code}>name</code>/
            <code className={styles.code}>description</code> frontmatter)
            and your agent will know how and when to call this API
            without further prompting.
          </p>
          {skill ? (
            <div className={styles.skillCard}>
              <div className={styles.skillMeta}>
                <p className={styles.skillName}>{skill.name}</p>
                <p className={styles.skillSize}>
                  {skill.line_count.toLocaleString()} lines ·{" "}
                  {(skill.size_bytes / 1024).toFixed(1)} KB ·
                  Markdown
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

        <section className={styles.skill}>
          <h2 className="h-data-section">Reproduce the figures</h2>
          <p className={styles.skillBody}>
            Every figure in this project is regenerated from{" "}
            <code className={styles.code}>
              api.deliverome.org/surfaceome/v1/*
            </code>
            . Cost-vs-accuracy, per-DB correctness, ensemble-vs-Sonnet,
            and the rest pull from one of two endpoints:
          </p>
          <ul className={styles.repList}>
            <li>
              <code className={styles.code}>
                /v1/triage/export.tsv?run_id=mainbench_canonical_v1
              </code>{" "}
              — long-format TSV of the 147-gene × {`{model × variant}`}{" "}
              sweep, with verdict / reason / confidence /{" "}
              <strong>cost_usd</strong> / token counts / latency.
            </li>
            <li>
              <code className={styles.code}>
                /v1/benchmark/export.tsv
              </code>{" "}
              — 7-column TSV of curated truth labels for the same
              147 genes (verdict / signal / reason / rationale).
            </li>
            <li>
              <code className={styles.code}>/v1/catalog</code> — genome-wide
              per-DB votes and latest triage verdict for the universe
              consensus figures.
            </li>
          </ul>
          <p className={styles.skillBody}>
            Each figure script under{" "}
            <code className={styles.code}>data/analysis/figures/</code>{" "}
            and its published gist load directly from these URLs — no
            local data files, no committed TSVs required.
          </p>
        </section>

        <section className={styles.endpoints}>
          <h2 className="h-data-section">Endpoints</h2>
          <ul className={styles.endpointList}>
            {ENDPOINTS.map((e) => (
              <li key={e.path} className={styles.endpoint}>
                <p className={styles.endpointLine}>
                  <span className={styles.method}>{e.method}</span>
                  <code className={styles.endpointPath}>{e.path}</code>
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
        </section>

        <footer className={styles.footnotes}>
          <p>
            <span className="label-mono">Caching ·</span> List
            endpoints (
            <code className={styles.code}>/v1/health</code>,{" "}
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
            <code className={styles.code}>SurfaceomeRecord</code> Pydantic
            schema at{" "}
            <code className={styles.code}>
              src/accessible_surfaceome/tools/_shared/models.py
            </code>{" "}
            in the source repo. Fields not present in older records are
            absent on the wire — use optional-chaining when reading.
          </p>
          <p>
            <span className="label-mono">Source ·</span> Worker code lives
            at{" "}
            <code className={styles.code}>
              cloudflare/workers/surfaceome_api/src/index.js
            </code>{" "}
            in the public repo; the D1 schema is at{" "}
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
