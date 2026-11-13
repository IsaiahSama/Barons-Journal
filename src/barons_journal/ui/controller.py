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
from ..journal import Journal
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
        self._follow_changed()

    def follow_latest(self) -> None:
        self._settings.follow = None
        self._follow_changed()

    def follow_path(self, path: Path) -> None:
        self._settings.follow = path
        self._follow_changed()

    def reload(self) -> None:
        """One load attempt for the followed save."""
        path = self._resolve()
        if path is None:
            self._finish_without_save()
            return
        try:
            mtime = datetime.fromtimestamp(path.stat().st_mtime)
            save = load_save(path)
        except InvalidSaveError as exc:
            self._failed(f"Couldn't read the save: {exc}. Showing the last good data.", False)
        except FileNotFoundError:
            self._failed(None, True)
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
        path = self._resolve()
        if path is None:
            self._live_view = ViewState("empty")
            self._show(self._live_view)
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
        self._show_live()
        self._update_banner()

    def _failed(self, message: str | None, missing: bool) -> None:
        """Keep the current view; retry shortly, and give up after MAX_RETRIES."""
        if message is not None:
            self._error = message
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
        self._update_banner()

    def _finish_without_save(self) -> None:
        if self._live_view.mode == "empty":
            self._show(self._live_view)
        self._update_banner()
        self._sync_watches()

    # -- view and banner ---------------------------------------------------

    def _show_live(self) -> None:
        """Put the live view on screen (Task 5: unless a past run is shown)."""
        self._show(self._live_view)

    def _show(self, view: ViewState) -> None:
        if view == self._view and self._shown:
            return
        self._view = view
        self._shown = True
        self.about_to_change.emit()
        self.view_changed.emit(view)

    def _update_banner(self) -> None:
        """The only place the banner is computed. Priority: error > ended."""
        banner: Banner | None = None
        if self._error is not None:
            banner = Banner("error", self._error)
        elif self._live_view.ended:
            banner = Banner("ended", "Save no longer found: this run may have ended.")
        if banner != self._banner:
            self._banner = banner
            self.banner_changed.emit(banner)

    # -- watching ----------------------------------------------------------

    def _sync_watches(self) -> None:
        wanted: set[str] = set()
        target = self._loaded_path or self._settings.follow
        if target is not None:
            wanted.add(str(target))
            wanted.add(str(target.parent))
        wanted.update(str(d) for d in self.save_dirs())
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
