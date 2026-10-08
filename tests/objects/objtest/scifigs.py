"""Scientific figures, made by real plotting tools and imported as form XObjects.

The light and dark builds run the same plotting code with only the colours changed, so the
figures carry each tool's own way of writing PDF: matplotlib's Type 3 fonts, background
rectangles, reused marker XObjects, Indexed heatmaps and Type 4 meshes, and pgfplots' Type 5
mesh shadings, axial-shading colour bars and Type 1 fonts.

Data colour maps are chosen per figure: viridis, inferno and similar sequential maps work on
both papers and stay; diverging maps with a white middle (RdBu) glare on dark paper, so the
dark build uses berlin, one of the dark-midpoint maps matplotlib 3.10 took from Crameri's
Scientific colour maps.
"""
import os
import subprocess

import numpy as np
import pikepdf
from pikepdf import Array, Dictionary, Name, String

from .core import Page, circle_path, n, poly_path, rect_path, round_rect_path
from .palette import HUES

FIG_W, FIG_H = 2.3, 1.72          # inches; tiles scale them to fit
CACHE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "out", "figures")


# -- matplotlib ----------------------------------------------------------------------------------

def mpl_rc(pal):
    from cycler import cycler
    h = pal.hexstr
    return {
        "figure.facecolor": h("tile"), "axes.facecolor": h("tile"), "savefig.facecolor": h("tile"),
        "axes.edgecolor": h("muted"), "axes.labelcolor": h("ink"), "text.color": h("ink"),
        "xtick.color": h("muted"), "ytick.color": h("muted"), "xtick.labelcolor": h("ink"),
        "ytick.labelcolor": h("ink"), "grid.color": h("rule"), "legend.facecolor": h("tile"),
        "legend.edgecolor": h("rule"), "legend.labelcolor": h("ink"),
        "axes.prop_cycle": cycler(color=[h(r) for r in ("accent", "red", "green", "orange", "purple", "teal")]),
        "font.size": 6.5, "axes.titlesize": 6.5, "legend.fontsize": 5.5, "lines.linewidth": 1.0,
        "axes.linewidth": 0.6, "xtick.major.width": 0.6, "ytick.major.width": 0.6, "errorbar.capsize": 2,
        "savefig.dpi": 200, "pdf.compression": 6,
    }


def diverging(pal):
    return "berlin" if pal.dark else "RdBu_r"


def mpl_figures():
    """name -> function(pal, rng) returning a matplotlib Figure."""
    import matplotlib.pyplot as plt
    from matplotlib import colors

    def fig(**kw):
        return plt.subplots(figsize=(FIG_W, FIG_H), layout="constrained", **kw)

    def lines(pal, rng):
        f, ax = fig()
        x = np.linspace(0, 10, 300)
        for k in range(4):
            ax.plot(x, np.sin(x + k) * np.exp(-x / 8), label="run %d" % (k + 1))
        ax.grid(True)
        ax.legend(ncols=2, loc="upper right")
        ax.set_xlabel(r"time $t$ (ms)")
        ax.set_ylabel(r"$V_\mathrm{out}$ (V)")
        return f

    def scatter(pal, rng):
        f, ax = fig()
        xs, ys = rng.normal(size=1500), rng.normal(size=1500)
        sc = ax.scatter(xs, ys, s=4, c=np.hypot(xs, ys), cmap="viridis", alpha=0.8, linewidths=0)
        f.colorbar(sc, ax=ax, label="radius")
        return f

    def errors(pal, rng):
        f, ax = fig()
        x = np.linspace(0, 10, 200)
        y, e = np.sin(x), 0.2 + 0.1 * np.cos(x)
        ax.fill_between(x, y - e, y + e, alpha=0.3, linewidth=0)
        ax.plot(x, y)
        ax.errorbar(x[::20], y[::20] + rng.normal(0, 0.08, 10), yerr=e[::20], fmt="o", ms=2.5)
        return f

    def hist(pal, rng):
        f, ax = fig()
        ax.hist(rng.normal(size=2000), bins=24, hatch="////", edgecolor=pal.hexstr("accent"),
                facecolor=pal.hexstr("tile"), linewidth=0.6)
        ax.hist(rng.normal(1.5, 0.6, size=800), bins=24, alpha=0.6, color=pal.hexstr("orange"))
        return f

    def heat_div(pal, rng):
        f, ax = fig()
        yy, xx = np.mgrid[-2:2:40j, -3:3:60j]
        z = np.sin(2 * xx) * np.exp(-yy ** 2) + 0.15 * rng.normal(size=xx.shape)
        im = ax.imshow(z, cmap=diverging(pal), vmin=-1.2, vmax=1.2, interpolation="nearest")
        f.colorbar(im, ax=ax)
        return f

    def heat_seq(pal, rng):
        f, ax = fig()
        yy, xx = np.mgrid[-2:2:40j, -3:3:60j]
        im = ax.imshow(np.exp(-(xx ** 2 + yy ** 2) / 2) + 0.1 * rng.random(xx.shape), cmap="viridis")
        f.colorbar(im, ax=ax)
        return f

    def gouraud(pal, rng):
        f, ax = fig()
        X, Y = np.meshgrid(np.linspace(-3, 3, 24), np.linspace(-2, 2, 16))
        ax.pcolormesh(X, Y, np.cos(X) * np.exp(-Y ** 2 / 2), shading="gouraud", cmap=diverging(pal))
        return f

    def contours(pal, rng):
        f, ax = fig()
        X, Y = np.meshgrid(np.linspace(-3, 3, 80), np.linspace(-2, 2, 60))
        Z = np.cos(X) * np.exp(-Y ** 2 / 2) - 0.3 * np.exp(-((X - 1) ** 2 + (Y - 1) ** 2))
        ax.contourf(X, Y, Z, 10, cmap=diverging(pal))
        cs = ax.contour(X, Y, Z, 5, colors=pal.hexstr("ink"), linewidths=0.5)
        ax.clabel(cs, fontsize=5)
        return f

    def surface(pal, rng):
        f = plt.figure(figsize=(FIG_W, FIG_H), layout="constrained")
        ax = f.add_subplot(projection="3d")
        X, Y = np.meshgrid(np.linspace(-2, 2, 24), np.linspace(-2, 2, 24))
        ax.plot_surface(X, Y, np.exp(-(X ** 2 + Y ** 2)) * np.cos(2 * X), cmap="viridis", linewidth=0)
        ax.set_facecolor(pal.hexstr("tile"))
        for axis in (ax.xaxis, ax.yaxis, ax.zaxis):
            axis.set_pane_color(colors.to_rgba(pal.hexstr("rule"), 0.4))
        return f

    def spectrum(pal, rng):
        f, ax = fig()
        m = np.sort(rng.uniform(1, 300, 160))
        i = rng.exponential(1, 160) ** 2
        peaks = {28: 40.0, 44: 25.0, 105: 60.0, 152: 18.0}
        m = np.concatenate([m, list(peaks)])
        i = np.concatenate([i, list(peaks.values())])
        ax.vlines(m, 1e-3, i, linewidth=0.6)
        ax.set_yscale("log")
        ax.set_ylim(1e-2, 200)
        for mz, inten in peaks.items():
            ax.annotate("%d" % mz, (mz, inten), xytext=(0, 2), textcoords="offset points", ha="center", fontsize=5)
        ax.set_xlabel("m/z")
        ax.set_ylabel("counts")
        return f

    def rasterised(pal, rng):
        f, ax = fig()
        ax.scatter(rng.normal(size=20000), rng.normal(size=20000), s=1, rasterized=True, linewidths=0)
        ax.set_title("20,000 points, rasterised")
        return f

    def spectrogram(pal, rng):
        f, ax = fig()
        fs = 8000
        t = np.arange(0, 2, 1 / fs)
        sig = np.sin(2 * np.pi * (300 + 600 * t) * t) + 0.3 * rng.normal(size=t.size)
        _, _, _, im = ax.specgram(sig, Fs=fs, NFFT=256, noverlap=128, cmap="inferno")
        f.colorbar(im, ax=ax, label="dB")
        ax.set_ylabel("Hz")
        return f

    def smith(pal, rng):
        f, ax = plt.subplots(figsize=(FIG_H, FIG_H), layout="constrained")
        ax.set_aspect("equal")
        ax.axis("off")
        grid = dict(color=pal.hexstr("rule"), linewidth=0.5)
        t = np.linspace(0, 2 * np.pi, 200)
        ax.plot(np.cos(t), np.sin(t), color=pal.hexstr("muted"), linewidth=0.8)
        for r in (0.2, 0.5, 1, 2, 5):
            c, rad = r / (1 + r), 1 / (1 + r)
            ax.plot(c + rad * np.cos(t), rad * np.sin(t), **grid)
        for x in (0.2, 0.5, 1, 2, 5):
            for s in (1, -1):
                z = 1j * s * x + np.concatenate([np.linspace(0, 1, 50), np.logspace(0, 3, 50)])
                g = (z - 1) / (z + 1)
                ax.plot(g.real, g.imag, **grid)
        ax.axhline(0, **grid)
        fr = np.linspace(0, 1, 120)
        zl = 1 + 0.6 * np.cos(6 * fr) + 1j * (1.4 * fr - 0.5 + 0.3 * np.sin(9 * fr))
        gl = (zl - 1) / (zl + 1)
        ax.plot(gl.real, gl.imag, color=pal.hexstr("accent"), linewidth=1.2)
        ax.plot(gl.real[0], gl.imag[0], "o", color=pal.hexstr("red"), ms=2.5)
        return f

    def constellation(pal, rng):
        f, ax = plt.subplots(figsize=(FIG_H, FIG_H), layout="constrained")
        lv = np.array([-3, -1, 1, 3])
        sym = (rng.choice(lv, 4000) + 1j * rng.choice(lv, 4000)) + 0.25 * (rng.normal(size=4000) + 1j * rng.normal(size=4000))
        ax.scatter(sym.real, sym.imag, s=1, alpha=0.25, linewidths=0)
        ax.scatter(np.repeat(lv, 4), np.tile(lv, 4), s=8, marker="+", color=pal.hexstr("red"), linewidths=0.8)
        ax.set_aspect("equal")
        ax.set_title("16-QAM, 4000 symbols")
        ax.grid(True)
        return f

    def eye(pal, rng):
        f, ax = fig()
        sps, n = 16, 300
        bits = rng.choice([-1.0, 1.0], n + 4)
        up = np.repeat(bits, sps)
        k = np.hanning(sps * 2)
        sig = np.convolve(up, k / k.sum() * sps / 2, mode="same") + 0.05 * rng.normal(size=up.size)
        for i in range(2, n):
            seg = sig[i * sps: i * sps + 2 * sps]
            ax.plot(np.arange(2 * sps) / sps, seg, color=pal.hexstr("teal"), alpha=0.08, linewidth=0.6)
        ax.set_title("eye diagram, 300 traces at 8% opacity")
        ax.set_xlabel("symbol periods")
        return f

    def ion_image(pal, rng):
        f, ax = fig()
        yy, xx = np.mgrid[0:96, 0:128]
        img = (np.exp(-((xx - 40) ** 2 + (yy - 50) ** 2) / 300) + 0.7 * np.exp(-((xx - 90) ** 2 + (yy - 30) ** 2) / 120)
               + 0.25 * rng.random((96, 128)))
        im = ax.imshow(img, cmap="inferno")
        ax.plot([8, 40], [88, 88], color="white", linewidth=2)      # the scale bar is part of the image: it stays
        ax.text(24, 84, "50 µm", color="white", ha="center", fontsize=5)
        ax.set_xticks([])
        ax.set_yticks([])
        f.colorbar(im, ax=ax, label="counts")
        return f

    def polar(pal, rng):
        f, ax = plt.subplots(figsize=(FIG_H, FIG_H), layout="constrained", subplot_kw=dict(projection="polar"))
        th = np.linspace(0, 2 * np.pi, 360)
        g = np.abs(np.sinc(3 * np.sin(th - np.pi / 2))) + 1e-3
        ax.plot(th, 20 * np.log10(g) + 40)
        ax.plot(th, 20 * np.log10(np.abs(np.cos(th)) ** 3 + 1e-3) + 40, linestyle="--")
        ax.set_rlim(0, 42)
        ax.set_title("antenna pattern (dB)")
        return f

    def bigline(pal, rng):
        import matplotlib as mpl
        f, ax = fig()
        with mpl.rc_context({"path.simplify": False, "agg.path.chunksize": 0}):
            x = np.linspace(0, 1, 100000)
            ax.plot(x, np.cumsum(rng.normal(size=x.size)) / 100, linewidth=0.3)
        ax.set_title("100,000 points as one vector path")
        return f

    def databehind(pal, rng):
        f, ax = fig()
        x = np.arange(0, 21)
        ax.plot(x, DATA_Y, "o-", ms=2.5)
        ax.set_xlabel("dose")
        ax.set_ylabel("response")
        ax.grid(True)
        return f

    return dict(lines=lines, scatter=scatter, errors=errors, hist=hist, heat_div=heat_div, heat_seq=heat_seq,
                gouraud=gouraud, contours=contours, surface=surface, spectrum=spectrum, rasterised=rasterised,
                spectrogram=spectrogram, smith=smith, constellation=constellation, eye=eye, ion_image=ion_image,
                polar=polar, bigline=bigline, databehind=databehind)


DATA_Y = np.round(1 / (1 + np.exp(-(np.arange(0, 21) - 10) / 2.5)) + np.sin(np.arange(21) * 1.7) * 0.02, 4)


def build_mpl(pal, cache=CACHE):
    import matplotlib
    matplotlib.use("pdf")
    import matplotlib.pyplot as plt
    os.makedirs(cache, exist_ok=True)
    paths = {}
    with matplotlib.rc_context(mpl_rc(pal)):
        for name, make in mpl_figures().items():
            rng = np.random.default_rng(sum(map(ord, name)))   # same data in both builds
            f = make(pal, rng)
            path = os.path.join(cache, "mpl-%s-%s.pdf" % (name, pal.name))
            f.savefig(path, metadata={"CreationDate": None, "Creator": "matplotlib", "Producer": None})
            plt.close(f)
            paths[name] = path
    return paths


# -- pgfplots and LaTeX -------------------------------------------------------------------------------

PGF_PREAMBLE = r"""\documentclass[border=2pt]{standalone}
\usepackage{pgfplots}
\usepgfplotslibrary{fillbetween}
\usetikzlibrary{patterns}
\pgfplotsset{compat=1.18}
%(colours)s
\pagecolor{tile}
\color{ink}
\pgfplotsset{every axis/.append style={axis line style={muted}, tick style={muted}, tick label style={ink, font=\tiny},
  label style={ink, font=\tiny}, title style={ink, font=\tiny}, legend style={fill=tile, draw=rule, text=ink, font=\tiny}},
  every colorbar/.append style={tick label style={font=\tiny}}}
\begin{document}
"""

PGF_FIGS = {
    "pgf_surface": r"""
\begin{tikzpicture}
\begin{axis}[width=5.2cm, height=4.2cm, title={surf, shader=interp}, colorbar, colormap/viridis, view={30}{40}]
\addplot3[surf, shader=interp, samples=18, domain=-2:2] {exp(-x^2-y^2)*cos(deg(2*x))};
\end{axis}
\end{tikzpicture}""",
    "pgf_errors": r"""
\begin{tikzpicture}
\begin{axis}[width=5.6cm, height=4.2cm, title={fill between, error bars, pattern}, cycle list={{accent},{red},{green}}]
\addplot[name path=a, draw=none, domain=0:6, samples=40] {sin(deg(x))+0.3};
\addplot[name path=b, draw=none, domain=0:6, samples=40] {sin(deg(x))-0.3};
\addplot[accent, fill opacity=0.35] fill between[of=a and b];
\addplot+[only marks, mark size=1.2pt, error bars/.cd, y dir=both, y explicit] coordinates
  {(0.5,0.48) +- (0,0.2) (1.5,1.0) +- (0,0.1) (2.5,0.6) +- (0,0.3) (3.5,-0.35) +- (0,0.2) (4.5,-0.98) +- (0,0.15)};
\addplot[ybar, bar width=6pt, pattern=north east lines, pattern color=orange, draw=orange] coordinates {(5.2,0.6) (5.8,0.9)};
\end{axis}
\end{tikzpicture}""",
    "equation": r"""
$\displaystyle P_r = P_t\,G_t\,G_r\left(\frac{\lambda}{4\pi d}\right)^{2}
\qquad \nabla\times\mathbf{E} = -\frac{\partial\mathbf{B}}{\partial t}$""",
}


def build_pgf(pal, cache=CACHE):
    os.makedirs(cache, exist_ok=True)
    colours = "\n".join(r"\definecolor{%s}{HTML}{%s}" % (r, pal.hexstr(r).lstrip("#"))
                        for r in ("paper", "tile", "rule", "ink", "muted", "accent", "red", "green", "orange", "blue"))
    paths = {}
    for name, body in PGF_FIGS.items():
        stem = "%s-%s" % (name, pal.name)
        tex = os.path.join(cache, stem + ".tex")
        with open(tex, "w") as f:
            f.write(PGF_PREAMBLE % {"colours": colours} + body + "\n\\end{document}\n")
        env = dict(os.environ, SOURCE_DATE_EPOCH="1790000000", FORCE_SOURCE_DATE="1")
        r = subprocess.run(["pdflatex", "-interaction=nonstopmode", "-halt-on-error", stem + ".tex"], cwd=cache,
                           capture_output=True, text=True, env=env)
        pdf = os.path.join(cache, stem + ".pdf")
        if r.returncode != 0 or not os.path.exists(pdf):
            raise RuntimeError("pdflatex failed for %s:\n%s" % (name, r.stdout[-2000:]))
        paths[name] = pdf
    return paths


# -- importing ------------------------------------------------------------------------------------------

def _fill_resources(xobj, seen):
    """PDF 2.0 requires Resources on every form XObject; matplotlib's marker XObjects have
    none, so give those an empty dictionary. Nothing else in the figures is changed."""
    if xobj.objgen in seen:
        return
    seen.add(xobj.objgen)
    if "/Resources" not in xobj:
        xobj.Resources = Dictionary()
    for _, child in xobj.Resources.get("/XObject", {}).items():
        if child.get("/Subtype") == Name.Form:
            _fill_resources(child, seen)
    for _, pat in xobj.Resources.get("/Pattern", {}).items():
        if isinstance(pat, pikepdf.Stream):
            _fill_resources(pat, seen) if pat.get("/Subtype") == Name.Form else None


def import_figure(doc, path):
    def make():
        src = pikepdf.open(path)
        form = src.pages[0].as_form_xobject()
        local = doc.pdf.copy_foreign(form)
        _fill_resources(local, set())
        bbox = [float(v) for v in local.BBox]
        return local, bbox
    return doc.once(("figure", path), make)


def place_figure(p, key, path, rect, alt):
    form, bbox = import_figure(p.doc, path)
    x, y, w, h = rect
    fw, fh = bbox[2] - bbox[0], bbox[3] - bbox[1]
    s = min(w / fw, h / fh)
    dx, dy = x + (w - fw * s) / 2 - bbox[0] * s, y + (h - fh * s) / 2 - bbox[1] * s
    nm = p.use("XObject", key, form)
    return p.figure("%s 0 0 %s %s %s cm %s Do" % (n(s), n(s), n(dx), n(dy), nm), alt)


def figures_for(doc):
    if "sci-paths" not in doc.shared:
        paths = build_mpl(doc.pal)
        paths.update(build_pgf(doc.pal))
        doc.shared["sci-paths"] = paths
    return doc.shared["sci-paths"]


# -- pages ----------------------------------------------------------------------------------------------

def page_sci_plots(doc, res):
    p = Page(doc, "Scientific figures: matplotlib",
             "Figures made by matplotlib 3.11 with its defaults, from one script run with light and dark colours. "
             "Fonts are Type 3, every figure starts with a background rectangle, markers are one XObject drawn "
             "thousands of times, and heatmaps and colour bars are Indexed images. Data colour maps that work on "
             "both papers stay; a diverging map swaps to a dark-midpoint one.")
    figs = figures_for(doc)
    t = p.grid(3, 4)
    rows = [
        ("lines", "Line plot: series, legend, grid", "T59, T110", "swaps", "Type 3 fonts, background rectangle"),
        ("scatter", "Scatter coloured by value", "T86, T93, T87", "swaps", "1,500 Do of one marker; data colours stay"),
        ("errors", "Error bars and a confidence band", "T57, T86", "swaps", "Band at 30% opacity"),
        ("hist", "Histogram with hatching", "T74, T57", "swaps", "Hatch colour lives inside the pattern"),
        ("heat_div", "Heatmap, diverging map", "T87, T61", "swaps", "RdBu in light, berlin in dark: a new image"),
        ("heat_seq", "Heatmap, viridis in both", "T87, T61", "stays", "Data colours kept; only the frame swaps"),
        ("gouraud", "Gouraud mesh (pcolormesh)", "T81", "swaps", "Type 4 shading with a diverging map"),
        ("contours", "Filled and labelled contours", "T59, T110", "swaps", "Contour fills swap with the map"),
        ("surface", "3D surface (mplot3d)", "T59", "stays", "Hundreds of polygons, each its own colour"),
        ("spectrum", "Mass spectrum: sticks, log scale", "T59, T110", "swaps", "Peak labels and 164 sticks"),
        ("rasterised", "Rasterised layer in a vector plot", "T87, T144", "swaps", "The points are baked into an image"),
        ("spectrogram", "Spectrogram with colour bar", "T87", "stays", "inferno in both builds"),
    ]
    for rect, (name, title, ref, expect, note) in zip(t, rows):
        inner = p.tile(rect, title, ref, expect, note=note)
        place_figure(p, "Fig_" + name, figs[name], inner, title + ", drawn by matplotlib.")
    return p


def page_sci_more(doc, res):
    p = Page(doc, "Scientific figures: RF, imaging, LaTeX and data",
             "RF plots, a false-colour image with a scale bar, pgfplots and LaTeX output, a chemical structure, a "
             "results table whose colours mean something, and the data behind a plot attached to the file.")
    pal = p.pal
    figs = figures_for(doc)
    t = p.grid(3, 4)
    rows = [
        ("smith", "Smith chart", "T59", "swaps", "Impedance grid and an S11 trace"),
        ("constellation", "Constellation: 16-QAM", "T57, T86", "swaps", "4,000 symbols at 25% opacity"),
        ("eye", "Eye diagram", "T57", "swaps", "Low-opacity traces build up differently on dark"),
        ("ion_image", "Ion image with a scale bar", "T87", "stays", "False colour and the bar are in the data"),
        ("polar", "Antenna pattern: polar axes", "T59", "swaps", None),
        ("pgf_surface", "pgfplots surface and colour bar", "T75, T82, T79", "stays",
         "Type 5 mesh in a pattern; viridis kept"),
        ("pgf_errors", "pgfplots: band, error bars, pattern", "T74, T57", "swaps", "Uncoloured pattern, colour at use"),
        ("equation", "Equations from LaTeX", "T109, T124", "swaps", "Type 1 Computer Modern"),
        ("bigline", "100,000 points in one path", "T58", "swaps", "Tests the cost of a theme switch"),
    ]
    for rect, (name, title, ref, expect, note) in zip(t, rows):
        inner = p.tile(rect, title, ref, expect, note=note)
        place_figure(p, "Fig_" + name, figs[name], inner, title + ".")

    # Chemical structure: element colours keep their hue in every theme.
    x, y, w, h = p.tile(t[9], "Chemical structure: element colours", "T59", "swaps",
                        note="O and N keep their hue; the dark build lightens them")
    cx, cy, r = x + w * 0.42, y + h / 2, min(w, h) * 0.24
    ring = [(cx + r * np.cos(np.radians(90 + 60 * k)), cy + r * np.sin(np.radians(90 + 60 * k))) for k in range(6)]
    bonds = [poly_path(ring, close=True)]
    inner_ring = [(cx + 0.72 * (px - cx), cy + 0.72 * (py - cy)) for px, py in ring]
    for k in (0, 2, 4):
        a, b = inner_ring[k], inner_ring[(k + 1) % 6]
        bonds.append("%s %s m %s %s l" % (n(a[0]), n(a[1]), n(b[0]), n(b[1])))
    top, bottom = ring[0], ring[3]
    o_pos = (top[0], top[1] + r * 0.75)
    n_pos = (bottom[0], bottom[1] - r * 0.75)
    bonds.append("%s %s m %s %s l %s %s m %s %s l" % (n(top[0]), n(top[1]), n(o_pos[0]), n(o_pos[1] - 4),
                                                       n(bottom[0]), n(bottom[1]), n(n_pos[0]), n(n_pos[1] + 4)))
    p.figure("%s 1 w 1 J %s S" % (pal.RG("ink"), " ".join(bonds)), "Para-aminophenol: a benzene ring with OH and NH2.")
    bold = p.font("SansBold")
    p.tagged("Span", p.text_op(o_pos[0] - 5, o_pos[1] - 2, "OH", 8, bold, "red"), actual="OH")
    p.tagged("Span", p.text_op(n_pos[0] - 7, n_pos[1] - 5, "NH2", 8, bold, "blue"), actual="NH2")

    # Results table: green and red cells mean pass and fail.
    x, y, w, h = p.tile(t[10], "Results table: colours that mean something", "T371, T378, T384", "swaps",
                        note="Green passes, red fails, in every theme")
    sans = p.font("Sans")
    data = [("Sample", "Mean", "p"), ("A", "4.21", "0.003"), ("B", "3.87", "0.041"), ("C", "4.02", "0.270"),
            ("D", "3.55", "0.610")]
    cw, rh = (w - 8) / 3, min(15, (h - 4) / len(data))
    p.begin("Table")
    for i, row in enumerate(data):
        p.begin("TR")
        for j, val in enumerate(row):
            cx_, cy_ = x + 4 + j * cw, y + h - 4 - (i + 1) * rh
            if i == 0:
                fill = "accent"
            elif j == 2:
                fill = "green" if float(val) < 0.05 else "red"
            else:
                fill = "tile"
            text_role = "paper" if fill in ("accent", "green", "red") else "ink"
            p.artifact("%s %s f %s 0.4 w %s S" % (pal.rg(fill), rect_path(cx_, cy_, cw, rh), pal.RG("rule"),
                                                  rect_path(cx_, cy_, cw, rh)))
            attrs = Dictionary(O=Name.Layout, BackgroundColor=doc.rgb(fill), Color=doc.rgb(text_role))
            p.tagged("TH" if i == 0 else "TD", p.text_op(cx_ + 4, cy_ + rh / 2 - 2.5, val, 7, bold if i == 0 else sans,
                                                         text_role), attrs=attrs)
        p.end()
    p.end()

    # The data behind a plot, attached to the figure.
    x, y, w, h = p.tile(t[11], "The data behind a plot: AF, Data", "T43, T45, T373", "stays",
                        note="The CSV hangs off the Figure element")
    csv = ("dose,response\n" + "\n".join("%d,%s" % (i, v) for i, v in enumerate(DATA_Y))).encode()
    fs = doc.embed_file("dose-response.csv", csv, "text/csv", "The data plotted in this figure", rel="Data")
    el = place_figure(p, "Fig_databehind", figs["databehind"], (x, y, w, h), "Dose against response, 21 points.")
    el.af = fs
    return p
