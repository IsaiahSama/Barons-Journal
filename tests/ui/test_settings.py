from pathlib import Path

from PySide6.QtCore import QByteArray

from barons_journal.ui.settings import AppSettings


def test_defaults(settings):
    assert settings.layout == "focus"
    assert settings.follow is None
    assert settings.save_dir is None
    assert settings.geometry is None
    assert settings.character_visible is True
    assert settings.notes_visible is True
    assert settings.splitter_sizes("focus") is None
    assert settings.splitter_sizes("dashboard") is None


def test_round_trip(tmp_path):
    path = tmp_path / "settings.ini"
    first = AppSettings(path)
    first.layout = "dashboard"
    first.save_dir = Path("/some/saves")
    first.follow = Path("/some/saves/savegame1.baronysave")
    first.geometry = QByteArray(b"\x01\x02geo")
    first.character_visible = False
    first.notes_visible = False
    first.set_splitter_sizes("focus", [300, 700])
    first.set_splitter_sizes("dashboard", [200, 300, 500])
    del first

    second = AppSettings(path)
    assert second.layout == "dashboard"
    assert second.save_dir == Path("/some/saves")
    assert second.follow == Path("/some/saves/savegame1.baronysave")
    assert second.geometry == QByteArray(b"\x01\x02geo")
    assert second.character_visible is False
    assert second.notes_visible is False
    assert second.splitter_sizes("focus") == [300, 700]
    assert second.splitter_sizes("dashboard") == [200, 300, 500]


def test_follow_can_be_cleared(tmp_path):
    path = tmp_path / "settings.ini"
    first = AppSettings(path)
    first.follow = Path("/x")
    first.follow = None
    assert AppSettings(path).follow is None


def test_popout_open_defaults_false_and_persists(settings, tmp_path):
    assert settings.popout_open("vitals") is False
    settings.set_popout_open("vitals", True)
    assert AppSettings(tmp_path / "settings.ini").popout_open("vitals") is True
    assert settings.popout_open("skills") is False


def test_popout_geometry_round_trip(settings, tmp_path):
    assert settings.popout_geometry("vitals") is None
    settings.set_popout_geometry("vitals", QByteArray(b"abc"))
    assert AppSettings(tmp_path / "settings.ini").popout_geometry("vitals") == QByteArray(b"abc")
