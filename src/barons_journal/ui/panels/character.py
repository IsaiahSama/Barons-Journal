"""Read-only character sheet for the live run."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFormLayout,
    QFrame,
    QScrollArea,
    QLabel,
    QProgressBar,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from ...data import SaveFile, Stats
from ...data.models import Effect, Equipment
from ._stats import StatsPanel

if TYPE_CHECKING:
    from ..controller import SessionController

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


def make_table(columns: int, rows: int) -> QTableWidget:
    table = QTableWidget(rows, columns)
    table.horizontalHeader().setVisible(False)
    table.verticalHeader().setVisible(False)
    table.horizontalHeader().setStretchLastSection(True)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
    table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    _fit_height(table)
    return table


def _section(text: str) -> QLabel:
    label = QLabel(text)
    label.setProperty("role", "section")
    return label


def _fit_height(table: QTableWidget) -> None:
    """Show every row: the panel scrolls as a whole instead of each table."""
    rows = sum(table.rowHeight(r) for r in range(table.rowCount()))
    table.setFixedHeight(rows + 2 * table.frameWidth())


def fill_table(table: QTableWidget, rows: tuple[tuple[str, object], ...]) -> None:
    table.setRowCount(len(rows))
    for r, (key, value) in enumerate(rows):
        table.setItem(r, 0, QTableWidgetItem(key))
        table.setItem(r, 1, QTableWidgetItem(str(value)))
    table.resizeColumnToContents(0)
    table.resizeRowsToContents()
    _fit_height(table)


def make_bars() -> tuple[QProgressBar, QProgressBar]:
    hp, mp = QProgressBar(), QProgressBar()
    hp.setObjectName("hpBar")
    mp.setObjectName("mpBar")
    for bar in (hp, mp):
        bar.setFormat("%v/%m")
    return hp, mp


def set_bars(hp: QProgressBar, mp: QProgressBar, stats: Stats) -> None:
    hp.setMaximum(stats.max_hp)
    hp.setValue(stats.hp)
    mp.setMaximum(stats.max_mp)
    mp.setValue(stats.mp)


GOLD_FULL = 10000
HUNGER_FULL = 1000


def make_meters() -> tuple[QProgressBar, QProgressBar]:
    """Gold and hunger bars (object names goldBar/hungerBar)."""
    gold, hunger = QProgressBar(), QProgressBar()
    gold.setObjectName("goldBar")
    hunger.setObjectName("hungerBar")
    gold.setMaximum(GOLD_FULL)
    hunger.setMaximum(HUNGER_FULL)
    return gold, hunger


def set_meters(gold: QProgressBar, hunger: QProgressBar, stats: Stats) -> None:
    # QProgressBar ignores values above its maximum: cap the bar, show the real number.
    gold.setValue(min(stats.gold, GOLD_FULL))
    gold.setFormat(str(stats.gold))
    hunger.setValue(min(stats.hunger, HUNGER_FULL))
    hunger.setFormat(f"{stats.hunger}/{HUNGER_FULL}")


def attribute_rows(stats: Stats) -> tuple[tuple[str, int], ...]:
    return (
        ("STR", stats.strength),
        ("DEX", stats.dexterity),
        ("CON", stats.constitution),
        ("INT", stats.intelligence),
        ("PER", stats.perception),
        ("CHR", stats.charisma),
    )


def skill_rows(stats: Stats) -> tuple[tuple[str, int], ...]:
    return tuple(stats.proficiencies_by_name.items())


class CharacterPanel(StatsPanel):
    def __init__(self, controller: SessionController, parent: QWidget | None = None) -> None:
        super().__init__(controller, parent)
        self.hp_bar, self.mp_bar = make_bars()
        self.level_label = QLabel()
        self.gold_bar, self.hunger_bar = make_meters()
        self.attributes = make_table(2, 6)
        self.skills = make_table(2, 0)
        self.equipment = make_table(2, len(Equipment.slot_names()))
        self.effects_label = QLabel()
        self.effects_label.setWordWrap(True)

        content = QWidget()
        form = QFormLayout(content)
        form.addRow("HP", self.hp_bar)
        form.addRow("MP", self.mp_bar)
        form.addRow("Level", self.level_label)
        form.addRow("Gold", self.gold_bar)
        form.addRow("Hunger", self.hunger_bar)
        form.addRow(self.attributes)
        form.addRow(_section("Skills"))
        form.addRow(self.skills)
        form.addRow(_section("Equipment"))
        form.addRow(self.equipment)
        form.addRow(_section("Effects"))
        form.addRow(self.effects_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(content)
        self.scroll = scroll

        self._init_stack(scroll)

    def _render_live(self, save: SaveFile) -> None:
        player = save.player
        stats = player.stats
        set_bars(self.hp_bar, self.mp_bar, stats)
        self.level_label.setText(f"{stats.level} ({stats.exp} exp)")
        set_meters(self.gold_bar, self.hunger_bar, stats)
        fill_table(self.attributes, attribute_rows(stats))
        fill_table(self.skills, skill_rows(stats))
        fill_table(
            self.equipment,
            tuple(
                (slot.capitalize(), item.name if item is not None else "—")
                for slot, item in player.equipment.slots()
            ),
        )
        visible = [effect_text(e) for e in player.effects if not e.hidden]
        self.effects_label.setText("\n".join(visible) if visible else "No active effects")
