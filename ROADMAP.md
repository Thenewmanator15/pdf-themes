# Roadmap: what is supported, and the work to do

4 November 2026. What each part of pdf-themes supports today, and the development work still needed in the specification, the tool, the contrast check and the PDF apps that would show themes. The site's [Limits page](https://thenewmanator15.github.io/pdf-themes/limits/) explains the gaps in plain words; this is the developer's version.

Status words: **Yes** works on `main`; **Partly** works with the limit given; **No** not done; **Planned** designed, not built; **Open** waiting on a decision in the specification.

## Support by kind of content

The parts are the specification (`SPEC.md`), `pdf-themes merge` (themes built from source, one build per theme), `pdf-themes add` (themes worked out from one build), the contrast check (`pdfthemes/contrast.py`) and the viewer on the site (`demo/site/viewer.js`).

| Content | Spec | merge | add | Check | Viewer |
| --- | --- | --- | --- | --- | --- |
| Solid colours in page content, any colour space | Yes | Yes | Yes | Yes, text | Yes |
| Colours inside forms, tiling patterns, Type 3 glyphs, annotation appearances and soft mask groups | Yes | Yes | Yes | Yes, text | Yes |
| Gradients, all 7 shading types | Yes, whole replacement with the same geometry | Yes, swapped whole | Yes | Partly: text on a gradient is measured, text filled with one isn't | Yes |
| Opacity and blend modes | Yes | Yes | Yes | Yes, text drawn at less than full opacity is measured as drawn | Yes |
| Images with the same shapes in every build | Yes | Yes, stored once as palette indices | Yes, Indexed images | n/a | Yes |
| Inline images | Yes, written as image objects | Yes | Not checked | n/a | Yes |
| Photos and screenshots | Yes, a whole image per theme | Yes when the builds differ, swapped whole | No: only drawings on white and grey scans are recoloured | n/a | Yes |
| Grey scans | Yes | Yes | Yes | n/a | Yes |
| 1-bit scans (JBIG2, fax) | Yes | Yes when the builds differ | No | n/a | Yes |
| Colour scans | Yes | Yes when the builds differ | No | n/a | Yes |
| Images whose soft mask has a Matte | Open (rule not written) | Kept as they are, or swapped whole | No | n/a | Yes |
| Annotation, field, bookmark, structure attribute and portfolio colours | Yes | Yes | Yes | Text in appearances | Yes |
| An annotation whose opacity differs | Yes, swapped whole | Yes, swapped whole | Yes | n/a | Yes |
| Comments and fields with no stored appearance | Open (question 6) | n/a | n/a | No | Up to pdf.js |
| Page thumbnails | Yes | Yes | Not checked | n/a | n/a |
| Paper colour | Yes | Yes | Yes | Yes | Yes |
| Wide-gamut colours (Display P3) | Yes | Yes, kept exactly | Partly: worked out as sRGB | Yes | Yes |
| Colour fonts (colour emoji) | No (question 15) | No | No | No | No |
| Colours set by JavaScript | No (question 16) | No | No | No | No |
| Inside 3D models, video and sound | No (question 17) | No | No | No | No |
| Line widths and dashes | Yes, up to twice the width (R5.3-11, 6.4) | No | No | No | No |
| PDFs attached or in a portfolio | No (question 18); the portfolio's own colours are Yes | No | No | No | No |

## Support in the contrast check

| Check | Status |
| --- | --- |
| Text against what's behind it, WCAG 1.4.3 (4.5:1) and 1.4.6 (7:1), at the size it's drawn | Yes |
| Text across two backgrounds | Partly: measured against the one it contrasts with best (fault 16) |
| Text drawn as outlines (matplotlib) | No: not seen as text |
| Text filled with a gradient | No: counted in the report, doesn't stop the mark (question 14) |
| Lines and shapes, WCAG 1.4.11 (3:1) | Partly: listed for the author, don't decide the mark (question 13) |
| Meaning carried by colour alone, WCAG 1.4.1 | No |
| Colour vision deficiency | No |
| Drawn in more than one reader | No: PDFium only |

## Support in PDF apps

| What a reader should do (SPEC section 7) | Site viewer | PdfCraft | Others |
| --- | --- | --- | --- |
| Read the themes | Yes (`/XXThemes`) | Planned | No: Poppler, MuPDF, PDFium, pdf.js and Acrobat show the default theme |
| Pick the theme matching light or dark and more contrast | Yes | Planned | No |
| Remember the person's choice | Yes, one choice | Planned, one for light and one for dark | No |
| Paint the paper colour | Yes | Planned | No |
| Ignore a theme that breaks section 5's rules (R7.1-3) | No | Planned | No |
| Print the default theme | n/a | Planned | n/a |
| Open your own PDFs | No: the site's documents only | Yes, it's a PDF app | n/a |

## Work to do

Size: **S** a day or two, **M** about a week, **L** several weeks. "Needs" names what has to come first.

### Specification

| ID | Change | Where | Size | Needs | Status |
| --- | --- | --- | --- | --- | --- |
| S1 | Agree the name a shared file uses, and whether there's an interim one, with the PDF Association's working group, so files carry as few names as possible. Until then prototypes keep `XXThemes`, and readers read the key from a list so an agreed name is a one-line addition. Ask too whether the keys inside the themes dictionary need a prefix, and add an `/Extensions` entry once there's a name to declare | 4.4 (R4.4-1), Annex C | S | The working group | Open |
| S2 | Separate the system's forced colours, which win over any theme, from a reader's own colour setting, where the reader shows the closest theme and offers the setting instead | R7.2-1, R7.2-3, 7.4 | S | | Written in 0.4 |
| S3 | Readers keep the person's choice for light and for dark apart, switching with the system's dark mode, and match the scheme before the tint | 7.3, R7.2-6 | S | | Written in 0.4 |
| S4 | Allow dark tinted themes, such as Dark cream | 5.2, 5.4 | S | | Written in 0.4 |
| S5 | Readers draw the appearances they make themselves in the theme shown (question 6 as a rule) | R7.5-2 to R7.5-4 | S | | Written in 0.4 |
| S6 | An image whose soft mask has a Matte keeps its values; a theme may swap in a whole image blended with the same matte | Open question 20 | S | | Needs a decision |
| S7 | Say what "draws the same" means for the default theme: within one level of each colour component | Open question 21 | S | | Needs a decision: PDFium is four levels out on one Display P3 file |
| S8 | A writer should check a themed file in more than one reader | R9.2-6 | S | | Written in 0.4 |
| S10 | A writer shall not share a palette between a soft mask group and visible content, since swapping it would change the mask's transparency too | R5.3-6 | S | | Written in 0.4 |
| S11 | An editor that changes a base object shall update its replacement in every theme, or drop those themes, since a replacement left behind (a different `hival`, an old `Rect`) makes readers reject the theme | 8.1 (R8.1-2) | S | | Written in 0.4 |
| S12 | Readers resolve references the same way with and without a theme: at every step of a chain of references, and in a repaired file by object number as the reader does | R5.3-8, R7.1-1 | S | | Written in 0.4 |
| S9 | Decide questions 2 and 15 to 19 | Annex D | | The PDF Association's working group | Open |

### Tool

| ID | Change | Where | Size | Needs | Status |
| --- | --- | --- | --- | --- | --- |
| T1 | Once a name is agreed: write it and the `/Extensions` entry, read it and `XXThemes`, and rebuild the demo files and `tests/objects` | `pdfthemes/theme.py`, `core.py`, `demo/site/viewer.js`, tests | M | S1 | Waiting on S1 |
| T2 | Warn before rewriting a signed file, and check a file's permissions before changing it, asking for the owner password where needed | `pdfthemes/cli.py`, `core.py` | S | | No |
| T3 | Theme 1-bit scans the way grey scans are, after checking how many of the 15 unthemed scans in the test set are 1-bit | `pdfthemes/merge.py` (`grey_scan`), `derive.py` (`scan_pair`) | M | | No |
| T4 | Work out dark tinted themes beside the light tints | `pdfthemes/derive.py` (`standard_specs`) | S | S4 | No |
| T5 | Theme a matted image by swapping in a whole image per theme, blended with the same matte | `pdfthemes/merge.py`, `derive.py` | M | S6 | No |
| T6 | Measure how often photos and screenshots matter in the test set, then decide on whole-image themes for them from a single build | `pdfthemes/derive.py`, the corpus run | L | | No |
| T7 | Write a two-colour image 8 bits an index, not 1, because PDFium draws a 1-bit palette image a level off where it resamples it | `pdfthemes/merge.py` | S | | Needs a decision: costs a little size |
| T8 | Work out wide-gamut themes in the file's own colour space, not sRGB | `pdfthemes/derive.py`, `colour.py` | M | Question 9 | No |
| T9 | Make worked-out themes hold on large files: all six fail on the 31-page objects test | `pdfthemes/derive.py` | M to L | | No |
| T10 | Release on PyPI as `pdf-themes` | `pyproject.toml` | S | S1, so a general release never writes `XXThemes` into shared files | Held |
| T11 | Let `pdf-themes merge` take builds that differ in line widths and dashes as well as colours, moving those into graphics states a theme replaces (R5.3-11, R6.4-10), and make `pair_check.py` allow them | `pdfthemes/merge.py`, `tests/objects/tools/pair_check.py` | M | | No |

### Contrast check

| ID | Change | Where | Size | Needs | Status |
| --- | --- | --- | --- | --- | --- |
| C1 | Hold text across two backgrounds against the worse one, without counting the strokes of neighbouring text as a background (fault 16; an earlier attempt failed on that) | `pdfthemes/contrast.py` | M | | Known limit |
| C2 | Recognise text drawn as outlines | `pdfthemes/contrast.py` | M | Question 13 | No |
| C3 | Measure text filled with a gradient | `pdfthemes/contrast.py` | M | Question 14 | No |
| C4 | Check meaning carried by colour alone (WCAG 1.4.1), and how each theme looks with colour vision deficiency | `pdfthemes/contrast.py` | L | Question 13 | No |
| C5 | Aim higher for text drawn at less than full opacity (fault 9) | `pdfthemes/derive.py` | S | | No |
| C6 | Draw each theme in a second reader as well as PDFium | `pdfthemes/contrast.py` | M | S8 | No |
| C7 | List chart series under 3:1 against the paper, or under 10 apart (ΔE00) as drawn or as simulated for protan, deutan and tritan vision with Brettel, Viénot and Mollon's model, and series with no second cue it can find; report widths that break R5.3-11 or that a `w` overrides (9.3) | `pdfthemes/contrast.py` | M | | No |

### Site viewer

| ID | Change | Where | Size | Needs | Status |
| --- | --- | --- | --- | --- | --- |
| V1 | Check section 5's rules before swapping (R7.1-3), and ignore a theme that breaks them | `demo/site/viewer.js` | S | | No |
| V2 | Remember a choice for light and one for dark | `demo/site/viewer.js` | S | S3 | No |
| V3 | Read the key from a list, so an agreed name is a one-line addition | `demo/site/viewer.js` | S | | No |
| V4 | Decide whether people can open their own PDFs, kept in the browser | `demo/site/viewer.js`, the Content Security Policy | M | | Needs a decision |

### PDF apps and other tools

| ID | Change | Where | Size | Needs | Status |
| --- | --- | --- | --- | --- | --- |
| A1 | Reference redirects: open a PDF so given references resolve to other objects, the general piece a theme needs | [LaurenzV/hayro](https://github.com/LaurenzV/hayro) | M | | Proposed: [hayro#1812](https://github.com/LaurenzV/hayro/issues/1812) |
| A2 | PdfCraft reads and shows themes, matched to the app, overriding its reading colours, with a theme picker; its own parser, used for the comments panel and the appearances it draws, applies the same swaps | [storytold/pdfcraft](https://github.com/storytold/pdfcraft) | L | A1 | Planned, eight tasks |
| A3 | PdfCraft edits themes: a check panel, a colour editor per theme, and themes kept through edits | storytold/pdfcraft | L | A2, R1 | Planned |
| R1 | A Rust crate under MIT or Apache 2.0: the contrast check first, then writing palettes and themes, then working themes out | New repository | L | | Planned |
| A4 | pdf.js reads and shows themes | [mozilla/pdf.js](https://github.com/mozilla/pdf.js) | L | A2 | Issue drafted |
| A5 | Typst: a colour per theme, krilla writing palettes and themes, one layout painted in each theme, a theme switch in the previews | typst, krilla, Tinymist | L | R1 | Forum post drafted |
| A6 | Typst and Tinymist: draw an embedded SVG in the page's colour scheme | typst, Tinymist | S | | Bug reports drafted |
| A7 | matplotlib: text written as outlines has no fill, so it stays black in a dark theme | matplotlib | S | | A note to write |
| A8 | Makie: colours as roles with a value per theme | Makie | L | | Ask the maintainers first |

### Beyond the code

| ID | What | Status |
| --- | --- | --- |
| P1 | Ask the PDF Association's working group how the name should be handled (S1), on [pdf-issues #369](https://github.com/pdf-association/pdf-issues/issues/369) | With spec draft 0.4 |
| P2 | Present to the PDF Technical Working Group, once a reader people use supports themes | After A2 |
| P4 | Take part in the UK's standards work through BSI's IDT/1 committee, the route to an ISO technical specification | Applying |
| P3 | Readers with dyslexia, visual stress, low vision or colour vision deficiency try the themes, including chart reading in light and dark with today's palettes, which no study has tested with readers who have the deficiency | Needs someone to lead a study |

## The route to the standard

PDF 2.1 hasn't been announced. New PDF features have been arriving as ISO technical specifications (ISO/TS 32001 to 32004) and amendments to ISO 32000-2, so the route is:

1. Spec draft 0.4 with rules for readers, editors, writers and checkers, and a test file per rule.
2. A reader people use: PdfCraft (A2), with hayro (A1), then its editor (A3).
3. The PDF Association's PDF Technical Working Group: the proposal, the tests and the implementations (P2), and the name (S1).
4. An ISO technical specification, through a national body (P4).
5. The next edition of ISO 32000.

Nothing writes themed files for general use until step 3 has settled the name.
