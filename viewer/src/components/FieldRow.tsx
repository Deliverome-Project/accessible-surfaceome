import type { ReactNode } from "react";
import { CiteChip, EvidenceStub } from "./CiteChip";

interface Props {
  k: string;
  children: ReactNode;
  ids?: string[];
  expanded?: boolean;
  onToggle?: () => void;
}

export function FieldRow({ k, children, ids, expanded, onToggle }: Props) {
  const hasCites = !!ids?.length && !!onToggle;
  return (
    <div className="def-row field-row">
      <div className="k">{k}</div>
      <div className="v">
        <div className="field-value">
          <div className="field-content">{children}</div>
          {hasCites && (
            <CiteChip ids={ids!} expanded={!!expanded} onToggle={onToggle!} label={k} />
          )}
        </div>
        {hasCites && expanded && <EvidenceStub />}
      </div>
    </div>
  );
}
