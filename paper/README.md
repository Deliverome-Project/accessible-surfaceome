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
| Tables | Maroon-blush header row, dark border under header |
| Block quotes | Maroon-blush background with maroon side rule |
| Footer | "Deliverome" left, page number right, both maroon |

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
- **Figure captions** in Word: write them as standalone paragraphs
  starting `Figure 1. <caption>`. Pandoc spots that pattern and
  emits `<figure><figcaption>` correctly.
- **Tables**: native Word tables work; pandoc emits real `<table>`
  markup. Don't paste tables in as images.
- **Italics** (gene names): survive intact through to JATS.
- **Bold key terms**: render as semibold in print, which keeps the
  page light.

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
