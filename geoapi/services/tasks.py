"""Task helpers. For now, only ephemeral tasks: submitted, polled, then deleted (see
``geoapi.tasks.utils.EphemeralTask`` for how they differ from durable tasks).

Flow: ``submit_ephemeral`` creates a QUEUED ``Task`` (owned by the user, with
``expires_at`` set) and dispatches the Celery task using the Task's ``process_id`` as the
Celery id. The worker moves the row RUNNING -> COMPLETED (or FAILED via
``GeoAPITask.on_failure``). ``get_ephemeral`` reads the row and, once COMPLETED, the
return value from the Celery result backend.

Results live only in the Celery result backend (``RESULT_EXPIRES``, 1 day); the Task row
outlives them (``EPHEMERAL_TASK_TTL``) so a late poll gets EXPIRED rather than a 404. The
``cleanup_expired_tasks`` beat task deletes rows past ``expires_at``.
"""

import uuid
from datetime import datetime, timezone
from typing import Any

from celery.result import AsyncResult
from litestar.exceptions import NotFoundException, PermissionDeniedException
from sqlalchemy import delete
from sqlalchemy.orm import Session

from geoapi.celery_app import RESULT_EXPIRES
from geoapi.celery_app import app as celery_app
from geoapi.log import logger
from geoapi.models import Task, TaskStatus

# Reported by get_ephemeral only -- never stored on the Task row (TaskStatus doesn't
# include it).
EXPIRED = "EXPIRED"

# How long an ephemeral Task row is kept. Twice RESULT_EXPIRES so a stale poll gets a
# helpful EXPIRED status before the row is deleted (then it's a clean 404).
EPHEMERAL_TASK_TTL = 2 * RESULT_EXPIRES


class TaskService:
    @staticmethod
    def submit_ephemeral(
        session: Session, user_id: int, celery_task, args: list, description: str
    ) -> Task:
        """Create a QUEUED ephemeral Task for ``user_id`` and dispatch
        ``celery_task(*args)``. ``celery_task`` should use ``EphemeralTask`` as its base.

        The Task row is committed *before* dispatch so the worker (or an eager run in
        tests) can find it by ``process_id``.
        """
        process_id = str(uuid.uuid4())
        task = Task(
            process_id=process_id,
            status=TaskStatus.QUEUED,
            description=description,
            user_id=user_id,
            expires_at=datetime.now(timezone.utc) + EPHEMERAL_TASK_TTL,
        )
        session.add(task)
        session.commit()

        try:
            celery_task.apply_async(args=args, task_id=process_id)
        except Exception as exc:
            # e.g. broker unreachable: don't leave a QUEUED row that will never run.
            logger.exception(f"Failed to dispatch task:{task.id} ({description})")
            task.status = TaskStatus.ERROR
            task.latest_message = f"Failed to dispatch task: {exc}"
            session.commit()
            raise

        # An eager run (tests) may already have moved the row on; pick that up.
        session.refresh(task)
        return task

    @staticmethod
    def get_ephemeral(
        session: Session, task_id: int, user_id: int
    ) -> tuple[Task, str, Any | None, str | None]:
        """Return ``(task, status, result, error)`` for an ephemeral task owned by
        ``user_id``.

        ``result`` is the Celery return value once COMPLETED (else ``None``); ``error`` is
        set for FAILED / ERROR / EXPIRED. Raises 404 if there is no such ephemeral task
        (durable tasks don't count) and 403 if it belongs to another user.
        """
        task = session.get(Task, task_id)
        if task is None or task.expires_at is None:
            raise NotFoundException(f"No task found with id {task_id}")
        if task.user_id != user_id:
            raise PermissionDeniedException("Access denied")
        session.refresh(task)  # the worker updates the row from another session

        status = task.status
        if status == TaskStatus.COMPLETED:
            async_result = AsyncResult(task.process_id, app=celery_app)
            if async_result.successful():
                return task, status, async_result.result, None
            # COMPLETED is only set after the result is stored (see EphemeralTask), so a
            # missing result means the backend has already dropped it.
            return (
                task,
                EXPIRED,
                None,
                "The task's result is no longer available; submit it again.",
            )

        if status in (TaskStatus.FAILED, TaskStatus.ERROR):
            return task, status, None, task.latest_message or f"Task {status.lower()}"

        if task.expires_at <= datetime.now(timezone.utc):
            return task, EXPIRED, None, "The task expired before it finished."

        return task, status, None, None

    @staticmethod
    def delete_expired(session: Session) -> int:
        """Delete Task rows whose ``expires_at`` has passed. Returns how many were
        deleted."""
        result = session.execute(
            delete(Task).where(
                Task.expires_at.is_not(None),
                Task.expires_at <= datetime.now(timezone.utc),
            )
        )
        session.commit()
        return result.rowcount or 0
