import { TIER_HELP, TIER_LABEL, type TierCode } from "../../lib/surface-proteomics";
import { HoverTip } from "../surfaceome/_shared/HoverTip";
import styles from "./TierPill.module.css";

/** Deep-dive tier chip, colored like the gene page's tier callout. */
export function TierPill({ tier, withTitle = true }: { tier: TierCode | "none"; withTitle?: boolean }) {
  const pill = <span className={`${styles.tier} ${styles[tier]}`}>{TIER_LABEL[tier]}</span>;
  return withTitle ? <HoverTip tip={TIER_HELP[tier]}>{pill}</HoverTip> : pill;
}
