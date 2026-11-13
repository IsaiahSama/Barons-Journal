"""Read-only character sheet for the live run."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QAbstractItemView,
    QFormLayout,
    QLabel,
    QProgressBar,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...data.models import Effect, Equipment
from ..controller import SessionController
from ..state import ViewState

_ROMAN = {2: "II", 3: "III", 4: "IV", 5: "V"}


def effect_text(effect: Effect) -> str:
    tier = f" {_ROMAN.get(effect.strength, effect.strength)}" if effect.strength > 1 else ""
    seconds = effect.seconds_remaining
    if seconds is None:
        left = "∞"
    else:
        minutes, secs = divmod(int(seconds), 60)
        left = f"{minutes}:{secs:02d}"
    return f"{effect.name}{tier} ({left})"


def _table(columns: int, rows: int) -> QTableWidget:
    table = QTableWidget(rows, columns)
    table.horizontalHeader().setVisible(False)
    table.verticalHeader().setVisible(False)
    table.horizontalHeader().setStretchLastSection(True)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
    return table


class CharacterPanel(QWidget):
    def __init__(self, controller: SessionController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.hp_bar = QProgressBar()
        self.mp_bar = QProgressBar()
        for bar in (self.hp_bar, self.mp_bar):
            bar.setFormat("%v/%m")
        self.level_label = QLabel()
        self.gold_label = QLabel()
        self.hunger_label = QLabel()
        self.attributes = _table(2, 6)
        self.skills = _table(2, 0)
        self.equipment = _table(2, len(Equipment.slot_names()))
        self.effects_label = QLabel()
        self.effects_label.setWordWrap(True)

        content = QWidget()
        form = QFormLayout(content)
        form.addRow("HP", self.hp_bar)
        form.addRow("MP", self.mp_bar)
        form.addRow("Level", self.level_label)
        form.addRow("Gold", self.gold_label)
        form.addRow("Hunger", self.hunger_label)
        form.addRow(self.attributes)
        form.addRow(QLabel("Skills"))
        form.addRow(self.skills)
        form.addRow(QLabel("Equipment"))
        form.addRow(self.equipment)
        form.addRow(QLabel("Effects"))
        form.addRow(self.effects_label)

        self.message = QLabel()
        self.stack = QStackedWidget()
        self.stack.addWidget(content)
        self.stack.addWidget(self.message)
        layout = QVBoxLayout(self)
        layout.addWidget(self.stack)

        controller.view_changed.connect(self.render)
        self.render(controller.view())

    def render(self, view: ViewState) -> None:
        if view.mode != "live" or view.save is None:
            self.message.setText(
                "Stats are only available for the live run" if view.mode == "past" else "No run loaded"
            )
            self.stack.setCurrentWidget(self.message)
            return
        player = view.save.player
        stats = player.stats
        self.hp_bar.setMaximum(stats.max_hp)
        self.hp_bar.setValue(stats.hp)
        self.mp_bar.setMaximum(stats.max_mp)
        self.mp_bar.setValue(stats.mp)
        self.level_label.setText(f"{stats.level} ({stats.exp} exp)")
        self.gold_label.setText(str(stats.gold))
        self.hunger_label.setText(str(stats.hunger))
        attributes = (
            ("STR", stats.strength),
            ("DEX", stats.dexterity),
            ("CON", stats.constitution),
            ("INT", stats.intelligence),
            ("PER", stats.perception),
            ("CHR", stats.charisma),
        )
        self._fill(self.attributes, attributes)
        self._fill(self.skills, tuple(stats.proficiencies_by_name.items()))
        self._fill(
            self.equipment,
            tuple(
                (slot.capitalize(), item.name if item is not None else "—")
                for slot, item in player.equipment.slots()
            ),
        )
        visible = [effect_text(e) for e in player.effects if not e.hidden]
        self.effects_label.setText("\n".join(visible) if visible else "No active effects")
        self.stack.setCurrentIndex(0)

    @staticmethod
    def _fill(table: QTableWidget, rows: tuple[tuple[str, object], ...]) -> None:
        table.setRowCount(len(rows))
        for r, (key, value) in enumerate(rows):
            table.setItem(r, 0, QTableWidgetItem(key))
            table.setItem(r, 1, QTableWidgetItem(str(value)))
        table.resizeColumnToContents(0)
