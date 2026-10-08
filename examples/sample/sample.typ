// Theme test page: a heading, body text and three kinds of picture.
// No page fill, so the theme's paper colour shows through; a vector chart
// with a key; a chart as an image; and a full-colour image left as it is.
//
//   typst compile --font-path ../fonts --pdf-standard 2.0 sample.typ
//   add --input mode=dark for the dark build

#let mode = sys.inputs.at("mode", default: "light")
#let dark = mode == "dark"

#let pal = if dark {(
  ink: rgb("#F2F2F7"), body: rgb("#E2E2E8"), secondary: rgb("#A1A1A8"),
  grid: rgb("#38383C"), axis: rgb("#C7C7CC"),
  s1: rgb("#C47BFF"), s2: rgb("#64B5FF"), s3: rgb("#FFB340"),
)} else {(
  ink: rgb("#1D1D1F"), body: rgb("#1D1D1F"), secondary: rgb("#6E6E73"),
  grid: rgb("#E3E1E8"), axis: rgb("#3A3A40"),
  s1: rgb("#9A20B6"), s2: rgb("#0060DF"), s3: rgb("#B35900"),
)}

#set document(title: "Theme test page", author: "Mathew Newman")
#set page(paper: "a5", margin: (x: 1.3cm, y: 1.2cm))
#set text(font: "Inter", size: 9.2pt, fill: pal.body, lang: "en", region: "gb")
#set par(leading: 0.6em, spacing: 0.9em)
#show heading: set text(fill: pal.ink, weight: "bold")
#show figure.caption: set text(size: 8.2pt, fill: pal.secondary)

#text(font: "Inter Display", size: 19pt, weight: "bold", fill: pal.ink)[Theme test page]

This page has no background of its own. In the dark theme the reader paints the
paper in the theme's colour before drawing the page. The chart below keeps its
key matched to its lines in both themes, because the key and the lines take
their colours from the same palette entries.

// A line chart drawn as vector graphics: three channels over twelve samples.
#let series = (
  (name: "Channel A", colour: pal.s1, ys: (22, 30, 41, 38, 52, 61, 58, 70, 74, 69, 81, 88)),
  (name: "Channel B", colour: pal.s2, ys: (40, 42, 39, 47, 45, 50, 56, 54, 60, 63, 61, 66)),
  (name: "Channel C", colour: pal.s3, ys: (65, 58, 60, 51, 49, 42, 44, 37, 33, 35, 28, 24)),
)
#let chart(w: 100%, h: 4.2cm) = layout(size => {
  let cw = size.width
  let x(i) = cw * i / 11
  let y(v) = h * (1 - v / 100)
  box(width: cw, height: h, {
    for k in range(5) {
      place(top + left, dy: y(k * 25), line(length: cw, stroke: 0.5pt + pal.grid))
    }
    place(top + left, dy: h, line(length: cw, stroke: 0.9pt + pal.axis))
    for s in series {
      let pts = s.ys.enumerate().map(((i, v)) => (x(i), y(v)))
      place(top + left, curve(stroke: (paint: s.colour, thickness: 1.6pt, join: "round", cap: "round"),
        curve.move(pts.first()), ..pts.slice(1).map(p => curve.line(p))))
    }
  })
})

#figure(
  {
    chart()
    v(0.5em)
    set text(size: 8.2pt, fill: pal.secondary)
    for s in series {
      box(baseline: -0.25em, line(length: 0.9em, stroke: 1.6pt + s.colour))
      h(0.4em)
      s.name
      h(1.2em)
    }
  },
  caption: [Vector chart: the key and the lines share palette entries.],
  alt: "Line chart of three channels over twelve samples. Channel A rises from 22 to 88, channel B rises gently from 40 to 66, channel C falls from 65 to 24.",
)

#figure(
  image("chart-" + mode + ".png", width: 100%,
    alt: "Bar chart of six pairs of bars. The purple bar of each pair is taller than the grey one in all but the third pair."),
  caption: [The same kind of chart as an image: one plane of pixels, a palette per theme.],
)

#figure(
  image("photo.png", width: 52%, alt: "A full-colour abstract image of soft colour fields."),
  caption: [A full-colour image is the same in both themes, so it is stored once.],
)
