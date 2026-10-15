from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from litestar.exceptions import NotFoundException, PermissionDeniedException

from geoapi.models import Task, TaskStatus
from geoapi.services import jobs


def _task(db_session, user, status=TaskStatus.QUEUED, expires_at=None, message=None):
    task = Task(
        process_id=f"proc-{datetime.now().timestamp()}",
        status=status,
        description="test job",
        user_id=user.id,
        expires_at=expires_at,
        latest_message=message,
    )
    db_session.add(task)
    db_session.commit()
    return task


def _ago(**kw):
    return datetime.now(timezone.utc) - timedelta(**kw)


def _from_now(**kw):
    return datetime.now(timezone.utc) + timedelta(**kw)


def test_submit_job_creates_queued_task_and_dispatches(db_session, user1):
    celery_task = MagicMock()
    task = jobs.submit_job(
        db_session, user1.id, celery_task, ["a", 1], "Doing a thing", expires_hours=2
    )
    assert task.id is not None
    assert task.status == TaskStatus.QUEUED
    assert task.user_id == user1.id
    assert task.description == "Doing a thing"
    assert _from_now(hours=1) < task.expires_at <= _from_now(hours=2)
    celery_task.apply_async.assert_called_once_with(
        args=["a", 1], task_id=task.process_id
    )


def test_submit_job_without_expiry_keeps_task(db_session, user1):
    task = jobs.submit_job(db_session, user1.id, MagicMock(), [], "durable")
    assert task.expires_at is None


def test_submit_job_dispatch_failure_marks_error(db_session, user1):
    celery_task = MagicMock()
    celery_task.apply_async.side_effect = ConnectionError("broker down")
    with pytest.raises(ConnectionError):
        jobs.submit_job(db_session, user1.id, celery_task, [], "boom")
    task = db_session.query(Task).filter(Task.description == "boom").one()
    assert task.status == TaskStatus.ERROR
    assert "broker down" in task.latest_message


def test_get_job_not_found(db_session, user1):
    with pytest.raises(NotFoundException):
        jobs.get_job(db_session, 999999, user1.id)


def test_get_job_other_user_forbidden(db_session, user1, user2):
    task = _task(db_session, user1)
    with pytest.raises(PermissionDeniedException):
        jobs.get_job(db_session, task.id, user2.id)


def test_get_job_running(db_session, user1):
    task = _task(db_session, user1, TaskStatus.RUNNING, expires_at=_from_now(hours=1))
    _, status, result, error = jobs.get_job(db_session, task.id, user1.id)
    assert (status, result, error) == ("RUNNING", None, None)


def test_get_job_failed_reports_message(db_session, user1):
    task = _task(db_session, user1, TaskStatus.FAILED, message="kaboom")
    _, status, result, error = jobs.get_job(db_session, task.id, user1.id)
    assert (status, result, error) == ("FAILED", None, "kaboom")


def test_get_job_unfinished_past_expiry_is_expired(db_session, user1):
    task = _task(db_session, user1, TaskStatus.RUNNING, expires_at=_ago(minutes=1))
    _, status, result, error = jobs.get_job(db_session, task.id, user1.id)
    assert status == jobs.EXPIRED
    assert result is None and error


def test_get_job_completed_returns_result(db_session, user1, monkeypatch):
    task = _task(db_session, user1, TaskStatus.COMPLETED)
    fake = MagicMock()
    fake.successful.return_value = True
    fake.result = [{"path": "/a.tif"}]
    monkeypatch.setattr(jobs, "AsyncResult", lambda *a, **kw: fake)
    _, status, result, error = jobs.get_job(db_session, task.id, user1.id)
    assert (status, result, error) == ("COMPLETED", [{"path": "/a.tif"}], None)


def test_get_job_completed_but_result_gone_is_expired(db_session, user1, monkeypatch):
    task = _task(db_session, user1, TaskStatus.COMPLETED)
    fake = MagicMock()
    fake.successful.return_value = False  # backend dropped it (PENDING)
    monkeypatch.setattr(jobs, "AsyncResult", lambda *a, **kw: fake)
    _, status, result, error = jobs.get_job(db_session, task.id, user1.id)
    assert status == jobs.EXPIRED
    assert result is None and error


def test_cleanup_expired_tasks_only_deletes_expired(db_session, user1):
    expired = _task(db_session, user1, TaskStatus.COMPLETED, expires_at=_ago(hours=1))
    fresh = _task(
        db_session, user1, TaskStatus.COMPLETED, expires_at=_from_now(hours=1)
    )
    durable = _task(db_session, user1, TaskStatus.COMPLETED, expires_at=None)
    expired_id, fresh_id, durable_id = expired.id, fresh.id, durable.id

    assert jobs.cleanup_expired_tasks(db_session) == 1
    db_session.expire_all()
    assert db_session.get(Task, expired_id) is None
    assert db_session.get(Task, fresh_id) is not None
    assert db_session.get(Task, durable_id) is not None
