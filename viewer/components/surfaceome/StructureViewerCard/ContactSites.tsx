"use client";
import { contactColor, LIGAND_CATEGORIES, contactContext, filterContacts, browsingContacts, ligandOptions, namedLigand } from "../../../lib/contact-sites";
import { InfoTip } from "../../InfoTip/InfoTip";
import { ContactPicker } from "./ContactPicker";
import { ContactProjections } from "./ContactProjections";
import type { ContactSite, ContactAtom, ContactGroup, LigandCategory } from "../../../lib/contact-sites";
import styles from "./StructureViewerCard.module.css";

const SOURCE_INFO: Record<string, string> = {
  "PDB/PDBe": "Contacts between protein partners in experimental PDB structures, mapped to canonical UniProt positions by PDBe. Proximity alone does not establish physiological binding.",
  "IUPHAR+PDBe": "Guide to Pharmacology identifies the ligand–target relationship; PDBe supplies residue contacts from experimental structures. These can duplicate PDB/PDBe observations of the same complex.",
  "PDBe": "Experimental small-molecule contacts linked to Guide to Pharmacology annotations. Contact residues are mapped to the canonical protein sequence.",
  "Thera-SAbDab": "Therapeutic antibody identities linked to structural antibody contacts. Includes investigational and discontinued agents, not only approved medicines.",
  "SAbDab": "Structural Antibody Database: antibody–antigen interfaces in experimental structures. This audit retains one mapped representative interface per gene.",
  "AACDB": "Antibody–antigen complex structures with mapped contact residues. Multiple structures can describe the same antibody and binding footprint.",
  "IEDB": "Immune Epitope Database: experimentally mapped antibody epitopes and assay references. Only exact mapped epitopes are included here; assay conditions and native accessibility vary.",
  "BioLiP": "Curated biologically relevant ligand interactions from structures. This audit retains one mapped representative site per gene; biological ligands can include cofactors.",
  "GPCRdb": "Curated GPCR structural ligand contacts mapped to receptor positions. Sites may include transmembrane residues.",
  "BioGRID+literature": "Literature-supported engineered binder contacts with source references. Broad interaction annotations alone are not treated as exact contact residues.",
};
function SourceInfo({source}: {source: string}) {
  return <span className={styles.contactSource}>{source}<InfoTip label={`About ${source}`} align="start">{SOURCE_INFO[source] ?? "Experimental contact evidence; see the linked source record for its methods and limitations."}</InfoTip></span>;
}

export function ContactSites({ sites, selected, onSelect, source, onSource, ecOnly, onEcOnly, status, onRetry, query, onQuery, atoms, visibleSites, compare, onCompare, onFocus, onReset }: {
  onFocus: () => void; onReset: () => void;
  atoms: ContactAtom[]; visibleSites: ContactGroup[]; compare: boolean; onCompare: (value: boolean) => void;
  query: string; onQuery: (query: string) => void;
  sites: ContactSite[]; selected: number; onSelect: (index: number) => void;
  source: string; onSource: (source: string) => void; ecOnly: boolean;
  onEcOnly: (value: boolean) => void; status: string; onRetry: () => void;
}) {
  const binderNames = ligandOptions(filterContacts(sites, source, ecOnly, ""));
  const allLigands = browsingContacts(filterContacts(sites, "", ecOnly, ""), true, "");
  const allCompartmentCount = browsingContacts(sites, true, "").length;
  const categoryCounts = Object.keys(LIGAND_CATEGORIES).map(key => ({
    key: key as LigandCategory,
    count: allLigands.filter(s => (s.category ?? "unclassified") === key).length,
  }));
  const records = filterContacts(sites, source, ecOnly, query);
  const filtered = browsingContacts(records, true, query);
  const site = filtered[selected];
  return <section className={styles.contactPanel} aria-label="Contact-site evidence">
    {status === "ready" && <header className={styles.contactOverview}>
      <strong>{allLigands.length} <span>{ecOnly ? "extracellular" : "total"} ligands / binders</span></strong>
      {ecOnly && <small>{allCompartmentCount} across all compartments</small>}
      <div className={styles.contactCategories} aria-label="Ligand categories and counts">
        {categoryCounts.map(({key, count}) => <span key={key} style={{borderLeftColor: LIGAND_CATEGORIES[key].color}}><i style={{background: LIGAND_CATEGORIES[key].color}} />{LIGAND_CATEGORIES[key].label} <b>{count}</b></span>)}
      </div>
    </header>}
    <div className={styles.contactFilters}>
      <ContactPicker label="Ligand" value={binderNames.includes(query) ? query : ""} placeholder="All ligands" onChange={onQuery}
        groups={categoryCounts.map(({key}) => ({label: LIGAND_CATEGORIES[key].label, options: binderNames.filter(name => allLigands.some(s => s.partner_label?.toLowerCase() === name.toLowerCase() && (s.category ?? "unclassified") === key))}))} />
    </div>
    {status === "loading" ? <p role="status">Loading contact evidence…</p> : status === "error" ?
      <p role="alert">Contact evidence could not be loaded. <button onClick={onRetry}>Retry</button></p> : status === "unaudited" ?
      <p>This protein has no unambiguous mapping in this audit.</p> : !site ?
      <p>No mapped sites in this audit match these filters. This does not establish absence of binders.</p> : <>
      {filtered.length > 1 && <div className={styles.contactSlider}>
        <button aria-label="Previous contact site" disabled={selected === 0} onClick={() => onSelect(selected - 1)}>←</button>
        <input type="range" aria-label="Contact site" min={0} max={Math.max(0, filtered.length - 1)} value={selected}
          aria-valuetext={`${selected + 1} of ${filtered.length}: ${site.source}, ${site.partner_label ?? site.partner}`}
          disabled={filtered.length === 1} onChange={e => onSelect(Number(e.target.value))}
          style={{ accentColor: contactColor(site) }} />
        <button aria-label="Next contact site" disabled={selected === filtered.length - 1} onClick={() => onSelect(selected + 1)}>→</button>
        <span className={styles.contactCounter}>Ligand {selected + 1} of {filtered.length}</span>
      </div>}
      <div className={styles.contactSelection}>
        <div><strong>{site.partner_label ?? site.partner}</strong><span><i style={{ background: contactColor(site) }} />{LIGAND_CATEGORIES[site.category ?? "unclassified"].label} · {site.positions.length} contact residues</span></div>
        <button onClick={onFocus}>Focus site</button><button onClick={onReset}>Whole protein</button>
      </div>
      {query.trim() && <button className={styles.contactTextAction} onClick={() => onQuery("")}>← All ligands</button>}
      <div className={styles.contactSourceRow}>Sources {Array.from(new Set(site.supportingSites.map(s => s.source))).map(source => <SourceInfo key={source} source={source} />)}</div>
      <details className={styles.contactEvidence}><summary>Evidence · {new Set(site.supportingSites.map(s => s.pdb).filter(Boolean)).size} structures · {site.supportingSites.length} source records</summary>
      <div>
        <SourceInfo source={site.source} /> · {site.partner_label ?? site.partner}{site.partner_label ? ` (${site.partner})` : ""}<br />
        {LIGAND_CATEGORIES[site.category ?? "unclassified"].label}{site.category_reference && <> · <a href={site.category_reference} target="_blank" rel="noreferrer">Category source ↗</a></>}<br />
        {contactContext(site.context)} · {site.positions.length} residues · {site.evidence}
        <p>{site.confidence}. Contacts are projected onto the canonical AlphaFold model; this is not a model of the bound complex.</p>
        {site.pdb && <a href={`https://www.rcsb.org/structure/${site.pdb}`} target="_blank" rel="noreferrer">PDB {site.pdb.toUpperCase()} ↗</a>}
        {site.reference && <> · <a href={site.reference} target="_blank" rel="noreferrer">Evidence ↗</a></>}
        {site.supportingSites.length > 1 && <details><summary>Alternative observations ({site.supportingSites.length})</summary>
          <p>One representative observed footprint is shown on the structure. Records below preserve alternative residue measurements and duplicate reports across sources; they are not additional ligands.</p>
          <ul>{site.supportingSites.map((support, index) => <li key={index}>
            <SourceInfo source={support.source} /> · {support.pdb ? <a href={`https://www.rcsb.org/structure/${support.pdb}`} target="_blank" rel="noreferrer">{support.pdb.toUpperCase()}</a> : "No PDB"} · {support.positions.length} residues
            <details><summary>Contact residues</summary><p className={styles.contactResidues}>{support.positions.join(", ")}</p></details>
            {support.reference && <> · <a href={support.reference} target="_blank" rel="noreferrer">Evidence</a></>}
          </li>)}</ul>
        </details>}
        <details><summary>Canonical residue positions</summary><p className={styles.contactResidues}>{site.positions.join(", ")}</p></details>
      </div>
      </details>
    </>}
    <details className={styles.contactEvidence}><summary>Filters &amp; comparison</summary>
      <div className={styles.contactFilters}>
      <label>Search <input type="search" placeholder="Name or identifier" value={query} onChange={e => onQuery(e.target.value)} /></label>
      <ContactPicker label="Source" value={source} placeholder="All sources" onChange={onSource} groups={[{options: Array.from(new Set(sites.map(s => s.source))).sort()}]} />
      <label><input type="checkbox" checked={compare} onChange={e => onCompare(e.target.checked)} /> Compare other binders separately</label>
      <label><input type="checkbox" checked={ecOnly} onChange={e => onEcOnly(e.target.checked)} /> Extracellular only</label>
      </div>
      <details className={styles.contactEvidence}><summary>Three-angle view</summary><ContactProjections atoms={atoms} sites={visibleSites} /></details>
      <p className={styles.contactNote}>{records.length} evidence records. The overview shows one observed footprint per named ligand; sources may overlap. {records.filter(s => !namedLigand(s)).length} unresolved identity records are searchable by identifier.</p>
    </details>
    <details className={styles.contactEvidence}><summary>About this evidence</summary><p className={styles.contactNote}>Colors indicate ligand category; database provenance is listed with the evidence. Endogenous large molecules include proteins and peptides. Therapeutic includes investigational and discontinued programs, not only approved drugs. Research tools are explicitly reviewed reagents; missing therapeutic annotation alone does not imply a tool. Unclassified entries lack a verified role. Totals count named ligands in this contact-evidence snapshot, not all known ligands. Audited contact and epitope evidence. SAbDab and BioLiP currently show one representative site per gene, not all known sites. Different sources or structures may describe the same interface. IntAct binding regions and mutation effects are excluded from this contact view. Source labels identify provenance, not confidence or therapeutic suitability. Source records may report the same experimental structure more than once. <a href="/data/contact-sites/manifest.json" target="_blank" rel="noreferrer">Snapshot provenance ↗</a></p></details>
  </section>;
}
