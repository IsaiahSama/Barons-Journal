"""Read a Barony .baronsave file into typed models.

All raw-dict handling and save-format quirks live here:

- Names end in ``\\r``; they are stripped.
- ``4294967295`` (uint32 -1) means "empty"; it becomes ``None``.
- The player object has a duplicate ``"race"`` key; ``json`` keeps the last one.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import Effect, Equipment, Item, Player, SaveFile, Stats

MAGIC_COOKIE = "BARONYJSONSAVE"
SUPPORTED_VERSIONS = frozenset({502})
UINT32_EMPTY = 4294967295
TIMESTAMP_FORMAT = "%Y-%m-%d %H-%M-%S"  # e.g. "2026-10-12 13-08-18", local time


class InvalidSaveError(ValueError):
    """The file isn't a usable Barony save."""


class UnsupportedVersionError(InvalidSaveError):
    """The save comes from a Barony version this app doesn't know how to read."""


def load_save(path: str | Path) -> SaveFile:
    """Read and parse the save at ``path``. Raises ``FileNotFoundError`` if missing."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except UnicodeDecodeError as e:
        raise InvalidSaveError(f"Save file is not valid UTF-8 text: {e}") from e
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

    level_track = _require(raw, "level_track")
    if isinstance(level_track, bool) or not isinstance(level_track, int) or level_track not in (0, 1):
        raise InvalidSaveError(f"level_track must be 0 or 1, got {level_track!r}")

    return SaveFile(
        game_version=version,
        game_name=_clean_name(_require(raw, "game_name")),
        gamekey=_require(raw, "gamekey"),
        dungeon_lvl=_require(raw, "dungeon_lvl"),
        timestamp=_parse_timestamp(_require(raw, "timestamp")),
        player=_parse_player(players[player_num]),
        in_secret_level=level_track == 1,
    )


def _parse_player(raw: dict) -> Player:
    stats = _require(raw, "stats")
    raw_inventory = _require(stats, "inventory")
    slot_indices = _parse_equipment_slots(_require(stats, "player_equipment"), len(raw_inventory))
    equipped = set(slot_indices.values())
    inventory = tuple(_parse_item(item, i in equipped) for i, item in enumerate(raw_inventory))
    return Player(
        name=_clean_name(_require(stats, "name")),
        char_class=_require(raw, "char_class"),
        race=_require(raw, "race"),
        stats=_parse_stats(stats),
        kills=tuple(_require(raw, "kills")),
        hotbar=tuple(_none_if_empty(slot) for slot in _require(raw, "hotbar")),
        inventory=inventory,
        equipment=Equipment(**{slot: inventory[i] for slot, i in slot_indices.items()}),
        effects=_parse_effects(stats),
    )


def _parse_item(raw: dict, equipped: bool) -> Item:
    return Item(
        type=_require(raw, "type"),
        status=_require(raw, "status"),
        beatitude=_require(raw, "beatitude"),
        count=_require(raw, "count"),
        appearance=_require(raw, "appearance"),
        identified=_require(raw, "identified"),
        equipped=equipped,
    )


def _parse_equipment_slots(raw: list[dict], inventory_size: int) -> dict[str, int]:
    """Slot name -> inventory index, for filled slots.

    For the local player, ``player_equipment`` holds indices into the inventory
    (empty slots are uint32 -1). Missing slots count as empty.
    """
    known = Equipment.slot_names()
    slots = {}
    for entry in raw:
        slot, index = _require(entry, "first"), _none_if_empty(_require(entry, "second"))
        if slot not in known:
            raise InvalidSaveError(f"Unknown equipment slot {slot!r}")
        if index is None:
            continue
        if not 0 <= index < inventory_size:
            raise InvalidSaveError(
                f"Equipment slot {slot!r} points at inventory index {index}, "
                f"but the inventory has {inventory_size} items"
            )
        slots[slot] = index
    return slots


def _parse_effects(stats: dict) -> tuple[Effect, ...]:
    strengths, timers = _require(stats, "EFFECTS"), _require(stats, "EFFECTS_TIMERS")
    if len(strengths) != len(timers):
        raise InvalidSaveError(
            f"EFFECTS has {len(strengths)} entries but EFFECTS_TIMERS has {len(timers)}"
        )
    return tuple(
        Effect(id=i, strength=strength, timer_ticks=timer)
        for i, (strength, timer) in enumerate(zip(strengths, timers))
        if strength
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


def _parse_timestamp(value: str) -> datetime:
    try:
        return datetime.strptime(value, TIMESTAMP_FORMAT)
    except (TypeError, ValueError):
        raise InvalidSaveError(f"Bad timestamp {value!r}; expected format {TIMESTAMP_FORMAT!r}") from None


def _clean_name(name: str) -> str:
    return name.rstrip("\r")


def _none_if_empty(value: int) -> int | None:
    return None if value == UINT32_EMPTY else value
