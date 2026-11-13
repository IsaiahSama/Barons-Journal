"""Tests for the numeric-ID -> name lookup tables."""

import pytest

from barons_journal.data import load_save, parse_save
from barons_journal.data.ids import (
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


# --- Table shapes match the game's enums (Barony v502) -----------------------


@pytest.mark.parametrize(
    ("table", "size"),
    [
        (CLASSES, 26),  # NUMCLASSES
        (RACES, 18),  # NUMRACES
        (MONSTERS, 53),  # NUMMONSTERS, also len(players[n].kills)
        (PROFICIENCIES, 16),  # NUMPROFICIENCIES, also len(stats.PROFICIENCIES)
        (ITEMS, 524),  # NUMITEMS
        (ITEMS_UNIDENTIFIED, 524),
        (SPELLS, 225),  # NUM_SPELLS
        (ITEM_STATUS, 5),
        (EFFECTS, 135),  # EFF_* constants; the save reserves NUMEFFECTS = 160 slots
    ],
)
def test_table_sizes(table, size):
    assert len(table) == size


def test_table_sizes_match_sample_save_arrays(raw_save):
    player = raw_save["players"][0]
    assert len(MONSTERS) == len(player["kills"])
    assert len(PROFICIENCIES) == len(player["stats"]["PROFICIENCIES"])


# --- Spot checks, at the start, end, and known-tricky spots ------------------


@pytest.mark.parametrize(
    ("table", "id_", "name"),
    [
        (CLASSES, 0, "Barbarian"),
        (CLASSES, 1, "Warrior"),
        (CLASSES, 17, "Mechanist"),  # enum is CLASS_MACHINIST; in-game text says Mechanist
        (CLASSES, 25, "Paladin"),
        (RACES, 0, "Human"),
        (RACES, 9, "Rat"),
        (RACES, 17, "Salamander"),
        (MONSTERS, 1, "human"),
        (MONSTERS, 23, "crystal golem"),
        (MONSTERS, 37, "bugbear"),
        (MONSTERS, 48, "earth sprite"),  # enum is EARTH_ELEMENTAL
        (PROFICIENCIES, 0, "Tinkering"),  # enum is PRO_LOCKPICKING
        (PROFICIENCIES, 12, "Polearm"),
        (PROFICIENCIES, 15, "Alchemy"),
        (ITEMS, 0, "wooden shield"),
        (ITEMS, 7, "iron spear"),
        (ITEMS_UNIDENTIFIED, 7, "iron spear"),
        (SPELLS, 1, "Forcebolt"),
        (SPELLS, 217, "Project Spirit"),
        # The Save Editor skips SPELL_DUCK_DIVE, shifting 218+ by one. Guard against that.
        (SPELLS, 218, "Duck Dive"),
        (SPELLS, 224, "Holy Beam"),
        (ITEM_STATUS, 0, "broken"),
        (ITEM_STATUS, 4, "excellent"),
        (EFFECTS, 0, "Asleep"),
        (EFFECTS, 16, "Magic Resistance"),
        (EFFECTS, 2, "Stunned"),  # no in-game name; derived from EFF_STUNNED
        (EFFECTS, 18, "Vampiric Aura"),  # in-game name varies by context
        (EFFECTS, 29, "Shapeshifted"),  # in-game: Rat Form / Troll Form / ...
        (EFFECTS, 47, "Flute"),  # in-game: Flute (Tier I..IV)
        (EFFECTS, 128, "Radiant Heart"),
        (EFFECTS, 133, "Sanctuary"),
        (EFFECTS, 134, "Ducked"),  # game data has placeholder "EFF_DUCKED"
    ],
)
def test_known_names(table, id_, name):
    assert table[id_] == name


def test_identified_and_unidentified_item_names_differ_where_expected():
    gloves = ITEMS.index_of("leather gloves of dexterity")
    assert ITEMS_UNIDENTIFIED[gloves] == "gloves"


def test_spell_item_constant():
    assert ITEMS[SPELL_ITEM] == "spell"


def test_hidden_effects_are_ones_the_game_does_not_show():
    assert 2 in HIDDEN_EFFECTS  # stunned
    assert 0 not in HIDDEN_EFFECTS  # asleep
    assert 134 not in HIDDEN_EFFECTS  # has a placeholder name, not a blank one
    assert all(0 <= i < len(EFFECTS) for i in HIDDEN_EFFECTS)


def test_spell_zero_means_no_spell():
    assert SPELLS.get(0) is None


def test_no_blank_names_except_spell_none():
    for table in (CLASSES, RACES, MONSTERS, PROFICIENCIES, ITEMS, ITEMS_UNIDENTIFIED, ITEM_STATUS, EFFECTS):
        assert all(table.get(i) for i in range(len(table))), table.kind
    assert all(SPELLS.get(i) for i in range(1, len(SPELLS)))


# --- Lookup behaviour ---------------------------------------------------------


class TestIdTable:
    def test_getitem_unknown_raises_key_error(self):
        with pytest.raises(KeyError):
            CLASSES[99]

    def test_get_unknown_returns_default(self):
        assert CLASSES.get(99) is None
        assert CLASSES.get(99, "?") == "?"

    def test_negative_ids_are_unknown_not_python_negative_indexing(self):
        assert CLASSES.get(-1) is None
        with pytest.raises(KeyError):
            CLASSES[-1]

    def test_label_falls_back_for_unknown_ids(self):
        assert CLASSES.label(1) == "Warrior"
        assert CLASSES.label(99) == "Unknown class #99"

    def test_index_of_unknown_name_raises(self):
        with pytest.raises(ValueError):
            CLASSES.index_of("Astronaut")


# --- Names exposed on the parsed models ---------------------------------------


class TestModelNames:
    @pytest.fixture
    def player(self, sample_save_path):
        return load_save(sample_save_path).player

    def test_class_and_race_names(self, player):
        assert player.class_name == "Warrior"
        assert player.race_name == "Human"

    def test_proficiencies_by_name(self, player):
        profs = player.stats.proficiencies_by_name
        assert list(profs) == [PROFICIENCIES[i] for i in range(16)]
        assert profs["Polearm"] == 50
        assert profs["Leader"] == 40

    def test_kills_by_monster_only_lists_nonzero(self, player, raw_save):
        assert player.kills_by_monster == {}
        raw_save["players"][0]["kills"][2] = 5  # rat
        raw_save["players"][0]["kills"][23] = 1  # crystal golem
        kills = parse_save(raw_save).player.kills_by_monster
        assert kills == {"rat": 5, "crystal golem": 1}

    def test_unknown_class_id_gets_fallback_label(self, raw_save):
        raw_save["players"][0]["char_class"] = 99
        assert parse_save(raw_save).player.class_name == "Unknown class #99"
