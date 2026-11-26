"""The Map widget: a see-through frame laid over the game's map, with markers dropped on it."""

from __future__ import annotations

from dataclasses import dataclass
from importlib.resources import files
from importlib.resources.abc import Traversable

from PySide6.QtCore import QPoint, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QMouseEvent, QPainter, QPaintEvent, QPalette, QPen, QResizeEvent
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QHBoxLayout, QSizeGrip, QToolButton, QVBoxLayout, QWidget

from ..controller import SessionController
from ..location import Location
from ..state import ViewState

MARKER_KINDS: tuple[tuple[str, str], ...] = (
    ("weapon", "Weapon"),
    ("armour", "Armour"),
    ("item", "Item"),
    ("key", "Key"),
    ("door", "Door"),
    ("boss", "Strong enemy"),
    ("chest", "Chest"),
)
MARKER_SIZE = 24


def icon_path(kind: str) -> Traversable:
    return files(__package__) / "icons" / f"{kind}.svg"


@dataclass
class Marker:
    kind: str
    x: float  # fractions of the canvas, 0..1, so markers follow the map when the frame is resized
    y: float


def _clamp(v: float) -> float:
    return min(max(v, 0.0), 1.0)


class MapCanvas(QWidget):
    """The see-through region. Markers live in memory only."""

    placed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.markers: list[Marker] = []
        self.kind: str | None = None
        self._dragging: int | None = None
        self._renderers = {k: QSvgRenderer(str(icon_path(k)), self) for k, _ in MARKER_KINDS}
        self.setMinimumSize(80, 60)

    def marker_center(self, i: int) -> QPoint:
        m = self.markers[i]
        return QPoint(round(m.x * self.width()), round(m.y * self.height()))

    def marker_at(self, pos: QPoint) -> int | None:
        half = MARKER_SIZE / 2
        for i in reversed(range(len(self.markers))):  # topmost (last placed) first
            c = self.marker_center(i)
            if abs(pos.x() - c.x()) <= half and abs(pos.y() - c.y()) <= half:
                return i
        return None

    def clear(self) -> None:
        self.markers.clear()
        self._dragging = None
        self.update()

    def _fraction(self, pos: QPoint) -> tuple[float, float]:
        return _clamp(pos.x() / max(self.width(), 1)), _clamp(pos.y() / max(self.height(), 1))

    def mousePressEvent(self, event: QMouseEvent) -> None:
        pos = event.position().toPoint()
        hit = self.marker_at(pos)
        if event.button() == Qt.MouseButton.RightButton:
            if hit is not None:
                del self.markers[hit]
                self._dragging = None  # its index may now point past the end, or at another marker
                self.update()
        elif event.button() == Qt.MouseButton.LeftButton:
            if hit is not None:
                self._dragging = hit
            elif self.kind is not None:
                self.markers.append(Marker(self.kind, *self._fraction(pos)))
                self.update()
                self.placed.emit()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        # Tracked by index rather than event.buttons(): QTest.mouseMove sends no buttons.
        if self._dragging is not None:
            m = self.markers[self._dragging]
            m.x, m.y = self._fraction(event.position().toPoint())
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._dragging = None

    def paintEvent(self, event: QPaintEvent) -> None:
        p = QPainter(self)
        # Not alpha 0: Windows layered windows let clicks fall through fully transparent pixels.
        p.fillRect(self.rect(), QColor(0, 0, 0, 1))
        p.setPen(QPen(self.palette().color(QPalette.ColorRole.BrightText), 2))
        p.drawRect(self.rect().adjusted(1, 1, -1, -1))
        half = MARKER_SIZE / 2
        for i, m in enumerate(self.markers):
            c = self.marker_center(i)
            self._renderers[m.kind].render(p, QRectF(c.x() - half, c.y() - half, MARKER_SIZE, MARKER_SIZE))


class _Strip(QWidget):
    """The top bar: holds the marker buttons and moves the window, which has no title bar."""

    def mousePressEvent(self, event: QMouseEvent) -> None:
        handle = self.window().windowHandle()
        if event.button() == Qt.MouseButton.LeftButton and handle is not None:
            handle.startSystemMove()  # COSMIC ignores move(), so let the compositor do it


class MapView(QWidget):
    def __init__(self, controller: SessionController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._floor: tuple[int | None, Location | None] = (None, None)
        self.strip = _Strip()
        self.strip.setAutoFillBackground(True)  # opaque while the window itself is translucent
        bar = QHBoxLayout(self.strip)
        bar.setContentsMargins(4, 2, 4, 2)
        bar.setSpacing(2)
        self.buttons: dict[str, QToolButton] = {}
        for kind, label in MARKER_KINDS:
            b = QToolButton()
            b.setIcon(QIcon(str(icon_path(kind))))
            b.setToolTip(label)
            b.setAccessibleName(label)
            b.setCheckable(True)
            b.setAutoRaise(True)
            b.toggled.connect(lambda on, k=kind: self._arm(k, on))
            bar.addWidget(b)
            self.buttons[kind] = b
        bar.addStretch(1)
        self.clear_button = QToolButton()
        self.clear_button.setText("Clear")
        self.clear_button.setToolTip("Clear markers")
        self.clear_button.setAutoRaise(True)
        bar.addWidget(self.clear_button)
        self.canvas = MapCanvas()
        self.canvas.placed.connect(self._disarm)
        self.clear_button.clicked.connect(self.canvas.clear)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.strip)
        layout.addWidget(self.canvas, 1)
        self._grip = QSizeGrip(self)
        controller.view_changed.connect(self.render)
        self.render(controller.view())

    def _arm(self, kind: str, on: bool) -> None:
        if on:
            for k, b in self.buttons.items():
                if k != kind:
                    b.setChecked(False)
            self.canvas.kind = kind
        elif self.canvas.kind == kind:
            self.canvas.kind = None

    def _disarm(self) -> None:
        if self.canvas.kind is not None:
            self.buttons[self.canvas.kind].setChecked(False)

    def render(self, view: ViewState) -> None:
        # The player can't go back to a floor, so its markers go when the floor (or run) changes.
        # Browsing a past run leaves the live floor's markers alone.
        if view.mode == "past":
            return
        floor = (view.run.gamekey if view.run else None, view.location)
        if floor != self._floor:
            self.canvas.clear()
            self._floor = floor

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        hint = self._grip.sizeHint()
        self._grip.move(self.width() - hint.width(), self.height() - hint.height())
        self._grip.raise_()
