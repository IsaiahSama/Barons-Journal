import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtTest import QTest

from barons_journal.ui.location import Location
from barons_journal.ui.popouts.map import MARKER_KINDS, MapCanvas, MapView, Marker, icon_path
from barons_journal.ui.state import ViewState

LEFT, RIGHT = Qt.MouseButton.LeftButton, Qt.MouseButton.RightButton


@pytest.fixture
def canvas(qtbot):
    c = MapCanvas()
    qtbot.addWidget(c)
    c.resize(200, 100)
    return c


def _place(c, kind, x, y):
    c.kind = kind
    QTest.mouseClick(c, LEFT, pos=QPoint(x, y))


def test_icons_are_valid_svgs():
    assert [k for k, _ in MARKER_KINDS] == ["weapon", "armour", "item", "key", "door", "boss", "chest"]
    for kind, _ in MARKER_KINDS:
        assert QSvgRenderer(str(icon_path(kind))).isValid(), kind


def test_click_places_armed_kind(canvas):
    placed = []
    canvas.placed.connect(lambda: placed.append(1))
    _place(canvas, "key", 50, 25)
    assert canvas.markers == [Marker("key", 0.25, 0.25)]
    assert placed == [1]


def test_click_unarmed_does_nothing(canvas):
    QTest.mouseClick(canvas, LEFT, pos=QPoint(50, 25))
    assert canvas.markers == []


def test_markers_scale_with_resize(canvas):
    _place(canvas, "key", 50, 25)
    canvas.resize(400, 200)
    assert canvas.marker_center(0) == QPoint(100, 50)


def test_right_click_removes_topmost(canvas):
    canvas.markers = [Marker("key", 0.25, 0.25), Marker("chest", 0.25, 0.25)]
    QTest.mouseClick(canvas, RIGHT, pos=QPoint(50, 25))
    assert [m.kind for m in canvas.markers] == ["key"]


def test_right_click_on_empty_does_nothing(canvas):
    canvas.markers = [Marker("key", 0.25, 0.25)]
    QTest.mouseClick(canvas, RIGHT, pos=QPoint(180, 80))
    assert len(canvas.markers) == 1


def _drag(c, start, end):
    QTest.mousePress(c, LEFT, pos=start)
    QTest.mouseMove(c, end)
    QTest.mouseRelease(c, LEFT, pos=end)


def test_drag_moves_marker_and_clamps(canvas):
    canvas.markers = [Marker("key", 0.25, 0.25)]
    _drag(canvas, QPoint(50, 25), QPoint(150, 75))
    assert canvas.markers == [Marker("key", 0.75, 0.75)]
    _drag(canvas, QPoint(150, 75), QPoint(300, -20))
    assert canvas.markers == [Marker("key", 1.0, 0.0)]


def test_move_after_release_does_not_drag(canvas):
    canvas.markers = [Marker("key", 0.25, 0.25)]
    _drag(canvas, QPoint(50, 25), QPoint(50, 25))
    QTest.mouseMove(canvas, QPoint(150, 75))
    assert canvas.markers == [Marker("key", 0.25, 0.25)]


def test_press_on_marker_while_armed_drags_not_places(canvas):
    canvas.markers = [Marker("key", 0.25, 0.25)]
    canvas.kind = "chest"
    _drag(canvas, QPoint(50, 25), QPoint(150, 75))
    assert canvas.markers == [Marker("key", 0.75, 0.75)]


def test_clear(canvas):
    _place(canvas, "key", 50, 25)
    canvas.clear()
    assert canvas.markers == []


def test_paints_without_error(canvas):
    canvas.markers = [Marker(k, 0.5, 0.5) for k, _ in MARKER_KINDS]
    assert not canvas.grab().isNull()


@pytest.fixture
def view(qtbot, controller):
    v = MapView(controller)
    qtbot.addWidget(v)
    v.resize(300, 250)
    v.show()
    return v


def _at(location):
    return ViewState("live", run=None, save=None, location=location, editable=True)


def test_buttons_in_order_with_tooltips(view):
    assert list(view.buttons) == [k for k, _ in MARKER_KINDS]
    assert view.buttons["boss"].toolTip() == "Strong enemy"
    assert view.buttons["key"].toolTip() == "Key"


def test_button_arms_and_disarms(view):
    view.buttons["key"].click()
    assert view.canvas.kind == "key"
    view.buttons["chest"].click()
    assert view.canvas.kind == "chest" and not view.buttons["key"].isChecked()
    view.buttons["chest"].click()
    assert view.canvas.kind is None


def test_placing_disarms(view):
    view.buttons["key"].click()
    QTest.mouseClick(view.canvas, LEFT, pos=QPoint(40, 40))
    assert len(view.canvas.markers) == 1
    assert view.canvas.kind is None and not view.buttons["key"].isChecked()


def test_floor_change_clears_same_floor_keeps(view):
    view.render(_at(Location(3)))
    view.canvas.markers = [Marker("key", 0.5, 0.5)]
    view.render(_at(Location(3)))
    assert len(view.canvas.markers) == 1
    view.render(_at(Location(3, secret=True)))
    assert view.canvas.markers == []
    view.canvas.markers = [Marker("key", 0.5, 0.5)]
    view.render(_at(None))
    assert view.canvas.markers == []
