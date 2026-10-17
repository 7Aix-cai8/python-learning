"""Domain models used by FocusBoard."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(slots=True)
class Task:
    """A persisted task."""

    id: int
    title: str
    description: str
    status: str
    priority: int
    tags: tuple[str, ...]
    due_date: str | None
    created_at: str
    completed_at: str | None

    @property
    def is_completed(self) -> bool:
        return self.status == "done"

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""
        data = asdict(self)
        data["tags"] = list(self.tags)
        return data
