from PySide6.QtCore import Qt

from barons_journal.data.ids import ITEMS
from barons_journal.reference import BASE_INGREDIENTS, RECIPES, SECONDARY_INGREDIENTS
from barons_journal.ui.panels.alchemy import AlchemyModel, AlchemyPanel


def _cell(model, base, secondary):
    return model.index(BASE_INGREDIENTS.index(base), SECONDARY_INGREDIENTS.index(secondary)).data()


def test_shape_and_headers():
    model = AlchemyModel()
    assert (model.rowCount(), model.columnCount()) == (6, 8)
    assert model.headerData(0, Qt.Orientation.Vertical) == "Bottle of water"


def test_water_pair_is_same():
    model = AlchemyModel()
    assert model.index(0, 0).data() == "same"


def test_polymorph_row_is_random():
    model = AlchemyModel()
    row = next(i for i, b in enumerate(BASE_INGREDIENTS) if ITEMS.label(b) == "potion of polymorph")
    cells = [model.index(row, c).data() for c in range(8)]
    poly_col = next(i for i, s in enumerate(SECONDARY_INGREDIENTS) if ITEMS.label(s) == "potion of polymorph")
    assert cells[poly_col] == "same"  # polymorph + polymorph is the same-potion rule
    assert [c for i, c in enumerate(cells) if i != poly_col] == ["random"] * 7


def test_acid_with_water_explodes():
    model = AlchemyModel()
    acid = next(b for b in BASE_INGREDIENTS if ITEMS.label(b) == "potion of acid")
    assert _cell(model, acid, SECONDARY_INGREDIENTS[0]) == "explodes"


def test_fixed_recipe_cell():
    model = AlchemyModel()
    r = RECIPES[0]
    assert _cell(model, r.base, r.secondary) == r.result_name


def test_result_combo_lists_recipes(qtbot):
    panel = AlchemyPanel()
    qtbot.addWidget(panel)
    r = RECIPES[0]
    names = [panel.result_combo.itemText(i) for i in range(panel.result_combo.count())]
    assert names == sorted({x.result_name for x in RECIPES})
    panel.result_combo.setCurrentIndex(names.index(r.result_name))
    items = [panel.recipes_list.item(i).text() for i in range(panel.recipes_list.count())]
    assert f"{r.base_name} + {r.secondary_name}" in items
