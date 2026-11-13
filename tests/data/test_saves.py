"""Tests for finding Barony save files on disk."""

import os
import shutil
from datetime import datetime
from pathlib import Path

import pytest

from barons_journal.data import SaveSlot, default_save_dirs, find_saves, latest_save, load_save


def touch(path: Path, mtime: float = 1_700_000_000.0) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{}", encoding="utf-8")
    os.utime(path, (mtime, mtime))
    return path


# --- Finding saves --------------------------------------------------------------


class TestFindSaves:
    def test_empty_or_missing_folder(self, tmp_path):
        assert find_saves([tmp_path]) == []
        assert find_saves([tmp_path / "does-not-exist"]) == []

    def test_finds_single_player_save(self, tmp_path):
        path = touch(tmp_path / "savegame0.baronysave")
        (slot,) = find_saves([tmp_path])
        assert slot == SaveSlot(path=path, slot=0, multiplayer=False, modded=False,
                                modified=datetime.fromtimestamp(1_700_000_000.0))

    @pytest.mark.parametrize(
        ("name", "slot", "multiplayer", "modded"),
        [
            ("savegame3.baronysave", 3, False, False),
            ("savegame12_mp.baronysave", 12, True, False),
            ("savegame0_modded.baronysave", 0, False, True),
            ("savegame99_mp_modded.baronysave", 99, True, True),
        ],
    )
    def test_file_name_variants(self, tmp_path, name, slot, multiplayer, modded):
        touch(tmp_path / name)
        (found,) = find_saves([tmp_path])
        assert (found.slot, found.multiplayer, found.modded) == (slot, multiplayer, modded)

    @pytest.mark.parametrize(
        "name",
        [
            "savegame0.dat",  # old binary format
            "savegame0_npcs.dat",
            "savegame0_screenshot.png",
            "savegame100.baronysave",  # slots only go to 99
            "savegame.baronysave",
            "savegame0.baronysave.bak",
            "notes.txt",
        ],
    )
    def test_ignores_other_files(self, tmp_path, name):
        touch(tmp_path / name)
        assert find_saves([tmp_path]) == []

    def test_ignores_folders_named_like_saves(self, tmp_path):
        (tmp_path / "savegame0.baronysave").mkdir()
        assert find_saves([tmp_path]) == []

    def test_most_recently_modified_first(self, tmp_path):
        touch(tmp_path / "savegame0.baronysave", mtime=1_000)
        touch(tmp_path / "savegame1.baronysave", mtime=3_000)
        touch(tmp_path / "savegame2_mp.baronysave", mtime=2_000)
        assert [s.path.name for s in find_saves([tmp_path])] == [
            "savegame1.baronysave", "savegame2_mp.baronysave", "savegame0.baronysave",
        ]

    def test_searches_several_folders(self, tmp_path):
        touch(tmp_path / "a" / "savegame0.baronysave", mtime=1_000)
        touch(tmp_path / "b" / "savegame5.baronysave", mtime=2_000)
        found = find_saves([tmp_path / "a", tmp_path / "b"])
        assert [s.slot for s in found] == [5, 0]

    def test_found_save_loads(self, tmp_path, sample_save_path):
        path = tmp_path / "savegame0.baronysave"
        shutil.copy(sample_save_path, path)
        (slot,) = find_saves([tmp_path])
        assert load_save(slot.path).player.name == "Moonshine"


class TestLatestSave:
    def test_latest(self, tmp_path):
        touch(tmp_path / "savegame0.baronysave", mtime=1_000)
        touch(tmp_path / "savegame1.baronysave", mtime=2_000)
        assert latest_save([tmp_path]).slot == 1

    def test_none_when_no_saves(self, tmp_path):
        assert latest_save([tmp_path]) is None

    def test_uses_default_dirs_when_none_given(self, tmp_path, monkeypatch):
        monkeypatch.setattr("sys.platform", "linux")
        monkeypatch.setenv("HOME", str(tmp_path))
        touch(tmp_path / ".barony" / "savegames" / "savegame4.baronysave")
        assert latest_save().slot == 4


# --- Default folders ----------------------------------------------------------


class TestDefaultSaveDirs:
    def test_linux(self, monkeypatch, tmp_path):
        monkeypatch.setattr("sys.platform", "linux")
        monkeypatch.setenv("HOME", str(tmp_path))
        dirs = default_save_dirs()
        assert dirs[0] == tmp_path / ".barony" / "savegames"  # Steam and DRM-free builds
        assert tmp_path / ".barony" / "epicgames" / "savegames" in dirs  # Epic-only builds
        assert tmp_path / ".var/app/com.valvesoftware.Steam/.barony/savegames" in dirs  # Flatpak Steam

    def test_macos_uses_same_home_folder(self, monkeypatch, tmp_path):
        monkeypatch.setattr("sys.platform", "darwin")
        monkeypatch.setenv("HOME", str(tmp_path))
        assert default_save_dirs()[0] == tmp_path / ".barony" / "savegames"

    def test_windows_looks_in_install_folders(self, monkeypatch):
        # On Windows Barony saves next to the game, in <install folder>/savegames.
        monkeypatch.setattr("sys.platform", "win32")
        monkeypatch.setenv("PROGRAMFILES(X86)", "C:/PF86")
        monkeypatch.setenv("PROGRAMFILES", "C:/PF")
        dirs = default_save_dirs()
        assert Path("C:/PF86/Steam/steamapps/common/Barony/savegames") in dirs
        assert Path("C:/PF/Epic Games/Barony/savegames") in dirs

    def test_no_duplicates(self, monkeypatch, tmp_path):
        monkeypatch.setattr("sys.platform", "linux")
        monkeypatch.setenv("HOME", str(tmp_path))
        dirs = default_save_dirs()
        assert len(dirs) == len(set(dirs))
