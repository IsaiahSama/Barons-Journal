# Data Layer Reference (for building the UI)

This is what the UI can use from Baron's Journal's non-UI code: what each part does, how to call it, and the rules the UI has to follow. Everything here is tested (`uv run pytest`). No GUI toolkit is chosen yet, and nothing in this layer depends on one.

## At a glance

| Package | What it gives the UI | Reads or writes |
|---|---|---|
| `barons_journal.data` | The current run's stats, inventory, equipment, and effects, parsed from Barony's save file | Reads the game's save (read-only) |
| `barons_journal.data.ids` | Numeric game ID → in-game name lookups (classes, races, items, spells, ...) | Bundled `ids.json` |
| `barons_journal.reference` | Static scroll data: the 16 scroll types and the 25 unidentified labels | Bundled `scrolls.json` |
| `barons_journal.journal` | The user's own data in SQLite: runs, scroll identifications, run notes, floor notes | Reads and writes the app's own database |

The UI should only use the typed objects these packages return. Never read the raw save JSON or query the SQLite database directly.

## Quick start

```python
from pathlib import Path

from barons_journal.data import load_save, InvalidSaveError
from barons_journal.journal import Journal, default_journal_path
from barons_journal.reference import SCROLL_LABELS, SCROLLS

save = load_save(Path.home() / ".barony/savegames/savegame0.baronysave")
player = save.player
print(player.name, player.race_name, player.class_name, "floor", save.dungeon_lvl)
print(f"HP {player.stats.hp}/{player.stats.max_hp}")

with Journal(default_journal_path()) as journal:
    journal.record_run(save)                                 # always do this first, every time a save loads
    journal.identify_scroll(save.gamekey, "ZELGO MER", 75)   # the user says ZELGO MER is a scroll of fire
    progress = journal.scroll_progress(save.gamekey)
    for label in progress.unknown_labels:
        print(label, "could be", [s.name for s in progress.candidates(label)])
```

---

## 1. Reading the save: `barons_journal.data`

### Loading

| Call | Returns | Notes |
|---|---|---|
| `load_save(path)` | `SaveFile` | Reads and parses a save file. Raises `FileNotFoundError` if it's missing. |
| `parse_save(raw_dict)` | `SaveFile` | Same thing, but takes JSON you've already decoded. |

**Errors:** both raise `InvalidSaveError` (a `ValueError`) when the file isn't usable: it isn't JSON, has the wrong magic cookie, is missing a field, or has bad indices. `UnsupportedVersionError` is a subclass of it, raised for a Barony version the app hasn't been checked against (only `game_version` **502** is supported right now). Catch `InvalidSaveError` to handle both, and show the message: it says what's wrong.

**Where saves live:** on Linux, Barony writes `~/.barony/savegames/savegameN.baronysave` (N is the save slot). Note the extension is `.baronysave`. Windows and macOS locations haven't been worked out yet.

### `SaveFile`

| Field | Type | Meaning |
|---|---|---|
| `game_version` | `int` | Barony's save format version (502) |
| `game_name` | `str` | The run's name |
| `gamekey` | `int` | Stays the same for the whole run. **This is the run's ID everywhere in the journal.** |
| `dungeon_lvl` | `int` | Current floor (0 is the first floor) |
| `timestamp` | `datetime` | When Barony wrote the save (local time, no timezone) |
| `player` | `Player` | The local player |

### `Player`

| Field / property | Type | Meaning |
|---|---|---|
| `name` | `str` | Character name |
| `char_class`, `race` | `int` | Raw IDs |
| `class_name`, `race_name` | `str` | Display names, e.g. "Warrior", "Human" |
| `stats` | `Stats` | See below |
| `inventory` | `tuple[Item, ...]` | Everything carried, **including equipped items and learned spells** |
| `equipment` | `Equipment` | What's worn and wielded |
| `effects` | `tuple[Effect, ...]` | Active status effects only, in ID order |
| `kills` | `tuple[int, ...]` | Kill counts indexed by monster ID |
| `kills_by_monster` | `dict[str, int]` | Monster name → kills, only monsters killed at least once |
| `hotbar` | `tuple[int \| None, ...]` | Raw hotbar slots, `None` = empty. **Not resolved to items yet** (see "Not built yet") |

### `Stats`

`hp`, `max_hp`, `mp`, `max_mp`, `strength`, `dexterity`, `constitution`, `intelligence`, `perception`, `charisma`, `exp`, `level`, `gold`, `hunger` (all `int`), and:

- `proficiencies`: `tuple[int, ...]`, 16 skill levels (0–100) in the game's order
- `proficiencies_by_name`: `dict[str, int]`, e.g. `{"Tinkering": 0, ..., "Polearm": 50, ...}` in the game's order

### `Item`

| Field / property | Type | Meaning |
|---|---|---|
| `name` | `str` | **What the UI should display.** Respects whether the item is identified: an unidentified "leather gloves of dexterity" is just "gloves", and an unidentified scroll is "scroll". Spell items are named after their spell ("Fireball"). |
| `status`, `status_name` | `int`, `str` | Condition 0–4: "broken", "decrepit", "worn", "serviceable", "excellent" |
| `beatitude` | `int` | Blessing: positive = blessed (+N), negative = cursed (−N) |
| `count` | `int` | Stack size |
| `identified` | `bool` | Whether the player has identified it |
| `equipped` | `bool` | Whether it's in an equipment slot |
| `is_spell` | `bool` | True for learned spells, which Barony keeps in the inventory |
| `type`, `appearance` | `int` | Raw values. **Don't display them; see rule 1.** |

To show a "backpack" without equipped items and spells: `[i for i in player.inventory if not i.equipped and not i.is_spell]`.

### `Equipment`

Ten slots, each an `Item` or `None`: `helmet`, `breastplate`, `gloves`, `shoes`, `shield`, `weapon`, `cloak`, `amulet`, `ring`, `mask`.

- `equipment.slots()` yields `(slot_name, item_or_None)` in the game's slot order, which suits rendering a paper-doll or a list.
- Each slot holds the same object as the matching entry in `player.inventory` (`equipment.weapon is inventory[0]`).

### `Effect`

| Field / property | Type | Meaning |
|---|---|---|
| `name` | `str` | In-game name, e.g. "Magic Resistance" |
| `strength` | `int` | Usually 1. Some effects use higher values for tiers (e.g. Flute tier III = 3) |
| `seconds_remaining` | `float \| None` | Game seconds left; `None` means no timer (lasts until removed) |
| `hidden` | `bool` | True for internal effects the game itself never shows (Stunned, Knockback, Dash, ...). **The UI should normally filter these out.** |
| `id`, `timer_ticks` | `int` | Raw values (timer runs at 50 ticks per second) |

---

## 2. Name lookups: `barons_journal.data.ids`

The models above already give names through properties, so the UI rarely needs these directly. They're useful for building pickers, legends, and filters.

| Table | Entries | Example |
|---|---|---|
| `CLASSES` | 26 | `CLASSES[1] == "Warrior"` |
| `RACES` | 18 | `RACES[0] == "Human"` |
| `MONSTERS` | 53 | `MONSTERS[23] == "crystal golem"` |
| `PROFICIENCIES` | 16 | `PROFICIENCIES[0] == "Tinkering"` |
| `ITEMS` / `ITEMS_UNIDENTIFIED` | 524 | `ITEMS[7] == "iron spear"` |
| `SPELLS` | 225 | `SPELLS[4] == "Fireball"` (ID 0 means "no spell") |
| `ITEM_STATUS` | 5 | `ITEM_STATUS[3] == "serviceable"` |
| `EFFECTS` | 135 | `EFFECTS[16] == "Magic Resistance"` |

Each table supports:

- `table[id]`: the name. Raises `KeyError` for an unknown ID.
- `table.get(id, default=None)`: the name, or `default`.
- `table.label(id)`: the name, or a placeholder like `"Unknown class #99"`. Never fails, so it's the safest choice for display.
- `table.index_of(name)`: reverse lookup.
- `len(table)`

Also available: `HIDDEN_EFFECTS` (a frozenset of effect IDs the game doesn't show) and `SPELL_ITEM` (162, the item type of a learned spell).

**Casing:** names use the game's own capitalisation. Classes, races, skills, spells and effects are capitalised ("Warrior", "Fireball"). Items and monsters are lowercase ("iron spear", "crystal golem"), because the game uses them mid-sentence. Capitalise in the UI where needed.

---

## 3. Scroll reference: `barons_journal.reference`

| Name | Type | Meaning |
|---|---|---|
| `SCROLL_LABELS` | `tuple[str, ...]` | All 25 labels an unidentified scroll can have, e.g. "ZELGO MER", "NR 9", "READ ME". In the game's order. |
| `SCROLLS` | `tuple[Scroll, ...]` | The 16 scroll types, in item-ID order |
| `scroll_by_item_id(id)` | `Scroll` | Lookup; raises `KeyError` if the item isn't a scroll |

### `Scroll`

| Field | Example (scroll of fire) |
|---|---|
| `item_id` | `75` |
| `name` | `"scroll of fire"` |
| `effect` | `"Summons flames at current location"` (one line, from the game's tooltip) |
| `value` | `35` (base gold value) |
| `weight` | `2` |
| `label_count` | `3` |

### How labels work (important for the scroll UI)

- In each run, all 25 labels are in use, and **each label always means one scroll type for the whole run**.
- A scroll type can have **more than one label** in the same run. `label_count` says how many:
  - **3 labels:** scroll of fire, scroll of destroy armor
  - **2 labels:** identify, light, food, teleportation, summon
  - **1 label:** the other nine
- So finding out that "ZELGO MER" is fire does **not** mean fire is ruled out for the other labels. Fire is only ruled out once all 3 of its labels are found. `ScrollProgress` (below) does this counting, so the UI doesn't have to.
- **The app can't read an inventory scroll's label from the save.** The player reads the label in-game and picks it from `SCROLL_LABELS` in the UI.

---

## 4. The user's journal: `barons_journal.journal`

Stored in SQLite at `default_journal_path()`:

- Linux: `~/.local/share/barons-journal/journal.sqlite3` (or under `$XDG_DATA_HOME`)
- Windows: `%APPDATA%\barons-journal\journal.sqlite3`
- macOS: `~/Library/Application Support/barons-journal/journal.sqlite3`

The folder is created automatically. Open the journal with `Journal(path)`, ideally as a context manager (`with Journal(...) as journal:`), or call `journal.close()`. Every write is saved immediately; there's no separate save step.

### Runs

| Call | Returns | Notes |
|---|---|---|
| `record_run(save)` | — | Creates or updates the run from a loaded save. **Call it every time a save loads, before any other journal call for that run.** Safe to call repeatedly. An older save (e.g. a restored backup) never rolls the run back. |
| `runs()` | `list[Run]` | Every recorded run, most recently seen first. For a "past runs" screen. |
| `run(gamekey)` | `Run \| None` | One run |
| `delete_run(gamekey)` | — | Deletes the run **and all of its notes and scroll identifications**. Ask the user to confirm first. |

`Run` fields: `gamekey`, `character_name`, `char_class`, `race`, `last_floor`, `first_seen`, `last_seen` (both `datetime`, taken from the save's own timestamps), plus the `class_name` and `race_name` properties.

### Scroll identifications

| Call | Returns | Notes |
|---|---|---|
| `identify_scroll(gamekey, label, scroll_item_id)` | — | Records "this label is this scroll" for the run. Replaces any earlier answer for that label. |
| `forget_scroll(gamekey, label)` | — | Removes an identification (undo). Does nothing if the label wasn't identified. |
| `scroll_identifications(gamekey)` | `dict[str, int]` | Label → scroll item ID |
| `scroll_progress(gamekey)` | `ScrollProgress` | What every label is, or could still be. **This is what the scroll screen should render from.** |

`identify_scroll` raises `JournalError` (a `ValueError`) if the result would be impossible:

- the label isn't one of `SCROLL_LABELS`
- the item isn't a scroll
- the scroll would have more labels than it has. For example, identifying a second label as magic mapping, which only has one, gives: "scroll of magic mapping only has 1 label(s) per run, but 2 are identified as it".

When that happens nothing is saved. Show the message to the user; it's written to be readable.

### `ScrollProgress`

| Member | Type | Meaning |
|---|---|---|
| `identified` | `Mapping[str, Scroll]` | Label → scroll, for labels identified so far, in label order |
| `unknown_labels` | `tuple[str, ...]` | Labels not identified yet, in label order |
| `remaining` | `Mapping[Scroll, int]` | Scrolls with labels still to find → how many. A scroll drops out once all its labels are found. |
| `candidates(label)` | `tuple[Scroll, ...]` | An identified label returns just its scroll. An unknown label returns every scroll in `remaining`, in item-ID order. |
| `is_complete` | `bool` | True once all 25 labels are identified |

Every unknown label has the same candidates, because nothing else distinguishes them. When only one scroll type is left in `remaining`, every unknown label must be that scroll, and `candidates()` reflects this automatically.

**Suggested scroll screen:** one row per label in `SCROLL_LABELS`:

- **Identified label:** show the scroll's name and effect, with an "undo" action that calls `forget_scroll`.
- **Unknown label:** show a picker filled from `candidates(label)`. Choosing an option calls `identify_scroll`; then re-read `scroll_progress` and redraw.

A "still to find" panel can show `remaining` (e.g. "scroll of fire: 2 labels left").

### Notes

Each run has one free-text scratchpad note, and each floor of a run has one note.

| Call | Returns |
|---|---|
| `run_note(gamekey)` | `str` (`""` if none) |
| `set_run_note(gamekey, body)` | — |
| `floor_note(gamekey, dungeon_lvl)` | `str` (`""` if none) |
| `set_floor_note(gamekey, dungeon_lvl, body)` | — |
| `floor_notes(gamekey)` | `dict[int, str]`: every floor of the run with a note, in floor order |

Saving an empty string deletes the note. Use `save.dungeon_lvl` for the current floor.

---

## Rules the UI must follow

1. **Don't reveal unidentified items.** The save stores an unidentified item's *true* type: an unidentified scroll of fire is saved as type 75. Always display `item.name`, which respects `identified`. Never show `item.type`, `item.appearance`, or a name looked up from `item.type` yourself for an item where `identified` is `False`. This includes tooltips, debug panels, and sorting or grouping by type.
2. **Call `journal.record_run(save)` every time a save loads**, before any other journal call for that run. Notes and identifications for an unrecorded run raise `JournalError` ("Run … is not recorded").
3. **The save is a snapshot.** Barony writes it on floor transitions, not continuously, so the stats view is always as of the last floor change. Say so in the UI, e.g. "As of floor 3, saved 14:02" using `save.dungeon_lvl` and `save.timestamp`.
4. **Hide `effect.hidden` effects** by default; they're internal flags the game itself doesn't show.
5. **Handle `InvalidSaveError`.** A save can be mid-write, from a newer Barony version, or not a save at all. Show the error message and keep the last good data on screen instead of crashing.
6. **Use the journal from one thread.** A `Journal` holds one SQLite connection, which only works on the thread that opened it. If save loading or file watching runs in a background thread, send the parsed `SaveFile` to the UI thread and do the journal calls there.
7. **Never write to the game's files.** The app only reads saves. Everything the user enters goes into the journal.

---

## Not built yet

These are known gaps the UI work will run into. They're not bugs.

- **Finding the save.** Nothing picks the save slot or works out the platform path yet; the path above is the Linux default. There may be several `savegameN.baronysave` slots.
- **Watching the save.** Nothing refreshes when Barony writes a new save. The planned approach is to watch the file (e.g. with `watchdog`), then `load_save` → `record_run` → refresh the views.
- **Labels on inventory scrolls.** By design (see "How labels work"), the player enters labels by hand.
- **Hotbar.** `player.hotbar` holds raw values that look like inventory indices, but this isn't confirmed or resolved to `Item`s.
- **Inventory grid positions** (`x`/`y` in the save) aren't parsed.
- **Other players in multiplayer.** Only the local player is parsed.
- **Potion recipes and floor reference data** (secret levels, artifacts) from the README aren't built yet.
- **Item display extras** like "+2 blessed" or "(cursed)" prefixes aren't formatted for you. The raw `beatitude` is available, but the player only knows it once the item is identified, so apply rule 1 here too.

## Running and testing

```
uv sync                      # install dependencies
uv run barons-journal        # run the app (main() is still a stub)
uv run pytest                # full test suite
```

`tests/save_file_example.baronsave` is a real save (level-1 Human Warrior on floor 0) that's handy for UI development without launching the game. `load_save` accepts it like any other save.
