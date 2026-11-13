"""Tests for the scroll reference tables."""

import pytest

from barons_journal.data.ids import ITEMS, ITEMS_UNIDENTIFIED
from barons_journal.reference import SCROLL_LABELS, SCROLLS, Scroll, scroll_by_item_id

# --- Unidentified scroll labels ----------------------------------------------


def test_there_are_25_labels():
    assert len(SCROLL_LABELS) == 25  # NUMLABELS in scrolls.hpp


def test_labels_are_unique():
    assert len(set(SCROLL_LABELS)) == len(SCROLL_LABELS)


def test_labels_in_game_order():
    # Order matters: the game assigns label i to the i-th entry of a per-run shuffle.
    assert SCROLL_LABELS[0] == "ZELGO MER"
    assert SCROLL_LABELS[2] == "NR 9"
    assert SCROLL_LABELS[-1] == "READ ME"


def test_labels_are_tuple_of_strings():
    assert isinstance(SCROLL_LABELS, tuple)
    assert all(isinstance(label, str) and label for label in SCROLL_LABELS)


# --- Scroll types -------------------------------------------------------------


def test_there_are_16_scroll_types():
    assert len(SCROLLS) == 16
    assert all(isinstance(s, Scroll) for s in SCROLLS)


def test_scrolls_in_item_id_order():
    ids = [s.item_id for s in SCROLLS]
    assert ids == sorted(ids)
    assert ids == [*range(68, 82), 274, 286]


def test_every_scroll_item_is_in_the_table():
    scroll_item_ids = {i for i in range(len(ITEMS)) if ITEMS_UNIDENTIFIED.get(i) in ("scroll", "stamped scroll")}
    assert scroll_item_ids == {s.item_id for s in SCROLLS}


def test_names_match_item_table():
    for scroll in SCROLLS:
        assert scroll.name == ITEMS[scroll.item_id]


def test_label_counts_cover_every_label_exactly():
    # Each label belongs to exactly one scroll type, so the counts sum to the label total.
    assert sum(s.label_count for s in SCROLLS) == len(SCROLL_LABELS)
    assert all(s.label_count >= 1 for s in SCROLLS)


@pytest.mark.parametrize(
    ("item_id", "name", "value", "weight", "label_count", "effect"),
    [
        (75, "scroll of fire", 35, 2, 3, "Summons flames at current location"),
        (79, "scroll of destroy armor", 50, 2, 3, "Destroys a random piece of worn armor"),
        (69, "scroll of identify", 35, 2, 2, "Identifies a chosen piece of equipment"),
        (72, "scroll of enchant weapon", 300, 2, 1, "Blesses a chosen piece of Main-hand equipment"),
        (286, "scroll of conjure arrow", 90, 5, 1, "Conjures ranged weapon ammunition"),
        (68, "piece of mail", 10, 1, 1, "A letter addressed to someone else."),
        (71, "blank scroll", 50, 2, 1, "No effect. Can be inscribed to imbue magical effects."),
    ],
)
def test_known_scrolls(item_id, name, value, weight, label_count, effect):
    scroll = scroll_by_item_id(item_id)
    assert scroll.name == name
    assert scroll.value == value
    assert scroll.weight == weight
    assert scroll.label_count == label_count
    assert scroll.effect == effect


def test_effects_have_no_markup_or_line_breaks():
    for scroll in SCROLLS:
        assert "[" not in scroll.effect and "\n" not in scroll.effect, scroll


def test_unknown_item_id_raises_key_error():
    with pytest.raises(KeyError):
        scroll_by_item_id(7)  # iron spear


def test_scroll_is_immutable():
    with pytest.raises(AttributeError):
        SCROLLS[0].value = 1
