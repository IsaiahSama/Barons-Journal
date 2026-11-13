"""Tests for working out what each scroll label can still be, from what's been identified."""

import pytest

from barons_journal.journal import ScrollProgress
from barons_journal.reference import SCROLL_LABELS, SCROLLS, scroll_by_item_id

FIRE = scroll_by_item_id(75)  # 3 labels per run
IDENTIFY = scroll_by_item_id(69)  # 2 labels per run
MAPPING = scroll_by_item_id(77)  # 1 label per run


def progress(**by_label: int) -> ScrollProgress:
    """Build progress from label=item_id pairs, e.g. progress(**{"ZELGO MER": 75})."""
    return ScrollProgress.from_identifications(by_label)


class TestNothingIdentified:
    def test_every_label_is_unknown(self):
        p = progress()
        assert p.identified == {}
        assert p.unknown_labels == SCROLL_LABELS

    def test_every_scroll_remains_with_its_full_label_count(self):
        p = progress()
        assert p.remaining == {s: s.label_count for s in SCROLLS}

    def test_unknown_label_could_be_any_scroll(self):
        assert progress().candidates("ZELGO MER") == SCROLLS


class TestSomeIdentified:
    def test_identified_label_has_one_candidate(self):
        p = progress(**{"ZELGO MER": 75})
        assert p.identified == {"ZELGO MER": FIRE}
        assert p.candidates("ZELGO MER") == (FIRE,)

    def test_identified_label_is_no_longer_unknown(self):
        p = progress(**{"ZELGO MER": 75})
        assert "ZELGO MER" not in p.unknown_labels
        assert len(p.unknown_labels) == 24

    def test_scroll_with_more_labels_stays_a_candidate(self):
        # Fire takes 3 labels, so finding one still leaves 2 to find.
        p = progress(**{"ZELGO MER": 75})
        assert p.remaining[FIRE] == 2
        assert FIRE in p.candidates("THARR")

    def test_scroll_drops_out_once_all_its_labels_are_found(self):
        p = progress(**{"ZELGO MER": 75, "THARR": 75, "KIRJE": 75})
        assert FIRE not in p.remaining
        assert FIRE not in p.candidates("TEMOV")

    def test_single_label_scroll_drops_out_after_one(self):
        p = progress(**{"NR 9": 77})
        assert MAPPING not in p.candidates("TEMOV")

    def test_candidates_keep_item_id_order(self):
        p = progress(**{"NR 9": 77})
        ids = [s.item_id for s in p.candidates("TEMOV")]
        assert ids == sorted(ids)

    def test_identified_keeps_label_order(self):
        p = progress(**{"READ ME": 77, "ZELGO MER": 75})
        assert list(p.identified) == ["ZELGO MER", "READ ME"]


class TestInvariant:
    @pytest.mark.parametrize("found", [{}, {"ZELGO MER": 75}, {"ZELGO MER": 75, "NR 9": 77, "THARR": 69}])
    def test_remaining_label_count_equals_unknown_labels(self, found):
        # All 25 labels are used every run, so what's left to find always matches what's unknown.
        p = progress(**found)
        assert sum(p.remaining.values()) == len(p.unknown_labels)


class TestSolved:
    def _all_but_one_type(self):
        """Identify every label except those for scroll of fire."""
        found, labels = {}, iter(SCROLL_LABELS)
        for scroll in SCROLLS:
            if scroll is not FIRE:
                for _ in range(scroll.label_count):
                    found[next(labels)] = scroll.item_id
        return found, list(labels)

    def test_last_remaining_type_is_the_only_candidate(self):
        found, leftover = self._all_but_one_type()
        p = progress(**found)
        assert len(leftover) == 3
        assert all(p.candidates(label) == (FIRE,) for label in leftover)

    def test_is_complete_only_when_every_label_is_identified(self):
        found, leftover = self._all_but_one_type()
        assert not progress(**found).is_complete
        assert progress(**found, **{label: 75 for label in leftover}).is_complete


class TestValidation:
    def test_unknown_label(self):
        with pytest.raises(ValueError, match="label"):
            progress(**{"NOT A LABEL": 75})

    def test_item_that_is_not_a_scroll(self):
        with pytest.raises(ValueError, match="scroll"):
            progress(**{"ZELGO MER": 7})  # iron spear

    def test_more_labels_than_the_scroll_has(self):
        with pytest.raises(ValueError, match="scroll of identify"):
            progress(**{"ZELGO MER": 69, "THARR": 69, "KIRJE": 69})

    def test_candidates_for_unknown_label(self):
        with pytest.raises(ValueError, match="label"):
            progress().candidates("NOT A LABEL")
