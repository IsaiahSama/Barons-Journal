import pytest

from barons_journal.data import load_save
from barons_journal.ui.location import Location
from barons_journal.ui.panels._stats import EMPTY_MESSAGE, PAST_MESSAGE
from barons_journal.ui.popouts.views import AttributesView, SkillsView, VitalsView
from barons_journal.ui.state import ViewState


def _live(save):
    return ViewState("live", run=None, save=save, location=Location.of_save(save), editable=True)


def _view(qtbot, controller, cls, save=None):
    v = cls(controller)
    qtbot.addWidget(v)
    if save is not None:
        v.render(_live(save))
    return v


def test_vitals_live(qtbot, controller, sample_save_path):
    v = _view(qtbot, controller, VitalsView, load_save(sample_save_path))
    assert (v.hp_bar.value(), v.hp_bar.maximum()) == (30, 30)
    assert (v.mp_bar.value(), v.mp_bar.maximum()) == (20, 20)
    assert v.hp_bar.objectName() == "hpBar" and v.mp_bar.objectName() == "mpBar"
    assert v.hp_bar.format() == "%v/%m"
    assert v.gold_label.text() == "0" and v.hunger_label.text() == "1000"


def test_attributes_live(qtbot, controller, sample_save_path):
    v = _view(qtbot, controller, AttributesView, load_save(sample_save_path))
    assert v.table.rowCount() == 6
    assert (v.table.item(0, 0).text(), v.table.item(0, 1).text()) == ("STR", "1")
    assert v.table.item(5, 0).text() == "CHR"


def test_skills_live(qtbot, controller, sample_save_path):
    v = _view(qtbot, controller, SkillsView, load_save(sample_save_path))
    assert v.table.rowCount() == 16


@pytest.mark.parametrize("cls", [VitalsView, AttributesView, SkillsView])
def test_not_live_shows_message(qtbot, controller, cls):
    v = _view(qtbot, controller, cls)
    v.render(ViewState("past"))
    assert v.message.text() == PAST_MESSAGE
    v.render(ViewState("empty"))
    assert v.message.text() == EMPTY_MESSAGE
