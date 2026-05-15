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
              className={styles.navLink}
              href="https://github.com/Deliverome-Project/accessible-surfaceome"
              target="_blank"
              rel="noopener noreferrer"
            >
              GitHub ↗
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
