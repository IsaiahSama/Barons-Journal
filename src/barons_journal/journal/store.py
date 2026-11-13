"""SQLite storage for the user's own data: scroll identifications and notes.

Kept in the app's data folder, never in the game's files. Keys:
- scroll identifications: (gamekey, label)
- run notes: gamekey
- floor notes: (gamekey, dungeon_lvl)

The schema version is kept in ``PRAGMA user_version``.
"""

import os
import sqlite3
import sys
from pathlib import Path
from types import TracebackType

from .scroll_progress import JournalError, ScrollProgress

APP_DIR_NAME = "barons-journal"
SCHEMA_VERSION = 1

_SCHEMA_V1 = """
CREATE TABLE scroll_identifications (
    gamekey INTEGER NOT NULL,
    label TEXT NOT NULL,
    scroll_item_id INTEGER NOT NULL,
    PRIMARY KEY (gamekey, label)
);
CREATE TABLE run_notes (
    gamekey INTEGER PRIMARY KEY,
    body TEXT NOT NULL
);
CREATE TABLE floor_notes (
    gamekey INTEGER NOT NULL,
    dungeon_lvl INTEGER NOT NULL,
    body TEXT NOT NULL,
    PRIMARY KEY (gamekey, dungeon_lvl)
);
"""


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
            with self._conn:
                self._conn.executescript(f"BEGIN; {_SCHEMA_V1} PRAGMA user_version = {SCHEMA_VERSION}; COMMIT;")

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "Journal":
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None
    ) -> None:
        self.close()

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
        with self._conn:
            proposed = self.scroll_identifications(gamekey) | {label: scroll_item_id}
            ScrollProgress.from_identifications(proposed)  # validates
            self._conn.execute(
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
        with self._conn:
            if body:
                self._conn.execute(
                    "INSERT INTO run_notes (gamekey, body) VALUES (?, ?) "
                    "ON CONFLICT (gamekey) DO UPDATE SET body = excluded.body",
                    (gamekey, body),
                )
            else:
                self._conn.execute("DELETE FROM run_notes WHERE gamekey = ?", (gamekey,))

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
        with self._conn:
            if body:
                self._conn.execute(
                    "INSERT INTO floor_notes (gamekey, dungeon_lvl, body) VALUES (?, ?, ?) "
                    "ON CONFLICT (gamekey, dungeon_lvl) DO UPDATE SET body = excluded.body",
                    (gamekey, dungeon_lvl, body),
                )
            else:
                self._conn.execute(
                    "DELETE FROM floor_notes WHERE gamekey = ? AND dungeon_lvl = ?", (gamekey, dungeon_lvl)
                )

    # --- Runs -----------------------------------------------------------------

    def runs(self) -> list[int]:
        """Every gamekey with any journal data, ascending."""
        rows = self._conn.execute(
            "SELECT gamekey FROM scroll_identifications "
            "UNION SELECT gamekey FROM run_notes "
            "UNION SELECT gamekey FROM floor_notes "
            "ORDER BY gamekey"
        )
        return [row[0] for row in rows]
