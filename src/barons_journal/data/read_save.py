"""Read a Barony .baronsave file into typed models.

All raw-dict handling and save-format quirks live here:

- Names end in ``\\r``; they are stripped.
- ``4294967295`` (uint32 -1) means "empty"; it becomes ``None``.
- The player object has a duplicate ``"race"`` key; ``json`` keeps the last one.
"""

import json
from pathlib import Path
from typing import Any

from .models import Player, SaveFile, Stats

MAGIC_COOKIE = "BARONYJSONSAVE"
SUPPORTED_VERSIONS = frozenset({502})
UINT32_EMPTY = 4294967295


class InvalidSaveError(ValueError):
    """The file isn't a usable Barony save."""


class UnsupportedVersionError(InvalidSaveError):
    """The save comes from a Barony version this app doesn't know how to read."""


def load_save(path: str | Path) -> SaveFile:
    """Read and parse the save at ``path``. Raises ``FileNotFoundError`` if missing."""
    text = Path(path).read_text(encoding="utf-8")
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as e:
        raise InvalidSaveError(f"Save file is not valid JSON: {e}") from e
    return parse_save(raw)


def parse_save(raw: Any) -> SaveFile:
    """Validate a decoded save dict and convert it to a ``SaveFile``."""
    if not isinstance(raw, dict):
        raise InvalidSaveError("Save file top level is not a JSON object")

    if raw.get("magic_cookie") != MAGIC_COOKIE:
        raise InvalidSaveError(
            f"Bad magic cookie: expected {MAGIC_COOKIE!r}, got {raw.get('magic_cookie')!r}"
        )

    version = _require(raw, "game_version")
    if version not in SUPPORTED_VERSIONS:
        raise UnsupportedVersionError(
            f"Unsupported game_version {version}; supported: {sorted(SUPPORTED_VERSIONS)}"
        )

    players = _require(raw, "players")
    player_num = _require(raw, "player_num")
    if not (isinstance(player_num, int) and 0 <= player_num < len(players)):
        raise InvalidSaveError(
            f"player_num {player_num!r} out of range for {len(players)} players"
        )

    return SaveFile(
        game_version=version,
        game_name=_clean_name(_require(raw, "game_name")),
        gamekey=_require(raw, "gamekey"),
        dungeon_lvl=_require(raw, "dungeon_lvl"),
        timestamp=_require(raw, "timestamp"),
        player=_parse_player(players[player_num]),
    )


def _parse_player(raw: dict) -> Player:
    stats = _require(raw, "stats")
    return Player(
        name=_clean_name(_require(stats, "name")),
        char_class=_require(raw, "char_class"),
        race=_require(raw, "race"),
        stats=_parse_stats(stats),
        kills=tuple(_require(raw, "kills")),
        hotbar=tuple(_none_if_empty(slot) for slot in _require(raw, "hotbar")),
    )


def _parse_stats(raw: dict) -> Stats:
    return Stats(
        hp=_require(raw, "HP"),
        max_hp=_require(raw, "maxHP"),
        mp=_require(raw, "MP"),
        max_mp=_require(raw, "maxMP"),
        strength=_require(raw, "STR"),
        dexterity=_require(raw, "DEX"),
        constitution=_require(raw, "CON"),
        intelligence=_require(raw, "INT"),
        perception=_require(raw, "PER"),
        charisma=_require(raw, "CHR"),
        exp=_require(raw, "EXP"),
        level=_require(raw, "LVL"),
        gold=_require(raw, "GOLD"),
        hunger=_require(raw, "HUNGER"),
        proficiencies=tuple(_require(raw, "PROFICIENCIES")),
    )


def _require(raw: dict, key: str) -> Any:
    try:
        return raw[key]
    except KeyError:
        raise InvalidSaveError(f"Save is missing required field {key!r}") from None


def _clean_name(name: str) -> str:
    return name.rstrip("\r")


def _none_if_empty(value: int) -> int | None:
    return None if value == UINT32_EMPTY else value
