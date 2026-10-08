# PDF objects test

A test for colour themes in PDF. It's a pair of files, light and dark, built from one source. Between them they hold every kind of object a PDF 2.0 file can contain and a viewer can show. The two builds draw the same objects in the same order and differ only in their colours. That makes them the input `pdf-themes merge` expects, and a check of every place a colour can live.

## Files

| File | What it is |
|---|---|
| `out/objects-light.pdf`, `out/objects-dark.pdf` | The main pair: 31 pages and 269 test tiles. PDF 2.0, clean in qpdf and checked against the Arlington PDF model. |
| `out/legacy-light.pdf`, `out/legacy-dark.pdf` | PDF 1.7. Covers what PDF 2.0 no longer allows but real files still carry, all drawn by the viewer: annotations and fields without appearance streams, NeedAppearances, standard 14 fonts without metrics, and a form XObject without Resources. |
| `out/portfolio-light.pdf`, `out/portfolio-dark.pdf` | A portable collection, with the Collection's own colours (background, cards, text), a schema, folders, sort and split. |
| `out/objects-light-encrypted.pdf`, `out/objects-dark-encrypted.pdf` | The main pair with AES-256 encryption and an empty user password. |
| `out/objects-light-signed.pdf` | The light build with an approval signature from a self-signed test certificate. The signature is valid but untrusted. |
| `out/figures/` | The scientific figures on their own, light and dark, exactly as matplotlib and pdflatex wrote them. Each pair is a small, real-world input for `pdf-themes merge`. |
| `out/COVERAGE.md`, `out/coverage.json` | Every tile, the ISO 32000-2 tables it exercises, and what a theme should do with it. |
| `out/audit.txt` | The audit's counts against the full lists in ISO 32000-2. |

## Reading a page

Each tile tests one thing. Its heading names the object, the line under it gives the ISO 32000-2 tables, and the chip says what a theme should do:

- **swaps**: the theme must change it. The dark build shows the intended result.
- **stays**: photos, print-production marks and media keep their colours in every theme.
- **viewer**: the viewer draws it from entries in the file, so the viewer has to follow the theme.

The bookmarks list every page and every tile, and the appendix has the full coverage table.

## What's covered

The audit (`tools/audit.py`) finds these in the main pair:

- All 28 annotation types and all 20 action types current in PDF 2.0.
- All 11 colour space families, including Indexed over Lab and ICC, Separation with All and None, DeviceN and NChannel, and Display P3 and FOGRA39 profiles.
- All 7 shading types, all 4 function types, and both pattern types, coloured and uncoloured.
- Every image filter. Crypt is in the encrypted pair.
- All 7 font types and all 6 ways of storing a font, from not embedded to OpenType. Vertical CJK text and Type 3 glyphs that set their own colours are both included.
- All 5 halftone types, all 16 blend modes, all 8 text render modes and all 73 content stream operators.
- All 14 kinds of form field. Each has an appearance drawn in the theme's colours, and its MK and DA entries say the same.
- Optional content with usage, auto-state, radio-button groups, locked layers and visibility expressions.
- Multimedia (Screen, RichMedia, Movie, Sound), a U3D model with three views, and a projection annotation.
- Measurement and geospatial viewports, page boxes with BoxColorInfo, thumbnails, transitions, article threads, navigation steps, document parts, page labels and output intents.
- Tagged structure: tables, lists, footnotes, ruby, formulas with MathML, and the Layout attributes that carry colour.
- Scientific figures, imported as made by matplotlib 3.11 and pgfplots:
  - plots: lines, scatter, error bars, hatching, heatmaps with colour bars, a Gouraud mesh, contours, a 3D surface, a mass spectrum, a rasterised layer, a spectrogram;
  - RF plots: a Smith chart, a constellation, an eye diagram, an antenna pattern;
  - other content: a false-colour image with a scale bar, a pgfplots surface, LaTeX equations, 100,000 points in one path, a chemical structure, and a results table whose colours mean pass and fail;
  - the data behind one plot, attached to its Figure element.

It also finds every colour-bearing key in ISO 32000-2, as listed by the Arlington model, apart from vendor extensions. The portfolio's colour keys are in the portfolio pair. That covers the 3D background, render mode, cross-section and measurement colours, BoxColorInfo, outline colours, MK BG and BC, annotation C, IC, DA, DS, RC and RV, the media window background, the structure attribute colours, shading Background, soft mask BC and the Indexed thumbnail.

## Scientific figures

The figures on pages 25 and 26 come from one script per tool, run once with light colours and once with dark. Only the colours change. That's the plotting tools' own theming: matplotlib style settings, pgfplots styles. The pair is merged afterwards, like the rest of the test.

- **Data colour maps stay when they work on both papers.** Examples are viridis, inferno and the ion image's colour scale, with the scale bar burnt into the image.
- **Diverging maps swap.** A white midpoint glares on dark paper, so the dark build uses berlin, one of the dark-midpoint maps matplotlib 3.10 took from Crameri's Scientific colour maps. Matplotlib writes a heatmap as an Indexed image whose palette and indices both change with the map, so the merge needs a whole image per theme there, not just a palette.
- **Matplotlib leaves out colour operators that don't change the colour.** The light build writes `1 G 1 g` and the dark build just `0 g`. So the two builds of one figure don't have the same operator list. `pair_check.py` ignores colour operators for this reason, and a merge has to compare what's painted rather than match operators one for one.
- **One change to the figures as written:** matplotlib's marker XObjects have no Resources, which PDF 2.0 requires. The import gives them an empty dictionary.

## Not included

- XFA forms: deprecated in PDF 2.0.
- PostScript XObjects and the PS operator: removed in PDF 2.0.
- Web Capture and alternate presentations: they draw nothing.
- JBIG2 symbol dictionaries: there's no encoder to hand. Generic regions are tested.
- 3D PRC streams: there's no PRC writer to hand. The U3D stream carries the same PDF-side colours.

## Building

The PDFs are committed, so you only need this to change the test.

```
pip install pikepdf pymupdf pypdfium2 fonttools numpy pillow reportlab pyhanko matplotlib
python3 -m objtest.build out      # the main pair, COVERAGE.md and coverage.json
python3 -m objtest.legacy out     # the legacy pair
python3 -m objtest.variants out   # portfolio, encrypted and signed files
```

It needs these fonts installed:

- DejaVu Sans, Sans Mono and Serif
- Inter
- Noto Sans CJK and Noto Color Emoji
- Bitstream Charter (Type 1, from TeX Live)

The scientific pages also need pdflatex with pgfplots. The sRGB and FOGRA39 profiles come from TeX Live. The video, tone and 3D model are in `assets/` (see `assets/NOTICE.md`).

## Checking

```
python3 tools/pair_check.py out/objects-light.pdf out/objects-dark.pdf
python3 tools/audit.py out/objects-light.pdf --arlington path/to/arlington-pdf-model
python3 tools/render.py out/objects-light.pdf out/objects-dark.pdf --dpi 60
```

- `pair_check.py` compares every content stream in the two builds and fails if anything but a colour differs. That covers pages, forms, patterns, Type 3 glyphs and appearance streams. Colour operators are left out of the comparison: see the matplotlib note above.
- `audit.py` counts what the file contains against the lists in ISO 32000-2, read from the PDF Association's Arlington model when you point it there.
- `render.py` draws each page in Poppler, MuPDF, PDFium and pdf.js side by side. Poppler comes from `pdftoppm`, and pdf.js runs through Node (`npm install pdfjs-dist @napi-rs/canvas` in `tools/`, or set `PDFJS_NODE_MODULES`).

## What the engines do with it

From renders in Poppler 24.02, MuPDF 1.28.2, PDFium 153 and pdf.js 6.2:

- **Link borders:** only Poppler draws them from C when it renders a page. The others leave them to their UI.
- **Annotations without appearances (legacy pair):** every engine handles these differently.
  - PDFium draws every note icon yellow, whatever C says.
  - When it renders to a canvas, pdf.js draws the shapes and text markup but skips the note icons, free text, stamps and attachments.
  - MuPDF and PDFium fill a free text annotation with its C.

  A theme can't count on viewers recolouring these, which is a good argument for requiring appearance streams in themed files.
- **Highlights:** a highlight using Multiply vanishes on dark paper. The dark build swaps in Screen, so a theme has to be able to swap blend modes as well as colours.
- **UserUnit:** PDFium ignores it.
- **Transfer functions:** none of the four applied TR in these renders.
- **ZapfDingbats:** Poppler needs the font installed to draw the check box marks.
