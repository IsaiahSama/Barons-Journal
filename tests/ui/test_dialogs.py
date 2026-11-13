from PySide6.QtCore import Qt

from barons_journal.data import load_save
from barons_journal.ui.dialogs.runs_browser import RunsBrowserDialog
from barons_journal.ui.dialogs.slot_picker import SlotPickerDialog


def _cell(table, row, col):
    return table.model().index(row, col).data(Qt.ItemDataRole.DisplayRole)


def _row_of(table, text, col=0):
    model = table.model()
    for row in range(model.rowCount()):
        if text in str(_cell(table, row, col)):
            return row
    raise AssertionError(text)


def _headers(table):
    m = table.model()
    return [m.headerData(i, Qt.Orientation.Horizontal) for i in range(m.columnCount())]


def test_runs_browser_lists_runs_and_marks_live(controller_with_two_runs, qtbot):
    c = controller_with_two_runs
    c.start()
    live = c.live_gamekey()
    dlg = RunsBrowserDialog(c)
    qtbot.addWidget(dlg)
    assert _headers(dlg.table) == [
        "Character", "Class", "Race", "Last floor", "First seen", "Last seen"
    ]
    assert dlg.table.model().rowCount() == 2
    live_row = _row_of(dlg.table, "(live)")
    assert _cell(dlg.table, live_row, 0).endswith(" (live)")
    assert c.journal.run(live).character_name in _cell(dlg.table, live_row, 0)
    other = 1 - live_row
    assert "(live)" not in _cell(dlg.table, other, 0)
    assert "Floor" in _cell(dlg.table, other, 3)
    last_seen = _cell(dlg.table, other, 5)
    assert last_seen == c.journal.run(42).last_seen.strftime("%Y-%m-%d %H:%M")


def test_open_past_run(controller_with_two_runs, qtbot):
    c = controller_with_two_runs
    c.start()
    dlg = RunsBrowserDialog(c)
    qtbot.addWidget(dlg)
    dlg.select_gamekey(42)
    dlg.open_button.click()
    assert c.view().mode == "past"
    assert dlg.result() == dlg.DialogCode.Accepted


def test_open_live_run_goes_back_to_live(controller_with_two_runs, qtbot):
    c = controller_with_two_runs
    c.start()
    c.open_run(42)
    dlg = RunsBrowserDialog(c)
    qtbot.addWidget(dlg)
    dlg.select_gamekey(c.live_gamekey())
    dlg.open_button.click()
    assert c.view().mode == "live"


def test_delete_requires_confirmation(controller_with_two_runs, qtbot):
    c = controller_with_two_runs
    c.start()
    asked = []
    answer = [False]

    def confirm(msg):
        asked.append(msg)
        return answer[0]

    dlg = RunsBrowserDialog(c, confirm=confirm)
    qtbot.addWidget(dlg)
    dlg.select_gamekey(42)
    name = c.journal.run(42).character_name
    dlg.delete_button.click()
    assert asked == [f"Delete {name}'s run and all its notes?"]
    assert c.journal.run(42) is not None
    answer[0] = True
    dlg.delete_button.click()
    assert c.journal.run(42) is None
    assert dlg.table.model().rowCount() == 1


def test_live_run_cannot_be_deleted(controller_with_two_runs, qtbot):
    c = controller_with_two_runs
    c.start()
    dlg = RunsBrowserDialog(c, confirm=lambda m: True)
    qtbot.addWidget(dlg)
    dlg.select_gamekey(c.live_gamekey())
    assert not dlg.delete_button.isEnabled()
    dlg.select_gamekey(42)
    assert dlg.delete_button.isEnabled()


def test_deleting_viewed_past_run_returns_to_live(controller_with_two_runs, qtbot):
    c = controller_with_two_runs
    c.start()
    c.open_run(42)
    dlg = RunsBrowserDialog(c, confirm=lambda m: True)
    qtbot.addWidget(dlg)
    dlg.select_gamekey(42)
    dlg.delete_button.click()
    assert c.view().mode == "live" and c.journal.run(42) is None


def test_slot_picker_rows(controller, save_dir, qtbot):
    (save_dir / "savegame3_mp.baronysave").write_text("not json")
    controller.start()
    dlg = SlotPickerDialog(controller)
    qtbot.addWidget(dlg)
    t = dlg.table
    assert _cell(t, 0, 0) == "Most recent save (automatic)"
    assert t.model().rowCount() == 3
    rows = {_cell(t, r, 0): r for r in range(1, 3)}
    good, bad = rows["0"], rows["3"]
    assert _cell(t, good, 1) == "Singleplayer"
    assert _cell(t, good, 4) == load_save(save_dir / 'savegame0.baronysave').player.name
    assert _cell(t, bad, 1) == "Multiplayer"
    assert _cell(t, bad, 4) == "unreadable"
    assert _cell(t, bad, 2) == ""
    assert dlg.table.currentIndex().row() == 0


def test_slot_picker_pins_and_unpins(controller, settings, save_dir, qtbot):
    controller.start()
    dlg = SlotPickerDialog(controller)
    qtbot.addWidget(dlg)
    dlg.select_row(1)
    dlg.choose_button.click()
    assert settings.follow == save_dir / "savegame0.baronysave"

    dlg2 = SlotPickerDialog(controller)
    qtbot.addWidget(dlg2)
    assert dlg2.table.currentIndex().row() == 1
    dlg2.select_row(0)
    dlg2.choose_button.click()
    assert settings.follow is None


def test_slot_picker_unreadable_for_bad_bytes_and_permission(controller, save_dir, qtbot, monkeypatch):
    (save_dir / "savegame3.baronysave").write_bytes(b"\xff\xfe\x00")
    controller.start()
    dlg = SlotPickerDialog(controller)
    qtbot.addWidget(dlg)
    t = dlg.table
    assert {_cell(t, r, 0): _cell(t, r, 4) for r in range(1, 3)}["3"] == "unreadable"

    import barons_journal.ui.dialogs.slot_picker as mod

    monkeypatch.setattr(mod, "load_save", lambda p: (_ for _ in ()).throw(PermissionError("x")))
    dlg2 = SlotPickerDialog(controller)
    qtbot.addWidget(dlg2)
    assert _cell(dlg2.table, 1, 4) == "unreadable"
