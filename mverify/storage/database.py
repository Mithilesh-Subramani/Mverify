import json
import sqlite3
from pathlib import Path

def _connect(database_path: Path):
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path)
    connection.execute("PRAGMA foreign_keys = ON")
    return connection

def initialize_database(database_path: Path) -> None:
    with _connect(database_path) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS scans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_path TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                report_json TEXT NOT NULL
            )
        ''')

def save_scan(database_path: Path, project_path: str, report: dict) -> int:
    with _connect(database_path) as conn:
        cursor = conn.execute(
            "INSERT INTO scans (project_path, report_json) VALUES (?, ?)",
            (project_path, json.dumps(report)),
        )
        return int(cursor.lastrowid)
