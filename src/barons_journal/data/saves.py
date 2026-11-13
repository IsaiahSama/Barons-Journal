"""Find Barony save files on disk.

Barony writes `savegame<N><suffix>` into a `savegames` folder (setSaveGameFileName
in scores.cpp). N is the slot, 0-99. The suffix says what kind of save it is:

    .baronysave             single-player
    _mp.baronysave          multiplayer
    _modded.baronysave      single-player with mods
    _mp_modded.baronysave   multiplayer with mods

Where the `savegames` folder is depends on the OS (game.cpp): under `~/.barony`
on Linux and macOS, and inside the game's install folder on Windows.
"""

import os
import re
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

MAX_SLOTS = 100  # SAVE_GAMES_MAX in scores.hpp
_SAVE_NAME = re.compile(r"^savegame(\d{1,2})(_mp)?(_modded)?\.baronysave$")


@dataclass(frozen=True, slots=True)
class SaveSlot:
    """A save file found on disk. Load it with ``load_save(slot.path)``."""

    path: Path
    slot: int
    multiplayer: bool
    modded: bool
    modified: datetime
    """When the file was last written (local time), from the file system."""


def default_save_dirs() -> list[Path]:
    """Folders where Barony usually keeps saves on this OS, most likely first.

    Not all of them exist; ``find_saves`` skips the missing ones. On Windows the
    saves live in the game's install folder, so only common install locations are
    listed. Let the user pick the folder if the game is installed elsewhere.
    """
    if sys.platform == "win32":
        dirs = []
        for env in ("PROGRAMFILES(X86)", "PROGRAMFILES"):
            base = os.environ.get(env)
            if base:
                dirs.append(Path(base) / "Steam/steamapps/common/Barony/savegames")
                dirs.append(Path(base) / "Epic Games/Barony/savegames")
    else:
        home = Path.home()
        dirs = [
            home / ".barony/savegames",  # Steam and DRM-free builds
            home / ".barony/epicgames/savegames",  # Epic-only builds
            home / ".var/app/com.valvesoftware.Steam/.barony/savegames",  # Flatpak Steam (Linux)
        ]
    return list(dict.fromkeys(dirs))  # drop duplicates, keep order


def find_saves(dirs: Iterable[str | Path] | None = None) -> list[SaveSlot]:
    """Every save file in ``dirs`` (default: ``default_save_dirs()``), most recently written first.

    Missing folders are skipped. Files that aren't JSON saves (old ``.dat`` saves,
    screenshots, follower files) are ignored. The files aren't opened; use
    ``load_save`` on the one you want.
    """
    found = []
    for folder in dirs if dirs is not None else default_save_dirs():
        folder = Path(folder)
        if not folder.is_dir():
            continue
        for path in folder.iterdir():
            match = _SAVE_NAME.match(path.name)
            if not match or not path.is_file():
                continue
            slot = int(match.group(1))
            if slot >= MAX_SLOTS:
                continue
            found.append(
                SaveSlot(
                    path=path,
                    slot=slot,
                    multiplayer=match.group(2) is not None,
                    modded=match.group(3) is not None,
                    modified=datetime.fromtimestamp(path.stat().st_mtime),
                )
            )
    found.sort(key=lambda s: (s.modified, str(s.path)), reverse=True)
    return found


def latest_save(dirs: Iterable[str | Path] | None = None) -> SaveSlot | None:
    """The most recently written save, or None if there are none."""
    saves = find_saves(dirs)
    return saves[0] if saves else None
