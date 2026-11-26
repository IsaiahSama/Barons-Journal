"""The pop-out widget windows: creating, toggling, and remembering them."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QVBoxLayout, QWidget

from ..controller import SessionController
from ..settings import AppSettings
from .views import AttributesView, CurrentFloorView, FloorNoteView, SkillsView, VitalsView

POPOUTS: tuple[tuple[str, str], ...] = (
    ("vitals", "Vitals"),
    ("attributes", "Attributes"),
    ("skills", "Skills"),
    ("floor_note", "Floor note"),
    ("current_floor", "Current floor"),
)

_VIEWS: dict[str, Callable[[SessionController], QWidget]] = {
    "vitals": VitalsView,
    "attributes": AttributesView,
    "skills": SkillsView,
    "floor_note": FloorNoteView,
    "current_floor": CurrentFloorView,
}


class PopoutWindow(QWidget):
    """A floating, always-on-top window around one view.

    Dialog, not Tool: COSMIC tiles Tool windows but floats dialogs. No parent, so minimising
    the main window leaves the widgets up.
    """

    closed = Signal(str)

    def __init__(self, key: str, title: str, content: QWidget) -> None:
        super().__init__(None, Qt.WindowType.Dialog | Qt.WindowType.WindowStaysOnTopHint)
        self.key = key
        self.content = content
        self.setWindowTitle(f"{title} · Baron's Journal")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(content)

    def closeEvent(self, event: QCloseEvent) -> None:
        super().closeEvent(event)
        self.closed.emit(self.key)


class PopoutManager(QObject):
    open_changed = Signal(str, bool)

    def __init__(self, controller: SessionController, settings: AppSettings) -> None:
        super().__init__()
        self._controller = controller
        self._settings = settings
        self._titles = dict(POPOUTS)
        self._windows: dict[str, PopoutWindow] = {}
        self._quitting = False

    def window(self, key: str) -> PopoutWindow | None:
        return self._windows.get(key)

    def is_open(self, key: str) -> bool:
        w = self._windows.get(key)
        return w is not None and w.isVisible()

    def set_open(self, key: str, on: bool) -> None:
        if on == self.is_open(key):
            return
        if not on:
            self._windows[key].close()  # _on_closed records it
            return
        w = self._windows.get(key)
        if w is None:
            w = PopoutWindow(key, self._titles[key], _VIEWS[key](self._controller))
            geometry = self._settings.popout_geometry(key)
            if geometry is not None:
                w.restoreGeometry(geometry)
            w.closed.connect(self._on_closed)
            self._windows[key] = w
        self._settings.set_popout_open(key, True)
        w.show()
        w.raise_()
        self.open_changed.emit(key, True)

    def restore(self) -> None:
        for key, _title in POPOUTS:
            if self._settings.popout_open(key):
                self.set_open(key, True)

    def shutdown(self) -> None:
        """Close every widget but remember it as open, so it comes back next launch."""
        self._quitting = True
        for key, w in self._windows.items():
            if w.isVisible():
                self._settings.set_popout_geometry(key, w.saveGeometry())
                w.close()

    def _on_closed(self, key: str) -> None:
        if self._quitting:
            return
        self._settings.set_popout_geometry(key, self._windows[key].saveGeometry())
        self._settings.set_popout_open(key, False)
        self.open_changed.emit(key, False)
