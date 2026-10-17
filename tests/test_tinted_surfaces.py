"""Pale tinted boxes keep their colours, darkened, in a worked-out dark theme.

A dark theme turns light surfaces dark by turning their lightness round. Pale boxes have
little chroma, so they all came out within a step of the black paper and of one another:
the colour coding of a network diagram (VGG-19 in the ResNet paper: blue, peach, lavender
and green layers) was lost. A tinted surface now goes to a dark tint that stays apart from
the paper and from the other tints, with room for light text on it.
"""

import math

from pdfthemes import colour as C
from pdfthemes.derive import Spec

PALE = {"pink": (242, 220, 218), "green": (235, 241, 223), "lavender": (238, 234, 242), "blue": (219, 238, 243)}
DARK = Spec("Dark", "Dark", source="derive")


def oklab(rgb):
    return C.srgb_to_oklab(rgb)


def test_pale_tints_stay_apart_from_the_paper_and_from_each_other():
    paper = DARK.paper((1.0, 1.0, 1.0), (0.0, 0.0, 0.0))
    dark = {k: DARK.background(tuple(v / 255 for v in rgb)) for k, rgb in PALE.items()}
    for name, rgb in dark.items():
        assert math.dist(oklab(rgb), oklab(paper)) > 0.08, name
        assert C.contrast((0.96, 0.96, 0.96), rgb) >= 7, name
    names = list(dark)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            assert math.dist(oklab(dark[a]), oklab(dark[b])) > 0.03, (a, b)


def test_white_still_becomes_the_paper():
    assert DARK.background((1.0, 1.0, 1.0)) == DARK.paper((1.0, 1.0, 1.0), (0.0, 0.0, 0.0))
