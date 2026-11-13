from barons_journal.reference import floor_at
from barons_journal.ui.location import Location
from barons_journal.ui.panels.header import HeaderPanel
from barons_journal.ui.state import Banner, ViewState


def _panel(qtbot, controller):
    panel = HeaderPanel(controller)
    qtbot.addWidget(panel)
    return panel


def test_live_title_and_caption(qtbot, controller):
    controller.start()
    panel = _panel(qtbot, controller)
    assert panel.title.text() == (
        f"Moonshine · Human Warrior · Lv 1 · Floor 0 ({floor_at(0).area})"
    )
    assert panel.caption.text().startswith("As of floor 0, saved ")


def test_secret_level_title(qtbot, controller, secret_save):
    panel = _panel(qtbot, controller)
    panel.render(ViewState("live", None, secret_save, Location.of_save(secret_save), True))
    assert "Gnomish Mines · depth 3" in panel.title.text()


def test_empty(qtbot, empty_dir_controller):
    panel = _panel(qtbot, empty_dir_controller)
    assert panel.title.text() == "No run loaded"
    assert panel.caption.text() == ""
    assert panel.banner.isHidden()


def test_past_title_and_caption(qtbot, controller_with_two_runs):
    c = controller_with_two_runs
    c.start()
    panel = _panel(qtbot, c)
    c.open_run(42)
    run = c.view().run
    assert panel.title.text() == (
        f"{run.character_name} · {run.race_name} {run.class_name} · "
        f"{panel.title.text().split(' · ')[-1]}"
    )
    assert "Lv" not in panel.title.text()
    assert panel.caption.text() == f"Last seen {run.last_seen:%Y-%m-%d %H:%M}"
    assert not panel.banner.isHidden()
    assert panel.banner_button.text() == "Back to live run"
    assert not panel.banner_button.isHidden()


def test_banner_kinds(qtbot, controller):
    panel = _panel(qtbot, controller)
    assert panel.banner.isHidden()
    panel.show_banner(Banner("new_run", "New run detected."))
    assert not panel.banner.isHidden()
    assert panel.banner_label.text() == "New run detected."
    assert panel.banner_button.text() == "View live run"
    assert not panel.banner_button.isHidden()
    for kind in ("error", "ended"):
        panel.show_banner(Banner(kind, "msg"))
        assert panel.banner_label.text() == "msg"
        assert panel.banner_button.isHidden()
    panel.show_banner(None)
    assert panel.banner.isHidden()


def test_button_calls_back_to_live(qtbot, controller_with_two_runs):
    c = controller_with_two_runs
    c.start()
    panel = _panel(qtbot, c)
    c.open_run(42)
    panel.banner_button.click()
    assert c.view().mode == "live"
    assert panel.banner.isHidden()


def test_initial_render_uses_current_state(qtbot, controller_with_two_runs):
    c = controller_with_two_runs
    c.start()
    c.open_run(42)
    panel = _panel(qtbot, c)
    assert "Lv" not in panel.title.text()
    assert not panel.banner.isHidden()
