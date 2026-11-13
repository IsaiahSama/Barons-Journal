"""Tests for the SQLite-backed journal: scroll identifications and notes."""

import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from barons_journal.journal import Journal, JournalError, default_journal_path
from barons_journal.reference import scroll_by_item_id

RUN = 1791824898
OTHER_RUN = 42


@pytest.fixture
def journal():
    with Journal(":memory:") as j:
        yield j


# --- Scroll identifications ---------------------------------------------------


class TestScrolls:
    def test_new_run_has_no_identifications(self, journal):
        assert journal.scroll_identifications(RUN) == {}

    def test_identify_and_read_back(self, journal):
        journal.identify_scroll(RUN, "ZELGO MER", 75)
        assert journal.scroll_identifications(RUN) == {"ZELGO MER": 75}

    def test_identifications_are_per_run(self, journal):
        journal.identify_scroll(RUN, "ZELGO MER", 75)
        journal.identify_scroll(OTHER_RUN, "ZELGO MER", 69)
        assert journal.scroll_identifications(RUN) == {"ZELGO MER": 75}
        assert journal.scroll_identifications(OTHER_RUN) == {"ZELGO MER": 69}

    def test_reidentifying_a_label_replaces_it(self, journal):
        journal.identify_scroll(RUN, "ZELGO MER", 75)
        journal.identify_scroll(RUN, "ZELGO MER", 77)
        assert journal.scroll_identifications(RUN) == {"ZELGO MER": 77}

    def test_forget_scroll(self, journal):
        journal.identify_scroll(RUN, "ZELGO MER", 75)
        journal.forget_scroll(RUN, "ZELGO MER")
        assert journal.scroll_identifications(RUN) == {}

    def test_forget_unknown_label_is_a_no_op(self, journal):
        journal.forget_scroll(RUN, "ZELGO MER")

    def test_scroll_progress(self, journal):
        journal.identify_scroll(RUN, "ZELGO MER", 75)
        progress = journal.scroll_progress(RUN)
        assert progress.identified == {"ZELGO MER": scroll_by_item_id(75)}

    def test_rejects_unknown_label(self, journal):
        with pytest.raises(JournalError, match="label"):
            journal.identify_scroll(RUN, "NOT A LABEL", 75)

    def test_rejects_non_scroll_item(self, journal):
        with pytest.raises(JournalError, match="scroll"):
            journal.identify_scroll(RUN, "ZELGO MER", 7)

    def test_rejects_more_labels_than_the_scroll_has(self, journal):
        journal.identify_scroll(RUN, "ZELGO MER", 77)  # magic mapping: 1 label
        with pytest.raises(JournalError, match="scroll of magic mapping"):
            journal.identify_scroll(RUN, "THARR", 77)
        assert journal.scroll_identifications(RUN) == {"ZELGO MER": 77}

    def test_reidentifying_same_label_does_not_count_twice(self, journal):
        journal.identify_scroll(RUN, "ZELGO MER", 77)
        journal.identify_scroll(RUN, "ZELGO MER", 77)
        assert journal.scroll_identifications(RUN) == {"ZELGO MER": 77}

    def test_moving_the_only_label_of_a_scroll_is_allowed_after_forgetting(self, journal):
        journal.identify_scroll(RUN, "ZELGO MER", 77)
        journal.forget_scroll(RUN, "ZELGO MER")
        journal.identify_scroll(RUN, "THARR", 77)
        assert journal.scroll_identifications(RUN) == {"THARR": 77}


# --- Notes --------------------------------------------------------------------


class TestRunNotes:
    def test_missing_note_is_empty(self, journal):
        assert journal.run_note(RUN) == ""

    def test_set_and_get(self, journal):
        journal.set_run_note(RUN, "Shopkeeper on 3 sells rings")
        assert journal.run_note(RUN) == "Shopkeeper on 3 sells rings"

    def test_overwrite(self, journal):
        journal.set_run_note(RUN, "first")
        journal.set_run_note(RUN, "second")
        assert journal.run_note(RUN) == "second"

    def test_per_run(self, journal):
        journal.set_run_note(RUN, "mine")
        assert journal.run_note(OTHER_RUN) == ""

    def test_empty_note_deletes(self, journal):
        journal.set_run_note(RUN, "temp")
        journal.set_run_note(RUN, "")
        assert journal.run_note(RUN) == ""
        assert journal.runs() == []

    def test_unicode_and_newlines_round_trip(self, journal):
        text = "Line 1\nLine 2 — ünïcode ✓"
        journal.set_run_note(RUN, text)
        assert journal.run_note(RUN) == text


class TestFloorNotes:
    def test_missing_note_is_empty(self, journal):
        assert journal.floor_note(RUN, 3) == ""

    def test_set_and_get(self, journal):
        journal.set_floor_note(RUN, 3, "Secret entrance behind the fountain")
        assert journal.floor_note(RUN, 3) == "Secret entrance behind the fountain"

    def test_per_floor_and_per_run(self, journal):
        journal.set_floor_note(RUN, 3, "three")
        assert journal.floor_note(RUN, 4) == ""
        assert journal.floor_note(OTHER_RUN, 3) == ""

    def test_floor_notes_for_run_in_floor_order(self, journal):
        journal.set_floor_note(RUN, 5, "five")
        journal.set_floor_note(RUN, 1, "one")
        journal.set_floor_note(OTHER_RUN, 2, "other")
        assert journal.floor_notes(RUN) == {1: "one", 5: "five"}

    def test_empty_note_deletes(self, journal):
        journal.set_floor_note(RUN, 3, "temp")
        journal.set_floor_note(RUN, 3, "")
        assert journal.floor_notes(RUN) == {}


class TestRuns:
    def test_runs_lists_every_run_with_any_data(self, journal):
        journal.set_run_note(RUN, "note")
        journal.set_floor_note(OTHER_RUN, 1, "floor")
        journal.identify_scroll(7, "ZELGO MER", 75)
        assert journal.runs() == [7, OTHER_RUN, RUN]

    def test_no_runs(self, journal):
        assert journal.runs() == []


# --- Persistence and schema ---------------------------------------------------


class TestPersistence:
    def test_data_survives_reopening(self, tmp_path):
        path = tmp_path / "journal.sqlite3"
        with Journal(path) as j:
            j.identify_scroll(RUN, "ZELGO MER", 75)
            j.set_run_note(RUN, "run")
            j.set_floor_note(RUN, 2, "floor")
        with Journal(path) as j:
            assert j.scroll_identifications(RUN) == {"ZELGO MER": 75}
            assert j.run_note(RUN) == "run"
            assert j.floor_note(RUN, 2) == "floor"

    def test_creates_parent_directories(self, tmp_path):
        path = tmp_path / "nested" / "dir" / "journal.sqlite3"
        with Journal(path):
            pass
        assert path.exists()

    def test_newer_schema_is_refused(self, tmp_path):
        path = tmp_path / "journal.sqlite3"
        with closing(sqlite3.connect(path)) as conn:  # sqlite3's own `with` doesn't close
            conn.execute("PRAGMA user_version = 999")
        with pytest.raises(JournalError, match="newer"):
            Journal(path)

    def test_failed_write_leaves_data_unchanged(self, journal):
        journal.identify_scroll(RUN, "ZELGO MER", 77)
        with pytest.raises(JournalError):
            journal.identify_scroll(RUN, "THARR", 77)
        assert journal.runs() == [RUN]
        assert journal.scroll_identifications(RUN) == {"ZELGO MER": 77}


class TestDefaultPath:
    def test_linux_uses_xdg_data_home(self, monkeypatch, tmp_path):
        monkeypatch.setattr("sys.platform", "linux")
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
        assert default_journal_path() == tmp_path / "barons-journal" / "journal.sqlite3"

    def test_linux_falls_back_to_local_share(self, monkeypatch):
        monkeypatch.setattr("sys.platform", "linux")
        monkeypatch.delenv("XDG_DATA_HOME", raising=False)
        expected = Path.home() / ".local/share/barons-journal/journal.sqlite3"
        assert default_journal_path() == expected

    def test_windows_uses_appdata(self, monkeypatch, tmp_path):
        monkeypatch.setattr("sys.platform", "win32")
        monkeypatch.setenv("APPDATA", str(tmp_path))
        assert default_journal_path() == tmp_path / "barons-journal" / "journal.sqlite3"

    def test_macos_uses_application_support(self, monkeypatch):
        monkeypatch.setattr("sys.platform", "darwin")
        expected = Path.home() / "Library/Application Support/barons-journal/journal.sqlite3"
        assert default_journal_path() == expected
