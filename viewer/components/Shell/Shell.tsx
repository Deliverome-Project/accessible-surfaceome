import Link from "next/link";
import type { ReactNode } from "react";
import { InfoTipAutoPlace } from "../InfoTip/InfoTipAutoPlace";
import { NavLink } from "./NavLink";
import styles from "./Shell.module.css";

interface ShellProps {
  children: ReactNode;
}

/**
 * Base URL for the parent deliverome.org site. Honors
 * ``NEXT_PUBLIC_DELIVEROME_SITE_URL`` so the surfaceome viewer can be
 * pointed at a staging preview (e.g. the PR24 branch preview at
 * ``https://feat-site-partners-careers-r.deliverome.pages.dev``) without
 * rebuilding the Shell. Default is production deliverome.org.
 */
const PARENT_SITE = (
  process.env.NEXT_PUBLIC_DELIVEROME_SITE_URL ?? "https://deliverome.org"
).replace(/\/$/, "");

function parentHref(path: string): string {
  return `${PARENT_SITE}${path}`;
}

/**
 * Shell — site-wide layout for surfaceome.deliverome.org.
 *
 * Single-row header (Pattern B in the sub-site shell taxonomy):
 *   • Brand lockup on the left — Deliverome logo + "The Deliverome Project"
 *     wordmark in Playfair Display italic, sized + spaced to match
 *     ``deliverome-internal:site/components/SiteShell/Header.tsx``. The
 *     wordmark is a link back to deliverome.org.
 *   • A `/` separator + "Surfaceome" sub-brand so the URL hierarchy
 *     reads inline ("Deliverome / Surfaceome") without a second nav row.
 *   • Right side: local Surfaceome nav (Compare · SurfaceBench · API ·
 *     Prompts · Reproducibility) + GitHub icon. Mirrors the spacing /
 *     typography of the parent's primary nav (`Team · News · Careers ·
 *     Contact`) so the two sites visually share a header shape.
 *
 * Why single-row instead of the prior two-row shell: a sub-site doesn't
 * need to claim a whole nav strip for the parent's links — visitors
 * arriving at surfaceome.deliverome.org are deep-link readers, not
 * marketing browsers. The brand lockup on the left is enough parent
 * context. Cleaner than the borrowed two-row design and removes the
 * competing nav contexts. See PR24 ref:
 *   github.com/Deliverome-Project/deliverome-internal/pull/24
 *
 * Keep the brand-lockup sizing in sync with that file when it rev's
 * (font-size, gap, logo dimensions).
 */
export function Shell({ children }: ShellProps) {
  return (
    <div className={styles.shell}>
      {/* One document-level listener that keeps every InfoTip popover on
       *  screen (writes `--infotip-shift`). Renders null — see
       *  InfoTipAutoPlace.tsx for why this stays out of the server-only
       *  InfoTip component. */}
      <InfoTipAutoPlace />
      <a className={styles.skipLink} href="#main-content">
        Skip to main content
      </a>
      <header className={styles.header}>
        <div className={styles.headerInner}>
          <div className={styles.brandLockup}>
            {/* Parent-site anchor — clicking the Deliverome wordmark
             *  returns to deliverome.org (or whatever
             *  NEXT_PUBLIC_DELIVEROME_SITE_URL is pointed at). */}
            <a className={styles.brandParent} href={parentHref("/")}>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                className={styles.brandMark}
                src="/assets/internalization_logo.svg"
                alt=""
                width={40}
                height={40}
              />
              <span className={styles.brandParentText}>
                The Deliverome Project
              </span>
            </a>
            <span className={styles.brandSep} aria-hidden="true">
              /
            </span>
            <Link href="/" className={styles.brandLocal}>
              <span className={styles.brandLocalText}>Surfaceome</span>
            </Link>
          </div>
          <nav id="primary-nav" className={styles.nav} aria-label="Surfaceome sections">
            <NavLink href="/compare" matchPrefix>
              Compare
            </NavLink>
            <NavLink href="/benchmark" matchPrefix>
              SurfaceBench
            </NavLink>
            <NavLink href="/api" matchPrefix>
              API
            </NavLink>
            <NavLink href="/prompts" matchPrefix>
              Prompts
            </NavLink>
            <NavLink href="/reproducibility" matchPrefix>
              Reproducibility
            </NavLink>
            <NavLink
              href="https://github.com/Deliverome-Project/accessible-surfaceome"
              external
              extraClass={styles.navIconLink}
              ariaLabel="GitHub — Deliverome-Project/accessible-surfaceome"
              title="GitHub — Deliverome-Project/accessible-surfaceome"
            >
              {/* Inline GitHub mark — public-domain octocat path from
                  github.com/logos. Kept inline so the icon ships in
                  the same React tree as the rest of the nav, no asset
                  pipeline. */}
              <svg
                viewBox="0 0 24 24"
                role="img"
                aria-hidden="true"
                focusable="false"
                width="18"
                height="18"
              >
                <path
                  fill="currentColor"
                  d="M12 .5C5.65.5.5 5.65.5 12c0 5.08 3.29 9.39 7.86 10.91.58.1.79-.25.79-.56v-1.97c-3.2.7-3.87-1.54-3.87-1.54-.52-1.32-1.27-1.67-1.27-1.67-1.04-.71.08-.7.08-.7 1.15.08 1.76 1.18 1.76 1.18 1.02 1.74 2.67 1.24 3.32.95.1-.74.4-1.24.73-1.53-2.55-.29-5.24-1.28-5.24-5.69 0-1.26.45-2.29 1.18-3.1-.12-.29-.51-1.46.11-3.05 0 0 .97-.31 3.18 1.18a11 11 0 0 1 5.79 0c2.21-1.49 3.18-1.18 3.18-1.18.62 1.59.23 2.76.11 3.05.73.81 1.18 1.84 1.18 3.1 0 4.42-2.69 5.39-5.25 5.68.41.36.78 1.06.78 2.14v3.17c0 .31.21.67.8.56 4.57-1.52 7.85-5.83 7.85-10.91C23.5 5.65 18.35.5 12 .5Z"
                />
              </svg>
              <span className="sr-only">GitHub</span>
            </NavLink>
          </nav>
        </div>
      </header>

      <main id="main-content" className={styles.main} tabIndex={-1}>
        {children}
      </main>

      <footer className={styles.footer}>
        <div className={styles.footerInner}>
          <div className={styles.footerCopyBlock}>
            <p className={styles.footerCopy}>
              Surfaceome is part of{" "}
              <a href={parentHref("/")} className={styles.footerLink}>
                The Deliverome Project
              </a>{" "}
              — a nonprofit focused research organization.
            </p>
            <p className={styles.footerMeta}>
              <span>© {new Date().getFullYear()} Deliverome Bio</span>
              <span aria-hidden="true" className={styles.metaSep}>·</span>
              <a href="mailto:surfaceome-viewer@deliverome.org" className={styles.footerLink}>
                surfaceome-viewer@deliverome.org
              </a>
            </p>
          </div>
          {/*
           * Socials block — X + LinkedIn. Mirrors the parent shell at
           * deliverome-internal:site/components/SiteShell/SiteShell.tsx
           * (same aria-labels, same `rel="noreferrer"`, same icon
           * dimensions — 18 × 18 for X, 19 × 19 for LinkedIn — and the
           * same LinkedIn company URL). Bluesky is intentionally omitted
           * on the sub-site. When the parent's social set changes, mirror
           * it here.
           */}
          <div className={styles.footerSocial} aria-label="Social links">
            <a
              className={styles.footerSocialLink}
              href="https://x.com/deliverome"
              target="_blank"
              rel="noreferrer"
              aria-label="Deliverome on X"
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src="/assets/x.svg" alt="" width={18} height={18} />
            </a>
            <a
              className={styles.footerSocialLink}
              href="https://www.linkedin.com/company/deliverome"
              target="_blank"
              rel="noreferrer"
              aria-label="Deliverome on LinkedIn"
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src="/assets/linkedin.svg" alt="" width={19} height={19} />
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
}
