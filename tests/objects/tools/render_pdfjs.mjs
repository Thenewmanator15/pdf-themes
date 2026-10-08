// Render pages of a PDF with pdf.js in Node and save PNGs.
// node render_pdfjs.mjs file.pdf outdir scale 1,2,3
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";

// Resolve pdfjs-dist and @napi-rs/canvas from this folder (npm install pdfjs-dist @napi-rs/canvas),
// or from PDFJS_NODE_MODULES if they're installed somewhere else.
const require = createRequire(process.env.PDFJS_NODE_MODULES ? process.env.PDFJS_NODE_MODULES.replace(/\/?$/, "/") : import.meta.url);
const pdfjsRoot = path.dirname(require.resolve("pdfjs-dist/package.json"));
// pdf.js and the canvas must share one Path2D/DOMMatrix implementation.
const napi = require("@napi-rs/canvas");
const { createCanvas } = napi;
globalThis.Path2D = napi.Path2D;
globalThis.DOMMatrix = napi.DOMMatrix;
globalThis.ImageData = napi.ImageData;
const pdfjs = await import(path.join(pdfjsRoot, "legacy/build/pdf.mjs"));

class SharedCanvasFactory {
  constructor() {}
  create(width, height) {
    const canvas = createCanvas(Math.max(1, width), Math.max(1, height));
    return { canvas, context: canvas.getContext("2d") };
  }
  reset(cc, width, height) {
    cc.canvas.width = Math.max(1, width);
    cc.canvas.height = Math.max(1, height);
  }
  destroy(cc) {
    cc.canvas.width = 0;
    cc.canvas.height = 0;
    cc.canvas = null;
    cc.context = null;
  }
}

const [, , file, outdir, scaleStr, pagesStr] = process.argv;
const scale = parseFloat(scaleStr);
const data = new Uint8Array(fs.readFileSync(file));
const doc = await pdfjs.getDocument({
  data,
  CanvasFactory: SharedCanvasFactory,
  standardFontDataUrl: path.join(pdfjsRoot, "standard_fonts") + "/",
  cMapUrl: path.join(pdfjsRoot, "cmaps") + "/",
  cMapPacked: true,
  wasmUrl: path.join(pdfjsRoot, "wasm") + "/",
  iccUrl: path.join(pdfjsRoot, "iccs") + "/",
  isEvalSupported: false,
  verbosity: 0,
}).promise;

const pages = pagesStr ? pagesStr.split(",").map(Number) : [...Array(doc.numPages).keys()].map((i) => i + 1);
for (const n of pages) {
  const page = await doc.getPage(n);
  const viewport = page.getViewport({ scale });
  const canvas = createCanvas(Math.ceil(viewport.width), Math.ceil(viewport.height));
  const ctx = canvas.getContext("2d");
  ctx.fillStyle = "white";
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  await page.render({
    canvasContext: ctx,
    canvas,
    viewport,
    annotationMode: pdfjs.AnnotationMode.ENABLE,
  }).promise;
  fs.writeFileSync(path.join(outdir, `j${String(n).padStart(3, "0")}.png`), canvas.toBuffer("image/png"));
}
