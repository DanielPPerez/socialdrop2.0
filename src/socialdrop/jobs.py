from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

DB_PATH = Path(os.environ.get("SOCIALDROP_JOBS_DB", "./socialdrop_jobs.db"))


@dataclass
class Job:
    id: int | None = None
    drop_id: str = ""
    platform: str = ""
    status: str = "pending"
    attempts: int = 0
    max_attempts: int = 3
    next_attempt_at: datetime | None = None
    payload: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class JobQueue:
    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or DB_PATH
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    drop_id TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    attempts INTEGER NOT NULL DEFAULT 0,
                    max_attempts INTEGER NOT NULL DEFAULT 3,
                    next_attempt_at TEXT,
                    payload TEXT,
                    result TEXT,
                    error TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_drop ON jobs(drop_id)")

    def enqueue(self, job: Job) -> Job:
        now = datetime.utcnow()
        job.created_at = now
        job.updated_at = now
        job.status = "pending"
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                """
                INSERT INTO jobs
                    (drop_id, platform, status, attempts, max_attempts,
                     next_attempt_at, payload, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job.drop_id,
                    job.platform,
                    job.status,
                    job.attempts,
                    job.max_attempts,
                    job.next_attempt_at.isoformat() if job.next_attempt_at else None,
                    json.dumps(job.payload) if job.payload else None,
                    now.isoformat(),
                    now.isoformat(),
                ),
            )
            job.id = cur.lastrowid
        return job

    def get_due_jobs(self, limit: int = 50) -> list[Job]:
        now = datetime.utcnow().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT * FROM jobs
                WHERE status = 'pending' AND (next_attempt_at IS NULL OR next_attempt_at <= ?)
                ORDER BY created_at ASC
                LIMIT ?
                """,
                (now, limit),
            ).fetchall()
        return [self._row_to_job(r) for r in rows]

    def mark_running(self, job_id: int) -> None:
        now = datetime.utcnow().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE jobs SET status = 'running', updated_at = ? WHERE id = ?",
                (now, job_id),
            )

    def mark_done(self, job_id: int, result: dict[str, Any]) -> None:
        now = datetime.utcnow().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE jobs SET status = 'done', result = ?, updated_at = ? WHERE id = ?",
                (json.dumps(result), now, job_id),
            )

    def mark_failed(self, job_id: int, error: str) -> None:
        now = datetime.utcnow().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE jobs SET status = 'failed', error = ?, updated_at = ? WHERE id = ?",
                (error, now, job_id),
            )

    def schedule_retry(self, job: Job, exc: Exception) -> bool:
        if job.attempts + 1 >= job.max_attempts:
            return False
        delay = min(30 * (2 ** job.attempts), 600)
        next_at = datetime.utcnow().timestamp() + delay
        job.attempts += 1
        job.status = "retrying"
        job.next_attempt_at = datetime.utcnow().fromtimestamp(next_at)
        now = datetime.utcnow().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                UPDATE jobs SET attempts = ?, status = 'retrying', next_attempt_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (job.attempts, job.next_attempt_at.isoformat(), now, job.id),
            )
        return True

    def reset_stuck(self, older_than_minutes: int = 10) -> int:
        cutoff = datetime.utcnow().timestamp() - (older_than_minutes * 60)
        cutoff_iso = datetime.utcnow().fromtimestamp(cutoff).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "UPDATE jobs SET status = 'pending' WHERE status = 'running' AND updated_at < ?",
                (cutoff_iso,),
            )
            return cur.rowcount

    def _row_to_job(self, row: sqlite3.Row) -> Job:
        job = Job()
        job.id = row["id"]
        job.drop_id = row["drop_id"]
        job.platform = row["platform"]
        job.status = row["status"]
        job.attempts = row["attempts"]
        job.max_attempts = row["max_attempts"]
        job.next_attempt_at = datetime.fromisoformat(row["next_attempt_at"]) if row["next_attempt_at"] else None
        job.payload = json.loads(row["payload"]) if row["payload"] else None
        job.result = json.loads(row["result"]) if row["result"] else None
        job.error = row["error"]
        job.created_at = datetime.fromisoformat(row["created_at"]) if row["created_at"] else None
        job.updated_at = datetime.fromisoformat(row["updated_at"]) if row["updated_at"] else None
        return job
