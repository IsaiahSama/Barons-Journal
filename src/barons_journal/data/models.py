"""Typed, cleaned-up views of a Barony save. The UI only sees these."""

from dataclasses import dataclass

from .ids import CLASSES, MONSTERS, PROFICIENCIES, RACES


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
class Player:
    name: str
    char_class: int
    race: int
    stats: Stats
    kills: tuple[int, ...]
    hotbar: tuple[int | None, ...]

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
    timestamp: str
    player: Player
    """The local player (``players[player_num]`` in the raw save)."""
