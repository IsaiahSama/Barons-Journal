# Baron's Journal

A native desktop application designed to serve as a companion for Barony players as they explore the mines.

In playing Barony, I find that there's often some things that I would like to take note of for future reference, that I'd have to jot down somewhere in an unorganized fashion. Figured it would be more convenient to have a mini application to do the same thing.

## Requirements

- Python 3.13 or later
- uv
- Barony

## Quick Start

```
git clone https://github.com/IsaiahSama/Barons-Journal
cd barons-journal
uv venv .venv
uv sync
uv run barons-journal
```

## Features

- Displays read only statistics of the current run including:
    - Character name, race, class, level, health, mana, stats, skills
    - Dungeon level, gold, kills, learnt spells, and inventory
- Scratchpad for quick note taking, for the entire run, and for a specific floor (including secret levels).
- Scroll identification: record which unidentified scroll label is which scroll, with the remaining possibilities worked out for you
- Browse past runs and their notes, and pick which save slot to follow
- Two switchable layouts (Focus and Dashboard)
- Floor information, such as which floor has secret levels, and what artifacts are present
- Potion recipes

## License

MIT License
