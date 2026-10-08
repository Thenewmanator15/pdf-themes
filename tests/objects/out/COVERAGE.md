# Coverage

Every tile in the objects test, the ISO 32000-2 tables it exercises, and what a theme should do with it.

| Page | Object | ISO 32000-2 tables | Theme |
|---|---|---|---|
| 1 | Fill rules: f and f* | 59 | swaps |
| 1 | Line widths | 56, 51 | swaps |
| 1 | Line caps: J 0, 1, 2 | 53 | swaps |
| 1 | Line joins and miter limit | 54, 56 | swaps |
| 1 | Dash patterns | 55, 56 | swaps |
| 1 | Curves: c, v and y | 58 | swaps |
| 1 | Fill and stroke: B, B*, b, b*, s | 59 | swaps |
| 1 | Clipping: W and W* | 60 | swaps |
| 1 | Rectangles, hairlines and dots | 58, 51 | swaps |
| 1 | Graphics state: q, Q, cm and gs | 56, 57 | swaps |
| 1 | Stroke adjustment and flatness | 57 | viewer |
| 1 | Strokes under a scaled CTM | 56 | swaps |
| 2 | DeviceGray: g, G | 61, 73 | swaps |
| 2 | DeviceRGB: rg, RG | 61, 73 | swaps |
| 2 | DeviceCMYK: k, K | 61, 73 | swaps |
| 2 | CalGray | 62 | swaps |
| 2 | CalRGB | 63 | swaps |
| 2 | Lab | 64 | swaps |
| 2 | ICCBased: sRGB | 65, 66 | swaps |
| 2 | ICCBased: Display P3 | 65, 67 | swaps |
| 2 | ICCBased: CMYK (FOGRA39) | 65, 68 | swaps |
| 2 | Indexed over RGB, Lab and ICC | 61 | swaps |
| 2 | Separation: spot, All, None | 61 | swaps |
| 2 | DeviceN and NChannel | 70, 71 | swaps |
| 2 | Rendering intents: ri | 69 | viewer |
| 2 | Default colour spaces in a form | 34, 61 | swaps |
| 2 | Overprint: OP, op and OPM | 57, 146 | viewer |
| 3 | Type 1: function-based | 78, 42 | swaps |
| 3 | Type 2: axial | 79, 40 | swaps |
| 3 | Type 3: radial | 80, 41 | swaps |
| 3 | Axial with a sampled function | 79, 39 | swaps |
| 3 | Type 4: free-form triangle mesh | 81 | swaps |
| 3 | Type 5: lattice-form mesh | 82 | swaps |
| 3 | Type 6: Coons patch mesh | 83, 84 | swaps |
| 3 | Type 7: tensor-product patch mesh | 83, 85 | swaps |
| 3 | Mesh with a function | 81 | swaps |
| 3 | Axial shading in Lab | 79, 64 | swaps |
| 3 | Axial shading in DeviceN | 79, 70 | swaps |
| 3 | Background, BBox and AntiAlias | 77 | swaps |
| 4 | Tiling, coloured (PaintType 1) | 74 | swaps |
| 4 | Tiling, uncoloured (PaintType 2) | 74 | swaps |
| 4 | Tiling types 1, 2, 3 and a Matrix | 74 | swaps |
| 4 | Shading pattern: fill | 75 | swaps |
| 4 | Shading pattern: stroke | 75 | swaps |
| 4 | Shading pattern: text | 75, 104 | swaps |
| 4 | Pattern inside a pattern | 74 | swaps |
| 4 | Shading pattern with ExtGState | 75, 57 | swaps |
| 4 | Uncoloured pattern over a spot colour | 74, 61 | swaps |
| 5 | Standard 14 fonts, not embedded | 108, 109 | swaps |
| 5 | Type 1, embedded (FontFile) | 109, 124 | swaps |
| 5 | TrueType, embedded (FontFile2) | 109, 124 | swaps |
| 5 | Bare CFF (FontFile3 /Type1C) | 124, 125 | swaps |
| 5 | OpenType CFF (FontFile3 /OpenType) | 124, 125 | swaps |
| 5 | Type 0 with CIDFontType2, Identity-H | 115, 119 | swaps |
| 5 | Type 0 with CIDFontType0 (CFF CIDs) | 115, 119 | swaps |
| 5 | Vertical writing: Identity-V | 115, 116 | swaps |
| 5 | Text state: Tc, Tw, Tz, Ts, TL, TJ | 103, 106, 107 | swaps |
| 5 | Text matrix: Tm | 106 | swaps |
| 6 | Type 3, uncoloured glyphs (d1) | 110, 111 | swaps |
| 6 | Type 3, coloured glyphs (d0) | 110, 111 | swaps |
| 6 | Type 3 glyph with a bitmap | 110 | stays |
| 6 | Rendering modes 0 to 3: Tr | 104 | swaps |
| 6 | Rendering modes 4 to 7: clip | 104 | swaps |
| 6 | Text knockout: TK | 57 | swaps |
| 6 | Invisible text over a scan | 104 | stays |
| 6 | Fill, stroke and pattern together | 104, 75 | swaps |
| 6 | Tiny, huge and scaled text | 103 | swaps |
| 7 | DeviceGray, 8-bit photo | 87, 61 | stays |
| 7 | DeviceGray at 1, 2 and 4 bits | 87, 88 | stays |
| 7 | DeviceRGB, 8-bit photo | 87 | stays |
| 7 | DeviceRGB, 16-bit samples | 87 | stays |
| 7 | DeviceCMYK photo | 87, 61 | stays |
| 7 | Lab photo | 87, 64 | stays |
| 7 | ICCBased: sRGB and Display P3 | 87, 65 | stays |
| 7 | Indexed, 8-bit diagram | 87, 61 | swaps |
| 7 | Indexed at 1, 2 and 4 bits | 87, 61 | swaps |
| 7 | Indexed over Lab and ICC | 87, 61 | swaps |
| 7 | Separation image (spot ink) | 87, 61 | swaps |
| 7 | DeviceN image (two spot inks) | 87, 70 | swaps |
| 8 | FlateDecode | 6, 8 | stays |
| 8 | FlateDecode with PNG predictor | 8, 9, 10 | stays |
| 8 | LZWDecode | 6, 7, 8 | stays |
| 8 | RunLengthDecode | 6 | swaps |
| 8 | ASCIIHexDecode then Flate | 6 | stays |
| 8 | ASCII85Decode | 6 | stays |
| 8 | DCTDecode (JPEG), baseline | 6, 13 | stays |
| 8 | DCTDecode, progressive greyscale | 6, 13 | stays |
| 8 | DCTDecode, CMYK (Adobe) | 6, 13, 88 | stays |
| 8 | JPXDecode (JPEG 2000) | 6 | stays |
| 8 | CCITTFaxDecode, Group 4 | 6, 11 | stays |
| 8 | CCITTFaxDecode, Group 3 | 6, 11 | stays |
| 8 | JBIG2Decode (generic region, MMR) | 6, 12 | stays |
| 8 | Interpolate: false and true | 87 | stays |
| 8 | Alternates and a Decode array | 87, 89, 88 | stays |
| 9 | Stencil mask (ImageMask) | 87, 88 | swaps |
| 9 | Stencil mask with Decode [1 0] | 88 | swaps |
| 9 | Explicit mask (Mask stream) | 87 | stays |
| 9 | Colour-key mask (Mask array) | 87 | swaps |
| 9 | Soft mask (SMask) | 87, 143 | stays |
| 9 | Soft mask with Matte | 144 | stays |
| 9 | JPEG 2000 with SMaskInData | 87 | stays |
| 9 | Inline images: grey, RGB, Indexed | 90, 91, 92 | swaps |
| 9 | Inline stencil mask | 91 | swaps |
| 10 | Fill opacity: ca | 57, 136 | swaps |
| 10 | Stroke opacity: CA | 57 | swaps |
| 10 | Alpha is shape: AIS | 57 | swaps |
| 10 | All sixteen blend modes: BM | 134, 135 | swaps |
| 10 | Highlighter: Multiply, or Screen in dark | 134 | swaps |
| 10 | Screen and Lighten on paper | 134 | swaps |
| 10 | Difference and Exclusion on text | 134 | swaps |
| 11 | Isolated and knockout groups: I and K | 94, 145 | swaps |
| 11 | Group colour space: CS | 145 | swaps |
| 11 | Luminosity soft mask with BC | 142 | swaps |
| 11 | Alpha soft mask | 142 | swaps |
| 11 | Soft mask with a transfer function | 142 | swaps |
| 11 | SMask None resets the mask | 57 | swaps |
| 11 | Transparency group reused | 94 | swaps |
| 12 | One form, placed four times | 93, 86 | swaps |
| 12 | Nested forms, three deep | 93 | swaps |
| 12 | Form drawn in the caller's colour | 93 | swaps |
| 12 | BBox clips and Matrix maps | 93 | swaps |
| 12 | Form with Measure and PtData (PDF 2.0) | 93, 266, 272 | swaps |
| 12 | Reference XObject (Ref) | 93, 95 | swaps |
| 12 | Form in a tiling pattern cell | 74, 93 | swaps |
| 12 | Form with its own Group and Matrix | 93, 94 | swaps |
| 12 | Image inside a form, reused | 93, 87 | stays |
| 13 | Default on | 96, 99 | swaps |
| 13 | Default off | 96, 99 | swaps |
| 13 | View and print usage | 100, 101 | swaps |
| 13 | Print-only layer | 100, 101 | swaps |
| 13 | Zoom-dependent layer | 100 | swaps |
| 13 | Language layers | 100 | swaps |
| 13 | Radio-button layers: RBGroups | 99 | swaps |
| 13 | Visibility expression: OCMD VE | 97 | swaps |
| 13 | Locked layer, layered annotation and form | 99, 166, 93 | swaps |
| 14 | Text (sticky note) with appearance | 175, 186 | swaps |
| 14 | Review state and a reply: IRT, RT, State | 172, 174, 175 | swaps |
| 14 | FreeText with DA, DS and RC | 177 | swaps |
| 14 | FreeText callout: CL, LE, IT | 177, 179 | swaps |
| 14 | FreeText typewriter | 177 | swaps |
| 14 | Line: all ten line endings | 178, 179 | swaps |
| 14 | Line dimension with Measure | 178, 266, 267 | swaps |
| 14 | Square and Circle with IC | 180, 168 | swaps |
| 14 | Cloudy border: BE | 169 | swaps |
| 14 | Polygon and PolyLine | 181 | swaps |
| 14 | Ink: InkList | 185 | swaps |
| 14 | C and IC in grey, CMYK and none | 166, 180 | swaps |
| 15 | Highlight | 182 | swaps |
| 15 | Underline, Squiggly, StrikeOut | 182 | swaps |
| 15 | Caret: Sy P and None | 183 | swaps |
| 15 | Stamp: drawn and image | 184 | swaps |
| 15 | Stamp names, with appearances | 184 | swaps |
| 15 | Popup, open | 186 | viewer |
| 15 | Redact (marked, not applied) | 195 | swaps |
| 15 | FileAttachment: six icon names | 187, 43 | swaps |
| 15 | Watermark with FixedPrint | 193, 194 | swaps |
| 15 | PrinterMark: colour bar and target | 398, 399 | stays |
| 15 | Annotation BM and ca (PDF 2.0), R and D | 166, 170 | swaps |
| 15 | TrapNet (deprecated in PDF 2.0) | 403, 404 | stays |
| 16 | Link with a border colour: C | 176, 210 | viewer |
| 16 | Highlight modes: H | 176 | viewer |
| 16 | Link over two lines: QuadPoints | 176 | viewer |
| 16 | Link with a dashed border style: BS | 168, 176 | viewer |
| 16 | Destinations: XYZ, Fit, FitH, FitR, FitB | 149 | swaps |
| 16 | Named, remote and embedded go-to | 202, 203, 204, 205 | swaps |
| 16 | Named actions | 215, 216 | swaps |
| 16 | Hide action and the Hidden flag | 214, 167 | swaps |
| 16 | JavaScript action and Next | 221, 196 | viewer |
| 16 | Launch, Thread and Transition actions | 207, 209, 219 | viewer |
| 16 | Flags: NoView, Print off, ToggleNoView | 167 | viewer |
| 16 | Page and document additional actions | 197, 198, 200 | viewer |
| 17 | Text field | 226, 228, 232 | swaps |
| 17 | Multiline text field | 231 | swaps |
| 17 | Password field | 231 | swaps |
| 17 | Comb field: MaxLen 6 | 231, 232 | swaps |
| 17 | File-select field | 231 | swaps |
| 17 | Rich text field: RV and DS | 228, 231 | swaps |
| 17 | Alignment: Q 1 and Q 2 | 228 | swaps |
| 17 | Border styles: beveled, inset, underline | 168, 192 | swaps |
| 17 | Required and read-only flags | 227 | swaps |
| 17 | Number format script: red negatives | 199, 221 | viewer |
| 17 | Calculated field: CO | 199, 224 | viewer |
| 17 | List box | 233, 234 | swaps |
| 17 | Multi-select list box | 233, 234 | swaps |
| 17 | Combo box | 233 | swaps |
| 17 | Editable combo box | 233 | swaps |
| 18 | Check boxes: six styles | 229, 230, 192 | swaps |
| 18 | Radio group | 229, 230 | swaps |
| 18 | Push button: N, R and D appearances | 229, 170, 192, 241 | swaps |
| 18 | Icon buttons: MK I, RI, IX, IF and TP | 192, 250 | swaps |
| 18 | Submit button | 239, 240 | viewer |
| 18 | Signature field, unsigned | 235, 236, 237 | swaps |
| 18 | Focus and blur scripts recolour a field | 197, 221 | viewer |
| 18 | Hidden field shown by a button | 167, 214 | swaps |
| 18 | Field hierarchy: a.b names | 226 | swaps |
| 18 | Read-only check box and NoExport | 227 | swaps |
| 18 | Import data action | 243 | viewer |
| 18 | MK colours in grey and CMYK | 192 | swaps |
| 19 | Screen with a Rendition action | 190, 218, 282, 293 | swaps |
| 19 | Rendition actions: play, pause, stop | 218 | viewer |
| 19 | RichMedia (video) | 333, 334, 335, 338, 339, 340, 341, 342, 222 | swaps |
| 19 | Movie annotation (deprecated) | 189, 306, 307, 213 | swaps |
| 19 | Sound annotation and action (deprecated) | 188, 305, 212 | swaps |
| 19 | 3D annotation (U3D) | 309, 310, 311, 315, 317, 318, 320, 322, 323, 326-331 | swaps |
| 19 | GoTo3DView actions, 3D markup | 220, 173, 324 | viewer |
| 19 | Projection annotation (PDF 2.0) | 172, 332, 327 | swaps |
| 19 | Selector rendition with MH and BE | 277, 278, 279, 283 | viewer |
| 19 | Floating window colour | 293, 294, 295 | swaps |
| 19 | Embedded media files | 43, 44, 45 | stays |
| 20 | Page boxes and BoxColorInfo | 31, 396, 397 | viewer |
| 20 | Thumbnail: Thumb | 31 | swaps |
| 20 | Transition and display time | 31, 164 | viewer |
| 20 | Article thread: beads | 162, 163 | viewer |
| 20 | Viewport with a scale: Measure RL | 265, 266, 267, 268 | swaps |
| 20 | Geospatial viewport: GEO, PROJCS, PtData | 265, 269, 270, 271, 272 | swaps |
| 20 | Navigation steps: PresSteps | 165 | viewer |
| 20 | Document parts and GoToDp | 206, 408, 409 | swaps |
| 20 | Associated file on a page: AF | 31, 43, 45 | stays |
| 20 | Outlines with colour and style | 151, 152 | swaps |
| 20 | Page labels | 161 | viewer |
| 20 | Page output intent, by reference | 31, 401, 402 | stays |
| 21 | Content on a rotated page | 31 | swaps |
| 21 | NoRotate and NoZoom flags | 167 | viewer |
| 21 | Article thread continues | 163 | viewer |
| 21 | Last bead | 163 | viewer |
| 22 | UserUnit page | 31 | swaps |
| 23 | Table with Layout colours | 371, 377, 378, 384 | swaps |
| 23 | List with numbering | 370, 382 | swaps |
| 23 | Underline with TextDecorationColor | 380 | swaps |
| 23 | Attribute class: ClassMap and C | 354, 355, 360 | swaps |
| 23 | FENote, E and Lang (PDF 2.0 namespace) | 355, 356, 366, 368 | swaps |
| 23 | Formula with a MathML file | 374, 43 | swaps |
| 23 | Ruby and Warichu | 369 | swaps |
| 23 | Figure with BBox and Caption | 373, 372, 379 | swaps |
| 24 | Halftone type 1: spot functions | 126, 127, 128 | stays |
| 24 | Halftone type 5 per colorant | 132 | stays |
| 24 | Threshold halftones: types 6, 10, 16 | 129, 130, 131 | stays |
| 24 | Transfer functions: TR and TR2 | 57 | viewer |
| 24 | Black generation and undercolour removal | 57 | stays |
| 24 | SM, HTO and UseBlackPtComp | 57 | stays |
| 24 | SeparationInfo | 400 | stays |
| 24 | Document output intent | 29, 401 | stays |
| 24 | OPI 1.3 and 2.0 on an image (deprecated) | 405, 406, 407 | stays |
| 24 | MMType1 font (deprecated) | 108, 109 | swaps |
| 24 | BX/EX and marked points: MP, DP | 33, 352 | swaps |
| 25 | Line plot: series, legend, grid | 59, 110 | swaps |
| 25 | Scatter coloured by value | 86, 93, 87 | swaps |
| 25 | Error bars and a confidence band | 57, 86 | swaps |
| 25 | Histogram with hatching | 74, 57 | swaps |
| 25 | Heatmap, diverging map | 87, 61 | swaps |
| 25 | Heatmap, viridis in both | 87, 61 | stays |
| 25 | Gouraud mesh (pcolormesh) | 81 | swaps |
| 25 | Filled and labelled contours | 59, 110 | swaps |
| 25 | 3D surface (mplot3d) | 59 | stays |
| 25 | Mass spectrum: sticks, log scale | 59, 110 | swaps |
| 25 | Rasterised layer in a vector plot | 87, 144 | swaps |
| 25 | Spectrogram with colour bar | 87 | stays |
| 26 | Smith chart | 59 | swaps |
| 26 | Constellation: 16-QAM | 57, 86 | swaps |
| 26 | Eye diagram | 57 | swaps |
| 26 | Ion image with a scale bar | 87 | stays |
| 26 | Antenna pattern: polar axes | 59 | swaps |
| 26 | pgfplots surface and colour bar | 75, 82, 79 | stays |
| 26 | pgfplots: band, error bars, pattern | 74, 57 | swaps |
| 26 | Equations from LaTeX | 109, 124 | swaps |
| 26 | 100,000 points in one path | 58 | swaps |
| 26 | Chemical structure: element colours | 59 | swaps |
| 26 | Results table: colours that mean something | 371, 378, 384 | swaps |
| 26 | The data behind a plot: AF, Data | 43, 45, 373 | stays |
