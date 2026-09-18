"use client";
import { contactColor, SHARED_CONTACT_COLOR, LIGAND_CATEGORIES, contactContext, filterContacts, browsingContacts, ligandOptions } from "../../../lib/contact-sites";
import { InfoTip } from "../../InfoTip/InfoTip";
import { ContactPicker } from "./ContactPicker";
import type { ContactSite, LigandCategory } from "../../../lib/contact-sites";
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

export function ContactSites({ sites, selected, source, ecOnly, status, onRetry, query, onQuery, onFocus, onReset }: {
  onFocus: () => void; onReset: () => void;
  query: string; onQuery: (query: string) => void;
  sites: ContactSite[]; selected: number;
  source: string; ecOnly: boolean;
  status: string; onRetry: () => void;
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
  const navigation = browsingContacts(filterContacts(sites, source, ecOnly, ""), true, "");
  const site = filtered[selected];
  const navigationIndex = site ? navigation.findIndex(item => item.partner_label?.toLowerCase() === site.partner_label?.toLowerCase()) : -1;
  const navigate = (index: number) => onQuery(navigation[index].partner_label ?? navigation[index].partner);
  const overview = filtered.length > 1;
  return <section className={styles.contactPanel} aria-label="Contact-site evidence">
    {status === "ready" && <header className={styles.contactOverview}>
      <strong>{allLigands.length} <span>{ecOnly ? "extracellular" : "total"} ligands / binders</span> <InfoTip label="About ligand coverage" align="start">Named partners with mapped contacts in this audit, not an exhaustive ligand census. Each ligand uses one observed footprint; evidence retains alternative observations. Category colors describe the partner’s role, not confidence. Therapeutic includes investigational and discontinued agents; unclassified roles are unverified.</InfoTip></strong>
      {ecOnly && <small>{allCompartmentCount} across all compartments</small>}
      <div className={styles.contactCategories} aria-label="Ligand categories and counts">
        {categoryCounts.map(({key, count}) => <span key={key} style={{borderLeftColor: LIGAND_CATEGORIES[key].color}}><i style={{background: LIGAND_CATEGORIES[key].color}} />{LIGAND_CATEGORIES[key].label} <b>{count}</b>{key === "unclassified" && count > 0 && <InfoTip label="Which partners are unclassified?" align="start">{allLigands.filter(s => s.category === "unclassified").map(s => s.partner_label ?? s.partner).join(", ")}. Binding evidence is present, but a role in these categories has not been verified. These may include receptor partners.</InfoTip>}</span>)}
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
      {overview ? <>
        <div className={styles.contactSelection}><div><strong>{filtered.length} ligand footprints shown together</strong><span>One observed footprint per named partner</span></div><button onClick={onFocus}>Focus sites</button><button onClick={onReset}>Whole protein</button></div>
        <p className={styles.contactNote}><i style={{display: "inline-block", width: 8, height: 8, background: SHARED_CONTACT_COLOR}} /> Blue-gray marks residues shared across categories. Overlap does not imply simultaneous binding.</p>
        <details className={styles.contactEvidence}><summary>Shown ligands &amp; evidence</summary><ul>{filtered.map(item => <li key={item.partner_label ?? item.partner}><button className={styles.contactTextAction} onClick={() => onQuery(item.partner_label ?? item.partner)}>{item.partner_label ?? item.partner}</button> · {item.positions.length} contact residues · {item.supportingSites.length} records</li>)}</ul></details>
      </> : <>
      {query.trim() && navigationIndex >= 0 && navigation.length > 1 && <div className={styles.contactSlider}>
        <button aria-label="Previous ligand" disabled={navigationIndex === 0} onClick={() => navigate(navigationIndex - 1)}>←</button>
        <input type="range" aria-label="Individual ligand" min={0} max={navigation.length - 1} value={navigationIndex}
          aria-valuetext={`${site.partner_label}: ${LIGAND_CATEGORIES[site.category ?? "unclassified"].label}, ${navigationIndex + 1} of ${navigation.length}`}
          style={{accentColor: contactColor(site)}} onChange={event => navigate(Number(event.target.value))} />
        <button aria-label="Next ligand" disabled={navigationIndex === navigation.length - 1} onClick={() => navigate(navigationIndex + 1)}>→</button>
        <span className={styles.contactCounter}>{LIGAND_CATEGORIES[site.category ?? "unclassified"].label} · {navigationIndex + 1} / {navigation.length}</span>
      </div>}
      <div className={styles.contactSelection}>
        <div><strong>{site.partner_label ?? site.partner}</strong><span><i style={{ background: contactColor(site) }} />{site.positions.length} contact residues</span></div>
        <button onClick={onFocus} aria-label="Focus contact site">Focus</button><button onClick={onReset} aria-label="Show whole protein">Reset</button>
      </div>

      <details key={site.partner_label ?? site.partner} className={styles.contactEvidence}><summary>Evidence ({site.supportingSites.length} records)</summary>
      <div>
      <div className={styles.contactSourceRow}>Sources {Array.from(new Set(site.supportingSites.map(s => s.source))).map(source => <SourceInfo key={source} source={source} />)}</div>
        <SourceInfo source={site.source} /> · {site.partner_label ?? site.partner}{site.partner_label ? ` (${site.partner})` : ""}<br />
        {LIGAND_CATEGORIES[site.category ?? "unclassified"].label}{site.category_reference && <> · <a href={site.category_reference} target="_blank" rel="noreferrer">Category source ↗</a></>}<br />
        {site.category_reason && <p>{site.category_reason}</p>}
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
    </>}
  </section>;
}
