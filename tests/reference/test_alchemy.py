"""Tests for the alchemy reference: ingredients, recipes, and mixing rules."""

import pytest

from barons_journal.data.ids import ITEMS
from barons_journal.reference.alchemy import (
    BASE_INGREDIENTS,
    RECIPES,
    SECONDARY_INGREDIENTS,
    Mix,
    Recipe,
    mix,
    recipes_making,
)

WATER, BOOZE, JUICE = 53, 54, 55
SICKNESS, CONFUSION, EXTRA_HEALING, HEALING = 56, 57, 58, 59
CURE_AILMENT, BLINDNESS, RESTORE_MAGIC, INVISIBILITY = 60, 61, 62, 63
LEVITATION, SPEED, ACID, PARALYSIS = 64, 65, 66, 67
POLYMORPH, FIRESTORM, ICESTORM, THUNDERSTORM, STRENGTH = 218, 222, 223, 224, 225


# --- Ingredients ----------------------------------------------------------------


def test_base_ingredients():
    assert BASE_INGREDIENTS == (WATER, POLYMORPH, BOOZE, JUICE, ACID, INVISIBILITY)


def test_secondary_ingredients():
    assert SECONDARY_INGREDIENTS == (
        WATER, SICKNESS, CONFUSION, CURE_AILMENT, BLINDNESS, RESTORE_MAGIC, SPEED, POLYMORPH,
    )


def test_ingredients_are_potions():
    for item_id in {*BASE_INGREDIENTS, *SECONDARY_INGREDIENTS}:
        assert any(word in ITEMS[item_id] for word in ("potion", "bottle")), ITEMS[item_id]


# --- Recipe table ---------------------------------------------------------------


def test_there_are_24_recipes():
    # 4 bases with fixed results x 6 secondaries with fixed results
    assert len(RECIPES) == 24
    assert all(isinstance(r, Recipe) for r in RECIPES)


def test_recipes_cover_every_fixed_pair_once():
    pairs = [(r.base, r.secondary) for r in RECIPES]
    assert len(set(pairs)) == 24
    assert {b for b, _ in pairs} == {BOOZE, JUICE, ACID, INVISIBILITY}
    assert {s for _, s in pairs} == {SICKNESS, CONFUSION, CURE_AILMENT, BLINDNESS, RESTORE_MAGIC, SPEED}


@pytest.mark.parametrize(
    ("base", "secondary", "result"),
    [
        (BOOZE, SICKNESS, CONFUSION),
        (BOOZE, BLINDNESS, STRENGTH),
        (BOOZE, SPEED, PARALYSIS),
        (JUICE, SICKNESS, BOOZE),
        (JUICE, RESTORE_MAGIC, HEALING),
        (JUICE, SPEED, INVISIBILITY),
        (ACID, CONFUSION, JUICE),
        (ACID, CURE_AILMENT, FIRESTORM),
        (ACID, BLINDNESS, ICESTORM),
        (ACID, SPEED, THUNDERSTORM),
        (INVISIBILITY, CURE_AILMENT, LEVITATION),
        (INVISIBILITY, BLINDNESS, POLYMORPH),
        (INVISIBILITY, RESTORE_MAGIC, EXTRA_HEALING),
    ],
)
def test_known_recipes(base, secondary, result):
    assert mix(base, secondary) == Mix("potion", result)


def test_recipe_names():
    recipe = next(r for r in RECIPES if (r.base, r.secondary) == (JUICE, RESTORE_MAGIC))
    assert (recipe.base_name, recipe.secondary_name, recipe.result_name) == (
        "bottle of fruit juice", "potion of restore magic", "potion of healing",
    )


def test_recipes_in_table_order():
    # base order, then secondary order, as the compendium-style grid reads
    keys = [(BASE_INGREDIENTS.index(r.base), SECONDARY_INGREDIENTS.index(r.secondary)) for r in RECIPES]
    assert keys == sorted(keys)


def test_recipes_making():
    assert [(r.base, r.secondary) for r in recipes_making(FIRESTORM)] == [
        (ACID, SICKNESS), (ACID, CURE_AILMENT),
    ]
    assert recipes_making(WATER) == ()


# --- Mixing rules -------------------------------------------------------------


class TestMixRules:
    def test_water_duplicates_the_other_potion(self):
        assert mix(BOOZE, WATER) == Mix("duplicate", BOOZE)
        assert mix(WATER, SPEED) == Mix("duplicate", SPEED)

    def test_acid_and_water_explode(self):
        assert mix(ACID, WATER) == Mix("explodes")

    def test_polymorph_gives_a_random_potion(self):
        assert mix(POLYMORPH, SICKNESS) == Mix("random")
        assert mix(BOOZE, POLYMORPH) == Mix("random")
        assert mix(ACID, POLYMORPH) == Mix("random")  # polymorph wins over acid's explosion

    def test_water_and_polymorph_is_random_not_duplicate(self):
        assert mix(WATER, POLYMORPH) == Mix("random")
        assert mix(POLYMORPH, WATER) == Mix("random")

    def test_same_potion_in_both_slots(self):
        assert mix(WATER, WATER) == Mix("same", WATER)
        assert mix(POLYMORPH, POLYMORPH) == Mix("same", POLYMORPH)

    def test_every_valid_pair_has_an_outcome(self):
        for base in BASE_INGREDIENTS:
            for secondary in SECONDARY_INGREDIENTS:
                assert mix(base, secondary).kind in {"potion", "duplicate", "random", "explodes", "same"}

    def test_rejects_non_base_ingredient(self):
        with pytest.raises(ValueError, match="base ingredient"):
            mix(SICKNESS, SPEED)

    def test_rejects_non_secondary_ingredient(self):
        with pytest.raises(ValueError, match="secondary ingredient"):
            mix(BOOZE, JUICE)
