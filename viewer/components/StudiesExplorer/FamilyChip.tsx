import type { StudyArm } from "../../lib/surface-proteomics";
import { StatusPill } from "../surfaceome/StatusPill/StatusPill";

type Tone = "teal" | "lavender" | "amber" | "maroon" | "neutral";

/** One tone per labeling chemistry; glycan chemistries share lavender. */
const TONE: Record<string, Tone> = {
  "biotin-amine": "teal",
  "glycoprotein-capture": "lavender",
  "glycopeptide-capture": "lavender",
  "peroxidase-proximity": "amber",
  "other-chemoproteomic": "maroon",
  "membrane-fractionation": "neutral",
};

/** Labeling chemistry (method family), as the viewer's standard status pill. */
export function FamilyChip({ arm }: { arm: Pick<StudyArm, "family" | "family_label"> }) {
  return (
    <StatusPill size="sm" tone={TONE[arm.family] ?? "neutral"}>
      {arm.family_label}
    </StatusPill>
  );
}
