# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Baron's Journal is a native desktop companion app for the game Barony (Python 3.13+, managed with uv). Planned features (from README): read-only stats for the current run, pulled from the save file; scratchpad notes per run and per floor; floor reference info (secret levels, artifacts); and potion recipes.

The project is at an early stage. `main()` in `src/barons_journal/__init__.py` is a stub, `src/barons_journal/data/read_save.py` only has a docstring, and no GUI toolkit has been picked yet. Design notes are in `plans/` (gitignored, local only). Read `plans/initial-review.md` before doing significant work.

## Commands

```
uv sync                      # install dependencies
uv run barons-journal        # run the app ([project.scripts] entry -> barons_journal:main)
```

The README's `uv run main.py` is outdated: there is no `main.py`. pytest isn't a dependency yet. Add it with `uv add --dev pytest`, then run tests with `uv run pytest` or `uv run pytest tests/test_x.py::test_name`.

## Architecture

- **Package layout:** src-layout, built with the `uv_build` backend. Code lives in `src/barons_journal/`.
- **Save parsing (`barons_journal.data`):** Barony's save files are **JSON**. The game writes them as `savegameN.baronysave` in `~/.barony/savegames/` on Linux (the sample in `tests/` is named `.baronsave`). Validate with `magic_cookie == "BARONYJSONSAVE"` and check `game_version`. `tests/save_file_example.baronsave` is a real save to develop and test against. The plan is to keep all raw-dict handling and quirk cleanup inside `data` and give the UI typed models only (`SaveFile`, `Player`, `Stats`, ...).
- **Where the data is:** the local player is `players[player_num]`. Most stats are under `players[n].stats` (`HP`/`maxHP`, `MP`/`maxMP`, `STR`/`DEX`/`CON`/`INT`/`PER`/`CHR`, `LVL`, `GOLD`, `PROFICIENCIES`). `stats.player_equipment` maps slot names to **indices into `stats.inventory`** (local player only; other players use `npc_equipment`). Learned spells are inventory items of type `SPELL_ITEM` (162) whose `appearance` is the spell ID. `EFFECTS`/`EFFECTS_TIMERS` have 160 slots (only 0-134 are defined); timers are in ticks, 50 per second. `gamekey` stays the same for the whole run, so it's the key for run notes; floor notes use `(gamekey, dungeon_lvl)`.
- **Save quirks to handle:**
  - The player object has a duplicate `"race"` key. Python's `json` keeps the last one.
  - Names end in `\r` (`game_name`, `stats.name`). Strip them.
  - `4294967295` (uint32 -1) means empty or none.
  - Class, race, kills, proficiencies, items, and spells are numeric IDs (list positions in Barony's C++ enums). `barons_journal.data.ids` maps them to in-game names from `ids.json`. Don't hand-edit that file: regenerate it with `scripts/build_id_tables.py <Barony checkout> --game-dir <installed Barony>`, which reads the enums and `lang/` files from `TurningWheel/Barony`. Status effect names aren't in the source repo, so they come from `data/status_effects.json` in the installed game (Steam: `~/.steam/steam/steamapps/common/Barony`). The Barony Save Editor (Groshie) is a useful cross-reference, but its spell list is missing `SPELL_DUCK_DIVE` (218), so spells from 218 on are shifted by one.
- **Save timing:** Barony writes the save on floor transitions, not continuously, so the stats view is always a snapshot.
- **Scrolls (`barons_journal.reference`):** `SCROLLS` (16 types) and `SCROLL_LABELS` (the 25 unidentified labels, in game order) come from `scrolls.json`; regenerate with `scripts/build_scroll_tables.py`, which takes the same arguments as the ID script. Each run shuffles a fixed 25-entry scroll list (`enchantedFeatherScrollsFixedList` in `items.hpp`, seeded from `gamekey`) and label `i` goes to entry `i`. Some scrolls take several labels (`label_count`: Fire and Destroy Armor have 3), so identifying one label doesn't rule that scroll out for the other labels. The plan is for the UI to record label -> scroll as the player identifies them. Don't compute the mapping from the seed. The save's player-level `scrolls` field (`known_scrolls` in `scores.cpp`) is a list of ints, probably label indices the player has learned; this isn't confirmed yet.
- **Unidentified items keep their true type in the save.** An unidentified scroll of fire is saved as type 75 with `identified: false`. The UI must show `Item.name` (which respects `identified`) and never the raw `type`/`item_id` of an unidentified item, or it gives away what the item is. For the same reason the app doesn't show an unidentified scroll's label: the label depends on the per-run shuffle, and working it out would mean computing the mapping.
- **Journal (`barons_journal.journal`):** the user's own data, in SQLite at `default_journal_path()` (XDG data dir / `%APPDATA%` / `~/Library/Application Support`). `Journal` stores runs keyed by `gamekey` (character, class, race, last floor, first/last seen, taken from the save's timestamp), plus scroll identifications keyed by `(gamekey, label)`, run notes keyed by `gamekey`, and floor notes keyed by `(gamekey, dungeon_lvl)`. Everything references `runs` through a foreign key with cascading delete, so call `record_run(save)` whenever a save is loaded, before writing anything for that run. An empty note deletes the row. `ScrollProgress` is plain logic with no SQLite: it uses `label_count` to work out which scrolls each unknown label can still be, and rejects impossible states (e.g. a 4th Fire label). The schema version is in `PRAGMA user_version`; bump `SCHEMA_VERSION` and add a migration step in `Journal._migrate` when the schema changes.
- **Data kept apart:** user notes go in the app's own storage, never in game files. Static reference data (floors, potion recipes) ships as curated JSON, separate from the save parser.
