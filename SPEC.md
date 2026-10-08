# Colour themes in PDF

Draft 0.3, October 2026. Mathew Newman.

This is a working draft for discussion with the PDF Association's PDF Technical
Working Group. It describes what `pdfthemes` in this repository writes and
reads. Key names are provisional: the proof of concept stores the theme
dictionary under the private key `XXThemes` (a third-class name, ISO 32000-2
Annex E). A standard would use a first-class key, written here as `Themes`.

## 1. What it does

A PDF can carry more than one set of colours for the same content. The
content streams, text, fonts and structure tree are stored once. Each
alternate theme lists objects to draw in place of others: mostly palettes,
sometimes a gradient, an opacity setting, an image's palette or a colour value
outside the page content.

Choosing a theme is a view setting, like draft mode or overprint preview. A
reader that supports themes picks one from the person's settings, paints the
theme's paper colour and draws the pages with the swapped objects. A reader
that doesn't support themes ignores them and shows the default colours.

## 2. Terms

- **Default theme**: the colours as written in the file.
- **Alternate theme**: a theme that replaces some objects with others.
- **Palette**: an Indexed colour space (ISO 32000-2, 8.6.6.3) that content
  streams use for solid colours, for example `/Th0 cs 15 sc`.
- **Replacement**: a pair of indirect objects. While the theme is shown, the
  first object is drawn as the second.
- **Derived theme**: an alternate theme the writer worked out from the default
  theme rather than one the author designed.
- **Contrast ratio**: as WCAG 2.2 defines it, from the relative luminance of
  two colours. Success criteria are cited by number and name, for example
  1.4.3 Contrast (Minimum).
- **Enhanced contrast**: WCAG's term for the 7:1 level of success criterion
  1.4.6. A theme with `Contrast` `More` is an enhanced contrast theme.
- **Forced colours**: a mode in which the person's own colours replace the
  document's, such as a Windows contrast theme (CSS `forced-colors`).

## 3. The themes dictionary

The document catalog's `Themes` entry is a dictionary:

| Key | Type | Value |
| --- | --- | --- |
| Default | dictionary | (Required) A theme dictionary describing the default theme. It shall not contain `Replace`. |
| Alternates | array | (Required) One or more theme dictionaries for alternate themes. |

## 4. Theme dictionaries

| Key | Type | Value |
| --- | --- | --- |
| Type | name | (Optional) `Theme`. |
| Name | text string | (Required) The name a reader shows, for example `(Dark)`. Unique within the file. |
| ColorScheme | name | (Required) `Light` or `Dark`: the setting this theme suits, as in CSS `prefers-color-scheme`. |
| Contrast | name | (Optional) `More` for an enhanced contrast theme (WCAG 1.4.6), made for people who ask for more contrast, as in CSS `prefers-contrast: more`. Absent means standard contrast. |
| Tint | name | (Optional) The tint of a tinted theme, from section 7, for example `Cream`. Absent means no tint. |
| Paper | array | (Optional) Three numbers from 0 to 1: the sRGB colour a reader paints before drawing each page. Default: `[1 1 1]`. |
| Checked | dictionary | (Optional) What the writer checked this theme against (section 8). |
| Replace | array | (Required in alternate themes) An even number of indirect references, read in pairs `base replacement`. |

`ColorScheme`, `Contrast` and `Tint` are labels a reader can match from one
document to the next. `Name` is for people and may be translated.

## 5. Replacements

1. Each element of `Replace` shall be an indirect reference.
2. A base object shall be one of these, and its replacement the same kind:

   | Base | The replacement shall keep |
   | --- | --- |
   | An Indexed colour space (a palette) | the same `hival`. Its base colour space may differ. |
   | Another colour space | the same family and number of components. |
   | A function | the same number of inputs and outputs. |
   | A shading or a shading pattern | the same shading type, geometry (`Coords`, `Domain`, `Extend`, `BBox`, `Matrix`) and, for meshes, the same vertices. |
   | A graphics state parameter dictionary | everything except `CA`, `ca` and `BM`. |
   | An image XObject, or a page thumbnail | the same `Width`, `Height`, `SMask` and `Mask`. |
   | A colour value: an array of 0, 1, 3 or 4 numbers, or an array of such arrays | the same structure. Used for annotation `C` and `IC`, `MK` `BG` and `BC`, bookmark `C`, `BoxColorInfo` `C`, soft mask `BC`, structure attributes such as `Color` and `BorderColor`, and portfolio colours. |
   | A text string that carries colour: `DA`, `DS` or `RC` | everything except its colour operators or CSS colour values. |
   | An annotation dictionary | everything except `C`, `IC`, `CA`, `ca`, `BM`, `DA`, `DS` and `RC`. |

   A base object shall not be a page, a content stream, a form XObject, a
   font, an optional content group, an action or anything in the structure
   tree other than an attribute's colour value. A theme can therefore repaint
   a document but cannot change its text, its shapes or what it does.
3. A base object shall appear at most once in a theme's `Replace` array.
4. While a theme is shown, every reference to a base object in the document
   shall be resolved to its replacement, wherever it is referenced from.

## 6. Writers

- A writer should paint every solid colour through a palette, so that one
  replacement recolours the document. An Indexed space holds at most 256
  colours; a document that needs more uses several palettes.
- A writer should give text, fills and strokes their own palette entries, even
  where the colours are the same, so a theme can change one without the
  others.
- A palette's base colour space should be the space the colour was written in.
  Colours a writer works out itself should be in an ICC-based sRGB space; a
  file that already has an sRGB profile should use it, which keeps PDF/A
  files within their rules.
- The default theme shall be a complete document on its own: a reader that
  ignores `Themes` shows it correctly.
- Images that differ between themes but share their shapes should be written
  once, as indices into a palette, with a palette per theme. A full replacement
  image is allowed, but costs its full size.
- A grey image of a page, such as a scan, may be given an Indexed colour space
  over its own grey space in which each entry is the grey of its own index.
  It draws exactly as before, its data isn't changed, and a theme replaces the
  palette. Scans that share a colour space and bit depth can share a palette.
- A writer should offer the standard themes in section 7, deriving any the
  author didn't design, and should leave out a derived theme that fails its
  check or that draws every page exactly as the default theme does.

## 7. Standard themes

| Name | ColorScheme | Contrast | Tint | For |
| --- | --- | --- | --- | --- |
| Light | Light | | | The author's design. |
| Dark | Dark | | | Light sensitivity, glare, reading in the dark, some low vision. |
| Light, more contrast | Light | More | | Low vision. Enhanced contrast. |
| Dark, more contrast | Dark | More | | Low vision with light sensitivity. Enhanced contrast. |
| Cream, Peach, Yellow, Turquoise | Light | | the same as the name | Readers who find a tinted background easier, including many with dyslexia or visual stress. It does the job of a coloured overlay. Which tint helps differs from person to person, hence a range. |

WCAG 2.2 success criterion 1.4.8 Visual Presentation asks that the person can
select foreground and background colours. A reader that recolours the page
meets that today, at the cost of the design. The standard themes give the
person a set to select from in which each one has been checked.

This draft doesn't specify how a writer works out a derived theme, only its
labels and the check it shall pass. The proof of concept's method is in
`pdfthemes/derive.py`.

## 8. Checking

A writer should check each theme before writing it, at least the contrast of
all text against what is drawn behind it, using the WCAG 2.2 contrast ratio.
The check should be made on the drawn page, so it sees gradients, images and
transparency as a reader shows them. Themes with `Contrast` `More` should be
held to 1.4.6 Contrast (Enhanced) (7:1, level AAA), others to 1.4.3 Contrast
(Minimum) (4.5:1, level AA).
Screens, brightness and room light all change how contrast looks, so a writer
fixing a colour should aim a little above the minimum.

This draft asks for a check of text only. Graphics that carry meaning, such
as chart lines, icons and the borders of form fields, come under 1.4.11
Non-text Contrast (3:1), and a chart that tells its series apart by colour
alone comes under 1.4.1 Use of Color. A writer may check those as well (open
question 13).

`Checked` records the success criterion the theme conforms to:

| Key | Type | Value |
| --- | --- | --- |
| Standard | text string | For example `(WCAG 2.2)`. |
| Criterion | text string | For example `(1.4.3 Contrast (Minimum))`. |
| Level | name | For example `AA`. |
| Date | date | When the check was made. |

A writer shall not write `Checked` for a theme that failed the check, or for
one in which there was no text to check.

PDF/UA-1, PDF/UA-2 and WTPDF cover structure and tagging and leave colour
contrast to WCAG. The rules public bodies work to, such as EN 301 549 in
Europe and Section 508 in the United States, apply WCAG's level AA criteria to
documents, and 1.4.3 is one of them. `Checked` is where a themed file says
which criterion each theme meets.

## 9. Readers

- A reader should choose the theme whose `ColorScheme` and `Contrast` match
  the app or system setting, and, once a person picks a tint, the theme with
  that `Tint` in later documents too. With no match, it shows the default
  theme.
- A reader should offer a way to choose any theme in the file.
- A reader shall paint the theme's `Paper` colour before drawing each page.
- A reader shall apply a theme's replacements as described in 5.4, and nothing
  else changes: text extraction, search, the structure tree, links and form
  fields behave the same in every theme.
- Theme colours are colour managed like any other colours in the file.
- A reader should print the default theme unless the person chooses another.
- When the person has turned on forced colours (for example a Windows
  contrast theme, CSS `forced-colors: active`), the reader's forced colours
  take precedence over any theme.
- A reader shall ignore a theme it cannot apply, for example one whose
  replacements break the rules in section 5, and show the default theme.

## 10. Security

Choosing a theme changes no bytes in the file, so a signature covers every
theme. A theme could still be used to hide content from one reader of a signed
document, for example by painting text in the paper colour. Because a theme
cannot change content streams, the check is narrow:

- a reader validating a signature should say which theme is shown;
- a validator should draw every theme and check text contrast in each;
- a signing profile may restrict alternate themes to palettes, gradients,
  colour values and opacity, with no replacement images.

## 11. Where colour lives in a PDF, and how a theme reaches it

| Where | How a theme changes it |
| --- | --- |
| Solid colours in content streams, in any colour space | Palette entries |
| Colours inside form XObjects, tiling patterns, Type 3 glyphs, annotation appearances and soft mask groups | Palette entries, the same way |
| Gradients (shading patterns and `sh`) | A replacement shading or pattern |
| Opacity and blend modes | A replacement graphics state |
| Images | A replacement palette (Indexed images, and images stored as indices), or a replacement image |
| Stencil masks and image masks | The fill colour, a palette entry |
| Inline images | Written as image XObjects, then as images |
| Annotation, form field, bookmark, structure and portfolio colours | Replacement colour values, strings or annotation dictionaries |
| Page thumbnails | A replacement image |
| The page background | `Paper` |

## 12. Open questions

1. A catalog key, or an extension of optional content configurations?
2. Should a theme be allowed to change line width, so a higher contrast theme
   can thicken thin lines?
3. Paper as sRGB, or as a palette entry? Should it also colour the space
   around pages?
4. Which theme prints when the default theme is dark?
5. Free text in `Checked`, or a minimum contrast ratio a validator can test?
6. Should readers theme the appearances they make themselves (highlights,
   form fields without appearance streams)?
7. Should HTML derived from tagged PDF carry the themes as CSS?
8. A fixed list of tints, or any named tint?
9. Derived themes for wide-gamut colours such as Display P3: worked out in the
   file's own colour space rather than sRGB?
10. Dark paper on OLED screens: pure black can smear when scrolling, which is
    why many dark designs use a dark grey. Should `Paper` have a preferred
    range?
11. Editing: when a person adds a highlight while a theme is shown, which
    theme's colours does it take?
12. Stale themes: a tool that doesn't know about themes can add content, say
    black text, that no theme recolours, so it disappears on dark paper.
    Should `Checked` record what was checked (a digest of the page content,
    for example), so a reader can tell when the themes no longer match the
    pages and fall back to the default?
13. Should the check cover 1.4.11 Non-text Contrast, so chart lines and other
    graphics are held to 3:1 in every theme? Should a theme be able to say it
    was made for colour vision deficiency?

## 13. Example

```
1 0 obj
<< /Type /Catalog /Pages 2 0 R
   /Themes <<
     /Default << /Type /Theme /Name (Light) /ColorScheme /Light /Paper [1 1 1] >>
     /Alternates [ << /Type /Theme /Name (Dark) /ColorScheme /Dark /Paper [0 0 0]
                      /Replace [ 67 0 R 230 0 R ] >>
                   << /Type /Theme /Name (Cream) /ColorScheme /Light /Tint /Cream
                      /Paper [0.988 0.953 0.855] /Replace [ 67 0 R 240 0 R ] >> ]
   >>
>>
endobj

67 0 obj  [/Indexed [/ICCBased 231 0 R] 16 <F5F5F7 FFFFFF ... 9A20B6 FFFFFF>] endobj
230 0 obj [/Indexed [/ICCBased 231 0 R] 16 <000000 2E2838 ... C47BFF 160A24>] endobj
240 0 obj [/Indexed [/ICCBased 231 0 R] 16 <F9F1DA FCF3DA ... 9A20B6 FCF3DA>] endobj

% in a content stream, the same bytes in every theme:
/Th0 cs 15 sc
```
