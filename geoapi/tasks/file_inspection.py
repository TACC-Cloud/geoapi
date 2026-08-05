from geoapi.celery_app import app
from geoapi.db import create_task_session
from geoapi.models import Task, TaskStatus, User
from geoapi.tasks.utils import GeoAPITask
from geoapi.utils.external_apis import TapisUtils


def _mark_task(session, process_id: str, status: str) -> None:
    """Set the status of the Task row that owns this Celery job (keyed by ``process_id``,
    which the API set to the Celery id at submit time). No-op if the row is gone."""
    task = session.query(Task).filter(Task.process_id == process_id).first()
    if task:
        task.status = status
        session.commit()


@app.task(bind=True, base=GeoAPITask, queue="default")
def inspect_files(
    self, user_id: int, system_id: str, path: str, recursive: bool = True
) -> list[dict]:
    """Expand ``path`` (file or directory) and probe each file on the worker.

    Returns a list of ``FileInspectResponse`` dicts (stored in the Celery result backend
    and read back by ``GET /files/inspect/{task_id}``). Updates the Task row RUNNING ->
    COMPLETED; ``GeoAPITask.on_failure`` marks it FAILED on error.
    """
    from geoapi.services.file_inspection import probe, list_tapis_files

    with create_task_session() as session:
        _mark_task(session, self.request.id, TaskStatus.RUNNING)
        user = session.get(User, user_id)
        client = TapisUtils(session, user)
        results = [
            probe(client, system_id, p).model_dump()
            for p in list_tapis_files(client, system_id, path, recursive)
        ]
        _mark_task(session, self.request.id, TaskStatus.COMPLETED)
        return results


@app.task(bind=True, base=GeoAPITask, queue="default")
def list_files_task(
    self, user_id: int, system_id: str, path: str, recursive: bool = True
) -> list[dict]:
    """Cheap listing (extension-only geospatial guess) of a Tapis path on the worker.

    No geo CLIs, no fetch -- just Tapis listing calls. Async (same submit/poll pattern as
    inspect) because a recursive listing of a deep tree is one Tapis call per directory and
    can be slow. Returns ``FileListEntry`` dicts; read back by ``GET /files/list/{task_id}``.
    """
    from geoapi.services.file_inspection import build_list_entries

    with create_task_session() as session:
        _mark_task(session, self.request.id, TaskStatus.RUNNING)
        user = session.get(User, user_id)
        client = TapisUtils(session, user)
        results = build_list_entries(client, system_id, path, recursive)
        _mark_task(session, self.request.id, TaskStatus.COMPLETED)
        return results
