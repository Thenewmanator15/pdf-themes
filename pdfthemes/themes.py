"""The themes a file carries, as its author describes them: a name a reader
shows, the labels a reader matches to the person's settings, and the paper
colour. STANDARD is the set an author is asked to supply."""

from __future__ import annotations

from dataclasses import dataclass, replace

from pikepdf import Array, Name, String

from . import colour as C
from .derive import TINTS


@dataclass(frozen=True)
class Theme:
    name: str
    scheme: str                      # "Light" or "Dark"
    contrast: str | None = None      # "More" for an enhanced contrast theme
    tint: str | None = None          # the tint's name, for a tinted theme
    paper: tuple[float, float, float] = (1.0, 1.0, 1.0)

    @property
    def enhanced(self) -> bool:
        return self.contrast == "More"

    def info(self) -> dict:
        """The theme's entries in the themes dictionary, without Replace or Checked."""
        d = {"/Name": String(self.name), "/ColorScheme": Name("/" + self.scheme)}
        if self.contrast:
            d["/Contrast"] = Name("/" + self.contrast)
        if self.tint:
            d["/Tint"] = Name("/" + self.tint)
        d["/Paper"] = Array([round(v, 4) for v in self.paper])
        return d


STANDARD = {t.name: t for t in (
    Theme("Light", "Light"),
    Theme("Dark", "Dark", paper=(0.0, 0.0, 0.0)),
    Theme("Light, more contrast", "Light", contrast="More"),
    Theme("Dark, more contrast", "Dark", contrast="More", paper=(0.0, 0.0, 0.0)),
    *(Theme(name, "Light", tint=name, paper=tuple(C.oklch_to_srgb(*TINTS[name]))) for name in TINTS),
)}


def standard(name: str, paper=None) -> Theme:
    """A standard theme by name, on its usual paper or the one given."""
    theme = STANDARD[name]
    return replace(theme, paper=tuple(paper)) if paper is not None else theme
