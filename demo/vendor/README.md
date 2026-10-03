# Libraries used by the demo

- `pdf.min.mjs`: pdf.js 6.3.289, legacy build (works in browsers without the newest JavaScript features). Apache 2.0, see `LICENSE-pdfjs.txt`.
- `pdf-worker.base64.txt`: the matching `pdf.worker.min.mjs`, base64 encoded. Its source contains raw control characters, which some hosts refuse to serve as text, so the demo decodes it and starts the worker from a blob URL.
- `pdf-lib.min.js`: pdf-lib 1.17.1. MIT, see `LICENSE-pdf-lib.md`. Five characters inside string literals are written as escapes (`"\x17"` and `"\uFFFD"`) instead of raw characters, for the same reason. The code is otherwise unchanged.

The demo uses pdf-lib to swap a theme's objects, the way a theme-aware reader would, and pdf.js to draw the result.
