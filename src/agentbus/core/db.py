"""SQLite database connection and schema management for agentbus-core."""

import os
import sqlite3
import stat
from pathlib import Path


SCHEMA_SQL = """
-- Sources
CREATE TABLE IF NOT EXISTS sources (
  source_id     TEXT PRIMARY KEY,
  uri           TEXT NOT NULL,
  namespace     TEXT NOT NULL,
  agent_id      TEXT NOT NULL,
  run_id        TEXT NOT NULL,
  trust_label   TEXT NOT NULL CHECK (trust_label IN ('agent-generated','external-fetched','user-provided')),
  fetched_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  ttl_ms        INTEGER NOT NULL DEFAULT 86400000,
  content_hash  TEXT NOT NULL,
  content_type  TEXT NOT NULL DEFAULT 'text/markdown',
  byte_count    INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_sources_namespace ON sources(namespace);
CREATE INDEX IF NOT EXISTS idx_sources_agent     ON sources(agent_id);
CREATE INDEX IF NOT EXISTS idx_sources_hash      ON sources(content_hash);
CREATE INDEX IF NOT EXISTS idx_sources_uri_ttl   ON sources(uri, fetched_at, ttl_ms);

-- Chunks (porter stemmed)
CREATE VIRTUAL TABLE IF NOT EXISTS chunks USING fts5(
  heading_path,
  body,
  source_id  UNINDEXED,
  namespace  UNINDEXED,
  agent_id   UNINDEXED,
  created_at UNINDEXED,
  tokenize='porter unicode61'
);

-- Chunks (trigram, substring search)
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_trigram USING fts5(
  heading_path,
  body,
  source_id  UNINDEXED,
  namespace  UNINDEXED,
  agent_id   UNINDEXED,
  created_at UNINDEXED,
  tokenize='trigram'
);

-- Key-value items (BaseStore backing)
CREATE TABLE IF NOT EXISTS items (
  namespace   TEXT NOT NULL,
  key         TEXT NOT NULL,
  value_json  TEXT NOT NULL,
  version     INTEGER NOT NULL DEFAULT 1,
  updated_by  TEXT NOT NULL,
  updated_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  PRIMARY KEY (namespace, key)
);

-- Event log (append-only)
CREATE TABLE IF NOT EXISTS events (
  event_id     TEXT PRIMARY KEY,
  ts           TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  agent_id     TEXT NOT NULL,
  run_id       TEXT NOT NULL,
  namespace    TEXT NOT NULL,
  type         TEXT NOT NULL,
  priority     INTEGER NOT NULL CHECK (priority BETWEEN 1 AND 4),
  payload_json TEXT NOT NULL DEFAULT '{}',
  ref_ids      TEXT NOT NULL DEFAULT '[]'
);

CREATE INDEX IF NOT EXISTS idx_events_namespace ON events(namespace);
CREATE INDEX IF NOT EXISTS idx_events_agent     ON events(agent_id);
CREATE INDEX IF NOT EXISTS idx_events_type      ON events(type);
CREATE INDEX IF NOT EXISTS idx_events_ts        ON events(ts);
CREATE INDEX IF NOT EXISTS idx_events_cursor    ON events(ts, event_id);

-- Snapshots
CREATE TABLE IF NOT EXISTS snapshots (
  snapshot_id  TEXT PRIMARY KEY,
  run_id       TEXT NOT NULL,
  namespace    TEXT NOT NULL,
  built_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  budget_bytes INTEGER NOT NULL DEFAULT 2048,
  body         TEXT NOT NULL,
  consumed     INTEGER NOT NULL DEFAULT 0
);

-- Agent registry
CREATE TABLE IF NOT EXISTS agents (
  agent_id           TEXT PRIMARY KEY,
  role               TEXT NOT NULL DEFAULT 'worker',
  allowed_namespaces TEXT NOT NULL DEFAULT '[]',
  registered_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

-- Schema version
CREATE TABLE IF NOT EXISTS schema_version (
  version    INTEGER PRIMARY KEY,
  applied_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
INSERT OR IGNORE INTO schema_version(version) VALUES (1);
"""


def check_sqlite_capabilities(conn: sqlite3.Connection) -> bool:
    """Verify that SQLite version supports trigram FTS5 (SQLite >= 3.34.0)."""
    try:
        conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS _cap_check USING fts5(x, tokenize='trigram')")
        conn.execute("DROP TABLE IF EXISTS _cap_check")
        return True
    except sqlite3.OperationalError as e:
        raise RuntimeError(
            f"agentbus requires SQLite >= 3.34.0 for trigram FTS5. "
            f"Current version: {sqlite3.sqlite_version}. Error: {e}"
        ) from e


def create_connection(db_path: str, timeout: float = 30.0) -> sqlite3.Connection:
    """Create a configured SQLite connection following CLAUDE.md requirements."""
    is_new = not os.path.exists(db_path) and db_path != ":memory:"
    
    # Ensure parent directory exists
    if db_path != ":memory:":
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(
        db_path,
        timeout=timeout,
        check_same_thread=False,
        isolation_level=None,  # Autocommit mode by default; manual transactions with BEGIN
    )
    
    # Configure WAL mode & pragmas
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute(f"PRAGMA busy_timeout={int(timeout * 1000)}")

    if is_new and os.name != "nt":
        try:
            os.chmod(db_path, stat.S_IRUSR | stat.S_IWUSR)  # 0o600
        except OSError:
            pass

    return conn


def init_db(db_path: str) -> None:
    """Initialize database schema and verify capabilities."""
    conn = create_connection(db_path)
    try:
        check_sqlite_capabilities(conn)
        conn.executescript(SCHEMA_SQL)
    finally:
        conn.close()
