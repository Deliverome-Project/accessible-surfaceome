"use client";

import { useMemo, useState } from "react";
import { type Compartment, compartmentAt } from "../../../lib/surface-bind";
import type { BindomeSite } from "../../../lib/surfaceome-types";
import { InfoTip } from "../../InfoTip/InfoTip";
import { StatusPill } from "../StatusPill/StatusPill";
import styles from "./BindingSitesCard.module.css";

// Compartment tone / glyph / rank are duplicated from SurfaceBindTable
// rather than shared, because that file reads them off a SurfaceBindSite.
// Keeping the mapping identical is what lets the two tables sit behind one
// toggle without the "Side" column changing meaning between them.
function compartmentTone(
  c: Compartment,
): "lavender" | "danger" | "success" | "neutral" {
  if (c === "extracellular") return "lavender";
  if (c === "signal") return "danger";
  if (c === "intracellular") return "success";
  return "neutral";
}

function compartmentGlyph(c: Compartment): string {
  if (c === "extracellular") return "EC";
  if (c === "intracellular") return "IC";
  if (c === "membrane") return "TM";
  if (c === "signal") return "SP";
  return "?";
}

function compartmentRank(c: Compartment): number {
  if (c === "extracellular") return 0;
  if (c === "membrane") return 1;
  if (c === "signal") return 2;
  if (c === "intracellular") return 3;
  return 4;
}

/** How strongly the designs agree on a site: the share of this protein's
 *  parsed designs that contact its most-contacted residue. Unanimous
 *  agreement is a much stronger signal than one design wandering past, so
 *  the tone is deliberately steep at the top. */
function consensusTone(frac: number): "success" | "teal" | "amber" {
  if (frac >= 0.8) return "success";
  if (frac >= 0.4) return "teal";
  return "amber";
}

interface Props {
  sites: BindomeSite[];
  topology: string | null;
}

export function BindomeTable({ sites, topology }: Props) {
  const [ecOnly, setEcOnly] = useState(false);

  const rows = useMemo(() => {
    const withSide = sites.map((s) => ({
      site: s,
      // Prefer the Worker's own label, but fall back to computing it from
      // the topology string so the column still renders if the block was
      // served before anchor_topology existed.
      side: (s.anchor_topology as Compartment | null)
        ?? (topology ? compartmentAt(topology, s.anchor_residue) : "unknown"),
    }));
    const kept = ecOnly
      ? withSide.filter((r) => r.side === "extracellular")
      : withSide;
    return kept.sort(
      (a, b) =>
        compartmentRank(a.side) - compartmentRank(b.side) ||
        b.site.n_designs_supporting - a.site.n_designs_supporting,
    );
  }, [sites, topology, ecOnly]);

  const nEc = sites.filter(
    (s) => (s.anchor_topology ?? "") === "extracellular",
  ).length;

  return (
    <>
      <div className={styles.tableControls}>
        <label className={styles.ecToggle}>
          <input
            type="checkbox"
            checked={ecOnly}
            onChange={(e) => setEcOnly(e.target.checked)}
          />{" "}
          Extracellular only ({nEc} of {sites.length})
        </label>
      </div>
      <table className={styles.table}>
        <thead>
          <tr>
            <th scope="col">Site</th>
            <th scope="col">
              Anchor{" "}
              <InfoTip label="Anchor residue">
                The residue nearest the centre of the contacted patch.
                Bindome publishes no site list of its own, so a site is
                recovered from where its BindCraft designs land: residues
                contacted by at least 20% of this protein&rsquo;s designs,
                clustered in 3D.
              </InfoTip>
            </th>
            <th scope="col">
              Side{" "}
              <InfoTip label="Membrane side">
                Which side of the membrane the anchor sits on, from the same
                DeepTMHMM topology used for the SURFACE-Bind sites. Only EC
                patches are reachable by a systemic antibody.
              </InfoTip>
            </th>
            <th scope="col">Residues</th>
            <th scope="col">
              Design support{" "}
              <InfoTip label="Design support">
                How many of this protein&rsquo;s parsed designs contact the
                site&rsquo;s most-contacted residue. Unanimous support means
                every design converged on the same patch.
              </InfoTip>
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map(({ site, side }) => {
            const frac = site.n_designs_total
              ? site.n_designs_supporting / site.n_designs_total
              : 0;
            return (
              <tr key={site.site_id}>
                <td>{site.site_id}</td>
                <td>{site.anchor_residue}</td>
                <td>
                  <StatusPill tone={compartmentTone(side)}>
                    {compartmentGlyph(side)}
                  </StatusPill>
                </td>
                <td>{site.n_residues}</td>
                <td>
                  <StatusPill tone={consensusTone(frac)}>
                    {site.n_designs_supporting}/{site.n_designs_total}
                  </StatusPill>
                </td>
              </tr>
            );
          })}
          {rows.length === 0 ? (
            <tr>
              <td colSpan={5} className={styles.emptyNote}>
                No extracellular sites — every Bindome patch on this protein
                anchors elsewhere.
              </td>
            </tr>
          ) : null}
        </tbody>
      </table>
    </>
  );
}
