# /l1-review/ — verification screenshots

Captured against the **live dev API** (`https://api.deliverome.org/surfaceome`, load
`l1d-3abdd2363fe07f1f`: 2,710 members / 3,498 sites / 6,450 structures), not a fixture,
by running the viewer locally with

```bash
cd viewer && NEXT_PUBLIC_L1_DESIGN_API_BASE=https://api.deliverome.org/surfaceome npm run dev
```

| File | What it shows |
|---|---|
| `01-three-arm-lhfpl6-1280x800.jpg` | `LHFPL6` `l1-p1088`, three arms. Whole working surface — header, filters, list, gene tabs, topology strip, verdict buttons — above the fold at 1280×800. |
| `02-three-arm-lhfpl6-1440x900.jpg` | The same member at 1440×900, with the Structure section also in view. |
| `03-one-arm-f11r-signal-peptide.jpg` | `F11R` `l1-p0598`, one arm, and the worst-case colour adjacency: the insert flag lands on the boundary of the red signal peptide. |
| `04-ortholog-tfrc-cyno.jpg` | `TFRC` cyno ortholog `l1-p2617` — tabs read `Canonical 760 aa` / `Cyno ortholog 732 aa`, each on its own residue numbering; the C-terminal flag is clamped inside the strip. |
| `05-keyboard-help.jpg` | The `?` key list, and the list re-fitting itself to the room left. |

Review artifacts, not generated outputs — nothing builds from them. Safe to delete once
the PR is merged.
