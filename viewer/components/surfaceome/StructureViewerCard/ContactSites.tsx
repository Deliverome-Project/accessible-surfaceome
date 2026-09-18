"use client";
import { CONTACT_COLORS, contactContext, filterContacts, browsingContacts, ligandOptions, namedLigand } from "../../../lib/contact-sites";
import { ContactProjections } from "./ContactProjections";
import type { ContactSite, ContactAtom, ContactGroup } from "../../../lib/contact-sites";
import styles from "./StructureViewerCard.module.css";

export function ContactSites({ sites, selected, onSelect, source, onSource, ecOnly, onEcOnly, status, onRetry, query, onQuery, grouped, onGrouped, atoms, visibleSites, compare, onCompare }: {
  atoms: ContactAtom[]; visibleSites: ContactGroup[]; compare: boolean; onCompare: (value: boolean) => void;
  grouped: boolean; onGrouped: (grouped: boolean) => void;
  query: string; onQuery: (query: string) => void;
  sites: ContactSite[]; selected: number; onSelect: (index: number) => void;
  source: string; onSource: (source: string) => void; ecOnly: boolean;
  onEcOnly: (value: boolean) => void; status: string; onRetry: () => void;
}) {
  const binderNames = ligandOptions(filterContacts(sites, source, ecOnly, ""));
  const records = filterContacts(sites, source, ecOnly, query);
  const filtered = browsingContacts(records, grouped, query);
  const site = filtered[selected];
  return <section className={styles.contactPanel} aria-label="Contact-site evidence">
    <div className={styles.contactFilters}>
      <label>Choose binder <select value={binderNames.includes(query) ? query : ""} onChange={e => onQuery(e.target.value)}>
        <option value="">All binders and ligands</option>
        {binderNames.map(name => <option key={name} value={name}>{name}</option>)}
      </select></label>
      <label>Search <input type="search" placeholder="Name or identifier" value={query} onChange={e => onQuery(e.target.value)} /></label>
      <label>Source <select value={source} onChange={e => onSource(e.target.value)}>
        <option value="">All sources</option>
        {Array.from(new Set(sites.map(s => s.source))).sort().map(s => <option key={s}>{s}</option>)}
      </select></label>
      <label><input type="checkbox" checked={compare} onChange={e => onCompare(e.target.checked)} /> Compare other binders separately</label>
      {query.trim() && <label><input type="checkbox" checked={grouped} onChange={e => onGrouped(e.target.checked)} /> Group similar sites</label>}
      <label><input type="checkbox" checked={ecOnly} onChange={e => onEcOnly(e.target.checked)} /> Extracellular only</label>
    </div>
    {status === "loading" ? <p role="status">Loading contact evidence…</p> : status === "error" ?
      <p role="alert">Contact evidence could not be loaded. <button onClick={onRetry}>Retry</button></p> : status === "unaudited" ?
      <p>This protein has no unambiguous mapping in this audit.</p> : !site ?
      <p>No mapped sites in this audit match these filters. This does not establish absence of binders.</p> : <>
      <div className={styles.contactSlider}>
        <button aria-label="Previous contact site" disabled={selected === 0} onClick={() => onSelect(selected - 1)}>←</button>
        <input type="range" aria-label="Contact site" min={0} max={Math.max(0, filtered.length - 1)} value={selected}
          aria-valuetext={`${selected + 1} of ${filtered.length}: ${site.source}, ${site.partner_label ?? site.partner}`}
          disabled={filtered.length === 1} onChange={e => onSelect(Number(e.target.value))}
          style={{ accentColor: CONTACT_COLORS[site.source] }} />
        <button aria-label="Next contact site" disabled={selected === filtered.length - 1} onClick={() => onSelect(selected + 1)}>→</button>
        <span className={styles.contactCounter}>{!query.trim() ? "Ligand" : grouped ? "Group" : "Record"} {selected + 1} of {filtered.length}</span>
      </div>
      <p><strong>{query.trim() ? `Matching “${query.trim()}”` : "All binders and ligands"}</strong> · {filtered.length} {!query.trim() ? "named ligands / binders" : grouped ? "similarity groups" : "records"} from {records.length} evidence records. These are not counts of distinct biological binding sites.</p>
      {!query.trim() && <p><button onClick={() => onQuery(site.partner_label ?? site.partner)}>Show contact groups for {site.partner_label ?? site.partner}</button> · One representative footprint per named ligand. {records.filter(s => !namedLigand(s)).length} unresolved identity records remain searchable by identifier.</p>}
      <ContactProjections atoms={atoms} sites={visibleSites} />
      <details className={styles.contactEvidence}><summary>Evidence for {site.partner_label ?? site.partner} · {site.source} · {site.supportingSites.length} supporting records</summary>
      <div>
        <strong style={{ color: CONTACT_COLORS[site.source] }}>● {site.source}</strong> · {site.partner_label ?? site.partner}{site.partner_label ? ` (${site.partner})` : ""}<br />
        {contactContext(site.context)} · {site.positions.length} residues · {site.evidence}
        <p>{site.confidence}. Contacts are projected onto the canonical AlphaFold model; this is not a model of the bound complex.</p>
        {site.pdb && <a href={`https://www.rcsb.org/structure/${site.pdb}`} target="_blank" rel="noreferrer">PDB {site.pdb.toUpperCase()} ↗</a>}
        {site.reference && <> · <a href={site.reference} target="_blank" rel="noreferrer">Evidence ↗</a></>}
        {site.supportingSites.length > 1 && <details><summary>{site.supportingSites.length} supporting records</summary>
          <p>{query.trim() ? "Similar footprints for the same partner, source and compartment (at least 70% Jaccard similarity between every pair)." : "All observations for this named ligand across sources; footprints may differ."} Highlighted residues come from one observed footprint, not their union.</p>
          <ul>{site.supportingSites.map((support, index) => <li key={index}>
            {support.source} · {support.pdb ? <a href={`https://www.rcsb.org/structure/${support.pdb}`} target="_blank" rel="noreferrer">{support.pdb.toUpperCase()}</a> : "No PDB"} · {support.positions.length} residues
            {support.reference && <> · <a href={support.reference} target="_blank" rel="noreferrer">Evidence</a></>}
          </li>)}</ul>
        </details>}
        <details><summary>Canonical residue positions</summary><p className={styles.contactResidues}>{site.positions.join(", ")}</p></details>
      </div>
      </details>
    </>}
    <details className={styles.contactEvidence}><summary>About this evidence</summary><p className={styles.contactNote}>Audited contact and epitope evidence. SAbDab and BioLiP currently show one representative site per gene, not all known sites. Different sources or structures may describe the same interface. IntAct binding regions and mutation effects are excluded from this contact view. Source labels identify provenance, not confidence or therapeutic suitability. <a href="/data/contact-sites/manifest.json" target="_blank" rel="noreferrer">Snapshot provenance ↗</a></p></details>
  </section>;
}
