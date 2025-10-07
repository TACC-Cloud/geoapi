import requests
from geoapi.log import logger
from geoapi.models import Task, TaskStatus, User
from geoapi.settings import settings
from geoapi.utils.client_backend import get_deployed_geoapi_url


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


def update_task_and_send_progress_update(
    database_session,
    user: User,
    task_id: int,
    status: TaskStatus = TaskStatus.RUNNING,
    latest_message: str = "",
) -> None:
    """
    Update task status and latest_message, then send progress update to user.
    """
    t = database_session.get(Task, task_id)
    t.status = status.value
    t.latest_message = latest_message
    database_session.add(t)
    database_session.commit()

    send_progress_update(user, t.process_id, status.value.lower(), latest_message)
