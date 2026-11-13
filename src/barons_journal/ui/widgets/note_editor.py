"""A plain-text editor that saves itself after a pause in typing."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFocusEvent
from PySide6.QtWidgets import QPlainTextEdit


class NoteEditor(QPlainTextEdit):
    IDLE_MS = 600

    focus_lost = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._load: Callable[[], str] | None = None
        self._save: Callable[[str], None] | None = None
        self._dirty = False
        self._loading = False
        self._idle = QTimer(self)
        self._idle.setSingleShot(True)
        self._idle.timeout.connect(self.flush)
        self.textChanged.connect(self._on_text_changed)
        self.setReadOnly(True)

    def bind(
        self,
        load: Callable[[], str] | None,
        save: Callable[[str], None] | None,
        *,
        read_only: bool,
    ) -> None:
        """Flush the previous binding, then show load()'s text. None/None unbinds."""
        self.flush()
        self._load = load
        self._save = save
        self._set_text(load() if load is not None else "")
        self.setReadOnly(read_only or load is None or save is None)

    def flush(self) -> None:
        self._idle.stop()
        if not self._dirty:
            return
        if self._save is not None:
            self._save(self.toPlainText())  # if it raises, the text stays dirty
        self._dirty = False

    def reload_if_unfocused(self) -> None:
        if self._load is None or self.hasFocus() or self._dirty:
            return
        text = self._load()
        if text != self.toPlainText():
            self._set_text(text)

    def focusOutEvent(self, event: QFocusEvent) -> None:
        super().focusOutEvent(event)
        self.flush()
        if event.reason() != Qt.FocusReason.PopupFocusReason:  # e.g. the context menu
            self.focus_lost.emit()

    def _set_text(self, text: str) -> None:
        self._loading = True
        try:
            self.setPlainText(text)
        finally:
            self._loading = False
        self._dirty = False

    def _on_text_changed(self) -> None:
        if self._loading:
            return
        self._dirty = True
        self._idle.start(self.IDLE_MS)
