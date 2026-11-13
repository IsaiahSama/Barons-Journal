"""The run note and the floor note, side by side."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..controller import SessionController
from ..location import Location, location_label
from ..state import ViewState
from ..widgets.note_editor import NoteEditor


class NotesPanel(QWidget):
    def __init__(self, controller: SessionController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._controller = controller
        self._bound_run: tuple[int, str, bool] | None = None
        self._showing: Location | None = None
        self._pending: ViewState | None = None
        """A view for a new floor, waiting for the user to switch."""

        self.floor_title = QLabel()
        self.floor_editor = NoteEditor()
        self.switch_label = QLabel()
        self.switch_button = QPushButton("Switch")
        self.switch_prompt = QWidget()
        prompt = QHBoxLayout(self.switch_prompt)
        prompt.setContentsMargins(0, 0, 0, 0)
        prompt.addWidget(self.switch_label, 1)
        prompt.addWidget(self.switch_button)
        self.switch_prompt.hide()
        self.run_editor = NoteEditor()

        layout = QVBoxLayout(self)
        layout.addWidget(self.floor_title)
        layout.addWidget(self.switch_prompt)
        layout.addWidget(self.floor_editor, 1)
        layout.addWidget(QLabel("Run notes"))
        layout.addWidget(self.run_editor, 1)

        self.switch_button.clicked.connect(self._switch)
        self.floor_editor.focus_lost.connect(self._switch)
        controller.about_to_change.connect(self.flush)
        controller.view_changed.connect(self._on_view)
        controller.floor_note_changed.connect(self._on_floor_note_changed)
        self._rebind(controller.view())

    def showing_location(self) -> Location | None:
        return self._showing

    def flush(self) -> None:
        self.floor_editor.flush()
        self.run_editor.flush()

    def _floor_editor_active(self) -> bool:
        return self.floor_editor.hasFocus()

    def _on_view(self, view: ViewState) -> None:
        same_run = (
            self._bound_run is not None
            and view.run is not None
            and (view.run.gamekey, view.mode) == self._bound_run[:2]
        )
        if (
            same_run
            and view.location != self._showing
            and self._showing is not None
            and self._floor_editor_active()
        ):
            self.flush()
            self._pending = view
            self.switch_label.setText(f"Now on {location_label(view.location)}")
            self.switch_prompt.show()
            return
        self._rebind(view)

    def _switch(self) -> None:
        if self._pending is not None:
            self._rebind(self._pending)

    def _rebind(self, view: ViewState) -> None:
        self._pending = None
        self.switch_prompt.hide()
        run = view.run
        if run is None or view.location is None:
            self._bound_run = None
            self._showing = None
            self.floor_title.setText("Floor notes")
            self.floor_editor.bind(None, None, read_only=True)
            self.run_editor.bind(None, None, read_only=True)
            return
        c = self._controller
        key, loc, read_only = run.gamekey, view.location, not view.editable
        self._bound_run = (key, view.mode, view.editable)
        self._showing = loc
        self.floor_title.setText(f"{location_label(loc)} notes")
        self.floor_editor.bind(
            lambda: c.floor_note(key, loc),
            lambda body: c.save_floor_note(key, loc, body),
            read_only=read_only,
        )
        self.run_editor.bind(
            lambda: c.run_note(key),
            lambda body: c.save_run_note(key, body),
            read_only=read_only,
        )

    def _on_floor_note_changed(self, gamekey: int, dungeon_lvl: int, secret: bool) -> None:
        shown = self._showing
        if (
            shown == Location(dungeon_lvl, secret)
            and self._bound_run is not None
            and self._bound_run[0] == gamekey
        ):
            self.floor_editor.reload_if_unfocused()
