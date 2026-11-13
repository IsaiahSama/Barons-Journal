import dataclasses

from PySide6.QtWidgets import QLabel

from barons_journal.data import load_save
from barons_journal.data.ids import EFFECTS, ITEMS_UNIDENTIFIED
from barons_journal.data.models import Effect, Item
from barons_journal.ui.location import Location
from barons_journal.ui.panels.backpack import BackpackPanel
from barons_journal.ui.panels.character import CharacterPanel
from barons_journal.ui.panels.kills import KillsPanel
from barons_journal.ui.state import ViewState

PANELS = (CharacterPanel, BackpackPanel, KillsPanel)


def _live(save):
    return ViewState("live", run=None, save=save, location=Location.of_save(save), editable=True)


def _with_player(save, **changes):
    return dataclasses.replace(save, player=dataclasses.replace(save.player, **changes))


def _panel(qtbot, controller, cls, save=None):
    panel = cls(controller)
    qtbot.addWidget(panel)
    if save is not None:
        panel.render(_live(save))
    return panel


def _sample(sample_save_path):
    return load_save(sample_save_path)


def test_character_sample(qtbot, controller, sample_save_path):
    panel = _panel(qtbot, controller, CharacterPanel, _sample(sample_save_path))
    assert (panel.hp_bar.value(), panel.hp_bar.maximum()) == (30, 30)
    assert (panel.mp_bar.value(), panel.mp_bar.maximum()) == (20, 20)
    assert panel.hp_bar.format() == "%v/%m"
    assert panel.skills.rowCount() == 16
    equipment = {
        panel.equipment.item(r, 0).text(): panel.equipment.item(r, 1).text()
        for r in range(panel.equipment.rowCount())
    }
    assert len(equipment) == 10
    assert equipment["Weapon"] == "iron spear"
    assert "—" in equipment.values()
    assert panel.effects_label.text() == "No active effects"


def test_effect_filtering(qtbot, controller, sample_save_path):
    save = _sample(sample_save_path)
    save = _with_player(
        save,
        effects=(Effect(id=16, strength=1, timer_ticks=500), Effect(id=2, strength=1, timer_ticks=100)),
    )
    panel = _panel(qtbot, controller, CharacterPanel, save)
    text = panel.effects_label.text()
    assert "Magic Resistance" in text
    assert "0:10" in text
    assert EFFECTS[2] not in text


def test_effect_tier_and_infinite(qtbot, controller, sample_save_path):
    save = _with_player(
        _sample(sample_save_path),
        effects=(Effect(id=16, strength=3, timer_ticks=0),),
    )
    panel = _panel(qtbot, controller, CharacterPanel, save)
    assert "Magic Resistance III" in panel.effects_label.text()
    assert "∞" in panel.effects_label.text()


def test_backpack_rows(qtbot, controller, sample_save_path):
    panel = _panel(qtbot, controller, BackpackPanel, _sample(sample_save_path))
    model = panel.table.model()
    assert [model.index(r, 0).data() for r in range(model.rowCount())] == ["bread", "fish"]
    assert [model.headerData(c, panel.table.horizontalHeader().orientation()) for c in range(4)] == [
        "Item",
        "Count",
        "Condition",
        "Blessing",
    ]
    assert panel.spells.count() == 0


def test_backpack_empty(qtbot, controller, sample_save_path):
    save = _with_player(_sample(sample_save_path), inventory=())
    panel = _panel(qtbot, controller, BackpackPanel, save)
    assert panel.empty_label.text() == "Backpack is empty"
    assert panel.empty_label.isHidden() is False


def test_kills_empty(qtbot, controller, sample_save_path):
    panel = _panel(qtbot, controller, KillsPanel, _sample(sample_save_path))
    assert panel.empty_label.text() == "No kills yet"
    assert not panel.empty_label.isHidden()


def test_kills_order(qtbot, controller, sample_save_path):
    kills = [0] * 80
    kills[1], kills[2], kills[3] = 5, 9, 5
    save = _with_player(_sample(sample_save_path), kills=tuple(kills))
    names = save.player.kills_by_monster
    panel = _panel(qtbot, controller, KillsPanel, save)
    model = panel.table.model()
    rows = [(model.index(r, 0).data(), model.index(r, 1).data()) for r in range(model.rowCount())]
    expected = sorted(names.items(), key=lambda kv: (-kv[1], kv[0]))
    assert rows == [(n[:1].upper() + n[1:], c) for n, c in expected]
    assert rows[0][1] == 9
    assert panel.empty_label.isHidden()


def test_past_and_empty_pages(qtbot, controller):
    for cls in PANELS:
        panel = _panel(qtbot, controller, cls)
        panel.render(ViewState("past"))
        label = panel.stack.currentWidget()
        assert isinstance(label, QLabel)
        assert label.text() == "Stats are only available for the live run"
        panel.render(ViewState("empty"))
        assert panel.stack.currentWidget().text() == "No run loaded"


def test_spoilers(qtbot, controller, sample_save_path, all_visible_text):
    secret = Item(
        type=75, status=3, beatitude=-2, count=1, appearance=0, identified=False, equipped=False
    )
    base = _sample(sample_save_path)
    save = _with_player(base, inventory=(*base.player.inventory, secret))
    for cls in PANELS:
        panel = _panel(qtbot, controller, cls, save)
        text = all_visible_text(panel).lower()
        assert "fire" not in text
        # identified items legitimately read "uncursed"; the secret item must not read "cursed"
        assert "cursed" not in text.replace("uncursed", "")
    backpack = _panel(qtbot, controller, BackpackPanel, save)
    assert ITEMS_UNIDENTIFIED[75] in all_visible_text(backpack)


def test_blessing_text(qtbot, controller, sample_save_path):
    base = _sample(sample_save_path)
    items = tuple(
        Item(type=base.player.inventory[-1].type, status=2, beatitude=b, count=1,
             appearance=0, identified=True, equipped=False)
        for b in (2, -1, 0)
    )
    panel = _panel(qtbot, controller, BackpackPanel, _with_player(base, inventory=items))
    model = panel.table.model()
    assert [model.index(r, 3).data() for r in range(3)] == ["+2 blessed", "-1 cursed", "uncursed"]


def test_backpack_item_column_stretches(qtbot, controller):
    from PySide6.QtWidgets import QHeaderView

    from barons_journal.ui.panels.backpack import BackpackPanel

    controller.start()
    panel = BackpackPanel(controller)
    qtbot.addWidget(panel)
    header = panel.table.horizontalHeader()
    assert header.sectionResizeMode(0) == QHeaderView.ResizeMode.Stretch
    assert header.sectionResizeMode(3) == QHeaderView.ResizeMode.ResizeToContents


def test_backpack_hides_spells_when_none(qtbot, controller):
    from barons_journal.ui.panels.backpack import BackpackPanel

    controller.start()
    panel = BackpackPanel(controller)
    qtbot.addWidget(panel)
    panel.show()
    has = panel.spells.count() > 0
    assert panel.spells.isVisible() == has and panel.spells_label.isVisible() == has
