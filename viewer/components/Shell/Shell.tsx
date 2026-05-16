import Link from "next/link";
import type { ReactNode } from "react";
import { NavDropdown } from "../NavDropdown/NavDropdown";
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
 *
 * Trailing slash trimmed so the link builder can concatenate paths
 * starting with ``/`` cleanly.
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
 * Two-row header so this subdomain reads as a tab inside the larger
 * deliverome.org property rather than a standalone microsite:
 *
 *   Row 1 (parent-site strip) — Deliverome logo + NavDropdown menus
 *                               (Platform → Overview / Progress;
 *                               Company → Team / Updates / Careers) +
 *                               Contact. Mirrors deliverome.org's
 *                               SiteShell nav structure.
 *   Row 2 (local nav)         — "Surfaceome" sub-brand + the four
 *                               in-site sections (SurfaceBench, API,
 *                               Prompts, GitHub icon).
 *
 * Keep both files in sync when the parent SiteShell rev's its nav.
 * Parent ref: ``Deliverome-Project/deliverome-internal:site/components/
 * site-shell.tsx``.
 */
export function Shell({ children }: ShellProps) {
  return (
    <div className={styles.shell}>
      <a className={styles.skipLink} href="#main-content">
        Skip to main content
      </a>
      <header className={styles.header}>
        <div className={styles.parentStrip}>
          <div className={styles.parentInner}>
            <a className={styles.parentBrand} href={parentHref("/")}>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src="/assets/provisional_logo.svg"
                alt=""
                width={32}
                height={32}
                className={styles.parentLogo}
              />
              <span className={styles.parentBrandText}>
                The Deliverome Project
              </span>
            </a>
            <nav className={styles.parentNav} aria-label="Deliverome">
              <NavDropdown
                label="Platform"
                items={[
                  { label: "Overview", href: parentHref("/platform/") },
                  { label: "Progress tracker", href: parentHref("/platform/progress/") },
                ]}
              />
              <NavDropdown
                label="Company"
                items={[
                  { label: "Team", href: parentHref("/team/") },
                  { label: "Updates", href: parentHref("/updates/") },
                  { label: "Careers", href: parentHref("/careers/") },
                ]}
              />
              <a className={styles.parentLink} href={parentHref("/contact/")}>
                Contact
              </a>
            </nav>
          </div>
        </div>
        <div className={styles.headerInner}>
          <Link href="/" className={styles.brand}>
            <span className={styles.brandMark} aria-hidden="true" />
            <span className={styles.brandText}>Surfaceome</span>
            <span className={styles.brandSubtitle} aria-hidden="true">
              · accessible surface proteome
            </span>
          </Link>
          <nav className={styles.nav} aria-label="Surfaceome sections">
            <Link className={styles.navLink} href="/benchmark">
              SurfaceBench
            </Link>
            <Link className={styles.navLink} href="/api">
              API
            </Link>
            <Link className={styles.navLink} href="/prompts">
              Prompts
            </Link>
            <Link className={styles.navLink} href="/reproducibility">
              Reproducibility
            </Link>
            <a
              className={`${styles.navLink} ${styles.navIconLink}`}
              href="https://github.com/Deliverome-Project/accessible-surfaceome"
              target="_blank"
              rel="noopener noreferrer"
              aria-label="GitHub — Deliverome-Project/accessible-surfaceome"
              title="GitHub — Deliverome-Project/accessible-surfaceome"
            >
              {/* Inline GitHub mark — keeps the icon a single self-contained
                  React element with no asset pipeline. Path lifted from
                  github.com/logos (public-domain octocat). */}
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
            </a>
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
              — a nonprofit focused research organization. Schema, evidence,
              and agents shipped from{" "}
              <a
                href="https://github.com/Deliverome-Project/accessible-surfaceome"
                target="_blank"
                rel="noopener noreferrer"
                className={styles.footerLink}
              >
                Deliverome-Project/accessible-surfaceome
              </a>
              .
            </p>
            <p className={styles.footerMeta}>
              <span>© {new Date().getFullYear()} Deliverome Bio</span>
              <span aria-hidden="true" className={styles.metaSep}>·</span>
              <a href="mailto:contact@deliverome.org" className={styles.footerLink}>
                contact@deliverome.org
              </a>
            </p>
          </div>
          <div className={styles.footerSocial} aria-label="Social links">
            <a
              className={styles.footerSocialLink}
              href="https://x.com/deliverome"
              target="_blank"
              rel="noopener noreferrer"
              aria-label="Deliverome on X"
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src="/assets/x.svg" alt="" width={18} height={18} />
            </a>
            <a
              className={styles.footerSocialLink}
              href="https://bsky.app/profile/deliverome.bsky.social"
              target="_blank"
              rel="noopener noreferrer"
              aria-label="Deliverome on Bluesky"
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src="/assets/bluesky.svg" alt="" width={19} height={19} />
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
}
