import Link from "next/link";
import { Shell } from "../components/Shell/Shell";
import { NotFoundNotice } from "../components/NotFoundNotice/NotFoundNotice";

/**
 * App-wide not-found page. Under ``output: export`` this compiles to a
 * single static ``404.html`` that Cloudflare Pages serves for every route
 * that isn't a statically-generated page — which, for genes, means every
 * ``/{SYMBOL}/`` that wasn't deep-dived (``generateStaticParams`` only emits
 * the deep-dive set). The catalog / search / rationale-drawer already gate
 * their deep-dive links on ``deep_dive``, so this is the safety net for a
 * direct hit (bookmark, stale link, hand-typed URL): show "no deep-dive page
 * for X" instead of a bare 404, with a route back to the catalog.
 */
export default function NotFound() {
  return (
    <Shell>
      <section
        className="page-width"
        style={{ padding: "3.5rem 0 4rem", maxWidth: "42rem" }}
      >
        <NotFoundNotice />
        <p style={{ marginTop: "1.75rem" }}>
          <Link href="/">&larr; Browse the surfaceome catalog</Link>
        </p>
      </section>
    </Shell>
  );
}
