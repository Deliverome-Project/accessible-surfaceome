# Comparing extracellular site predictors: SURFACE-Bind, Bindome, MaSIF rerun

Status: **work in progress.** Two sweeps were running when this was written;
numbers below are from the completed fractions and are labelled as such.

## Why

SURFACE-Bind (Balbi 2026 PNAS, [PMID 41604262]) is the only site-level resource
the catalogue carries, and it covers **1,612 of 5,316** cohort accessions (30%).
This compares it against a second designability resource (Bindome) and against
our own rerun of the method SURFACE-Bind itself used (MaSIF-site), to decide
whether the remaining 70% can be filled in credibly.

## SURFACE-Bind baseline

Of 2,708 proteins listed, only **1,649 carry scored sites** (4,557 sites). Anchor
residues were classified through the served DeepTMHMM topology:

| Anchor location | Sites | Share |
|---|---|---|
| extracellular | 3,492 | 77% |
| intracellular | 697 | 15% |
| signal peptide | 166 | 4% |
| membrane | 119 | 3% |
| no topology | 83 | 2% |

**1,349 proteins have at least one extracellular site.** Their methods say sites
in TM domains were removed, but 23% of published anchors are not extracellular —
the filter caught TM helices and not cytoplasmic regions. Applying the cohort's
DeepTMHMM strings is a correction to the published set, not just a reimplementation.

## Bindome (BindCraft, 305,806 designs / 8,289 targets)

Bindome publishes no target-side site list: `InterfaceResidues` in its metrics is
chain B (the binder's own residues) and `Target_Hotspot` is empty for every one of
the 305,815 rows — all designs used the `no_hotspot` protocol, so sites emerged
from design rather than being specified. Target sites therefore have to be computed
from the complex CIFs (chain A/B contacts at 5 A).

Overlap with the 1,349 SURFACE-Bind extracellular-site proteins is **481 (36%)**,
and strongly topology-dependent: 58% of 0-TM proteins, 40% of single-pass, ~0-15%
of multi-pass. ECD length does *not* predict exclusion above ~100 residues.

**Coverage, not disagreement, dominates**: Bindome cannot speak to 82% of
SURFACE-Bind's extracellular sites (62% on proteins it never designed against,
20% outside every designed domain window).

Concordance on the comparable set (sweep in progress, ~1/3 complete):
**median 0.0 A, 67% of anchors within 5 A, 82% within 10 A** of a Bindome
interface residue. A matched null (exposed non-interface residues in the same
domain) gives median 14.9 A and 11% within 5 A — Mann-Whitney p = 1.6e-14,
AUC 0.812, ~4.6x enrichment. In the reverse direction 39% of Bindome sites are
>10 A from any SURFACE-Bind anchor, so the union is ~1.6x either alone.

## MaSIF rerun

SURFACE-Bind's published pipeline (from their methods): MaSIF-site per-point
threshold **0.7** -> **DBSCAN** -> discard clusters **<200 points** -> drop TM
sites, over **AlphaFold2 models** filtered at pLDDT > 0.6. They do not specify the
DBSCAN `eps`, the anchor-residue definition, or how site area is computed.

Reproducing that on 4 matched proteins, then applying the DeepTMHMM filter to our
own sites:

| Gene | our sites (raw -> extracellular) | theirs (all -> EC) | matched |
|---|---|---|---|
| LY6G6C | 2 -> 1 | 2 -> 1 | 1/1 |
| CD8A | 2 -> 2 | 2 -> 1 | 1/1 |
| IL7R | 6 -> 1 | 1 -> 1 | 1/1 |
| SPINT2 | 2 -> 0 | 3 -> 2 | 0/2 |

The topology filter is what makes this interpretable: IL7R looked like 6 sites
against their 1 before filtering and is 1-vs-1 after. Matched site areas are
4182/3950/3154 A^2; unmatched are 2073/1279 A^2 — we reproduce large sites and
miss small ones. An `eps` sweep (1.5-8.0 A) leaves the result unchanged, so
clustering parameters are not the cause. pLDDT does not explain SPINT2 either:
its anchors sit at 97.7 and 97.6. The open candidates are the MaSIF model variant
and weights, neither of which their methods name.

## Cost

Measured on AlphaFold models (surface prep dominates; prediction is 12-22 s
regardless of size): 78 s at 125 aa, 197 s at 235, 208 s at 252, 548 s at 459,
620 s at 1210.

| Scope | Proteins | Compute | Cost | Wall clock @100 |
|---|---|---|---|---|
| L1 minus existing SURFACE-Bind sites | 1,202 | 137 core-h | **~$22** | 1.4 h |
| All L1 canonical (adds a validation set) | 2,420 | ~275 core-h | ~$44 | 2.8 h |
| Full deep-dive cohort | 5,316 | 635 core-h | ~$100 | 6.3 h |

## Reproducing

```bash
# Bindome x SURFACE-Bind concordance (detached, resumable)
uv run modal run --detach modal/bindome_concordance_app.py

# MaSIF-site over the L1 library (detached, resumable, 100 concurrent)
uv run python scripts/audit/build_l1_masif_inputs.py l1_canonical.json l1_inputs.json
uv run modal volume put masif-l1 l1_inputs.json /l1_inputs.json
uv run modal run --detach modal/masif_site_app.py::driver

# site-level comparison + the eps sensitivity check
uv run --with scikit-learn python scripts/audit/masif_vs_surface_bind_sites.py sb.json masif_out/
uv run --with scikit-learn python scripts/audit/masif_dbscan_eps_sweep.py sb.json masif_out/
```

### Note on the MaSIF image

`modal/masif/Dockerfile` exists because the published `pablogainza/masif` image
cannot run under Modal as shipped. The lineage is pinned to Python 3.6 by PyMesh
(latest release v0.3, 2020) on Debian 9 / glibc 2.24, while Modal's runtime needs
>=3.10. The Dockerfile keeps MaSIF's own interpreter at `/masifbin` and installs a
conda Python 3.11 as the default. It also rebuilds `reduce`, which ships as a
**32-bit i386 binary** on an x86_64 base and otherwise fails every protonation
call with "Exec format error" — the surface `.ply` is then never written and the
failure only surfaces downstream in PyMesh.

[PMID 41604262]: https://pubmed.ncbi.nlm.nih.gov/41604262/
