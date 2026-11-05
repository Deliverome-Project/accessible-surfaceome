import type { StudyArm } from "../../lib/surface-proteomics";
import styles from "./FamilyChip.module.css";

/** Labeling chemistry (method family) chip, one colour per family. */
export function FamilyChip({ arm }: { arm: Pick<StudyArm, "family" | "family_label"> }) {
  const tone = styles[`fam_${arm.family.replace(/-/g, "_")}`] ?? styles.fam_other;
  return <span className={`${styles.chip} ${tone}`}>{arm.family_label}</span>;
}
