"""Application services and validation for FocusBoard."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Iterable

from .db import Database
from .models import Task


class ValidationError(ValueError):
    """Raised when user input cannot form a valid task."""


class TaskService:
    """Business rules for creating and managing tasks."""

    def __init__(self, database: Database) -> None:
        self.db = database

    @staticmethod
    def _validate_title(title: str) -> str:
        cleaned = title.strip()
        if not cleaned:
            raise ValidationError("title must not be empty")
        if len(cleaned) > 200:
            raise ValidationError("title must be 200 characters or fewer")
        return cleaned

    @staticmethod
    def _validate_priority(priority: int) -> int:
        if priority not in range(1, 6):
            raise ValidationError("priority must be between 1 (highest) and 5 (lowest)")
        return priority

    @staticmethod
    def _validate_due_date(due_date: str | None) -> str | None:
        if due_date is None or due_date == "":
            return None
        try:
            return date.fromisoformat(due_date).isoformat()
        except ValueError as exc:
            raise ValidationError("due date must use YYYY-MM-DD format") from exc

    @staticmethod
    def _normalize_tags(tags: Iterable[str]) -> tuple[str, ...]:
        normalized = {tag.strip().lower() for tag in tags if tag.strip()}
        if any(len(tag) > 30 for tag in normalized):
            raise ValidationError("each tag must be 30 characters or fewer")
        return tuple(sorted(normalized))

    def add_task(
        self,
        title: str,
        *,
        description: str = "",
        priority: int = 3,
        tags: Iterable[str] = (),
        due_date: str | None = None,
    ) -> Task:
        return self.db.add(
            self._validate_title(title),
            description.strip(),
            self._validate_priority(priority),
            self._normalize_tags(tags),
            self._validate_due_date(due_date),
        )

    def list_tasks(
        self,
        *,
        status: str | None = None,
        tag: str | None = None,
        search: str | None = None,
        overdue: bool = False,
        today: date | None = None,
    ) -> list[Task]:
        if status not in (None, "todo", "done"):
            raise ValidationError("status must be todo or done")
        if tag:
            tag = self._normalize_tags([tag])[0]
        due_before = (today or date.today()).isoformat() if overdue else None
        return self.db.list(status=status, tag=tag, search=search, due_before=due_before)

    def complete_task(self, task_id: int) -> Task:
        return self.db.set_status(task_id, "done")

    def reopen_task(self, task_id: int) -> Task:
        return self.db.set_status(task_id, "todo")

    def delete_task(self, task_id: int) -> None:
        self.db.delete(task_id)

    def update_task(
        self,
        task_id: int,
        *,
        title: str | None = None,
        description: str | None = None,
        priority: int | None = None,
        tags: Iterable[str] | None = None,
        due_date: str | None = None,
        clear_due_date: bool = False,
    ) -> Task:
        if title is not None:
            title = self._validate_title(title)
        if priority is not None:
            priority = self._validate_priority(priority)
        if tags is not None:
            tags = self._normalize_tags(tags)
        if due_date is not None:
            due_date = self._validate_due_date(due_date)
        return self.db.update(
            task_id,
            title=title,
            description=None if description is None else description.strip(),
            priority=priority,
            tags=tags,
            due_date=due_date,
            clear_due_date=clear_due_date,
        )

    def stats(self, today: date | None = None) -> dict[str, int]:
        counts = self.db.counts()
        counts["total"] = counts["todo"] + counts["done"]
        counts["overdue"] = len(self.list_tasks(overdue=True, today=today))
        return counts

    def export_json(self, path: str | Path) -> int:
        tasks = [task.as_dict() for task in self.list_tasks()]
        destination = Path(path).expanduser()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps({"version": 1, "tasks": tasks}, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return len(tasks)

    def import_json(self, path: str | Path) -> int:
        source = Path(path).expanduser()
        payload = json.loads(source.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or not isinstance(payload.get("tasks"), list):
            raise ValidationError("import file must contain a top-level tasks list")

        imported = 0
        for item in payload["tasks"]:
            if not isinstance(item, dict):
                raise ValidationError("each imported task must be an object")
            task = self.add_task(
                str(item.get("title", "")),
                description=str(item.get("description", "")),
                priority=int(item.get("priority", 3)),
                tags=item.get("tags", []),
                due_date=item.get("due_date"),
            )
            if item.get("status") == "done":
                self.complete_task(task.id)
            imported += 1
        return imported
