import type { ReactNode } from "react";
import { CiteChip, EvidenceStub } from "./CiteChip";

interface Props {
  // `k` accepts a ReactNode so callers can render a string + decorations
  // (e.g. <>UniProt acc <span className="tag">canonical</span></>).
  // CiteChip's aria-label uses `k` when it's a plain string; otherwise
  // pass `ariaLabel` for screen-reader text.
  k: ReactNode;
  ariaLabel?: string;
  children: ReactNode;
  ids?: string[];
  expanded?: boolean;
  onToggle?: () => void;
}

export function FieldRow({ k, ariaLabel, children, ids, expanded, onToggle }: Props) {
  const hasCites = !!ids?.length && !!onToggle;
  const citeLabel = typeof k === "string" ? k : ariaLabel;
  return (
    <div className="def-row field-row">
      <div className="k">{k}</div>
      <div className="v">
        <div className="field-value">
          <div className="field-content">{children}</div>
          {hasCites && (
            <CiteChip ids={ids!} expanded={!!expanded} onToggle={onToggle!} label={citeLabel} />
          )}
        </div>
        {hasCites && expanded && <EvidenceStub />}
      </div>
    </div>
  );
}
