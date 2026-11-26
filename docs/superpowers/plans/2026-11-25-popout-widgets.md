# Pop-out Widgets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Five always-on-top, floating, resizable widget windows (Vitals, Attributes, Skills, Floor note, Current floor), toggled from View → Widgets and remembered between launches.

**Architecture:** Each widget is a small content view that listens to `SessionController.view_changed` like the existing panels do, wrapped in a parentless `PopoutWindow` (`Qt.Dialog | Qt.WindowStaysOnTopHint`). A `PopoutManager` owns the windows, syncs the menu, and saves open state and geometry in `AppSettings`. `run()` switches the app to XWayland on Wayland so stay-on-top works on COSMIC.

**Tech Stack:** Python 3.13, PySide6 6.12, pytest + pytest-qt (offscreen platform).

**Spec:** `docs/superpowers/specs/2026-11-25-popout-widgets-design.md`

## Global Constraints

- Only `src/barons_journal/ui/` imports Qt.
- Every `Journal` / controller note call stays on the main thread (it does; everything here is signal-driven).
- Widget window flags: exactly `Qt.WindowType.Dialog | Qt.WindowType.WindowStaysOnTopHint`, no parent (measured: `Tool` gets tiled on COSMIC; `Dialog` floats).
- Platform: `os.environ.setdefault("QT_QPA_PLATFORM", "xcb")` only on Linux with `WAYLAND_DISPLAY` set, before `QApplication` exists.
- Widget keys and titles, in menu order: `vitals` "Vitals", `attributes` "Attributes", `skills` "Skills", `floor_note` "Floor note", `current_floor` "Current floor". Window title: `f"{title} · Baron's Journal"`.
- Not-live messages reuse `StatsPanel` (`PAST_MESSAGE`, `EMPTY_MESSAGE` in `panels/_stats.py`).
- Styling via existing object names only: HP/MP bars keep `objectName` `hpBar` / `mpBar`.
- Run tests with `uv run pytest`; the whole suite must pass at the end of every task.

## Review Focus

1. **Typing in the floor-note widget when the save reloads on the same floor** must not wipe or reload the text under the cursor: rebind only when `(gamekey, location, editable)` changes. Test in Task 4.
2. **Closing a widget window with unsaved note text** (no focus-out first) must save it. Test in Task 4 (`hideEvent` flush).
3. **Quitting with widgets open** must reopen them next launch, and must not record them as closed. Test in Task 5.
4. **Closing a widget via its title-bar X** must uncheck its menu item and record it as closed. Test in Task 5.
5. **Being on a secret level** must show the secret-level row in Current floor, not the main floor's. Test in Task 4.

---

### Task 1: Prefer XWayland on Wayland

**Files:**
- Modify: `src/barons_journal/ui/__init__.py`
- Test: `tests/ui/test_platform.py` (create)

**Interfaces:**
- Produces: `prefer_xwayland(environ: MutableMapping[str, str], platform: str) -> None` in `barons_journal.ui`; `run()` calls `prefer_xwayland(os.environ, sys.platform)` as its first line.

- [ ] **Step 1: Write the failing tests**

```python
from barons_journal.ui import prefer_xwayland

def test_wayland_linux_gets_xcb():
    env = {"WAYLAND_DISPLAY": "wayland-1"}
    prefer_xwayland(env, "linux")
    assert env["QT_QPA_PLATFORM"] == "xcb"

def test_explicit_platform_kept():
    env = {"WAYLAND_DISPLAY": "wayland-1", "QT_QPA_PLATFORM": "offscreen"}
    prefer_xwayland(env, "linux")
    assert env["QT_QPA_PLATFORM"] == "offscreen"

def test_x11_session_untouched():
    env = {"DISPLAY": ":0"}
    prefer_xwayland(env, "linux")
    assert "QT_QPA_PLATFORM" not in env

def test_other_os_untouched():
    env = {"WAYLAND_DISPLAY": "wayland-1"}
    prefer_xwayland(env, "win32")
    assert "QT_QPA_PLATFORM" not in env
```

- [ ] **Step 2: Run `uv run pytest tests/ui/test_platform.py -v`** — expect ImportError.
- [ ] **Step 3: Implement `prefer_xwayland`** (one-line docstring with the why: native Wayland lets no app stay on top) and call it at the top of `run()`.
- [ ] **Step 4: Run `uv run pytest tests/ui/test_platform.py -v`** — expect 4 passed.
- [ ] **Step 5: Commit** `git add src/barons_journal/ui/__init__.py tests/ui/test_platform.py && git commit -m "Run under XWayland on Wayland so windows can stay on top"`

---

### Task 2: Pop-out settings

**Files:**
- Modify: `src/barons_journal/ui/settings.py`
- Test: `tests/ui/test_settings.py`

**Interfaces:**
- Produces on `AppSettings`:
  - `popout_open(key: str) -> bool` (default `False`), `set_popout_open(key: str, value: bool) -> None` — QSettings key `popouts/<key>/open`.
  - `popout_geometry(key: str) -> QByteArray | None` (None when missing/empty, same rule as `geometry`), `set_popout_geometry(key: str, value: QByteArray) -> None` — key `popouts/<key>/geometry`.

- [ ] **Step 1: Write the failing tests** (use the `settings` fixture; reopen with `AppSettings(same path)` to prove persistence)

```python
def test_popout_open_defaults_false_and_persists(settings, tmp_path):
    assert settings.popout_open("vitals") is False
    settings.set_popout_open("vitals", True)
    assert AppSettings(tmp_path / "settings.ini").popout_open("vitals") is True
    assert settings.popout_open("skills") is False

def test_popout_geometry_round_trip(settings, tmp_path):
    assert settings.popout_geometry("vitals") is None
    settings.set_popout_geometry("vitals", QByteArray(b"abc"))
    assert AppSettings(tmp_path / "settings.ini").popout_geometry("vitals") == QByteArray(b"abc")
```

- [ ] **Step 2: Run** `uv run pytest tests/ui/test_settings.py -v` — expect AttributeError.
- [ ] **Step 3: Implement** the four methods using the existing `_bool` helper and the `geometry` property's validity rule.
- [ ] **Step 4: Run** the same command — expect pass.
- [ ] **Step 5: Commit** `"Store pop-out widget open state and geometry"`

---

### Task 3: Vitals, Attributes and Skills views

**Files:**
- Modify: `src/barons_journal/ui/panels/character.py`
- Create: `src/barons_journal/ui/popouts/__init__.py` (empty docstring module), `src/barons_journal/ui/popouts/views.py`
- Test: `tests/ui/test_popouts.py` (create)

**Interfaces:**
- Produces in `panels/character.py` (rename the private helpers so both modules share them; `CharacterPanel` uses them, behaviour unchanged):
  - `make_table(columns: int, rows: int) -> QTableWidget` (was `_table`)
  - `fill_table(table: QTableWidget, rows: tuple[tuple[str, object], ...]) -> None` (was `CharacterPanel._fill`)
  - `make_bars() -> tuple[QProgressBar, QProgressBar]` — HP and MP bars with object names `hpBar`/`mpBar`, format `"%v/%m"`
  - `set_bars(hp: QProgressBar, mp: QProgressBar, stats: Stats) -> None`
  - `attribute_rows(stats: Stats) -> tuple[tuple[str, int], ...]` — STR, DEX, CON, INT, PER, CHR in that order
  - `skill_rows(stats: Stats) -> tuple[tuple[str, int], ...]` — `tuple(stats.proficiencies_by_name.items())`
- Produces in `popouts/views.py`, all `StatsPanel` subclasses taking `(controller, parent=None)`:
  - `VitalsView`: attributes `hp_bar`, `mp_bar`, `gold_label`, `hunger_label` (`QFormLayout`: HP, MP, Gold, Hunger)
  - `AttributesView`: attribute `table` (2 columns)
  - `SkillsView`: attribute `table` (2 columns)

- [ ] **Step 1: Write the failing tests** (reuse the `_live` helper pattern from `tests/ui/test_stats_panels.py`; sample save values: HP 30/30, MP 20/20, gold 0, hunger 1000, 16 skills, STR 1)

```python
def test_vitals_live(qtbot, controller, sample_save_path):
    v = VitalsView(controller); qtbot.addWidget(v)
    v.render(_live(load_save(sample_save_path)))
    assert (v.hp_bar.value(), v.hp_bar.maximum()) == (30, 30)
    assert (v.mp_bar.value(), v.mp_bar.maximum()) == (20, 20)
    assert v.hp_bar.objectName() == "hpBar" and v.mp_bar.objectName() == "mpBar"
    assert v.gold_label.text() == "0" and v.hunger_label.text() == "1000"

def test_attributes_live(...):  # table.rowCount() == 6; item(0,0) "STR", item(0,1) "1"
def test_skills_live(...):      # table.rowCount() == 16

@pytest.mark.parametrize("cls", [VitalsView, AttributesView, SkillsView])
def test_not_live_shows_message(qtbot, controller, cls):
    v = cls(controller); qtbot.addWidget(v)
    v.render(ViewState("past"))
    assert v.message.text() == PAST_MESSAGE
    v.render(ViewState("empty"))
    assert v.message.text() == EMPTY_MESSAGE
```

- [ ] **Step 2: Run** `uv run pytest tests/ui/test_popouts.py -v` — expect ImportError.
- [ ] **Step 3: Refactor `character.py`** to the shared helpers above, then implement the three views with them.
- [ ] **Step 4: Run** `uv run pytest tests/ui -v` — expect all pass (existing `test_stats_panels.py` proves `CharacterPanel` unchanged).
- [ ] **Step 5: Commit** `"Add Vitals, Attributes and Skills pop-out views"`

---

### Task 4: Floor note and Current floor views

**Files:**
- Modify: `src/barons_journal/ui/popouts/views.py`
- Test: `tests/ui/test_popouts.py`

**Interfaces:**
- Consumes: `NoteEditor.bind/flush/reload_if_unfocused`, `controller.floor_note`, `controller.save_floor_note`, `controller.floor_note_changed`, `controller.about_to_change`, `location_label`, `FloorsModel` (`row_of`, `set_state`, `COLUMNS`).
- Produces:
  - `FloorNoteView(controller, parent=None)`: attributes `title: QLabel` (role `section`; text `location_label(view.location)`, or `"Floor note"` with no run), `editor: NoteEditor`; method `flush() -> None`. Rebinds only when `(run.gamekey, view.location, view.editable)` changes; unbinds (`bind(None, None, read_only=True)`) when there's no run or location. Connects `about_to_change → flush`, `floor_note_changed → reload_if_unfocused` when the signal matches the bound `(gamekey, location)`. Overrides `hideEvent` to call `flush()`.
  - `CurrentFloorView(controller, parent=None)`: attributes `model: FloorsModel`, `table: QTableView`. The `"Note"` column is hidden; every row is hidden except `model.row_of(view.location)`; all rows hidden when there's no run or location. Calls `model.set_state(set(), location)`.

- [ ] **Step 1: Write the failing tests** (`LIVE = 1791824898`; start the controller so the view is live; the sample save is on `Location(0)`; `secret_save` fixture is on a secret level)

```python
def test_floor_note_saves_and_syncs(qtbot, controller):
    controller.start()
    v = FloorNoteView(controller); qtbot.addWidget(v); v.show()
    assert v.title.text() == location_label(Location(0))
    v.editor.setFocus(); QTest.keyClicks(v.editor, "lever")
    v.flush()
    assert controller.floor_note(LIVE, Location(0)) == "lever"
    v.editor.clearFocus()
    controller.save_floor_note(LIVE, Location(0), "edited elsewhere")
    assert v.editor.toPlainText() == "edited elsewhere"

def test_floor_note_same_floor_reload_keeps_typing(qtbot, controller, monkeypatch):
    monkeypatch.setattr(NoteEditor, "IDLE_MS", 600_000)
    controller.start()
    v = FloorNoteView(controller); qtbot.addWidget(v); v.show()
    v.editor.setFocus(); QTest.keyClicks(v.editor, "half typed")
    v._on_view(controller.view())  # same run, floor, editable
    assert v.editor.toPlainText() == "half typed"

def test_floor_note_saved_when_hidden(qtbot, controller, monkeypatch):
    monkeypatch.setattr(NoteEditor, "IDLE_MS", 600_000)
    controller.start()
    v = FloorNoteView(controller); qtbot.addWidget(v); v.show()
    v.editor.setFocus(); QTest.keyClicks(v.editor, "bye")
    v.hide()
    assert controller.floor_note(LIVE, Location(0)) == "bye"

def test_floor_note_read_only_when_not_live(qtbot, controller):
    v = FloorNoteView(controller); qtbot.addWidget(v)
    v._on_view(ViewState("empty"))
    assert v.editor.isReadOnly() and v.title.text() == "Floor note"

def test_current_floor_shows_only_current_row(qtbot, controller):
    controller.start()
    v = CurrentFloorView(controller); qtbot.addWidget(v)
    visible = [r for r in range(v.model.rowCount()) if not v.table.isRowHidden(r)]
    assert visible == [v.model.row_of(Location(0))]
    assert v.table.isColumnHidden(v.model.COLUMNS.index("Note"))

def test_current_floor_secret_level(qtbot, controller, journal, secret_save):
    journal.record_run(secret_save)
    run = journal.run(secret_save.gamekey)
    v = CurrentFloorView(controller); qtbot.addWidget(v)
    loc = Location.of_save(secret_save)
    v._on_view(ViewState("live", run=run, save=secret_save, location=loc, editable=True))
    visible = [r for r in range(v.model.rowCount()) if not v.table.isRowHidden(r)]
    assert visible == [v.model.row_of(loc)] and loc.secret
```

Name the view slot `_on_view(view: ViewState)` in both classes, connected to `view_changed` and called once from `__init__` with `controller.view()`.

- [ ] **Step 2: Run** `uv run pytest tests/ui/test_popouts.py -v` — expect ImportError on the new classes.
- [ ] **Step 3: Implement** both views.
- [ ] **Step 4: Run** `uv run pytest tests/ui -v` — expect all pass.
- [ ] **Step 5: Commit** `"Add Floor note and Current floor pop-out views"`

---

### Task 5: Pop-out windows, manager, menu, shutdown

**Files:**
- Create: `src/barons_journal/ui/popouts/manager.py`
- Modify: `src/barons_journal/ui/main_window.py`, `src/barons_journal/ui/__init__.py`, `CLAUDE.md` (UI section: one bullet for `popouts/` and one line on XWayland/COSMIC limits)
- Test: `tests/ui/test_popouts.py`, `tests/ui/test_main_window.py`

**Interfaces:**
- Consumes: the five views (Tasks 3–4), `AppSettings` pop-out methods (Task 2).
- Produces in `popouts/manager.py`:
  - `POPOUTS: tuple[tuple[str, str], ...]` — the keys and titles from Global Constraints, in order.
  - `PopoutWindow(QWidget)`: `__init__(key: str, title: str, content: QWidget)`; flags per Global Constraints; attributes `key`, `content`; signal `closed = Signal(str)` emitted from `closeEvent`.
  - `PopoutManager(QObject)`: `__init__(controller, settings)`; signal `open_changed = Signal(str, bool)`; `set_open(key: str, on: bool) -> None`; `is_open(key: str) -> bool`; `window(key: str) -> PopoutWindow | None`; `restore() -> None` (opens every key whose `popout_open` is True); `shutdown() -> None` (for each open window: save geometry, leave `popout_open` True, close it).
  - Windows are created on first open (restoring `popout_geometry` if present) and reused afterwards. Closing a window by the user (not via `shutdown`) saves geometry, sets `popout_open(key, False)` and emits `open_changed(key, False)`. `set_open(key, True)` sets `popout_open` True, shows the window and emits `open_changed(key, True)`.
- `MainWindow`: attribute `popouts: PopoutManager`; View → "Widgets" submenu with checkable actions `actions[f"popout_{key}"]` (text = title); action `toggled → popouts.set_open`; `open_changed → action.setChecked` with the action's signals blocked; `closeEvent` calls `self.popouts.shutdown()` after `panels.flush_notes()`.
- `run()`: call `window.popouts.restore()` after the main window is shown.

- [ ] **Step 1: Write the failing tests**

```python
# tests/ui/test_popouts.py
def test_popout_window_flags(qtbot, controller):
    w = PopoutWindow("vitals", "Vitals", VitalsView(controller)); qtbot.addWidget(w)
    assert w.windowFlags() & Qt.WindowType.WindowStaysOnTopHint
    assert w.windowType() == Qt.WindowType.Dialog
    assert w.parent() is None and w.windowTitle() == "Vitals · Baron's Journal"

# tests/ui/test_main_window.py  (window fixture)
def test_widget_menu_lists_popouts_in_order(window):
    assert [k for k, _ in POPOUTS] == ["vitals", "attributes", "skills", "floor_note", "current_floor"]
    assert all(f"popout_{k}" in window.actions for k, _ in POPOUTS)

def test_toggle_opens_and_records(window, settings):
    window.actions["popout_vitals"].setChecked(True)
    assert window.popouts.window("vitals").isVisible()
    assert settings.popout_open("vitals") is True
    window.actions["popout_vitals"].setChecked(False)
    assert not window.popouts.window("vitals").isVisible()
    assert settings.popout_open("vitals") is False

def test_closing_widget_unchecks_menu(window, settings):
    window.actions["popout_skills"].setChecked(True)
    window.popouts.window("skills").close()
    assert not window.actions["popout_skills"].isChecked()
    assert settings.popout_open("skills") is False
    assert settings.popout_geometry("skills") is not None

def test_quit_keeps_widgets_open_for_next_launch(window, settings, controller, qtbot):
    window.actions["popout_vitals"].setChecked(True)
    window.close()
    assert not window.popouts.window("vitals").isVisible()
    assert settings.popout_open("vitals") is True
    w2 = MainWindow(controller, settings); qtbot.addWidget(w2)
    w2.popouts.restore()
    assert w2.popouts.window("vitals").isVisible()
    assert w2.actions["popout_vitals"].isChecked()

def test_quit_flushes_floor_note_widget(window, controller, monkeypatch):
    monkeypatch.setattr(NoteEditor, "IDLE_MS", 600_000)
    window.actions["popout_floor_note"].setChecked(True)
    editor = window.popouts.window("floor_note").content.editor
    editor.setFocus(); QTest.keyClicks(editor, "from widget")
    window.close()
    assert "from widget" in controller.floor_notes(LIVE).values()
```

- [ ] **Step 2: Run** `uv run pytest tests/ui/test_popouts.py tests/ui/test_main_window.py -v` — expect ImportError/KeyError.
- [ ] **Step 3: Implement** `PopoutWindow`, `PopoutManager`, the menu wiring, `closeEvent` call and `run()` restore. Update `CLAUDE.md`.
- [ ] **Step 4: Run** `uv run pytest` — expect the whole suite to pass.
- [ ] **Step 5: Manual check** `uv run barons-journal` on COSMIC: open each widget from View → Widgets, check it floats, stays above another window and resizes, then quit and relaunch and check the same widgets reopen at their saved size.
- [ ] **Step 6: Commit** `"Add pop-out widget windows with View > Widgets menu"`
