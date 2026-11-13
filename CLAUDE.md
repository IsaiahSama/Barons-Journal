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
- **Data kept apart:** user notes go in the app's own storage, never in game files. Static reference data (floors, potion recipes) ships as curated JSON, separate from the save parser.
