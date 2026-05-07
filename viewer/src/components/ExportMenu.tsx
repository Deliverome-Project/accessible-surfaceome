import { useEffect, useMemo, useRef, useState } from "react";
import type { SurfaceomeRecord } from "../lib/types";
import { recordToMarkdown } from "../lib/markdownExport";

export function ExportMenu({ rec }: { rec: SurfaceomeRecord }) {
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState<string | null>(null);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function onDoc(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    function onKey(e: KeyboardEvent) { if (e.key === "Escape") setOpen(false); }
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const symbol = rec.gene.hgnc_symbol;
  const md = useMemo(() => recordToMarkdown(rec, [], {}), [rec]);
  const json = useMemo(() => JSON.stringify({ record: rec, evidence: [], sources: {} }, null, 2), [rec]);

  async function copyText(text: string, kind: string) {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(kind);
      setTimeout(() => setCopied(null), 1400);
    } catch {
      window.prompt("Copy with ⌘C / Ctrl+C", text);
    }
  }

  function download(text: string, ext: string, mime: string) {
    const blob = new Blob([text], { type: mime });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = symbol + "." + ext;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    setOpen(false);
  }

  function openRaw(fmt: "json" | "md") {
    const u = new URL(window.location.href);
    u.searchParams.set("format", fmt);
    window.open(u.toString(), "_blank", "noopener");
    setOpen(false);
  }

  return (
    <div className="export-menu" ref={ref}>
      <button
        className={"export-pill" + (open ? " open" : "")}
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="menu"
        aria-expanded={open}
      >
        <span className="dot" aria-hidden="true" />
        Export
        <span className="caret" aria-hidden="true">⌄</span>
      </button>
      {open && (
        <div className="export-pop" role="menu">
          <div className="export-section">
            <div className="export-label">Copy to clipboard</div>
            <button className="export-row" role="menuitem" onClick={() => copyText(md, "md")}>
              <span className="k">Markdown</span>
              <span className="v">{copied === "md" ? "Copied" : ".md"}</span>
            </button>
            <button className="export-row" role="menuitem" onClick={() => copyText(json, "json")}>
              <span className="k">JSON</span>
              <span className="v">{copied === "json" ? "Copied" : ".json"}</span>
            </button>
          </div>
          <div className="export-section">
            <div className="export-label">Download</div>
            <button className="export-row" role="menuitem" onClick={() => download(md, "md", "text/markdown")}>
              <span className="k">{symbol}.md</span>
              <span className="v">Markdown</span>
            </button>
            <button className="export-row" role="menuitem" onClick={() => download(json, "json", "application/json")}>
              <span className="k">{symbol}.json</span>
              <span className="v">JSON</span>
            </button>
          </div>
          <div className="export-section">
            <div className="export-label">For agents</div>
            <button className="export-row" role="menuitem" onClick={() => openRaw("md")}>
              <span className="k">Open raw Markdown</span>
              <span className="v mono">?format=md</span>
            </button>
            <button className="export-row" role="menuitem" onClick={() => openRaw("json")}>
              <span className="k">Open raw JSON</span>
              <span className="v mono">?format=json</span>
            </button>
          </div>
          <div className="export-foot">
            Static URLs — drop into <code>curl</code> or fetch from an LLM.
          </div>
        </div>
      )}
    </div>
  );
}
