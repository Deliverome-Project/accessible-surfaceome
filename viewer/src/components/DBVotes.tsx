import type { DBComparison } from "../lib/types";

const SOURCES: (keyof DBComparison)[] = [
  "surfy", "cspa", "uniprot_query", "go", "hpa", "deeptmhmm", "compartments", "patent_handle",
];

export function DBVotes({ db }: { db: DBComparison }) {
  return (
    <>
      <div className="db-votes">
        {SOURCES.map((s) => (
          <div key={s} className={"db-vote " + (db[s] ? "yes" : "no")}>
            <span className="src">{String(s).replace(/_/g, " ")}</span>
            <span className="vote">{db[s] ? "Surface" : "Non-surface"}</span>
          </div>
        ))}
      </div>
      <div className="tally">
        <span className="n">{db.n_sources_voting_surface}</span>
        <span>of</span>
        <span className="n" style={{ fontSize: 18, color: "var(--fg-dim)" }}>{SOURCES.length}</span>
        <span>sources called surface</span>
      </div>
    </>
  );
}
