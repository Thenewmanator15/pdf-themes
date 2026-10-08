"""Colour themes in PDF: proof of concept.

One PDF carries its default colours and further themes (dark, more contrast,
a range of tints), each checked for text contrast. The page content is stored
once; a theme swaps a few objects, mostly palettes.
See README.md and SPEC.md.
"""

from .core import THEMES_KEY, MergeError, apply, describe, paint_paper, themes
from .merge import Merger, merge, merge_builds

__all__ = ["THEMES_KEY", "MergeError", "Merger", "apply", "describe", "merge", "merge_builds", "paint_paper", "themes"]
__version__ = "0.3.0"
