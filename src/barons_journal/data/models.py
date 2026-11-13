"""Typed, cleaned-up views of a Barony save. The UI only sees these."""

from dataclasses import dataclass


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


@dataclass(frozen=True, slots=True)
class Player:
    name: str
    char_class: int
    race: int
    stats: Stats
    kills: tuple[int, ...]
    hotbar: tuple[int | None, ...]


@dataclass(frozen=True, slots=True)
class SaveFile:
    game_version: int
    game_name: str
    gamekey: int
    dungeon_lvl: int
    timestamp: str
    player: Player
    """The local player (``players[player_num]`` in the raw save)."""
