import type { ReactNode } from "react";
import tip from "../../InfoTip/InfoTip.module.css";

/**
 * Wraps any element so hovering or focusing it shows the site's styled
 * InfoTip popover, instead of the browser's native `title=` bubble (delayed,
 * unstyled, not theme-aware). Uses the same CSS and auto-placer as InfoTip.
 */
export function HoverTip({ tip: body, children }: { tip: ReactNode; children: ReactNode }) {
  return (
    <span className={tip.wrap} data-infotip="">
      {children}
      <span role="tooltip" className={tip.popover}>
        {body}
      </span>
    </span>
  );
}
