import dataclasses

import pytest
from PySide6.QtTest import QTest

from barons_journal.data import load_save
from barons_journal.ui.location import Location, location_label
from barons_journal.ui.panels._stats import EMPTY_MESSAGE, PAST_MESSAGE
from barons_journal.ui.popouts.views import (
    AttributesView,
    CurrentFloorView,
    FloorNoteView,
    SkillsView,
    VitalsView,
)
from barons_journal.ui.state import ViewState
from barons_journal.ui.widgets.note_editor import NoteEditor

LIVE = 1791824898


def _live(save):
    return ViewState("live", run=None, save=save, location=Location.of_save(save), editable=True)


def _view(qtbot, controller, cls, save=None):
    v = cls(controller)
    qtbot.addWidget(v)
    if save is not None:
        v.render(_live(save))
    return v


def test_vitals_live(qtbot, controller, sample_save_path):
    v = _view(qtbot, controller, VitalsView, load_save(sample_save_path))
    assert (v.hp_bar.value(), v.hp_bar.maximum()) == (30, 30)
    assert (v.mp_bar.value(), v.mp_bar.maximum()) == (20, 20)
    assert v.hp_bar.objectName() == "hpBar" and v.mp_bar.objectName() == "mpBar"
    assert v.hp_bar.format() == "%v/%m"
    assert (v.gold_bar.value(), v.gold_bar.maximum(), v.gold_bar.text()) == (0, 10000, "0")
    assert (v.hunger_bar.value(), v.hunger_bar.maximum(), v.hunger_bar.text()) == (1000, 1000, "1000")
    assert v.gold_bar.objectName() == "goldBar" and v.hunger_bar.objectName() == "hungerBar"


def test_vitals_over_the_cap_shows_full_bar_and_real_number(qtbot, controller, sample_save_path):
    save = load_save(sample_save_path)
    stats = dataclasses.replace(save.player.stats, gold=12345, hunger=1400)
    save = dataclasses.replace(save, player=dataclasses.replace(save.player, stats=stats))
    v = _view(qtbot, controller, VitalsView, save)
    assert (v.gold_bar.value(), v.gold_bar.text()) == (10000, "12345")
    assert (v.hunger_bar.value(), v.hunger_bar.text()) == (1000, "1400")


def test_attributes_live(qtbot, controller, sample_save_path):
    v = _view(qtbot, controller, AttributesView, load_save(sample_save_path))
    assert v.table.rowCount() == 6
    assert (v.table.item(0, 0).text(), v.table.item(0, 1).text()) == ("STR", "1")
    assert v.table.item(5, 0).text() == "CHR"


def test_skills_live(qtbot, controller, sample_save_path):
    v = _view(qtbot, controller, SkillsView, load_save(sample_save_path))
    assert v.table.rowCount() == 16


@pytest.mark.parametrize("cls", [VitalsView, AttributesView, SkillsView])
def test_not_live_shows_message(qtbot, controller, cls):
    v = _view(qtbot, controller, cls)
    v.render(ViewState("past"))
    assert v.message.text() == PAST_MESSAGE
    v.render(ViewState("empty"))
    assert v.message.text() == EMPTY_MESSAGE


def _shown(qtbot, controller, cls):
    v = cls(controller)
    qtbot.addWidget(v)
    v.show()
    return v


def test_floor_note_saves_and_syncs(qtbot, controller):
    controller.start()
    v = _shown(qtbot, controller, FloorNoteView)
    assert v.title.text() == location_label(Location(0))
    v.editor.setFocus()
    QTest.keyClicks(v.editor, "lever")
    v.flush()
    assert controller.floor_note(LIVE, Location(0)) == "lever"
    v.editor.clearFocus()
    controller.save_floor_note(LIVE, Location(0), "edited elsewhere")
    assert v.editor.toPlainText() == "edited elsewhere"


def test_floor_note_same_floor_reload_keeps_typing(qtbot, controller, monkeypatch):
    monkeypatch.setattr(NoteEditor, "IDLE_MS", 600_000)
    controller.start()
    v = _shown(qtbot, controller, FloorNoteView)
    v.editor.setFocus()
    QTest.keyClicks(v.editor, "half typed")
    v._on_view(controller.view())
    assert v.editor.toPlainText() == "half typed"


def test_floor_note_saved_when_hidden(qtbot, controller, monkeypatch):
    monkeypatch.setattr(NoteEditor, "IDLE_MS", 600_000)
    controller.start()
    v = _shown(qtbot, controller, FloorNoteView)
    v.editor.setFocus()
    QTest.keyClicks(v.editor, "bye")
    v.hide()
    assert controller.floor_note(LIVE, Location(0)) == "bye"


def test_floor_note_read_only_when_not_live(qtbot, controller):
    v = _shown(qtbot, controller, FloorNoteView)
    v._on_view(ViewState("empty"))
    assert v.editor.isReadOnly()
    assert v.title.text() == "Floor note"


def _visible_rows(v):
    return [r for r in range(v.model.rowCount()) if not v.table.isRowHidden(r)]


def test_current_floor_shows_only_current_row(qtbot, controller):
    controller.start()
    v = _shown(qtbot, controller, CurrentFloorView)
    assert _visible_rows(v) == [v.model.row_of(Location(0))]
    assert v.table.isColumnHidden(v.model.COLUMNS.index("Note"))


def test_current_floor_empty_without_run(qtbot, controller):
    v = _shown(qtbot, controller, CurrentFloorView)
    v._on_view(ViewState("empty"))
    assert _visible_rows(v) == []


def test_current_floor_secret_level(qtbot, controller, journal, secret_save):
    journal.record_run(secret_save)
    run = journal.run(secret_save.gamekey)
    v = _shown(qtbot, controller, CurrentFloorView)
    loc = Location.of_save(secret_save)
    v._on_view(ViewState("live", run=run, save=secret_save, location=loc, editable=True))
    assert loc.secret
    assert _visible_rows(v) == [v.model.row_of(loc)]


def test_popout_window_flags(qtbot, controller):
    from PySide6.QtCore import Qt

    from barons_journal.ui.popouts.manager import PopoutWindow

    w = PopoutWindow("vitals", "Vitals", VitalsView(controller))
    qtbot.addWidget(w)
    assert w.windowFlags() & Qt.WindowType.WindowStaysOnTopHint
    assert w.windowType() == Qt.WindowType.Dialog
    assert w.parent() is None
    assert w.windowTitle() == "Vitals · Baron's Journal"
