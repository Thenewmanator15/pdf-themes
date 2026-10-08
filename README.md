# pdf-themes

Colour themes for PDF: one file, its content stored once, with the light,
dark, higher contrast and tinted themes its author built, each checked before
it goes in.

PDF readers that offer a dark mode make it up themselves. They invert the page
or swap its colours, which spoils colour designs and charts, because the file
never says what each colour is for. Readers who need tinted backgrounds or
more contrast get the same treatment. This project tries another way. The
author builds the document once per theme, with its charts and pictures
adjusted for each, and the builds are merged into one file. Every colour in
the file becomes an entry in a small palette, and a theme is another set of
palettes, plus any gradient, opacity or colour value that also changes. A
reader that knows about themes swaps those few objects. A reader that doesn't
shows the default colours, exactly as today.

Choosing a theme is a view setting, like draft mode: it changes how the pages
are drawn, never what they say.

It's a proof of concept for a proposal to the PDF Association. The draft
specification is in [SPEC.md](SPEC.md).

## Results

Every file here was saved the same way, with compressed object streams, so
the sizes compare fairly.

Themes built from source, one build per theme:

| | Theme lab, 1 page of plots | Objects test, 31 pages |
| --- | --- | --- |
| Builds | 8, one per standard theme | 2, light and dark |
| Light build | 38,318 bytes | 1,900,431 bytes |
| Themed file, Light and Dark | 38,801 (+1.3%) | 1,943,737 (+2.3%) |
| Themed file, all 8 themes | 39,718 (+3.7%) | |
| The builds as separate files | 304,725 | 3,800,176 |
| Each theme against its own build, in PDFium | identical | identical but for page 2 |
| Themes that passed their contrast check | 8 of 8 | see below |

The theme lab (`tests/theme-lab`) is a Typst document with Lilaq plots. It
sets its paper, text and rule colours per theme and fits each plot's series
colours to the paper. The objects test (`tests/objects`) holds every kind of
object a PDF 2.0 file can contain. Page 2 is its colour spaces page: colours
written as decimals in Lab, calibrated and ICC spaces go through 8-bit
palettes, and land up to 4 levels out of 255 away in light and 1 in dark. It
also has text that is faint on purpose, so neither of its themes is marked as
checked.

The first prototype measured a test page built twice with Typst (light and
dark) and a test document written to use every way a PDF can carry colour
(`tools/corpus.py`, six pages). In these the six themes beyond light and dark
were worked out by the tool:

| | Test page | Test document, 6 pages |
| --- | --- | --- |
| Light build | 187,564 bytes | 135,140 bytes |
| Themed file, Light and Dark | 185,965 (−0.9%) | 186,480 (+38%) |
| Themed file, all 8 themes | 186,382 (−0.6%) | 198,557 (+47%) |
| Both builds as layers, as an author can do today | 192,715 (+2.7%) | 193,597 (+43%) |
| Light theme against the light build | identical | identical |
| Dark theme against the dark build | identical | identical |
| Colour values outside the page (annotations, fields, bookmarks, tags) | none in the file | 42 of 42 the same |
| Themes that passed their contrast check | 8 of 8 | 8 of 8 |

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
pdf-themes typst document.typ -o themed.pdf --modes light,dark,light-contrast,cream
pdf-themes merge --theme Light=light.pdf --theme Dark=dark.pdf --theme Cream=cream.pdf -o themed.pdf
pdf-themes merge light.pdf dark.pdf -o themed.pdf --dark-paper 1C1C1E
pdf-themes add document.pdf -o themed.pdf
pdf-themes info themed.pdf
pdf-themes apply themed.pdf --theme Cream -o cream.pdf
pdf-themes check document.pdf
```

`typst` compiles a Typst document once per mode, with `--input mode=light`,
`--input mode=dark` and so on, and merges the builds. Each mode is a standard
theme: light, dark, light-contrast, dark-contrast, cream, peach, yellow and
turquoise. Without `--modes` it builds light and dark. It runs the `typst`
program if it's installed, or the typst Python package, and passes on
`--root`, `--font-path`, `--pdf-standard` and any other `--input`.

`merge` takes one build per theme, the default first. The builds must draw
the same shapes and text and differ only in paint. A standard name brings its
labels and paper colour, `--paper Dark=1C1C1E` changes a paper, and any other
name gives its own labels: `--theme "Night=night.pdf;scheme=Dark;paper=0B0C10"`.

Both commands put in the themes you built and nothing else. Each theme is
drawn and its text contrast measured. One that passes is marked as checked.
One that fails is still written, unmarked, with a list of the text that fell
short, and its colours are left alone: fixing it is for you, in the source.

`--derive` is the fallback for when you only have a light and a dark build: it
works the other six standard themes out from them and leaves out any that
fail. `add` does the same from a single PDF with no source at all, Dark
included. `apply` does what a theme-aware reader would and saves the result
as a plain PDF, so any reader can show it.

The live demo in `demo/` is a viewer that loads the themes stored in a PDF.
It lists the themes it finds in the file, shows the one that matches the
system's light or dark setting, and switches when you pick another. Nothing
is worked out in the viewer: every colour it shows comes from the file. Serve
the folder and open it:

```
cd demo && python -m http.server 8000
```

## The standard themes

| Theme | Labels | Who it's for |
| --- | --- | --- |
| Light | ColorScheme Light | The author's design. |
| Dark | ColorScheme Dark | Light sensitivity, glare, reading at night, some low vision. |
| Light, more contrast | Light, Contrast More | Low vision. Enhanced contrast: text is held to 7:1 (WCAG 1.4.6 Contrast (Enhanced), level AAA). |
| Dark, more contrast | Dark, Contrast More | Low vision with light sensitivity. Also 7:1. |
| Cream, Peach, Yellow, Turquoise | Light, Tint | Many readers with dyslexia or visual stress find a tinted background easier, which is what a coloured overlay is for. People differ in which tint helps, so there's a range. |

The other themes are held to 4.5:1 (WCAG 1.4.3 Contrast (Minimum), level AA).
The labels follow the CSS preferences `prefers-color-scheme` and
`prefers-contrast`, and forced colours, such as a Windows contrast theme,
still win when they're turned on. Offering a set of checked themes is a way
to meet WCAG 1.4.8 Visual Presentation, which asks that the person can select
foreground and background colours.

This is the set an author is asked to build. The labels let a reader
remember a person's choice from one document to the next, and match it to the
system setting. The research behind the list is in the proposal.

## How it works

`merge` walks the content streams of two builds side by side. With more than
two, it merges the first two, then merges each further build into the result
and carries the earlier themes' replacements across.

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
`typst compile --input mode=dark`, and `pdf-themes typst --modes ...` runs
every build and merges them. Set each theme's colours in the source, charts
and pictures included, as `tests/theme-lab/theme-lab.typ` does. Then make
sure every build draws the same shapes and the same text:

- if one theme fills something with a gradient, the other must use a gradient
  too (one with every stop the same colour works);
- if one theme strokes an outline, the other must stroke it too, fully
  transparent if it shouldn't show. In Typst a block's stroke also changes its
  fill's corner radius, so this matters even when nothing else changes;
- the same goes for glows and other layered effects.

A build that prints its own theme's name, or a figure worked out from its
colours, has different text from the others and won't merge.

With no source to build from, `pdf-themes add` works the themes out.

## Limits

- Derived themes read every three-channel ICC profile as sRGB and write their
  colours in sRGB. Author-made themes keep wide-gamut colours such as Display
  P3 exactly; derived ones would lose the most saturated.
- A gradient or image that differs between builds is swapped whole. An image
  with the same shapes in the first two builds is stored once with a palette
  for each, but a third theme that changes it gets its own copy.
- Worked-out themes are fragile on a large file. On the 31-page objects test
  all six fail their check and are left out, where on its first page alone
  all six pass. Themes built from source don't have this problem.
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
- Only text contrast is checked. Chart lines, icons and other graphics, which
  WCAG 1.4.11 Non-text Contrast holds to 3:1, aren't measured yet.
- Uses the private key `/XXThemes`. Files shared beyond testing should use a
  registered developer prefix until a standard key exists.

## PDF/A and PDF/UA

Typst writes PDF/A-2b and PDF/UA-1. Themed versions of the test page in each,
and in both at once, keep their XMP metadata byte for byte, their output
intent, structure tree and marked content, and use no colour space the build
didn't already use (`tools/conformance.py build.pdf themed.pdf`). That covers
what theming touches, but it isn't a full validation. That needs veraPDF,
which couldn't be installed where this was built.

PDF/UA covers structure and tagging and leaves colour contrast to WCAG, so
the two sit side by side: the tags are the same in every theme, and each
theme records the WCAG success criterion it was checked against.

## Licence

Apache 2.0, see [LICENSE](LICENSE). `demo/vendor` holds pdf.js (Apache 2.0)
and pdf-lib (MIT) under their own licences, and `examples/fonts` holds Inter
(SIL Open Font Licence).
