"""Submit/poll helpers for short-lived ("ephemeral") Celery jobs backed by a ``Task`` row.

Flow: ``submit_job`` creates a QUEUED ``Task`` (owned by the user, with an optional
``expires_at``) and dispatches the Celery task using the Task's ``process_id`` as the
Celery id. The worker moves the row RUNNING -> COMPLETED (or FAILED via
``GeoAPITask.on_failure``). ``get_job`` reads the row and, once COMPLETED, the return
value from the Celery result backend.

Results live only in the Celery result backend (``result_expires``, ~1 day by default);
the Task row outlives them (``expires_at``) so a late poll gets EXPIRED rather than a
404. ``cleanup_expired_tasks`` (a beat job) deletes rows past ``expires_at``.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from celery.result import AsyncResult
from litestar.exceptions import NotFoundException, PermissionDeniedException
from sqlalchemy import delete
from sqlalchemy.orm import Session

from geoapi.celery_app import app as celery_app
from geoapi.log import logger
from geoapi.models import Task, TaskStatus

# Reported by get_job only -- never stored on the Task row (TaskStatus doesn't include it).
EXPIRED = "EXPIRED"


def submit_job(
    session: Session,
    user_id: int,
    celery_task,
    args: list,
    description: str,
    expires_hours: float | None = None,
) -> Task:
    """Create a QUEUED Task for ``user_id`` and dispatch ``celery_task(*args)``.

    The Task row is committed *before* dispatch so the worker (or an eager run in tests)
    can find it by ``process_id``. ``expires_hours`` sets ``expires_at``; ``None`` keeps
    the row indefinitely.
    """
    process_id = str(uuid.uuid4())
    expires_at = (
        datetime.now(timezone.utc) + timedelta(hours=expires_hours)
        if expires_hours is not None
        else None
    )
    task = Task(
        process_id=process_id,
        status=TaskStatus.QUEUED,
        description=description,
        user_id=user_id,
        expires_at=expires_at,
    )
    session.add(task)
    session.commit()

    try:
        celery_task.apply_async(args=args, task_id=process_id)
    except Exception as exc:
        # e.g. broker unreachable: don't leave a QUEUED row that will never run.
        logger.exception(f"Failed to dispatch job task:{task.id} ({description})")
        task.status = TaskStatus.ERROR
        task.latest_message = f"Failed to dispatch job: {exc}"
        session.commit()
        raise

    # An eager run (tests) may already have moved the row on; pick that up.
    session.refresh(task)
    return task


def get_job(
    session: Session, task_id: int, user_id: int
) -> tuple[Task, str, Any | None, str | None]:
    """Return ``(task, status, result, error)`` for a job owned by ``user_id``.

    ``result`` is the Celery return value once COMPLETED (else ``None``); ``error`` is
    set for FAILED / ERROR / EXPIRED. Raises 404 if the task doesn't exist and 403 if it
    belongs to another user.
    """
    task = session.get(Task, task_id)
    if task is None:
        raise NotFoundException(f"No job found with id {task_id}")
    if task.user_id != user_id:
        raise PermissionDeniedException("Access denied")
    session.refresh(task)  # the worker updates the row from another session

    status = task.status
    if status == TaskStatus.COMPLETED:
        async_result = AsyncResult(task.process_id, app=celery_app)
        if async_result.successful():
            return task, status, async_result.result, None
        # COMPLETED is only set after the result is stored (see EphemeralJobTask), so a
        # missing result means the backend has already dropped it.
        return (
            task,
            EXPIRED,
            None,
            "The job's result is no longer available; submit the job again.",
        )

    if status in (TaskStatus.FAILED, TaskStatus.ERROR):
        return task, status, None, task.latest_message or f"Job {status.lower()}"

    if task.expires_at is not None and task.expires_at <= datetime.now(timezone.utc):
        return task, EXPIRED, None, "The job expired before it finished."

    return task, status, None, None


def cleanup_expired_tasks(session: Session) -> int:
    """Delete Task rows whose ``expires_at`` has passed. Returns how many were deleted."""
    result = session.execute(
        delete(Task).where(
            Task.expires_at.is_not(None),
            Task.expires_at <= datetime.now(timezone.utc),
        )
    )
    session.commit()
    return result.rowcount or 0
