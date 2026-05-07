// Format-aware preflight: ?format=json or ?format=md replaces the page with
// a plaintext rendering for agents and curl. Runs synchronously before React.

import type { SurfaceomeRecord } from "./types";
import { recordToMarkdown } from "./markdownExport";

export async function maybeRunPreflight(): Promise<boolean> {
  const p = new URLSearchParams(window.location.search);
  const fmt = (p.get("format") || "").toLowerCase();
  if (fmt !== "json" && fmt !== "md" && fmt !== "markdown") return false;

  // Only intercept on /gene/:symbol routes.
  const m = /^\/gene\/([^\/?#]+)/.exec(window.location.pathname);
  if (!m) return false;
  const symbol = decodeURIComponent(m[1]);

  let rec: SurfaceomeRecord;
  try {
    const r = await fetch(`/data/genes/${symbol}.json`);
    if (!r.ok) throw new Error(`fetch ${symbol}.json: ${r.status}`);
    rec = await r.json();
  } catch (e) {
    document.body.textContent = `Error loading ${symbol}: ${(e as Error).message}`;
    return true;
  }

  let body: string;
  let mime: string;
  let ext: string;
  if (fmt === "json") {
    body = JSON.stringify({ record: rec, evidence: [], sources: {} }, null, 2);
    mime = "application/json";
    ext = "json";
  } else {
    body = recordToMarkdown(rec, [], {});
    mime = "text/markdown";
    ext = "md";
  }
  document.open();
  document.write(
    '<!doctype html><html><head><meta charset="utf-8">' +
      `<meta http-equiv="Content-Type" content="${mime}; charset=utf-8">` +
      `<title>${rec.gene.hgnc_symbol}.${ext}</title>` +
      `<style>html,body{margin:0;padding:0;background:#fafaf7;color:#1c1c19;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:13px;line-height:1.55}pre{margin:0;padding:32px;white-space:pre-wrap;word-break:break-word}</style>` +
      "</head><body><pre id=\"raw\"></pre></body></html>",
  );
  document.close();
  document.getElementById("raw")!.textContent = body;
  return true;
}
