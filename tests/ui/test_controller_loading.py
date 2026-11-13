import json
import os
import time

from barons_journal.ui.location import Location


def _write(save_dir, raw, name="savegame0.baronysave"):
    path = save_dir / name
    path.write_text(json.dumps(raw))
    return path


def test_start_loads_latest_and_records_run(controller, journal):
    controller.start()
    v = controller.view()
    assert v.mode == "live" and v.editable and v.save.player.name == "Moonshine"
    assert journal.run(1791824898) is not None


def test_no_saves_gives_empty_view(empty_dir_controller):
    empty_dir_controller.start()
    assert empty_dir_controller.view().mode == "empty"
    assert empty_dir_controller.banner() is None


def test_file_change_reloads_after_debounce(controller, qtbot, save_dir, raw_save):
    controller.start()
    raw_save["dungeon_lvl"] = 2
    _write(save_dir, raw_save)
    qtbot.waitUntil(lambda: controller.view().location == Location(2), timeout=3000)


def test_truncated_then_good_write_recovers(controller, qtbot, save_dir, raw_save):
    controller.start()
    text = json.dumps(raw_save)
    path = save_dir / "savegame0.baronysave"
    path.write_text(text[: len(text) // 2])
    qtbot.waitUntil(
        lambda: controller.banner() is not None and controller.banner().kind == "error",
        timeout=3000,
    )
    assert controller.view().location == Location(0)
    assert controller.banner().text.startswith("Couldn't read the save:")
    raw_save["dungeon_lvl"] = 1
    _write(save_dir, raw_save)
    qtbot.waitUntil(lambda: controller.banner() is None, timeout=3000)
    assert controller.view().location == Location(1)


def test_retries_stop_after_max(controller, qtbot, save_dir, monkeypatch):
    calls = []
    original = controller.reload

    def spy():
        calls.append(1)
        original()

    controller.start()
    monkeypatch.setattr(controller, "reload", spy)
    (save_dir / "savegame0.baronysave").write_text("{ not json")
    qtbot.waitUntil(lambda: len(calls) >= 1 + controller.MAX_RETRIES, timeout=3000)
    qtbot.wait(300)
    # one change-triggered reload, then MAX_RETRIES retries
    assert len(calls) == 1 + controller.MAX_RETRIES
    assert controller.banner().kind == "error"


def test_deleted_save_marks_run_ended(controller, qtbot, save_dir):
    controller.start()
    (save_dir / "savegame0.baronysave").unlink()
    qtbot.waitUntil(lambda: controller.view().ended, timeout=3000)
    v = controller.view()
    assert v.mode == "live" and v.editable
    assert controller.banner().kind == "ended"


def test_deleted_save_does_not_fall_back_to_older_slot(
    controller, qtbot, save_dir, raw_save
):
    controller.start()
    raw_save["gamekey"] = 42
    older = _write(save_dir, raw_save, "savegame5.baronysave")
    past = time.time() - 100000
    os.utime(older, (past, past))
    (save_dir / "savegame0.baronysave").unlink()
    qtbot.waitUntil(lambda: controller.view().ended, timeout=3000)
    assert controller.view().run.gamekey == 1791824898


def test_newer_slot_in_latest_mode_switches_live(controller, qtbot, save_dir, raw_save):
    controller.start()
    raw_save["gamekey"] = 42
    path = _write(save_dir, raw_save, "savegame3.baronysave")
    future = time.time() + 1000
    os.utime(path, (future, future))
    qtbot.waitUntil(
        lambda: controller.view().run is not None and controller.view().run.gamekey == 42,
        timeout=3000,
    )
    assert controller.view().mode == "live"


def test_follow_path_pins_slot(controller, save_dir, raw_save, settings):
    controller.start()
    raw_save["gamekey"] = 42
    older = _write(save_dir, raw_save, "savegame5.baronysave")
    past = time.time() - 100000
    os.utime(older, (past, past))
    controller.follow_path(older)
    assert controller.view().run.gamekey == 42
    assert settings.follow == older
    controller.follow_latest()
    assert settings.follow is None
    assert controller.view().run.gamekey == 1791824898


def test_about_to_change_precedes_view_changed(controller):
    order = []
    controller.about_to_change.connect(lambda: order.append("about"))
    controller.view_changed.connect(lambda v: order.append("view"))
    controller.start()
    assert order == ["about", "view"]


def test_bad_bytes_save_at_start_shows_error_and_retries(controller, qtbot, save_dir):
    (save_dir / "savegame0.baronysave").write_bytes(b"\xff\xfe\x00bad")
    controller.start()  # must not raise
    assert controller.view().mode == "empty"
    banner = controller.banner()
    assert banner is not None and banner.kind == "error"
    assert banner.text.startswith("Couldn't read the save:")
    assert "last good data" not in banner.text
    assert controller._retries >= 1


def test_permission_error_is_retryable(controller, monkeypatch):
    import barons_journal.ui.controller as mod

    def locked(_path):
        raise PermissionError("locked")

    monkeypatch.setattr(mod, "load_save", locked)
    controller.start()
    assert controller.banner().kind == "error"
    assert "locked" in controller.banner().text
    assert controller._retries >= 1


def test_good_data_then_error_keeps_last_good_wording(controller, save_dir):
    controller.start()
    (save_dir / "savegame0.baronysave").write_bytes(b"\xff\xfe")
    controller.reload()
    assert controller.banner().text.endswith("Showing the last good data.")


def test_choose_folder_clears_pinned_save(controller, settings, save_dir, tmp_path):
    controller.start()
    controller.follow_path(save_dir / "savegame0.baronysave")
    other = tmp_path / "other"
    other.mkdir()
    controller.set_save_dir(other)
    assert settings.follow is None
    assert controller.view().mode == "empty"
