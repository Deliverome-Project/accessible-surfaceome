import Link from "next/link";
import type { ReactNode } from "react";
import styles from "./Shell.module.css";

interface ShellProps {
  children: ReactNode;
}

/**
 * Shell — site-wide layout for surfaceome.deliverome.org. Thin
 * header + footer with a Deliverome cross-link, designed for a
 * sub-product shipping at its own subdomain. Doesn't try to
 * replicate the main deliverome.org SiteShell (funder strip, nav
 * dropdowns) — this site has one purpose and a small surface.
 */
export function Shell({ children }: ShellProps) {
  return (
    <div className={styles.shell}>
      <a className={styles.skipLink} href="#main-content">
        Skip to main content
      </a>
      <header className={styles.header}>
        <div className={styles.headerInner}>
          <Link href="/" className={styles.brand}>
            <span className={styles.brandMark} aria-hidden="true" />
            <span className={styles.brandText}>Surfaceome</span>
          </Link>
          <nav className={styles.nav} aria-label="Primary">
            <Link className={styles.navLink} href="/benchmark">
              SurfaceBench
            </Link>
            <Link className={styles.navLink} href="/api">
              API
            </Link>
            <Link className={styles.navLink} href="/prompts">
              Prompts
            </Link>
            <a
              className={styles.navLink}
              href="https://deliverome.org/"
              target="_blank"
              rel="noopener noreferrer"
            >
              Deliverome ↗
            </a>
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
          <p className={styles.footerCopy}>
            A working atlas of cell-surface proteins. Schema, evidence, and
            agents shipped from{" "}
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
            <span aria-hidden="true" className={styles.metaSep}>
              ·
            </span>
            <a href="mailto:contact@deliverome.org" className={styles.footerLink}>
              contact@deliverome.org
            </a>
          </p>
        </div>
      </footer>
    </div>
  );
}
