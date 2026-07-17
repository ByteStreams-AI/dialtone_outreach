"""Neutral starter package for lead discovery experiments."""

from dataclasses import dataclass
from typing import Iterable


@dataclass(slots=True)
class Lead:
    """Minimal lead record used by the starter CLI."""

    name: str
    city: str
    source: str
    url: str
    notes: str = ""


def collect_leads(items: Iterable[Lead] | None = None) -> list[Lead]:
    """Return a list of leads, defaulting to an empty starter set."""

    if items is None:
        return []
    return list(items)
