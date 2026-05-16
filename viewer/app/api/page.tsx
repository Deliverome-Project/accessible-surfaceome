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
    blurb: "Health + per-gene lookups.",
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
          "List of genes that have a deep-dive SurfaceomeRecord on file (summary fields only — gene symbol, UniProt, schema version, top-line verdict).",
        curl: "curl -s https://api.deliverome.org/surfaceome/v1/genes | jq '.count'",
      },
      {
        method: "GET",
        path: "/v1/genes/{SYMBOL}",
        summary:
          "Full SurfaceomeRecord JSON for one gene — targetability tier, surface biology with seven per-DB votes, primary + secondary evidence chain, risk flags, rationale. The single richest payload in the API.",
        curl:
          "curl -s https://api.deliverome.org/surfaceome/v1/genes/ERBB2 | jq '.targetability.tier, .confidence'",
      },
      {
        method: "GET",
        path: "/v1/orthologs/{SYMBOL}",
        summary:
          "Mouse + cynomolgus orthologs for a human gene from the latest Ensembl Compara release. Powers the cross-species ECD-identity callouts on the deep-dive page.",
        curl:
          "curl -s https://api.deliverome.org/surfaceome/v1/orthologs/ERBB2 | jq '.release_version, (.orthologs | length)'",
      },
    ],
  },
  {
    label: "Genome-wide",
    blurb:
      "All ~19,300 protein-coding human genes with their per-DB surface votes and the latest Sonnet/NCBI triage verdict. This is the data the homepage table renders.",
    endpoints: [
      {
        method: "GET",
        path: "/v1/catalog",
        summary:
          "Per-gene-per-source DB-vote matrix (5 gating DBs: UniProt / GO / SURFY / CSPA / HPA) + latest triage verdict + reason code + deep-dive flag. One row per protein-coding gene (~19k rows); response is ~3.8 MB gzipped, ~24 MB decoded — too large to inline reasoning text, so the free-text per-run verdict_reasoning is on /v1/triage/{SYMBOL} instead. Drives the homepage CatalogTable.",
        curl:
          "curl -s https://api.deliverome.org/surfaceome/v1/catalog | jq '.universe_version, .n_rows, .n_with_triage'",
      },
      {
        method: "GET",
        path: "/v1/triage/{SYMBOL}",
        anchor: "triage",
        summary:
          "Every triage run on file for one gene — model × prompt-variant × replicate, with verdict, reason, confidence, latency, cost_usd, per-call token counts, and the agent's free-text verdict_reasoning. The catalog's drawer pulls from this endpoint.",
        curl:
          "curl -s https://api.deliverome.org/surfaceome/v1/triage/ERBB2 | jq '.count, .runs[0]'",
      },
      {
        method: "GET",
        path: "/v1/triage/export.tsv",
        summary:
          "Long-format TSV of every triage run for one run_id. Default is mainbench_canonical_v1 (1,470 SurfaceBench rows); pass run_id=genome_full_sonnet_ncbi_v1 for the full ~19k-gene Sonnet/NCBI sweep. Same 14-column shape that scripts/export_mainbench_to_tsv.py writes to data/processed/triage_bench/.",
        curl:
          "curl -s 'https://api.deliverome.org/surfaceome/v1/triage/export.tsv?run_id=genome_full_sonnet_ncbi_v1&replicate=1' | head -3",
      },
    ],
  },
  {
    label: "SurfaceBench",
    blurb:
      "147 curated proteins with ground-truth surface verdicts — the eval set behind every published cost/accuracy figure.",
    endpoints: [
      {
        method: "GET",
        path: "/v1/benchmark",
        summary:
          "147 SurfaceBench ground-truth labels (gene, UniProt, class, verdict, signal, reason, rationale) for the current bench_version. JSON shape.",
        curl:
          "curl -s https://api.deliverome.org/surfaceome/v1/benchmark | jq '.count, .bench_version'",
      },
      {
        method: "GET",
        path: "/v1/benchmark/export.tsv",
        summary:
          "Same 147 truth labels as /v1/benchmark, in 7-column TSV shape — mirrors data/eval/triage_benchmark_v1.tsv so figure scripts can pd.read_csv it directly.",
        curl:
          "curl -s https://api.deliverome.org/surfaceome/v1/benchmark/export.tsv | head -3",
      },
      {
        method: "GET",
        path: "/v1/benchmark/{SYMBOL}",
        summary: "Single gene's SurfaceBench truth label + rationale.",
        curl:
          "curl -s https://api.deliverome.org/surfaceome/v1/benchmark/ERBB2 | jq '.truth_verdict, .truth_reason'",
      },
      {
        method: "GET",
        path: "/v1/benchmark/matrix",
        anchor: "benchmark-matrix",
        summary:
          "Full SurfaceBench matrix — one row per gene with truth + 7 per-DB flags + per-model LLM verdicts (headline + 3 alt prompt variants). Includes the agent's free-text reasoning on every (model, variant) cell, which the SurfaceBench page's side-drawer renders. Single round-trip; ~2 MB JSON.",
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

        <aside className={styles.callout}>
          <p className={styles.calloutLabel}>Where the reasoning lives</p>
          <p className={styles.calloutBody}>
            The bulk summary endpoints (
            <code className={styles.code}>/v1/catalog</code>,{" "}
            <code className={styles.code}>/v1/benchmark</code>) ship
            verdicts + reason codes only — they&apos;d be too large to
            inline the agent&apos;s free-text{" "}
            <code className={styles.code}>verdict_reasoning</code>{" "}
            paragraph on every row. For the full reasoning text:
          </p>
          <ul className={styles.calloutList}>
            <li>
              One gene (any of ~19k):{" "}
              <code className={styles.code}>
                GET /v1/triage/&#123;SYMBOL&#125;
              </code>{" "}
              — every model × prompt-variant × replicate run on file,
              with the reasoning paragraph on each.
            </li>
            <li>
              Bulk download:{" "}
              <code className={styles.code}>
                GET /v1/triage/export.tsv?run_id=…
              </code>{" "}
              — long-format TSV, one row per (gene, run), reasoning
              column included.
            </li>
            <li>
              SurfaceBench 147 with reasoning per cell:{" "}
              <code className={styles.code}>
                GET /v1/benchmark/matrix
              </code>{" "}
              — full 3 model × 4 variant grid with{" "}
              <code className={styles.code}>reasoning</code> populated
              on each verdict object.
            </li>
          </ul>
        </aside>

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
          <h2 className="h-data-section">Data flow (pre-publication)</h2>
          <p className={styles.skillBody}>
            The work is <strong>pre-publication</strong>; figures and
            tables shown today are draft artifacts and will be re-pinned
            to Zenodo DOIs at submission time. Today the lineage runs:
          </p>
          <pre className={styles.lineage}>
{`private D1 ──sync_public_d1.py──▶ public D1
                                    │
                                    ├─▶ this API  (live consumers: viewer, agents, notebooks)
                                    │
                                    └─▶ scripts/export_mainbench_to_tsv.py
                                          ▼
                                        data/processed/triage_bench/mainbench_canonical_v1.tsv
                                          ▼
                                        raw.githubusercontent.com/<repo>/<branch>/...
                                          ▼
                                        figure scripts + published gists`}
          </pre>
          <p className={styles.skillBody}>
            <strong>Final figures</strong> read their data from{" "}
            <code className={styles.code}>raw.githubusercontent.com</code>{" "}
            — pinned to a commit SHA at publication for stable citation,
            and eventually mirrored to a Zenodo DOI. The API on this
            page is the source for everything <em>live</em>: the viewer,
            agent skills, notebook exploration. Both surfaces mirror the
            same public D1.
          </p>
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
