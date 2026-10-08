// Theme lab: try out PDF themes on Lilaq plots.
//
// Lilaq draws plots with no background, so the page colour shows through, and every
// label, tick label and legend entry is ordinary Typst text in the document's text colour.
// Each theme below sets the paper, the text and the few plot colours Lilaq doesn't take
// from the text: spines and ticks, the grid, the legend box, and the series colours.
//
// In the editor, change `preview` to look at a theme. To build one:
//   typst compile --input mode=dark theme-lab.typ dark.pdf
//
// This copy is the one the tests merge, so every build draws the same text and
// shapes: it prints nothing about the theme it was built in. out/ holds the
// eight builds, made with
//   typst compile --input mode=<mode> --pdf-standard 2.0 --font-path ../../examples/fonts theme-lab.typ out/<mode>.pdf

#import "@preview/lilaq:0.6.0" as lq

#let preview = "light"
#let mode = sys.inputs.at("mode", default: preview)

// -- Contrast (WCAG 2.2): 4.5:1 for text, 7:1 for more contrast, 3:1 for lines and marks --

#let channel(c) = if c <= 0.04045 { c / 12.92 } else { calc.pow((c + 0.055) / 1.055, 2.4) }
#let luminance(col) = {
  let (r, g, b, ..) = rgb(col).components().map(x => channel(x / 100%))
  0.2126 * r + 0.7152 * g + 0.0722 * b
}
#let contrast(a, b) = {
  let (la, lb) = (luminance(a), luminance(b))
  (calc.max(la, lb) + 0.05) / (calc.min(la, lb) + 0.05)
}

// Move a colour towards the text colour, a step at a time, until it reaches `target`
// against the paper. Its hue stays, so a series keeps its identity in every theme.
#let fit(col, paper, ink, target) = {
  let k = 0
  let out = col
  while contrast(out, paper) < target and k < 95 {
    k += 5
    out = color.mix((col, 100% - k * 1%), (ink, k * 1%))
  }
  out
}

// -- The themes -----------------------------------------------------------------

#let themes = (
  light:          (paper: white,          ink: rgb("#1b1d21"), rule: luma(85%), text-min: 4.5, line-min: 3),
  dark:           (paper: rgb("#18191c"), ink: rgb("#e8eaed"), rule: luma(30%), text-min: 4.5, line-min: 3),
  light-contrast: (paper: white,          ink: black,          rule: luma(60%), text-min: 7,   line-min: 4.5),
  dark-contrast:  (paper: black,          ink: white,          rule: luma(45%), text-min: 7,   line-min: 4.5),
  cream:          (paper: rgb("#fdf6e3"), ink: rgb("#1b1d21"), rule: rgb("#e3d9bd"), text-min: 4.5, line-min: 3),
  yellow:         (paper: rgb("#fff7c2"), ink: rgb("#1b1d21"), rule: rgb("#e6d98a"), text-min: 4.5, line-min: 3),
  turquoise:      (paper: rgb("#e3eefa"), ink: rgb("#1b1d21"), rule: rgb("#bcd0e6"), text-min: 4.5, line-min: 3),
  peach:          (paper: rgb("#fde7dc"), ink: rgb("#1b1d21"), rule: rgb("#ecc6b4"), text-min: 4.5, line-min: 3),
)

#let t = themes.at(mode)
#let series = lq.color.map.petroff10.map(c => fit(c, t.paper, t.ink, t.line-min))

#set page(width: 210mm, height: auto, margin: 12mm, fill: t.paper)
#set text(font: ("Inter", "DejaVu Sans"), size: 9pt, fill: t.ink)

#show: lq.set-diagram(cycle: series)
#show: lq.set-spine(stroke: 0.6pt + t.ink)
#show: lq.set-grid(stroke: 0.4pt + t.rule)
#show: lq.set-legend(fill: t.paper, stroke: 0.5pt + t.rule)

= Theme lab

The same plots in every theme. Each theme sets its paper, its text and its rule colour, and the series
colours are fitted to the paper so lines and marks keep their contrast.

#let xs = lq.linspace(0, 10, num: 120)

#grid(columns: 2, gutter: 8mm,
  lq.diagram(
    width: 80mm, height: 50mm, title: [Six series], xlabel: [time (ms)], ylabel: [signal (V)],
    legend: (position: bottom + right),
    ..range(6).map(k => lq.plot(xs, xs.map(x => calc.sin(x + k) * calc.exp(-x / 8)), mark: none,
      label: [run #(k + 1)])),
  ),
  lq.diagram(
    width: 80mm, height: 50mm, title: [Bars and marks], xlabel: [sample],
    lq.bar(range(1, 9), (3, 5, 2, 6, 4, 7, 5, 3)),
    lq.plot(range(1, 9), (2.5, 4, 2.5, 5, 4.5, 6, 4, 3.5), mark: "o", stroke: none),
  ),
  lq.diagram(
    width: 80mm, height: 50mm, title: [Error bars], xlabel: [dose],
    lq.plot(range(0, 10), range(0, 10).map(x => 1 / (1 + calc.exp(-(x - 5)))), yerr: 0.08, mark: "s"),
  ),
  {
    let mesh = lq.colormesh(lq.linspace(-2, 2, num: 40), lq.linspace(-2, 2, num: 30),
      (x, y) => calc.exp(-(x * x + y * y)) * calc.cos(2 * x), map: color.map.viridis)
    lq.diagram(width: 64mm, height: 50mm, title: [Heatmap (an image: viridis in every theme)], mesh)
  },
)

== Series colours against this paper

#table(
  columns: 3, stroke: 0.4pt + t.rule, inset: 4pt,
  [*Series*], [*Petroff 10*], [*In this theme*],
  ..range(10).map(i => (
    [#(i + 1)],
    box(width: 22mm, height: 3mm, fill: lq.color.map.petroff10.at(i)),
    box(width: 22mm, height: 3mm, fill: series.at(i)),
  )).flatten()
)
