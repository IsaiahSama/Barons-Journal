"""Content shown inside the pop-out widget windows."""

from __future__ import annotations

from PySide6.QtGui import QHideEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFormLayout,
    QFrame,
    QHeaderView,
    QLabel,
    QScrollArea,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from ...data import SaveFile
from ..controller import SessionController
from ..location import Location, location_label
from ..panels.floors import FloorsModel
from ..panels._stats import StatsPanel
from ..panels.character import attribute_rows, fill_table, make_bars, make_table, set_bars, skill_rows
from ..state import ViewState
from ..widgets.note_editor import NoteEditor


def _scrolling(widget: QWidget) -> QScrollArea:
    """The shared tables size to fit every row; scroll so the window can be made smaller."""
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setWidget(widget)
    return scroll


class VitalsView(StatsPanel):
    def __init__(self, controller: SessionController, parent: QWidget | None = None) -> None:
        super().__init__(controller, parent)
        self.hp_bar, self.mp_bar = make_bars()
        self.gold_label = QLabel()
        self.hunger_label = QLabel()
        content = QWidget()
        form = QFormLayout(content)
        form.addRow("HP", self.hp_bar)
        form.addRow("MP", self.mp_bar)
        form.addRow("Gold", self.gold_label)
        form.addRow("Hunger", self.hunger_label)
        self._init_stack(content)

    def _render_live(self, save: SaveFile) -> None:
        stats = save.player.stats
        set_bars(self.hp_bar, self.mp_bar, stats)
        self.gold_label.setText(str(stats.gold))
        self.hunger_label.setText(str(stats.hunger))


class AttributesView(StatsPanel):
    def __init__(self, controller: SessionController, parent: QWidget | None = None) -> None:
        super().__init__(controller, parent)
        self.table = make_table(2, 6)
        self._init_stack(_scrolling(self.table))

    def _render_live(self, save: SaveFile) -> None:
        fill_table(self.table, attribute_rows(save.player.stats))


class SkillsView(StatsPanel):
    def __init__(self, controller: SessionController, parent: QWidget | None = None) -> None:
        super().__init__(controller, parent)
        self.table = make_table(2, 0)
        self._init_stack(_scrolling(self.table))

    def _render_live(self, save: SaveFile) -> None:
        fill_table(self.table, skill_rows(save.player.stats))


class FloorNoteView(QWidget):
    """The current floor's note, kept in sync with the other floor-note editors."""

    def __init__(self, controller: SessionController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._controller = controller
        self._bound: tuple[int, Location, bool] | None = None
        self.title = QLabel()
        self.title.setProperty("role", "section")
        self.editor = NoteEditor()
        layout = QVBoxLayout(self)
        layout.addWidget(self.title)
        layout.addWidget(self.editor, 1)
        controller.about_to_change.connect(self.flush)
        controller.view_changed.connect(self._on_view)
        controller.floor_note_changed.connect(self._on_floor_note_changed)
        self._on_view(controller.view())

    def flush(self) -> None:
        self.editor.flush()

    def hideEvent(self, event: QHideEvent) -> None:
        super().hideEvent(event)
        self.flush()

    def _on_view(self, view: ViewState) -> None:
        run, loc = view.run, view.location
        if run is None or loc is None:
            self._bound = None
            self.title.setText("Floor note")
            self.editor.bind(None, None, read_only=True)
            return
        bound = (run.gamekey, loc, view.editable)
        if bound == self._bound:
            return  # same floor: never reload text under the user's cursor
        self._bound = bound
        self.title.setText(location_label(loc))
        c, key = self._controller, run.gamekey
        self.editor.bind(
            lambda: c.floor_note(key, loc),
            lambda body: c.save_floor_note(key, loc, body),
            read_only=not view.editable,
        )

    def _on_floor_note_changed(self, gamekey: int, dungeon_lvl: int, secret: bool) -> None:
        if self._bound is not None and self._bound[:2] == (gamekey, Location(dungeon_lvl, secret)):
            self.editor.reload_if_unfocused()


class CurrentFloorView(QWidget):
    """The Floors-table row for the floor the player is on."""

    def __init__(self, controller: SessionController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.model = FloorsModel(self)
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnHidden(FloorsModel.COLUMNS.index("Note"), True)
        QVBoxLayout(self).addWidget(self.table)
        controller.view_changed.connect(self._on_view)
        self._on_view(controller.view())

    def _on_view(self, view: ViewState) -> None:
        current = view.location if view.run is not None else None
        self.model.set_state(set(), current)
        row = self.model.row_of(current) if current is not None else None
        for r in range(self.model.rowCount()):
            self.table.setRowHidden(r, r != row)
