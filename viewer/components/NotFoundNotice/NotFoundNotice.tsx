"use client";

import { useEffect, useState } from "react";

/**
 * A path like ``/GPR75/`` → ``GPR75``. Only a SINGLE, gene-symbol-shaped
 * segment counts as a gene; multi-segment or odd paths fall through to the
 * generic not-found copy. Kept deliberately loose (the catalog has ~5k
 * symbols and we don't ship the list to the 404 bundle) — we only claim
 * "no deep-dive page for X", which is true for any catalogued-but-not-
 * deep-dived gene AND harmless for a genuinely bogus symbol-shaped URL.
 */
function geneFromPath(pathname: string): string | null {
  const segs = pathname.split("/").filter(Boolean);
  if (segs.length !== 1) return null;
  const seg = decodeURIComponent(segs[0]);
  return /^[A-Za-z0-9][A-Za-z0-9._-]{0,19}$/.test(seg) ? seg.toUpperCase() : null;
}

/**
 * Client leaf of the app-wide not-found page. Under ``output: export`` the
 * whole app compiles a single static ``404.html`` that Cloudflare Pages
 * serves for every unmatched route — including ``/{SYMBOL}/`` for a gene
 * that has no deep-dive page (not every catalogued protein is deep-dived).
 * The gene symbol only exists in the browser URL at serve time, so this
 * runs client-side to turn a bare "404" into a self-explaining
 * "no deep-dive page for GPR75".
 */
export function NotFoundNotice() {
  const [gene, setGene] = useState<string | null>(null);
  const [ready, setReady] = useState(false);
  useEffect(() => {
    setGene(geneFromPath(window.location.pathname));
    setReady(true);
  }, []);

  // Pre-hydration (== the statically-baked 404.html) and non-gene paths get
  // the neutral copy, so the exported HTML is never wrong before the URL is
  // known.
  if (!ready || !gene) {
    return (
      <>
        <p className="label-mono">404 · page not found</p>
        <h1 className="h-display">This page doesn&rsquo;t exist</h1>
        <p className="lede">
          The page you&rsquo;re looking for isn&rsquo;t here. If you were after a
          gene, it may not have a deep-dive page yet.
        </p>
      </>
    );
  }
  return (
    <>
      <p className="label-mono">No deep dive</p>
      <h1 className="h-display">No deep-dive page for {gene}</h1>
      <p className="lede">
        Not every catalogued protein has a deep-dive page yet — only genes the
        deep-dive agent has been run on do. {gene} may be in the surfaceome
        catalog, but it hasn&rsquo;t been deep-dived, so there&rsquo;s no
        deep-dive page to show.
      </p>
    </>
  );
}
