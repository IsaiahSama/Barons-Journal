import copy
import json
from pathlib import Path

import pytest

SAMPLE_SAVE = Path(__file__).parent / "save_file_example.baronsave"
SECRET_SAVE = Path(__file__).parent / "save_file_secret_level.baronsave"


@pytest.fixture(scope="session")
def _sample_raw() -> dict:
    return json.loads(SAMPLE_SAVE.read_text(encoding="utf-8"))


@pytest.fixture
def sample_save_path() -> Path:
    """Path to the real Barony save checked into the repo."""
    return SAMPLE_SAVE


@pytest.fixture
def secret_save_path() -> Path:
    """Path to a real save taken inside a secret level (Gnomish Mines)."""
    return SECRET_SAVE


@pytest.fixture
def raw_save(_sample_raw) -> dict:
    """A fresh, mutable copy of the sample save's raw JSON dict."""
    return copy.deepcopy(_sample_raw)


@pytest.fixture
def write_save(tmp_path):
    """Write a raw save dict (or raw text) to a temp .baronsave file and return its path."""

    def _write(content: dict | str, name: str = "test.baronsave") -> Path:
        path = tmp_path / name
        text = content if isinstance(content, str) else json.dumps(content)
        path.write_text(text, encoding="utf-8")
        return path

    return _write
