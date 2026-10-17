"""SQLite persistence layer for FocusBoard."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .models import Task

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL CHECK(length(trim(title)) > 0),
    description TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'todo' CHECK(status IN ('todo', 'done')),
    priority INTEGER NOT NULL DEFAULT 3 CHECK(priority BETWEEN 1 AND 5),
    tags TEXT NOT NULL DEFAULT '[]',
    due_date TEXT,
    created_at TEXT NOT NULL,
    completed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_due_date ON tasks(due_date);
"""


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class Database:
    """Small repository around a SQLite connection."""

    def __init__(self, path: str | Path = "~/.focusboard/tasks.db") -> None:
        self.path = Path(path).expanduser()
        if str(self.path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(SCHEMA)
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> "Database":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    @staticmethod
    def _from_row(row: sqlite3.Row) -> Task:
        return Task(
            id=row["id"],
            title=row["title"],
            description=row["description"],
            status=row["status"],
            priority=row["priority"],
            tags=tuple(json.loads(row["tags"])),
            due_date=row["due_date"],
            created_at=row["created_at"],
            completed_at=row["completed_at"],
        )

    def add(
        self,
        title: str,
        description: str,
        priority: int,
        tags: Iterable[str],
        due_date: str | None,
    ) -> Task:
        cursor = self.connection.execute(
            """
            INSERT INTO tasks(title, description, priority, tags, due_date, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (title, description, priority, json.dumps(sorted(set(tags))), due_date, utc_now()),
        )
        self.connection.commit()
        return self.get(cursor.lastrowid)

    def get(self, task_id: int) -> Task:
        row = self.connection.execute(
            "SELECT * FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"Task {task_id} not found")
        return self._from_row(row)

    def list(
        self,
        *,
        status: str | None = None,
        tag: str | None = None,
        search: str | None = None,
        due_before: str | None = None,
    ) -> list[Task]:
        clauses: list[str] = []
        values: list[Any] = []
        if status:
            clauses.append("status = ?")
            values.append(status)
        if tag:
            clauses.append("tags LIKE ?")
            values.append(f'%"{tag}"%')
        if search:
            clauses.append("(lower(title) LIKE ? OR lower(description) LIKE ?)")
            needle = f"%{search.lower()}%"
            values.extend([needle, needle])
        if due_before:
            clauses.append("status = 'todo' AND due_date IS NOT NULL AND due_date < ?")
            values.append(due_before)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self.connection.execute(
            f"""
            SELECT * FROM tasks
            {where}
            ORDER BY CASE status WHEN 'todo' THEN 0 ELSE 1 END,
                     CASE WHEN due_date IS NULL THEN 1 ELSE 0 END,
                     due_date,
                     priority,
                     id
            """,
            values,
        ).fetchall()
        return [self._from_row(row) for row in rows]

    def set_status(self, task_id: int, status: str) -> Task:
        completed_at = utc_now() if status == "done" else None
        cursor = self.connection.execute(
            "UPDATE tasks SET status = ?, completed_at = ? WHERE id = ?",
            (status, completed_at, task_id),
        )
        if cursor.rowcount == 0:
            raise KeyError(f"Task {task_id} not found")
        self.connection.commit()
        return self.get(task_id)

    def update(
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
        current = self.get(task_id)
        values = {
            "title": current.title if title is None else title,
            "description": current.description if description is None else description,
            "priority": current.priority if priority is None else priority,
            "tags": json.dumps(list(current.tags) if tags is None else sorted(set(tags))),
            "due_date": None if clear_due_date else (current.due_date if due_date is None else due_date),
        }
        self.connection.execute(
            """
            UPDATE tasks
            SET title = :title, description = :description, priority = :priority,
                tags = :tags, due_date = :due_date
            WHERE id = :id
            """,
            {**values, "id": task_id},
        )
        self.connection.commit()
        return self.get(task_id)

    def delete(self, task_id: int) -> None:
        cursor = self.connection.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        if cursor.rowcount == 0:
            raise KeyError(f"Task {task_id} not found")
        self.connection.commit()

    def counts(self) -> dict[str, int]:
        rows = self.connection.execute(
            "SELECT status, COUNT(*) AS count FROM tasks GROUP BY status"
        ).fetchall()
        result = {"todo": 0, "done": 0}
        result.update({row["status"]: row["count"] for row in rows})
        return result
