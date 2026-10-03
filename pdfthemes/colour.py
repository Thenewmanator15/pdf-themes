"""Colour spaces as PDF defines them, and the colour maths themes need.

Conversions to sRGB here are for working out themes and checking contrast,
not for colour management: ICC profiles are read by their component count,
CMYK is converted with the simple formula, and Lab goes through CIE XYZ.
"""

from __future__ import annotations

import math

import numpy as np
import pikepdf
from pikepdf import Name

DEVICE = {"/DeviceGray": 1, "/DeviceRGB": 3, "/DeviceCMYK": 4}


# ── Colour spaces ────────────────────────────────────────────────────────────

def family(space) -> str:
    if isinstance(space, pikepdf.Name):
        return str(space)
    if isinstance(space, pikepdf.Array) and len(space):
        return str(space[0])
    raise ValueError(f"not a colour space: {space!r}")


def resolve(resources, name: str):
    """The colour space a content stream means by `name`."""
    if name in DEVICE or name == "/Pattern":
        return Name(name)
    spaces = resources.get("/ColorSpace") if resources is not None else None
    if spaces is None or name not in spaces:
        raise KeyError(f"colour space {name} is not in the resources")
    return spaces[name]


def components(space) -> int:
    f = family(space)
    if f in DEVICE:
        return DEVICE[f]
    if f == "/ICCBased":
        return int(space[1].N)
    if f == "/CalGray":
        return 1
    if f in ("/CalRGB", "/Lab"):
        return 3
    if f in ("/Indexed", "/Separation"):
        return 1
    if f == "/DeviceN":
        return len(space[1])
    if f == "/Pattern":
        return 0
    raise ValueError(f"unknown colour space family {f}")


def ranges(space) -> list[tuple[float, float]]:
    f = family(space)
    if f == "/Lab":
        r = [float(v) for v in space[1].get("/Range", [-100, 100, -100, 100])]
        return [(0.0, 100.0), (r[0], r[1]), (r[2], r[3])]
    if f == "/ICCBased":
        n = int(space[1].N)
        r = space[1].get("/Range")
        if r is not None:
            r = [float(v) for v in r]
            return [(r[2 * i], r[2 * i + 1]) for i in range(n)]
        return [(0.0, 1.0)] * n
    if f == "/Indexed":
        return [(0.0, float(int(space[2])))]
    return [(0.0, 1.0)] * components(space)


def indexed_lookup(space) -> bytes:
    lut = space[3]
    return lut.read_bytes() if isinstance(lut, pikepdf.Stream) else bytes(lut)


def indexed_resolve(space, index):
    """An Indexed colour as (base space, component values)."""
    base = space[1]
    n = components(base)
    i = min(max(int(round(float(index))), 0), int(space[2]))
    data = indexed_lookup(space)[i * n:(i + 1) * n]
    return base, tuple(lo + b / 255 * (hi - lo) for b, (lo, hi) in zip(data, ranges(base)))


def quantise(values, rng) -> tuple[int, ...]:
    """Component values as the bytes of an Indexed lookup table."""
    out = []
    for v, (lo, hi) in zip(values, rng):
        out.append(0 if hi <= lo else min(255, max(0, round((float(v) - lo) / (hi - lo) * 255))))
    return tuple(out)


def dequantise(byte_values, rng) -> tuple[float, ...]:
    return tuple(lo + b / 255 * (hi - lo) for b, (lo, hi) in zip(byte_values, rng))


# ── PDF functions ────────────────────────────────────────────────────────────

def _clip(x, lo, hi):
    return lo if x < lo else hi if x > hi else x


def _pairs(arr):
    v = [float(x) for x in arr]
    return [(v[i], v[i + 1]) for i in range(0, len(v), 2)]


def eval_function(fn, inputs) -> list[float]:
    """Evaluate a PDF function (types 0, 2, 3 and 4)."""
    if isinstance(fn, pikepdf.Array):  # an array of one-output functions
        return [eval_function(f, inputs)[0] for f in fn]
    t = int(fn.FunctionType)
    domain = _pairs(fn.Domain)
    x = [_clip(float(v), lo, hi) for v, (lo, hi) in zip(inputs, domain)]
    if t == 2:
        c0 = [float(v) for v in fn.get("/C0", [0.0])]
        c1 = [float(v) for v in fn.get("/C1", [1.0])]
        n = float(fn.N)
        out = [a + (x[0] ** n) * (b - a) for a, b in zip(c0, c1)]
    elif t == 3:
        bounds = [float(v) for v in fn.get("/Bounds", [])]
        encode = _pairs(fn.Encode)
        k = sum(1 for b in bounds if x[0] >= b)
        lo = domain[0][0] if k == 0 else bounds[k - 1]
        hi = domain[0][1] if k == len(bounds) else bounds[k]
        e0, e1 = encode[k]
        t_ = e0 if hi == lo else e0 + (x[0] - lo) * (e1 - e0) / (hi - lo)
        out = eval_function(fn.Functions[k], [t_])
    elif t == 0:
        out = _sampled(fn, x, domain)
    elif t == 4:
        out = _postscript(fn.read_bytes().decode("latin-1"), x)
    else:
        raise ValueError(f"function type {t}")
    if "/Range" in fn:
        out = [_clip(v, lo, hi) for v, (lo, hi) in zip(out, _pairs(fn.Range))]
    return out


def _sampled(fn, x, domain):
    size = [int(s) for s in fn.Size]
    bps = int(fn.BitsPerSample)
    rng = _pairs(fn.Range)
    n_out = len(rng)
    encode = _pairs(fn.get("/Encode", [v for s in size for v in (0, s - 1)]))
    decode = _pairs(fn.get("/Decode", fn.Range))
    data = fn.read_bytes()
    bits = np.unpackbits(np.frombuffer(data, dtype=np.uint8))
    maxv = (1 << bps) - 1

    def sample(idx):
        flat = 0
        mult = 1
        for i, s in zip(idx, size):
            flat += i * mult
            mult *= s
        out = []
        for j in range(n_out):
            pos = (flat * n_out + j) * bps
            chunk = bits[pos:pos + bps]
            v = 0
            for b in chunk:
                v = (v << 1) | int(b)
            lo, hi = decode[j]
            out.append(lo + v * (hi - lo) / maxv)
        return out

    # Position in sample space; linear between neighbours on the first input,
    # nearest sample on any others.
    pos = []
    for xi, (d0, d1), (e0, e1), s in zip(x, domain, encode, size):
        e = e0 if d1 == d0 else e0 + (xi - d0) * (e1 - e0) / (d1 - d0)
        pos.append(_clip(e, 0, s - 1))
    i0 = [int(math.floor(p)) for p in pos]
    if len(pos) == 1 and i0[0] < size[0] - 1:
        f = pos[0] - i0[0]
        a, b = sample([i0[0]]), sample([i0[0] + 1])
        return [p + f * (q - p) for p, q in zip(a, b)]
    return sample([int(round(p)) for p in pos])


def _postscript(code: str, inputs) -> list[float]:
    """A small interpreter for PDF type 4 (PostScript calculator) functions."""
    tokens = code.replace("{", " { ").replace("}", " } ").split()

    def parse(i):
        block = []
        while i < len(tokens):
            t = tokens[i]
            if t == "{":
                sub, i = parse(i + 1)
                block.append(sub)
            elif t == "}":
                return block, i + 1
            else:
                block.append(t)
                i += 1
        return block, i

    program, _ = parse(0)
    if len(program) == 1 and isinstance(program[0], list):
        program = program[0]
    stack = [float(v) for v in inputs]

    def run(block):
        for t in block:
            if isinstance(t, list):
                stack.append(t)
                continue
            if t in ("true", "false"):
                stack.append(t == "true")
                continue
            try:
                stack.append(float(t))
                continue
            except ValueError:
                pass
            if t in ("add", "sub", "mul", "div", "idiv", "mod", "exp", "atan", "eq", "ne", "gt", "ge", "lt", "le",
                     "and", "or", "xor", "bitshift"):
                b, a = stack.pop(), stack.pop()
                stack.append({
                    "add": lambda: a + b, "sub": lambda: a - b, "mul": lambda: a * b,
                    "div": lambda: a / b if b else 0.0, "idiv": lambda: float(int(a) // int(b)) if b else 0.0,
                    "mod": lambda: float(int(a) % int(b)) if b else 0.0, "exp": lambda: a ** b,
                    "atan": lambda: math.degrees(math.atan2(a, b)) % 360, "eq": lambda: a == b,
                    "ne": lambda: a != b, "gt": lambda: a > b, "ge": lambda: a >= b, "lt": lambda: a < b,
                    "le": lambda: a <= b, "and": lambda: (a and b) if isinstance(a, bool) else float(int(a) & int(b)),
                    "or": lambda: (a or b) if isinstance(a, bool) else float(int(a) | int(b)),
                    "xor": lambda: (a != b) if isinstance(a, bool) else float(int(a) ^ int(b)),
                    "bitshift": lambda: float(int(a) << int(b) if b >= 0 else int(a) >> -int(b)),
                }[t]())
            elif t in ("abs", "neg", "ceiling", "floor", "round", "truncate", "sqrt", "sin", "cos", "ln", "log",
                       "cvi", "cvr", "not"):
                a = stack.pop()
                stack.append({
                    "abs": lambda: abs(a), "neg": lambda: -a, "ceiling": lambda: float(math.ceil(a)),
                    "floor": lambda: float(math.floor(a)), "round": lambda: float(math.floor(a + 0.5)),
                    "truncate": lambda: float(int(a)), "sqrt": lambda: math.sqrt(max(a, 0.0)),
                    "sin": lambda: math.sin(math.radians(a)), "cos": lambda: math.cos(math.radians(a)),
                    "ln": lambda: math.log(a) if a > 0 else 0.0, "log": lambda: math.log10(a) if a > 0 else 0.0,
                    "cvi": lambda: float(int(a)), "cvr": lambda: float(a),
                    "not": lambda: (not a) if isinstance(a, bool) else float(~int(a)),
                }[t]())
            elif t == "dup":
                stack.append(stack[-1])
            elif t == "pop":
                stack.pop()
            elif t == "exch":
                stack[-1], stack[-2] = stack[-2], stack[-1]
            elif t == "copy":
                n = int(stack.pop())
                stack.extend(stack[-n:] if n else [])
            elif t == "index":
                n = int(stack.pop())
                stack.append(stack[-1 - n])
            elif t == "roll":
                j, n = int(stack.pop()), int(stack.pop())
                if n:
                    part = stack[-n:]
                    j %= n
                    stack[-n:] = part[-j:] + part[:-j] if j else part
            elif t == "if":
                block, cond = stack.pop(), stack.pop()
                if cond:
                    run(block)
            elif t == "ifelse":
                b2, b1, cond = stack.pop(), stack.pop(), stack.pop()
                run(b1 if cond else b2)
            else:
                raise ValueError(f"PostScript operator {t}")

    run(program)
    return [float(v) for v in stack]


# ── Conversion to sRGB ───────────────────────────────────────────────────────

def to_srgb(space, values) -> tuple[float, float, float]:
    """A colour in any PDF colour space, as sRGB components from 0 to 1."""
    f = family(space)
    v = [float(x) for x in values]
    if f == "/ICCBased":
        n = int(space[1].N)
        f = {1: "/DeviceGray", 3: "/DeviceRGB", 4: "/DeviceCMYK"}[n]
    if f in ("/DeviceGray", "/CalGray"):
        return (v[0], v[0], v[0])
    if f in ("/DeviceRGB", "/CalRGB"):
        return tuple(_clip(c, 0.0, 1.0) for c in v[:3])
    if f == "/DeviceCMYK":
        c, m, y, k = (_clip(x, 0.0, 1.0) for x in v[:4])
        return ((1 - c) * (1 - k), (1 - m) * (1 - k), (1 - y) * (1 - k))
    if f == "/Lab":
        return _lab_to_srgb(space, v)
    if f == "/Indexed":
        base, vals = indexed_resolve(space, v[0])
        return to_srgb(base, vals)
    if f in ("/Separation", "/DeviceN"):
        alt = space[2]
        return to_srgb(alt, eval_function(space[3], v))
    raise ValueError(f"can't convert {f} to sRGB")


def _lab_to_srgb(space, v):
    wp = [float(x) for x in space[1].WhitePoint]
    L, a, b = v
    fy = (L + 16) / 116
    fx = fy + a / 500
    fz = fy - b / 200

    def finv(t):
        return t ** 3 if t > 6 / 29 else 3 * (6 / 29) ** 2 * (t - 4 / 29)

    X, Y, Z = wp[0] * finv(fx), wp[1] * finv(fy), wp[2] * finv(fz)
    # Bradford adaptation from the space's white point to D65, then to linear sRGB.
    M = np.array([[0.8951, 0.2664, -0.1614], [-0.7502, 1.7135, 0.0367], [0.0389, -0.0685, 1.0296]])
    src = M @ np.array(wp)
    dst = M @ np.array([0.95047, 1.0, 1.08883])
    adapt = np.linalg.inv(M) @ np.diag(dst / src) @ M
    xyz = adapt @ np.array([X, Y, Z])
    to_rgb = np.array([[3.2404542, -1.5371385, -0.4985314], [-0.9692660, 1.8760108, 0.0415560],
                       [0.0556434, -0.2040259, 1.0572252]])
    lin = to_rgb @ xyz
    return tuple(linear_to_srgb(_clip(c, 0.0, 1.0)) for c in lin)


# ── Perceptual colour (OKLab) and contrast ───────────────────────────────────

def srgb_to_linear(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def linear_to_srgb(c: float) -> float:
    return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def srgb_to_oklab(rgb):
    r, g, b = (srgb_to_linear(c) for c in rgb)
    l_ = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3)
    m_ = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
    s_ = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
    return (0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
            1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
            0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_)


def oklab_to_linear(lab):
    L, a, b = lab
    l_ = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m_ = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s_ = (L - 0.0894841775 * a - 1.2914855480 * b) ** 3
    return (4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_,
            -1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_,
            -0.0041960863 * l_ - 0.7034186147 * m_ + 1.7076147010 * s_)


def oklch_to_srgb(L, C, h):
    """OKLCH to sRGB, reducing chroma until the colour fits in sRGB."""
    L = _clip(L, 0.0, 1.0)
    for _ in range(40):
        a, b = C * math.cos(math.radians(h)), C * math.sin(math.radians(h))
        lin = oklab_to_linear((L, a, b))
        if all(-1e-6 <= c <= 1 + 1e-6 for c in lin):
            return tuple(linear_to_srgb(_clip(c, 0.0, 1.0)) for c in lin)
        C *= 0.9
    lin = oklab_to_linear((L, 0.0, 0.0))
    return tuple(linear_to_srgb(_clip(c, 0.0, 1.0)) for c in lin)


def srgb_to_oklch(rgb):
    L, a, b = srgb_to_oklab(rgb)
    return L, math.hypot(a, b), math.degrees(math.atan2(b, a)) % 360


def luminance(rgb) -> float:
    r, g, b = (srgb_to_linear(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(fg, bg) -> float:
    a, b = luminance(fg), luminance(bg)
    return (max(a, b) + 0.05) / (min(a, b) + 0.05)


def hex_rgb(text: str) -> tuple[float, float, float]:
    text = text.lstrip("#")
    return tuple(int(text[i:i + 2], 16) / 255 for i in (0, 2, 4))


def rgb_hex(rgb) -> str:
    return "#" + "".join(f"{round(_clip(c, 0, 1) * 255):02X}" for c in rgb)
