/*
 * Tiny TSV builder + browser download trigger.
 *
 * TSV (not CSV) on purpose: gene symbols, UniProt accessions, and
 * controlled-vocabulary verdicts don't contain tabs or newlines, so we
 * dodge CSV's quoting rules entirely. Any cell that *does* contain a
 * tab or newline (rare — a free-text reason field, maybe) gets its
 * whitespace collapsed to a single space rather than escaped.
 */

export type TsvCell = string | number | boolean | null | undefined;

function scrub(cell: TsvCell): string {
  if (cell == null) return "";
  const s = String(cell);
  // Collapse \t / \r / \n so the row stays on one line. Anything else
  // is fine — TSV doesn't quote, doesn't need to escape commas, etc.
  return s.replace(/[\t\r\n]+/g, " ");
}

export function buildTsv(headers: string[], rows: TsvCell[][]): string {
  const head = headers.map(scrub).join("\t");
  const body = rows.map((r) => r.map(scrub).join("\t")).join("\n");
  return `${head}\n${body}\n`;
}

/**
 * Browser-only — triggers a file download via a temporary anchor.
 * Safe to call from a client component event handler; should never
 * run during SSR.
 */
export function downloadTextFile(
  filename: string,
  content: string,
  mime = "text/tab-separated-values",
): void {
  if (typeof window === "undefined") return;
  const blob = new Blob([content], { type: `${mime};charset=utf-8` });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.style.display = "none";
  document.body.appendChild(a);
  a.click();
  a.remove();
  // Defer revoke so Safari has time to start the download.
  setTimeout(() => URL.revokeObjectURL(url), 4_000);
}
