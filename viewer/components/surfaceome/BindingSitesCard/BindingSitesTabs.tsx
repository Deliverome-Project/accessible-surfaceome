"use client";

import { useState } from "react";
import type {
  BindomeSite,
  SurfaceBindSite,
} from "../../../lib/surfaceome-types";
import { BindomeTable } from "./BindomeTable";
import { SurfaceBindTable } from "./SurfaceBindTable";
import styles from "./BindingSitesCard.module.css";

type Source = "surface_bind" | "bindome";

interface Props {
  surfaceBindSites: SurfaceBindSite[];
  bindomeSites: BindomeSite[] | null;
  topology: string;
}

/**
 * Source toggle over the two binding-site predictions.
 *
 * They are deliberately NOT merged into one table: SURFACE-Bind scores
 * surface patches with MaSIF and rates them by binder-seed pools, while
 * Bindome recovers a site from where 305,806 BindCraft designs actually
 * landed and rates it by design consensus. The per-site metrics have no
 * common scale, so a merged table would invite a comparison that the
 * numbers do not support. What they DO share is the compartment axis —
 * both label an anchor with the same DeepTMHMM topology — so the EC
 * filter means the same thing on either tab.
 *
 * Only rendered with a toggle when both sources have sites; with one
 * source it renders that table directly rather than a single dead tab.
 */
export function BindingSitesTabs({
  surfaceBindSites,
  bindomeSites,
  topology,
}: Props) {
  const hasBindome = !!bindomeSites && bindomeSites.length > 0;
  const hasSurfaceBind = surfaceBindSites.length > 0;
  const [source, setSource] = useState<Source>(
    hasSurfaceBind ? "surface_bind" : "bindome",
  );

  if (!hasBindome) {
    return <SurfaceBindTable sites={surfaceBindSites} topology={topology} />;
  }
  if (!hasSurfaceBind) {
    return <BindomeTable sites={bindomeSites} topology={topology} />;
  }
  return (
    <>
      <div className={styles.sourceTabs} role="tablist" aria-label="Prediction source">
        <button
          type="button"
          role="tab"
          aria-selected={source === "surface_bind"}
          className={
            source === "surface_bind" ? styles.sourceTabActive : styles.sourceTab
          }
          onClick={() => setSource("surface_bind")}
        >
          SURFACE-Bind ({surfaceBindSites.length})
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={source === "bindome"}
          className={
            source === "bindome" ? styles.sourceTabActive : styles.sourceTab
          }
          onClick={() => setSource("bindome")}
        >
          Bindome ({bindomeSites.length})
        </button>
      </div>
      {source === "surface_bind" ? (
        <SurfaceBindTable sites={surfaceBindSites} topology={topology} />
      ) : (
        <BindomeTable sites={bindomeSites} topology={topology} />
      )}
    </>
  );
}
