import json
import re

import pytest
from PySide6.QtCore import QByteArray
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QComboBox, QSplitter

from barons_journal.ui.main_window import MainWindow
from barons_journal.ui.settings import AppSettings

LIVE = 1791824898


def _make(controller, settings, qtbot, *, start=True):
    if start:
        controller.start()
    w = MainWindow(controller, settings)
    qtbot.addWidget(w)
    w.show()
    return w


@pytest.fixture
def window(controller, settings, qtbot):
    return _make(controller, settings, qtbot)


@pytest.fixture
def empty_window(empty_dir_controller, settings, qtbot):
    return _make(empty_dir_controller, settings, qtbot)


@pytest.fixture
def window_with_unidentified_scroll(controller, settings, qtbot, save_dir, raw_save):
    raw_save["players"][0]["stats"]["inventory"].append(
        {
            "type": 75,
            "status": 3,
            "appearance": 0,
            "beatitude": 0,
            "count": 1,
            "identified": False,
            "x": -9999,
            "y": -9999,
        }
    )
    (save_dir / "savegame0.baronysave").write_text(json.dumps(raw_save))
    return _make(controller, settings, qtbot)


def _tab_titles(window):
    tabs = window.layouts.tabs
    return [tabs.tabText(i) for i in range(tabs.count())]


def test_default_layout_is_focus_with_five_tabs(window, settings):
    assert window.layouts.current == "focus"
    assert _tab_titles(window) == ["Backpack", "Floors", "Alchemy", "Scrolls", "Kills"]
    assert window.stack.currentIndex() == 1
    assert window.actions["layout_focus"].isChecked()


def test_switching_layout_keeps_panel_instances_and_text(window, settings):
    notes = window.panels.notes
    notes.run_editor.setPlainText("draft")
    window.actions["layout_dashboard"].trigger()
    assert window.panels.notes is notes and notes.run_editor.toPlainText() == "draft"
    assert window.layouts.tabs.count() == 3
    assert [window.layouts.tabs.tabText(i) for i in range(3)] == ["Floors", "Alchemy", "Scrolls"]
    assert settings.layout == "dashboard"
    window.actions["layout_focus"].trigger()
    assert window.layouts.tabs.count() == 5 and settings.layout == "focus"
    assert notes.run_editor.toPlainText() == "draft"


def test_layout_persists_across_windows(controller, settings, qtbot):
    w = _make(controller, settings, qtbot)
    w.actions["layout_dashboard"].trigger()
    w.close()
    w2 = _make(controller, AppSettings(settings._q.fileName()), qtbot, start=False)
    assert w2.layouts.current == "dashboard"
    assert w2.actions["layout_dashboard"].isChecked()


def test_hide_notes_panel(window, settings):
    window.actions["show_notes"].trigger()
    assert not window.panels.notes.isVisible()
    assert settings.notes_visible is False
    window.actions["layout_dashboard"].trigger()
    assert not window.panels.notes.isVisible()
    window.actions["show_notes"].trigger()
    assert window.panels.notes.isVisible()


def test_hide_character_panel(window, settings):
    window.actions["show_character"].trigger()
    assert not window.panels.character.isVisible()
    assert settings.character_visible is False


def test_hidden_panels_stay_hidden_in_new_window(controller, settings, qtbot):
    settings.notes_visible = False
    w = _make(controller, settings, qtbot)
    assert not w.panels.notes.isVisible()
    assert not w.actions["show_notes"].isChecked()


def test_menus(window):
    titles = [a.text().replace("&", "") for a in window.menuBar().actions()]
    assert titles == ["File", "Runs", "View"]
    a = window.actions
    assert a["choose_folder"].text() == "Choose save folder…"
    assert a["switch_run"].text() == "Switch run…"
    assert a["save_slot"].text() == "Save slot…"
    assert a["back_to_live"].text() == "Back to live run"


def test_back_to_live_action_enabled_only_in_past_mode(window, controller_with_two_runs):
    action = window.actions["back_to_live"]
    assert not action.isEnabled()
    controller_with_two_runs.open_run(42)
    assert action.isEnabled()
    action.trigger()
    assert controller_with_two_runs.view().mode == "live"
    assert not action.isEnabled()


def test_empty_state_page_when_no_saves(empty_window):
    assert empty_window.stack.currentIndex() == 0
    assert empty_window.choose_folder_button.isVisible()
    assert not empty_window.actions["back_to_live"].isEnabled()


def test_choose_folder_sets_save_dir_and_leaves_empty_state(
    empty_window, empty_dir_controller, save_dir, settings, monkeypatch
):
    monkeypatch.setattr(empty_window, "_ask_for_folder", lambda: save_dir)
    empty_window.choose_folder_button.click()
    assert settings.save_dir == save_dir
    assert empty_dir_controller.view().mode == "live"
    assert empty_window.stack.currentIndex() == 1


def test_choose_folder_action_and_cancel(empty_window, settings, monkeypatch):
    before = settings.save_dir
    monkeypatch.setattr(empty_window, "_ask_for_folder", lambda: None)
    empty_window.actions["choose_folder"].trigger()
    assert settings.save_dir == before


def test_close_flushes_pending_note(window, controller, qtbot, monkeypatch):
    from barons_journal.ui.widgets.note_editor import NoteEditor

    monkeypatch.setattr(NoteEditor, "IDLE_MS", 600_000)
    window.panels.notes.run_editor.setFocus()
    QTest.keyClicks(window.panels.notes.run_editor, "last words")
    window.close()
    assert controller.run_note(LIVE) == "last words"


def test_close_saves_geometry_and_splitter_sizes(window, settings):
    window.close()
    assert settings.geometry is not None
    assert settings.splitter_sizes("focus") is not None


def test_splitter_sizes_restored(controller, settings, qtbot):
    settings.set_splitter_sizes("focus", [200, 500, 300])
    w = _make(controller, settings, qtbot)
    splitter = w.layouts.splitter
    assert isinstance(splitter, QSplitter)
    assert splitter.sizes()[0] < splitter.sizes()[1]
    assert settings.splitter_sizes("focus") == [200, 500, 300]


def test_geometry_restored(controller, settings, qtbot):
    w = _make(controller, settings, qtbot)
    w.resize(900, 700)
    w.close()
    saved = settings.geometry
    assert isinstance(saved, QByteArray)
    w2 = MainWindow(controller, settings)  # not shown: no window-manager sizing involved
    qtbot.addWidget(w2)
    assert w2.size().width() == 900


def test_close_flushes_pending_floors_tab_note(window, controller, monkeypatch):
    from barons_journal.ui.widgets.note_editor import NoteEditor

    monkeypatch.setattr(NoteEditor, "IDLE_MS", 600_000)
    editor = window.panels.floors.note_editor
    editor.setFocus()
    QTest.keyClicks(editor, "floor words")
    window.close()
    assert "floor words" in controller.floor_notes(LIVE).values()


def test_layout_switch_flushes_pending_floors_tab_note(window, controller, monkeypatch):
    from barons_journal.ui.widgets.note_editor import NoteEditor

    monkeypatch.setattr(NoteEditor, "IDLE_MS", 600_000)
    editor = window.panels.floors.note_editor
    editor.setFocus()
    QTest.keyClicks(editor, "floor words")
    window.actions["layout_dashboard"].trigger()
    assert "floor words" in controller.floor_notes(LIVE).values()


def test_whole_window_never_shows_unidentified_true_name(
    window_with_unidentified_scroll, all_visible_text
):
    w = window_with_unidentified_scroll
    scrolls = w.panels.scrolls
    for name in ("focus", "dashboard"):
        w.actions[f"layout_{name}"].trigger()
        # The Scrolls tab's candidate pickers and "Still to find" list name every
        # scroll type by design; they say nothing about this item. Sweep the rest.
        combos = scrolls.findChildren(QComboBox)
        skip = [scrolls.remaining_list, *combos, *(c.view() for c in combos)]
        text = all_visible_text(w, skip=skip)
        assert "scroll of fire" not in text.lower()
        assert not re.search(r"\bfire\b", text, re.I)
        backpack = all_visible_text(w.panels.backpack)
        assert "scroll" in backpack.lower()
        rows = [line for line in backpack.splitlines() if "scroll" in line.lower()]
        assert rows and not any("fire" in line.lower() for line in rows)


def test_unreadable_only_save_shows_error_on_empty_page(controller, settings, save_dir, qtbot):
    (save_dir / "savegame0.baronsave").unlink(missing_ok=True)
    (save_dir / "savegame0.baronysave").write_text('{"magic_cookie": "BARONYJSONSAVE", "game_version": 503}')
    w = _make(controller, settings, qtbot)
    assert w.stack.currentIndex() == 0
    assert not w.empty_error.isHidden()
    assert w.empty_error.text().startswith("Couldn't read the save:")
    assert "last good data" not in w.empty_error.text()
    assert w.empty_title.text() != "No Barony saves found"
    assert not w.choose_folder_button.isHidden()


def test_no_saves_shows_plain_empty_page(empty_dir_controller, settings, qtbot):
    w = _make(empty_dir_controller, settings, qtbot)
    assert w.empty_title.text() == "No Barony saves found"
    assert w.empty_error.isHidden()
