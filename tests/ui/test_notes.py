import pytest
from PySide6.QtTest import QTest

from barons_journal.ui.location import Location
from barons_journal.ui.panels.notes import NotesPanel
from barons_journal.ui.widgets.note_editor import NoteEditor

LIVE = 1791824898


def _editor(qtbot):
    ed = NoteEditor()
    qtbot.addWidget(ed)
    ed.show()
    return ed


def _bind(ed, initial=""):
    saved: list[str] = []
    ed.bind(lambda: initial, saved.append, read_only=False)
    return saved


def test_typing_saves_after_idle(qtbot):
    ed = _editor(qtbot)
    saved = _bind(ed)
    QTest.keyClicks(ed, "hi")
    assert saved == []
    qtbot.waitUntil(lambda: saved == ["hi"], timeout=3000)


def test_flush_saves_immediately(qtbot):
    ed = _editor(qtbot)
    saved = _bind(ed)
    QTest.keyClicks(ed, "hi")
    ed.flush()
    assert saved == ["hi"]
    ed.flush()
    assert saved == ["hi"]


def test_rebinding_flushes_previous(qtbot):
    ed = _editor(qtbot)
    a = _bind(ed)
    QTest.keyClicks(ed, "hi")
    b = _bind(ed, "other")
    assert a == ["hi"]
    assert ed.toPlainText() == "other"
    assert b == []


def test_programmatic_load_does_not_save(qtbot):
    ed = _editor(qtbot)
    saved = _bind(ed, "loaded")
    ed.flush()
    qtbot.wait(NoteEditor.IDLE_MS + 200)
    assert saved == []


def test_read_only_binding(qtbot):
    ed = _editor(qtbot)
    ed.bind(lambda: "x", lambda body: None, read_only=True)
    assert ed.isReadOnly() and ed.toPlainText() == "x"
    ed.bind(None, None, read_only=False)
    assert ed.isReadOnly() and ed.toPlainText() == ""


def test_reload_if_unfocused(qtbot):
    ed = _editor(qtbot)
    text = ["a"]
    ed.bind(lambda: text[0], lambda b: None, read_only=False)
    text[0] = "b"
    ed.reload_if_unfocused()
    assert ed.toPlainText() == "b"


@pytest.fixture
def notes_panel(controller, qtbot):
    controller.start()
    panel = NotesPanel(controller)
    qtbot.addWidget(panel)
    panel.show()
    return panel


def _go_to(controller, raw_save, lvl, secret=0):
    raw_save["dungeon_lvl"] = lvl
    raw_save["level_track"] = secret
    import json

    path = controller._resolve()
    path.write_text(json.dumps(raw_save))
    controller.reload()


def test_panel_follows_floor_when_unfocused(notes_panel, controller, raw_save):
    assert notes_panel.showing_location() == Location(0)
    _go_to(controller, raw_save, 1)
    assert notes_panel.showing_location() == Location(1)
    assert notes_panel.floor_title.text() == "Floor 1 (Mines) notes"
    assert not notes_panel.switch_prompt.isVisible()


def test_panel_prompts_instead_of_jumping_when_focused(
    notes_panel, controller, raw_save, monkeypatch
):
    monkeypatch.setattr(notes_panel, "_floor_editor_active", lambda: True)
    QTest.keyClicks(notes_panel.floor_editor, "loot")
    _go_to(controller, raw_save, 1)
    assert notes_panel.showing_location() == Location(0)
    assert notes_panel.switch_prompt.isVisible()
    assert "Now on Floor 1 (Mines)" in notes_panel.switch_label.text()
    assert controller.floor_note(LIVE, Location(0)) == "loot"
    notes_panel.switch_button.click()
    assert notes_panel.showing_location() == Location(1)
    assert not notes_panel.switch_prompt.isVisible()


def test_run_note_saves_and_flushes_on_about_to_change(notes_panel, controller):
    QTest.keyClicks(notes_panel.run_editor, "plan")
    controller.about_to_change.emit()
    assert controller.run_note(LIVE) == "plan"


def test_floor_note_changed_reloads_unfocused_editor(notes_panel, controller):
    controller.save_floor_note(LIVE, Location(0), "from elsewhere")
    assert notes_panel.floor_editor.toPlainText() == "from elsewhere"


def test_past_run_notes_are_read_only(notes_panel, controller_with_two_runs, journal):
    c = controller_with_two_runs
    journal.set_run_note(42, "old plan")
    c.open_run(42)
    assert notes_panel.run_editor.isReadOnly()
    assert notes_panel.floor_editor.isReadOnly()
    assert notes_panel.run_editor.toPlainText() == "old plan"
    c.back_to_live()
    assert not notes_panel.run_editor.isReadOnly()


def test_secret_level_note_separate_in_panel(notes_panel, controller, raw_save, journal):
    journal.set_floor_note(LIVE, 3, "main three")
    _go_to(controller, raw_save, 3, 1)
    assert notes_panel.showing_location() == Location(3, True)
    assert notes_panel.floor_title.text() == "Gnomish Mines · depth 3 notes"
    assert notes_panel.floor_editor.toPlainText() == ""


def test_same_floor_view_change_keeps_text_and_cursor(
    notes_panel, controller, raw_save, monkeypatch
):
    monkeypatch.setattr(notes_panel, "_floor_editor_active", lambda: True)
    floor, run = notes_panel.floor_editor, notes_panel.run_editor
    QTest.keyClicks(floor, "floor text")
    QTest.keyClicks(run, "run text")
    cursor = run.textCursor()
    cursor.setPosition(3)
    run.setTextCursor(cursor)
    before = (floor.toPlainText(), floor.textCursor().position(), run.textCursor().position())
    raw_save["gold"] = 1
    raw_save["players"][0]["stats"]["GOLD"] = 12345
    _go_to(controller, raw_save, 0)
    after = (floor.toPlainText(), floor.textCursor().position(), run.textCursor().position())
    assert after == before
    assert run.toPlainText() == "run text"
    assert not notes_panel.switch_prompt.isVisible()
