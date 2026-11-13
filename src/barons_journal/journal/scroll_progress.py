"""Work out what each scroll label can still be, from the labels identified so far.

Every run uses all 25 labels, and each scroll type takes ``label_count`` of them.
So a scroll type stays a candidate for the unknown labels until all of its
labels have been found.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from ..reference import SCROLL_LABELS, SCROLLS, Scroll, scroll_by_item_id


class JournalError(ValueError):
    """A journal entry that can't be valid, like an unknown label or too many labels for a scroll."""


@dataclass(frozen=True, slots=True)
class ScrollProgress:
    identified: Mapping[str, Scroll]
    """Label -> scroll, for identified labels, in the game's label order."""
    unknown_labels: tuple[str, ...]
    """Labels not identified yet, in the game's label order."""
    remaining: Mapping[Scroll, int]
    """Scroll -> how many of its labels are still unknown. Only scrolls with at least one."""

    @classmethod
    def from_identifications(cls, by_label: Mapping[str, int]) -> "ScrollProgress":
        """Build from label -> scroll item ID. Raises ``JournalError`` if the identifications are impossible."""
        for label in by_label:
            _check_label(label)

        identified = {}
        for label in SCROLL_LABELS:
            if label in by_label:
                try:
                    identified[label] = scroll_by_item_id(by_label[label])
                except KeyError:
                    raise JournalError(f"Item {by_label[label]} is not a scroll") from None

        remaining = {}
        for scroll in SCROLLS:
            found = sum(1 for s in identified.values() if s == scroll)
            if found > scroll.label_count:
                raise JournalError(
                    f"{scroll.name} only has {scroll.label_count} label(s) per run, "
                    f"but {found} are identified as it"
                )
            if found < scroll.label_count:
                remaining[scroll] = scroll.label_count - found

        return cls(
            identified=MappingProxyType(identified),
            unknown_labels=tuple(label for label in SCROLL_LABELS if label not in identified),
            remaining=MappingProxyType(remaining),
        )

    def candidates(self, label: str) -> tuple[Scroll, ...]:
        """Scrolls this label could be, in item-ID order."""
        _check_label(label)
        if label in self.identified:
            return (self.identified[label],)
        return tuple(self.remaining)

    @property
    def is_complete(self) -> bool:
        return not self.unknown_labels


def _check_label(label: str) -> None:
    if label not in SCROLL_LABELS:
        raise JournalError(f"{label!r} is not a scroll label")
