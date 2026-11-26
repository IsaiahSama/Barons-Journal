# Pop-out widgets

## Why

While playing Barony, the user wants specific bits of information floating over the game, each in its own small window they drag and resize, instead of one big app window.

## Goals

Five pop-out widget windows, each toggled from the main window:

| Widget | Shows |
|---|---|
| Vitals | HP bar, MP bar, gold, hunger |
| Attributes | STR, DEX, CON, INT, PER, CHR |
| Skills | proficiency table |
| Floor note | the current floor's note, editable |
| Current floor | the Floors-table row for the current floor: Floor, Area, Secret entrance, Leads to, Artifacts, Orb |

- Each widget stays above other windows (including the game when it runs windowed/borderless), floats instead of being tiled, and can be resized.
- Which widgets are open and their sizes are remembered between launches.

## Non-goals

- No widget for equipment, effects, scrolls, backpack, kills, alchemy or run notes; those stay in the main window.
- No global hotkey, no click-through, no opacity setting.
- No change to the main window's Focus/Dashboard layouts; the Character panel keeps showing everything it does today.
- Scroll auto-fill from the save: investigated separately and not possible without the per-run shuffle (see conversation); out of scope.

## Constraints (measured on the user's machine: COSMIC 1.0, Wayland, auto-tiling on)

- Native Wayland lets no app keep itself on top. Under XWayland, `Qt.WindowStaysOnTopHint` **works**.
- Under XWayland, a window flagged `Qt.Dialog` **floats** with auto-tiling on; a `Qt.Tool` window gets tiled.
- COSMIC **ignores app-requested positions**, both before show and after (a delayed `move()` did nothing). So on COSMIC widgets open where the compositor puts them and the user drags them each session. Size is still restored.
- Only `ui` may import Qt; every `Journal` call stays on the main thread (CLAUDE.md).

## Approaches

1. **Separate top-level widget windows (picked).** Each widget is a new small window listening to `SessionController.view_changed`, like the panels do. Main window untouched; pop-outs toggled from a menu.
2. Qt dock widgets: floating docks belong to the main window (hide when it is minimised) and would replace the current splitter layouts. Rejected: large rewrite, wrong behaviour.
3. Moving the real panel instances out of the main window: fights `LayoutManager`, leaves holes. Rejected.
4. One transparent full-screen overlay hosting the widgets (the only way to own positions on COSMIC): needs input masking so clicks reach the game around the widgets, i.e. the click-through the user said they don't need. Rejected.

## Design

- **Platform:** in `ui.run()`, before `QApplication` is created, on Linux when `WAYLAND_DISPLAY` is set, do `os.environ.setdefault("QT_QPA_PLATFORM", "xcb")`. `setdefault` keeps a user's (or the offscreen tests') explicit choice. This moves the whole app to XWayland; there is one platform per process.
- **Windows:** each widget is a parentless `QWidget` with `Qt.Dialog | Qt.WindowStaysOnTopHint`. Parentless means minimising the main window leaves the widgets up. Title like "Vitals · Baron's Journal". They pick up the app stylesheet/theme automatically.
- **Toggling:** View → Widgets submenu with five checkable actions. Closing a widget window unchecks its action.
- **Persistence (`AppSettings`):** per widget, whether it's open and its `saveGeometry()` bytes. Restore both at startup. Position restore works on X11/Windows and is a no-op on COSMIC; that's fine.
- **Content when not live:** stats widgets show the same message the panels show (`StatsPanel` behaviour: "Stats are only available for the live run" / "No run loaded"). The floor note follows `ViewState.editable` (read-only when not live). The current-floor row is empty when there's no location.
- **Vitals / Attributes / Skills:** render the same data as `CharacterPanel` does today. Share the rendering code with `CharacterPanel` instead of copying it; the builder decides how (e.g. small `StatsPanel` subclasses, or shared fill helpers).
- **Floor note:** a `NoteEditor` bound to `(gamekey, view.location)`. It flushes on `controller.about_to_change`, rebinds on `view_changed`, and calls `reload_if_unfocused()` on `floor_note_changed`, so it stays in sync with the Notes panel and the Floors tab editor.
- **Current floor:** its own `FloorsModel` instance updated via `set_state`, shown in a `QTableView` with every row hidden except `row_of(view.location)`.
- **Shutdown:** closing the main window saves which widgets are open (before closing them), flushes the floor-note widget along with the existing note flush, closes the widgets and quits.
- **Tests (`tests/ui`, offscreen):** toggle opens/closes and syncs the menu check; open state and geometry persist; widgets render the live save and the past/empty messages; the floor-note widget saves and picks up edits made elsewhere; the current-floor widget shows exactly the current row.

## Left to the builder

File layout (e.g. `ui/widgets/popouts.py` or a `ui/popouts/` package), how the Character rendering is shared, default sizes.

## Known risks

- XWayland apps can look blurry under fractional scaling.
- The `xcb` platform plugin needs `libxcb-cursor0` on some distros (it works on this machine).
