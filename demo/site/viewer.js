// The viewer, demo/index.html. Kept out of the page so the site's Content Security
// Policy needs no inline scripts. The import is relative to this file; the files it
// fetches and links to are relative to the page.

import * as pdfjsLib from "../vendor/pdf.min.mjs";

// pdf.js's worker ships as base64 text (its source holds raw control characters)
// and starts from a blob URL, which is why the Content Security Policy allows blob: workers.
const workerText = await fetch("vendor/pdf-worker.base64.txt")
  .then((r) => (r.ok ? r.text() : Promise.reject(new Error("the PDF engine's worker is missing"))));
const workerBytes = Uint8Array.from(atob(workerText.trim()), (c) => c.charCodeAt(0));
pdfjsLib.GlobalWorkerOptions.workerSrc = URL.createObjectURL(new Blob([workerBytes], { type: "text/javascript" }));
const { PDFDocument, PDFName, PDFArray, PDFDict, PDFNumber, PDFRawStream, decodePDFRawStream } = window.PDFLib;

const THEMES_KEY = "XXThemes";  // a private name until a standard one is agreed
const DOCS = [
  { id: "proposal", file: "proposal-themed.pdf", label: "The proposal, in eight themes" },
  { id: "lab", file: "theme-lab-themed.pdf", label: "Theme lab: plots in eight themes" },
  { id: "corpus", file: "corpus-themed.pdf", label: "Test document, 6 pages" },
  { id: "sample", file: "sample-themed.pdf", label: "Test page" },
  { id: "scan", file: "scan-themed.pdf", label: "Scanned page" },
  { id: "objects", file: "objects-themed.pdf", label: "Objects test, 31 pages" },
  { id: "figure", file: "figure-themed.pdf", label: "Matplotlib figure" },
];
const state = { mode: "auto", doc: null, page: 1 };
const loaded = new Map();
const $ = (id) => document.getElementById(id);

// What a theme-aware reader does to show a theme. Each pair in the theme's
// Replace array swaps places, so whatever pointed at the first object now
// gets the second. The page content itself is never touched.
function applyTheme(pdf, theme) {
  const replace = theme.lookup(PDFName.of("Replace"), PDFArray);
  for (let i = 0; i < replace.size(); i += 2) {
    const a = replace.get(i);
    const b = replace.get(i + 1);
    const objectA = pdf.context.lookup(a);
    const objectB = pdf.context.lookup(b);
    pdf.context.assign(a, objectB);
    pdf.context.assign(b, objectA);
  }
}

// A reader remembers what a person chose by the theme's labels, not its name,
// so the choice carries over to the next document. Kept in this browser only.
const SAVED = "themed-pdf-choice";
function savedChoice() {
  try { return JSON.parse(localStorage.getItem(SAVED) || "null"); } catch { return null; }
}
function saveChoice(choice) {
  try { localStorage.setItem(SAVED, JSON.stringify(choice)); } catch { /* storage may be off */ }
}

// Reading the file, for the panel.
const plain = (o) => (o ? o.toString().replace(/^\//, "") : "");
const textOf = (o) => (o && typeof o.decodeText === "function" ? o.decodeText() : plain(o));
const num = (o) => (o instanceof PDFNumber ? o.asNumber() : Number(plain(o)));
const refText = (r) => `${r.objectNumber} ${r.generationNumber} R`;
const hex = (rgb) => "#" + rgb.map((v) => Math.max(0, Math.min(255, Math.round(v))).toString(16).padStart(2, "0")).join("").toUpperCase();

function readThemes(pdf) {
  const root = pdf.catalog.lookupMaybe(PDFName.of(THEMES_KEY), PDFDict);
  if (!root) return null;
  const read = (dict, isDefault) => {
    const checked = dict.lookupMaybe(PDFName.of("Checked"), PDFDict);
    return {
      dict,
      isDefault,
      name: textOf(dict.lookup(PDFName.of("Name"))),
      scheme: plain(dict.lookup(PDFName.of("ColorScheme"))),
      contrast: plain(dict.get(PDFName.of("Contrast"))),
      tint: plain(dict.get(PDFName.of("Tint"))),
      paper: (dict.lookupMaybe(PDFName.of("Paper"), PDFArray)?.asArray() ?? [1, 1, 1]).map(num),
      checked: checked ? `${textOf(checked.lookup(PDFName.of("Standard")))} ${textOf(checked.lookup(PDFName.of("Criterion")))}, ${plain(checked.lookup(PDFName.of("Level")))}` : null,
    };
  };
  const alternates = root.lookup(PDFName.of("Alternates"), PDFArray).asArray();
  return [read(root.lookup(PDFName.of("Default"), PDFDict), true),
          ...alternates.map((a) => read(pdf.context.lookup(a, PDFDict), false))];
}

// Palette colours for the panel, from the palette's base colour space.
function baseOf(pdf, space) {
  let base = pdf.context.lookup(space);
  if (base instanceof PDFArray) {
    const family = plain(base.get(0));
    if (family === "ICCBased") {
      const n = num(pdf.context.lookup(base.get(1)).dict.get(PDFName.of("N")));
      return { family: n === 1 ? "Gray" : n === 4 ? "CMYK" : "RGB", n };
    }
    if (family === "CalRGB") return { family: "RGB", n: 3 };
    if (family === "CalGray") return { family: "Gray", n: 1 };
    if (family === "Lab") {
      const params = pdf.context.lookup(base.get(1), PDFDict);
      const range = params.lookupMaybe(PDFName.of("Range"), PDFArray)?.asArray().map(num) ?? [-100, 100, -100, 100];
      return { family: "Lab", n: 3, range };
    }
    if (family === "DeviceN") return { family: "inks", n: pdf.context.lookup(base.get(1), PDFArray).size() };
    if (family === "Separation") return { family: "ink", n: 1 };
    return { family, n: 1 };
  }
  const family = plain(base);
  return { family: family === "DeviceGray" ? "Gray" : family === "DeviceCMYK" ? "CMYK" : "RGB",
           n: family === "DeviceGray" ? 1 : family === "DeviceCMYK" ? 4 : 3 };
}

function labToRgb(L, a, b) {
  const fy = (L + 16) / 116, fx = fy + a / 500, fz = fy - b / 200;
  const f = (t) => (t > 6 / 29 ? t ** 3 : 3 * (6 / 29) ** 2 * (t - 4 / 29));
  const [X, Y, Z] = [0.9505 * f(fx), f(fy), 1.089 * f(fz)];
  const lin = [3.2404542 * X - 1.5371385 * Y - 0.4985314 * Z, -0.969266 * X + 1.8760108 * Y + 0.041556 * Z,
               0.0556434 * X - 0.2040259 * Y + 1.0572252 * Z];
  return lin.map((c) => 255 * (c <= 0.0031308 ? 12.92 * c : 1.055 * Math.max(c, 0) ** (1 / 2.4) - 0.055));
}

function paletteColours(pdf, arr) {
  const count = num(arr.lookup(2)) + 1;
  const lookup = pdf.context.lookup(arr.get(3));
  const bytes = lookup instanceof PDFRawStream ? decodePDFRawStream(lookup).decode() : lookup.asBytes();
  const base = baseOf(pdf, arr.get(1));
  return Array.from({ length: count }, (_, i) => {
    const v = Array.from(bytes.slice(base.n * i, base.n * (i + 1)));
    if (base.family === "RGB") return hex(v);
    if (base.family === "Gray") return hex([v[0], v[0], v[0]]);
    if (base.family === "CMYK") return hex(v.slice(0, 3).map((c) => (255 - c) * (255 - v[3]) / 255));
    if (base.family === "Lab") {
      const [amin, amax, bmin, bmax] = base.range;
      return hex(labToRgb(v[0] / 2.55, amin + (v[1] / 255) * (amax - amin), bmin + (v[2] / 255) * (bmax - bmin)));
    }
    return null;  // spot inks: their colour comes from a function the panel doesn't run
  });
}

function kindOf(x) {
  if (x instanceof PDFArray && plain(x.get(0)) === "Indexed") return "palette";
  const dict = x instanceof PDFDict ? x : x?.dict;
  if (dict && (dict.has(PDFName.of("PatternType")) || dict.has(PDFName.of("ShadingType")))) return "gradient";
  if (dict && (plain(dict.get(PDFName.of("Type"))) === "ExtGState"
      || (!dict.has(PDFName.of("Subtype")) && ["CA", "ca", "BM"].some((k) => dict.has(PDFName.of(k)))))) return "graphics state";
  if (dict && plain(dict.get(PDFName.of("Type"))) === "Annot") return "annotation";
  if (dict && (plain(dict.get(PDFName.of("Subtype"))) === "Image" || dict.has(PDFName.of("Width")))) return "image";
  if (x instanceof PDFArray) return "colour value";
  if (x && typeof x.decodeText === "function") return "text style";
  return "object";
}

// Palettes that colour an image rather than the page's own drawing.
function imagePalettes(pdf) {
  const refs = new Set();
  for (const [, obj] of pdf.context.enumerateIndirectObjects()) {
    const dict = obj?.dict;
    if (!dict || plain(dict.get(PDFName.of("Subtype"))) !== "Image") continue;
    const space = dict.get(PDFName.of("ColorSpace"));
    if (space && space.objectNumber !== undefined) refs.add(refText(space));
  }
  return refs;
}

function describeSwaps(pdf, theme, forImages) {
  if (theme.isDefault) return [];
  const replace = theme.dict.lookup(PDFName.of("Replace"), PDFArray);
  const swaps = [];
  for (let i = 0; i < replace.size(); i += 2) {
    const a = replace.get(i);
    const b = replace.get(i + 1);
    const x = pdf.context.lookup(a);
    const y = pdf.context.lookup(b);
    const swap = { from: refText(a), to: refText(b), kind: kindOf(x) };
    if (swap.kind === "palette") {
      swap.palette = [paletteColours(pdf, x), paletteColours(pdf, y)];
      swap.forImage = forImages.has(swap.from);
    }
    swaps.push(swap);
  }
  return swaps;
}

// Loading: the default theme is the file as it is; each other theme is the
// same bytes with that theme's swaps applied, made the first time it is shown.
// The Content Security Policy allows neither eval nor WebAssembly. useWasm: false keeps
// pdf.js's decoders in plain JavaScript. pdf.js 6.3 no longer evaluates code it builds,
// so it ignores isEvalSupported; the option stays in case an older build is vendored.
const engineOptions = { isEvalSupported: false, useWasm: false };

async function load(entry) {
  const pdf = await PDFDocument.load(entry.bytes, { updateMetadata: false });
  const themes = readThemes(pdf);
  if (!themes) throw new Error(`${entry.file} has no themes`);
  const forImages = imagePalettes(pdf);
  for (const theme of themes) theme.swaps = describeSwaps(pdf, theme, forImages);
  return { entry, size: entry.bytes.length, themes, views: new Map() };
}

async function viewOf(doc, theme) {
  if (!doc.views.has(theme.name)) {
    let data = doc.entry.bytes.slice();
    if (!theme.isDefault) {
      const copy = await PDFDocument.load(doc.entry.bytes, { updateMetadata: false });
      applyTheme(copy, readThemes(copy).find((t) => t.name === theme.name).dict);
      data = await copy.save({ useObjectStreams: false, updateFieldAppearances: false });
    }
    doc.views.set(theme.name, pdfjsLib.getDocument({ data, ...engineOptions }).promise);
  }
  return doc.views.get(theme.name);
}

// Which theme to show: the one the person picked, matched by its labels;
// otherwise the one that suits the system setting.
function systemScheme() {
  const set = document.documentElement.getAttribute("data-theme");
  if (set === "dark" || set === "light") return set;
  return matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function chosenTheme(doc) {
  if (state.mode !== "auto") {
    const c = state.mode;
    return doc.themes.find((t) => t.scheme === c.scheme && t.contrast === c.contrast && t.tint === c.tint) ?? doc.themes[0];
  }
  const scheme = systemScheme() === "dark" ? "Dark" : "Light";
  const more = matchMedia("(prefers-contrast: more)").matches ? "More" : "";
  return doc.themes.find((t) => t.scheme === scheme && t.contrast === more && !t.tint)
      ?? doc.themes.find((t) => t.scheme === scheme && !t.tint) ?? doc.themes[0];
}

// The controls and the panel.
function fillThemePicker(doc) {
  const auto = document.createElement("button");
  auto.type = "button";
  auto.textContent = "Auto";
  auto.dataset.auto = "true";
  const buttons = [auto, ...doc.themes.map((t) => {
    const b = document.createElement("button");
    b.type = "button";
    const dot = document.createElement("span");
    dot.className = "dot";
    dot.style.background = `rgb(${t.paper.map((v) => Math.round(v * 255)).join(", ")})`;
    b.append(dot, document.createTextNode(t.name));
    b.dataset.theme = t.name;
    return b;
  })];
  for (const b of buttons) {
    b.addEventListener("click", () => {
      if (b.dataset.auto) state.mode = "auto";
      else {
        const t = doc.themes.find((x) => x.name === b.dataset.theme);
        state.mode = { scheme: t.scheme, contrast: t.contrast, tint: t.tint };
      }
      saveChoice(state.mode);
      draw().catch(fail);
    });
  }
  $("theme-picker").replaceChildren(...buttons);
}

function markPicker(theme) {
  for (const b of $("theme-picker").querySelectorAll("button")) {
    const on = state.mode === "auto" ? Boolean(b.dataset.auto) : b.dataset.theme === theme.name;
    b.setAttribute("aria-pressed", String(on));
    // On a phone the themes scroll sideways: keep the chosen one in sight.
    const row = $("theme-picker");
    if (on && row.scrollWidth > row.clientWidth) {
      const left = b.offsetLeft - row.offsetLeft;
      if (left < row.scrollLeft || left + b.offsetWidth > row.scrollLeft + row.clientWidth) {
        row.scrollLeft = left - (row.clientWidth - b.offsetWidth) / 2;
      }
    }
  }
}

function setFacts(id, rows) {
  $(id).replaceChildren(...rows.flatMap(([k, v]) => {
    const dt = document.createElement("dt");
    dt.textContent = k;
    const dd = document.createElement("dd");
    dd.textContent = v;
    return [dt, dd];
  }));
}

function fillFilePanel(doc) {
  setFacts("facts", [
    ["Size", `${doc.size.toLocaleString("en-GB")} bytes, one file`],
    ["Themes", `${doc.themes.length}: ${doc.themes.map((t) => t.name).join(", ")}`],
    ["Page content", "The same bytes in every theme"],
    ["Marked as checked", `${doc.themes.filter((t) => t.checked).length} of ${doc.themes.length} themes`],
  ]);
  $("download").href = doc.entry.file;
}

function fillThemePanel(doc, theme) {
  const labels = [theme.scheme, theme.contrast && `${theme.contrast} contrast`, theme.tint && `${theme.tint} tint`]
    .filter(Boolean).join(", ");
  const counts = new Map();
  for (const s of theme.swaps) counts.set(s.kind, (counts.get(s.kind) ?? 0) + 1);
  const swapped = theme.isDefault ? "Nothing: the default is the file as written"
    : `${theme.swaps.length} object${theme.swaps.length > 1 ? "s" : ""}: `
      + [...counts].map(([k, n]) => `${n} ${k}${n > 1 ? "s" : ""}`).join(", ");
  $("theme-title").textContent = `This theme: ${theme.name}`;
  setFacts("theme-facts", [
    ["Labels", labels],
    ["Paper", hex(theme.paper.map((v) => v * 255))],
    ["Marked as checked", theme.checked ?? "No"],
    ["Swapped", swapped],
  ]);
  $("swaps-box").hidden = theme.isDefault;
  $("swaps-summary").textContent = `Every object swapped for ${theme.name}`;
  $("swaps").replaceChildren(...theme.swaps.map((s) => {
    const li = document.createElement("li");
    const ref = document.createElement("span");
    ref.className = "ref";
    ref.textContent = `${s.from} → ${s.to}`;
    const what = document.createElement("span");
    what.className = "what";
    what.textContent = s.palette ? `${s.forImage ? "image palette" : "palette"}, ${s.palette[0].length} colours` : s.kind;
    li.append(ref, what);
    return li;
  }));

  const palettes = theme.swaps.filter((s) => s.palette)
    .sort((a, b) => (a.forImage - b.forImage) || (b.palette[0].length - a.palette[0].length));
  if (!palettes.length) {
    $("palettes").replaceChildren(Object.assign(document.createElement("p"), {
      className: "note", textContent: "The default theme swaps nothing. Pick another theme to see its palettes beside these.",
    }));
    return;
  }
  $("palettes").replaceChildren(...palettes.map((s, n) => {
    const box = document.createElement("div");
    box.className = "table-box";
    const table = document.createElement("table");
    const head = table.createTHead().insertRow();
    for (const label of ["Entry", doc.themes[0].name, theme.name]) {
      const th = document.createElement("th");
      th.scope = "col";
      th.textContent = label;
      head.append(th);
    }
    const body = table.createTBody();
    s.palette[0].forEach((colour, i) => {
      const row = body.insertRow();
      row.insertCell().textContent = String(i);
      for (const c of [colour, s.palette[1][i]]) {
        const cell = row.insertCell();
        if (c) {
          const sw = document.createElement("span");
          sw.className = "swatch";
          sw.style.background = c;
          cell.append(sw, document.createTextNode(c));
        } else {
          cell.textContent = "spot ink";
        }
      }
    });
    box.append(table);
    const details = document.createElement("details");
    details.open = n === 0;
    const summary = document.createElement("summary");
    summary.textContent = `${s.forImage ? "Image palette" : "Palette"} ${s.from}, ${s.palette[0].length} colours`;
    details.append(summary, box);
    return details;
  }));
}

// Drawing.
let task = null;
let drawing = 0;

async function draw() {
  const doc = state.doc;
  if (!doc) return;
  const ticket = ++drawing;
  const theme = chosenTheme(doc);
  markPicker(theme);
  fillThemePanel(doc, theme);
  $("status").textContent = state.mode === "auto"
    ? `Auto: your system is set to ${systemScheme()}, so this is ${theme.name}.`
    : `Showing ${theme.name}. Your choice carries over to the other documents.`;
  const view = await viewOf(doc, theme);
  if (ticket !== drawing) return;
  const pages = view.numPages;
  state.page = Math.min(Math.max(1, state.page), pages);
  $("pager").hidden = pages < 2;
  $("page-label").textContent = `Page ${state.page} of ${pages}`;
  $("prev").disabled = state.page <= 1;
  $("next").disabled = state.page >= pages;

  const page = await view.getPage(state.page);
  const base = page.getViewport({ scale: 1 });
  const width = Math.max(200, Math.min($("sheet").clientWidth, 860));
  const ratio = window.devicePixelRatio || 1;
  const viewport = page.getViewport({ scale: (width / base.width) * ratio });
  const off = document.createElement("canvas");
  off.width = Math.floor(viewport.width);
  off.height = Math.floor(viewport.height);
  if (task) task.cancel();
  const paper = `rgb(${theme.paper.map((v) => Math.round(v * 255)).join(", ")})`;
  task = page.render({ canvas: off, viewport, background: paper });
  try {
    await task.promise;
  } catch (e) {
    if (e?.name === "RenderingCancelledException") return;
    throw e;
  }
  if (ticket !== drawing) return;
  const canvas = $("page");
  canvas.width = off.width;
  canvas.height = off.height;
  canvas.style.width = `${width}px`;
  canvas.style.aspectRatio = `${base.width} / ${base.height}`;
  canvas.getContext("2d").drawImage(off, 0, 0);
  canvas.setAttribute("aria-label", `${doc.entry.label}, page ${state.page} of ${pages}, drawn in the ${theme.name} theme`);
  canvas.hidden = false;
  $("placeholder").hidden = true;
}

function fail(error) {
  $("status").textContent = `Something went wrong: ${error.message}`;
  $("status").classList.add("error");
}

async function show(entry) {
  $("doc-picker").value = entry.id;
  try {
    if (!loaded.has(entry.id)) {
      $("status").textContent = `Loading ${entry.file}…`;
      loaded.set(entry.id, await load(entry));
    }
    state.doc = loaded.get(entry.id);
    state.page = 1;
    fillFilePanel(state.doc);
    fillThemePicker(state.doc);
    await draw();
  } catch (e) {
    fail(e);
  }
}

// Controls.
// Turning the page brings the top of the new one into view, below the toolbar.
async function turn(by) {
  const pages = state.doc ? (await viewOf(state.doc, chosenTheme(state.doc))).numPages : 1;
  const next = Math.min(Math.max(1, state.page + by), pages);
  if (next === state.page) return;
  state.page = next;
  await draw();
  const canvas = $("page");
  const barBottom = $("toolbar").getBoundingClientRect().bottom;
  if (canvas.getBoundingClientRect().top < barBottom) canvas.scrollIntoView({ block: "start" });
}
$("prev").addEventListener("click", () => turn(-1).catch(fail));
$("next").addEventListener("click", () => turn(1).catch(fail));
document.addEventListener("keydown", (e) => {
  if (e.altKey || e.ctrlKey || e.metaKey || e.shiftKey || $("pager").hidden) return;
  if (e.target instanceof Element && e.target.closest("input, select, textarea, [contenteditable]")) return;
  if (e.key === "ArrowLeft") { e.preventDefault(); turn(-1).catch(fail); }
  if (e.key === "ArrowRight") { e.preventDefault(); turn(1).catch(fail); }
});
$("doc-picker").addEventListener("change", (e) => show(DOCS.find((d) => d.id === e.target.value)));
// The toolbar's height, for the panel and the page to sit below it.
new ResizeObserver(([entry]) => {
  document.documentElement.style.setProperty("--bar-h", `${Math.round(entry.borderBoxSize[0].blockSize)}px`);
}).observe($("toolbar"));
matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => draw().catch(fail));
matchMedia("(prefers-contrast: more)").addEventListener("change", () => draw().catch(fail));
new MutationObserver(() => draw().catch(fail)).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
let resizeTimer = 0;
new ResizeObserver(() => { clearTimeout(resizeTimer); resizeTimer = setTimeout(() => draw().catch(fail), 120); }).observe($("sheet"));
$("code").textContent = applyTheme.toString();
const remembered = savedChoice();
if (remembered) state.mode = remembered;

// Offer only the documents that are here. They are fetched one at a time, in
// order, and the first is shown as soon as it arrives rather than after the rest.
let shown = false;
for (const entry of DOCS) {
  const response = await fetch(entry.file).catch(() => null);
  if (!response?.ok) continue;
  entry.bytes = new Uint8Array(await response.arrayBuffer());
  $("doc-picker").append(new Option(entry.label, entry.id));
  if (!shown) {
    shown = true;
    show(entry);
  }
}
if (!shown) fail(new Error("no themed PDF was found next to this page"));
