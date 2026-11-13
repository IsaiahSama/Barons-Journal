import json

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from barons_journal.ui.location import Location
from barons_journal.ui.panels.floors import FloorsModel, FloorsPanel
from barons_journal.ui.state import ViewState

LIVE = 1791824898


def _col(model, name):
    return model.COLUMNS.index(name)


def _text(model, loc, name):
    return model.index(model.row_of(loc), _col(model, name)).data()


def _go_to(controller, raw_save, lvl, secret=0):
    raw_save["dungeon_lvl"] = lvl
    raw_save["level_track"] = secret
    controller._resolve().write_text(json.dumps(raw_save))
    controller.reload()


def _panel(qtbot, controller):
    controller.start()
    panel = FloorsPanel(controller)
    qtbot.addWidget(panel)
    panel.show()
    return panel


def test_model_rows_and_order():
    model = FloorsModel()
    assert model.rowCount() == 49
    row = model.row_of(Location(3, True))
    assert model.location_at(row) == Location(3, True)
    assert model.location_at(row - 1) == Location(3)
    assert model.row_of(Location(99)) is None


def test_model_cells():
    model = FloorsModel()
    assert _text(model, Location(3), "Secret entrance") == "50%"
    assert _text(model, Location(2), "Secret entrance") == "Yes"
    assert _text(model, Location(2), "Leads to") == "Gnomish Mines"
    assert "Sphinx's Casque" in _text(model, Location(2), "Artifacts")
    assert _text(model, Location(8), "Orb") == "green mystic orb"
    assert _text(model, Location(3, True), "Floor") == "↳ 3"
    assert _text(model, Location(3, True), "Area") == "Gnomish Mines"
    assert _text(model, Location(1), "Secret entrance") == ""


def test_note_marker_after_save(qtbot, controller):
    panel = _panel(qtbot, controller)
    assert _text(panel.model, Location(5), "Note") in ("", None)
    controller.save_floor_note(LIVE, Location(5), "x")
    assert _text(panel.model, Location(5), "Note") == "📝"


def test_current_row_bold_for_secret(qtbot, controller, raw_save):
    panel = _panel(qtbot, controller)
    _go_to(controller, raw_save, 3, 1)
    idx = panel.model.index(panel.model.row_of(Location(3, True)), 0)
    assert panel.model.data(idx, Qt.ItemDataRole.FontRole).bold()
    assert panel.model.data(idx, Qt.ItemDataRole.BackgroundRole) is not None
    other = panel.model.index(panel.model.row_of(Location(3)), 0)
    assert panel.model.data(other, Qt.ItemDataRole.FontRole) is None
    assert panel.table.currentIndex().row() == idx.row()
    assert panel.treasures.text() != ""


def test_secret_row_note_saves_separately(qtbot, controller):
    panel = _panel(qtbot, controller)
    panel.select(Location(3, True))
    QTest.keyClicks(panel.note_editor, "deep")
    controller.about_to_change.emit()
    assert controller.floor_note(LIVE, Location(3, True)) == "deep"
    assert controller.floor_note(LIVE, Location(3)) == ""
    assert "deep" not in controller.floor_note(LIVE, Location(3))


def test_main_row_without_secret_has_empty_treasures(qtbot, controller):
    panel = _panel(qtbot, controller)
    panel.select(Location(3, True))
    assert panel.treasures.text() != ""
    panel.select(Location(1))
    assert panel.treasures.text() == ""


def test_user_selection_kept_on_same_run_view_change(qtbot, controller, raw_save):
    panel = _panel(qtbot, controller)
    panel.table.selectRow(panel.model.row_of(Location(7)))
    _go_to(controller, raw_save, 1)
    assert panel.table.currentIndex().row() == panel.model.row_of(Location(7))


def test_follows_current_without_user_choice(qtbot, controller, raw_save):
    panel = _panel(qtbot, controller)
    _go_to(controller, raw_save, 4)
    assert panel.table.currentIndex().row() == panel.model.row_of(Location(4))


def test_past_run_read_only(qtbot, controller_with_two_runs, journal):
    c = controller_with_two_runs
    journal.set_floor_note(42, 0, "old")
    panel = _panel(qtbot, c)
    assert not panel.note_editor.isReadOnly()
    c.open_run(42)
    assert panel.note_editor.isReadOnly()
    assert panel.note_editor.toPlainText() == "old"


def test_empty_mode(qtbot, empty_dir_controller):
    panel = _panel(qtbot, empty_dir_controller)
    assert not panel.table.currentIndex().isValid()
    assert panel.note_editor.isReadOnly()
    idx = panel.model.index(0, 0)
    assert panel.model.data(idx, Qt.ItemDataRole.FontRole) is None
    panel.render(ViewState("empty"))


def test_external_note_change_reloads_editor(qtbot, controller):
    panel = _panel(qtbot, controller)
    panel.select(Location(0))
    controller.save_floor_note(LIVE, Location(0), "elsewhere")
    assert panel.note_editor.toPlainText() == "elsewhere"
