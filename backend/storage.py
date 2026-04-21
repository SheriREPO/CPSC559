# storage.py — SQLite persistence for task state + Write-Ahead Log

import sqlite3
import json
import time
import os

DB_PATH  = os.environ.get("DB_PATH", "/app/tasks.db")
WAL_PATH = os.environ.get("WAL_PATH", "/app/tasks.wal")


# ── Database setup ─────────────────────────────────────────────────────────────
def init_db():
    """Create the tasks table and WAL file if they don't exist."""
    conn = _connect()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            task_id      INTEGER PRIMARY KEY,
            token        TEXT,
            task_name    TEXT    NOT NULL,
            category     TEXT,
            details      TEXT,       -- JSON
            status       TEXT    NOT NULL DEFAULT 'PENDING',
            assigned_to  INTEGER,    -- server_id of assigned worker
            assigned_at  REAL,
            completed_at REAL,
            result       TEXT,       -- JSON
            created_at   REAL    NOT NULL
        )
    """)
    conn.commit()
    conn.close()

    # Create WAL file if it doesn't exist
    if not os.path.exists(WAL_PATH):
        open(WAL_PATH, "w").close()


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ── WAL helpers ────────────────────────────────────────────────────────────────
def _wal_append(entry: dict):
    """Append a log entry BEFORE making any DB change."""
    with open(WAL_PATH, "a") as f:
        f.write(json.dumps({**entry, "ts": time.time()}) + "\n")


# ── Task operations ────────────────────────────────────────────────────────────
def save_task(task_id: int, token: str, task_name: str, category: str, details: dict):
    """Insert a new PENDING task. Called by leader when task is received."""
    _wal_append({
        "op": "INSERT", "task_id": task_id, "token": token,
        "task_name": task_name, "status": "PENDING",
    })
    conn = _connect()
    conn.execute("""
        INSERT OR IGNORE INTO tasks
            (task_id, token, task_name, category, details, status, created_at)
        VALUES (?, ?, ?, ?, ?, 'PENDING', ?)
    """, (task_id, token, task_name, category, json.dumps(details), time.time()))
    conn.commit()
    conn.close()


def mark_assigned(task_id: int, worker_id: int):
    """Update task to ASSIGNED. Called by leader after round-robin pick."""
    _wal_append({
        "op": "UPDATE", "task_id": task_id,
        "old_status": "PENDING", "new_status": "ASSIGNED", "worker": worker_id,
    })
    conn = _connect()
    conn.execute("""
        UPDATE tasks SET status='ASSIGNED', assigned_to=?, assigned_at=?
        WHERE task_id=?
    """, (worker_id, time.time(), task_id))
    conn.commit()
    conn.close()


def mark_completed(task_id: int, result: dict):
    """Update task to COMPLETED. Called by all servers on TASK_DONE broadcast."""
    _wal_append({
        "op": "UPDATE", "task_id": task_id,
        "old_status": "ASSIGNED", "new_status": "COMPLETED",
    })
    conn = _connect()
    conn.execute("""
        UPDATE tasks SET status='COMPLETED', result=?, completed_at=?
        WHERE task_id=?
    """, (json.dumps(result), time.time(), task_id))
    conn.commit()
    conn.close()


def mark_failed(task_id: int, error: str):
    """Update task to FAILED."""
    _wal_append({
        "op": "UPDATE", "task_id": task_id,
        "old_status": "ASSIGNED", "new_status": "FAILED", "error": error,
    })
    conn = _connect()
    conn.execute("""
        UPDATE tasks SET status='FAILED', result=?, completed_at=?
        WHERE task_id=?
    """, (json.dumps({"error": error}), time.time(), task_id))
    conn.commit()
    conn.close()


def replicate_task(task_id: int, token: str, task_name: str, category: str,
                   details: dict, status: str, assigned_to: int):
    """
    Called on all servers when leader broadcasts TASK_REPLICATED.
    Ensures every server has a record of in-flight tasks, not just completed ones.
    Uses INSERT OR REPLACE so it's idempotent.
    """
    conn = _connect()
    conn.execute("""
        INSERT OR REPLACE INTO tasks
            (task_id, token, task_name, category, details, status, assigned_to, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (task_id, token, task_name, category, json.dumps(details),
          status, assigned_to, time.time()))
    conn.commit()
    conn.close()


def get_incomplete_tasks() -> list:
    """
    Return all PENDING or ASSIGNED tasks.
    Used by new leader on startup to find tasks that need re-queuing.
    """
    conn = _connect()
    rows = conn.execute("""
        SELECT task_id, token, task_name, category, details, status, assigned_to, assigned_at
        FROM tasks
        WHERE status IN ('PENDING', 'ASSIGNED')
        ORDER BY task_id ASC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_tasks() -> list:
    """Return full task history. Used by dashboard API."""
    conn = _connect()
    rows = conn.execute("""
        SELECT * FROM tasks ORDER BY task_id DESC LIMIT 100
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]

# This is used before marking a task done/failed so the server doesn’t try to update a task record that was never stored.
def task_exists(task_id: int) -> bool:
    conn = _connect()
    row = conn.execute("SELECT 1 FROM tasks WHERE task_id=?", (task_id,)).fetchone()
    conn.close()
    return row is not None


# ── WAL replay (called on startup to fix any incomplete writes) ────────────────
def replay_wal():
    """
    On startup, replay the WAL to fix any DB state left incomplete
    by a crash mid-write. Safe to call multiple times (idempotent).
    """
    if not os.path.exists(WAL_PATH):
        return

    conn = _connect()
    with open(WAL_PATH, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                op       = entry.get("op")
                task_id  = entry.get("task_id")
                status   = entry.get("new_status")

                if op == "INSERT":
                    # Ensure PENDING row exists
                    conn.execute("""
                        INSERT OR IGNORE INTO tasks
                            (task_id, token, task_name, status, created_at)
                        VALUES (?, ?, ?, 'PENDING', ?)
                    """, (task_id, entry.get("token"), entry.get("task_name"), entry.get("ts", 0)))

                elif op == "UPDATE" and status == "ASSIGNED":
                    conn.execute("""
                        UPDATE tasks SET status='ASSIGNED', assigned_to=?
                        WHERE task_id=? AND status='PENDING'
                    """, (entry.get("worker"), task_id))

                elif op == "UPDATE" and status == "COMPLETED":
                    conn.execute("""
                        UPDATE tasks SET status='COMPLETED'
                        WHERE task_id=? AND status='ASSIGNED'
                    """, (task_id,))

                elif op == "UPDATE" and status == "FAILED":
                    conn.execute("""
                        UPDATE tasks SET status='FAILED'
                        WHERE task_id=? AND status='ASSIGNED'
                    """, (task_id,))

            except Exception:
                pass  # Skip malformed lines

    conn.commit()
    conn.close()
