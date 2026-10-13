/*
 * Integration test for build-data-snapshot.mjs's early-abort circuit
 * breaker (PR #275 review, I1): once the running failure count exceeds
 * `floor(SURFACEOME_BUILD_MAX_FAILED_FRAC × total)`, the per-gene
 * pre-fetch worker loop must stop pulling NEW genes rather than
 * exhausting the retry budget on every single one of them during a real
 * outage.
 *
 * This runs the REAL script as a child process against a local HTTP mock
 * server (127.0.0.1, ephemeral port) — never the production API. Because
 * it exercises the script's actual (un-overridden) retry backoff
 * schedule, a single gene's retries genuinely take ~15s wall-clock
 * (1s+2s+4s+8s between 5 attempts) before the abort fires, so this test
 * is slow (~15-20s) but exact — it pins the real wiring, not just the
 * pure `shouldAbortEarly` predicate (which build_fetch.test.mjs already
 * covers instantly with an injected clock).
 *
 *   npx --yes tsx --test tests/build_data_snapshot_early_abort.test.mjs
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import { createServer } from "node:http";
import { spawn } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const VIEWER_ROOT = path.join(__dirname, "..");
const SCRIPT = path.join(VIEWER_ROOT, "scripts", "build-data-snapshot.mjs");

test(
  "build-data-snapshot.mjs: aborts early on an outage instead of exhausting every gene (I1)",
  { timeout: 60_000 },
  async () => {
    const TOTAL_GENES = 6;
    const attemptedGenes = new Set();

    const server = createServer((req, res) => {
      if (req.url === "/v1/genes") {
        const genes = Array.from({ length: TOTAL_GENES }, (_, i) => ({ gene_symbol: `GENE${i}` }));
        res.writeHead(200, { "content-type": "application/json" });
        res.end(JSON.stringify({ genes }));
        return;
      }
      if (req.url === "/v1/catalog" || req.url === "/v1/benchmark/matrix") {
        res.writeHead(200, { "content-type": "application/json" });
        res.end("{}");
        return;
      }
      if (req.url && req.url.startsWith("/v1/genes/")) {
        attemptedGenes.add(req.url);
        res.writeHead(500);
        res.end("simulated outage");
        return;
      }
      res.writeHead(404);
      res.end();
    });
    await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
    const { port } = server.address();
    const base = `http://127.0.0.1:${port}`;

    const child = spawn(
      process.execPath,
      [SCRIPT],
      {
        cwd: VIEWER_ROOT,
        env: {
          ...process.env,
          SURFACEOME_API_BASE: base,
          // concurrency=1 makes the outcome deterministic: only ONE gene
          // is ever in flight, so an early abort provably prevents the
          // cursor from ever reaching gene #2.
          SURFACEOME_BUILD_FETCH_CONCURRENCY: "1",
          SURFACEOME_BUILD_FETCH_RPS: "1000",
          // floor(0 × 6) = 0 — abort as soon as the FIRST gene fails.
          SURFACEOME_BUILD_MAX_FAILED_FRAC: "0",
        },
      },
    );
    let stderr = "";
    child.stderr.on("data", (d) => {
      stderr += d.toString();
    });
    const exitCode = await new Promise((resolve) => child.on("close", resolve));
    server.close();

    assert.equal(exitCode, 1, "must exit non-zero on a detected outage");
    assert.ok(
      stderr.includes("OUTAGE DETECTED"),
      `expected the early-abort log line, got stderr:\n${stderr.slice(0, 4000)}`,
    );
    assert.ok(
      attemptedGenes.size < TOTAL_GENES,
      `expected early abort to stop before every gene was attempted — ` +
        `attempted ${attemptedGenes.size}/${TOTAL_GENES}: ${[...attemptedGenes].join(", ")}`,
    );
    assert.equal(
      attemptedGenes.size,
      1,
      "with concurrency=1 and threshold=0, exactly ONE gene should ever be attempted before abort",
    );
  },
);
