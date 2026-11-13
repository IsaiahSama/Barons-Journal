import json
import os
import time

import pytest

from barons_journal.journal import JournalError
from barons_journal.ui.location import Location

LIVE = 1791824898


def _write(save_dir, raw, name="savegame0.baronysave", future=False):
    path = save_dir / name
    path.write_text(json.dumps(raw))
    if future:
        t = time.time() + 1000
        os.utime(path, (t, t))
    return path


def _new_run(save_dir, raw_save, gamekey=99):
    raw_save["gamekey"] = gamekey
    return _write(save_dir, raw_save, "savegame3.baronysave", future=True)


def test_open_past_run_is_read_only(controller_with_two_runs):
    c = controller_with_two_runs
    c.start()
    c.open_run(42)
    v = c.view()
    assert v.mode == "past" and not v.editable and v.save is None
    assert v.run.gamekey == 42
    assert v.location == Location.of_run(v.run)
    assert c.banner().kind == "past"


def test_open_live_run_stays_live(controller):
    controller.start()
    controller.open_run(LIVE)
    assert controller.view().mode == "live"
    assert controller.banner() is None


def test_past_mode_writes_rejected(controller_with_two_runs):
    c = controller_with_two_runs
    c.start()
    c.open_run(42)
    with pytest.raises(JournalError, match="Past runs are read-only"):
        c.save_run_note(42, "x")
    with pytest.raises(JournalError):
        c.save_floor_note(42, Location(1), "x")
    with pytest.raises(JournalError):
        c.identify_scroll(42, "ZELGO MER", 77)
    with pytest.raises(JournalError):
        c.forget_scroll(42, "ZELGO MER")
    assert c.run_note(42) == ""


def test_new_run_while_in_past_mode_shows_banner_not_switch(
    controller_with_two_runs, qtbot, save_dir, raw_save
):
    c = controller_with_two_runs
    c.start()
    c.open_run(42)
    views = []
    c.view_changed.connect(views.append)
    _new_run(save_dir, raw_save)
    qtbot.waitUntil(lambda: c.banner().kind == "new_run", timeout=3000)
    assert c.banner().text == "New run detected."
    assert c.view().mode == "past" and views == []
    assert c.live_gamekey() == 99


def test_back_to_live_is_immediate_and_clears_banner(
    controller_with_two_runs, qtbot, save_dir, raw_save
):
    c = controller_with_two_runs
    c.start()
    c.open_run(42)
    _new_run(save_dir, raw_save)
    qtbot.waitUntil(lambda: c.banner().kind == "new_run", timeout=3000)
    order = []
    c.about_to_change.connect(lambda: order.append("about"))
    c.view_changed.connect(lambda v: order.append("view"))
    c.back_to_live()
    assert order == ["about", "view"]
    assert c.view().mode == "live" and c.view().run.gamekey == 99
    assert c.banner() is None


def test_back_to_live_with_nothing_live_is_empty(empty_dir_controller, journal, sample_save_path):
    from barons_journal.data import load_save

    journal.record_run(load_save(sample_save_path))
    c = empty_dir_controller
    c.start()
    c.open_run(LIVE)
    assert c.view().mode == "past"
    c.back_to_live()
    assert c.view().mode == "empty" and c.banner() is None


def test_floor_notes_keyed_by_location(controller):
    controller.start()
    controller.save_floor_note(LIVE, Location(3), "main")
    controller.save_floor_note(LIVE, Location(3, True), "secret")
    assert controller.floor_note(LIVE, Location(3)) == "main"
    assert controller.floor_note(LIVE, Location(3, True)) == "secret"
    assert controller.floor_notes(LIVE) == {Location(3): "main", Location(3, True): "secret"}


def test_save_run_note_roundtrip(controller):
    controller.start()
    controller.save_run_note(LIVE, "hello")
    assert controller.run_note(LIVE) == "hello"


def test_save_floor_note_emits_change(controller, qtbot):
    controller.start()
    with qtbot.waitSignal(controller.floor_note_changed) as sig:
        controller.save_floor_note(LIVE, Location(3, True), "x")
    assert sig.args == [LIVE, 3, True]


def test_identify_scroll_emits_and_errors_propagate(controller, qtbot):
    controller.start()
    with qtbot.waitSignal(controller.scrolls_changed) as sig:
        controller.identify_scroll(LIVE, "ZELGO MER", 77)
    assert sig.args == [LIVE]
    assert controller.scroll_progress(LIVE).identified["ZELGO MER"].item_id == 77
    emitted = []
    controller.scrolls_changed.connect(emitted.append)
    with pytest.raises(JournalError):
        controller.identify_scroll(LIVE, "JUYED AWK YACC", 77)
    assert emitted == []
    with qtbot.waitSignal(controller.scrolls_changed):
        controller.forget_scroll(LIVE, "ZELGO MER")
    assert "ZELGO MER" not in controller.scroll_progress(LIVE).identified


def test_delete_live_run_refused(controller):
    controller.start()
    with pytest.raises(ValueError):
        controller.delete_run(LIVE)
    assert controller.journal.run(LIVE) is not None


def test_delete_viewed_past_run_returns_to_live(controller_with_two_runs):
    c = controller_with_two_runs
    c.start()
    c.open_run(42)
    c.delete_run(42)
    assert c.journal.run(42) is None
    assert c.view().mode == "live" and c.banner() is None


def test_delete_other_run_keeps_past_view(controller_with_two_runs, journal, sample_save_path):
    import dataclasses

    from barons_journal.data import load_save

    journal.record_run(dataclasses.replace(load_save(sample_save_path), gamekey=43))
    c = controller_with_two_runs
    c.start()
    c.open_run(42)
    c.delete_run(43)
    assert c.view().mode == "past" and c.view().run.gamekey == 42


# -- fixes from the Task 4 review ----------------------------------------


def test_follow_change_to_nothing_resets_live_view(controller, tmp_path):
    controller.start()
    empty = tmp_path / "nothing"
    empty.mkdir()
    controller.set_save_dir(empty)
    assert controller.view().mode == "empty"
    assert controller.live_gamekey() is None


def test_failure_on_new_target_does_not_end_previous_run(controller, qtbot, save_dir):
    controller.start()
    bad = save_dir / "savegame7.baronysave"
    bad.write_text("{ nope")
    controller.follow_path(bad)
    qtbot.waitUntil(lambda: controller.banner() is not None, timeout=3000)
    qtbot.wait(300)
    assert controller.banner().kind == "error"
    assert controller.view().mode == "empty"
    assert controller.live_gamekey() is None


def test_failure_on_missing_new_target_never_marks_ended(controller, qtbot, save_dir):
    controller.start()
    controller.follow_path(save_dir / "savegame9.baronysave")
    qtbot.wait(300)
    assert controller.view().mode == "empty" and not controller.view().ended


def test_in_place_write_to_other_slot_reloads_in_latest_mode(
    controller, qtbot, save_dir, raw_save
):
    other = save_dir / "savegame5.baronysave"
    raw_save["gamekey"] = 77
    old = _write(save_dir, raw_save, "savegame5.baronysave")
    past = time.time() - 100000
    os.utime(old, (past, past))
    controller.start()
    assert controller.view().run.gamekey == LIVE
    raw_save["gamekey"] = 78
    with other.open("w") as f:  # in place, no directory event
        f.write(json.dumps(raw_save))
    qtbot.waitUntil(lambda: controller.view().run.gamekey == 78, timeout=3000)


def test_unloaded_pinned_target_is_watched(controller, save_dir):
    bad = save_dir / "savegame7.baronysave"
    bad.write_text("{ nope")
    controller.follow_path(bad)
    assert str(bad) in controller._watcher.files()


def test_first_load_failure_emits_empty_view(controller, qtbot, save_dir):
    bad = save_dir / "savegame7.baronysave"
    bad.write_text("{ nope")
    controller._settings.follow = bad
    views = []
    controller.view_changed.connect(views.append)
    controller.start()
    assert [v.mode for v in views] == ["empty"]
