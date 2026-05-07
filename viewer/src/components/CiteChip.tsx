// Phase-1 stub: shows a citation-count chip with a +/− toggle. Drilling into
// inline evidence is a no-op for now (we render a placeholder line). The full
// EvidenceInline + SourceDrawer port lands when M3 source corpus persistence
// is in place.

interface Props {
  ids: string[];
  expanded: boolean;
  onToggle: () => void;
  label?: string;
}

export function CiteChip({ ids, expanded, onToggle, label }: Props) {
  if (!ids?.length) return null;
  return (
    <button
      type="button"
      className={"cite" + (expanded ? " cite-active" : "")}
      onClick={onToggle}
      aria-expanded={expanded}
      aria-label={`${ids.length} citation${ids.length === 1 ? "" : "s"}${label ? ` for ${label}` : ""}`}
    >
      {ids.length} {expanded ? "−" : "+"}
    </button>
  );
}

export function EvidenceStub() {
  return (
    <div className="evidence-stub">
      Source detail lands with the M3 evidence corpus — see{" "}
      <em>Raw record</em> for the cited evidence ids.
    </div>
  );
}
