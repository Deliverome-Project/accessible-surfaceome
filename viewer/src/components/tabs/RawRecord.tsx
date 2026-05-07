import type { SurfaceomeRecord } from "../../lib/types";
import { highlightJSON } from "../../lib/highlightJson";

export function RawRecordTab({ rec }: { rec: SurfaceomeRecord }) {
  return (
    <div className="card" style={{ marginTop: 24 }}>
      <header>
        <h2><span className="num">02</span>Raw record</h2>
        <span className="header-meta">JSON · {rec.schema_version}</span>
      </header>
      <pre className="json-viewer" dangerouslySetInnerHTML={{ __html: highlightJSON(rec) }} />
    </div>
  );
}
