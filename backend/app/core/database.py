from __future__ import annotations

import sqlite3
from pathlib import Path

from app.core.config import settings


SCHEMA_SQL = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS tasks (
  task_id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  description TEXT NOT NULL,
  status TEXT NOT NULL,
  config_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  report_path TEXT,
  last_error TEXT
);

CREATE TABLE IF NOT EXISTS task_nodes (
  task_id TEXT NOT NULL,
  node_id TEXT NOT NULL,
  parent_task_id TEXT,
  title TEXT NOT NULL,
  description TEXT NOT NULL,
  status TEXT NOT NULL,
  priority INTEGER NOT NULL,
  search_depth INTEGER NOT NULL,
  info_gain_score REAL NOT NULL,
  dependencies_json TEXT NOT NULL,
  children_json TEXT NOT NULL,
  output_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (task_id, node_id)
);

CREATE TABLE IF NOT EXISTS snapshots (
  task_id TEXT PRIMARY KEY,
  snapshot_json TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
"""


def get_connection() -> sqlite3.Connection:
    db_path = Path(settings.db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript(SCHEMA_SQL)
        conn.commit()
