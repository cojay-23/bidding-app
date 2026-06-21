from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

from .config import DB_PATH, ensure_dirs


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    ensure_dirs()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                summary_json TEXT,
                error TEXT,
                report_path TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL,
                filename TEXT NOT NULL,
                stored_name TEXT NOT NULL,
                size INTEGER NOT NULL,
                uploaded_at TEXT NOT NULL,
                FOREIGN KEY(project_id) REFERENCES projects(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL,
                filename TEXT NOT NULL,
                stored_name TEXT NOT NULL,
                analyze_type TEXT NOT NULL,
                engine TEXT,
                size INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(project_id) REFERENCES projects(id)
            )
            """
        )


def row_to_project(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    data["summary"] = json.loads(data.pop("summary_json") or "{}")
    return data


def create_project(project_id: str, name: str) -> dict[str, Any]:
    ts = now_iso()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO projects (id, name, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (project_id, name, "draft", ts, ts),
        )
        row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    return row_to_project(row)


def list_projects() -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM projects ORDER BY created_at DESC").fetchall()
    return [row_to_project(row) for row in rows]


def get_project(project_id: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    return row_to_project(row) if row else None


def update_project(project_id: str, **fields: Any) -> None:
    if not fields:
        return
    fields["updated_at"] = now_iso()
    values: list[Any] = []
    assignments = []
    for key, value in fields.items():
        if key == "summary":
            key = "summary_json"
            value = json.dumps(value, ensure_ascii=False)
        assignments.append(f"{key} = ?")
        values.append(value)
    values.append(project_id)
    with connect() as conn:
        conn.execute(f"UPDATE projects SET {', '.join(assignments)} WHERE id = ?", values)


def add_file(project_id: str, filename: str, stored_name: str, size: int) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO files (project_id, filename, stored_name, size, uploaded_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (project_id, filename, stored_name, size, now_iso()),
        )


def list_files(project_id: str) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM files WHERE project_id = ? ORDER BY uploaded_at ASC",
            (project_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def delete_project(project_id: str) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM files WHERE project_id = ?", (project_id,))
        conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))


def stored_file_path(project_id: str, stored_name: str) -> Path:
    from .config import PROJECTS_DIR

    return PROJECTS_DIR / project_id / "uploads" / stored_name


def add_report(project_id: str, filename: str, stored_name: str,
               analyze_type: str, engine: str | None, size: int) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO reports (project_id, filename, stored_name, analyze_type, engine, size, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (project_id, filename, stored_name, analyze_type, engine, size, now_iso()),
        )


def list_reports(project_id: str) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM reports WHERE project_id = ? ORDER BY created_at DESC",
            (project_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def report_stored_path(project_id: str, stored_name: str) -> Path:
    from .config import PROJECTS_DIR

    return PROJECTS_DIR / project_id / "reports" / stored_name
