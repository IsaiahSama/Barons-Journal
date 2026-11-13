"""Floor reference table with secret levels, plus a note for the selected floor."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QItemSelectionModel, QModelIndex, QPersistentModelIndex, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPalette
from PySide6.QtWidgets import (
    QAbstractItemView,
    QLabel,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from ...reference import FLOORS, floor_at, secret_level_at
from ..location import Location
from ..state import ViewState
from ..widgets.note_editor import NoteEditor
from ._stats import ColumnsModel

if TYPE_CHECKING:
    from ..controller import SessionController

_Index = QModelIndex | QPersistentModelIndex

NOTE_MARK = "📝"


def _locations() -> list[Location]:
    rows: list[Location] = []
    for floor in FLOORS:
        n = floor.dungeon_lvl
        rows.append(Location(n))
        if secret_level_at(n) is not None:
            rows.append(Location(n, True))
    return rows


class FloorsModel(ColumnsModel):
    COLUMNS = ("Floor", "Area", "Secret entrance", "Leads to", "Artifacts", "Orb", "Note")

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._rows = _locations()
        self._row_of = {loc: i for i, loc in enumerate(self._rows)}
        self._noted: set[Location] = set()
        self._current: Location | None = None

    def _row_count(self) -> int:
        return len(self._rows)

    def location_at(self, row: int) -> Location:
        return self._rows[row]

    def row_of(self, loc: Location) -> int | None:
        return self._row_of.get(loc)

    def set_state(self, noted: set[Location], current: Location | None) -> None:
        self._noted = noted
        self._current = current
        if self._rows:
            self.dataChanged.emit(
                self.index(0, 0), self.index(len(self._rows) - 1, len(self.COLUMNS) - 1)
            )

    def _cell(self, loc: Location, column: str) -> str:
        n = loc.dungeon_lvl
        if column == "Note":
            return NOTE_MARK if loc in self._noted else ""
        if loc.secret:
            secret = secret_level_at(n)
            if column == "Floor":
                return f"↳ {n}"
            if column == "Area":
                return secret.name
            if column == "Artifacts":
                return ", ".join(secret.artifact_names)
            return ""
        floor = floor_at(n)
        target = floor.secret_entrance
        if column == "Floor":
            return str(n)
        if column == "Area":
            return floor.area
        if column == "Secret entrance":
            chance = floor.secret_entrance_chance
            if chance is None:
                return ""
            return "Yes" if chance >= 1.0 else f"{round(chance * 100)}%"
        if column == "Leads to":
            return target.name if target else ""
        if column == "Artifacts":
            return ", ".join(target.artifact_names) if target else ""
        if column == "Orb":
            return floor.orb_name or ""
        return ""

    def data(self, index: _Index, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        loc = self._rows[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return self._cell(loc, self.COLUMNS[index.column()])
        if loc == self._current:
            if role == Qt.ItemDataRole.FontRole:
                font = QFont()
                font.setBold(True)
                return font
            if role == Qt.ItemDataRole.BackgroundRole:
                color = QColor(QPalette().color(QPalette.ColorRole.Highlight))
                color.setAlpha(50)
                return QBrush(color)
        return None


class FloorsPanel(QWidget):
    def __init__(self, controller: SessionController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._controller = controller
        self._view = controller.view()
        self._bound: tuple[int, Location, bool] | None = None
        self._selecting = False
        self._user_choice = False
        self._run_key: tuple[int, str] | None = None

        self.model = FloorsModel(self)
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().hide()
        self.treasures = QLabel()
        self.treasures.setWordWrap(True)
        self.note_editor = NoteEditor()

        layout = QVBoxLayout(self)
        layout.addWidget(self.table, 3)
        layout.addWidget(self.treasures)
        layout.addWidget(self.note_editor, 1)

        self.table.selectionModel().currentRowChanged.connect(self._on_current_row)
        controller.about_to_change.connect(self.note_editor.flush)
        controller.view_changed.connect(self.render)
        controller.floor_note_changed.connect(self._on_floor_note_changed)
        self.render(controller.view())

    def select(self, loc: Location) -> None:
        row = self.model.row_of(loc)
        if row is None:
            return
        self._selecting = True
        try:
            self.table.selectionModel().setCurrentIndex(
                self.model.index(row, 0),
                QItemSelectionModel.SelectionFlag.ClearAndSelect
                | QItemSelectionModel.SelectionFlag.Rows,
            )
        finally:
            self._selecting = False
        self._bind(loc)

    def render(self, view: ViewState) -> None:
        self._view = view
        run = view.run
        key = (run.gamekey, view.mode) if run is not None else None
        if key != self._run_key:
            self._run_key = key
            self._user_choice = False
        current = view.location if run is not None else None
        self._refresh_notes(current)
        if run is None or current is None:
            self.table.selectionModel().clearSelection()
            self.table.setCurrentIndex(QModelIndex())
            self._bind(None)
            return
        if not self._user_choice:
            self.select(current)
        else:
            self._bind(self._selected_location())

    def _refresh_notes(self, current: Location | None = None) -> None:
        run = self._view.run
        noted: set[Location] = set()
        if run is not None:
            noted = {
                loc for loc, body in self._controller.floor_notes(run.gamekey).items() if body
            }
        if current is None and run is not None:
            current = self._view.location
        self.model.set_state(noted, current if run is not None else None)

    def _selected_location(self) -> Location | None:
        index = self.table.currentIndex()
        return self.model.location_at(index.row()) if index.isValid() else None

    def _on_current_row(self, current: QModelIndex, _previous: QModelIndex) -> None:
        if self._selecting or not current.isValid():
            return
        self._user_choice = True
        self._bind(self.model.location_at(current.row()))

    def _bind(self, loc: Location | None) -> None:
        view = self._view
        run = view.run
        if run is None or loc is None:
            self._bound = None
            self.treasures.setText("")
            self.note_editor.bind(None, None, read_only=True)
            return
        secret = secret_level_at(loc.dungeon_lvl) if loc.secret else None
        self.treasures.setText("\n".join(secret.treasures) if secret else "")
        bound = (run.gamekey, loc, view.editable)
        if bound == self._bound:
            return
        self._bound = bound
        c, key = self._controller, run.gamekey
        self.note_editor.bind(
            lambda: c.floor_note(key, loc),
            lambda body: c.save_floor_note(key, loc, body),
            read_only=not view.editable,
        )

    def _on_floor_note_changed(self, gamekey: int, dungeon_lvl: int, secret: bool) -> None:
        self._refresh_notes()
        if self._bound is not None and self._bound[:2] == (gamekey, Location(dungeon_lvl, secret)):
            self.note_editor.reload_if_unfocused()
