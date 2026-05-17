"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import styles from "./Shell.module.css";

interface NavLinkProps {
  href: string;
  /** Optional extra class (e.g. styles.navIconLink for the GitHub icon). */
  extraClass?: string;
  /** Match by prefix (e.g. /benchmark/ should highlight when visiting
   *  any nested path like /benchmark/details). */
  matchPrefix?: boolean;
  children: ReactNode;
  /** Extra props for icon links (target=_blank, aria-label, etc.). */
  external?: boolean;
  ariaLabel?: string;
  title?: string;
}

/**
 * NavLink — Shell-internal client component that sets data-active=true
 * when the current pathname matches its href. Mirrors PR24's nav
 * pattern: the .navLink CSS handles the underline-on-hover-or-active
 * affordance, this component just tells it whether to draw the
 * underline as active.
 *
 * Stayed a small client component (vs converting the whole Shell)
 * because the Shell wraps every page and the bulk of its content
 * shouldn't re-render on route change.
 */
export function NavLink({
  href,
  extraClass,
  matchPrefix,
  external,
  ariaLabel,
  title,
  children,
}: NavLinkProps) {
  const pathname = usePathname();
  const active = isActive(href, pathname, matchPrefix);
  const cls = `${styles.navLink} ${extraClass ?? ""}`.trim();
  if (external) {
    return (
      <a
        className={cls}
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        aria-label={ariaLabel}
        title={title}
      >
        {children}
      </a>
    );
  }
  return (
    <Link
      className={cls}
      href={href}
      data-active={active || undefined}
      aria-current={active ? "page" : undefined}
    >
      {children}
    </Link>
  );
}

function isActive(
  href: string,
  pathname: string | null,
  matchPrefix?: boolean,
): boolean {
  if (!pathname) return false;
  if (matchPrefix) return pathname === href || pathname.startsWith(href);
  return pathname === href;
}
