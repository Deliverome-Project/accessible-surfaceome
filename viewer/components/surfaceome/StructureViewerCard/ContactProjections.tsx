"use client";
import { contactColor, contactHull } from "../../../lib/contact-sites";
import type { ContactAtom, ContactGroup } from "../../../lib/contact-sites";
import styles from "./StructureViewerCard.module.css";

const VIEWS = [ ["Front (XY)", "x", "y"], ["Side (ZY)", "z", "y"], ["Top (XZ)", "x", "z"] ] as const;
export function ContactProjections({ atoms, sites }: { atoms: ContactAtom[]; sites: ContactGroup[] }) {
  if (!atoms.length || !sites.length) return null;
  const contactPositions = new Set(sites.flatMap(site => site.positions));
  const contactAtoms = atoms.filter(atom => contactPositions.has(atom.resi));
  const framingAtoms = contactAtoms.length ? contactAtoms : atoms;
  return <div>
    <p className={styles.contactNote}><strong>{sites.length} {sites.length === 1 ? "footprint shown" : "footprints shown together"}</strong> · use the slider for alternatives</p>
    <div className={styles.contactViews}>
      {VIEWS.map(([label, horizontal, vertical]) => {
        const xs = framingAtoms.map(a => a[horizontal]), ys = framingAtoms.map(a => a[vertical]);
        const minX = Math.min(...xs), minY = Math.min(...ys);
        const width = Math.max(...xs)-minX, height = Math.max(...ys)-minY;
        const scale = 160 / Math.max(width, height, 1);
        const project = (a: ContactAtom): [number,number] => [
          100 + (a[horizontal]-minX-width/2)*scale,
          100 - (a[vertical]-minY-height/2)*scale,
        ];
        return <figure key={label} className={styles.contactView}>
          <svg viewBox="0 0 200 200" role="img" aria-label={`${label}: ${sites.length} contact footprints`}>
            {atoms.slice(1).map((a,i) => {
              if (a.resi !== atoms[i].resi + 1) return null;
              const p=project(atoms[i]), q=project(a);
              return <line key={i} x1={p[0]} y1={p[1]} x2={q[0]} y2={q[1]} stroke="#c4c8ce" strokeWidth="0.8" />;
            })}
            {sites.map((site,i) => {
              const positions = new Set(site.positions);
              const points = atoms.filter(a=>positions.has(a.resi)).map(project);
              if (!points.length) return null;
              const hull = contactHull(points);
              const center = [points.reduce((s,p)=>s+p[0],0)/points.length,points.reduce((s,p)=>s+p[1],0)/points.length];
              const color=contactColor(site);
              return <g key={i}>
                {hull.length > 2 ? <polygon points={hull.map(p=>p.join(",")).join(" ")} fill={color} fillOpacity="0.09" stroke={color} strokeWidth="3" strokeLinejoin="round" strokeDasharray={i===0 ? undefined : i===1 ? "7 3" : "2 3"} /> :
                  <ellipse cx={center[0]} cy={center[1]} rx={Math.max(6,...points.map(p=>Math.abs(p[0]-center[0])))} ry={Math.max(6,...points.map(p=>Math.abs(p[1]-center[1])))} fill="none" stroke={color} strokeWidth="3" />}
                <circle cx={center[0]} cy={center[1]} r="8" fill="white" stroke={color} strokeWidth="1.5" />
                <text x={center[0]} y={center[1]+3} textAnchor="middle" fontSize="10" fontWeight="bold" fill={color}>{i+1}</text>
              </g>;
            })}
          </svg>
          <figcaption>{label}</figcaption>
        </figure>;
      })}
    </div>
    <ol className={styles.contactComparisonList}>
      {sites.map((site,i) => <li key={i} style={{borderColor:contactColor(site)}}>
        <strong>{i+1}. {site.partner_label ?? site.partner}</strong> · {site.source} · {site.positions.length} residues
        {i===0 ? " · selected binder" : " · separate comparison binder"}
      </li>)}
    </ol>
    <p className={styles.contactNote}>Three fixed orthogonal views, zoomed to the compared contacts on the canonical model. Outlines enclose contact residues; enclosed gaps are not additional contacts. Compared footprints share at most 20% of the smaller residue set. This does not establish simultaneous binding.</p>
  </div>;
}
