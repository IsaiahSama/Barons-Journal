"""Where in the dungeon a save or run is, and how to word it."""

from __future__ import annotations

from dataclasses import dataclass

from ..data import SaveFile
from ..journal import Run
from ..reference import floor_at, secret_level_at


@dataclass(frozen=True, slots=True, order=True)
class Location:
    dungeon_lvl: int
    secret: bool = False

    @classmethod
    def of_save(cls, save: SaveFile) -> Location:
        return cls(save.dungeon_lvl, save.in_secret_level)

    @classmethod
    def of_run(cls, run: Run) -> Location:
        return cls(run.last_floor, run.last_floor_secret)


def location_label(loc: Location) -> str:
    """Wording for headers and prompts."""
    if loc.secret:
        secret = secret_level_at(loc.dungeon_lvl)
        if secret is None:
            return f"Secret level · depth {loc.dungeon_lvl}"
        return f"{secret.name} · depth {loc.dungeon_lvl}"
    try:
        return f"Floor {loc.dungeon_lvl} ({floor_at(loc.dungeon_lvl).area})"
    except KeyError:
        return f"Floor {loc.dungeon_lvl}"


def snapshot_caption(save: SaveFile) -> str:
    """The caption every stats view carries."""
    time = save.timestamp.strftime("%H:%M")
    if save.in_secret_level:
        secret = secret_level_at(save.dungeon_lvl)
        where = secret.name if secret else "a secret level"
    else:
        where = f"floor {save.dungeon_lvl}"
    return f"As of {where}, saved {time}"
