# Map Widget Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A see-through, always-on-top "Map" pop-out that the user lays over Barony's in-game map and drops marker icons on.

**Architecture:** A `MapCanvas` widget holds markers in memory (fractions of its size) and paints them from bundled SVGs. A `MapView` puts a draggable button strip and a size grip around it and clears the markers when the floor changes. It is registered as a sixth pop-out in the existing `PopoutManager`, whose `PopoutWindow` gains a frameless and translucent mode.

**Tech Stack:** Python 3.13, PySide6 (QtWidgets, QtSvg), pytest-qt on the offscreen platform.

**Spec:** `docs/superpowers/specs/2026-11-25-map-widget-design.md`

## Global Constraints

- Markers are not saved anywhere: in memory only, cleared when `ViewState.location` changes.
- 7 marker kinds, in this order: Weapon (sword), Armour (helmet), Item (star), Key (key), Door (padlocked door), Strong enemy (skull and crossbones), Chest (chest).
- No new dependencies. Icons are SVG files rendered with `QtSvg`.
- Only `ui` imports Qt. Panels take colours from the palette or stylesheet and never hard-code them.
- Run the tests with `uv run pytest` from the worktree `/home/lenova/Code/Apps/Barons-Journal-map`.

## Review Focus

1. Clicks or drags at or past the edge: positions are clamped to 0..1 so markers never vanish off the canvas (test in Task 1).
2. Overlapping markers: right-click and drag act on the topmost one, which is the last placed (test in Task 1).
3. Windows layered windows let clicks fall through fully transparent pixels: the canvas fills itself with alpha 1/255 so clicks still land (code in Task 1; checked manually in Task 3).
4. One click places one marker: the armed kind disarms after placing, so stray clicks don't scatter icons (test in Task 2).
5. Re-rendering the same floor (the save is rewritten, or a note changes) must not wipe the markers (test in Task 2).

---

### Task 1: Marker icons and `MapCanvas`

**Files:**
- Create: `src/barons_journal/ui/popouts/icons/{weapon,armour,item,key,door,boss,chest}.svg`
- Create: `src/barons_journal/ui/popouts/map.py`
- Test: `tests/ui/test_map.py`

**Interfaces:**
- Produces, all in `ui/popouts/map.py`:
  - `MARKER_KINDS: tuple[tuple[str, str], ...] = (("weapon", "Weapon"), ("armour", "Armour"), ("item", "Item"), ("key", "Key"), ("door", "Door"), ("boss", "Strong enemy"), ("chest", "Chest"))`
  - `MARKER_SIZE = 24` (pixels, square)
  - `icon_path(kind: str) -> Traversable`, using `importlib.resources.files(__package__) / "icons" / f"{kind}.svg"`, as `reference/*.py` loads its JSON
  - `@dataclass class Marker: kind: str; x: float; y: float` (x and y are fractions of the canvas, 0..1)
  - `class MapCanvas(QWidget)`: `markers: list[Marker]`, `kind: str | None` (the armed kind), `placed = Signal()`, `marker_center(i: int) -> QPoint`, `marker_at(pos: QPoint) -> int | None` (topmost hit, so search from the end), `clear() -> None`

- [ ] **Step 1: Draw the 7 SVGs.** Simple filled shapes, a 24×24 viewBox, a light fill with a dark outline so they read on any map. Door = an arched door with a padlock. Boss = skull and crossbones.

- [ ] **Step 2: Write the failing tests** in `tests/ui/test_map.py`. Each one builds `c = MapCanvas(); qtbot.addWidget(c); c.resize(200, 100)`.

```python
def test_icons_are_valid_svgs():
    for kind, _ in MARKER_KINDS:
        assert QSvgRenderer(str(icon_path(kind))).isValid(), kind

def test_click_places_armed_kind(qtbot):        # c.kind = "key"; left click at (50, 25)
    assert c.markers == [Marker("key", 0.25, 0.25)]
    # placed emitted once (qtbot.waitSignal or a counter)

def test_click_unarmed_does_nothing(qtbot):     # kind None, click → markers == []

def test_markers_scale_with_resize(qtbot):      # place at (50, 25), then c.resize(400, 200)
    assert c.marker_center(0) == QPoint(100, 50)

def test_right_click_removes_topmost(qtbot):    # two markers at the same spot, right click there
    assert [m.kind for m in c.markers] == ["key"]   # placed "key" first, then "chest"

def test_drag_moves_marker_and_clamps(qtbot):   # place at (50, 25); kind None;
    # QTest.mousePress (50, 25), mouseMove (150, 75), mouseRelease (150, 75) → (0.75, 0.75)
    # then a drag to (300, -20) → (1.0, 0.0)

def test_press_on_marker_while_armed_drags_not_places(qtbot):  # len(markers) stays 1

def test_clear(qtbot):                          # markers == [] after clear()
```

- [ ] **Step 3: Run them and check they fail.** Run `uv run pytest tests/ui/test_map.py -v`. Expected: an ImportError on `barons_journal.ui.popouts.map`.

- [ ] **Step 4: Implement `MapCanvas`.**
  - Left press on a marker starts a drag (store its index). Otherwise, if armed, append a marker at the clamped fraction, emit `placed`, and `update()`.
  - Move: while a drag index is set, move that marker (clamped). Track the drag by the stored index, not `event.buttons()`, because `QTest.mouseMove` sends no buttons. Release clears the index.
  - Right press on a marker removes it.
  - `paintEvent`: fill `rect()` with `QColor(0, 0, 0, 1)` (comment: Windows layered windows let clicks through alpha-0 pixels). Draw a 2 px border in `palette().color(QPalette.ColorRole.BrightText)` (the theme sets it to gold). Render each marker with a cached `QSvgRenderer` per kind into a `MARKER_SIZE` square centred on `marker_center(i)`.
  - Set `setMinimumSize(80, 60)`.

- [ ] **Step 5: Run the tests and check they pass.** Run `uv run pytest tests/ui/test_map.py -v`. Expected: all PASS.

- [ ] **Step 6: Commit.**

```bash
git add src/barons_journal/ui/popouts/icons src/barons_journal/ui/popouts/map.py tests/ui/test_map.py
git commit -m "Add map canvas with placeable, draggable markers"
```

### Task 2: `MapView`, frameless pop-out window, and registration

**Files:**
- Modify: `src/barons_journal/ui/popouts/map.py` (add `MapView`)
- Modify: `src/barons_journal/ui/popouts/manager.py` (`POPOUTS`, `_VIEWS`, `PopoutWindow`)
- Modify: `CLAUDE.md` (the `popouts/` bullet: mention the Map widget)
- Test: `tests/ui/test_map.py`, `tests/ui/test_popouts.py`

**Interfaces:**
- Consumes: everything Task 1 produces.
- Produces:
  - `class MapView(QWidget)`: `__init__(self, controller: SessionController, parent: QWidget | None = None)`, `canvas: MapCanvas`, `strip: QWidget`, `buttons: dict[str, QToolButton]` (keyed by kind), `render(view: ViewState) -> None`. It connects `controller.view_changed` to `render`.
  - `PopoutWindow(key, title, content, frameless: bool = False)`
  - `POPOUTS` gains `("map", "Map")` at the end, and `_VIEWS["map"] = MapView`.

- [ ] **Step 1: Write the failing tests.**

```python
# test_map.py — v = MapView(controller); qtbot.addWidget(v)
def test_buttons_in_order_with_tooltips(qtbot, controller):
    assert list(v.buttons) == [k for k, _ in MARKER_KINDS]
    assert v.buttons["boss"].toolTip() == "Strong enemy"

def test_button_arms_and_disarms(qtbot, controller):
    v.buttons["key"].click();   assert v.canvas.kind == "key"
    v.buttons["chest"].click(); assert v.canvas.kind == "chest" and not v.buttons["key"].isChecked()
    v.buttons["chest"].click(); assert v.canvas.kind is None

def test_placing_disarms(qtbot, controller):     # arm key, click the canvas → kind None, button unchecked

def test_floor_change_clears_same_floor_keeps(qtbot, controller):
    # render(ViewState("live", ..., location=Location(3))), place a marker,
    # render the same location again → 1 marker; render Location(4) → 0; render location=None → 0

# test_popouts.py
def test_map_window_is_frameless_and_translucent(qtbot, controller):
    w = PopoutWindow("map", "Map", MapView(controller), frameless=True)
    assert w.windowFlags() & Qt.WindowType.FramelessWindowHint
    assert w.windowFlags() & Qt.WindowType.WindowStaysOnTopHint
    assert w.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    assert w.windowType() == Qt.WindowType.Dialog

def test_map_registered():
    assert POPOUTS[-1] == ("map", "Map")
```

- [ ] **Step 2: Run them and check they fail.** Run `uv run pytest tests/ui/test_map.py tests/ui/test_popouts.py -v`. Expected: the new tests FAIL (no `MapView`, no `frameless`).

- [ ] **Step 3: Implement `MapView`.**
  - Layout: the strip on top, the canvas below with a `QSizeGrip` in its bottom-right corner.
  - The strip has `autoFillBackground(True)` so it stays opaque in both themes while the window is translucent. It holds one checkable `QToolButton` per kind (an icon from `icon_path`, the tooltip set to the label) and a stretch.
  - Arming: toggling a button on unchecks the others and sets `canvas.kind`. Toggling it off sets `canvas.kind = None`. `canvas.placed` unchecks the armed button.
  - A left press on the strip's empty area calls `self.window().windowHandle().startSystemMove()`. There's no title bar, and COSMIC ignores `move()`.
  - `render`: when `view.location != self._location`, call `canvas.clear()`, then store the location.

- [ ] **Step 4: Implement `PopoutWindow(frameless=True)`.** Add `Qt.WindowType.FramelessWindowHint` to the flags and set `WA_TranslucentBackground`. In `PopoutManager.set_open`, pass `frameless=(key == "map")`. Register `("map", "Map")` and `MapView`. Update the `popouts/` bullet in CLAUDE.md.

- [ ] **Step 5: Run the whole suite.** Run `uv run pytest`. Expected: all PASS, including the existing main-window tests that loop over `POPOUTS`.

- [ ] **Step 6: Commit.**

```bash
git add -A src tests CLAUDE.md
git commit -m "Add Map pop-out: translucent frame with marker strip, cleared on floor change"
```

### Task 3: Manual check on the real desktop (with the user)

- [ ] **Step 1:** Run `uv run barons-journal` from the worktree, then View → Widgets → Map. Ask the user to confirm on COSMIC:
  - the region is see-through, with Barony visible underneath;
  - dragging the strip moves the window, and the grip resizes it;
  - the window stays above windowed Barony;
  - clicking in the region places a marker (clicks don't fall through).

  If the region is opaque black, the compositor isn't giving an ARGB visual. Report that to the user rather than working around it.
