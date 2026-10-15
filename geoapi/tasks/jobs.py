from geoapi.celery_app import app
from geoapi.db import create_task_session
from geoapi.log import logger
from geoapi.models import Task, TaskStatus
from geoapi.tasks.utils import GeoAPITask


def mark_task(session, process_id: str, status: TaskStatus) -> None:
    """Set the status of the Task row that owns this Celery job (keyed by ``process_id``,
    which ``submit_job`` set to the Celery id). No-op if the row is gone."""
    task = session.query(Task).filter(Task.process_id == process_id).first()
    if task:
        task.status = status
        session.commit()


class EphemeralJobTask(GeoAPITask):
    """Base for submit/poll jobs (see ``geoapi.services.jobs``).

    Marks the Task COMPLETED in ``on_success``, which Celery calls *after* storing the
    return value in the result backend -- so a poll that sees COMPLETED can always read
    the result. Failures are handled by ``GeoAPITask.on_failure`` (FAILED).
    """

    abstract = True

    def before_start(self, task_id, args, kwargs):
        with create_task_session() as session:
            mark_task(session, task_id, TaskStatus.RUNNING)

    def on_success(self, retval, task_id, args, kwargs):
        with create_task_session() as session:
            mark_task(session, task_id, TaskStatus.COMPLETED)


@app.task(queue="default")
def cleanup_expired_tasks() -> int:
    """Beat job: delete Task rows past their ``expires_at`` (ephemeral jobs)."""
    from geoapi.services.jobs import cleanup_expired_tasks as _cleanup

    with create_task_session() as session:
        deleted = _cleanup(session)
    logger.info(f"cleanup_expired_tasks: deleted {deleted} expired task(s)")
    return deleted
