# Map widget

## Why

While playing, the user wants to mark where things are on the current floor: a see-through frame laid over Barony's in-game map, with icons dropped on it.

## Goals

- A sixth pop-out, "Map", toggled from View → Widgets like the others (builds on `ui/popouts/`).
- Frameless, translucent, always on top: a gold border around an empty (see-through) region, a corner grip to resize, a thin top strip to drag the window.
- The top strip holds 7 marker buttons: Weapon (sword), Armour (helmet), Item (star), Key (key), Door (padlocked door), Strong enemy (skull and crossbones), Chest (chest).
- Pick a marker button, click in the region to place it. Drag a marker to move it, right-click it to remove it.
- Markers are positioned as fractions of the region, so resizing keeps them aligned with the map.

## Non-goals

- Markers are **not saved**: they live in memory only. The player can't return to a floor, so they're cleared when the current floor (`ViewState.location`) changes. Restarting the app also loses them.
- No key/door colour variants, no labels or notes on markers, no opacity setting, no click-through.

## Constraints

- COSMIC ignores app-requested positions: size is restored (existing `PopoutManager` geometry handling), position is not, so the user re-drags the frame each session.
- Translucency needs `WA_TranslucentBackground` + `FramelessWindowHint` under XWayland; untested on the user's machine, so verify it first. Moving and resizing use `startSystemMove()` / `QSizeGrip` since there's no title bar.
- Clicking the overlay takes focus from the game.
- Only `ui` imports Qt.

## Approaches

1. **New view in the existing `PopoutManager` (picked):** reuses the toggle, open state and size persistence. The map window needs different window flags, so `PopoutWindow` gets a way to be frameless/translucent for this key.
2. A standalone window outside `PopoutManager`: duplicates toggling and persistence. Rejected.
3. Saving markers in the journal per floor: dropped by the user (see Non-goals).

## Left to the builder

- Icons: small bundled SVGs rendered with QtSvg (already part of PySide6), no new dependency.
- Exact sizes, border width, marker size.
