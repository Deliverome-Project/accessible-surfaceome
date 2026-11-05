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
/** Short pill text where the full family name is too long for a table cell. */
const SHORT: Record<string, string> = {
  "other-chemoproteomic": "Other chemistry",
};

export function FamilyChip({ arm }: { arm: Pick<StudyArm, "family" | "family_label"> }) {
  const short = SHORT[arm.family];
  return (
    <StatusPill
      size="sm"
      tone={TONE[arm.family] ?? "neutral"}
      title={short ? arm.family_label : undefined}
    >
      {short ?? arm.family_label}
    </StatusPill>
  );
}
