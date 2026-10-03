"""Images for the theme test page.

chart-light.png and chart-dark.png: the same bar chart drawn twice with
different colours. The shapes match pixel for pixel, as they would when a
chart library draws one chart in two styles, so the themed PDF can keep one
plane of pixels and swap only the palette.

photo.png: a full-colour image that is the same in both themes.
"""

import pathlib

import numpy as np
from PIL import Image, ImageDraw

HERE = pathlib.Path(__file__).resolve().parent
W, H, SS = 640, 260, 4  # drawn 4 times larger, then averaged down for smooth edges

THEMES = {
    "light": dict(bg="#FFFFFF", grid="#E3E1E8", axis="#3A3A40", a="#9A20B6", b="#8E8E93"),
    "dark": dict(bg="#1C1C1E", grid="#38383C", axis="#C7C7CC", a="#C47BFF", b="#8E8E93"),
}
VALUES = [(62, 48), (75, 52), (58, 60), (88, 64), (70, 71), (94, 69)]


def chart(t):
    img = Image.new("RGB", (W * SS, H * SS), t["bg"])
    d = ImageDraw.Draw(img)
    top, base, left, right = 16, 236, 24, 616
    for k in range(5):
        y = base - k * (base - top) // 4
        d.rectangle([left * SS, y * SS, right * SS, y * SS + SS - 1], fill=t["grid"])
    group = (right - left) // len(VALUES)
    bar = 28
    for i, (va, vb) in enumerate(VALUES):
        x = left + i * group + (group - 2 * bar - 8) // 2
        for j, (v, colour) in enumerate(((va, t["a"]), (vb, t["b"]))):
            x0 = x + j * (bar + 8)
            y0 = base - v * (base - top) // 100
            d.rounded_rectangle([x0 * SS, y0 * SS, (x0 + bar) * SS - 1, base * SS + 6 * SS], radius=6 * SS, fill=colour)
    d.rectangle([left * SS, base * SS, right * SS, (base + 2) * SS - 1], fill=t["axis"])
    d.rectangle([0, (base + 2) * SS, W * SS, H * SS], fill=t["bg"])  # square off the bar feet
    return img.resize((W, H), Image.BOX)


def photo():
    y, x = np.mgrid[0:200, 0:320] / 200.0
    rng = np.random.default_rng(7)
    r = 0.55 + 0.35 * np.sin(3.1 * x + 1.3) * np.cos(2.2 * y)
    g = 0.45 + 0.30 * np.sin(2.0 * y + 0.4 + x)
    b = 0.65 + 0.25 * np.cos(4.0 * x * y)
    rgb = np.stack([r, g, b], axis=2) + rng.normal(0, 0.03, (200, 320, 3))
    return Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8))


if __name__ == "__main__":
    for name, t in THEMES.items():
        chart(t).save(HERE / f"chart-{name}.png")
    photo().save(HERE / "photo.png")
    a = np.asarray(Image.open(HERE / "chart-light.png"))
    b = np.asarray(Image.open(HERE / "chart-dark.png"))
    pairs = np.unique(np.concatenate([a.reshape(-1, 3), b.reshape(-1, 3)], axis=1), axis=0)
    print("distinct colour pairs in the chart:", len(pairs))
