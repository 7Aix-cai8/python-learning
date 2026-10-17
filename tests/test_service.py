from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from focusboard.db import Database
from focusboard.service import TaskService, ValidationError


class TaskServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.temp_dir.name) / "tasks.db")
        self.service = TaskService(self.db)

    def tearDown(self) -> None:
        self.db.close()
        self.temp_dir.cleanup()

    def test_task_lifecycle_and_filters(self) -> None:
        first = self.service.add_task(
            "Prepare release",
            description="Package the next version",
            priority=1,
            tags=["Release", "python"],
            due_date="2026-10-10",
        )
        second = self.service.add_task("Read design notes", tags=["research"])

        self.assertEqual(first.tags, ("python", "release"))
        self.assertEqual([task.id for task in self.service.list_tasks(tag="PYTHON")], [first.id])
        self.assertEqual(
            [task.id for task in self.service.list_tasks(search="PACKAGE")], [first.id]
        )
        self.assertEqual(
            [task.id for task in self.service.list_tasks(overdue=True, today=date(2026, 10, 11))],
            [first.id],
        )

        self.service.complete_task(first.id)
        self.assertTrue(self.service.db.get(first.id).is_completed)
        self.assertEqual(self.service.stats(today=date(2026, 10, 11)), {
            "todo": 1,
            "done": 1,
            "total": 2,
            "overdue": 0,
        })
        self.service.reopen_task(first.id)
        self.assertEqual(self.service.db.get(first.id).status, "todo")
        self.service.delete_task(second.id)
        self.assertEqual(len(self.service.list_tasks()), 1)

    def test_validation_rejects_bad_input(self) -> None:
        with self.assertRaises(ValidationError):
            self.service.add_task("   ")
        with self.assertRaises(ValidationError):
            self.service.add_task("bad priority", priority=0)
        with self.assertRaises(ValidationError):
            self.service.add_task("bad date", due_date="tomorrow")

    def test_json_round_trip(self) -> None:
        self.service.add_task("Backup database", priority=2, tags=["ops"])
        export_path = Path(self.temp_dir.name) / "backup.json"

        self.assertEqual(self.service.export_json(export_path), 1)
        payload = json.loads(export_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["version"], 1)
        self.assertEqual(payload["tasks"][0]["title"], "Backup database")

        other_db = Database(Path(self.temp_dir.name) / "other.db")
        try:
            other_service = TaskService(other_db)
            self.assertEqual(other_service.import_json(export_path), 1)
            imported = other_service.list_tasks()[0]
            self.assertEqual(imported.title, "Backup database")
            self.assertEqual(imported.tags, ("ops",))
        finally:
            other_db.close()


if __name__ == "__main__":
    unittest.main()
