# database.py
import sqlite3
import time
from config import DB_PATH

_instance = None


def get_db():
    global _instance
    if _instance is None:
        _instance = TaskDB()
    return _instance


class TaskDB:
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self._create_table()

    def _create_table(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                task_id    TEXT PRIMARY KEY,
                task_name  TEXT,
                category   TEXT,
                status     TEXT DEFAULT 'pending',
                worker_id  INTEGER,
                created_at REAL,
                updated_at REAL
            )
        """)
        self.conn.commit()

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

    def insert_task(self, task_id: str, task_name: str, category: str):
        now = time.time()
        self.conn.execute(
            "INSERT OR IGNORE INTO tasks "
            "(task_id, task_name, category, status, created_at, updated_at) "
            "VALUES (?, ?, ?, 'pending', ?, ?)",
            (task_id, task_name, category, now, now),
        )
        self.conn.commit()

    def set_completed(self, task_id: str, worker_id: int):
        self.conn.execute(
            "UPDATE tasks SET status='completed', worker_id=?, updated_at=? "
            "WHERE task_id=?",
            (worker_id, time.time(), task_id),
        )
        self.conn.commit()


    def get_pending_tasks(self):
        cur = self.conn.execute(
            "SELECT task_id, task_name, category FROM tasks WHERE status='pending'"
        )
        return [
            {"task_id": r[0], "task_name": r[1], "category": r[2]}
            for r in cur.fetchall()
        ]

    def get_all_tasks(self):
        cur = self.conn.execute(
            "SELECT task_id, task_name, category, status, worker_id, created_at, updated_at "
            "FROM tasks ORDER BY created_at"
        )
        return cur.fetchall()
