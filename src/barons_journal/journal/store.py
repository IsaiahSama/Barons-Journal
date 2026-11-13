"""SQLite storage for the user's own data: runs, scroll identifications, and notes.

Kept in the app's data folder, never in the game's files. Keys:
- runs: gamekey (one row per run, updated from each loaded save)
- scroll identifications: (gamekey, label)
- run notes: gamekey
- floor notes: (gamekey, dungeon_lvl)

Everything else references ``runs``, so record a run (``record_run``) before
writing anything for it. Deleting a run deletes its notes and identifications.

The schema version is kept in ``PRAGMA user_version``.
"""

import os
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from types import TracebackType

from ..data import SaveFile
from ..data.ids import CLASSES, RACES
from .scroll_progress import JournalError, ScrollProgress

APP_DIR_NAME = "barons-journal"
SCHEMA_VERSION = 1

# Timestamps are stored as ISO 8601 text, which sorts correctly as a string.
_SCHEMA_V1 = """
CREATE TABLE runs (
    gamekey INTEGER PRIMARY KEY,
    character_name TEXT NOT NULL,
    char_class INTEGER NOT NULL,
    race INTEGER NOT NULL,
    last_floor INTEGER NOT NULL,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL
);
CREATE TABLE scroll_identifications (
    gamekey INTEGER NOT NULL REFERENCES runs ON DELETE CASCADE,
    label TEXT NOT NULL,
    scroll_item_id INTEGER NOT NULL,
    PRIMARY KEY (gamekey, label)
);
CREATE TABLE run_notes (
    gamekey INTEGER PRIMARY KEY REFERENCES runs ON DELETE CASCADE,
    body TEXT NOT NULL
);
CREATE TABLE floor_notes (
    gamekey INTEGER NOT NULL REFERENCES runs ON DELETE CASCADE,
    dungeon_lvl INTEGER NOT NULL,
    body TEXT NOT NULL,
    PRIMARY KEY (gamekey, dungeon_lvl)
);
"""


@dataclass(frozen=True, slots=True)
class Run:
    """What the journal remembers about a run, as of the newest save it has seen."""

    gamekey: int
    character_name: str
    char_class: int
    race: int
    last_floor: int
    first_seen: datetime
    last_seen: datetime

    @property
    def class_name(self) -> str:
        return CLASSES.label(self.char_class)

    @property
    def race_name(self) -> str:
        return RACES.label(self.race)


def default_journal_path() -> Path:
    """Where the journal lives by default, following each OS's convention for app data."""
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData/Roaming")
    elif sys.platform == "darwin":
        base = Path.home() / "Library/Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share")
    return base / APP_DIR_NAME / "journal.sqlite3"


class Journal:
    """The user's journal. Use as a context manager, or call ``close()``."""

    def __init__(self, path: str | Path) -> None:
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path)
        try:
            # Off by default on every new SQLite connection.
            self._conn.execute("PRAGMA foreign_keys = ON")
            self._migrate()
        except BaseException:
            self._conn.close()
            raise

    def _migrate(self) -> None:
        version = self._conn.execute("PRAGMA user_version").fetchone()[0]
        if version > SCHEMA_VERSION:
            raise JournalError(
                f"Journal schema version {version} is newer than this app supports ({SCHEMA_VERSION})"
            )
        if version == 0:
            self._conn.executescript(f"BEGIN; {_SCHEMA_V1} PRAGMA user_version = {SCHEMA_VERSION}; COMMIT;")

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "Journal":
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None
    ) -> None:
        self.close()

    def _write(self, gamekey: int, sql: str, params: tuple) -> None:
        """Run one write, turning a missing run into a clear error."""
        try:
            with self._conn:
                self._conn.execute(sql, params)
        except sqlite3.IntegrityError as e:
            if "FOREIGN KEY" in str(e):
                raise JournalError(f"Run {gamekey} is not recorded; call record_run first") from None
            raise

    # --- Runs -----------------------------------------------------------------

    def record_run(self, save: SaveFile) -> None:
        """Create or update the run's entry from a loaded save.

        A save older than one already seen (e.g. a restored backup) only moves
        ``first_seen`` back; it doesn't roll back the character details.
        """
        seen = save.timestamp.isoformat()
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO runs (gamekey, character_name, char_class, race, last_floor, first_seen, last_seen)
                VALUES (:gamekey, :name, :char_class, :race, :floor, :seen, :seen)
                ON CONFLICT (gamekey) DO UPDATE SET
                    first_seen = min(first_seen, excluded.first_seen),
                    character_name = iif(excluded.last_seen >= last_seen, excluded.character_name, character_name),
                    char_class = iif(excluded.last_seen >= last_seen, excluded.char_class, char_class),
                    race = iif(excluded.last_seen >= last_seen, excluded.race, race),
                    last_floor = iif(excluded.last_seen >= last_seen, excluded.last_floor, last_floor),
                    last_seen = max(last_seen, excluded.last_seen)
                """,
                {
                    "gamekey": save.gamekey,
                    "name": save.player.name,
                    "char_class": save.player.char_class,
                    "race": save.player.race,
                    "floor": save.dungeon_lvl,
                    "seen": seen,
                },
            )

    def run(self, gamekey: int) -> Run | None:
        row = self._conn.execute(f"{_RUN_SELECT} WHERE gamekey = ?", (gamekey,)).fetchone()
        return _run_from_row(row) if row else None

    def runs(self) -> list[Run]:
        """Every recorded run, most recently seen first."""
        rows = self._conn.execute(f"{_RUN_SELECT} ORDER BY last_seen DESC, gamekey")
        return [_run_from_row(row) for row in rows]

    def delete_run(self, gamekey: int) -> None:
        """Delete a run and all of its notes and scroll identifications."""
        with self._conn:
            self._conn.execute("DELETE FROM runs WHERE gamekey = ?", (gamekey,))

    # --- Scroll identifications ---------------------------------------------

    def scroll_identifications(self, gamekey: int) -> dict[str, int]:
        """Label -> scroll item ID, for this run."""
        rows = self._conn.execute(
            "SELECT label, scroll_item_id FROM scroll_identifications WHERE gamekey = ?", (gamekey,)
        )
        return dict(rows.fetchall())

    def scroll_progress(self, gamekey: int) -> ScrollProgress:
        return ScrollProgress.from_identifications(self.scroll_identifications(gamekey))

    def identify_scroll(self, gamekey: int, label: str, scroll_item_id: int) -> None:
        """Record that ``label`` is ``scroll_item_id`` in this run, replacing any earlier answer.

        Raises ``JournalError`` if the result is impossible, such as an unknown label or a
        scroll identified under more labels than it has.
        """
        proposed = self.scroll_identifications(gamekey) | {label: scroll_item_id}
        ScrollProgress.from_identifications(proposed)  # validates
        self._write(
            gamekey,
            "INSERT INTO scroll_identifications (gamekey, label, scroll_item_id) VALUES (?, ?, ?) "
            "ON CONFLICT (gamekey, label) DO UPDATE SET scroll_item_id = excluded.scroll_item_id",
            (gamekey, label, scroll_item_id),
        )

    def forget_scroll(self, gamekey: int, label: str) -> None:
        with self._conn:
            self._conn.execute(
                "DELETE FROM scroll_identifications WHERE gamekey = ? AND label = ?", (gamekey, label)
            )

    # --- Notes ----------------------------------------------------------------

    def run_note(self, gamekey: int) -> str:
        row = self._conn.execute("SELECT body FROM run_notes WHERE gamekey = ?", (gamekey,)).fetchone()
        return row[0] if row else ""

    def set_run_note(self, gamekey: int, body: str) -> None:
        """Save the run's note. An empty note deletes it."""
        if body:
            self._write(
                gamekey,
                "INSERT INTO run_notes (gamekey, body) VALUES (?, ?) "
                "ON CONFLICT (gamekey) DO UPDATE SET body = excluded.body",
                (gamekey, body),
            )
        else:
            self._write(gamekey, "DELETE FROM run_notes WHERE gamekey = ?", (gamekey,))

    def floor_note(self, gamekey: int, dungeon_lvl: int) -> str:
        row = self._conn.execute(
            "SELECT body FROM floor_notes WHERE gamekey = ? AND dungeon_lvl = ?", (gamekey, dungeon_lvl)
        ).fetchone()
        return row[0] if row else ""

    def floor_notes(self, gamekey: int) -> dict[int, str]:
        """Floor -> note, for every floor of this run that has one, in floor order."""
        rows = self._conn.execute(
            "SELECT dungeon_lvl, body FROM floor_notes WHERE gamekey = ? ORDER BY dungeon_lvl", (gamekey,)
        )
        return dict(rows.fetchall())

    def set_floor_note(self, gamekey: int, dungeon_lvl: int, body: str) -> None:
        """Save a floor's note. An empty note deletes it."""
        if body:
            self._write(
                gamekey,
                "INSERT INTO floor_notes (gamekey, dungeon_lvl, body) VALUES (?, ?, ?) "
                "ON CONFLICT (gamekey, dungeon_lvl) DO UPDATE SET body = excluded.body",
                (gamekey, dungeon_lvl, body),
            )
        else:
            self._write(
                gamekey,
                "DELETE FROM floor_notes WHERE gamekey = ? AND dungeon_lvl = ?",
                (gamekey, dungeon_lvl),
            )


_RUN_SELECT = (
    "SELECT gamekey, character_name, char_class, race, last_floor, first_seen, last_seen FROM runs"
)


def _run_from_row(row: tuple) -> Run:
    gamekey, name, char_class, race, last_floor, first_seen, last_seen = row
    return Run(
        gamekey=gamekey,
        character_name=name,
        char_class=char_class,
        race=race,
        last_floor=last_floor,
        first_seen=datetime.fromisoformat(first_seen),
        last_seen=datetime.fromisoformat(last_seen),
    )
