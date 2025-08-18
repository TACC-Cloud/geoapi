import requests
from geoapi.models import User
from geoapi.log import logger


def send_progress_update(user: User, task_id: str, status: str, message: str) -> None:
    """Send task update payload to webhook."""
    url = "http://geoapi_backend:8000/api/webhooks/task-update"
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
