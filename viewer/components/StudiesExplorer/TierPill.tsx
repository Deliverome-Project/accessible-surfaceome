import { TIER_HELP, TIER_LABEL, type TierCode } from "../../lib/surface-proteomics";
import styles from "./TierPill.module.css";

/** Deep-dive tier chip, colored like the gene page's tier callout. */
export function TierPill({ tier, withTitle = true }: { tier: TierCode | "none"; withTitle?: boolean }) {
  return (
    <span className={`${styles.tier} ${styles[tier]}`} title={withTitle ? TIER_HELP[tier] : undefined}>
      {TIER_LABEL[tier]}
    </span>
  );
}
