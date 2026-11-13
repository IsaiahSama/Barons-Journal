"""Tests for the floor map: main floors, secret levels, and where artifacts are."""

import pytest

from barons_journal.data.ids import ITEMS
from barons_journal.reference.floors import (
    FLOORS,
    SECRET_LEVELS,
    Floor,
    SecretLevel,
    artifact_locations,
    floor_at,
    orb_floors,
    secret_level_at,
)

DYRNWYN, GUNGNIR, KHRYSELAKATOS, DRAGONS_MAIL = 163, 165, 167, 168
SPHINXS_CASQUE, ORACLES_TREADS, WRAITHS_GOWN, DJINNIS_BRACE = 169, 170, 171, 172
BLUE_ORB, RED_ORB, PURPLE_ORB, GREEN_ORB = 211, 212, 213, 214


# --- Main floors ----------------------------------------------------------------


def test_one_floor_per_dungeon_level():
    assert [f.dungeon_lvl for f in FLOORS] == list(range(36))
    assert all(isinstance(f, Floor) for f in FLOORS)


@pytest.mark.parametrize(
    ("lvl", "area"),
    [
        (0, "Minehead"),
        (1, "Mines"),
        (5, "Transition Floor"),
        (6, "Swamps"),
        (11, "Labyrinth"),
        (16, "Ruins"),
        (20, "Lich's Bastion"),
        (21, "Hell"),
        (24, "The Molten Throne"),
        (25, "Hamlet"),
        (26, "Crystal Caves"),
        (31, "Arcane Citadel"),
        (35, "Citadel Sanctum"),
    ],
)
def test_floor_areas(lvl, area):
    assert floor_at(lvl).area == area


def test_floor_at_unknown_level():
    with pytest.raises(KeyError):
        floor_at(99)


# --- Secret entrances on main floors ---------------------------------------------


@pytest.mark.parametrize(
    ("lvl", "secret_name"),
    [
        (2, "Gnomish Mines"),
        (3, "Minetown"),
        (5, "Underworld"),
        (7, "Temple"),
        (8, "Haunted Castle"),
        (11, "Sokoban"),
        (13, "Minotaur Maze"),
        (16, "Mystic Library"),
        (18, "Underworld"),
        (28, "Cockatrice Lair"),
        (33, "Bram's Castle"),
    ],
)
def test_secret_entrances(lvl, secret_name):
    assert floor_at(lvl).secret_entrance.name == secret_name


def test_floors_without_secret_entrance():
    # Floor 23 has an entrance in the code, but it leads to a secret-list line that isn't a secret place.
    for lvl in (0, 1, 4, 9, 12, 20, 23, 25, 35):
        assert floor_at(lvl).secret_entrance is None, lvl
        assert floor_at(lvl).secret_entrance_chance is None, lvl


def test_secret_entrance_chance():
    assert floor_at(2).secret_entrance_chance == 1.0
    assert floor_at(3).secret_entrance_chance == 0.5  # maps.cpp: currentlevel == 3 && rand() % 2


def test_secret_entrance_leads_one_level_down():
    for floor in FLOORS:
        if floor.secret_entrance:
            assert floor.secret_entrance.dungeon_lvl == floor.dungeon_lvl + 1


# --- Secret levels --------------------------------------------------------------


def test_secret_levels_by_depth():
    assert [s.dungeon_lvl for s in SECRET_LEVELS] == [3, 4, 6, 7, 8, 9, 12, 14, 17, 19, 20, 29, 34]
    assert all(isinstance(s, SecretLevel) for s in SECRET_LEVELS)


def test_secret_level_at():
    assert secret_level_at(3).name == "Gnomish Mines"
    assert secret_level_at(5) is None


def test_reached_from_main_floor():
    gnomish = secret_level_at(3)
    assert (gnomish.entrance_floor, gnomish.previous) == (2, None)


def test_every_secret_level_has_a_known_way_in():
    for secret in SECRET_LEVELS:
        assert (secret.entrance_floor is None) != (secret.previous is None), secret.name


def test_second_underworld_floor_is_reached_from_the_first():
    # compendium: "a trapdoor down to a second floor of the underworld"
    for lvl in (7, 20):
        underworld = secret_level_at(lvl)
        assert (underworld.entrance_floor, underworld.previous) == (None, "Underworld")


def test_minetown_and_haunted_castle_have_main_floor_entrances():
    assert secret_level_at(4).entrance_floor == 3
    assert secret_level_at(9).entrance_floor == 8


def test_treasures_from_compendium():
    assert secret_level_at(9).treasures == ("Oracle's Treads", "Hidden treasure chests", "4 Potions of levitation")
    assert "Four random shops" in secret_level_at(4).treasures


# --- Artifacts ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("lvl", "artifacts"),
    [
        (3, (SPHINXS_CASQUE,)),
        (4, ()),
        (6, ()),  # first underworld floor: the artifact is one floor further down
        (7, (KHRYSELAKATOS,)),
        (9, (ORACLES_TREADS,)),
        (12, (DJINNIS_BRACE,)),
        (14, (GUNGNIR,)),
        (19, ()),
        (20, (KHRYSELAKATOS,)),
        (29, (DRAGONS_MAIL,)),
        (34, (WRAITHS_GOWN,)),
    ],
)
def test_artifacts_per_secret_level(lvl, artifacts):
    assert secret_level_at(lvl).artifacts == artifacts


def test_artifact_names():
    assert secret_level_at(14).artifact_names == ("Gungnir",)


def test_artifact_locations():
    locations = artifact_locations()
    assert set(locations) == {
        SPHINXS_CASQUE, ORACLES_TREADS, DJINNIS_BRACE, GUNGNIR, KHRYSELAKATOS, DRAGONS_MAIL, WRAITHS_GOWN,
    }
    assert [s.dungeon_lvl for s in locations[KHRYSELAKATOS]] == [7, 20]
    assert DYRNWYN not in locations  # not a secret-level treasure


def test_artifacts_are_real_items():
    for secret in SECRET_LEVELS:
        for item_id in secret.artifacts:
            assert ITEMS.get(item_id), item_id


# --- Mystic orbs --------------------------------------------------------------


@pytest.mark.parametrize(
    ("lvl", "orb", "orb_name", "area"),
    [
        (8, GREEN_ORB, "green mystic orb", "Swamps"),
        (13, RED_ORB, "red mystic orb", "Labyrinth"),
        (18, BLUE_ORB, "blue mystic orb", "Ruins"),
    ],
)
def test_orb_floors(lvl, orb, orb_name, area):
    floor = floor_at(lvl)
    assert (floor.orb, floor.orb_name, floor.area) == (orb, orb_name, area)


def test_other_floors_have_no_orb():
    assert [f.dungeon_lvl for f in FLOORS if f.orb is not None] == [8, 13, 18]
    assert floor_at(0).orb_name is None


def test_orb_floors_lookup():
    assert {orb: f.dungeon_lvl for orb, f in orb_floors().items()} == {GREEN_ORB: 8, RED_ORB: 13, BLUE_ORB: 18}
    assert PURPLE_ORB not in orb_floors()  # not placed on any floor
