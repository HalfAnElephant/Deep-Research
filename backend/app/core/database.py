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
  research_scorecard_json TEXT,
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
  branch_id TEXT,
  branch_score REAL NOT NULL DEFAULT 0,
  branch_depth INTEGER NOT NULL DEFAULT 0,
  position_x REAL,
  position_y REAL,
  dependencies_json TEXT NOT NULL,
  children_json TEXT NOT NULL,
  output_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (task_id, node_id)
);

CREATE TABLE IF NOT EXISTS search_branches (
  task_id TEXT NOT NULL,
  branch_id TEXT NOT NULL,
  parent_branch_id TEXT,
  root_node_id TEXT NOT NULL,
  branch_type TEXT NOT NULL,
  branch_goal TEXT NOT NULL,
  depth INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL,
  score_info_gain REAL NOT NULL DEFAULT 0,
  score_evidence_strength REAL NOT NULL DEFAULT 0,
  score_feasibility REAL NOT NULL DEFAULT 0,
  score_total REAL NOT NULL DEFAULT 0,
  prune_reason TEXT,
  debug_depth INTEGER NOT NULL DEFAULT 0,
  worker_id TEXT,
  node_ids_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (task_id, branch_id)
);

CREATE TABLE IF NOT EXISTS branch_actions (
  action_id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL,
  branch_id TEXT NOT NULL,
  action_type TEXT NOT NULL,
  action_input_json TEXT NOT NULL,
  action_output_json TEXT NOT NULL,
  score_before REAL NOT NULL DEFAULT 0,
  score_after REAL NOT NULL DEFAULT 0,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS branch_repairs (
  repair_id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL,
  branch_id TEXT NOT NULL,
  node_id TEXT NOT NULL,
  attempt INTEGER NOT NULL,
  diagnosis TEXT NOT NULL,
  proposal TEXT NOT NULL,
  succeeded INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS experiment_runs (
  run_id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL,
  branch_id TEXT NOT NULL,
  node_id TEXT NOT NULL,
  status TEXT NOT NULL,
  objective TEXT NOT NULL,
  stdout TEXT NOT NULL,
  stderr TEXT NOT NULL,
  exit_code INTEGER,
  metrics_json TEXT NOT NULL,
  started_at TEXT NOT NULL,
  completed_at TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS experiment_artifacts (
  artifact_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  task_id TEXT NOT NULL,
  branch_id TEXT NOT NULL,
  node_id TEXT NOT NULL,
  artifact_type TEXT NOT NULL,
  path TEXT NOT NULL,
  summary TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS snapshots (
  task_id TEXT PRIMARY KEY,
  snapshot_json TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS evidences (
  evidence_id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL,
  node_id TEXT NOT NULL,
  source_type TEXT NOT NULL,
  url TEXT NOT NULL,
  content TEXT NOT NULL,
  metadata_json TEXT NOT NULL,
  score REAL NOT NULL,
  extracted_data_json TEXT NOT NULL,
  favorited INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_evidences_task_id ON evidences(task_id);
CREATE INDEX IF NOT EXISTS idx_evidences_source_type ON evidences(source_type);
CREATE INDEX IF NOT EXISTS idx_search_branches_task_id ON search_branches(task_id);
CREATE INDEX IF NOT EXISTS idx_branch_actions_task_branch ON branch_actions(task_id, branch_id);
CREATE INDEX IF NOT EXISTS idx_branch_repairs_task_branch ON branch_repairs(task_id, branch_id);
CREATE INDEX IF NOT EXISTS idx_experiment_runs_task_id ON experiment_runs(task_id);
CREATE INDEX IF NOT EXISTS idx_experiment_artifacts_task_id ON experiment_artifacts(task_id);

CREATE TABLE IF NOT EXISTS conflicts (
  conflict_id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL,
  parameter TEXT NOT NULL,
  disputed_values_json TEXT NOT NULL,
  variance REAL NOT NULL,
  context TEXT NOT NULL,
  resolution_status TEXT NOT NULL,
  resolution_json TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS conversations (
  conversation_id TEXT PRIMARY KEY,
  topic TEXT NOT NULL,
  status TEXT NOT NULL,
  config_json TEXT NOT NULL,
  current_ideas_json TEXT NOT NULL DEFAULT '[]',
  task_id TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS plan_revisions (
  conversation_id TEXT NOT NULL,
  version INTEGER NOT NULL,
  author TEXT NOT NULL,
  markdown TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (conversation_id, version)
);

CREATE TABLE IF NOT EXISTS conversation_messages (
  message_id TEXT PRIMARY KEY,
  conversation_id TEXT NOT NULL,
  role TEXT NOT NULL,
  kind TEXT NOT NULL,
  content TEXT NOT NULL,
  metadata_json TEXT NOT NULL,
  collapsed INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_conversations_task_id ON conversations(task_id);
CREATE INDEX IF NOT EXISTS idx_conversation_messages_created_at
  ON conversation_messages(conversation_id, created_at ASC);
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

        # Handle migrations: add favorited column if it doesn't exist
        cursor = conn.execute("PRAGMA table_info(evidences)")
        columns = [row[1] for row in cursor.fetchall()]
        if "favorited" not in columns:
            conn.execute(
                "ALTER TABLE evidences ADD COLUMN favorited INTEGER NOT NULL DEFAULT 0")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_evidences_favorited ON evidences(favorited)")
            conn.commit()

        # Handle migrations: add task node position columns if they don't exist
        cursor = conn.execute("PRAGMA table_info(task_nodes)")
        task_node_columns = [row[1] for row in cursor.fetchall()]
        if "position_x" not in task_node_columns:
            conn.execute("ALTER TABLE task_nodes ADD COLUMN position_x REAL")
        if "position_y" not in task_node_columns:
            conn.execute("ALTER TABLE task_nodes ADD COLUMN position_y REAL")
        if "branch_id" not in task_node_columns:
            conn.execute("ALTER TABLE task_nodes ADD COLUMN branch_id TEXT")
        if "branch_score" not in task_node_columns:
            conn.execute(
                "ALTER TABLE task_nodes ADD COLUMN branch_score REAL NOT NULL DEFAULT 0")
        if "branch_depth" not in task_node_columns:
            conn.execute(
                "ALTER TABLE task_nodes ADD COLUMN branch_depth INTEGER NOT NULL DEFAULT 0")

        cursor = conn.execute("PRAGMA table_info(conversations)")
        conversation_columns = [row[1] for row in cursor.fetchall()]
        if "current_ideas_json" not in conversation_columns:
            conn.execute(
                "ALTER TABLE conversations ADD COLUMN current_ideas_json TEXT NOT NULL DEFAULT '[]'")

        cursor = conn.execute("PRAGMA table_info(tasks)")
        task_columns = [row[1] for row in cursor.fetchall()]
        if "research_scorecard_json" not in task_columns:
            conn.execute(
                "ALTER TABLE tasks ADD COLUMN research_scorecard_json TEXT")
        conn.commit()

        conn.commit()
