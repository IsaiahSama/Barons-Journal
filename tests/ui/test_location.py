import pytest

from barons_journal.data import load_save
from barons_journal.ui.location import Location, location_label, snapshot_caption


@pytest.mark.parametrize(
    ("loc", "label"),
    [
        (Location(3), "Floor 3 (Mines)"),
        (Location(3, True), "Gnomish Mines · depth 3"),
        (Location(24, True), "Secret level · depth 24"),
        (Location(40), "Floor 40"),
    ],
)
def test_location_label(loc, label):
    assert location_label(loc) == label


def test_snapshot_caption_main_floor(sample_save_path):
    assert snapshot_caption(load_save(sample_save_path)) == "As of floor 0, saved 13:08"


def test_snapshot_caption_secret(secret_save):
    assert snapshot_caption(secret_save) == "As of Gnomish Mines, saved 13:46"


def test_location_of_save(secret_save):
    assert Location.of_save(secret_save) == Location(3, True)
