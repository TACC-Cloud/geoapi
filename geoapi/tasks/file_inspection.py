from geoapi.celery_app import app
from geoapi.db import create_task_session
from geoapi.models import User
from geoapi.tasks.jobs import EphemeralJobTask
from geoapi.utils.external_apis import TapisUtils


@app.task(bind=True, base=EphemeralJobTask, queue="default")
def inspect_files(
    self, user_id: int, system_id: str, path: str, recursive: bool = True
) -> list[dict]:
    """Expand ``path`` (file or directory) and probe each file on the worker.

    Returns a list of ``FileInspectResponse`` dicts (stored in the Celery result backend
    and read back by ``GET /files/inspect/{task_id}``). ``EphemeralJobTask`` moves the
    Task row RUNNING -> COMPLETED; ``GeoAPITask.on_failure`` marks it FAILED on error.
    """
    from geoapi.services.file_inspection import probe, list_tapis_files

    with create_task_session() as session:
        user = session.get(User, user_id)
        client = TapisUtils(session, user)
        return [
            probe(client, system_id, p).model_dump()
            for p in list_tapis_files(client, system_id, path, recursive)
        ]


@app.task(bind=True, base=EphemeralJobTask, queue="default")
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
        user = session.get(User, user_id)
        client = TapisUtils(session, user)
        return build_list_entries(client, system_id, path, recursive)
