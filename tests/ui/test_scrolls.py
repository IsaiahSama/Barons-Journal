from barons_journal.reference import SCROLL_LABELS
from barons_journal.ui.panels.scrolls import ScrollsPanel

FIRE = 75
MAPPING = 77


def _gamekey(controller):
    return controller.view().run.gamekey


def _pick(combo, name):
    index = combo.findText(name)
    assert index > 0
    combo.setCurrentIndex(index)
    combo.activated.emit(index)


def _remaining(panel):
    return [panel.remaining_list.item(i).text() for i in range(panel.remaining_list.count())]


def _panel(qtbot, controller):
    controller.start()
    panel = ScrollsPanel(controller)
    qtbot.addWidget(panel)
    return panel


def test_one_row_per_label(qtbot, controller):
    panel = _panel(qtbot, controller)
    for label in SCROLL_LABELS:
        combo, undo = panel.row_widgets(label)
        assert combo is not None and undo is None
        assert combo.itemText(0) == "Pick…"
    assert len(SCROLL_LABELS) == 25


def test_identify_updates_row_and_remaining(qtbot, controller):
    panel = _panel(qtbot, controller)
    combo, _ = panel.row_widgets("ZELGO MER")
    _pick(combo, "scroll of fire")
    combo, undo = panel.row_widgets("ZELGO MER")
    assert combo is None and undo is not None
    assert "scroll of fire: 2 labels left" in _remaining(panel)
    assert controller.scroll_progress(_gamekey(controller)).identified["ZELGO MER"].item_id == FIRE


def test_undo_restores_picker(qtbot, controller):
    panel = _panel(qtbot, controller)
    _pick(panel.row_widgets("ZELGO MER")[0], "scroll of fire")
    panel.row_widgets("ZELGO MER")[1].click()
    combo, undo = panel.row_widgets("ZELGO MER")
    assert combo is not None and undo is None
    assert "scroll of fire: 3 labels left" in _remaining(panel)


def test_singular_label_text(qtbot, controller):
    panel = _panel(qtbot, controller)
    assert "scroll of magic mapping: 1 label left" in _remaining(panel)


def test_error_shown_and_journal_unchanged(qtbot, controller, journal):
    panel = _panel(qtbot, controller)
    gk = _gamekey(controller)
    journal.identify_scroll(gk, "ZELGO MER", MAPPING)  # behind the panel's back
    combo, _ = panel.row_widgets("NR 9")
    assert combo.findText("scroll of magic mapping") > 0
    _pick(combo, "scroll of magic mapping")
    assert not panel.error_label.isHidden()
    assert panel.error_label.text()
    assert set(journal.scroll_progress(gk).identified) == {"ZELGO MER"}
    assert panel.row_widgets("NR 9")[0] is not None


def test_error_cleared_on_success(qtbot, controller, journal):
    panel = _panel(qtbot, controller)
    journal.identify_scroll(_gamekey(controller), "ZELGO MER", MAPPING)
    _pick(panel.row_widgets("NR 9")[0], "scroll of magic mapping")
    _pick(panel.row_widgets("NR 9")[0], "scroll of fire")
    assert panel.error_label.isHidden()


def test_past_mode_is_read_only(qtbot, controller_with_two_runs):
    c = controller_with_two_runs
    c.start()
    panel = ScrollsPanel(c)
    qtbot.addWidget(panel)
    c.open_run(42)
    combo, _ = panel.row_widgets(SCROLL_LABELS[0])
    assert not combo.isEnabled()
    c.back_to_live()
    assert panel.row_widgets(SCROLL_LABELS[0])[0].isEnabled()


def test_past_mode_undo_disabled(qtbot, controller_with_two_runs, journal):
    c = controller_with_two_runs
    c.start()
    journal.identify_scroll(42, "ZELGO MER", FIRE)
    panel = ScrollsPanel(c)
    qtbot.addWidget(panel)
    c.open_run(42)
    combo, undo = panel.row_widgets("ZELGO MER")
    assert combo is None and not undo.isEnabled()


def test_empty_mode(qtbot, empty_dir_controller):
    c = empty_dir_controller
    c.start()
    panel = ScrollsPanel(c)
    qtbot.addWidget(panel)
    assert panel.empty_label.text() == "No run loaded"
    assert not panel.empty_label.isHidden()
    assert panel.remaining_list.count() == 0
    assert panel.row_widgets(SCROLL_LABELS[0]) == (None, None)
