import requests

import celery

from geoapi.log import logger
from geoapi.models import Task, TaskStatus, User
from geoapi.settings import settings
from geoapi.utils.client_backend import get_deployed_geoapi_url
from geoapi.db import create_task_session


class GeoAPITask(celery.Task):
    """
    Base Celery task for GeoAPI workflows.

    This task provides a safety-net failure handler that updates the GeoAPI
    Task database record when an unexpected exception escapes the task body.
    """

    abstract = True  # don't register this as a concrete Celery task

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        logger.error(f"[Task Failure] {self.name} ({task_id}): {exc}")

        # NOTE: If retryable tasks are introduced, handle celery.exceptions.Retry
        # here so retries do not trigger FAILED status updates.

        try:
            with create_task_session() as session:
                task = session.query(Task).filter(Task.process_id == task_id).first()

                if not task:
                    return

                # Only mark FAILED if the task didn't explicitly set some other terminal state
                if task.status != TaskStatus.FAILED:
                    task.status = TaskStatus.FAILED
                    task.last_message = str(exc)
                    session.add(task)
                    session.commit()

        except Exception as error:
            logger.exception(
                f"[Task Failure] Error updating Task status for {task_id}: {error}"
            )


def send_progress_update(user: User, task_id: str, status: str, message: str) -> None:
    """Send task update payload to webhook."""
    base_url = (
        get_deployed_geoapi_url()
        if settings.APP_ENV != "local"
        else "http://geoapi_backend:8000"
    )
    url = f"{base_url}/webhooks/task-update"
    payload = {
        "task_id": str(task_id),
        "status": status,
        "message": message,
    }
    headers = {"X-Tapis-Token": user.jwt}
    try:
        requests.post(url, json=payload, headers=headers, timeout=2)
    except requests.RequestException:
        logger.exception(
            "Failed to send progress update for task %s, user %s with status %s",
            task_id,
            user,
            status,
        )


def _map_task_status_to_notification(status: TaskStatus) -> str | None:
    """
    Map TaskStatus to frontend notification status: 'success' | 'error'.
    Returns None for statuses that shouldn't trigger notifications.
    """
    mapping = {
        TaskStatus.COMPLETED: "success",
        TaskStatus.FAILED: "error",
        TaskStatus.ERROR: "error",
        # QUEUED and RUNNING don't trigger notifications
        TaskStatus.QUEUED: None,
        TaskStatus.RUNNING: None,
    }
    return mapping.get(status)


def update_task_and_send_progress_update(
    database_session,
    user: User,
    task_id: int,
    status: TaskStatus = TaskStatus.RUNNING,
    latest_message: str = "",
) -> None:
    """
    Update task status and latest_message, then send progress update to user.

    Progress/notification update is only sent to user when the task is at
    a terminal state; see _map_task_status_to_notification
    """
    t = database_session.get(Task, task_id)
    t.status = status.value
    t.latest_message = latest_message
    database_session.add(t)
    database_session.commit()

    notification_status = _map_task_status_to_notification(status)
    if notification_status is not None:
        send_progress_update(user, t.process_id, notification_status, latest_message)
