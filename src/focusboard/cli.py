"""Command-line interface for FocusBoard."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from .db import Database
from .service import TaskService, ValidationError


def _tags(value: str | None) -> list[str]:
    return [] if not value else [part for part in value.split(",") if part.strip()]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="focusboard",
        description="A focused SQLite task manager for the command line.",
    )
    parser.add_argument(
        "--db",
        default="~/.focusboard/tasks.db",
        help="database path (default: ~/.focusboard/tasks.db)",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    add = commands.add_parser("add", help="create a task")
    add.add_argument("title")
    add.add_argument("-d", "--description", default="")
    add.add_argument("-p", "--priority", type=int, default=3, help="1 is highest, 5 is lowest")
    add.add_argument("-t", "--tags", help="comma-separated tags")
    add.add_argument("--due", metavar="YYYY-MM-DD")

    show = commands.add_parser("list", help="list tasks")
    show.add_argument("--status", choices=("todo", "done"))
    show.add_argument("--tag")
    show.add_argument("--search")
    show.add_argument("--overdue", action="store_true")

    done = commands.add_parser("done", help="mark a task complete")
    done.add_argument("id", type=int)

    reopen = commands.add_parser("reopen", help="reopen a completed task")
    reopen.add_argument("id", type=int)

    delete = commands.add_parser("delete", help="delete a task")
    delete.add_argument("id", type=int)

    edit = commands.add_parser("edit", help="edit task fields")
    edit.add_argument("id", type=int)
    edit.add_argument("--title")
    edit.add_argument("-d", "--description")
    edit.add_argument("-p", "--priority", type=int)
    edit.add_argument("-t", "--tags")
    edit.add_argument("--due", metavar="YYYY-MM-DD")
    edit.add_argument("--clear-due", action="store_true")

    commands.add_parser("stats", help="show task counts")

    export = commands.add_parser("export", help="export all tasks as JSON")
    export.add_argument("path", type=Path)

    import_cmd = commands.add_parser("import", help="import tasks from JSON")
    import_cmd.add_argument("path", type=Path)
    return parser


def _print_task(task: object) -> None:
    # Task is deliberately duck-typed here to keep output concerns out of the domain model.
    print(
        f"[{task.id}] {'✓' if task.status == 'done' else ' '} "
        f"P{task.priority} {task.title}"
        + (f" (due {task.due_date})" if task.due_date else "")
        + (f"  #{' #'.join(task.tags)}" if task.tags else "")
    )
    if task.description:
        print(f"    {task.description}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    with Database(args.db) as database:
        service = TaskService(database)
        try:
            if args.command == "add":
                task = service.add_task(
                    args.title,
                    description=args.description,
                    priority=args.priority,
                    tags=_tags(args.tags),
                    due_date=args.due,
                )
                print(f"Created task {task.id}: {task.title}")

            elif args.command == "list":
                tasks = service.list_tasks(
                    status=args.status,
                    tag=args.tag,
                    search=args.search,
                    overdue=args.overdue,
                )
                if not tasks:
                    print("No tasks found.")
                for task in tasks:
                    _print_task(task)

            elif args.command == "done":
                task = service.complete_task(args.id)
                print(f"Completed task {task.id}: {task.title}")

            elif args.command == "reopen":
                task = service.reopen_task(args.id)
                print(f"Reopened task {task.id}: {task.title}")

            elif args.command == "delete":
                service.delete_task(args.id)
                print(f"Deleted task {args.id}")

            elif args.command == "edit":
                if (
                    args.title is None
                    and args.description is None
                    and args.priority is None
                    and args.tags is None
                    and args.due is None
                    and not args.clear_due
                ):
                    parser.error("edit requires at least one field")
                task = service.update_task(
                    args.id,
                    title=args.title,
                    description=args.description,
                    priority=args.priority,
                    tags=None if args.tags is None else _tags(args.tags),
                    due_date=args.due,
                    clear_due_date=args.clear_due,
                )
                print(f"Updated task {task.id}: {task.title}")

            elif args.command == "stats":
                counts = service.stats()
                print(
                    f"Total: {counts['total']} | To do: {counts['todo']} | "
                    f"Done: {counts['done']} | Overdue: {counts['overdue']}"
                )

            elif args.command == "export":
                count = service.export_json(args.path)
                print(f"Exported {count} task(s) to {args.path}")

            elif args.command == "import":
                count = service.import_json(args.path)
                print(f"Imported {count} task(s) from {args.path}")

            return 0
        except (KeyError, OSError, ValueError, ValidationError) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2
