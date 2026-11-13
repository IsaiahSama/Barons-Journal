"""The hub the panels listen to: which save is followed, and what is on screen."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QFileSystemWatcher, QObject, QTimer, Signal

from ..data import (
    InvalidSaveError,
    SaveSlot,
    default_save_dirs,
    find_saves,
    latest_save,
    load_save,
)
from ..journal import Journal, JournalError, Run, ScrollProgress
from .location import Location
from .settings import AppSettings
from .state import Banner, ViewState


class SessionController(QObject):
    about_to_change = Signal()
    """Emitted synchronously right before view_changed: editors flush on it."""
    view_changed = Signal(object)  # ViewState
    banner_changed = Signal(object)  # Banner | None
    floor_note_changed = Signal(int, int, bool)  # gamekey, dungeon_lvl, secret
    scrolls_changed = Signal(int)  # gamekey

    DEBOUNCE_MS = 300
    RETRY_MS = 1000
    MAX_RETRIES = 5

    def __init__(
        self,
        journal: Journal,
        settings: AppSettings,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._journal = journal
        self._settings = settings

        self._live_view: ViewState = ViewState("empty")
        """The followed run's state; what is on screen unless a past run is shown."""
        self._view: ViewState = self._live_view
        """What is on screen."""
        self._shown = False
        self._writable_key: int | None = None
        """The run that may be written. It follows the live run only after
        about_to_change was emitted, so editors can still flush the old run."""
        self._past_run: Run | None = None
        """The past run on screen, if any."""
        self._new_run = False
        self._banner: Banner | None = None

        self._loaded_path: Path | None = None
        self._loaded_mtime: datetime | None = None
        self._error: str | None = None
        self._retries = 0

        self._watcher = QFileSystemWatcher(self)
        self._watcher.fileChanged.connect(self._on_fs_change)
        self._watcher.directoryChanged.connect(self._on_fs_change)
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.timeout.connect(self._on_debounce)
        self._retry = QTimer(self)
        self._retry.setSingleShot(True)
        self._retry.timeout.connect(self._on_retry)

    @property
    def journal(self) -> Journal:
        return self._journal

    def start(self) -> None:
        self.reload()

    def view(self) -> ViewState:
        return self._view

    def banner(self) -> Banner | None:
        return self._banner

    def save_dirs(self) -> list[Path]:
        folder = self._settings.save_dir
        return [folder] if folder is not None else default_save_dirs()

    def saves(self) -> list[SaveSlot]:
        return find_saves(self.save_dirs())

    def set_save_dir(self, path: Path) -> None:
        self._settings.save_dir = path
        self._settings.follow = None  # a pinned save would override the new folder
        self._follow_changed()

    def following(self) -> Path | None:
        """The pinned save, or None when following the latest one."""
        return self._settings.follow

    def follow_latest(self) -> None:
        self._settings.follow = None
        self._follow_changed()

    def follow_path(self, path: Path) -> None:
        self._settings.follow = path
        self._follow_changed()

    # -- live and past runs ------------------------------------------------

    def live_gamekey(self) -> int | None:
        run = self._live_view.run
        return run.gamekey if run is not None else None

    def open_run(self, gamekey: int) -> None:
        """Show a past run read-only; the live run's key goes back to live."""
        if gamekey == self.live_gamekey():
            self.back_to_live()
            return
        run = self._journal.run(gamekey)
        if run is None:
            raise ValueError(f"No such run: {gamekey}")
        self._past_run = run
        self._show(ViewState("past", run, None, Location.of_run(run), editable=False))
        self._update_banner()

    def back_to_live(self) -> None:
        self._past_run = None
        self._new_run = False
        self._show(self._live_view)
        self._update_banner()

    def delete_run(self, gamekey: int) -> None:
        if gamekey == self.live_gamekey():
            raise ValueError("The live run can't be deleted")
        self._journal.delete_run(gamekey)
        if self._past_run is not None and self._past_run.gamekey == gamekey:
            self.back_to_live()

    # -- journal data ------------------------------------------------------

    def _check_writable(self, gamekey: int) -> None:
        if gamekey != self._writable_key:
            raise JournalError("Past runs are read-only")

    def run_note(self, gamekey: int) -> str:
        return self._journal.run_note(gamekey)

    def save_run_note(self, gamekey: int, body: str) -> None:
        self._check_writable(gamekey)
        self._journal.set_run_note(gamekey, body)

    def floor_note(self, gamekey: int, loc: Location) -> str:
        return self._journal.floor_note(gamekey, loc.dungeon_lvl, secret=loc.secret)

    def save_floor_note(self, gamekey: int, loc: Location, body: str) -> None:
        self._check_writable(gamekey)
        self._journal.set_floor_note(gamekey, loc.dungeon_lvl, body, secret=loc.secret)
        self.floor_note_changed.emit(gamekey, loc.dungeon_lvl, loc.secret)

    def floor_notes(self, gamekey: int) -> dict[Location, str]:
        return {
            Location(lvl, secret): body
            for (lvl, secret), body in self._journal.floor_notes(gamekey).items()
        }

    def scroll_progress(self, gamekey: int) -> ScrollProgress:
        return self._journal.scroll_progress(gamekey)

    def identify_scroll(self, gamekey: int, label: str, item_id: int) -> None:
        self._check_writable(gamekey)
        self._journal.identify_scroll(gamekey, label, item_id)
        self.scrolls_changed.emit(gamekey)

    def forget_scroll(self, gamekey: int, label: str) -> None:
        self._check_writable(gamekey)
        self._journal.forget_scroll(gamekey, label)
        self.scrolls_changed.emit(gamekey)

    def reload(self) -> None:
        """One load attempt for the followed save."""
        path = self._resolve()
        if path is None:
            self._finish_without_save()
            return
        try:
            mtime = datetime.fromtimestamp(path.stat().st_mtime)
            save = load_save(path)
        except FileNotFoundError:
            self._failed(None, True)
        except (InvalidSaveError, OSError) as exc:
            self._failed(f"Couldn't read the save: {exc}", False)
        else:
            self._loaded(path, mtime, save)
        self._sync_watches()

    # -- following ---------------------------------------------------------

    def _follow_changed(self) -> None:
        """The user changed folder or followed save: start from scratch."""
        self._loaded_path = None
        self._loaded_mtime = None
        self._retry.stop()
        self._retries = 0
        self._error = None
        self._live_view = ViewState("empty")  # a failure on the new target must not reuse the old run
        path = self._resolve()
        if path is None:
            self._show_live()
            self._update_banner()
            self._sync_watches()
        else:
            self.reload()

    def _resolve(self) -> Path | None:
        pinned = self._settings.follow
        if pinned is not None:
            return pinned
        latest = latest_save(self.save_dirs())
        if latest is None:
            return self._loaded_path
        if self._loaded_mtime is not None and latest.modified < self._loaded_mtime:
            return self._loaded_path  # latest mode never goes back to an older save
        return latest.path

    # -- outcomes ----------------------------------------------------------

    def _loaded(self, path: Path, mtime: datetime, save) -> None:
        before = self.live_gamekey()
        self._journal.record_run(save)
        run = self._journal.run(save.gamekey)
        self._loaded_path = path
        self._loaded_mtime = mtime
        self._error = None
        self._retries = 0
        self._retry.stop()
        self._live_view = ViewState(
            "live", run, save, Location.of_save(save), editable=True
        )
        if self._past_run is not None and before is not None and before != save.gamekey:
            self._new_run = True
        self._show_live()
        self._update_banner()

    def _failed(self, message: str | None, missing: bool) -> None:
        """Keep the current view; retry shortly, and give up after MAX_RETRIES."""
        if message is not None:
            has_data = self._live_view.mode != "empty"
            self._error = message + (". Showing the last good data." if has_data else "")
        if self._retries < self.MAX_RETRIES:
            self._retries += 1
            self._retry.start(self.RETRY_MS)
        elif missing and self._live_view.mode == "live" and not self._live_view.ended:
            self._error = None
            self._live_view = ViewState(
                "live",
                self._live_view.run,
                self._live_view.save,
                self._live_view.location,
                editable=True,
                ended=True,
            )
            self._show_live()
        if self._live_view.mode == "empty":
            self._show_live()  # nothing to keep: panels show the empty state
        self._update_banner()

    def _finish_without_save(self) -> None:
        if self._live_view.mode == "empty":
            self._show_live()
        self._update_banner()
        self._sync_watches()

    # -- view and banner ---------------------------------------------------

    def _show_live(self) -> None:
        """Put the live view on screen, unless a past run is shown."""
        if self._past_run is None:
            self._show(self._live_view)
        self._writable_key = self.live_gamekey()

    def _show(self, view: ViewState) -> None:
        if view == self._view and self._shown:
            return
        self.about_to_change.emit()
        self._view = view
        self._shown = True
        self.view_changed.emit(view)

    def _update_banner(self) -> None:
        """The only place the banner is computed. Priority: error > new_run > past > ended."""
        banner: Banner | None = None
        if self._error is not None:
            banner = Banner("error", self._error)
        elif self._new_run:
            banner = Banner("new_run", "New run detected.")
        elif self._past_run is not None:
            banner = Banner("past", "Viewing a past run.")
        elif self._live_view.ended:
            banner = Banner("ended", "Save no longer found: this run may have ended.")
        if banner != self._banner:
            self._banner = banner
            self.banner_changed.emit(banner)

    # -- watching ----------------------------------------------------------

    def _sync_watches(self) -> None:
        wanted: set[str] = set()
        target = self._resolve()
        if target is not None:
            wanted.add(str(target))
            wanted.add(str(target.parent))
        wanted.update(str(d) for d in self.save_dirs())
        wanted.update(str(slot.path) for slot in self.saves())
        wanted = {p for p in wanted if Path(p).exists()}
        current = set(self._watcher.files()) | set(self._watcher.directories())
        stale = list(current - wanted)
        if stale:
            self._watcher.removePaths(stale)
        missing = list(wanted - current)
        if missing:
            self._watcher.addPaths(missing)

    def _on_fs_change(self, _path: str) -> None:
        self._debounce.start(self.DEBOUNCE_MS)

    def _on_debounce(self) -> None:
        self._retries = 0
        self.reload()

    def _on_retry(self) -> None:
        self.reload()
