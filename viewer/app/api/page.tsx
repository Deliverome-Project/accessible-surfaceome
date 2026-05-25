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
}

interface EndpointGroup {
  label: string;
  blurb: string;
  endpoints: Endpoint[];
}

const ENDPOINT_GROUPS: EndpointGroup[] = [
  {
    label: "Discovery",
    blurb: "Liveness check and per-gene record lookups.",
    endpoints: [
      {
        method: "GET",
        path: "/v1/health",
        summary:
          "Liveness check. Returns the count of deep-dive SurfaceomeRecords on file.",
        curl: "curl -s https://api.deliverome.org/surfaceome/v1/health",
      },
      {
        method: "GET",
        path: "/v1/genes",
        summary:
          "Index of genes with a deep-dive SurfaceomeRecord on file. Summary fields only: gene_symbol, uniprot_acc, schema_version, triage_signal, surface_status, annotated_at.",
        curl: "curl -s https://api.deliverome.org/surfaceome/v1/genes | jq '.count'",
      },
      {
        method: "GET",
        path: "/v1/genes/{SYMBOL}",
        summary:
          "Full SurfaceomeRecord JSON for one gene. Contains the executive summary, evidence-grade rationale, per-method observations, deterministic features, accessibility risks, and the full evidence ledger with citations.",
        curl:
          "curl -s https://api.deliverome.org/surfaceome/v1/genes/ERBB2 | jq '.executive_summary.surface_accessibility, .confidence'",
      },
      {
        method: "GET",
        path: "/v1/orthologs/{SYMBOL}",
        summary:
          "Mouse and cynomolgus orthologs for a human gene from the latest Ensembl Compara release.",
        curl:
          "curl -s https://api.deliverome.org/surfaceome/v1/orthologs/ERBB2 | jq '.release_version, (.orthologs | length)'",
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
        summary:
          "Per-gene-per-source surface-vote matrix (5 gating DBs: UniProt / GO / SURFY / CSPA / HPA) plus the latest triage verdict, short reason code, and deep-dive flag. One row per protein-coding gene (~19k). Free-text reasoning is omitted at this scale — fetch it per-gene from /v1/triage/{SYMBOL}.",
        curl:
          "curl -s https://api.deliverome.org/surfaceome/v1/catalog | jq '.universe_version, .n_rows, .n_with_triage'",
      },
      {
        method: "GET",
        path: "/v1/triage/{SYMBOL}",
        anchor: "triage",
        summary:
          "Every triage run on file for one gene — model × prompt-variant × replicate — with verdict, reason code, confidence, latency, per-call token counts, and the agent's free-text verdict_reasoning paragraph.",
        curl:
          "curl -s https://api.deliverome.org/surfaceome/v1/triage/ERBB2 | jq '.count, .runs[0]'",
      },
      {
        method: "GET",
        path: "/v1/triage/export.tsv",
        summary:
          "Long-format TSV of every triage run for one run_id. Each row is (gene × model × variant × replicate) with the 5-DB votes and uniprot_acc joined in server-side. Default run_id is mainbench_canonical_v1 (147 bench rows × 3 models × 4 variants); pass run_id=genome_full_sonnet_ncbi_v1 for the full ~19k-gene Sonnet sweep.",
        curl:
          "curl -s 'https://api.deliverome.org/surfaceome/v1/triage/export.tsv?run_id=genome_full_sonnet_ncbi_v1&replicate=1' | head -3",
      },
    ],
  },
  {
    label: "SurfaceBench",
    blurb:
      "147 curated proteins with ground-truth surface verdicts — the eval set behind the cost / accuracy figures.",
    endpoints: [
      {
        method: "GET",
        path: "/v1/benchmark",
        summary:
          "147 ground-truth labels (gene, UniProt, class, verdict, signal, reason, rationale) for the current bench_version.",
        curl:
          "curl -s https://api.deliverome.org/surfaceome/v1/benchmark | jq '.count, .bench_version'",
      },
      {
        method: "GET",
        path: "/v1/benchmark/export.tsv",
        summary:
          "Long-format TSV of the bench-restricted multi-model sweep: one row per (bench gene × model × variant) for the canonical bench_version. Adds the 5-DB vote vector and truth_verdict / truth_signal / truth_reason to the triage export shape.",
        curl:
          "curl -s https://api.deliverome.org/surfaceome/v1/benchmark/export.tsv | head -3",
      },
      {
        method: "GET",
        path: "/v1/benchmark/{SYMBOL}",
        summary:
          "Single gene's ground-truth label and rationale for the latest bench_version.",
        curl:
          "curl -s https://api.deliverome.org/surfaceome/v1/benchmark/ERBB2 | jq '.truth_verdict, .truth_reason'",
      },
      {
        method: "GET",
        path: "/v1/benchmark/matrix",
        anchor: "benchmark-matrix",
        summary:
          "Full SurfaceBench matrix in one round-trip: per-gene truth label, 5-DB vote vector, and per-(model, variant) verdicts with the agent's free-text reasoning on each cell. ~2 MB JSON. Drives the SurfaceBench page's side-drawer.",
        curl:
          "curl -s https://api.deliverome.org/surfaceome/v1/benchmark/matrix | jq '.n_genes, .models, .headline_variant, .alt_variants'",
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

export default function ApiPage() {
  const skill = loadSkillMeta();

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
