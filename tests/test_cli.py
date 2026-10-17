from __future__ import annotations

import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from focusboard.cli import main


class CliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp_dir.name) / "cli.db")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def run_cli(self, *args: str) -> str:
        output = StringIO()
        with redirect_stdout(output):
            exit_code = main(["--db", self.db_path, *args])
        self.assertEqual(exit_code, 0)
        return output.getvalue()

    def test_add_list_done_and_stats(self) -> None:
        self.assertIn("Created task 1", self.run_cli("add", "Ship feature", "--tags", "work"))
        self.assertIn("Ship feature", self.run_cli("list"))
        self.assertIn("Completed task 1", self.run_cli("done", "1"))
        stats = self.run_cli("stats")
        self.assertIn("Total: 1", stats)
        self.assertIn("Done: 1", stats)

    def test_empty_list_is_friendly(self) -> None:
        self.assertEqual(self.run_cli("list"), "No tasks found.\n")


if __name__ == "__main__":
    unittest.main()
