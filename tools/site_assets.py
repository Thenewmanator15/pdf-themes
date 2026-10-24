"""Make the colours and pictures for the site's pages, and check every colour.

    python tools/site_assets.py

Writes into demo/site/:

- themes.css: the pages' colours in each of the eight standard themes. Text
  colours are moved towards the ink until they reach 4.5:1 against the paper
  and the panels (7:1 in the more contrast themes), and line colours until
  they reach 3:1 (4.5:1), the same fit the theme lab uses.
- picture.jpg: a landscape drawn by this script, for the demo of what
  inverting does to a picture.
- theme-<mode>.webp and theme-inverted.webp: the theme lab's page
  (demo/theme-lab-themed.pdf) in each of its themes, shown as a reader that
  knows about themes would show it, and its light page inverted.

It also writes the demo chart into demo/why/index.html, between the lines
<!-- chart --> and <!-- /chart -->. Run it again after changing a colour
here. It prints every contrast it checked and stops if one falls short.
"""

import math
import pathlib
import re
import sys

import numpy as np
import pikepdf
import pypdfium2
from PIL import Image

from pdfthemes import core

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE = ROOT / "demo" / "site"

# -- Colour ------------------------------------------------------------------


def rgb(hex_):
    return np.array([int(hex_[i:i + 2], 16) / 255 for i in (0, 2, 4)])


def hex_(c):
    return "#" + "".join(f"{round(float(min(max(v, 0), 1)) * 255):02X}" for v in c)


def linear(c):
    c = np.asarray(c, dtype=float)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def gamma(c):
    c = np.clip(np.asarray(c, dtype=float), 0, 1)
    return np.where(c <= 0.0031308, 12.92 * c, 1.055 * c ** (1 / 2.4) - 0.055)


def luminance(c):
    r, g, b = linear(c)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = luminance(a), luminance(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


# OKLab, so a colour moves towards the ink the way Typst's color.mix moves it
# in the theme lab.
_M1 = np.array([[0.4122214708, 0.5363325363, 0.0514459929],
                [0.2119034982, 0.6806995451, 0.1073969566],
                [0.0883024619, 0.2817188376, 0.6299787005]])
_M2 = np.array([[0.2104542553, 0.7936177850, -0.0040720468],
                [1.9779984951, -2.4285922050, 0.4505937099],
                [0.0259040371, 0.7827717662, -0.8086757660]])


def oklab(c):
    return _M2 @ np.cbrt(_M1 @ linear(c))


def from_oklab(lab):
    return gamma(np.linalg.inv(_M1) @ (np.linalg.inv(_M2) @ lab) ** 3)


def fit(colour, grounds, ink, target, visions=None):
    """Move a colour towards the ink, 5 % at a time, until it reaches the target against every ground.

    With `visions`, the target has to hold for each of those simulated kinds of colour vision too."""
    base, towards = oklab(rgb(colour)), oklab(rgb(ink))
    visions = visions or {"typical": np.eye(3)}
    for k in range(0, 100, 5):
        out = from_oklab(base * (1 - k / 100) + towards * (k / 100))
        if all(contrast(simulate(out, m), simulate(rgb(g), m)) >= target for g in grounds for m in visions.values()):
            return out
    return rgb(ink)


# Colour vision deficiency, simulated as Machado, Oliveira and Fernandes (2009) do it at
# severity 1, on linear sRGB (as colorspacious and most checkers do).
VISIONS = {
    "typical": np.eye(3),
    "protan": np.array([[0.152286, 1.052583, -0.204868], [0.114503, 0.786281, 0.099216],
                        [-0.003882, -0.048116, 1.051998]]),
    "deutan": np.array([[0.367322, 0.860646, -0.227968], [0.280085, 0.672501, 0.047413],
                        [-0.011820, 0.042940, 0.968881]]),
    "tritan": np.array([[1.255528, -0.076749, -0.178779], [-0.078411, 0.930809, 0.147602],
                        [0.004733, 0.691367, 0.303900]]),
}
SERIES_APART = 0.1   # the smallest OKLab distance between two of the chart's lines, under every vision


def simulate(c, matrix):
    return gamma(np.clip(matrix @ linear(c), 0, 1))


# -- The themes ----------------------------------------------------------------

# The papers are the theme lab's (tests/theme-lab/theme-lab.typ). Each theme
# also has a panel colour for boxes and a rule colour for lines between things.
THEMES = {
    "light": dict(name="Light", scheme="light", paper="FFFFFF", panel="F3F4F6", rule="D3D6DD", ink="1B1D21"),
    "dark": dict(name="Dark", scheme="dark", paper="18191C", panel="222428", rule="3A3D45", ink="E8EAED"),
    "light-contrast": dict(name="Light, more contrast", scheme="light", paper="FFFFFF", panel="F2F2F2",
                           rule="6E6E6E", ink="000000", more=True),
    "dark-contrast": dict(name="Dark, more contrast", scheme="dark", paper="000000", panel="141414",
                          rule="9C9C9C", ink="FFFFFF", more=True),
    "cream": dict(name="Cream", scheme="light", paper="FDF6E3", panel="F5ECD3", rule="E3D9BD", ink="1B1D21"),
    "peach": dict(name="Peach", scheme="light", paper="FDE7DC", panel="F7DBCD", rule="ECC6B4", ink="1B1D21"),
    "yellow": dict(name="Yellow", scheme="light", paper="FFF7C2", panel="F8EDAC", rule="E6D98A", ink="1B1D21"),
    "turquoise": dict(name="Turquoise", scheme="light", paper="E3EEFA", panel="D6E4F4", rule="BCD0E6", ink="1B1D21"),
}

# Text colours other than the ink: a light and a dark starting point each.
TEXT_ROLES = {
    "muted": ("575D68", "A5ABB6"),     # secondary text
    "accent": ("1E58B4", "8FB2FF"),    # links and controls
    "est": ("2C7A27", "9FD49A"),       # evidence: established
    "meas": ("1C6AA0", "8CC2E6"),      # evidence: measured
    "open": ("8F6200", "E8B04A"),      # evidence: open
}
# The chart's three series: a blue, an orange (Okabe and Ito's) and a wine red (Tol's), picked
# so that once each theme has fitted them they stay at least SERIES_APART from each other, and
# reach their contrast against the paper, under typical vision and the three simulated
# deficiencies. Inverting swaps the blue and the orange, which the demo's note relies on.
SERIES = ("3F90DA", "E69F00", "882255")


def theme_colours(t):
    more = t.get("more", False)
    text_min, line_min = (7, 4.5) if more else (4.5, 3)
    dark = t["scheme"] == "dark"
    grounds = (t["paper"], t["panel"])
    out = {"paper": rgb(t["paper"]), "panel": rgb(t["panel"]), "rule": rgb(t["rule"]), "ink": rgb(t["ink"])}
    for role, (light_start, dark_start) in TEXT_ROLES.items():
        out[role] = fit(dark_start if dark else light_start, grounds, t["ink"], text_min)
    for i, s in enumerate(SERIES, 1):
        out[f"s{i}"] = fit(s, (t["paper"],), t["ink"], line_min, VISIONS)
    # The grid is the rule colour, held to 3:1 only in the more contrast themes,
    # where the grid is drawn heavier too.
    out["grid"] = fit(t["rule"], (t["paper"],), t["ink"], 3) if more else rgb(t["rule"])
    out["line-w"], out["grid-w"], out["axis-w"] = (3.5, 1.4, 2) if more else (2.25, 1, 1.25)
    # Dashes: the more contrast themes lengthen the gaps along with the lines.
    out["dash2"], out["dash3"] = ("12 7", "3.5 7") if more else ("9 5", "2.5 4.5")
    return out, text_min, line_min


def check(mode, t, c, text_min, line_min):
    """Every text colour against the paper and the panel, every line colour against the paper."""
    rows, failed = [], False
    for role in ("ink", *TEXT_ROLES):
        for ground in ("paper", "panel"):
            r = contrast(c[role], c[ground])
            failed |= r < text_min
            rows.append(f"  {role:6} on {ground:5} {r:5.2f}:1 (needs {text_min})")
    for role in ("s1", "s2", "s3"):
        worst = min((contrast(simulate(c[role], m), simulate(c["paper"], m)), v) for v, m in VISIONS.items())
        failed |= worst[0] < line_min
        rows.append(f"  {role:6} on paper {worst[0]:5.2f}:1 at worst ({worst[1]}; needs {line_min})")
    if t.get("more"):
        r = contrast(c["grid"], c["paper"])
        failed |= r < 3
        rows.append(f"  grid   on paper {r:5.2f}:1 (needs 3)")
    apart = min((float(np.linalg.norm(oklab(simulate(c[a], m)) - oklab(simulate(c[b], m)))), v, a, b)
                for v, m in VISIONS.items() for a, b in (("s1", "s2"), ("s1", "s3"), ("s2", "s3")))
    failed |= apart[0] < SERIES_APART
    rows.append(f"  lines apart by {apart[0]:.3f} at least ({apart[2]} and {apart[3]}, {apart[1]}; needs {SERIES_APART})")
    print(f"{t['name']}:")
    print("\n".join(rows))
    return failed


def css_block(c, scheme):
    names = ("paper", "panel", "rule", "ink", *TEXT_ROLES, "s1", "s2", "s3", "grid")
    body = [f"color-scheme: {scheme};"]
    body += [f"--{n}: {hex_(c[n])};" for n in names]
    body += [f"--fig-line-w: {c['line-w']};", f"--fig-grid-w: {c['grid-w']};", f"--fig-axis-w: {c['axis-w']};",
             f"--fig-dash2: {c['dash2']};", f"--fig-dash3: {c['dash3']};"]
    return " ".join(body)


def write_css():
    blocks, failed = {}, False
    for mode, t in THEMES.items():
        c, text_min, line_min = theme_colours(t)
        failed |= check(mode, t, c, text_min, line_min)
        blocks[mode] = (css_block(c, t["scheme"]), c)
    if failed:
        sys.exit("site_assets: a colour fell short of its contrast; nothing written")
    light = blocks["light"][0]
    lines = [
        "/* Made by tools/site_assets.py. Do not edit: change the colours there and run it again.",
        "   Every text colour reaches 4.5:1 against the paper and the panels (7:1 in the more",
        "   contrast themes), and every chart line 3:1 against the paper (4.5:1), for typical",
        "   vision and simulated protan, deutan and tritan vision. The dark themes are for",
        "   screens only: a printed page has no dark paper, so it prints in light colours. */",
        f":root {{ {light} }}",
        f"@media screen and (prefers-color-scheme: dark) {{ :root:not([data-theme]) {{ {blocks['dark'][0]} }} }}",
        f"@media (prefers-contrast: more) {{ :root:not([data-theme]) {{ {blocks['light-contrast'][0]} }} }}",
        "@media screen and (prefers-contrast: more) and (prefers-color-scheme: dark) { "
        f":root:not([data-theme]) {{ {blocks['dark-contrast'][0]} }} }}",
    ]
    for mode, (block, _) in blocks.items():
        rule = f':root[data-theme="{mode}"] {{ {block} }}'
        lines.append(f"@media screen {{ {rule} }}" if THEMES[mode]["scheme"] == "dark" else rule)
    # The inverted demo: the light figure, whatever the page's theme, turned
    # into its negative the way a reader's colour inversion does it.
    lines.append(f'.demo[data-view="inverted"] .stage {{ {light} background: var(--paper); filter: invert(1); }}')
    (SITE / "themes.css").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {SITE / 'themes.css'}")


# -- A picture to invert -------------------------------------------------------


def write_picture(w=720, h=450):
    """A landscape: sky, sun, two ranges of hills and a meadow. Drawn, not photographed."""
    rng = np.random.default_rng(7)
    y, x = np.mgrid[0:h, 0:w] / np.array([h, w])[:, None, None]
    horizon = 0.62
    sky_top, sky_low = rgb("2F64A8"), rgb("CFE2F2")
    t = np.clip(y / horizon, 0, 1)[..., None]
    img = sky_top * (1 - t) ** 1.2 + sky_low * (1 - (1 - t) ** 1.2)
    # The sun and its glow.
    sx, sy = 0.73, 0.27
    d = np.hypot((x - sx) * w / h, y - sy)
    img = img + (rgb("FFF1C9") - img) * np.clip(np.exp(-(d / 0.16) ** 2) * 0.55, 0, 1)[..., None]
    img = np.where((d < 0.055)[..., None], rgb("FFF8E6"), img)

    def ridge(base, amp, seed_waves):
        r = np.full(w, base)
        for k, (f, a) in enumerate(seed_waves):
            r += amp * a * np.sin(2 * np.pi * f * np.arange(w) / w + rng.uniform(0, 2 * np.pi))
        return r

    for base, amp, waves, colour, haze in (
            (0.50, 0.06, ((1.3, 1), (2.9, 0.5), (7.1, 0.18), (17, 0.06)), "7F95B0", 0.45),
            (0.60, 0.05, ((1.7, 1), (3.7, 0.45), (9.3, 0.15), (23, 0.05)), "4E6B8A", 0.2),
            (0.74, 0.035, ((0.9, 1), (2.3, 0.4), (5.9, 0.12)), "5F8F4B", 0.0)):
        top = ridge(base, amp, waves)
        mask = y >= top[None, :]
        shade = np.clip((y - top[None, :]) / 0.35, 0, 1)[..., None]
        fill = rgb(colour) * (1 - 0.35 * shade)
        fill = fill * (1 - haze) + sky_low * haze
        img = np.where(mask[..., None], fill, img)
    # A little grain, as a photograph has.
    img = img + rng.normal(0, 0.012, img.shape)
    Image.fromarray((np.clip(img, 0, 1) * 255).round().astype(np.uint8)).save(
        SITE / "picture.jpg", quality=86, optimize=True, progressive=True)
    print(f"wrote {SITE / 'picture.jpg'}")


# -- The theme lab in each theme ---------------------------------------------------

MODES = {"Light": "light", "Dark": "dark", "Light, more contrast": "light-contrast",
         "Dark, more contrast": "dark-contrast", "Cream": "cream", "Peach": "peach", "Yellow": "yellow",
         "Turquoise": "turquoise"}


def write_theme_pages(width_px=560):
    themed = ROOT / "demo" / "theme-lab-themed.pdf"
    tmp = ROOT / "out" / "site"
    tmp.mkdir(parents=True, exist_ok=True)
    with pikepdf.open(themed) as pdf:
        names = core.themes(pdf)
    missing = set(MODES) - set(names)
    if missing:
        sys.exit(f"site_assets: the theme lab has no theme called {sorted(missing)}")
    light = None
    for name in names:
        with pikepdf.open(themed) as pdf:
            paper = core.apply(pdf, name)
            core.paint_paper(pdf, paper)
            core.save(pdf, tmp / f"{MODES[name]}.pdf")
        page = pypdfium2.PdfDocument(tmp / f"{MODES[name]}.pdf")[0]
        image = page.render(scale=width_px / page.get_width()).to_pil().convert("RGB")
        image.save(SITE / f"theme-{MODES[name]}.webp", quality=82, method=6)
        if name == "Light":
            light = image
        print(f"wrote {SITE / f'theme-{MODES[name]}.webp'}")
    inverted = Image.fromarray(255 - np.asarray(light))
    inverted.save(SITE / "theme-inverted.webp", quality=82, method=6)
    print(f"wrote {SITE / 'theme-inverted.webp'}")
    write_share_image()


def write_share_image(w=1200, h=630):
    """The picture a link preview shows: the theme lab's page in its eight themes, cropped to the top."""
    tiles = [Image.open(SITE / f"theme-{mode}.webp").convert("RGB") for mode in MODES.values()]
    gap, margin = 12, 24
    tile_w = (w - 2 * margin - 3 * gap) // 4
    tile_h = (h - 2 * margin - gap) // 2
    canvas = Image.new("RGB", (w, h), (231, 232, 236))
    for i, tile in enumerate(tiles):
        scaled = tile.resize((tile_w, round(tile.height * tile_w / tile.width)), Image.LANCZOS)
        x = margin + (i % 4) * (tile_w + gap)
        y = margin + (i // 4) * (tile_h + gap)
        canvas.paste(scaled.crop((0, 0, tile_w, tile_h)), (x, y))
    canvas.save(SITE / "share.jpg", quality=86, optimize=True, progressive=True)
    print(f"wrote {SITE / 'share.jpg'}")


# -- The demo chart ----------------------------------------------------------------


def chart_svg():
    """Temperature over a day at three made-up sites, with a second cue for each line."""
    W, H = 600, 370
    x0, x1, y0, y1 = 64, 500, 26, 296          # the plot area
    t_lo, t_hi = 0, 25
    hours = np.linspace(0, 24, 97)

    def X(h):
        return x0 + (x1 - x0) * h / 24

    def Y(v):
        return y1 - (y1 - y0) * (v - t_lo) / (t_hi - t_lo)

    def day(mean, swing, peak, ripple=0.0, phase=0.0):
        return mean + swing * np.sin((hours - peak + 6) / 24 * 2 * np.pi) + ripple * np.sin(hours / 24 * 6 * np.pi + phase)

    sites = [
        ("A", "s1", day(12.5, 7.0, 15), "circle"),
        ("B", "s2", day(10.0, 4.5, 16, 0.8, 1.0), "square"),
        ("C", "s3", day(15.0, 2.5, 14, 0.6, 2.2), "triangle"),
    ]

    def when(i):
        return f"{int(hours[i]):02d}:{int(round(hours[i] % 1 * 60)):02d}"

    def described(name, v):
        lo, hi = int(np.argmin(v)), int(np.argmax(v))
        return (f"Site {name} is lowest at {when(lo)}, at {v[lo]:.1f} °C, and highest at {when(hi)}, "
                f"at {v[hi]:.1f} °C.")

    desc = (" ".join(described(name, v) for name, _, v, _ in sites)
            + " With the markers, dashes and labels shown, Site A's line is solid with circles, Site B's is dashed"
            + " with squares and Site C's is dotted with triangles, and each line is labelled at its right-hand end.")
    out = [f'<svg class="chart" viewBox="0 0 {W} {H}" role="img" aria-labelledby="chart-title" aria-describedby="chart-desc">',
           '<title id="chart-title">Temperature through one day at three sites (made-up data)</title>',
           f'<desc id="chart-desc">{desc}</desc>',
           '<g class="grid">']
    for v in range(t_lo, t_hi + 1, 5):
        out.append(f'<line x1="{x0}" x2="{x1}" y1="{Y(v):.1f}" y2="{Y(v):.1f}"/>')
    for h in range(0, 25, 6):
        out.append(f'<line x1="{X(h):.1f}" x2="{X(h):.1f}" y1="{y0}" y2="{y1}"/>')
    out.append('</g>')
    out.append(f'<path class="axis" d="M{x0} {y0}V{y1}H{x1}"/>')
    out.append('<g class="ticks">')
    for v in range(t_lo, t_hi + 1, 5):
        out.append(f'<text x="{x0 - 8}" y="{Y(v) + 4.5:.1f}" text-anchor="end">{v}</text>')
    for h in range(0, 25, 6):
        out.append(f'<text x="{X(h):.1f}" y="{y1 + 26}" text-anchor="middle">{h:02d}:00</text>')
    out.append(f'<text x="{(x0 + x1) / 2:.0f}" y="{H - 10}" text-anchor="middle">Time of day</text>')
    out.append(f'<text transform="translate(18 {(y0 + y1) / 2:.0f}) rotate(-90)" text-anchor="middle">'
               'Temperature (°C)</text>')
    out.append('</g>')
    ends = []
    for name, cls, v, mark in sites:
        d = "M" + " L".join(f"{X(h):.1f} {Y(t):.1f}" for h, t in zip(hours, v))
        out.append(f'<g class="series {cls}">')
        out.append(f'<path class="line" d="{d}"/>')
        out.append('<g class="marks">')
        for h in range(0, 25, 3):
            t = v[np.argmin(abs(hours - h))]
            cx, cy = X(h), Y(t)
            if mark == "circle":
                out.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="5"/>')
            elif mark == "square":
                out.append(f'<rect x="{cx - 4.5:.1f}" y="{cy - 4.5:.1f}" width="9" height="9"/>')
            else:
                out.append(f'<path d="M{cx:.1f} {cy - 6:.1f}L{cx + 5.5:.1f} {cy + 4:.1f}L{cx - 5.5:.1f} '
                           f'{cy + 4:.1f}Z"/>')
        out.append('</g></g>')
        ends.append((name, cls, Y(v[-1])))
    # Labels at the ends of the lines, pushed apart evenly where they would overlap.
    ends.sort(key=lambda e: e[2])
    ys = [e[2] for e in ends]
    for _ in range(100):
        for i in range(len(ys) - 1):
            gap = ys[i + 1] - ys[i]
            if gap < 30:
                ys[i] -= (30 - gap) / 2
                ys[i + 1] += (30 - gap) / 2
    for (name, cls, _), y in zip(ends, ys):
        out.append(f'<text class="end-label {cls}" x="{x1 + 10}" y="{y + 5:.1f}">Site {name}</text>')
    # A key by colour alone, shown instead of the labels when the second cues are off.
    out.append('<g class="key">')
    for i, (name, cls, *_) in enumerate(sites):
        kx = x0 + 14 + i * 96
        out.append(f'<line class="{cls}" x1="{kx}" x2="{kx + 22}" y1="{y0 + 14}" y2="{y0 + 14}"/>')
        out.append(f'<text x="{kx + 28}" y="{y0 + 18.5}">Site {name}</text>')
    out.append('</g>')
    out.append('</svg>')
    return "\n".join(out)


def write_chart():
    page = ROOT / "demo" / "why" / "index.html"
    if not page.exists():
        print(f"skipped the chart: {page} doesn't exist yet")
        return
    html = page.read_text(encoding="utf-8")
    pattern = re.compile(r"(<!-- chart -->).*?(<!-- /chart -->)", re.S)
    new, n = pattern.subn(lambda m: m.group(1) + "\n" + chart_svg() + "\n" + m.group(2), html)
    if n != 1:
        sys.exit(f"site_assets: expected one chart marker pair in {page}, found {n}")
    page.write_text(new, encoding="utf-8", newline="\n")
    print(f"wrote the chart into {page}")


def number_references():
    """Number the evidence page's citations in the order they first appear, and put its list in that order.

    A citation is <a class="ref" href="#key">[n]</a>, and each reference is an <li id="key"> in <ol class="refs">.
    Every citation must have a reference and every reference a citation."""
    page = ROOT / "demo" / "evidence" / "index.html"
    if not page.exists():
        print(f"skipped the references: {page} doesn't exist yet")
        return
    html = page.read_text(encoding="utf-8")
    start, end = html.index('<ol class="refs">'), html.index("</ol>", html.index('<ol class="refs">'))
    body, refs = html[:start], html[start:end]
    items = dict(re.findall(r'(?s)<li id="([\w-]+)">(.*?)</li>', refs))
    order = []
    for key in re.findall(r'<a class="ref" href="#([\w-]+)">', body):
        if key not in order:
            order.append(key)
    missing = [k for k in order if k not in items]
    unused = [k for k in items if k not in order]
    if missing or unused:
        sys.exit(f"site_assets: references cited but not listed {missing}; listed but not cited {unused}")
    number = {k: i + 1 for i, k in enumerate(order)}
    body = re.sub(r'<a class="ref" href="#([\w-]+)">\[[^\]]*\]</a>',
                  lambda m: f'<a class="ref" href="#{m.group(1)}">[{number[m.group(1)]}]</a>', body)
    refs = '<ol class="refs">\n' + "\n".join(f'    <li id="{k}">{items[k]}</li>' for k in order) + "\n  "
    page.write_text(body + refs + html[end:], encoding="utf-8", newline="\n")
    print(f"numbered {len(order)} references in {page}")


def tidy_evidence_tables():
    """Give the evidence page's tables what screen readers and links need, each time the page changes.

    Each table gets a hidden caption (its section's heading) and a focusable, named scroll box;
    each body row's first cell becomes a row header; and the first row citing a reference gets
    id="row-<key>", which the other pages link to. Running it twice changes nothing."""
    page = ROOT / "demo" / "evidence" / "index.html"
    if not page.exists():
        return
    html = page.read_text(encoding="utf-8")
    out, pos, n = [], 0, 0
    heading = ""
    used = set(re.findall(r'id="(row-[\w-]+)"', html))
    for m in re.finditer(r'<h[23][^>]*>(.*?)</h[23]>|<div class="scroll"[^>]*>\s*<table>(.*?)</table>', html, re.S):
        if m.group(1) is not None:
            heading = re.sub(r"<[^>]+>", "", m.group(1)).strip()
            continue
        n += 1
        body = m.group(2)
        cap_id = f"t-{n}"
        if "<caption" not in body:
            body = f'<caption id="{cap_id}" class="visually-hidden">{heading}</caption>' + body
        else:
            cap_id = re.search(r'<caption id="([^"]+)"', body).group(1)

        def row(r):
            tr, cells = r.group(1), r.group(2)
            cells = re.sub(r"^(\s*)<td>(.*?)</td>", r'\1<th scope="row">\2</th>', cells, count=1, flags=re.S)
            if "id=" not in tr:
                key = re.search(r'<a class="ref" href="#([\w-]+)">', cells)
                if key and f"row-{key.group(1)}" not in used:
                    used.add(f"row-{key.group(1)}")
                    tr = tr[:-1] + f' id="row-{key.group(1)}">'
            return tr + cells + "</tr>"

        body = re.sub(r"<thead>(.*?)</thead>", lambda t: "<thead>" + t.group(1).replace("<th>", '<th scope="col">') + "</thead>",
                      body, flags=re.S)
        tbody = re.search(r"<tbody>(.*?)</tbody>", body, re.S)
        if tbody:
            rows = re.sub(r"(<tr[^>]*>)(.*?)</tr>", row, tbody.group(1), flags=re.S)
            body = body[:tbody.start(1)] + rows + body[tbody.end(1):]
        out.append(html[pos:m.start()])
        out.append(f'<div class="scroll" role="region" tabindex="0" aria-labelledby="{cap_id}"><table>{body}</table>')
        pos = m.end()
    out.append(html[pos:])
    new = "".join(out)
    if new != html:
        page.write_text(new, encoding="utf-8", newline="\n")
    print(f"tidied {n} tables in {page}")


if __name__ == "__main__":
    SITE.mkdir(parents=True, exist_ok=True)
    write_css()
    write_picture()
    write_theme_pages()
    write_chart()
    number_references()
    tidy_evidence_tables()
