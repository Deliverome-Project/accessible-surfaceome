"use client";

import {
  Children,
  cloneElement,
  isValidElement,
  useEffect,
  useRef,
  type CSSProperties,
  type ReactNode,
} from "react";

/**
 * Reveal — IntersectionObserver scroll-fade wrapper. Ported from
 * the deliverome-internal `site/` design system (PR #24). Two modes:
 *
 *  - Default: the wrapper itself fades in.
 *  - `stagger`: the wrapper stays visible and each direct child
 *    fades up in sequence, gated by `--reveal-i` (set per child)
 *    + `--reveal-step` (set on the wrapper, default 90ms).
 *
 * Reduced-motion users skip all animation via the CSS rule in
 * `app/globals.css`.
 */

type RevealTag =
  | "section"
  | "div"
  | "article"
  | "ul"
  | "ol"
  | "header"
  | "footer"
  | "main";

interface RevealProps {
  children: ReactNode;
  as?: RevealTag;
  className?: string;
  id?: string;
  stagger?: boolean;
  stagger_ms?: number;
  threshold?: number;
  rootMargin?: string;
  delay?: number;
  style?: CSSProperties;
}

export function Reveal({
  children,
  as = "div",
  className = "",
  id,
  stagger = false,
  stagger_ms = 90,
  threshold = 0.12,
  rootMargin = "0px 0px -10% 0px",
  delay = 0,
  style,
}: RevealProps) {
  const ref = useRef<HTMLElement | null>(null);

  useEffect(() => {
    const node = ref.current;
    if (!node) return;

    if (typeof window === "undefined" || !("IntersectionObserver" in window)) {
      node.classList.add("is-visible");
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            window.setTimeout(() => entry.target.classList.add("is-visible"), delay);
            observer.unobserve(entry.target);
          }
        }
      },
      { rootMargin, threshold },
    );

    observer.observe(node);
    return () => observer.disconnect();
  }, [delay, rootMargin, threshold]);

  const Tag = as as "section";

  if (stagger) {
    const staggered = Children.map(children, (child, index) => {
      if (!isValidElement(child)) return child;
      const childProps = child.props as { style?: CSSProperties };
      const mergedStyle: CSSProperties = {
        ...(childProps.style ?? {}),
        ["--reveal-i" as never]: index,
      };
      return cloneElement(child, { style: mergedStyle } as Partial<typeof childProps>);
    });

    return (
      <Tag
        ref={ref as React.RefObject<HTMLElement>}
        className={`reveal ${className}`.trim()}
        id={id}
        data-reveal-stagger="true"
        style={{
          ...(style ?? {}),
          ["--reveal-step" as never]: `${stagger_ms}ms`,
        }}
      >
        {staggered}
      </Tag>
    );
  }

  return (
    <Tag
      ref={ref as React.RefObject<HTMLElement>}
      className={`reveal ${className}`.trim()}
      id={id}
      style={style}
    >
      {children}
    </Tag>
  );
}
