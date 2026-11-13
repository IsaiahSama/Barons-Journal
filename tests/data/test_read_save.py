"""Tests for loading and parsing Barony .baronsave files."""

import pytest

from barons_journal.data import (
    InvalidSaveError,
    SaveFile,
    UnsupportedVersionError,
    load_save,
    parse_save,
)


# --- Loading the real sample save -------------------------------------------


class TestSampleSave:
    @pytest.fixture
    def save(self, sample_save_path) -> SaveFile:
        return load_save(sample_save_path)

    def test_returns_save_file(self, save):
        assert isinstance(save, SaveFile)

    def test_run_metadata(self, save):
        assert save.game_version == 502
        assert save.game_name == "Moonshine"
        assert save.gamekey == 1791824898
        assert save.dungeon_lvl == 0
        assert save.timestamp == "2026-10-12 13-08-18"

    def test_local_player_identity(self, save):
        player = save.player
        assert player.name == "Moonshine"
        assert player.char_class == 1
        assert player.race == 0

    def test_local_player_stats(self, save):
        stats = save.player.stats
        assert (stats.hp, stats.max_hp) == (30, 30)
        assert (stats.mp, stats.max_mp) == (20, 20)
        assert stats.strength == 1
        assert stats.dexterity == 1
        assert stats.constitution == 0
        assert stats.intelligence == -2
        assert stats.perception == -1
        assert stats.charisma == 1
        assert stats.exp == 0
        assert stats.level == 1
        assert stats.gold == 0
        assert stats.hunger == 1000

    def test_proficiencies(self, save):
        assert save.player.stats.proficiencies == (
            0, 0, 0, 0, 0, 40, 0, 0, 25, 25, 0, 0, 50, 25, 10, 0,
        )

    def test_kills_is_tuple_of_ints(self, save):
        kills = save.player.kills
        assert isinstance(kills, tuple)
        assert all(k == 0 for k in kills)

    def test_hotbar_empty_slots_are_none(self, save):
        assert save.player.hotbar == (None, 0, None, None, 1, None, None, None, None, None)


# --- Quirk handling ----------------------------------------------------------


class TestQuirks:
    def test_trailing_carriage_return_stripped_from_names(self, raw_save):
        raw_save["game_name"] = "Hero\r"
        raw_save["players"][0]["stats"]["name"] = "Hero\r"
        save = parse_save(raw_save)
        assert save.game_name == "Hero"
        assert save.player.name == "Hero"

    def test_uint32_minus_one_becomes_none_in_hotbar(self, raw_save):
        raw_save["players"][0]["hotbar"] = [4294967295] * 10
        assert parse_save(raw_save).player.hotbar == (None,) * 10

    def test_duplicate_race_key_uses_last_value(self, write_save, sample_save_path):
        text = sample_save_path.read_text(encoding="utf-8")
        # The real file has `"race": 0` twice in the local player; make them differ.
        first = text.index('"race": 0')
        second = text.index('"race": 0', first + 1)
        text = text[:second] + '"race": 3' + text[second + len('"race": 0'):]
        assert load_save(write_save(text)).player.race == 3

    def test_uses_player_num_to_pick_local_player(self, raw_save):
        raw_save["player_num"] = 2
        raw_save["players"][2]["stats"]["name"] = "Friend\r"
        assert parse_save(raw_save).player.name == "Friend"

    def test_parse_does_not_mutate_input(self, raw_save):
        import copy

        before = copy.deepcopy(raw_save)
        parse_save(raw_save)
        assert raw_save == before


# --- Validation --------------------------------------------------------------


class TestValidation:
    def test_wrong_magic_cookie(self, raw_save):
        raw_save["magic_cookie"] = "NOTASAVE"
        with pytest.raises(InvalidSaveError, match="magic"):
            parse_save(raw_save)

    def test_missing_magic_cookie(self, raw_save):
        del raw_save["magic_cookie"]
        with pytest.raises(InvalidSaveError, match="magic"):
            parse_save(raw_save)

    def test_unsupported_game_version(self, raw_save):
        raw_save["game_version"] = 9999
        with pytest.raises(UnsupportedVersionError, match="9999"):
            parse_save(raw_save)

    def test_unsupported_version_is_an_invalid_save(self):
        # Lets callers catch every "can't use this save" case with one except.
        assert issubclass(UnsupportedVersionError, InvalidSaveError)

    def test_not_json(self, write_save):
        with pytest.raises(InvalidSaveError, match="JSON"):
            load_save(write_save("this is not json"))

    def test_top_level_not_an_object(self, write_save):
        with pytest.raises(InvalidSaveError):
            load_save(write_save("[1, 2, 3]"))

    def test_missing_required_field(self, raw_save):
        del raw_save["players"][0]["stats"]["HP"]
        with pytest.raises(InvalidSaveError, match="HP"):
            parse_save(raw_save)

    def test_player_num_out_of_range(self, raw_save):
        raw_save["player_num"] = 7
        with pytest.raises(InvalidSaveError, match="player_num"):
            parse_save(raw_save)

    def test_missing_file_raises_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_save(tmp_path / "nope.baronsave")
