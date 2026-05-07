import type { Modality } from "../lib/types";
import { prettyEnum } from "../lib/formatPretty";

export function Modalities({ list }: { list: Modality[] }) {
  return (
    <div className="modality-list">
      {list.map((m, i) => {
        const kindClass = m.kind === "not_recommended" ? "not_recommended" : i === 0 ? "recommended" : "alternate";
        const name = m.kind_other_label ? prettyEnum(m.kind_other_label) : prettyEnum(m.kind);
        const flag = kindClass === "recommended" ? "Primary" : kindClass === "alternate" ? "Alternate" : "Not viable";
        return (
          <div key={i} className={"modality kind-" + kindClass}>
            <div className="rank">{String(i + 1).padStart(2, "0")}</div>
            <div>
              <div className="name">{name}</div>
              <div className="rationale">{m.rationale}</div>
            </div>
            <div className="recommend-flag">{flag}</div>
          </div>
        );
      })}
    </div>
  );
}
