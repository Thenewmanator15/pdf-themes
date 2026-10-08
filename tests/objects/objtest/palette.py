"""Light and dark palettes, by role, with each colour worked out in every space the test uses.

The two builds use the same roles in the same places, so they draw the same
objects and differ only in paint. A role's value in a space other than sRGB is
derived from its sRGB value, so the colour looks the same whichever space a
tile uses.
"""

LIGHT = {
    "paper": "#FFFFFF",
    "tile": "#F3F4F6",
    "rule": "#C9CDD3",
    "ink": "#1B1D21",
    "muted": "#5D636B",
    "accent": "#1F5FD1",
    "red": "#C62828",
    "orange": "#D7600A",
    "yellow": "#B58A00",
    "green": "#2E7D32",
    "teal": "#00796B",
    "blue": "#1565C0",
    "purple": "#6A1B9A",
    "pink": "#AD1457",
    "hl": "#FFE066",
    "swaps": "#1F5FD1",
    "stays": "#5D636B",
    "viewer": "#B4530E",
}

DARK = {
    "paper": "#18191C",
    "tile": "#222429",
    "rule": "#454952",
    "ink": "#E8EAED",
    "muted": "#A3A9B1",
    "accent": "#8AB4FF",
    "red": "#FF8A80",
    "orange": "#FFAB70",
    "yellow": "#F2C94C",
    "green": "#81C995",
    "teal": "#5ED3C2",
    "blue": "#7CB7FF",
    "purple": "#D7A6FF",
    "pink": "#FF8DC0",
    "hl": "#7A6200",
    "swaps": "#8AB4FF",
    "stays": "#A3A9B1",
    "viewer": "#FFAB70",
}

HUES = ["red", "orange", "yellow", "green", "teal", "blue", "purple", "pink"]


def _hex(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def _lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _enc(c):
    c = max(0.0, min(1.0, c))
    return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


# sRGB (D65) to XYZ, then Bradford to D50, which is what PDF Lab and ICC use.
_M_SRGB = ((0.4124564, 0.3575761, 0.1804375),
           (0.2126729, 0.7151522, 0.0721750),
           (0.0193339, 0.1191920, 0.9503041))
_BRADFORD_D65_D50 = ((1.0478112, 0.0228866, -0.0501270),
                     (0.0295424, 0.9904844, -0.0170491),
                     (-0.0092345, 0.0150436, 0.7521316))
# Display P3 (D65) from XYZ
_M_XYZ_P3 = ((2.4934969, -0.9313836, -0.4027108),
             (-0.8294890, 1.7626641, 0.0236247),
             (0.0358458, -0.0761724, 0.9568845))
D50 = (0.9642, 1.0, 0.8249)


def _mul(m, v):
    return tuple(sum(m[i][j] * v[j] for j in range(3)) for i in range(3))


class Palette:
    """Colours for one build. `name` is 'light' or 'dark' and is never drawn,
    so both builds carry the same text."""

    def __init__(self, name, table):
        self.name = name
        self.table = dict(table)
        self.dark = name == "dark"

    def rgb(self, role):
        return _hex(self.table[role])

    def hexstr(self, role):
        return self.table[role]

    def gray(self, role):
        r, g, b = (_lin(c) for c in self.rgb(role))
        return _enc(0.2126 * r + 0.7152 * g + 0.0722 * b)

    def cmyk(self, role):
        r, g, b = self.rgb(role)
        k = 1 - max(r, g, b)
        if k >= 0.9999:
            return (0.0, 0.0, 0.0, 1.0)
        return ((1 - r - k) / (1 - k), (1 - g - k) / (1 - k), (1 - b - k) / (1 - k), k)

    def xyz_d50(self, role):
        lin = tuple(_lin(c) for c in self.rgb(role))
        return _mul(_BRADFORD_D65_D50, _mul(_M_SRGB, lin))

    def lab(self, role):
        x, y, z = self.xyz_d50(role)

        def f(t):
            return t ** (1 / 3) if t > 216 / 24389 else (24389 / 27 * t + 16) / 116

        fx, fy, fz = f(x / D50[0]), f(y / D50[1]), f(z / D50[2])
        return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))

    def p3(self, role):
        lin = tuple(_lin(c) for c in self.rgb(role))
        xyz = _mul(_M_SRGB, lin)
        return tuple(_enc(c) for c in _mul(_M_XYZ_P3, xyz))

    # Content stream operators -------------------------------------------------
    def rg(self, role):
        return "%s rg" % fmt(self.rgb(role))

    def RG(self, role):
        return "%s RG" % fmt(self.rgb(role))


def fmt(values):
    out = []
    for v in values:
        s = ("%.4f" % v).rstrip("0").rstrip(".")
        out.append("0" if s in ("-0", "") else s)
    return " ".join(out)


def build_palettes():
    return Palette("light", LIGHT), Palette("dark", DARK)
