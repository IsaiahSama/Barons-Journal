"""What the main window is showing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ..data import SaveFile
from ..journal import Run
from .location import Location

Mode = Literal["empty", "live", "past"]
BannerKind = Literal["error", "new_run", "ended", "past"]


@dataclass(frozen=True, slots=True)
class ViewState:
    mode: Mode
    run: Run | None = None
    """Journal row of the run on screen."""
    save: SaveFile | None = None
    """Live mode only."""
    location: Location | None = None
    editable: bool = False
    """True in live mode (also when ended), False in past and empty."""
    ended: bool = False
    """The live save disappeared for good."""


@dataclass(frozen=True, slots=True)
class Banner:
    kind: BannerKind
    text: str
