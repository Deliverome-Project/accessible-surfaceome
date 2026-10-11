# Paper build

Render a `.docx` manuscript into a Deliverome-branded PDF + JATS XML
in one command. Aesthetic reference: bioRxiv preprint layout, polished
like Pioneer Labs' [BioBloom paper](https://doi.org/10.64898/2026.02.04.703572).

## Quick start

```bash
brew install pandoc          # or apt install pandoc
pip install weasyprint        # or pipx install weasyprint

bash paper/build.sh path/to/manuscript.docx
```

Outputs under `<docx-dir>/build/`:

| File | What it is |
|---|---|
| `<stem>.pdf` | Deliverome-branded PDF — feed to the manuscript bundle's `pdf_path` |
| `<stem>.xml` | JATS XML — feed to the manuscript bundle's `jats_filename` |
| `<stem>.html` | Intermediate (for debugging the print layout in a browser) |

Both outputs come from the same `.docx`, so your Word + Zotero
workflow stays untouched.

## How the brand stays consistent

`paper/deliverome-print.css` imports the project-wide design tokens
from `../viewer/app/design-tokens.css`. When the web brand evolves —
color tweak, font swap, palette extension — the next paper build
picks it up automatically. Nothing in `paper/` should hard-code a
color or font family that's already a token in `design-tokens.css`.

The visual reference points the CSS mirrors from the Pioneer paper:

| Element | Treatment |
|---|---|
| Page background | `var(--bg)` (off-white) |
| Title block | Cream wash (`var(--bg-warm)`) with maroon-pale bottom rule |
| Title | Playfair Display 28pt, `var(--maroon-deepest)` |
| Section headings (Abstract / Introduction / …) | Manrope 700 UPPERCASE caps, `var(--maroon-dark)` |
| Subsection headings | Playfair Display 13pt, `var(--maroon-dark)` |
| Body | Manrope 9.5pt, two-column, justified, hyphenated |
| Figures | Cream card with 4px maroon left bar, full column-span |
| Figure-caption lead ("Figure N. Title.") | Manrope 700, `var(--maroon-dark)` — extent set by `figures.lua`, not by line breaks |
| Tables | Maroon-blush header row, dark border under header |
| Block quotes | Maroon-blush background with maroon side rule |
| Footer | "Deliverome" left, page number right, both maroon |

## The web edition's motion layer

`build.py --web` adds a scroll-reveal pass on top of the same pandoc
output the PDF uses. Three files share the work, and the split is
load-bearing rather than cosmetic:

| File | Owns |
|---|---|
| `web_assets.py` | Stamps `class="reveal"` onto structural blocks at build time, plus the `<head>` fragments (fonts, the reveal gate). Imports no pandoc, so CI tests it on every run. |
| `deliverome-web.css` | The motion itself — hidden state, transition, escapes. |
| `deliverome-web.js` | The parts needing a viewport: what is already on screen, arming, the observers. |

**The safety property.** The hidden state (`opacity: 0`) applies only
under `html.js-reveal`, and that class is set by one inline `<head>`
script which first checks for `IntersectionObserver`. A reader whose JS
fails, a crawler, or Reader Mode therefore gets an ordinary fully
visible paper — the `reveal` classes in the markup do nothing on their
own. `tests/test_paper_web_motion.py` fails the build if any rule
hides content outside that gate. **Don't "simplify" the gate away.**

Two orderings also matter, and both have already bitten once:

* The gate must be set **inline in `<head>`**, not from the deferred
  `paper.js`. Set later, the page paints visible and then blanks out.
* Arming the transition is a **separate class**, applied after whatever
  is already on screen has been marked visible. That is what keeps the
  opening screen from animating. It is applied synchronously after a
  forced style flush, not in a `requestAnimationFrame` — rAF is paused
  in a background tab, and it races the observer's first batch.

Tuning lives in the `:root` block of `deliverome-web.css`
(`--reveal-duration`, `--reveal-distance`, `--reveal-step`,
`--reveal-ease`).

**Prose reveals too, and that is the whole effect.** An earlier version
animated only structure — headings, figures, tables — reasoning that
`opacity: 0` text is still matched by find-in-page. The reasoning was
sound and the result was wrong: it left 97 of 184 top-level blocks
static, and since prose is what a reader spends almost all of their
scrolling inside, the page read as though nothing was happening.
Find-in-page is handled where the problem actually is instead — the
`beforematch` / Cmd+F handler in `deliverome-web.js` drops the entire
reveal the moment anyone starts searching. Don't "fix" find-in-page by
taking prose back out.

**Large blocks move further and slower.** A figure that travels the
same 18px over the same 620ms as a line of text has barely shifted
relative to its own height, so it reads as simply appearing rather than
arriving. `.figure-block` and `table` override both tokens.

**The trigger is held** (`rootMargin: 0px 0px -18% 0px`) rather than
firing as a block clips the viewport edge. Fired at the edge, the
animation completes below where anyone is looking and the page just
seems to have been that way already.

Only the reference list is staggered — it is the one place with a
column of near-identical siblings. Figures here are single composite
renders, so there is nothing to stagger inside one.

### The lightbox fits the screen, legend and all

Opening a figure full-screen is for seeing the whole figure *and* its
legend, so nothing in the lightbox scrolls. The overlay is
`overflow: hidden` and the panel is a flex column:

* The **legend is laid out first** and keeps its natural height, at the
  full panel width. An earlier version capped it and let it scroll,
  which meant opening a figure full-screen and still not being able to
  read its legend. Full width is also what makes it fit — a wider
  measure wraps the same text into fewer lines.
* The **image takes whatever is left**. `min-height: 0` is the
  load-bearing line: a flex item defaults to `min-height: auto` and
  refuses to shrink below its intrinsic size, which is the usual reason
  a `max-height` on a flexbox image appears to do nothing.
  `object-fit: contain` keeps it from distorting as it shrinks.

**The figure zooms inside its own window.** Pinch (or scroll) over the
figure to magnify it up to 8x within the frame it already occupies —
the panel keeps its shape and the legend stays exactly where it is.
Once zoomed, drag or two-finger scroll to pan. A **Reset zoom** button
appears in the window while zoomed; double-click and Escape do the same
thing but neither is visible, so neither is a way out for a reader who
doesn't already know. Opening another figure always starts fitted.

Two things about panning are easy to get wrong and fail silently:

* A plain wheel has to **pan** once zoomed in, not zoom. Mapping it to
  zoom leaves the reader magnified with no way to reach the rest of the
  figure — a two-finger scroll is how anyone expects to move around a
  magnified image.
* A drag on an `<img>` is the browser's **native image drag** unless
  both `draggable="false"` and `preventDefault()` on `pointerdown` say
  otherwise. The pointer stream stops, a ghost thumbnail follows the
  cursor, and the pan never starts. Synthetic PointerEvents in a test
  do not reproduce this — it only shows up under a real drag.

The window takes its `aspect-ratio` from the image's own dimensions,
set by `paper.js` when the figure opens. That indirection is load
bearing: left to size the window itself, the image gives the window its
height, the window then shrinks to make room for the legend, and the
image — whose `max-height: 100%` resolves against a height derived from
it — keeps its original size and is clipped top and bottom. A window
with a shape of its own breaks the circularity.

Zoom is about the pointer, not the centre: zooming about the centre
drifts whatever you were looking at off screen, which is what makes a
zoom feel broken. Panning is clamped so the image always covers the
window.

Note that the overlay's dismiss-on-click would otherwise swallow the
zoom gesture — the image click is intercepted before that fallthrough.

### Figures reserve their box before they load

`apply_image_hints` stamps intrinsic `width`/`height` on every `<img>`,
which is what stops a figure shoving the prose below it down the page
as it decodes. Two things make that non-obvious:

* **It has to run late.** `figure_swap.swap_figures` strips
  `width`/`height` off every `<img>` it rewrites, and the title band
  isn't grouped into `<header>` until near the end — and that grouping
  is how an above-the-fold image is recognised, so it can be exempted
  from `loading="lazy"` (lazy-loading what the reader is already
  looking at costs LCP for nothing).
* **Most figures are SVG**, which Pillow cannot read. `_svg_size`
  parses `width`/`height` or falls back to the `viewBox`, rejecting
  percentage lengths — `width="100%"` is not an intrinsic size, and
  reserving a box 100 units wide is worse than reserving none.

### Appending to `<head>` or `<body>`

Use `_append_fragment`, not `lxml.html.fromstring`. On a head-only
element — `<link>`, `<meta>`, `<script>` — `fromstring` returns an
entire `<html><head>…</head></html>` document, so appending its result
nests a stray document inside the page. Browsers untangle it and the
paper shipped that way for a while, but the reveal bootstrap depends on
running before first paint, which should not rest on parser error
recovery.

### Web fonts load from `<head>`, not from the stylesheet

`deliverome-web.css` used to `@import` a Google Fonts URL. That is the
slowest path a font can take — our CSS, then Google's CSS, then the
woff2, three serial round trips before a character renders in the brand
face, visible as a full-page reflow on every cold load. The `<link>`
now lives in `<head>` behind two preconnects, emitted from
`web_assets.FONT_HEAD_LINKS`.

**Adding a weight or a face means editing `FONT_HEAD_LINKS`, not the
stylesheet.** Note the consequence for embedding: the fonts no longer
travel with the sheet, so a site that copies `paper.css` alone gets the
system stack unless it loads the faces itself. Every rule names a
fallback, so that degrades rather than breaks.

## Iterating on the print look

WeasyPrint reads exactly what Chrome's print emulation shows. To
iterate fast:

1. `bash paper/build.sh manuscript.docx` to produce the HTML.
2. Open `<docx-dir>/build/<stem>.html` in Chrome.
3. DevTools → ⋮ → More tools → Rendering → "Emulate CSS media type: print".
4. Tweak `paper/deliverome-print.css` and reload.
5. Re-run `bash paper/build.sh ...` for the final PDF.

The "Local overrides" block at the bottom of `deliverome-print.css`
is where one-off tweaks land — keeps the imported tokens clean.

## .docx → polish tips

These are the Word-side things that translate cleanest to the
print layout:

- **Use Word heading styles**, not bold body text. Pandoc maps
  Word's H1 / H2 / H3 to `<h1>` / `<h2>` / `<h3>`, and the CSS
  hangs the section-heading treatment off those.
- **Figure captions** in Word: style them as Heading 5, starting
  `Figure 1. <caption>`. Bold the lead clause — the figure label plus
  the title sentence, exactly as
  `data/analysis/figures/<slug>.caption.md` writes it — and both
  editions print that clause in brand maroon. `figures.lua` falls back
  to finding the clause itself (label + first sentence) when the bold
  is missing, and reports at build time any caption where even that
  failed.
- **Tables**: native Word tables work; pandoc emits real `<table>`
  markup. Don't paste tables in as images.
- **Italics** (gene names): survive intact through to JATS.
- **Bold key terms**: render as semibold in print, which keeps the
  page light.

## Figures — automatic swap to the canonical render

Between pandoc HTML and WeasyPrint PDF, the build runs a **figure-swap
step** that replaces each in-document `<img>` with the canonical
render per `paper/figure_manifest.json`. This means: **whatever bitmap
is pasted into the `.docx` is ignored** — the published PDF always
carries the HEAD-of-main render of each figure (same artifact the
viewer, the gist, and the Zenodo deposit point at). The swap matches
on the anchor id pandoc emits for each figure caption — `figure-N` for
main figures, `appendix-figure-N` for appendix figures.

Assets resolve against a two-directory **search path**, first match
wins:

| Order | Directory | What belongs there |
|---|---|---|
| 1 | `paper/figures/` | Print-ready *derived* assets — chiefly vector SVGs converted from the canonical PDFs with `pdftocairo -svg`. |
| 2 | `data/analysis/figures/` | The curated figure library (`.pdf` + `.png` + `make_<slug>.py`). |

The split exists so the print build can carry a print-specific
rendition without mutating the curated library, whose README defines
its own admission criteria.

> **Never point the manifest at a `.pdf`.** WeasyPrint ships no PDF
> image decoder, so `<img src="fig.pdf">` renders as a silently blank
> box — no error, just a missing figure. Convert to SVG instead:
>
> ```bash
> pdftocairo -svg data/analysis/figures/my_fig.pdf paper/figures/my_fig.svg
> ```
>
> `format: "pdf"` is rejected by the validator for exactly this reason.

**Vector vs raster.** Prefer SVG; fall back to a ≥600 DPI PNG when the
vector is pathological. Figure 6 (`deep_dive_record_richness`) is the
worked example: it plots one dot per gene (n = 5,130 across five
panels), so its SVG is ~20 MB and slow to render, while its 600-DPI
PNG is 14,659 px wide — far past what print needs.

To add a new figure to the manifest:

```json
{
  "figures": {
    "3": {
      "slug": "my_new_figure",
      "format": "png",
      "min_dpi": 600,
      "description": "Author-facing only"
    }
  }
}
```

The build validates every swapped asset:

- **PNG** → file must exist and Pillow-reported DPI ≥ `min_dpi`
  (default 600). Matplotlib writes 599.9988 for 600 — the validator
  rounds, so this passes cleanly.
- **SVG** → root element must be `<svg>`. Soft-warns if the SVG
  wraps a base64 raster (the embedded bitmap then keeps its own
  resolution; the SVG wrapper isn't "vector at any zoom").
- **PDF** → always rejected; see the callout above.

A figure with **no** manifest entry is left alone — the `.docx`
bitmap survives into the PDF and the swap logs
`no manifest entry for key 'N'`. That's the right fallback for a
figure with no canonical asset yet (currently Figure 7, the viewer
screenshot); see `_pending` in the manifest.

Default mode warns and keeps the build moving. Pass `--strict-figures`
to escalate any unresolved issue (missing canonical asset, PNG below
DPI threshold, etc.) into a build error:

```bash
uv run python paper/build.py --strict-figures my_manuscript.docx
```

You can also run the validator standalone, without a `.docx`:

```bash
uv run python paper/figure_swap.py            # report issues
uv run python paper/figure_swap.py --strict   # exit 1 on any issue
```

### Alert: figures that changed since the .docx

Swapping in the canonical render means the PDF can carry a figure the
manuscript never showed you. So before each swap the build compares the
figure the .docx embedded with the render replacing it, and flags any that
visibly differ:

- the swap log prints `compared with the .docx: N changed, M unchanged, K not
  compared`, and the build **ends** with a `⚠⚠ N FIGURE(S) DIFFER FROM THE
  VERSION IN THE .DOCX` block listing each one, so it can't scroll past;
- each changed figure gets an old | new | difference image (differing pixels
  marked red) in `<docx-dir>/build/figure-changes/`.

The comparison is built to ignore what the .docx round-trip does to a pasted
image (downscaling, JPEG re-compression, a flattened transparent background):
an unchanged figure scores 0 differing pixels, while a single edited number
still scores hundreds. Vector (SVG) entries are compared through the sibling
`<slug>.png` every published figure ships; a figure with no PNG is reported
as "not compared" rather than silently passed. The alert never fails the
build; review the listed figures before publishing.

## Cross-reference links

The build synthesises clickable in-PDF cross-references from the prose,
because Google Docs exports its cross-references as plain text — the
`.docx` carries 64 bookmarks but zero `w:anchor` hyperlinks pointing at
them, so there is nothing to preserve.

Two filters, applied in this order (`sections.lua` must run second — it
indexes the headings that `figures.lua` leaves behind):

| Filter | Turns into a link | Example |
|---|---|---|
| `filters/figures.lua` | `Figure N`, `Appendix Figure N` | "…as shown in **Figure 3**." |
| `filters/sections.lua` | Section names: Methods, Results, Discussion, Introduction, Abstract, Data availability, Code availability | "…(see **Methods**)" |

Section links fire in **body text and figure captions** alike — three of
the draft's six "Methods" references live inside captions, which pandoc
emits as `<h5>`, not `<p>`. A heading whose own text *is* a section name
is skipped so "Methods" never links to itself.

**Supplementary references are deliberately left as plain text.**
`Figure S3`, `Table S1` and friends live in a separate supplementary
file, so an intra-document anchor would be a dead link — worse than
plain text, because it looks clickable and goes nowhere. If the
supplement is ever merged into the main file, drop the
`SUPPLEMENTARY_PATTERNS` guard in `sections.lua` and add
`figure-sN` anchors.

If a section name matches **more than one** heading the reference is
left unlinked and a warning goes to stderr — the draft currently has a
duplicated `Web viewer and public API` H3, which is the kind of thing
this catches.

## Citations

If you're using **Zotero in Word**, leave citations alone — Zotero
bakes the formatted citation text and bibliography into the `.docx`,
and pandoc carries that through into both the PDF and JATS as plain
text. That's plenty for a Zenodo deposit.

Switching to pandoc-managed citations (structured `<ref>` elements
in JATS) requires exporting a `.bib` and toggling Zotero's Word
plugin from "Word fields" → "BibTeX cite keys" mode. Skip unless you
specifically need it.

## Math

WeasyPrint doesn't render LaTeX math. If your manuscript has
equations, the simplest workflow is:

1. Edit equations in Word's equation editor.
2. Render the build, accept that equations come through as their
   text representation.
3. For a publication-grade equation layout, escalate to the LaTeX
   template option in [`../scripts/release/README.md`](../scripts/release/README.md)
   under "manuscript bundle".

For figures + tables + body text + footnotes, WeasyPrint is plenty.

## Wiring this into the Zenodo deposit

Once you've built the PDF + JATS, uncomment the `manuscript`
entry in `EXTRA_FILES` at the bottom of
[`scripts/release/publish-archive.py`](../scripts/release/publish-archive.py):

```python
{
    "manuscript": True,
    "source": "paper/manuscript.docx",
    "pdf_path": "paper/build/manuscript.pdf",
    "jats_filename": "manuscript.xml",
    "extra_pandoc_args": [],
},
```

The publish script copies the PDF verbatim and runs its own pandoc
JATS conversion. The PDF in the deposit will match exactly what
WeasyPrint produces here.
