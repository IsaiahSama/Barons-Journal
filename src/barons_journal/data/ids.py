"""Numeric ID -> display name lookups for Barony's enums.

Data lives in ids.json, generated from the Barony source by
scripts/build_id_tables.py. Names are the in-game English strings.
"""

import json
from collections.abc import Sequence
from importlib.resources import files


class IdTable:
    """An immutable ID -> name table. IDs are list positions in the game's enum."""

    __slots__ = ("kind", "_names")

    def __init__(self, kind: str, names: Sequence[str | None]) -> None:
        self.kind = kind
        self._names = tuple(names)

    def __len__(self) -> int:
        return len(self._names)

    def __getitem__(self, id_: int) -> str:
        name = self.get(id_)
        if name is None:
            raise KeyError(f"no {self.kind} with ID {id_}")
        return name

    def get[T](self, id_: int, default: T = None) -> str | T:
        # Explicit bounds check: Python's negative indexing would silently map -1 to the last entry.
        if 0 <= id_ < len(self._names) and self._names[id_] is not None:
            return self._names[id_]
        return default

    def label(self, id_: int) -> str:
        """The name, or a readable placeholder for IDs this table doesn't know."""
        return self.get(id_) or f"Unknown {self.kind} #{id_}"

    def index_of(self, name: str) -> int:
        """Reverse lookup. Raises ``ValueError`` if no entry has this name."""
        return self._names.index(name)

    def __repr__(self) -> str:
        return f"IdTable({self.kind!r}, {len(self)} entries)"


_data = json.loads(files(__package__).joinpath("ids.json").read_text(encoding="utf-8"))

CLASSES = IdTable("class", _data["classes"])
RACES = IdTable("race", _data["races"])
MONSTERS = IdTable("monster", _data["monsters"])
PROFICIENCIES = IdTable("proficiency", _data["proficiencies"])
ITEMS = IdTable("item", _data["items"])
ITEMS_UNIDENTIFIED = IdTable("item", _data["items_unidentified"])
SPELLS = IdTable("spell", _data["spells"])
ITEM_STATUS = IdTable("item status", _data["item_status"])
EFFECTS = IdTable("effect", _data["effects"])
HIDDEN_EFFECTS: frozenset[int] = frozenset(_data["effects_hidden"])
"""Effect IDs the game never shows in its HUD (internal timers and flags)."""

SPELL_ITEM = 162
"""Item type of a learned spell in the inventory; the item's ``appearance`` is the spell ID."""

del _data
