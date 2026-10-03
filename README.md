# pdf-themes

Colour themes for PDF: one file, its content stored once, with light, dark,
higher contrast and tinted themes, each checked before it goes in.

PDF readers that offer a dark mode make it up themselves. They invert the page
or swap its colours, which spoils colour designs and charts, because the file
never says what each colour is for. Readers who need tinted backgrounds or
more contrast get the same treatment. This project tries another way. Every
colour in the file becomes an entry in a small palette, and a theme is another
set of palettes, plus any gradient, opacity or colour value that also changes.
A reader that knows about themes swaps those few objects. A reader that
doesn't shows the default colours, exactly as today.

Choosing a theme is a view setting, like draft mode: it changes how the pages
are drawn, never what they say.

It's a proof of concept for a proposal to the PDF Association. The draft
specification is in [SPEC.md](SPEC.md).

## Results

Three documents: my CV and a test page, each built twice with Typst (light and
dark), and a test document written to use every way a PDF can carry colour
(`tools/corpus.py`, six pages). Every file was saved the same way, with
compressed object streams, so the sizes compare fairly.

| | CV, 2 pages | Test page | Test document, 6 pages |
| --- | --- | --- | --- |
| Light build | 51,273 bytes | 187,564 bytes | 135,140 bytes |
| Themed file, Light and Dark | 51,902 (+1.2%) | 185,965 (−0.9%) | 186,480 (+38%) |
| Themed file, all 8 themes | 52,880 (+3.1%) | 186,382 (−0.6%) | 198,557 (+47%) |
| Both builds as layers, as an author can do today | 64,945 (+26.7%) | 192,715 (+2.7%) | 193,597 (+43%) |
| Light theme against the light build | identical | identical | identical |
| Dark theme against the dark build | identical | identical | identical |
| Colour values outside the page (annotations, fields, bookmarks, tags) | none in the file | none in the file | 42 of 42 the same |
| Themes that passed their contrast check | 8 of 8 | 8 of 8 | 8 of 8 |

"Identical" means every pixel, at 144 dpi, in Poppler 24.02, MuPDF 1.28.2 and
PDFium 153 (the engine in Chrome). There's one exception, and it's PDFium's:
on the test document's swatch for "a colour space set with no colour", PDFium
keeps the previous colour, where the PDF specification says the space's
initial colour applies. Poppler and MuPDF follow the specification. The themed
file writes the colour out, so PDFium draws it like the others there.

The test document is built to be hard. Two of its images change completely
between builds, and those have to be stored twice. On real documents the
themed file costs a few per cent.

Organising a single build (no dark build at all) and adding the standard
themes took the test document from 135,140 to 160,068 bytes, with the default
look unchanged pixel for pixel. `results/` has every number and contact sheets.
The CV figures come from an earlier run that saved files with slightly larger
metadata; its build and themed files were saved the same way as each other,
so the percentages still compare.

Scanned pages work too. `tools/scan.py` draws the test page at 150 dpi in
grey and saves it as a JPEG inside a PDF, as a scanner would, so the file has
no text and no vector colour at all. The themed file keeps the JPEG exactly as
it was, costs 4,755 bytes (3.6%) for all eight themes, and its default look is
the same pixel for pixel in all three engines.

## Try it

```
pip install -e ".[dev]"
pytest
python tools/run.py            # build, merge and measure the test page into out/
python tools/check_corpus.py   # the six-page test document, every object type
python tools/scan.py           # a scanned page, themed from the scan alone
```

The command line:

```
pdf-themes typst document.typ -o themed.pdf --dark-paper 1C1C1E
pdf-themes merge light.pdf dark.pdf -o themed.pdf --dark-paper 1C1C1E
pdf-themes add document.pdf -o themed.pdf
pdf-themes info themed.pdf
pdf-themes apply themed.pdf --theme Cream -o cream.pdf
pdf-themes check document.pdf
```

`typst` compiles a Typst document twice, with `--input mode=light` and
`--input mode=dark`, and merges the two builds. It runs the `typst` program if
it's installed, or the typst Python package, and passes on `--root`,
`--font-path`, `--pdf-standard` and any other `--input`. `merge` takes two
builds that draw the same shapes and differ only in paint. `add` takes a
single PDF and works out every theme from it, Dark included. All three add
the standard themes by default, check each one by drawing it, and leave out
any that fail or that would draw every page exactly like the default. `apply`
does what a theme-aware reader would and saves the result as a plain PDF, so
any reader can show it.

The live demo in `demo/` opens a themed PDF in the browser and follows the
system's dark mode. Serve the folder and open it:

```
cd demo && python -m http.server 8000
```

## The standard themes

| Theme | Labels | Who it's for |
| --- | --- | --- |
| Light | ColorScheme Light | The author's design. |
| Dark | ColorScheme Dark | Light sensitivity, glare, reading at night, some low vision. The author's dark build if there is one, otherwise worked out from the light one. |
| Light, more contrast | Light, Contrast More | Low vision. Text is held to 7:1 (WCAG 1.4.6, level AAA). |
| Dark, more contrast | Dark, Contrast More | Low vision with light sensitivity. Also 7:1. |
| Cream, Peach, Yellow, Turquoise | Light, Tint | Many readers with dyslexia or visual stress find a tinted background easier. People differ in which tint helps, so there's a range. |

The labels let a reader remember a person's choice from one document to the
next, and match it to the system setting. The research behind the list is in
the proposal.

## How it works

`merge` walks the content streams of the two builds side by side.

- **Colours.** Every solid colour, in any colour space, becomes an entry in an
  Indexed palette. The page then says `/Th0 cs 15 sc` where it said
  `0.604 0.125 0.714 scn`. A colour is written just before the operator that
  paints with it, so text, fills and strokes get their own entries. That's
  what lets a theme strengthen text without touching a highlight of the same
  colour.
- **Inside other objects.** Form XObjects, tiling patterns, Type 3 glyphs,
  annotation appearances and soft mask groups are walked the same way, so
  their colours join the palettes.
- **Whole objects.** A gradient, graphics state or image that differs gets
  its own copy, and the theme lists the copy and its other version as a pair
  to swap. An image with the same shapes in both builds is stored once, as
  palette indices, with a palette per theme.
- **Outside the page content.** Annotation, form field, bookmark, structure
  attribute and portfolio colours are moved into their own objects so a theme
  can replace them.
- **Scanned pages.** A grey image that looks like a page (mostly paper, few
  mid-greys) gets an Indexed colour space whose entries are its own greys. It
  draws exactly as before and its data, often a JPEG, isn't touched. A theme
  swaps that palette for one running from the theme's ink to its paper, so
  the scanned page's white becomes the theme's paper. Every scan in a file
  shares the one palette.
- Text, paths, tags and fonts must match exactly. The merge stops with an
  error at the first place the builds draw something different.

The themes then sit in the catalog under `/XXThemes`:

```
/XXThemes <<
  /Default << /Type /Theme /Name (Light) /ColorScheme /Light /Paper [1 1 1] /Checked << ... >> >>
  /Alternates [ << /Type /Theme /Name (Dark) /ColorScheme /Dark /Paper [0 0 0]
                   /Replace [ 67 0 R 230 0 R  68 0 R 220 0 R ... ] >>
                << /Type /Theme /Name (Cream) /ColorScheme /Light /Tint /Cream
                   /Paper [0.988 0.953 0.855] /Replace [ ... ] >> ... ]
>>
```

`apply` swaps each pair in `Replace`, so anything that pointed at the first
object now gets the second. In the demo that's about ten lines of JavaScript.

Derived themes (`pdfthemes/derive.py`) are new versions of the palettes,
gradients and colour values, worked out in OKLCH. Light surfaces take the tint
or go dark, text keeps its hue and moves in lightness until it reaches its
contrast target, and in a dark theme a highlighter's Multiply blend becomes
Screen. Each theme is then drawn with PDFium and every run of text is measured
against what's behind it. Colours that fall short are fixed and the theme is
drawn again, up to four times. Where text is already as light or as dark as it
can go, what's behind it moves instead. A theme that would draw every page
exactly like the default is left out, and a theme with no text to measure is
kept without a `Checked` entry.

## Making a document themeable

Build it once per theme with the same layout. In Typst that's an input:
`typst compile --input mode=dark`, and `pdf-themes typst` runs both builds and
merges them. Then make sure both builds draw the same shapes:

- if one theme fills something with a gradient, the other must use a gradient
  too (one with every stop the same colour works);
- if one theme strokes an outline, the other must stroke it too, fully
  transparent if it shouldn't show. In Typst a block's stroke also changes its
  fill's corner radius, so this matters even when nothing else changes;
- the same goes for glows and other layered effects.

With no dark build, `pdf-themes add` works one out.

## Limits

- Derived themes read every three-channel ICC profile as sRGB and write their
  colours in sRGB. Author-made themes keep wide-gamut colours such as Display
  P3 exactly; derived ones would lose the most saturated.
- A gradient or image that differs between builds is swapped whole.
- From a single build, an image is recoloured only when it looks like a
  drawing on white (a chart, a diagram) or a grey scan of a page, never a
  photo.
- An annotation whose opacity differs between builds is swapped whole, because
  pikepdf can't make a number an indirect object. The specification allows
  either.
- On a scanned page, Dark turns the whole scan light on dark, so a photo on
  it becomes a negative. Only grey scans are themed. A colour scan keeps its
  colours, and themes that would change nothing are left out.
- pdf.js draws the default theme of a JPEG scan within one level of the
  original on a few per cent of pixels. It lets the browser decode a plain
  grey JPEG but decodes one with a palette itself, and the two decoders round
  differently.
- Uses the private key `/XXThemes`. Files shared beyond testing should use a
  registered developer prefix until a standard key exists.

## PDF/A and PDF/UA

Typst writes PDF/A-2b and PDF/UA-1. Themed versions of the test page in each,
and in both at once, keep their XMP metadata byte for byte, their output
intent, structure tree and marked content, and use no colour space the build
didn't already use (`tools/conformance.py build.pdf themed.pdf`). That covers
what theming touches, but it isn't a full validation. That needs veraPDF,
which couldn't be installed where this was built.

## Licence

Apache 2.0, see [LICENSE](LICENSE). `demo/vendor` holds pdf.js (Apache 2.0)
and pdf-lib (MIT) under their own licences, and `examples/fonts` holds Inter
(SIL Open Font Licence).
