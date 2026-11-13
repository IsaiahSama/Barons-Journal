"""Tests for parsing a player's inventory, equipment, and status effects."""

import pytest

from barons_journal.data import Effect, Equipment, InvalidSaveError, Item, load_save, parse_save
from barons_journal.data.ids import SPELL_ITEM

EMPTY = 4294967295


@pytest.fixture
def player(sample_save_path):
    return load_save(sample_save_path).player


def _stats(raw_save):
    return raw_save["players"][0]["stats"]


def _item(type_, *, status=3, appearance=0, beatitude=0, count=1, identified=True):
    return {
        "type": type_, "status": status, "appearance": appearance, "beatitude": beatitude,
        "count": count, "identified": identified, "x": 0, "y": 0,
    }


# --- Inventory ----------------------------------------------------------------


class TestInventory:
    def test_sample_inventory_names_in_order(self, player):
        assert [item.name for item in player.inventory] == [
            "iron spear", "bronze shield", "leather helm", "iron breastpiece",
            "leather boots", "bread", "fish",
        ]

    def test_item_fields(self, player):
        spear = player.inventory[0]
        assert isinstance(spear, Item)
        assert spear.type == 7
        assert spear.status == 3
        assert spear.status_name == "serviceable"
        assert spear.beatitude == 0
        assert spear.count == 1
        assert spear.identified is True
        assert spear.is_spell is False

    def test_worn_status(self, player):
        assert player.inventory[2].status_name == "worn"  # leather helm

    def test_equipped_flag(self, player):
        assert [item.equipped for item in player.inventory] == [True] * 5 + [False] * 2

    def test_unidentified_item_uses_unidentified_name(self, raw_save):
        gloves_of_dex = 21  # "leather gloves of dexterity" / "gloves"
        _stats(raw_save)["inventory"].append(_item(gloves_of_dex, identified=False))
        assert parse_save(raw_save).player.inventory[-1].name == "gloves"

    def test_identified_item_uses_full_name(self, raw_save):
        _stats(raw_save)["inventory"].append(_item(21, identified=True))
        assert parse_save(raw_save).player.inventory[-1].name == "leather gloves of dexterity"

    def test_spell_item_is_named_after_its_spell(self, raw_save):
        # Learned spells sit in the inventory as SPELL_ITEMs; appearance holds the spell ID.
        _stats(raw_save)["inventory"].append(_item(SPELL_ITEM, appearance=4))
        spell = parse_save(raw_save).player.inventory[-1]
        assert spell.is_spell is True
        assert spell.name == "Fireball"

    def test_beatitude_and_count(self, raw_save):
        _stats(raw_save)["inventory"].append(_item(154, beatitude=-2, count=3))
        bread = parse_save(raw_save).player.inventory[-1]
        assert (bread.beatitude, bread.count) == (-2, 3)

    def test_unknown_item_type_gets_fallback_name(self, raw_save):
        _stats(raw_save)["inventory"].append(_item(9999))
        assert parse_save(raw_save).player.inventory[-1].name == "Unknown item #9999"

    def test_missing_item_field_is_invalid(self, raw_save):
        del _stats(raw_save)["inventory"][0]["count"]
        with pytest.raises(InvalidSaveError, match="count"):
            parse_save(raw_save)


# --- Equipment ----------------------------------------------------------------


class TestEquipment:
    def test_sample_equipment_resolves_to_inventory_items(self, player):
        eq = player.equipment
        assert isinstance(eq, Equipment)
        assert eq.weapon.name == "iron spear"
        assert eq.shield.name == "bronze shield"
        assert eq.helmet.name == "leather helm"
        assert eq.breastplate.name == "iron breastpiece"
        assert eq.shoes.name == "leather boots"

    def test_empty_slots_are_none(self, player):
        eq = player.equipment
        assert (eq.gloves, eq.cloak, eq.amulet, eq.ring, eq.mask) == (None,) * 5

    def test_equipped_item_is_the_same_object_as_in_inventory(self, player):
        assert player.equipment.weapon is player.inventory[0]

    def test_slots_in_game_order(self, player):
        assert [slot for slot, _ in player.equipment.slots()] == [
            "helmet", "breastplate", "gloves", "shoes", "shield",
            "weapon", "cloak", "amulet", "ring", "mask",
        ]

    def test_index_out_of_range_is_invalid(self, raw_save):
        _stats(raw_save)["player_equipment"][0]["second"] = 50
        with pytest.raises(InvalidSaveError, match="helmet"):
            parse_save(raw_save)

    def test_unknown_slot_is_invalid(self, raw_save):
        _stats(raw_save)["player_equipment"].append({"first": "tail", "second": EMPTY})
        with pytest.raises(InvalidSaveError, match="tail"):
            parse_save(raw_save)

    def test_missing_slots_are_empty(self, raw_save):
        _stats(raw_save)["player_equipment"] = []
        save = parse_save(raw_save)
        assert all(item is None for _, item in save.player.equipment.slots())
        assert not any(item.equipped for item in save.player.inventory)


# --- Status effects -----------------------------------------------------------


class TestEffects:
    def test_sample_has_no_active_effects(self, player):
        assert player.effects == ()

    def test_active_effect(self, raw_save):
        _stats(raw_save)["EFFECTS"][16] = 1
        _stats(raw_save)["EFFECTS_TIMERS"][16] = 500  # 50 ticks per second
        (effect,) = parse_save(raw_save).player.effects
        assert isinstance(effect, Effect)
        assert effect.id == 16
        assert effect.name == "Magic Resistance"
        assert effect.strength == 1
        assert effect.timer_ticks == 500
        assert effect.seconds_remaining == 10.0
        assert effect.hidden is False

    def test_zero_timer_means_indefinite(self, raw_save):
        _stats(raw_save)["EFFECTS"][0] = 1
        (effect,) = parse_save(raw_save).player.effects
        assert effect.seconds_remaining is None

    def test_strength_above_one_is_kept(self, raw_save):
        _stats(raw_save)["EFFECTS"][47] = 3  # flute, tier III
        (effect,) = parse_save(raw_save).player.effects
        assert effect.strength == 3

    def test_effects_in_id_order(self, raw_save):
        for i in (30, 4, 16):
            _stats(raw_save)["EFFECTS"][i] = 1
        assert [e.id for e in parse_save(raw_save).player.effects] == [4, 16, 30]

    def test_hidden_effect_is_flagged(self, raw_save):
        _stats(raw_save)["EFFECTS"][2] = 1  # stunned: the game shows no HUD entry
        (effect,) = parse_save(raw_save).player.effects
        assert effect.hidden is True

    def test_reserved_slot_gets_fallback_name(self, raw_save):
        _stats(raw_save)["EFFECTS"][150] = 1
        (effect,) = parse_save(raw_save).player.effects
        assert effect.name == "Unknown effect #150"

    def test_effects_and_timers_length_mismatch_is_invalid(self, raw_save):
        _stats(raw_save)["EFFECTS_TIMERS"] = _stats(raw_save)["EFFECTS_TIMERS"][:10]
        with pytest.raises(InvalidSaveError, match="EFFECTS"):
            parse_save(raw_save)
