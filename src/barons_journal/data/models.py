"""Typed, cleaned-up views of a Barony save. The UI only sees these."""

from collections.abc import Iterator
from dataclasses import dataclass, fields
from datetime import datetime

from .ids import (
    CLASSES,
    EFFECTS,
    HIDDEN_EFFECTS,
    ITEM_STATUS,
    ITEMS,
    ITEMS_UNIDENTIFIED,
    MONSTERS,
    PROFICIENCIES,
    RACES,
    SPELL_ITEM,
    SPELLS,
)

TICKS_PER_SECOND = 50


@dataclass(frozen=True, slots=True)
class Stats:
    hp: int
    max_hp: int
    mp: int
    max_mp: int
    strength: int
    dexterity: int
    constitution: int
    intelligence: int
    perception: int
    charisma: int
    exp: int
    level: int
    gold: int
    hunger: int
    proficiencies: tuple[int, ...]

    @property
    def proficiencies_by_name(self) -> dict[str, int]:
        """Skill name -> level (0-100), in the game's skill order."""
        return {PROFICIENCIES.label(i): level for i, level in enumerate(self.proficiencies)}


@dataclass(frozen=True, slots=True)
class Item:
    type: int
    status: int
    """Condition, 0 (broken) to 4 (excellent). See ``status_name``."""
    beatitude: int
    """Blessing: positive is blessed (+N), negative is cursed (-N)."""
    count: int
    appearance: int
    """Random per-item value; for spell items, the spell ID."""
    identified: bool
    equipped: bool

    @property
    def is_spell(self) -> bool:
        return self.type == SPELL_ITEM

    @property
    def name(self) -> str:
        """The in-game name, as the player currently knows it."""
        if self.is_spell:
            return SPELLS.label(self.appearance)
        table = ITEMS if self.identified else ITEMS_UNIDENTIFIED
        return table.label(self.type)

    @property
    def status_name(self) -> str:
        return ITEM_STATUS.label(self.status)


@dataclass(frozen=True, slots=True)
class Equipment:
    """What the player is wearing and wielding. Each slot is an item from the inventory, or None."""

    helmet: Item | None = None
    breastplate: Item | None = None
    gloves: Item | None = None
    shoes: Item | None = None
    shield: Item | None = None
    weapon: Item | None = None
    cloak: Item | None = None
    amulet: Item | None = None
    ring: Item | None = None
    mask: Item | None = None

    @classmethod
    def slot_names(cls) -> tuple[str, ...]:
        return tuple(f.name for f in fields(cls))

    def slots(self) -> Iterator[tuple[str, Item | None]]:
        """(slot name, item) pairs, in the game's slot order."""
        for name in self.slot_names():
            yield name, getattr(self, name)


@dataclass(frozen=True, slots=True)
class Effect:
    """An active status effect."""

    id: int
    strength: int
    """Effect level. Usually 1; some effects use higher values for tiers."""
    timer_ticks: int

    @property
    def name(self) -> str:
        return EFFECTS.label(self.id)

    @property
    def hidden(self) -> bool:
        """True for internal effects the game doesn't show the player."""
        return self.id in HIDDEN_EFFECTS

    @property
    def seconds_remaining(self) -> float | None:
        """Time left in game seconds, or None if the effect has no timer."""
        return self.timer_ticks / TICKS_PER_SECOND if self.timer_ticks > 0 else None


@dataclass(frozen=True, slots=True)
class Player:
    name: str
    char_class: int
    race: int
    stats: Stats
    kills: tuple[int, ...]
    hotbar: tuple[int | None, ...]
    inventory: tuple[Item, ...]
    """Everything carried, including equipped items and learned spells."""
    equipment: Equipment
    effects: tuple[Effect, ...]
    """Active status effects only, in ID order."""

    @property
    def class_name(self) -> str:
        return CLASSES.label(self.char_class)

    @property
    def race_name(self) -> str:
        return RACES.label(self.race)

    @property
    def kills_by_monster(self) -> dict[str, int]:
        """Monster name -> kill count, for monsters killed at least once."""
        return {MONSTERS.label(i): n for i, n in enumerate(self.kills) if n}


@dataclass(frozen=True, slots=True)
class SaveFile:
    game_version: int
    game_name: str
    gamekey: int
    dungeon_lvl: int
    timestamp: datetime
    """When Barony wrote the save, in local time (no timezone)."""
    player: Player
    """The local player (``players[player_num]`` in the raw save)."""
