"""The Map widget: a see-through frame laid over the game's map, with markers dropped on it."""

from __future__ import annotations

from dataclasses import dataclass
from importlib.resources import files
from importlib.resources.abc import Traversable

from PySide6.QtCore import QPoint, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPaintEvent, QPalette, QPen
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QWidget

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
