from geoapi.celery_app import app
from geoapi.db import create_task_session
from geoapi.models import User
from geoapi.utils.external_apis import TapisUtils


@app.task
def inspect_files(
    user_id: int, system_id: str, path: str, recursive: bool = True
) -> list[dict]:
    """Expand ``path`` (file or directory) and probe each file on the worker.

    Builds a Tapis client for ``user_id`` and returns a list of ``FileInspectResponse``
    dicts (Celery results must be JSON-friendly) -- one per file; a single file yields a
    list of one.
    """
    from geoapi.services.file_inspection import probe, list_tapis_files

    with create_task_session() as session:
        user = session.get(User, user_id)
        client = TapisUtils(session, user)
        return [
            probe(client, system_id, p).model_dump()
            for p in list_tapis_files(client, system_id, path, recursive)
        ]
