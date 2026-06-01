import type { SearchEntry } from "../../../lib/surfaceome-types";
import { prettyEnum } from "../../../lib/surfaceome";
import { InfoTip } from "../../InfoTip/InfoTip";
import { StatusPill } from "../StatusPill/StatusPill";
import styles from "./SearchChips.module.css";

/**
 * SearchChips — a compact "Searches run" strip summarizing the agent
 * searches that produced a card's evidence. One chip per (tool, mode),
 * labeled with the search type + how many times it ran, tinted by whether
 * it's a DETERMINISTIC sweep (fixed per-gene query) or an LLM-PLANNED
 * search (a topic query the agent chose). Hover a chip for the agent's
 * own `intent` text on the first such search.
 *
 * Routed by `agent_focus`: A1 searches feed §Surface evidence, A2 feed
 * §Biological context — each card renders only its own focus's chips.
 */

/** Deterministic = fixed sweeps that run per gene regardless of what the
 *  LLM planned: the baseline NCBI pulls + every evidence_retrieval assay
 *  category. Everything else (topic_search, fetch_*) is LLM-planned. */
const DETERMINISTIC_LIT_MODES = new Set(["gene2pubmed", "recent_corpus"]);

/** Reader-facing labels for the search modes — prettyEnum mangles the
 *  assay acronyms ("Ihc", "If", "Ecd", "Gene2pubmed"), so spell the known
 *  ones out. Unknown modes fall back to prettyEnum. */
const MODE_LABELS: Record<string, string> = {
  flow_cytometry: "Flow cytometry",
  if: "Immunofluorescence",
  ihc: "Immunohistochemistry",
  mass_spec_surfaceome: "Mass-spec surfaceome",
  surface_biotinylation: "Surface biotinylation",
  western_blot_paired: "Western blot (paired)",
  structure_with_ecd: "Structure (ECD)",
  other: "Other assay",
  gene2pubmed: "NCBI gene2pubmed",
  recent_corpus: "Recent corpus",
  topic_search: "Topic search",
  fetch_abstract: "Fetch abstract",
  fetch_fulltext: "Fetch full text",
};

function modeLabel(e: SearchEntry): string {
  if (e.mode && MODE_LABELS[e.mode]) return MODE_LABELS[e.mode];
  return prettyEnum(e.mode || e.tool);
}

function isDeterministic(e: SearchEntry): boolean {
  if (e.tool === "evidence_retrieval") return true;
  if (e.tool === "gene_literature" && e.mode) {
    return DETERMINISTIC_LIT_MODES.has(e.mode);
  }
  return false;
}

interface ModeGroup {
  key: string;
  label: string;
  count: number;
  deterministic: boolean;
  /** First non-empty agent `intent` across the grouped searches — shown on
   *  hover so the reader sees WHY this search ran. */
  intent: string | null;
  totalResults: number;
}

/** Collapse a focus's searches into one group per (tool, mode), preserving
 *  a stable display order: deterministic sweeps first (they're the
 *  "what always runs" baseline), then LLM-planned, each alphabetized. */
function groupByMode(entries: SearchEntry[]): ModeGroup[] {
  const map = new Map<string, ModeGroup>();
  for (const e of entries) {
    const key = `${e.tool}:${e.mode ?? ""}`;
    const intent =
      typeof e.query?.intent === "string" ? (e.query.intent as string) : null;
    const existing = map.get(key);
    if (existing) {
      existing.count += 1;
      existing.totalResults += e.n_results ?? 0;
      if (!existing.intent && intent) existing.intent = intent;
    } else {
      map.set(key, {
        key,
        label: modeLabel(e),
        count: 1,
        deterministic: isDeterministic(e),
        intent,
        totalResults: e.n_results ?? 0,
      });
    }
  }
  return [...map.values()].sort((a, b) => {
    if (a.deterministic !== b.deterministic) return a.deterministic ? -1 : 1;
    return a.label.localeCompare(b.label);
  });
}

interface Props {
  searchLog: SearchEntry[];
  /** Which agent's searches to show — "a1" feeds Surface evidence, "a2"
   *  feeds Biological context. */
  focus: "a1" | "a2";
}

export function SearchChips({ searchLog, focus }: Props) {
  const mine = searchLog.filter((e) => e.query?.agent_focus === focus);
  if (mine.length === 0) return null;
  const groups = groupByMode(mine);
  const nDet = groups.filter((g) => g.deterministic).length;

  return (
    <div className={styles.wrap}>
      <span className={`label-mono ${styles.label}`}>
        Searches run
        <InfoTip>
          The searches the deep-dive agent ran to build this section.{" "}
          <strong>Deterministic</strong> sweeps (teal) are fixed queries that
          run for every gene — the baseline NCBI pulls and one query per assay
          category (flow cytometry, IHC, surface biotinylation, mass-spec
          surfaceome, …). <strong>LLM-planned</strong> searches (neutral) are
          topic queries the agent chose. Each chip shows how many times that
          search ran; hover for the agent&apos;s stated intent.
        </InfoTip>
      </span>
      <span className={styles.chips}>
        {groups.map((g) => (
          <StatusPill
            key={g.key}
            tone={g.deterministic ? "teal" : "neutral"}
            size="sm"
            title={
              g.intent
                ? `${g.deterministic ? "Deterministic sweep" : "LLM-planned"} · ${g.intent}`
                : g.deterministic
                  ? "Deterministic sweep — runs for every gene"
                  : "LLM-planned search"
            }
          >
            {g.label} · {g.count}
          </StatusPill>
        ))}
      </span>
      {nDet > 0 ? (
        <span className={styles.legend}>
          {nDet} deterministic sweep{nDet === 1 ? "" : "s"} ·{" "}
          {groups.length - nDet} LLM-planned
        </span>
      ) : null}
    </div>
  );
}
