from pathlib import Path

import pytest

from socialdrop.jobs import Job, JobQueue


@pytest.fixture
def tmp_db(tmp_path: Path) -> Path:
    db = tmp_path / "jobs.db"
    return db


def test_enqueue_and_get_due(tmp_path: Path):
    queue = JobQueue(db_path=tmp_path / "jobs.db")
    job = Job(drop_id="drop1", platform="youtube", payload={"md_path": "drop1.md"})
    saved = queue.enqueue(job)
    assert saved.id is not None
    due = queue.get_due_jobs()
    assert len(due) == 1
    assert due[0].drop_id == "drop1"


def test_mark_done_and_failed(tmp_path: Path):
    queue = JobQueue(db_path=tmp_path / "jobs.db")
    job = Job(drop_id="drop1", platform="youtube")
    saved = queue.enqueue(job)
    assert saved.id is not None
    queue.mark_done(saved.id, {"url": "https://youtu.be/1"})
    assert saved.id is not None
    queue.mark_failed(saved.id, "boom")
    due = queue.get_due_jobs()
    assert len(due) == 0


def test_schedule_retry(tmp_path: Path):
    queue = JobQueue(db_path=tmp_path / "jobs.db")
    job = Job(drop_id="drop1", platform="youtube", max_attempts=3)
    saved = queue.enqueue(job)
    retried = queue.schedule_retry(saved, Exception("timeout"))
    assert retried is True
    assert saved.attempts == 1
    assert saved.status == "retrying"
    assert saved.next_attempt_at is not None


def test_reset_stuck(tmp_path: Path):
    queue = JobQueue(db_path=tmp_path / "jobs.db")
    job = Job(drop_id="drop1", platform="youtube")
    saved = queue.enqueue(job)
    assert saved.id is not None
    queue.mark_running(saved.id)
    reset = queue.reset_stuck(older_than_minutes=0)
    assert reset == 1
    due = queue.get_due_jobs()
    assert len(due) == 1
