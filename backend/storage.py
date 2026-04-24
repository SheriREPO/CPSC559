import sqlite3
import json
import time
import os

DB_PATH = os.environ.get("DB_PATH", "/app/tasks.db")
WAL_PATH = os.environ.get("WAL_PATH", "/app/tasks.wal")


def init_db():
    conn = _connect()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            task_id      INTEGER PRIMARY KEY,
            token        TEXT,
            task_name    TEXT    NOT NULL,
            category     TEXT,
            details      TEXT,
            status       TEXT    NOT NULL DEFAULT 'PENDING',
            assigned_to  INTEGER,
            assigned_at  REAL,
            completed_at REAL,
            result       TEXT,
            created_at   REAL    NOT NULL
        )
    """)
    conn.commit()
    conn.close()

    if not os.path.exists(WAL_PATH):
        open(WAL_PATH, "w").close()


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# Writes a structured log entry to disk before any state change is committed to the database.
def _wal_append(entry: dict):
    # always write to the WAL before touching the DB — if we crash between the two, replay fixes it
    with open(WAL_PATH, "a") as f:
        f.write(json.dumps({**entry, "ts": time.time()}) + "\n")


def save_task(task_id: int, token: str, task_name: str, category: str, details: dict):
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

# Upserts task metadata across all replicas immediately after assignment, ensuring cluster-wide consistency.
def replicate_task(task_id: int, token: str, task_name: str, category: str,
                   details: dict, status: str, assigned_to: int):
    conn = _connect()
    # INSERT OR REPLACE so this is idempotent if the same broadcast arrives more than once
    conn.execute("""
        INSERT OR REPLACE INTO tasks
            (task_id, token, task_name, category, details, status, assigned_to, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (task_id, token, task_name, category, json.dumps(details),
          status, assigned_to, time.time()))
    conn.commit()
    conn.close()

# Queries the local database for all tasks in PENDING Or ASSIGNED states, used during leader recovery.
def get_incomplete_tasks() -> list:
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
    conn = _connect()
    rows = conn.execute("""
        SELECT * FROM tasks ORDER BY task_id DESC LIMIT 100
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def task_exists(task_id: int) -> bool:
    conn = _connect()
    row = conn.execute("SELECT 1 FROM tasks WHERE task_id=?", (task_id,)).fetchone()
    conn.close()
    return row is not None

# Reconstructs local database state on restart by replaying all log entries in sequence.
def replay_wal():
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
                op = entry.get("op")
                task_id = entry.get("task_id")
                status = entry.get("new_status")

                if op == "INSERT":
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
                pass

    conn.commit()
    conn.close()
