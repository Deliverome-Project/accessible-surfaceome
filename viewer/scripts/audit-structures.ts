#!/usr/bin/env -S npx --yes tsx
/**
 * Cohort audit of the gene page's 3D structure: for every published
 * deep-dive gene, run the structure viewer's own selection and loading
 * code against the live PDBe / RCSB / AlphaFold DB services and report
 * every gene whose structure would fail to load.
 *
 * ## Why this exists
 *
 * The viewer picks a gene's experimental structure at page-view time from
 * PDBe `best_structures`, so the pick changes whenever a new structure is
 * deposited — no rebuild, no record change, nothing in CI. 9V8W (SLC6A8)
 * shipped broken because RCSB publishes no `.pdb` for it, and it was 1 of
 * 168 genes in that state before anyone noticed. A weekly run of this
 * script (`.github/workflows/structure-audit.yml`) catches the next one,
 * and its diff against the previous run lists genes that gained or
 * changed a structure.
 *
 * ## What counts as a failure
 *
 * Experimental tab (`lib/experimental-structure.ts`, the same functions
 * the viewer calls):
 *   - no RCSB format loads (`fetchExperimentalPdb` throws);
 *   - the mapped chain isn't in the loaded file (`pickPdbChain` returns
 *     null or falls back to a different chain — the topology colours the
 *     wrong chain);
 *   - none of the chain's UniProt-mapped residues land on atoms under the
 *     viewer's projection (`projectExperimentalChain`, SIFTS fallback
 *     included), so topology colouring would come out blank.
 * Canonical AlphaFold tab:
 *   - AFDB's first prediction entry (the one the viewer renders) is an
 *     isoform while a canonical model exists.
 *   Model files themselves aren't downloaded: AFDB's file host rate-
 *   limits a client to far below cohort scale (it 429'd within minutes
 *   of the first full run), and the viewer already re-resolves a stale
 *   model URL through the prediction API.
 * Not failures: no PDB structure at all, or no AFDB canonical model —
 * the viewer shows an honest empty state for both. A service that keeps
 * erroring after retries is counted as `error`; the run fails if errors
 * exceed 1% of genes (an outage, not a gene problem).
 *
 * Requests are paced per host (PDBe, AFDB, RCSB each get their own
 * budget, see HOST_RATE) so the weekly run stays a polite client of
 * three public services.
 *
 * ## Usage
 *
 *   cd viewer
 *   npx --yes tsx scripts/audit-structures.ts [--out DIR] [--previous TSV]
 *       [--genes A,B] [--concurrency N]
 *
 * Writes `DIR/structure_audit.tsv` (one row per gene) and
 * `DIR/structure_audit_summary.md`; exits 1 on any failure.
 */
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import {
  fetchCanonicalSequence,
  fetchExperimentalPdb,
  isCleanStructure,
  MIN_IDENTITY,
  observedResSeq,
  pickBestStructure,
  pickPdbChain,
  projectedCoverage,
  projectedIdentity,
  projectExperimentalChain,
  residueOneLetterByResSeq,
  type PDBeBestStructure,
} from "../lib/experimental-structure";
import {
  alphafoldPredictionApiUrl,
  type AlphafoldPredictionEntry,
} from "../lib/structure-viewer-types";

const API_BASE = (
  process.env.SURFACEOME_API_BASE ?? "https://api.deliverome.org/surfaceome"
).replace(/\/+$/, "");
const USER_AGENT =
  "accessible-surfaceome structure audit (https://github.com/Deliverome-Project/accessible-surfaceome)";

function arg(name: string): string | undefined {
  const i = process.argv.indexOf(`--${name}`);
  return i >= 0 ? process.argv[i + 1] : undefined;
}
const OUT_DIR = arg("out") ?? "structure-audit";
const PREVIOUS = arg("previous");
const ONLY_GENES = arg("genes")?.split(",").map((g) => g.trim().toUpperCase());
const CONCURRENCY = Number(arg("concurrency") ?? 8);

/** Max request starts per second, per host. */
const HOST_RATE: Record<string, number> = {
  "www.ebi.ac.uk": 5,
  "alphafold.ebi.ac.uk": 3,
  "files.rcsb.org": 5,
  "data.rcsb.org": 5,
  "models.rcsb.org": 2,
};
const DEFAULT_RATE = 2;
const nextSlot = new Map<string, number>();

/** Wait for this host's next request slot. Slots are handed out in call
 *  order, so concurrent workers queue rather than burst. */
async function throttle(host: string): Promise<void> {
  const interval = 1000 / (HOST_RATE[host] ?? DEFAULT_RATE);
  const now = Date.now();
  const slot = Math.max(now, nextSlot.get(host) ?? 0);
  nextSlot.set(host, slot + interval);
  if (slot > now) await sleep(slot - now);
}

/** Thrown when a service keeps failing after retries — an outage, not a
 *  property of the gene. */
class ServiceError extends Error {}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

/** fetch with an identifiable User-Agent (AFDB 403s Node's default one),
 *  paced per host, retrying 429 / 5xx / network errors with backoff and
 *  honouring Retry-After. A 404 is an answer, not a transient. */
const auditFetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
  const headers = new Headers(init?.headers);
  headers.set("User-Agent", USER_AGENT);
  const host = new URL(String(input)).host;
  let last = "";
  let wait = 0;
  for (let attempt = 0; attempt < 5; attempt += 1) {
    if (attempt > 0) await sleep(Math.max(wait, 2000 * 2 ** (attempt - 1)));
    await throttle(host);
    try {
      const r = await fetch(input, { ...init, headers });
      if (r.status !== 429 && r.status < 500) return r;
      last = `HTTP ${r.status}`;
      wait = Number(r.headers.get("retry-after") ?? 0) * 1000;
      await r.body?.cancel();
    } catch (e) {
      last = (e as Error).message;
    }
  }
  throw new ServiceError(`${String(input)}: ${last}`);
}) as typeof fetch;

/** Below this many comparable residues the identity figure is noise —
 *  a short peptide chain can match by luck. Reported, never judged. */
const MIN_TESTED = 20;

interface Gene {
  gene_symbol: string;
  uniprot_acc: string;
}

interface Row {
  gene_symbol: string;
  uniprot_acc: string;
  pdb_id: string;
  chain_id: string;
  /** pdb | cif | cif_chain_only — which RCSB path loaded it. */
  source: string;
  /** ok | fail | misregistered | no_structure | error */
  exp_status: string;
  /** Percent of the projected residues that are the right amino acid.
   *  Blank when no canonical sequence was reachable. A structure can
   *  load perfectly and still be numbered wrong, which is what this
   *  catches: coverage says a projection lands on atoms, identity says
   *  it lands on the RIGHT atoms. */
  identity_pct: string;
  /** ok | fail | none | isoform_only | error */
  afdb_status: string;
  detail: string;
}

async function auditExperimental(g: Gene, row: Row): Promise<void> {
  const r = await auditFetch(
    `https://www.ebi.ac.uk/pdbe/api/mappings/best_structures/${g.uniprot_acc}`,
  );
  if (!r.ok) {
    await r.body?.cancel();
    row.exp_status = "no_structure";
    return;
  }
  const j = (await r.json()) as Record<string, PDBeBestStructure[]>;
  const pick = pickBestStructure(j[g.uniprot_acc] ?? []);
  if (!pick) {
    row.exp_status = "no_structure";
    return;
  }
  row.pdb_id = pick.pdb_id.toUpperCase();
  row.chain_id = pick.chain_id;
  let exp;
  try {
    exp = await fetchExperimentalPdb(pick.pdb_id, pick.chain_id, auditFetch);
  } catch (e) {
    if (e instanceof ServiceError) throw e;
    row.exp_status = "fail";
    row.detail = (e as Error).message;
    return;
  }
  row.source = exp.source;
  const chain = pickPdbChain(exp.rawPdb, exp.chainId);
  if (chain !== exp.chainId) {
    row.exp_status = "fail";
    row.detail = chain
      ? `chain ${pick.chain_id} not in file; viewer falls back to ${chain}`
      : "file has no atoms";
    return;
  }
  // The viewer's UniProt→author projection, SIFTS fallback included.
  const observed = observedResSeq(exp.rawPdb, chain);
  const segments = await projectExperimentalChain(
    {
      pdbId: pick.pdb_id,
      uniprotAcc: g.uniprot_acc,
      chainId: pick.chain_id,
      unpStart: pick.unp_start,
      unpEnd: pick.unp_end,
      pdbStart: pick.start,
      approx: !isCleanStructure(pick),
    },
    exp.rawPdb,
    chain,
    auditFetch,
  );
  if (projectedCoverage(segments, observed) === 0) {
    row.exp_status = "fail";
    row.detail = "no UniProt-mapped residue lands on an atom";
    return;
  }
  // Loading is not the same as being numbered right. Compare the amino
  // acids: the residue at author `u + offset` has to BE the UniProt
  // residue at `u`. A wrong offset still covers every residue and still
  // renders — it just renders the wrong ones, and it moves the
  // compartment colours and the membrane slab with it.
  const canonicalSeq = await fetchCanonicalSequence(g.uniprot_acc, auditFetch);
  if (canonicalSeq) {
    const { matches, tested } = projectedIdentity(segments, {
      seq: canonicalSeq,
      resNames: residueOneLetterByResSeq(exp.rawPdb, chain),
    });
    if (tested >= MIN_TESTED) {
      const frac = matches / tested;
      row.identity_pct = (frac * 100).toFixed(1);
      if (frac < MIN_IDENTITY) {
        row.exp_status = "misregistered";
        row.detail = appendDetail(
          row.detail,
          `projection puts ${matches}/${tested} residues on the right amino acid`,
        );
        return;
      }
    }
  }
  row.exp_status = "ok";
}

async function auditAfdb(g: Gene, row: Row): Promise<void> {
  const r = await auditFetch(alphafoldPredictionApiUrl(g.uniprot_acc));
  if (!r.ok) {
    await r.body?.cancel();
    row.afdb_status = "none";
    return;
  }
  const entries = (await r.json()) as Array<
    AlphafoldPredictionEntry & { uniprotAccession?: string }
  >;
  if (!Array.isArray(entries) || entries.length === 0) {
    row.afdb_status = "none";
    return;
  }
  // Same availability rule as the viewer's mount probe.
  if (!entries.some((e) => e.uniprotAccession === g.uniprot_acc)) {
    row.afdb_status = "isoform_only";
    return;
  }
  // The viewer renders entries[0] on the canonical tab.
  if (entries[0].uniprotAccession !== g.uniprot_acc) {
    row.afdb_status = "fail";
    row.detail = appendDetail(
      row.detail,
      `AFDB entry 0 is ${entries[0].uniprotAccession}, not the canonical model`,
    );
    return;
  }
  row.afdb_status = "ok";
}

function appendDetail(a: string, b: string): string {
  return a ? `${a}; ${b}` : b;
}

async function auditGene(g: Gene): Promise<Row> {
  const row: Row = {
    gene_symbol: g.gene_symbol,
    uniprot_acc: g.uniprot_acc,
    pdb_id: "",
    chain_id: "",
    source: "",
    exp_status: "",
    identity_pct: "",
    afdb_status: "",
    detail: "",
  };
  // The two lanes hit different hosts, so run them side by side.
  await Promise.all(
    ([
      ["exp", auditExperimental],
      ["afdb", auditAfdb],
    ] as const).map(async ([part, run]) => {
      try {
        await run(g, row);
      } catch (e) {
        if (part === "exp") row.exp_status = "error";
        else row.afdb_status = "error";
        row.detail = appendDetail(row.detail, (e as Error).message);
      }
    }),
  );
  return row;
}

const COLUMNS: (keyof Row)[] = [
  "gene_symbol", "uniprot_acc", "pdb_id", "chain_id", "source",
  "exp_status", "identity_pct", "afdb_status", "detail",
];

function toTsv(rows: Row[]): string {
  const clean = (v: string) => v.replace(/[\t\n]/g, " ");
  return [
    COLUMNS.join("\t"),
    ...rows.map((r) => COLUMNS.map((c) => clean(r[c])).join("\t")),
  ].join("\n") + "\n";
}

function readPrevious(path: string): Map<string, Row> {
  const [header, ...lines] = readFileSync(path, "utf8").trim().split("\n");
  const cols = header.split("\t");
  const out = new Map<string, Row>();
  for (const line of lines) {
    const v = line.split("\t");
    const r = Object.fromEntries(cols.map((c, i) => [c, v[i] ?? ""])) as unknown as Row;
    out.set(r.gene_symbol, r);
  }
  return out;
}

async function main() {
  const listResp = await auditFetch(`${API_BASE}/v1/genes`);
  if (!listResp.ok) throw new Error(`/v1/genes returned ${listResp.status}`);
  let genes = ((await listResp.json()) as { genes: Gene[] }).genes;
  if (ONLY_GENES) {
    genes = genes.filter((g) => ONLY_GENES.includes(g.gene_symbol.toUpperCase()));
  }
  console.log(`auditing ${genes.length} genes, concurrency ${CONCURRENCY}`);

  const rows: Row[] = new Array(genes.length);
  let next = 0;
  let done = 0;
  await Promise.all(
    Array.from({ length: CONCURRENCY }, async () => {
      while (next < genes.length) {
        const i = next++;
        rows[i] = await auditGene(genes[i]);
        done += 1;
        if (done % 250 === 0) console.log(`  ${done}/${genes.length}`);
      }
    }),
  );
  rows.sort((a, b) => a.gene_symbol.localeCompare(b.gene_symbol));

  const count = (k: keyof Row, v: string) => rows.filter((r) => r[k] === v).length;
  const failures = rows.filter((r) => r.exp_status === "fail" || r.afdb_status === "fail");
  const misregistered = rows.filter((r) => r.exp_status === "misregistered");
  const scored = rows.filter((r) => r.identity_pct !== "");
  const errors = rows.filter((r) => r.exp_status === "error" || r.afdb_status === "error");
  const nothing = rows.filter(
    (r) => r.exp_status === "no_structure" && r.afdb_status !== "ok",
  );
  const withExp = rows.filter((r) => r.pdb_id);

  const md: string[] = [
    `# Structure audit — ${new Date().toISOString().slice(0, 10)}`,
    "",
    `${rows.length} genes. Experimental: ${withExp.length} with a PDB pick ` +
      `(${count("source", "pdb")} .pdb, ${count("source", "cif")} mmCIF, ` +
      `${count("source", "cif_chain_only")} mmCIF chain-only), ` +
      `${count("exp_status", "no_structure")} with none. ` +
      `AlphaFold canonical: ${count("afdb_status", "ok")} ok, ` +
      `${count("afdb_status", "none")} no model, ` +
      `${count("afdb_status", "isoform_only")} isoform-only.`,
    "",
    `**${failures.length} failing, ${misregistered.length} misregistered, ` +
      `${errors.length} service errors.** ` +
      `${nothing.length} genes show no 3D structure (no PDB entry and no AFDB canonical model).`,
    "",
    `Numbering was checked against the canonical sequence for ${scored.length} ` +
      `of the ${withExp.length} genes with a PDB pick. "Misregistered" means the ` +
      `structure loads and covers the mapping, but the residues it puts at those ` +
      `numbers are not this protein's — so the highlighted residue, the ` +
      `compartment colours and the membrane slab are all shifted.`,
  ];
  const list = (title: string, rs: Row[]) => {
    if (rs.length === 0) return;
    md.push("", `## ${title}`, "",
      "| gene | PDB | chain | exp | identity | afdb | detail |", "|---|---|---|---|---|---|---|");
    for (const r of rs) {
      md.push(`| ${r.gene_symbol} | ${r.pdb_id} | ${r.chain_id} | ${r.exp_status} | ` +
        `${r.identity_pct ? `${r.identity_pct}%` : "—"} | ${r.afdb_status} | ${r.detail} |`);
    }
  };
  list("Misregistered — loads, but numbered wrong", misregistered);
  list("Failures", failures);
  list("Service errors", errors);

  if (PREVIOUS) {
    const prev = readPrevious(PREVIOUS);
    const gained = withExp.filter((r) => !prev.get(r.gene_symbol)?.pdb_id);
    const changed = withExp.filter((r) => {
      const p = prev.get(r.gene_symbol)?.pdb_id;
      return p && p !== r.pdb_id;
    });
    md.push("", "## Since the previous run", "",
      `${gained.length} genes gained an experimental structure, ` +
        `${changed.length} switched to a different one.`);
    for (const r of gained) md.push(`- ${r.gene_symbol}: new ${r.pdb_id} (${r.exp_status})`);
    for (const r of changed) {
      md.push(`- ${r.gene_symbol}: ${prev.get(r.gene_symbol)?.pdb_id} → ${r.pdb_id} (${r.exp_status})`);
    }
  }

  mkdirSync(OUT_DIR, { recursive: true });
  writeFileSync(join(OUT_DIR, "structure_audit.tsv"), toTsv(rows));
  writeFileSync(join(OUT_DIR, "structure_audit_summary.md"), md.join("\n") + "\n");
  console.log(md.join("\n"));

  const errorBudget = Math.floor(rows.length * 0.01);
  if (failures.length > 0 || misregistered.length > 0 || errors.length > errorBudget) {
    process.exit(1);
  }
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
