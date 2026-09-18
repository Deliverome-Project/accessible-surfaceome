"use client";
import { CONTACT_COLORS, contactContext } from "../../../lib/contact-sites";
import type { ContactSite } from "../../../lib/contact-sites";
import styles from "./StructureViewerCard.module.css";

export function ContactSites({ sites, selected, onSelect, source, onSource, ecOnly, onEcOnly, status, onRetry }: {
  sites: ContactSite[]; selected: number; onSelect: (index: number) => void;
  source: string; onSource: (source: string) => void; ecOnly: boolean;
  onEcOnly: (value: boolean) => void; status: string; onRetry: () => void;
}) {
  const filtered = sites.filter(s => (!ecOnly || s.context.startsWith("extracellular_")) && (!source || s.source === source));
  const site = filtered[selected];
  return <section className={styles.contactPanel} aria-label="Contact-site evidence">
    <div className={styles.contactFilters}>
      <label>Source <select value={source} onChange={e => onSource(e.target.value)}>
        <option value="">All sources</option>
        {Array.from(new Set(sites.map(s => s.source))).sort().map(s => <option key={s}>{s}</option>)}
      </select></label>
      <label><input type="checkbox" checked={ecOnly} onChange={e => onEcOnly(e.target.checked)} /> Extracellular only</label>
    </div>
    {status === "loading" ? <p role="status">Loading contact evidence…</p> : status === "error" ?
      <p role="alert">Contact evidence could not be loaded. <button onClick={onRetry}>Retry</button></p> : status === "unaudited" ?
      <p>This protein has no unambiguous mapping in this audit.</p> : !site ?
      <p>No mapped sites in this audit match these filters. This does not establish absence of binders.</p> : <>
      <div className={styles.contactSlider}>
        <button aria-label="Previous contact site" disabled={selected === 0} onClick={() => onSelect(selected - 1)}>←</button>
        <input type="range" aria-label="Contact site" min={0} max={Math.max(0, filtered.length - 1)} value={selected}
          aria-valuetext={`${selected + 1} of ${filtered.length}: ${site.source}, ${site.partner}`}
          disabled={filtered.length === 1} onChange={e => onSelect(Number(e.target.value))}
          style={{ accentColor: CONTACT_COLORS[site.source] }} />
        <button aria-label="Next contact site" disabled={selected === filtered.length - 1} onClick={() => onSelect(selected + 1)}>→</button>
        <span>{selected + 1} / {filtered.length}</span>
      </div>
      <div aria-live="polite">
        <strong style={{ color: CONTACT_COLORS[site.source] }}>● {site.source}</strong> · {site.partner}<br />
        {contactContext(site.context)} · {site.positions.length} residues · {site.evidence}
        <p>{site.confidence}. Contacts are projected onto the canonical AlphaFold model; this is not a model of the bound complex.</p>
        {site.pdb && <a href={`https://www.rcsb.org/structure/${site.pdb}`} target="_blank" rel="noreferrer">PDB {site.pdb.toUpperCase()} ↗</a>}
        {site.reference && <> · <a href={site.reference} target="_blank" rel="noreferrer">Evidence ↗</a></>}
        <details><summary>Canonical residue positions</summary><p className={styles.contactResidues}>{site.positions.join(", ")}</p></details>
      </div>
    </>}
    <p className={styles.contactNote}>Audited contact and epitope evidence. SAbDab and BioLiP currently show one representative site per gene, not all known sites. Different sources or structures may describe the same interface. IntAct binding regions and mutation effects are excluded from this contact view. Source labels identify provenance, not confidence or therapeutic suitability. <a href="/data/contact-sites/manifest.json" target="_blank" rel="noreferrer">Snapshot provenance ↗</a></p>
  </section>;
}
