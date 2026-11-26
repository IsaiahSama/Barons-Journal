"""Content shown inside the pop-out widget windows."""

from __future__ import annotations

from PySide6.QtWidgets import QFormLayout, QFrame, QLabel, QScrollArea, QWidget

from ...data import SaveFile
from ..controller import SessionController
from ..panels._stats import StatsPanel
from ..panels.character import attribute_rows, fill_table, make_bars, make_table, set_bars, skill_rows


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
